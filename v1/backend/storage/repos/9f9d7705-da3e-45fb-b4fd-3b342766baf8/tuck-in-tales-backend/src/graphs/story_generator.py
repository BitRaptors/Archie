import operator
import json
import httpx
import uuid
import base64
import io
import mimetypes
import logging
import asyncio
from typing import TypedDict, Annotated, Sequence, Dict, Any, List, Tuple, Optional
from uuid import uuid4
from datetime import datetime

from fastapi import HTTPException
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from supabase import Client
# from langgraph.checkpoint.sqlite import SqliteSaver # Remove checkpointer import

from src.config import settings
from src.utils.openai_client import async_openai_client, get_embedding
from src.utils.gemini_client import async_gemini_client, generate_image_with_gemini
from src.utils.sse import send_sse_event
from src.utils.supabase import get_supabase_client
from src.utils.prompt_resolver import resolve_prompt, get_prompt_config

# --- Global State --- 
# Removed client_wait_events and client_pause_requests

# --- Checkpointer Setup --- 
# Removed checkpointer setup
# memory_saver = SqliteSaver.from_conn_string("checkpoints.sqlite") 

# --- SSE Message Helpers ---
async def send_sse_status(story_id: str | None, message: str, step: str | None = None, page: int | None = None, total_pages: int | None = None):
    if story_id:
        payload = {"message": message}
        if step: payload["step"] = step
        if page is not None: payload["page"] = page
        if total_pages is not None: payload["total_pages"] = total_pages
        await send_sse_event(story_id, "status", payload)

async def send_sse_error(story_id: str | None, message: str, step: str | None = None, page: int | None = None):
    if story_id:
        payload = {"message": message}
        if step: payload["step"] = step
        if page is not None: payload["page"] = page
        await send_sse_event(story_id, "error", payload)

# --- Language Mapping --- 
# Keep this in sync with frontend SUPPORTED_LANGUAGES
LANGUAGE_CODE_TO_NAME = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese", # Assuming general Portuguese for LLM
    "ru": "Russian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese (Simplified)",
    "hi": "Hindi",
    "ar": "Arabic",
    "bn": "Bengali",
    "ur": "Urdu",
    "id": "Indonesian",
    "nl": "Dutch",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "pl": "Polish",
    "th": "Thai",
    "fa": "Persian (Farsi)",
    "ro": "Romanian",
    "el": "Greek",
    "he": "Hebrew",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "cs": "Czech",
    "hu": "Hungarian", # Added Hungarian
    "ms": "Malay",
    "sw": "Swahili",
    "af": "Afrikaans",
    "fil": "Filipino",
    "uk": "Ukrainian",
    "bg": "Bulgarian",
    "sk": "Slovak",
    "hr": "Croatian",
    "sr": "Serbian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "sl": "Slovenian",
    "is": "Icelandic",
    "ga": "Irish",
    "cy": "Welsh",
    "ca": "Catalan",
    "eu": "Basque",
    "gl": "Galician",
    # Add more as needed
}

def get_language_name(code: Optional[str]) -> str:
    """Gets the full language name from code, defaulting to English."""
    return LANGUAGE_CODE_TO_NAME.get(code or 'en', "English") # Default to English if code is None or not found

# --- 1. Define the State (Simplified for DB-driven approach) --- 
CharacterInfo = TypedDict("CharacterInfo", {
    "id": str, 
    "name": str, 
    "bio": str | None, 
    "birth_date": str | None, # Add birth_date field
    "avatar_url": str | None, # Path in storage
    "visual_description": str | None, # Added visual_description field
})
# StoryPageData is now defined in models/story.py as StoryPageProgress
# We don't need to store full pages in graph state anymore

class StoryGenerationState(TypedDict):
    # Core identifier passed through the graph
    story_id: str
    # Initial context needed by multiple nodes (passed from trigger)
    characters_info: Sequence[CharacterInfo] | None 
    language_code: str | None # Store the language code
    # Optional fields populated/used during the graph run
    language_name: str | None # Store the full language name
    # Optional fields that nodes might update locally before DB update
    # Or fields fetched from DB for use in subsequent nodes
    # Example: downloaded_avatars could still be useful if fetched once
    num_pages: int | None # Optional: requested number of pages
    downloaded_avatars: Dict[str, Tuple[str, bytes, str]] | None # Track downloaded avatar data
    consistency_retry_count: int # Number of retries for current page consistency check (0-2)
    consistency_feedback: str | None # Issues found by consistency check, passed to write_page on retry
    # Fields previously needed for checkpointer/SSE are removed or handled differently
    # - input_prompt, target_age, language: fetched from DB via story_id if needed
    # - story_outline: outline is now stored in DB pages array
    # - retrieved_memories: fetched/used within a node, maybe not passed in state
    # - story_pages: managed entirely in the DB record
    # - current_step: implicitly tracked by node execution, status in DB
    # - family_id: can be derived from story_id via DB lookup if needed
    # - saved_story_id: story_id is known from the start

# --- 2. Define Graph Nodes (Updates needed) ---

# --- Function to fetch characters by name from DB (helper) ---
async def fetch_characters_by_names(family_id: str, names: List[str]) -> List[Dict[str, Any]]:
    """Fetches character records from DB by name for a given family (case-insensitive)."""
    if not names:
        return []
    try:
        supabase_client: Client = get_supabase_client()
        response = (
            supabase_client.table("characters")
            .select("id, name, bio, avatar_url, birthdate, visual_description")
            .eq("family_id", family_id)
            .execute()
        )
        if not response.data:
            return []
        # Case-insensitive match
        names_lower = {n.lower() for n in names}
        return [c for c in response.data if c["name"].lower() in names_lower]
    except Exception as e:
        logging.warning(f"Failed to fetch characters by names for family {family_id}: {e}")
        return []

# --- Function to fetch story data (helper) ---
async def get_story_data(story_id: str) -> Dict[str, Any]:
    """Fetches the current story record from Supabase."""
    try:
        supabase_client: Client = get_supabase_client()
        response = supabase_client.table("stories").select("*").eq("id", story_id).maybe_single().execute()
        if response.data:
            return response.data
        else:
            raise ValueError(f"Story not found in DB with ID: {story_id}")
    except Exception as e:
        logging.error(f"Error fetching story data for {story_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error fetching story {story_id}")

# --- Function to update story data (helper) ---
async def update_story_data(story_id: str, updates: Dict[str, Any]):
    """Updates specific fields of a story record in Supabase."""
    try:
        supabase_client: Client = get_supabase_client()
        response = supabase_client.table("stories").update(updates).eq("id", story_id).execute()
        # Add check? response.data might be empty on success for update
        if hasattr(response, 'error') and response.error:
             raise Exception(f"DB update error: {response.error}")
        logging.info(f"Story {story_id} updated with keys: {list(updates.keys())}")
    except Exception as e:
        logging.error(f"Error updating story data for {story_id}: {e}", exc_info=True)
        # Don't raise HTTPException here, let the node handle flow
        raise e # Re-raise the original error for the node's catch block

# --- Nodes refactored to use story_id and DB updates ---

