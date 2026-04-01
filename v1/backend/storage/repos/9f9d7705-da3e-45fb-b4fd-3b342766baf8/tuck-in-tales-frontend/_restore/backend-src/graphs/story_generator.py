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
    downloaded_avatars: Dict[str, Tuple[str, bytes, str]] | None # Track downloaded avatar data
    # Fields previously needed for checkpointer/SSE are removed or handled differently
    # - input_prompt, target_age, language: fetched from DB via story_id if needed
    # - story_outline: outline is now stored in DB pages array
    # - retrieved_memories: fetched/used within a node, maybe not passed in state
    # - story_pages: managed entirely in the DB record
    # - current_step: implicitly tracked by node execution, status in DB
    # - family_id: can be derived from story_id via DB lookup if needed
    # - saved_story_id: story_id is known from the start

# --- 2. Define Graph Nodes (Updates needed) --- 

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
        print(f"Generating outline for story {story_id} based on: {prompt}")
        
        # 3. Construct LLM messages
        messages = [
            SystemMessage(content=f"You are a creative assistant specializing in children's bedtime stories. Generate a suitable story title and a simple, structured outline (JSON object: {{ 'title': 'story title here', 'outline': [{{ 'page': 1, 'description': '...' }}, ...] }}) for a short story (3-5 pages) in {language_name}. Base it on the user's prompt and characters involved. Keep descriptions concise.{age_context}"),
            HumanMessage(content=f"Story idea (in {language_name}): {prompt}\n{char_desc}")
        ]
        
        # 4. Call LLM
        llm = ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL, 
            temperature=0.2,
            openai_api_key=settings.OPENAI_API_KEY,
            model_kwargs={"response_format": {"type": "json_object"}}
        )
        await send_sse_status(story_id, "Calling LLM for outline...", step=step_name)
        response = await llm.ainvoke(messages)
        
        # 5. Parse Outline
        outline_json_str = response.content 
        if not outline_json_str or not isinstance(outline_json_str, str):
             raise ValueError(f"LLM returned unexpected outline content type: {type(outline_json_str)}")
        outline_data = json.loads(outline_json_str)
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
        initial_pages_db = [
            { # Conforms to StoryPageProgress structure
                "page": p.get("page"), 
                "description": p.get("description"),
                "text": None,
                "image_prompt": None,
                "image_url": None,
                "characters_on_page": None
            }
            for p in outline_pages if p.get("page") and p.get("description") # Basic validation
        ]
        
        if not initial_pages_db:
            raise ValueError("Failed to parse valid pages from LLM outline.")
            
        total_pages = len(initial_pages_db)
        # Add logging for the number of pages planned
        logging.info(f"[{story_id}] LLM generated outline with {total_pages} pages.")

        # 7. Update DB
        await update_story_data(story_id, {
            "title": generated_title, # Save the generated title
            "pages": initial_pages_db,
            "status": "GENERATING_PAGES", # Set status for next phase
        })
        
        # 8. Send SSE update
        await send_sse_event(story_id,"outline", {"outline_pages": initial_pages_db, "total_pages": total_pages})
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

async def retrieve_relevant_memories(state: StoryGenerationState):
    # This node might become internal to write_page_content
    # Or fetch based on story_id and context, returning memories (not saved to state)
    pass # TODO: Implement or remove

