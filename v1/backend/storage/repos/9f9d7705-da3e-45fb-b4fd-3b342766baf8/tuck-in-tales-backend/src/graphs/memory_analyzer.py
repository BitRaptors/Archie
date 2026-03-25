"""
Memory Analyzer LangGraph pipeline.

Flow: analyze_memory_text -> analyze_photos -> save_analysis -> finish

1. Text analysis: categorize, detect known + new characters (OpenAI)
2. Photo analysis: per-photo person detection with known + new char matching (Groq vision)
3. Save results to DB with embeddings
4. Stream everything via SSE
"""

import json
import logging
from typing import TypedDict, List, Optional, Any
from uuid import UUID

from langgraph.graph import StateGraph, END, START

from src.utils.openai_client import async_openai_client, get_embedding
from src.utils.groq_client import async_groq_client, GroqError
from src.utils.supabase import get_supabase_client
from src.utils.sse import send_sse_event
from src.utils.prompt_resolver import resolve_prompt, get_prompt_config

logger = logging.getLogger(__name__)

MEMORY_PHOTOS_BUCKET = "memory-photos"
SIGNED_URL_EXPIRY = 300


# --- State ---

class MemoryAnalysisState(TypedDict):
    memory_id: str
    family_id: str
    text: Optional[str]
    photo_paths: List[str]
    characters_info: List[dict]  # [{id, name, bio, visual_description}]
    # Outputs from text analysis
    new_characters: List[dict]  # [{name, guessed_bio}]
    analysis: Optional[dict]  # full text analysis result
    # Outputs from photo analysis
    photo_results: List[dict]  # [{photo_index, description, detected_people}]
    photo_descriptions: List[str]  # flat list for embedding
    error_message: Optional[str]


# --- Helper ---

def _build_character_context(characters_info: List[dict]) -> str:
    """Build a text description of known characters for LLM context."""
    if not characters_info:
        return "No known characters yet."
    lines = []
    for c in characters_info:
        parts = [f"- {c['name']} (ID: {c['id']})"]
        if c.get('bio'):
            parts.append(f"  Bio: {c['bio']}")
        if c.get('visual_description'):
            parts.append(f"  Appearance: {c['visual_description']}")
        lines.append("\n".join(parts))
    return "\n".join(lines)


# --- Nodes ---