# Helper function to format character details for prompts
def _prepare_character_context(characters_info: Sequence[CharacterInfo] | None, include_visual: bool = False) -> str:
    """Formats character information into a string for LLM context."""
    if not characters_info:
        return "No specific characters mentioned."
    
    char_parts = []
    for c in characters_info:
        char_str = f"{c['name']}"
        if c.get('birth_date'):
            char_str += f" (Born: {c['birth_date']})"
        if c.get('bio'):
            char_str += f" - {c['bio']}"
        if include_visual and c.get('visual_description'):
             # Keep it concise for the context
             desc = c['visual_description']
             char_str += f" - Looks: {desc[:150]}..." if len(desc) > 150 else f" - Looks: {desc}"
        char_parts.append(char_str)
        
    return "Characters: " + "; ".join(char_parts)

async def determine_language_name(state: StoryGenerationState):
    """Maps the language_code to language_name and updates state."""
    story_id = state['story_id']
    language_code = state.get('language_code', 'en') # Default to 'en' if not passed
    language_name = get_language_name(language_code)
    logging.info(f"[{story_id}] Determined language name: '{language_name}' from code: '{language_code}'")
    return { "language_name": language_name }

async def generate_initial_outline(state: StoryGenerationState):
    story_id = state["story_id"]
    characters_info = state.get("characters_info", [])
    language_name = state.get("language_name", "English") # Get language name from state
    step_name = "generate_outline"
    await send_sse_status(story_id, "Fetching story details for outline...", step=step_name)
    
    try:
        # 1. Fetch story data from DB
        story_data = await get_story_data(story_id)
        prompt = story_data.get('input_prompt', "A simple children's story.")
        target_age = story_data.get('target_age')
        
        # 2. Prepare context for LLM (using characters_info from state)
        # Use the helper function
        char_desc = _prepare_character_context(characters_info)
        age_context = f" The story should be appropriate for a {target_age}-year-old child." if target_age else ""

        # Determine page count instruction
        num_pages = state.get("num_pages")
        if num_pages:
            num_pages_instruction = f"exactly {num_pages} pages"
        else:
            num_pages_instruction = "3-5 pages"

        print(f"Generating outline for story {story_id} based on: {prompt}, pages: {num_pages_instruction}")

        # 3. Construct LLM messages from DB-driven prompts
        prompt_config = get_prompt_config("story_outline")
        system_msg, user_msg = resolve_prompt("story_outline", {
            "language_name": language_name,
            "story_prompt": prompt,
            "character_context": char_desc,
            "age_context": age_context,
            "num_pages": num_pages_instruction,
        })
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ]

        # 4. Call LLM
        model_kwargs = {}
        if prompt_config.get("response_format"):
            model_kwargs["response_format"] = prompt_config["response_format"]
        llm = ChatOpenAI(
            model=prompt_config["model"],
            temperature=prompt_config["temperature"] or 0.2,
            openai_api_key=settings.OPENAI_API_KEY,
            model_kwargs=model_kwargs
        )
        await send_sse_status(story_id, "Calling LLM for outline...", step=step_name)
        response = await llm.ainvoke(messages)
        
        # 5. Parse Outline
        outline_json_str = response.content
        logging.info(f"[{story_id}] Outline LLM response type={type(outline_json_str)}, len={len(outline_json_str) if isinstance(outline_json_str, str) else 'N/A'}, repr={repr(outline_json_str)[:200]}")
        if not outline_json_str or not isinstance(outline_json_str, str):
             raise ValueError(f"LLM returned unexpected outline content type: {type(outline_json_str)}")
        # Strip markdown code fences if present
        stripped = outline_json_str.strip()
        if stripped.startswith("```"):
            stripped = stripped.split("\n", 1)[1] if "\n" in stripped else stripped[3:]
            if stripped.endswith("```"):
                stripped = stripped[:-3]
            stripped = stripped.strip()
        outline_data = json.loads(stripped)
        print(f"LLM generated outline for {story_id}: {outline_data}")
        
        # --- Extract Title and Outline --- 
        generated_title = outline_data.get('title')
        outline_pages = outline_data.get('outline')
        # Basic validation
        if not generated_title or not isinstance(generated_title, str):
             logging.warning(f"LLM response missing or invalid 'title'. Using default.")
             generated_title = "A Fun Bedtime Story"
        if not outline_pages or not isinstance(outline_pages, list):
            raise ValueError("LLM outline JSON did not contain a valid 'outline' list.")
        # ----------------------------------
            
        # 6. Create initial pages structure for DB
        # Build case-insensitive lookup: LLM names -> DB names
        char_name_lookup = {}
        if characters_info:
            for c in characters_info:
                char_name_lookup[c['name'].lower()] = c['name']

        initial_pages_db = [
            { # Conforms to StoryPageProgress structure
                "page": p.get("page"),
                "description": p.get("description"),
                "text": None,
                "image_prompt": None,
                "image_url": None,
                "characters_on_page": [
                    char_name_lookup.get(name.lower(), name)
                    for name in (p.get("characters") or [])
                ]
            }
            for p in outline_pages if p.get("page") and p.get("description") # Basic validation
        ]
        
        if not initial_pages_db:
            raise ValueError("Failed to parse valid pages from LLM outline.")
            
        total_pages = len(initial_pages_db)
        # Add logging for the number of pages planned
        logging.info(f"[{story_id}] LLM generated outline with {total_pages} pages.")

        # 6b. Build story-level debug prompts
        story_debug_prompts = {
            "outline": {
                "system": system_msg,
                "user": user_msg,
                "model": prompt_config["model"],
                "temperature": prompt_config["temperature"] or 0.2,
            }
        }

        # 7. Update DB
        await update_story_data(story_id, {
            "title": generated_title, # Save the generated title
            "pages": initial_pages_db,
            "debug_prompts": story_debug_prompts,
            "status": "GENERATING_PAGES", # Set status for next phase
        })
        
        # 8. Send SSE update
        await send_sse_event(story_id,"outline", {"outline_pages": initial_pages_db, "total_pages": total_pages, "debug_prompts": story_debug_prompts.get("outline"), "raw_response": outline_json_str})
        await send_sse_status(story_id, f"Outline generated ({total_pages} pages). Starting page content generation...", step="write_page")

        # 9. Return state (unchanged fields, just pass through)
        return {
             "story_id": story_id, 
             "characters_info": characters_info, 
             "language_code": state.get("language_code"), # Pass through code
             "language_name": language_name, # Pass through name
             "downloaded_avatars": state.get("downloaded_avatars") 
        }

    except Exception as e:
        error_message = f"Error in generate_initial_outline for story {story_id}: {e}"
        logging.error(error_message, exc_info=True)
        await send_sse_error(story_id, f"Failed to generate outline: {e}", step=step_name)
        # Update status to FAILED
        try: 
            await update_story_data(story_id, {"status": "FAILED"})
        except Exception as db_err:
             logging.error(f"Failed to update story {story_id} status to FAILED after outline error: {db_err}")
        raise e # Re-raise to potentially stop the graph

async def retrieve_relevant_memories(family_id: str, search_query: str, max_results: int = 5) -> list:
    """Retrieve relevant confirmed memories for story context via vector search."""
    try:
        from src.utils.openai_client import get_embedding
        query_embedding = await get_embedding(search_query)
        supabase_client: Client = get_supabase_client()
        rpc_params = {
            "query_embedding": query_embedding,
            "match_threshold": 0.5,
            "match_count": max_results,
            "filter_family_id": family_id,
        }
        response = supabase_client.rpc("match_memories", params=rpc_params).execute()
        if response.data:
            # Only return CONFIRMED memories
            return [m for m in response.data if m.get("analysis_status") == "CONFIRMED"]
        return []
    except Exception as e:
        logging.warning(f"Failed to retrieve memories for family {family_id}: {e}")
        return []