async def download_character_avatars(state: StoryGenerationState):
    story_id = state["story_id"]
    characters_info = state.get("characters_info", [])
    step_name = "download_avatars"
    await send_sse_status(story_id, "Preparing character avatars...", step=step_name)
    
    if not characters_info:
        logging.info(f"[{story_id}] No characters info provided, skipping avatar download.")
        await send_sse_status(story_id, "No characters, skipping avatar download.", step=step_name)
        # Return state unmodified, ensuring downloaded_avatars is explicitly None or empty dict
        return { "downloaded_avatars": {} } # Explicitly return update for this key

    supabase_client: Client = get_supabase_client()
    AVATARS_BUCKET = settings.AVATARS_BUCKET
    downloaded_data: Dict[str, Tuple[str, bytes, str]] = {}
    total_chars = len(characters_info)
    downloaded_count = 0

    logging.info(f"[{story_id}] Starting avatar download for {total_chars} characters.")

    async with httpx.AsyncClient() as http_client:
        for index, character in enumerate(characters_info):
            # Use CharacterInfo typed dict access
            char_id = character['id'] 
            char_name = character['name']
            avatar_path = character.get('avatar_url') # Path in storage

            if not avatar_path:
                logging.info(f"[{story_id}] Skipping avatar download for {char_name} ({char_id}): No avatar_url path provided.")
                continue

            await send_sse_status(story_id, f"Downloading avatar {index+1}/{total_chars} for {char_name}...", step=step_name)
            try:
                # Need to construct the full public URL
                avatar_public_url = supabase_client.storage.from_(AVATARS_BUCKET).get_public_url(avatar_path)
                if not avatar_public_url:
                    logging.warning(f"[{story_id}] Could not get public URL for avatar path: {avatar_path} (Character: {char_name})")
                    await send_sse_error(story_id, f"Could not get URL for {char_name}'s avatar.", step=step_name)
                    continue
                
                logging.debug(f"[{story_id}] Downloading avatar for {char_name} from {avatar_public_url}")
                get_response = await http_client.get(avatar_public_url)
                get_response.raise_for_status()
                avatar_bytes = get_response.content
                avatar_content_type = get_response.headers.get("content-type", "image/png")
                avatar_extension = mimetypes.guess_extension(avatar_content_type) or ".png"
                filename = f"avatar_{char_name}{avatar_extension}"
                
                # Store by character NAME as key for easy lookup in image generation? Or ID?
                # Using NAME for consistency with previous logic and potentially simpler access in image prompt node
                downloaded_data[char_name] = (filename, avatar_bytes, avatar_content_type)
                downloaded_count += 1
                logging.debug(f"[{story_id}] Downloaded avatar for {char_name} ({char_id}), size: {len(avatar_bytes)}")

            except httpx.RequestError as req_err:
                logging.warning(f"[{story_id}] HTTP request error downloading avatar for {char_name} from {avatar_public_url}: {req_err}")
                await send_sse_error(story_id, f"Network error downloading {char_name}'s avatar.", step=step_name)
            except httpx.HTTPStatusError as status_err:
                logging.warning(f"[{story_id}] HTTP status error {status_err.response.status_code} downloading avatar for {char_name} from {avatar_public_url}")
                await send_sse_error(story_id, f"Error fetching {char_name}'s avatar (Status: {status_err.response.status_code}).", step=step_name)
            except Exception as dl_err:
                logging.warning(f"[{story_id}] Failed to download avatar for {char_name} (Path: {avatar_path}): {dl_err}")
                await send_sse_error(story_id, f"Failed to process {char_name}'s avatar.", step=step_name)

    logging.info(f"[{story_id}] Finished avatar download. Successfully downloaded {downloaded_count}/{total_chars} avatars.")
    await send_sse_status(story_id, f"Successfully prepared {downloaded_count} character avatars.", step=step_name)
    
    # Return ONLY the updated part of the state (the downloaded avatars)
    # LangGraph will merge this with the existing state
    return { "downloaded_avatars": downloaded_data }