async def analyze_memory_text(state: MemoryAnalysisState) -> dict:
    """Analyze memory text to categorize, find known characters, detect new characters."""
    memory_id = state["memory_id"]
    text = state.get("text") or ""
    characters_info = state.get("characters_info", [])

    # For photo-only memories with no text, create a minimal analysis
    if not text:
        logger.info(f"[Memory {memory_id}] No text, skipping text analysis.")
        minimal_analysis = {
            "categories": ["context"],
            "summary": None,
            "linked_characters": [],
            "new_characters": [],
            "suggestions": [],
        }
        await send_sse_event(memory_id, "text_analysis_complete", minimal_analysis)
        return {"analysis": minimal_analysis, "new_characters": []}

    await send_sse_event(memory_id, "status", {"step": "analyzing_text", "message": "Analyzing memory text..."})

    character_context = _build_character_context(characters_info)

    config = get_prompt_config("memory_analysis")
    system_prompt, user_prompt = resolve_prompt("memory_analysis", {
        "memory_text": text,
        "photo_descriptions": "Photos will be analyzed separately.",
        "character_context": character_context,
    })

    try:
        accumulated_text = ""
        stream = await async_openai_client.chat.completions.create(
            model=config.get("model", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config.get("temperature", 0.3),
            max_tokens=config.get("max_tokens", 800),
            response_format=config.get("response_format", {"type": "json_object"}),
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                accumulated_text += token
                await send_sse_event(memory_id, "analysis_chunk", {"token": token})

        # Parse JSON
        try:
            analysis = json.loads(accumulated_text)
        except json.JSONDecodeError:
            logger.error(f"[Memory {memory_id}] Failed to parse analysis JSON: {accumulated_text[:200]}")
            analysis = {
                "categories": [],
                "summary": accumulated_text[:200],
                "linked_characters": [],
                "new_characters": [],
                "suggestions": [],
            }

        new_characters = analysis.get("new_characters", [])

        # Send structured result
        await send_sse_event(memory_id, "text_analysis_complete", {
            "categories": analysis.get("categories", []),
            "summary": analysis.get("summary"),
            "linked_characters": analysis.get("linked_characters", []),
            "new_characters": new_characters,
            "suggestions": analysis.get("suggestions", []),
        })

        return {"analysis": analysis, "new_characters": new_characters}

    except Exception as e:
        logger.error(f"[Memory {memory_id}] Error during text analysis: {e}", exc_info=True)
        error_msg = f"Text analysis failed: {e}"
        await send_sse_event(memory_id, "error", {"message": error_msg})
        return {"error_message": error_msg}


async def analyze_photos(state: MemoryAnalysisState) -> dict:
    """Analyze each photo, detecting known + new characters. Sends per-photo SSE events."""
    memory_id = state["memory_id"]
    photo_paths = state.get("photo_paths", [])

    if not photo_paths:
        logger.info(f"[Memory {memory_id}] No photos to analyze, skipping.")
        return {"photo_results": [], "photo_descriptions": []}

    if not async_groq_client:
        logger.warning(f"[Memory {memory_id}] Groq client not available, skipping photo analysis.")
        await send_sse_event(memory_id, "status", {"step": "photo_analysis", "message": "Photo analysis skipped (Groq not configured)."})
        return {"photo_results": [], "photo_descriptions": []}

    await send_sse_event(memory_id, "status", {"step": "photo_analysis", "message": f"Analyzing {len(photo_paths)} photo(s)..."})

    supabase = get_supabase_client()
    characters_info = state.get("characters_info", [])
    new_characters = state.get("new_characters", [])

    character_context = _build_character_context(characters_info)
    new_char_names = ", ".join([c.get("name", "") for c in new_characters]) if new_characters else "None"

    config = get_prompt_config("memory_photo_analysis")

    photo_results = []
    photo_descriptions = []

    for i, photo_path in enumerate(photo_paths):
        try:
            # Create signed URL
            signed_url_response = supabase.storage.from_(MEMORY_PHOTOS_BUCKET).create_signed_url(photo_path, SIGNED_URL_EXPIRY)
            signed_url = signed_url_response.get("signedURL")
            if not signed_url:
                logger.error(f"[Memory {memory_id}] Failed to create signed URL for {photo_path}")
                continue

            _, vision_prompt = resolve_prompt("memory_photo_analysis", {
                "character_context": character_context,
                "new_character_names": new_char_names,
            })

            model_name = config.get("model", "meta-llama/llama-4-scout-17b-16e-instruct")
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_prompt},
                        {"type": "image_url", "image_url": {"url": signed_url}},
                    ],
                }
            ]

            response = async_groq_client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=config.get("max_tokens", 500),
            )
            raw_response = response.choices[0].message.content or ""

            # Try to parse JSON from response (Groq may wrap in markdown or add explanation text)
            photo_result = None
            try:
                clean = raw_response.strip()
                # Strip markdown code blocks
                if "```" in clean:
                    # Extract content between first ``` and last ```
                    parts = clean.split("```")
                    for part in parts[1:]:
                        # Skip language identifier (e.g., "json\n")
                        candidate = part.strip()
                        if candidate.startswith("json"):
                            candidate = candidate[4:].strip()
                        if candidate.startswith("{"):
                            clean = candidate
                            break
                # If response has JSON embedded with surrounding text, extract it
                if not clean.startswith("{"):
                    # Find first { and last }
                    start = clean.find("{")
                    end = clean.rfind("}")
                    if start != -1 and end != -1 and end > start:
                        clean = clean[start:end + 1]
                photo_result = json.loads(clean)
            except (json.JSONDecodeError, IndexError, ValueError):
                logger.warning(f"[Memory {memory_id}] Photo {i+1} response not valid JSON, using as description")
                photo_result = {
                    "description": raw_response[:300],
                    "detected_people": [],
                }

            result = {
                "photo_index": i,
                "description": photo_result.get("description", raw_response[:200]),
                "detected_people": photo_result.get("detected_people", []),
            }

            photo_results.append(result)
            photo_descriptions.append(result["description"])

            # Send per-photo SSE event
            await send_sse_event(memory_id, "photo_analyzed", result)
            logger.info(f"[Memory {memory_id}] Photo {i+1}: {result['description'][:80]}... People: {[p.get('name') for p in result['detected_people']]}")

        except GroqError as e:
            logger.error(f"[Memory {memory_id}] Groq error analyzing photo {photo_path}: {e}")
            await send_sse_event(memory_id, "photo_analyzed", {
                "photo_index": i,
                "description": f"Photo analysis failed: {e}",
                "detected_people": [],
            })
        except Exception as e:
            logger.error(f"[Memory {memory_id}] Error analyzing photo {photo_path}: {e}", exc_info=True)

    return {"photo_results": photo_results, "photo_descriptions": photo_descriptions}