async def write_page_content(state: StoryGenerationState):
    story_id = state["story_id"]
    characters_info = state.get("characters_info", [])
    language_name = state.get("language_name", "English") # Get language name from state
    step_name = "write_page"
    page_text = ""
    page_number_to_write = 0
    total_pages = 0
    
    try:
        # 1. Fetch current story data from DB
        await send_sse_status(story_id, "Fetching current story progress...", step=step_name)
        story_data = await get_story_data(story_id)
        current_pages_db = story_data.get("pages", [])
        input_prompt = story_data.get("input_prompt", "A fun story")
        target_age = story_data.get("target_age")
        language = story_data.get("language", "en")
        family_id_str = story_data.get("family_id", "")
        memories = await retrieve_relevant_memories(family_id_str, input_prompt) if family_id_str else []
        
        # 2. Determine which page to write next
        next_page_index = -1
        for i, page_db in enumerate(current_pages_db):
            if not page_db.get("text"):
                next_page_index = i
                break
                
        if next_page_index == -1:
            logging.warning(f"[{story_id}] In write_page_content, but no pages found needing text.")
            await send_sse_status(story_id, "All page text seems complete.", step="writing_complete")
            return {} # Return empty dict, no state change

        page_number_to_write = current_pages_db[next_page_index]["page"]
        page_description = current_pages_db[next_page_index].get("description", f"Page {page_number_to_write}")
        total_pages = len(current_pages_db)
        
        await send_sse_status(story_id, f"Starting page {page_number_to_write}/{total_pages} text generation...", step=step_name, page=page_number_to_write, total_pages=total_pages)
        logging.info(f"[{story_id}] Writing page {page_number_to_write}: {page_description}")
        
        # 3. Prepare LLM Context
        age_context = f" Keep the language and themes appropriate for a {target_age}-year-old child." if target_age else ""
        length_guidance = " Aim for 2-4 short paragraphs per page."
        # Use the helper function, include visual description
        char_desc = _prepare_character_context(characters_info, include_visual=True).replace("Characters:", "Characters potentially involved in the story:") # Adjust prefix slightly
        memory_context = "Relevant Memories:\n" + "\n".join([f"- {m.get('summary') or m.get('text', '')} (Date: {m.get('date', 'N/A')})" for m in memories]) if memories else "No specific memories provided."
        
        previous_pages_summary = "\n".join([
            f"Page {p['page']} Content Summary: {p.get('text', '')[:100]}..."
            for i, p in enumerate(current_pages_db) if i < next_page_index and p.get('text')
        ])
        
        outline_summary = "Story Outline Overview:\n" + "\n".join([
            f"- Page {p['page']}: {p.get('description')}" 
            for p in current_pages_db
        ])

        # 3b. Construct LLM messages from DB-driven prompts
        prompt_config = get_prompt_config("page_text")
        system_msg, user_msg = resolve_prompt("page_text", {
            "language_name": language_name,
            "story_prompt": input_prompt,
            "character_context": char_desc,
            "memory_context": memory_context,
            "outline_summary": outline_summary,
            "previous_pages": previous_pages_summary,
            "page_number": str(page_number_to_write),
            "page_description": page_description,
            "age_context": age_context,
        })

        # 3c. If retrying due to consistency issues, append feedback to user message
        consistency_feedback = state.get("consistency_feedback")
        if consistency_feedback:
            user_msg += (
                f"\n\nIMPORTANT REVISION NEEDED: The previous version of this page had these issues:\n"
                f"{consistency_feedback}\n"
                f"Please rewrite this page fixing ALL the above issues while maintaining the story flow."
            )
            logging.info(f"[{story_id}] Retrying page {page_number_to_write} with consistency feedback")

        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ]

        # 4. Call LLM (streaming)
        llm_kwargs = {
            "model": prompt_config["model"],
            "temperature": prompt_config["temperature"] or 0.7,
            "openai_api_key": settings.OPENAI_API_KEY,
            "streaming": True,
        }
        if prompt_config.get("max_tokens"):
            llm_kwargs["max_tokens"] = prompt_config["max_tokens"]
        llm = ChatOpenAI(**llm_kwargs)
        await send_sse_status(story_id, f"Writing page {page_number_to_write} text...", step=step_name, page=page_number_to_write, total_pages=total_pages)

        # Send page_start event
        await send_sse_event(story_id, "page_start", {"page": page_number_to_write, "total_pages": total_pages})

        # Stream tokens
        page_text = ""
        async for chunk in llm.astream(messages):
            token = chunk.content
            if token:
                page_text += token
                await send_sse_event(story_id, "text_chunk", {"page": page_number_to_write, "chunk": token})

        if not page_text:
            raise ValueError(f"LLM returned empty content for page {page_number_to_write}")
        logging.info(f"[{story_id}] LLM generated page {page_number_to_write} text: {page_text[:100]}...")
        
        # 5. Build page-level debug prompts for text generation
        page_debug_prompts = {
            "page_text": {
                "system": system_msg,
                "user": user_msg,
                "model": prompt_config["model"],
                "temperature": prompt_config["temperature"] or 0.7,
            }
        }

        # 6. Update the specific page in the DB array
        updated_page_data = {
            "text": page_text,
            "debug_prompts": page_debug_prompts,
        }
        # Ensure current_pages_db is treated as a list of dictionaries
        if isinstance(current_pages_db, list) and next_page_index < len(current_pages_db):
             current_pages_db[next_page_index].update(updated_page_data) 
        else:
             logging.error(f"[{story_id}] Failed to update page data in list. Index: {next_page_index}, List: {current_pages_db}")
             raise TypeError("current_pages_db is not a list or index is out of bounds")

        await send_sse_status(story_id, f"Updating database for page {page_number_to_write}...", step=step_name, page=page_number_to_write)
        await update_story_data(story_id, {"pages": current_pages_db}) # Send the whole modified list back
        
        # 7. Send SSE update
        await send_sse_event(story_id, "page_text", {"page": page_number_to_write, "text": page_text, "debug_prompts": page_debug_prompts.get("page_text")})
        await send_sse_status(story_id, f"Page {page_number_to_write} text generated. Generating image prompt...", step="generate_image_prompt", page=page_number_to_write)

        # 8. Return state (no changes needed in the graph state itself)
        return {}

    except Exception as e:
        error_message = f"Error writing page content (page {page_number_to_write}) for story {story_id}: {e}"
        logging.error(error_message, exc_info=True)
        await send_sse_error(story_id, f"Failed to write page {page_number_to_write}: {e}", step=step_name, page=page_number_to_write)
        try: 
            await update_story_data(story_id, {"status": "FAILED"})
        except Exception as db_err:
             logging.error(f"Failed to update story {story_id} status to FAILED after page write error: {db_err}")
        raise e # Re-raise to stop the graph