async def write_page_content(state: StoryGenerationState):
    story_id = state["story_id"]
    characters_info = state.get("characters_info", [])
    language_name = state.get("language_name", "English") # Get language name from state
    step_name = "write_page"
    page_text = ""
    characters_on_page = []
    page_number_to_write = 0
    total_pages = 0
    
    try:
        # 1. Fetch current story data from DB
        await send_sse_status(story_id, "Fetching current story progress...", step=step_name)
        story_data = await get_story_data(story_id)
        current_pages_db = story_data.get("pages", [])
        input_prompt = story_data.get("input_prompt", "A fun story")
        target_age = story_data.get("target_age")
        language = story_data.get("language", "en") # Needed for LLM context?
        # TODO: Retrieve memories relevant to this story_id / family_id if RAG is desired
        memories = [] 
        
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
        memory_context = "Relevant Memories:\n" + "\n".join([f"- {m['text']} (Date: {m.get('date', 'N/A')})" for m in memories]) if memories else "No specific memories provided."
        
        previous_pages_summary = "\n".join([
            f"Page {p['page']} Content Summary: {p.get('text', '')[:100]}..."
            for i, p in enumerate(current_pages_db) if i < next_page_index and p.get('text')
        ])
        
        outline_summary = "Story Outline Overview:\n" + "\n".join([
            f"- Page {p['page']}: {p.get('description')}" 
            for p in current_pages_db
        ])

        prompt_context = (
            f"Story Prompt: {input_prompt}\n{char_desc}\n{memory_context}\n{outline_summary}\nPrevious Pages Summary:\n{previous_pages_summary}\n\n"
            f"Write the content FOR ONLY page {page_number_to_write} in {language_name}, which has this description: '{page_description}'. "
            f"Focus *only* on the narrative for this single page. Ensure smooth transition from previous pages if applicable. Keep it engaging.{age_context}{length_guidance}"
        )
        messages = [
            SystemMessage(content=f"You are a talented children's story author writing in {language_name}. Write the content for the current page of a bedtime story, following the provided context. Focus *only* on the text for page {page_number_to_write}."),
            HumanMessage(content=prompt_context)
        ]
        
        # 4. Call LLM (streaming)
        llm = ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL,
            temperature=0.7,
            max_tokens=350,
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=True
        )
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
        
        # 5. Identify characters on page
        if characters_info and page_text:
            for char_info in characters_info:
                if char_info['name'].lower() in page_text.lower(): 
                    characters_on_page.append(char_info['name'])
            logging.info(f"[{story_id}] Identified characters on page {page_number_to_write}: {characters_on_page}")

        # 6. Update the specific page in the DB array
        updated_page_data = {
            "text": page_text,
            "characters_on_page": characters_on_page
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
        await send_sse_event(story_id,"page_text", {"page": page_number_to_write, "text": page_text, "characters_on_page": characters_on_page})
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
        # TODO: Retrieve memories if needed for prompt generation
        memories = []
        
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

        # --- Fetch latest bios AND birthdates for characters on page ---
        # REFACTORED: Use the helper function with the relevant subset of characters
        characters_on_this_page_info = []
        if character_names_on_page and all_characters_info:
            characters_on_this_page_info = [c for c in all_characters_info if c['name'] in character_names_on_page]
        
        # Use the helper, no need for include_visual=True for image prompt context
        char_desc_from_helper = _prepare_character_context(characters_on_this_page_info)

        # Adjust the prefix for the prompt context
        if char_desc_from_helper != "No specific characters mentioned.":
            # Replace the default prefix and add the age guidance
            char_desc = char_desc_from_helper.replace("Characters:", "Characters featured on this page:") + ". Ensure their appearance matches their description and implied age."
        else:
            char_desc = "No specific characters featured on this page."

        memory_context = "Relevant Story Memories: " + "; ".join([f"{m['text']}" for m in memories]) if memories else ""
        style_keywords = "watercolor, cartoonish, soft lighting, vibrant, friendly, children's book illustration style"
        age_appropriate_visuals = f" Ensure visuals are suitable for a {target_age}-year-old, avoiding anything scary." if target_age else " Avoid scary elements."
        
        prompt_context = (
            f"Create a Openai GPT image generation prompt for a children's storybook illustration. "
            f"Style: {style_keywords}.{age_appropriate_visuals} "
            f"{char_desc} " # Inject the enhanced character description
            f"{memory_context} "
            f"Generate a prompt based *only* on the following scene text, focusing on key visual elements and emotions: \"{page_text}\".\""
            f" The prompt should be concise and descriptive for image generation."
        )
        messages = [
            SystemMessage(content="You are an expert prompt engineer for Openai GPT image generation... Use the character descriptions (including age context from birth date) to guide the visual details."), # Updated system msg
            HumanMessage(content=prompt_context)
        ]

        # 4. Call LLM
        llm = ChatOpenAI(
            model=settings.OPENAI_CHAT_MODEL, 
            temperature=0.5, 
            max_tokens=150,
            openai_api_key=settings.OPENAI_API_KEY
        )
        await send_sse_status(story_id, f"Calling LLM for image prompt (page {page_number})...", step=step_name, page=page_number, total_pages=total_pages)
        response = await llm.ainvoke(messages)
        
        image_prompt = response.content
        if not image_prompt or not isinstance(image_prompt, str):
            raise ValueError(f"LLM returned empty or invalid image prompt for page {page_number}")
        logging.info(f"[{story_id}] Generated image prompt for page {page_number}: {image_prompt}")
        
        # 5. Update the specific page in the DB array
        # Store the original character names list, not the detailed descriptions
        current_pages_db[page_to_prompt_index]["image_prompt"] = image_prompt
        current_pages_db[page_to_prompt_index]["characters_on_page"] = character_names_on_page
        
        await send_sse_status(story_id, f"Updating database with image prompt for page {page_number}...", step=step_name, page=page_number)
        await update_story_data(story_id, {"pages": current_pages_db}) # Send the whole modified list back
        
        # 6. Send SSE update
        await send_sse_event(story_id,"image_prompt", {"page": page_number, "prompt": image_prompt, "characters_on_page": character_names_on_page})
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

# --- 4. Build the Graph (Edges updated) --- 
workflow = StateGraph(StoryGenerationState)
workflow.add_node("determine_language_name", determine_language_name)
workflow.add_node("download_character_avatars", download_character_avatars)
workflow.add_node("generate_outline", generate_initial_outline)
workflow.add_node("write_page", write_page_content)
workflow.add_node("generate_image_prompt", generate_image_prompt)
workflow.add_node("generate_page_image", generate_page_image)
# workflow.add_node("save_story", save_story_to_db) # Removed

workflow.set_entry_point("determine_language_name")
# workflow.add_edge("generate_outline", "retrieve_relevant_memories") # Decide if needed
workflow.add_edge("determine_language_name", "download_character_avatars") # Or after memories?
workflow.add_edge("download_character_avatars", "generate_outline")
workflow.add_edge("generate_outline", "write_page")
workflow.add_edge("write_page", "generate_image_prompt")
workflow.add_edge("generate_image_prompt", "generate_page_image")
workflow.add_conditional_edges(
    "generate_page_image", 
    should_continue_writing,
    {
        "continue": "write_page",
        "end": END # End the graph directly after last page image
    }
)
# workflow.add_edge("save_story", END) # Removed

# Compile without checkpointer
story_generation_app = workflow.compile()

# --- 5. Function to Invoke the Graph (Refactored) --- 
async def run_story_generation(
    story_id: str, 
    characters_info: List[CharacterInfo],
    language_code: Optional[str] = None # Accept language code
):
    """Runs the complete story generation graph."""
    logging.info(f"Starting graph execution for story_id: {story_id}, Language Code: {language_code}")
    
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
            # Start with None, download node will populate if successful
            "downloaded_avatars": None, 
        }
        
        # Run the graph (no config needed for checkpointer)
        final_state = None
        async for event in story_generation_app.astream(initial_input, {
            "recursion_limit": 50 # Increased limit
        }): 
            # Note: event format might differ slightly without checkpointer
            # Typically, keys are node names or special keys like '__end__'
            print(f"Graph Event for {story_id}: {event}")
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