async def save_analysis(state: MemoryAnalysisState) -> dict:
    """Save analysis results to the database."""
    memory_id = state["memory_id"]
    analysis = state.get("analysis")

    if not analysis:
        logger.warning(f"[Memory {memory_id}] No analysis to save.")
        return {}

    supabase = get_supabase_client()

    try:
        linked_ids = [c["id"] for c in analysis.get("linked_characters", []) if c.get("id")]
        suggestions = analysis.get("suggestions", [])

        # Include new_characters and photo_results in raw_analysis
        full_analysis = {
            **analysis,
            "photo_results": state.get("photo_results", []),
        }

        update_data = {
            "categories": analysis.get("categories", []),
            "summary": analysis.get("summary"),
            "linked_character_ids": linked_ids,
            "raw_analysis": full_analysis,
            "suggestions": suggestions,
            "analysis_status": "ANALYZED",
        }

        # Generate embedding from combined text
        text = state.get("text") or ""
        summary = analysis.get("summary") or ""
        photo_desc_combined = " ".join(state.get("photo_descriptions", []))
        embedding_text = " ".join(filter(None, [text, summary, photo_desc_combined]))

        if embedding_text.strip():
            embedding = await get_embedding(embedding_text)
            update_data["embedding"] = embedding

        supabase.table("memories").update(update_data).eq("id", memory_id).execute()
        logger.info(f"[Memory {memory_id}] Analysis saved to database.")

    except Exception as e:
        logger.error(f"[Memory {memory_id}] Error saving analysis: {e}", exc_info=True)
        await send_sse_event(memory_id, "status", {"step": "save_warning", "message": f"Warning: could not save analysis: {e}"})

    return {}


async def finish(state: MemoryAnalysisState) -> dict:
    """Send done event to close the SSE stream."""
    memory_id = state["memory_id"]

    if state.get("error_message"):
        await send_sse_event(memory_id, "error", {"message": state["error_message"]})
    else:
        await send_sse_event(memory_id, "done", {
            "memory_id": memory_id,
            "analysis": state.get("analysis"),
            "photo_results": state.get("photo_results", []),
        })

    return {}


# --- Conditional Edges ---

def route_after_text(state: MemoryAnalysisState) -> str:
    if state.get("error_message"):
        return "finish"
    if state.get("photo_paths"):
        return "analyze_photos"
    return "save_analysis"


def route_after_photos(state: MemoryAnalysisState) -> str:
    if state.get("error_message"):
        return "finish"
    return "save_analysis"


# --- Graph Definition ---

workflow = StateGraph(MemoryAnalysisState)

workflow.add_node("analyze_memory_text", analyze_memory_text)
workflow.add_node("analyze_photos", analyze_photos)
workflow.add_node("save_analysis", save_analysis)
workflow.add_node("finish", finish)

# START -> text analysis always runs first
workflow.add_edge(START, "analyze_memory_text")

# After text: photos if available, otherwise save
workflow.add_conditional_edges("analyze_memory_text", route_after_text, {
    "analyze_photos": "analyze_photos",
    "save_analysis": "save_analysis",
    "finish": "finish",
})

# After photos: save
workflow.add_conditional_edges("analyze_photos", route_after_photos, {
    "save_analysis": "save_analysis",
    "finish": "finish",
})

workflow.add_edge("save_analysis", "finish")
workflow.add_edge("finish", END)

memory_analyzer_graph = workflow.compile()


async def run_memory_analysis(
    memory_id: str,
    family_id: str,
    text: Optional[str],
    photo_paths: List[str],
) -> None:
    """Entry point: run memory analysis pipeline."""
    logger.info(f"[Memory {memory_id}] Starting analysis pipeline...")

    supabase = get_supabase_client()
    characters_info = []
    try:
        response = supabase.table("characters")\
            .select("id, name, bio, visual_description")\
            .eq("family_id", family_id)\
            .execute()
        if response.data:
            characters_info = [
                {
                    "id": str(c["id"]),
                    "name": c["name"],
                    "bio": c.get("bio"),
                    "visual_description": c.get("visual_description"),
                }
                for c in response.data
            ]
    except Exception as e:
        logger.error(f"[Memory {memory_id}] Error fetching characters: {e}")

    try:
        supabase.table("memories").update({"analysis_status": "ANALYZING"}).eq("id", memory_id).execute()
    except Exception as e:
        logger.error(f"[Memory {memory_id}] Error updating status to ANALYZING: {e}")

    initial_state: MemoryAnalysisState = {
        "memory_id": memory_id,
        "family_id": family_id,
        "text": text,
        "photo_paths": photo_paths,
        "characters_info": characters_info,
        "new_characters": [],
        "analysis": None,
        "photo_results": [],
        "photo_descriptions": [],
        "error_message": None,
    }

    try:
        await memory_analyzer_graph.ainvoke(initial_state)
        logger.info(f"[Memory {memory_id}] Analysis pipeline completed.")
    except Exception as e:
        logger.error(f"[Memory {memory_id}] Analysis pipeline failed: {e}", exc_info=True)
        try:
            supabase.table("memories").update({"analysis_status": "FAILED"}).eq("id", memory_id).execute()
        except Exception as db_err:
            logger.error(f"[Memory {memory_id}] Error updating status to FAILED: {db_err}")
        await send_sse_event(memory_id, "error", {"message": f"Analysis failed: {e}"})