async def check_page_consistency(state: StoryGenerationState):
    """Check the just-written page for consistency with outline and previous pages."""
    story_id = state["story_id"]
    retry_count = state.get("consistency_retry_count", 0)
    step_name = "check_page_consistency"

    try:
        # 1. Fetch current story data
        story_data = await get_story_data(story_id)
        current_pages_db = story_data.get("pages", [])

        # 2. Find the page that was just written (has text but no image_prompt)
        page_index = -1
        for i in range(len(current_pages_db) - 1, -1, -1):
            page_db = current_pages_db[i]
            if page_db.get("text") and not page_db.get("image_prompt"):
                page_index = i
                break

        if page_index == -1:
            logging.warning(f"[{story_id}] check_page_consistency: no page found needing check.")
            return {"consistency_retry_count": 0, "consistency_feedback": None}

        page_data = current_pages_db[page_index]
        page_number = page_data["page"]
        current_page_text = page_data.get("text", "")

        await send_sse_status(story_id, f"Checking page {page_number} consistency...", step=step_name, page=page_number)

        # 3. Build full context
        outline_summary = "Story Outline:\n" + "\n".join([
            f"- Page {p['page']}: {p.get('description')}"
            for p in current_pages_db
        ])

        full_previous_pages = "\n\n".join([
            f"--- Page {p['page']} ---\n{p.get('text', '')}"
            for i, p in enumerate(current_pages_db)
            if i < page_index and p.get('text')
        ]) or "No previous pages (this is the first page)."

        # 4. Call LLM for consistency check
        prompt_config = get_prompt_config("page_consistency_check")
        system_msg, user_msg = resolve_prompt("page_consistency_check", {
            "outline_summary": outline_summary,
            "full_previous_pages": full_previous_pages,
            "current_page_text": current_page_text,
            "page_number": str(page_number),
        })
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ]

        llm_kwargs = {
            "model": prompt_config["model"],
            "temperature": prompt_config["temperature"] or 0.1,
            "openai_api_key": settings.OPENAI_API_KEY,
        }
        if prompt_config.get("max_tokens"):
            llm_kwargs["max_tokens"] = prompt_config["max_tokens"]
        llm_kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        llm = ChatOpenAI(**llm_kwargs)

        response = await llm.ainvoke(messages)
        result_text = response.content

        # 5. Parse result
        passed = True
        issues = ""
        try:
            result_json = json.loads(result_text)
            passed = result_json.get("pass", True)
            issues = result_json.get("issues", "")
        except json.JSONDecodeError:
            logging.warning(f"[{story_id}] Consistency check returned non-JSON: {result_text}")
            passed = True  # If we can't parse, assume it's fine

        # 6. Save debug info with numbered key (consistency_check_1, _2, _3)
        attempt_number = retry_count + 1
        debug_key = f"consistency_check_{attempt_number}"
        existing_debug = page_data.get("debug_prompts") or {}
        existing_debug[debug_key] = {
            "system": system_msg,
            "user": user_msg,
            "model": prompt_config["model"],
            "temperature": prompt_config["temperature"] or 0.1,
            "response": result_text,
            "passed": passed,
            "attempt": attempt_number,
        }
        current_pages_db[page_index]["debug_prompts"] = existing_debug
        await update_story_data(story_id, {"pages": current_pages_db})

        # 6b. Send SSE event with consistency check result
        await send_sse_event(story_id, "consistency_result", {
            "page": page_number,
            "passed": passed,
            "issues": issues,
            "attempt": attempt_number,
            "debug_key": debug_key,
            "debug_prompts": existing_debug.get(debug_key),
        })

        # 7. Route based on result
        if passed or not issues:
            logging.info(f"[{story_id}] Page {page_number} consistency check PASSED (attempt {attempt_number})")
            await send_sse_status(story_id, f"Page {page_number} consistency check passed.", step=step_name, page=page_number)
            return {"consistency_retry_count": 0, "consistency_feedback": None}

        # Failed - check retry limit (max 3 attempts)
        if retry_count >= 3:
            logging.warning(f"[{story_id}] Page {page_number} consistency check FAILED after {attempt_number} attempts. Accepting anyway. Issues: {issues}")
            await send_sse_status(story_id, f"Page {page_number} accepted after max retries.", step=step_name, page=page_number)
            return {"consistency_retry_count": 0, "consistency_feedback": None}

        # Failed and can retry - clear page text in DB and send retry event
        logging.info(f"[{story_id}] Page {page_number} consistency check FAILED (retry={retry_count}). Issues: {issues}")
        current_pages_db[page_index]["text"] = None
        await update_story_data(story_id, {"pages": current_pages_db})

        await send_sse_event(story_id, "page_retry", {
            "page": page_number,
            "retry": retry_count + 1,
            "issues": issues,
        })
        await send_sse_status(story_id, f"Revising page {page_number} (attempt {retry_count + 2})...", step="write_page", page=page_number)

        return {"consistency_retry_count": retry_count + 1, "consistency_feedback": issues}

    except Exception as e:
        logging.error(f"[{story_id}] Error in check_page_consistency: {e}", exc_info=True)
        # On error, don't block the pipeline - just continue
        logging.warning(f"[{story_id}] Skipping consistency check due to error, continuing pipeline.")
        return {"consistency_retry_count": 0, "consistency_feedback": None}


def route_after_consistency_check(state: StoryGenerationState):
    """Route based on consistency check result: retry write or continue to character detection."""
    if state.get("consistency_feedback"):
        return "retry_write"
    return "continue"


async def detect_page_characters(state: StoryGenerationState):
    """LLM-based character detection: analyzes page text to find extra characters beyond outline."""
    story_id = state["story_id"]
    characters_info = state.get("characters_info", [])
    step_name = "detect_page_characters"

    try:
        story_data = await get_story_data(story_id)
        current_pages_db = story_data.get("pages", [])

        # Find page with text but no image_prompt (the one just written)
        page_index = -1
        for i in range(len(current_pages_db) - 1, -1, -1):
            page_db = current_pages_db[i]
            if page_db.get("text") and not page_db.get("image_prompt"):
                page_index = i
                break

        if page_index == -1:
            logging.warning(f"[{story_id}] detect_page_characters: no page found needing character detection.")
            return {}

        page_data = current_pages_db[page_index]
        page_number = page_data["page"]
        page_text = page_data.get("text", "")
        outline_characters = page_data.get("characters_on_page", [])

        await send_sse_status(story_id, f"Detecting characters on page {page_number}...", step=step_name, page=page_number)

        # Build known character names list
        character_names = ", ".join([c["name"] for c in characters_info]) if characters_info else "None"
        outline_chars_str = ", ".join(outline_characters) if outline_characters else "None"

        # Resolve prompt
        prompt_config = get_prompt_config("character_detection")
        system_msg, user_msg = resolve_prompt("character_detection", {
            "character_names": character_names,
            "outline_characters": outline_chars_str,
            "page_text": page_text,
        })
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ]

        # Call LLM
        llm_kwargs = {
            "model": prompt_config["model"],
            "temperature": prompt_config["temperature"] or 0.1,
            "openai_api_key": settings.OPENAI_API_KEY,
        }
        if prompt_config.get("max_tokens"):
            llm_kwargs["max_tokens"] = prompt_config["max_tokens"]

        # Force JSON response
        llm_kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}
        llm = ChatOpenAI(**llm_kwargs)

        response = await llm.ainvoke(messages)
        result_text = response.content

        # Parse JSON response
        detected_characters = []
        try:
            result_json = json.loads(result_text)
            detected_characters = result_json.get("characters", [])
        except json.JSONDecodeError:
            logging.warning(f"[{story_id}] Character detection returned non-JSON: {result_text}")
            detected_characters = list(outline_characters)  # Fallback to outline

        # Normalize: only keep names that exist in characters_info
        known_names = {c["name"].lower(): c["name"] for c in characters_info}
        normalized = []
        for name in detected_characters:
            canonical = known_names.get(name.lower())
            if canonical and canonical not in normalized:
                normalized.append(canonical)

        # Merge with outline characters (ensure outline chars are always included)
        for oc in outline_characters:
            if oc not in normalized:
                normalized.append(oc)

        logging.info(f"[{story_id}] Characters on page {page_number}: outline={outline_characters}, detected={normalized}")

        # Build debug prompts
        existing_debug = page_data.get("debug_prompts") or {}
        existing_debug["character_detection"] = {
            "system": system_msg,
            "user": user_msg,
            "model": prompt_config["model"],
            "temperature": prompt_config["temperature"] or 0.1,
            "response": result_text,
            "detected": normalized,
        }

        # Update DB
        current_pages_db[page_index]["characters_on_page"] = normalized
        current_pages_db[page_index]["debug_prompts"] = existing_debug
        await update_story_data(story_id, {"pages": current_pages_db})

        # SSE event
        await send_sse_event(story_id, "characters_detected", {
            "page": page_number,
            "characters_on_page": normalized,
            "debug_prompts": existing_debug.get("character_detection"),
        })

        return {}

    except Exception as e:
        logging.error(f"[{story_id}] Error in detect_page_characters: {e}", exc_info=True)
        await send_sse_error(story_id, f"Failed to detect characters: {e}", step=step_name)
        try:
            await update_story_data(story_id, {"status": "FAILED"})
        except Exception as db_err:
            logging.error(f"Failed to update status to FAILED: {db_err}")
        raise e

async def download_page_avatars(state: StoryGenerationState):
    """Download avatars only for characters on current page, with caching across pages."""
    story_id = state["story_id"]
    characters_info = state.get("characters_info", [])
    existing_cache = dict(state.get("downloaded_avatars") or {})
    step_name = "download_page_avatars"

    try:
        story_data = await get_story_data(story_id)
        current_pages_db = story_data.get("pages", [])

        # Find current page (has text, no image_prompt)
        page_index = -1
        for i in range(len(current_pages_db) - 1, -1, -1):
            page_db = current_pages_db[i]
            if page_db.get("text") and not page_db.get("image_prompt"):
                page_index = i
                break

        if page_index == -1:
            return {"downloaded_avatars": existing_cache}

        page_data = current_pages_db[page_index]
        page_number = page_data["page"]
        characters_on_page = page_data.get("characters_on_page", [])

        if not characters_on_page:
            return {"downloaded_avatars": existing_cache}

        # Build lookup: name (case-insensitive) -> CharacterInfo
        char_lookup = {c["name"].lower(): c for c in characters_info}

        # Check for characters not in the original selection — fetch from DB
        missing_names = [name for name in characters_on_page if name.lower() not in char_lookup]
        if missing_names:
            family_id = story_data.get("family_id")
            if family_id:
                db_chars = await fetch_characters_by_names(family_id, missing_names)
                for c in db_chars:
                    char_lookup[c["name"].lower()] = {
                        "id": str(c["id"]),
                        "name": c["name"],
                        "bio": c.get("bio"),
                        "birth_date": c.get("birthdate"),
                        "avatar_url": c.get("avatar_url"),
                        "visual_description": c.get("visual_description"),
                    }
                logging.info(f"[{story_id}] Fetched {len(db_chars)} extra characters from DB for avatar download on page {page_number}")

        # Find which characters need downloading
        to_download = []
        for name in characters_on_page:
            char_info = char_lookup.get(name.lower())
            if char_info and char_info["name"] not in existing_cache and name not in existing_cache:
                if char_info.get("avatar_url"):
                    to_download.append(char_info)

        if not to_download:
            logging.info(f"[{story_id}] Page {page_number}: all {len(characters_on_page)} character avatars already cached.")
            return {"downloaded_avatars": existing_cache}

        await send_sse_status(story_id, f"Downloading {len(to_download)} avatar(s) for page {page_number}...", step=step_name, page=page_number)

        supabase_client: Client = get_supabase_client()
        AVATARS_BUCKET = settings.AVATARS_BUCKET

        async with httpx.AsyncClient() as http_client:
            for character in to_download:
                char_name = character["name"]
                avatar_path = character["avatar_url"]
                try:
                    avatar_public_url = supabase_client.storage.from_(AVATARS_BUCKET).get_public_url(avatar_path)
                    if not avatar_public_url:
                        logging.warning(f"[{story_id}] No public URL for {char_name}'s avatar: {avatar_path}")
                        continue

                    get_response = await http_client.get(avatar_public_url)
                    get_response.raise_for_status()
                    avatar_bytes = get_response.content
                    content_type = get_response.headers.get("content-type", "image/png")
                    extension = mimetypes.guess_extension(content_type) or ".png"
                    filename = f"avatar_{char_name}{extension}"

                    existing_cache[char_name] = (filename, avatar_bytes, content_type)
                    logging.debug(f"[{story_id}] Downloaded avatar for {char_name}, size: {len(avatar_bytes)}")

                except httpx.RequestError as req_err:
                    logging.warning(f"[{story_id}] HTTP error downloading avatar for {char_name}: {req_err}")
                except Exception as dl_err:
                    logging.warning(f"[{story_id}] Error downloading avatar for {char_name}: {dl_err}")

        logging.info(f"[{story_id}] Page {page_number}: avatar cache now has {len(existing_cache)} entries.")

        # IMPORTANT: return the FULL cache dict (LangGraph replaces the key, not deep-merge)
        return {"downloaded_avatars": existing_cache}

    except Exception as e:
        logging.error(f"[{story_id}] Error in download_page_avatars: {e}", exc_info=True)
        await send_sse_error(story_id, f"Failed to download avatars: {e}", step=step_name)
        try:
            await update_story_data(story_id, {"status": "FAILED"})
        except Exception as db_err:
            logging.error(f"Failed to update status to FAILED: {db_err}")
        raise e

async def generate_image_prompt(state: StoryGenerationState):
    story_id = state["story_id"]
    # Get full character info passed in the state
    all_characters_info = state.get("characters_info", [])
    step_name = "generate_image_prompt"
    image_prompt = ""
    page_number = 0
    total_pages = 0

    try:
        # 1. Fetch current story data
        await send_sse_status(story_id, "Fetching story text for image prompt...", step=step_name)
        story_data = await get_story_data(story_id)
        current_pages_db = story_data.get("pages", [])
        target_age = story_data.get("target_age")
        family_id_str = story_data.get("family_id", "")
        input_prompt = story_data.get("input_prompt", "")
        memories = await retrieve_relevant_memories(family_id_str, input_prompt) if family_id_str else []
        
        # 2. Find the page that most recently had text added (and needs an image prompt)
        page_to_prompt_index = -1
        for i in range(len(current_pages_db) - 1, -1, -1): # Iterate backwards
            page_db = current_pages_db[i]
            if page_db.get("text") and not page_db.get("image_prompt"):
                page_to_prompt_index = i
                break
        
        if page_to_prompt_index == -1:
            logging.warning(f"[{story_id}] In generate_image_prompt, but no page found needing a prompt.")
            await send_sse_status(story_id, "Couldn't find page needing image prompt.", step=step_name)
            return {} # No state change

        page_data = current_pages_db[page_to_prompt_index]
        page_number = page_data["page"]
        page_text = page_data.get("text", "")
        # This is currently a list of NAMES
        character_names_on_page = page_data.get("characters_on_page", [])
        total_pages = len(current_pages_db)

        await send_sse_status(story_id, f"Generating image prompt for page {page_number}...", step=step_name, page=page_number, total_pages=total_pages)

        # --- Build visual-focused character context for image prompt ---
        # Match characters_on_page against characters_info (case-insensitive)
        info_by_name_lower = {c['name'].lower(): c for c in all_characters_info} if all_characters_info else {}
        characters_on_this_page_info = []
        missing_names = []
        for name in character_names_on_page:
            matched = info_by_name_lower.get(name.lower())
            if matched:
                characters_on_this_page_info.append(matched)
            else:
                missing_names.append(name)

        # Fetch missing characters from DB (e.g. characters not in original selection but detected on page)
        if missing_names:
            family_id = story_data.get("family_id")
            if family_id:
                db_chars = await fetch_characters_by_names(family_id, missing_names)
                for c in db_chars:
                    characters_on_this_page_info.append({
                        "id": str(c["id"]),
                        "name": c["name"],
                        "bio": c.get("bio"),
                        "birth_date": c.get("birthdate"),
                        "avatar_url": c.get("avatar_url"),
                        "visual_description": c.get("visual_description"),
                    })
                logging.info(f"[{story_id}] Fetched {len(db_chars)} extra characters from DB for page {page_number}: {[c['name'] for c in db_chars]}")

        if characters_on_this_page_info:
            char_lines = []
            for c in characters_on_this_page_info:
                line = f"- {c['name']}"
                if c.get('birth_date'):
                    line += f" (Born: {c['birth_date']})"
                visual = c.get('visual_description')
                if visual:
                    line += f": {visual[:200]}" if len(visual) > 200 else f": {visual}"
                else:
                    line += ": [no visual description available]"
                char_lines.append(line)
            char_desc = "Visual description of characters on this page:\n" + "\n".join(char_lines) + "\nEnsure their appearance matches their description and implied age."
        else:
            char_desc = "No specific characters featured on this page."

        # --- Collect avatar public URLs for SSE debug ---
        avatar_urls_for_sse: Dict[str, str] = {}
        if characters_on_this_page_info:
            supabase_client: Client = get_supabase_client()
            AVATARS_BUCKET = settings.AVATARS_BUCKET
            for c in characters_on_this_page_info:
                avatar_path = c.get('avatar_url')
                if avatar_path:
                    try:
                        public_url = supabase_client.storage.from_(AVATARS_BUCKET).get_public_url(avatar_path)
                        if public_url:
                            avatar_urls_for_sse[c['name']] = public_url
                    except Exception as url_err:
                        logging.warning(f"[{story_id}] Could not get public URL for {c['name']}'s avatar: {url_err}")

        memory_context = "Relevant Story Memories: " + "; ".join([m.get("summary") or m.get("text", "") for m in memories]) if memories else ""
        style_keywords = "watercolor, cartoonish, soft lighting, vibrant, friendly, children's book illustration style"
        age_appropriate_visuals = f" Ensure visuals are suitable for a {target_age}-year-old, avoiding anything scary." if target_age else " Avoid scary elements."

        # 3b. Construct LLM messages from DB-driven prompts
        language_name = state.get("language_name", "English")
        prompt_config = get_prompt_config("image_prompt")
        system_msg, user_msg = resolve_prompt("image_prompt", {
            "style_keywords": style_keywords,
            "age_context": age_appropriate_visuals,
            "character_context": char_desc,
            "memory_context": memory_context,
            "page_text": page_text,
            "language_name": language_name,
        })
        messages = [
            SystemMessage(content=system_msg),
            HumanMessage(content=user_msg)
        ]

        # 4. Call LLM
        llm_kwargs = {
            "model": prompt_config["model"],
            "temperature": prompt_config["temperature"] or 0.5,
            "openai_api_key": settings.OPENAI_API_KEY,
        }
        if prompt_config.get("max_tokens"):
            llm_kwargs["max_tokens"] = prompt_config["max_tokens"]
        llm = ChatOpenAI(**llm_kwargs)
        await send_sse_status(story_id, f"Calling LLM for image prompt (page {page_number})...", step=step_name, page=page_number, total_pages=total_pages)
        response = await llm.ainvoke(messages)
        
        image_prompt = response.content
        if not image_prompt or not isinstance(image_prompt, str):
            raise ValueError(f"LLM returned empty or invalid image prompt for page {page_number}")
        logging.info(f"[{story_id}] Generated image prompt for page {page_number}: {image_prompt}")
        
        # 4b. Append image_prompt debug to existing page debug_prompts
        existing_debug = current_pages_db[page_to_prompt_index].get("debug_prompts") or {}
        existing_debug["image_prompt"] = {
            "system": system_msg,
            "user": user_msg,
            "model": prompt_config["model"],
            "temperature": prompt_config["temperature"] or 0.5,
        }

        # 5. Update the specific page in the DB array
        current_pages_db[page_to_prompt_index]["image_prompt"] = image_prompt
        # characters_on_page is already set by detect_page_characters, don't overwrite
        current_pages_db[page_to_prompt_index]["debug_prompts"] = existing_debug
        if avatar_urls_for_sse:
            current_pages_db[page_to_prompt_index]["avatar_urls"] = avatar_urls_for_sse

        await send_sse_status(story_id, f"Updating database with image prompt for page {page_number}...", step=step_name, page=page_number)
        await update_story_data(story_id, {"pages": current_pages_db}) # Send the whole modified list back

        # 6. Send SSE update
        await send_sse_event(story_id, "image_prompt", {"page": page_number, "prompt": image_prompt, "characters_on_page": character_names_on_page, "debug_prompts": existing_debug.get("image_prompt"), "avatar_urls": avatar_urls_for_sse})
        await send_sse_status(story_id, f"Image prompt for page {page_number} generated. Generating image...", step="generate_page_image", page=page_number)

        # 7. Return state (no changes needed in the graph state itself)
        return {}

    except Exception as e:
        error_message = f"Error generating image prompt (page {page_number}) for story {story_id}: {e}"
        logging.error(error_message, exc_info=True)
        await send_sse_error(story_id, f"Failed to generate image prompt for page {page_number}: {e}", step=step_name, page=page_number)
        try: 
            await update_story_data(story_id, {"status": "FAILED"})
        except Exception as db_err:
             logging.error(f"Failed to update story {story_id} status to FAILED after image prompt error: {db_err}")
        raise e

async def generate_page_image(state: StoryGenerationState):
    story_id = state["story_id"]
    # Get downloaded avatar data from the graph state
    downloaded_avatars = state.get('downloaded_avatars', {})
    step_name = "generate_page_image"
    page_number = 0
    total_pages = 0
    permanent_image_url = None

    try:
        # 1. Fetch current story data
        await send_sse_status(story_id, "Fetching image prompt...", step=step_name)
        story_data = await get_story_data(story_id)
        current_pages_db = story_data.get("pages", [])
        family_id = story_data.get("family_id") # Needed for storage path
        if not family_id:
            raise ValueError("Family ID missing from story data, cannot determine storage path.")

        # 2. Find the page that most recently had a prompt added (and needs an image)
        page_to_image_index = -1
        for i in range(len(current_pages_db) - 1, -1, -1):
            page_db = current_pages_db[i]
            if page_db.get("image_prompt") and not page_db.get("image_url"):
                page_to_image_index = i
                break
        
        if page_to_image_index == -1:
            logging.warning(f"[{story_id}] In generate_page_image, but no page found needing an image.")
            await send_sse_status(story_id, "Couldn't find page needing image generation.", step=step_name)
            return {} # No state change

        page_data = current_pages_db[page_to_image_index]
        page_number = page_data["page"]
        image_prompt = page_data.get("image_prompt", "A simple children's book illustration")
        characters_on_page = page_data.get("characters_on_page", [])
        total_pages = len(current_pages_db)

        await send_sse_status(story_id, f"Starting image generation for page {page_number}...", step=step_name, page=page_number, total_pages=total_pages)
        
        # Determine which provider to use
        provider = settings.IMAGE_GENERATION_PROVIDER
        logging.info(f"[{story_id} Page {page_number}] Generating image for page {page_number} using {provider} with prompt: {image_prompt[:100]}...")

        # 3. Prepare image input tuple (using downloaded_avatars from state)
        image_tuples_for_api = []
        if downloaded_avatars and characters_on_page:
            logging.info(f"[{story_id} Page {page_number}] Checking for avatars for characters: {characters_on_page}")
            for char_name in characters_on_page:
                if char_name in downloaded_avatars:
                    # Append avatar if found
                    image_tuples_for_api.append(downloaded_avatars[char_name]) 
                    logging.info(f"[{story_id} Page {page_number}] Adding avatar for '{char_name}' for image generation.")
                else:
                    logging.warning(f"[{story_id} Page {page_number}] Avatar not found in downloaded data for character: '{char_name}'")
            
            if not image_tuples_for_api:
                 logging.warning(f"[{story_id} Page {page_number}] No downloaded avatars matched any characters on page: {characters_on_page}")
        else:
            logging.info(f"[{story_id} Page {page_number}] No avatars downloaded or no characters listed for this page.")

        # 4. Call Image API using selected provider
        image_content = None
        content_type = "image/png"
        file_extension = ".png"
        
        try:
            if provider == "GEMINI":
                # Use Gemini for image generation
                if image_tuples_for_api:
                    await send_sse_status(story_id, f"Calling Gemini with reference images for page {page_number}...", step=step_name, page=page_number, total_pages=total_pages)
                    image_content = await generate_image_with_gemini(
                        prompt=image_prompt,
                        reference_images=image_tuples_for_api,
                        size="1024x1024"
                    )
                    if image_content:
                        logging.info(f"[{story_id} Page {page_number}] Image generated with Gemini using reference images, size: {len(image_content)}")
                    else:
                        raise ValueError("Gemini failed to generate image content")
                else:
                    await send_sse_status(story_id, f"Calling Gemini for page {page_number}...", step=step_name, page=page_number, total_pages=total_pages)
                    image_content = await generate_image_with_gemini(
                        prompt=image_prompt,
                        size="1024x1024"
                    )
                    if image_content:
                        logging.info(f"[{story_id} Page {page_number}] Image generated with Gemini, size: {len(image_content)}")
                    else:
                        raise ValueError("Gemini failed to generate image content")
                        
            else:  # Default to OpenAI
                if image_tuples_for_api:
                    await send_sse_status(story_id, f"Calling OpenAI Image Edit for page {page_number}...", step=step_name, page=page_number, total_pages=total_pages)
                    edit_response = await async_openai_client.images.edit(
                        model=settings.OPENAI_EDIT_MODEL,
                        image=image_tuples_for_api, # Pass the tuple (filename, bytes, content_type)
                        prompt=image_prompt,
                        n=1,
                        size="1024x1024",
                    )
                    if not edit_response.data or not edit_response.data[0].b64_json:
                        raise ValueError("Image edit response missing image data (b64_json)")
                    image_base64 = edit_response.data[0].b64_json
                    image_content = base64.b64decode(image_base64)
                    logging.info(f"[{story_id} Page {page_number}] Image edited and decoded, size: {len(image_content)}")
                else:
                    # Fallback to image generation if no suitable avatar was found
                    await send_sse_status(story_id, f"Calling OpenAI Image Generate for page {page_number}...", step=step_name, page=page_number, total_pages=total_pages)
                    generate_response = await async_openai_client.images.generate(
                         model=settings.OPENAI_EDIT_MODEL,
                         prompt=image_prompt,
                         n=1,
                         size="1024x1024",
                    )
                    if not generate_response.data or not generate_response.data[0].b64_json:
                         raise ValueError("Image generate response missing image data (b64_json)")
                    image_base64 = generate_response.data[0].b64_json
                    image_content = base64.b64decode(image_base64)
                    logging.info(f"[{story_id} Page {page_number}] Image generated and decoded, size: {len(image_content)}")

        except Exception as api_err:
            logging.error(f"[{story_id} Page {page_number}] Error during image generation: {api_err}")
            # Don't fail the whole graph, just skip image for this page
            await send_sse_error(story_id, f"Failed to generate image for page {page_number}: {api_err}", step=step_name, page=page_number)
            image_content = None # Ensure no upload happens

        # 5. Upload image to Supabase Storage if content exists
        if image_content:
            try:
                supabase_client: Client = get_supabase_client()
                STORY_IMAGES_BUCKET = "story-images"
                await send_sse_status(story_id, f"Uploading image for page {page_number}...", step=step_name, page=page_number, total_pages=total_pages)
                # Use story_id in the path for better organization
                storage_path = f"{family_id}/{story_id}/page_{page_number}{file_extension}"
                logging.info(f"[{story_id} Page {page_number}] Uploading image to storage path: {storage_path}")
                upload_response = supabase_client.storage.from_(STORY_IMAGES_BUCKET).upload(
                    path=storage_path,
                    file=image_content,
                    file_options={"content-type": content_type, "upsert": "true"}
                )
                permanent_image_url = supabase_client.storage.from_(STORY_IMAGES_BUCKET).get_public_url(storage_path)
                logging.info(f"[{story_id} Page {page_number}] Image uploaded. Public URL: {permanent_image_url}")
            except Exception as upload_err:
                logging.error(f"[{story_id} Page {page_number}] Error uploading image to Supabase storage: {upload_err}")
                await send_sse_error(story_id, f"Failed to upload image for page {page_number}: {upload_err}", step=step_name, page=page_number)
                permanent_image_url = None # Ensure URL is None if upload fails
        else:
            logging.warning(f"[{story_id} Page {page_number}] No image content generated/available to upload.")
            permanent_image_url = None

        # 6. Update the specific page in the DB array
        current_pages_db[page_to_image_index]["image_url"] = permanent_image_url # Update the dict in the list
        
        await send_sse_status(story_id, f"Updating database with image URL for page {page_number}...", step=step_name, page=page_number)
        await update_story_data(story_id, {"pages": current_pages_db}) # Send the whole modified list back
        
        # 7. Send SSE update
        await send_sse_event(story_id,"page_image", {"page": page_number, "image_url": permanent_image_url})
        await send_sse_status(story_id, f"Page {page_number} image generated. Checking if more pages...", step="checking_completion", page=page_number)

        # 8. Return state (no changes needed in the graph state itself)
        return {}

    except Exception as e:
        error_message = f"Error generating image (page {page_number}) for story {story_id}: {e}"
        logging.error(error_message, exc_info=True)
        await send_sse_error(story_id, f"Failed to generate image for page {page_number}: {e}", step=step_name, page=page_number)
        # Attempt to mark story as failed, but don't crash the background task if DB update fails
        try: 
            await update_story_data(story_id, {"status": "FAILED"})
        except Exception as db_err:
             logging.error(f"Failed to update story {story_id} status to FAILED after image generation error: {db_err}")
        raise e # Re-raise error to stop the graph for this story

# async def save_story_to_db(state: StoryGenerationState): # REMOVED

# --- 3. Define Conditional Edges (Refactored) --- 
async def should_continue_writing(state: StoryGenerationState):
    story_id = state["story_id"]
    logging.info(f"[{story_id}] Checking if story generation should continue...")
    try:
        # 1. Fetch current story data
        story_data = await get_story_data(story_id)
        pages_db = story_data.get("pages", [])
        
        # Log the state being checked
        logging.debug(f"[{story_id}] Checking completion. Pages in DB: {json.dumps(pages_db, indent=2)}")
        
        if not pages_db: 
             logging.warning(f"[{story_id}] No pages found in DB during should_continue check.")
             return END 
        
        # 2. NEW LOGIC: Check if ALL pages have an image_prompt.
        # This signifies that the text and prompt steps are complete for all pages,
        # and the image generation step has been attempted (or will be next) for the last page.
        all_prompts_generated = True
        missing_prompt_page = -1
        for i, p in enumerate(pages_db):
            if not p.get("image_prompt"):
                all_prompts_generated = False
                missing_prompt_page = p.get('page', i+1)
                break

        if all_prompts_generated:
             logging.info(f"[{story_id}] All pages ({len(pages_db)}) have image prompts generated. Ending generation cycle after this image attempt.")
             # This condition is met *after* the last page's image node runs.
             # Return the *key* for the end condition, not END itself
             return "end" 
        else:
             logging.info(f"[{story_id}] Page {missing_prompt_page} (and possibly others) still needs an image prompt. Continuing generation.")
             return "continue"
             
    except Exception as e:
        logging.error(f"[{story_id}] Error checking story completion status: {e}. Ending graph.", exc_info=True)
        await send_sse_error(story_id, f"Error checking completion status: {e}", step="checking_completion")
        # Setting status to FAILED in the main run_story_generation error handler is likely better
        return END 

# --- 4. Build the Graph ---
workflow = StateGraph(StoryGenerationState)
workflow.add_node("determine_language_name", determine_language_name)
workflow.add_node("generate_outline", generate_initial_outline)
workflow.add_node("write_page", write_page_content)
workflow.add_node("check_page_consistency", check_page_consistency)
workflow.add_node("detect_page_characters", detect_page_characters)
workflow.add_node("download_page_avatars", download_page_avatars)
workflow.add_node("generate_image_prompt", generate_image_prompt)
workflow.add_node("generate_page_image", generate_page_image)

workflow.set_entry_point("determine_language_name")
workflow.add_edge("determine_language_name", "generate_outline")
workflow.add_edge("generate_outline", "write_page")
workflow.add_edge("write_page", "check_page_consistency")
workflow.add_conditional_edges(
    "check_page_consistency",
    route_after_consistency_check,
    {
        "retry_write": "write_page",
        "continue": "detect_page_characters",
    }
)
workflow.add_edge("detect_page_characters", "download_page_avatars")
workflow.add_edge("download_page_avatars", "generate_image_prompt")
workflow.add_edge("generate_image_prompt", "generate_page_image")
workflow.add_conditional_edges(
    "generate_page_image",
    should_continue_writing,
    {
        "continue": "write_page",
        "end": END
    }
)

story_generation_app = workflow.compile()

# --- 5. Function to Invoke the Graph (Refactored) --- 
async def run_story_generation(
    story_id: str,
    characters_info: List[CharacterInfo],
    language_code: Optional[str] = None,
    num_pages: Optional[int] = None,
):
    """Runs the complete story generation graph."""
    logging.info(f"Starting graph execution for story_id: {story_id}, Language Code: {language_code}, Num Pages: {num_pages}")
    
    # Send initial SSE message immediately
    await send_sse_status(story_id, "Generation process starting...", step="initializing")
    
    try:
        # Update DB status before starting graph
        await update_story_data(story_id, {"status": "OUTLINING"})
        await send_sse_status(story_id, "Creating story outline...", step="generate_outline")
        
        # Prepare initial state for the graph
        initial_input = {
            "story_id": story_id,
            "characters_info": characters_info,
            "language_code": language_code or 'en', # Pass language code, default to 'en'
            "num_pages": num_pages,
            # Lazy cache: starts empty, download_page_avatars populates per page
            "downloaded_avatars": {},
            # Consistency check state
            "consistency_retry_count": 0,
            "consistency_feedback": None,
        }
        
        # Run the graph (no config needed for checkpointer)
        final_state = None
        async for event in story_generation_app.astream(initial_input, {
            "recursion_limit": 50 # Increased limit
        }): 
            # Note: event format might differ slightly without checkpointer
            # Typically, keys are node names or special keys like '__end__'
            # Log only event keys to avoid logging large image data
            event_keys = list(event.keys()) if isinstance(event, dict) else type(event).__name__
            print(f"Graph Event for {story_id}: {event_keys}")
            # Optional: Send simplified status based on node execution
            # Extract node name and maybe send SSE update (though nodes should do this after DB update)
            
            # Check for the end event 
            if END in event: 
                final_state_values = event[END]
                logging.info(f"[{story_id}] Graph execution successfully reached END.")
                break
        
        # If loop finishes without END event (e.g., recursion limit), treat as potential issue or maybe okay if logic ensures completion
        # For now, assume successful completion if no exception was raised
        logging.info(f"Graph execution finished for story_id: {story_id}. Updating status to COMPLETED.")
        await update_story_data(story_id, {"status": "COMPLETED"})
        await send_sse_event(story_id, "done", {"story_id": story_id})
        
        return {"success": True, "story_id": story_id}

    except Exception as e:
        error_message = f"Error during story generation for story_id {story_id}: {e}"
        logging.error(error_message, exc_info=True)
        
        # Attempt to update DB status to FAILED
        try:
            await update_story_data(story_id, {"status": "FAILED"})
            await send_sse_error(story_id, f"Generation failed: {e}", step="graph_execution")
        except Exception as db_update_err:
            logging.error(f"Failed to update story {story_id} status to FAILED after error: {db_update_err}", exc_info=True)
            await send_sse_error(story_id, f"Generation failed and status update failed: {e}", step="graph_execution")

        # Do not re-raise HTTPException here, let the background task handler manage it
        # Just log the error and ensure status is FAILED
        # The background task itself won't return a value to the original HTTP request anyway
        return {"success": False, "story_id": story_id, "error": error_message} # Indicate failure