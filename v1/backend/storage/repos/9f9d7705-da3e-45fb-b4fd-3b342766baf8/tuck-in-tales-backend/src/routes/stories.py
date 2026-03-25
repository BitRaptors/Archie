from fastapi import APIRouter, HTTPException, Depends, Response, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from src.utils.sse import sse_generator, get_or_create_queue
from uuid import UUID, uuid4
from typing import List, Annotated, Optional, Any
from supabase import Client
from urllib.parse import urlparse
from src.config import settings # For base URL
import asyncio
import logging # Import logging
import openai # Import openai
import httpx # Import httpx for later use
import json # Import json for parsing LLM response
import mimetypes # Import mimetypes
import io # Import io for BytesIO
import base64 # Import base64
from datetime import date, datetime # Add date

# Assuming models are in src.models
from src.models.story import Story, StoryGenerationRequest, StoryBasic # Remove StoryCreate, StoryPage
from src.utils.supabase import get_supabase_client # Import dependency injector
from src.graphs.story_generator import run_story_generation, CharacterInfo # Import the generator service and CharacterInfo type
from src.models.story import StoryPageProgress # Import progress type if needed here

# Add Character model for fetching
from src.models.character import Character
from src.utils.auth import get_current_supabase_user # Import NEW dependency
from src.models.user import User # Import User model for type hint
# from langgraph.checkpoint.memory import MemorySaver # Remove direct import

# Helper function (consider moving to shared utils)
def get_required_family_id(current_supabase_user: User) -> UUID:
    if current_supabase_user.family_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to a family. Cannot manage stories."
        )
    return current_supabase_user.family_id

# Helper function to calculate age
def calculate_age(born: date | None) -> int | None:
    if born is None:
        return None
    today = date.today()
    try:
        # Calculate age, considering leap years etc.
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        return age
    except TypeError: # Handle cases where comparison might fail (e.g., invalid date components)
        logging.warning(f"Could not calculate age for birthdate {born}")
        return None
# --------------------------

router = APIRouter(
    prefix="/stories",
    tags=["stories"],
    dependencies=[Depends(get_current_supabase_user)], # Use new dependency
    responses={404: {"description": "Not found"}, 401: {"description": "Unauthorized"}},
)

# --- List Stories Endpoint ---
@router.get("/", response_model=List[StoryBasic])
def list_stories(
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """(Authenticated) Retrieve all stories for the user's family."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        # Select only the fields needed for the basic list view
        response = supabase.table("stories")\
            .select("id, title, status, language, created_at")\
            .eq("family_id", str(family_id))\
            .order("created_at", desc=True)\
            .execute()
        
        # response.data will be a list of dictionaries
        # Pydantic will automatically validate them against StoryBasic
        return response.data
    except Exception as e:
        logging.error(f"Error listing stories for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# --- Get Single Story Endpoint --- 
@router.get("/{story_id}", response_model=Story)
def read_story(
    story_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """(Authenticated) Retrieve a single story by ID, checking family ownership."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        response = supabase.table("stories").select("*")\
            .eq("id", str(story_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        if response.data is None:
            raise HTTPException(status_code=404, detail="Story not found or access denied")
        return Story(**response.data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error reading story {story_id} for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# --- Delete Story Endpoint ---
@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_story(
    story_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """(Authenticated) Delete a story and its associated images from storage."""
    family_id = get_required_family_id(current_supabase_user)
    image_paths_to_delete = []
    
    # Helper function to extract storage path (adapted from previous version)
    def get_storage_path(public_url: str | None) -> str | None:
        if not public_url: return None
        try:
            parsed = urlparse(public_url)
            # Path format: /storage/v1/object/public/<bucket_name>/<actual_path>
            path_parts = parsed.path.strip('/').split('/')
            if len(path_parts) >= 5 and path_parts[3] == 'public':
                return "/".join(path_parts[5:]) # Index 5 onwards is the file path
            return None
        except Exception as e:
            logging.error(f"Error parsing storage URL {public_url}: {e}")
            return None

    try:
        # 1. Fetch story pages to get image URLs
        story_response = supabase.table("stories").select("pages")\
            .eq("id", str(story_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()

        if story_response.data and story_response.data.get('pages'):
            pages = story_response.data['pages']
            for page in pages:
                # Check if page is a dict and has image_url
                if isinstance(page, dict) and page.get('image_url'):
                    path = get_storage_path(page['image_url'])
                    if path:
                        image_paths_to_delete.append(path)
            logging.info(f"Identified image paths to delete for story {story_id}: {image_paths_to_delete}")
        else:
            logging.info(f"No story data or pages found for story {story_id}, skipping image path extraction.")

        # 2. Delete story record from DB
        logging.info(f"Attempting to delete story record {story_id} for family {family_id}")
        db_delete_response = supabase.table("stories")\
            .delete()\
            .eq("id", str(story_id))\
            .eq("family_id", str(family_id))\
            .execute()
        # Optional: Check db_delete_response if needed, though delete might not return data
        logging.info(f"Story record {story_id} deleted from database.")

        # 3. Delete images from storage
        if image_paths_to_delete:
            logging.info(f"Attempting to delete {len(image_paths_to_delete)} images from storage for story {story_id}")
            try:
                STORY_IMAGES_BUCKET = "story-images" # Assuming this is the bucket name
                remove_response = supabase.storage.from_(STORY_IMAGES_BUCKET).remove(image_paths_to_delete)
                # Optional: Check remove_response for errors if needed
                logging.info(f"Successfully deleted images from storage for story {story_id}.")
            except Exception as storage_exc:
                # Log error but don't fail the whole request if DB deletion succeeded
                logging.error(f"Error deleting images from storage for story {story_id}: {storage_exc}", exc_info=True)
        else:
            logging.info(f"No images to delete from storage for story {story_id}.")

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logging.error(f"Error deleting story {story_id} for family {family_id}: {str(e)}", exc_info=True)
        # Use a more specific error code if possible (e.g., 404 if initial fetch failed)
        raise HTTPException(status_code=500, detail=f"Internal server error while deleting story: {str(e)}")

# --- Generate Story Endpoint --- 
@router.post("/generate", status_code=status.HTTP_202_ACCEPTED)
def generate_story(
    request: StoryGenerationRequest,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """(Authenticated) Creates initial story record and triggers background generation."""
    
    family_id = get_required_family_id(current_supabase_user)
    logging.info(f"Trigger Story Generation Request Received for family {family_id}")
    logging.debug(f"Request Body: {request.model_dump()}")
    
    target_age = None # Initialize target_age
    characters_info: List[CharacterInfo] = [] # Initialize characters_info

    try:
        # --- Validate Character IDs --- 
        if not request.character_ids:
            logging.warning("Story generation request rejected: No character IDs provided.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="At least one character must be selected."
            )

        # --- Determine Language (before calculating age) ---
        family_language = 'en' # Default fallback
        try:
            family_response = supabase.table("families").select("default_language").eq("id", str(family_id)).maybe_single().execute()
            if family_response.data and family_response.data.get("default_language"):
                family_language = family_response.data["default_language"]
                logging.info(f"Using default language '{family_language}' from family {family_id}")
            else:
                logging.info(f"No default language set for family {family_id}, using fallback '{family_language}'.")
        except Exception as fam_lang_err:
            logging.warning(f"Could not fetch default language for family {family_id}: {fam_lang_err}. Using fallback '{family_language}'.")
        story_language = request.language or family_language
        logging.info(f"Language determined for story generation: {story_language}")
        # --------------------------------

        # --- Determine Target Age from Youngest Main Character --- 
        try:
            # Fetch main character IDs for the family
            main_char_ids_response = supabase.table("family_main_characters")\
                .select("character_id")\
                .eq("family_id", str(family_id))\
                .execute()
            
            if main_char_ids_response.data:
                main_char_ids = [item['character_id'] for item in main_char_ids_response.data]
                logging.info(f"Found main character IDs for age calculation: {main_char_ids}")
                
                # Fetch birthdates for these main characters
                birthdate_response = supabase.table("characters")\
                    .select("id, birthdate")\
                    .in_("id", main_char_ids)\
                    .execute()
                
                if birthdate_response.data:
                    ages = []
                    for char_data in birthdate_response.data:
                        birthdate_str = char_data.get('birthdate')
                        if birthdate_str:
                            try:
                                # Convert string from DB ('YYYY-MM-DD') to date object
                                birthdate_obj = date.fromisoformat(birthdate_str)
                                age = calculate_age(birthdate_obj)
                                if age is not None:
                                    ages.append(age)
                                    logging.debug(f"Character {char_data['id']} age calculated: {age}")
                            except (TypeError, ValueError):
                                logging.warning(f"Could not parse birthdate '{birthdate_str}' for character {char_data['id']}")
                        
                    if ages:
                        target_age = min(ages) # Use the youngest age
                        logging.info(f"Target age set to {target_age} based on youngest main character.")
                    else:
                        logging.info("No valid birthdates found for main characters to determine target age.")
                else:
                    logging.info("No birthdate data found for the selected main characters.")
            else:
                logging.info("No main characters set for this family. Target age will not be set automatically.")
        except Exception as age_calc_err:
            logging.warning(f"Could not automatically determine target age due to error: {age_calc_err}. Proceeding without target age.")
        # -------------------------------------------------------

        # --- Fetch Character Details (including birthdate) --- 
        logging.info(f"Fetching character details for IDs: {request.character_ids}")
        characters_info = [] # Ensure it's reset before fetch
        try:
            # Select id, name, bio, avatar_url, AND birthdate
            char_query = supabase.table("characters")\
                .select("id, name, bio, avatar_url, birthdate, visual_description")\
                .eq("family_id", str(family_id))\
                .in_("id", [str(cid) for cid in request.character_ids])
            char_response = char_query.execute()
            if char_response.data:
                characters_info = [
                    CharacterInfo(
                        id=str(c['id']),
                        name=c['name'],
                        bio=c.get('bio'),
                        avatar_url=c.get('avatar_url'),
                        birth_date=c.get('birthdate'), # Get birthdate
                        visual_description=c.get('visual_description'), # Get visual description
                    ) 
                    for c in char_response.data
                ]
                # Verify all requested characters were found and belong to the family
                if len(characters_info) != len(request.character_ids):
                     logging.warning(f"Could not find all requested characters for family {family_id}. Requested: {request.character_ids}, Found: {[c['id'] for c in characters_info]}")
                     # Depending on requirements, could raise error or proceed with found characters
                     # raise HTTPException(status_code=404, detail="One or more requested characters not found or don't belong to your family.")
            else:
                 logging.warning(f"No characters found for IDs: {request.character_ids} in family {family_id}")
                 raise HTTPException(status_code=404, detail="None of the selected characters were found.")
        except Exception as char_fetch_err:
            logging.error(f"Error fetching character details: {char_fetch_err}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to fetch character details.")
        # -------------------------------------------------------

        # --- Create Initial Story Record in DB --- 
        initial_story_data = {
            "family_id": str(family_id),
            "input_prompt": request.prompt,
            "character_ids": [str(cid) for cid in request.character_ids],
            "target_age": target_age, # Use the calculated age (or None)
            "language": story_language,
            "num_pages": request.num_pages,
            "status": 'INITIALIZING',
            "pages": []
        }
        logging.info(f"Inserting initial story record for family {family_id}")
        insert_response = supabase.table("stories").insert(initial_story_data).execute()

        if not insert_response.data or len(insert_response.data) == 0:
            logging.error(f"Failed to insert initial story record for family {family_id}. Response: {insert_response}")
            raise HTTPException(status_code=500, detail="Failed to create initial story record in database.")

        new_story_record = insert_response.data[0]
        story_id = new_story_record['id']
        logging.info(f"Initial story record created successfully. Story ID: {story_id}")
        # ------------------------------------------

        # Add the graph runner to background tasks, passing the new story_id and language
        background_tasks.add_task(
            run_story_generation,
            story_id=story_id,
            characters_info=characters_info,
            language_code=story_language,
            num_pages=request.num_pages,
        )
        
        logging.info(f"Background task added successfully for story_id: {story_id}")
        # Return the new story ID to the client
        return {"message": "Story creation initiated.", "story_id": story_id}

    except HTTPException as http_exc:
        # Log HTTP exceptions specifically if needed
        logging.error(f"HTTPException in trigger_story_generation: {http_exc.status_code} - {http_exc.detail}", exc_info=(http_exc.status_code == 500)) # Log traceback for 500s
        raise http_exc
    except Exception as e:
        # Catch-all for unexpected errors during setup/initial insert
        error_msg = f"Unexpected error triggering generation: {e}"
        logging.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while initiating story generation.")

# --- Retry Failed Story Generation ---
@router.post("/{story_id}/retry")
def retry_story_generation(
    story_id: UUID,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """Retry a FAILED story generation from scratch."""
    family_id = get_required_family_id(current_supabase_user)

    # Fetch story and verify ownership
    response = supabase.table("stories").select("*")\
        .eq("id", str(story_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()
    if response.data is None:
        raise HTTPException(status_code=404, detail="Story not found or access denied")

    story_data = response.data
    if story_data.get("status") != "FAILED":
        raise HTTPException(status_code=400, detail="Only FAILED stories can be retried.")

    # Reset story state
    supabase.table("stories").update({
        "status": "INITIALIZING",
        "pages": [],
        "title": None,
        "debug_prompts": None,
    }).eq("id", str(story_id)).execute()
    logging.info(f"Story {story_id} reset for retry.")

    # Rebuild characters_info from stored character_ids
    character_ids = story_data.get("character_ids", [])
    characters_info: List[CharacterInfo] = []
    if character_ids:
        char_response = supabase.table("characters")\
            .select("id, name, bio, avatar_url, birthdate, visual_description")\
            .eq("family_id", str(family_id))\
            .in_("id", character_ids)\
            .execute()
        if char_response.data:
            characters_info = [
                CharacterInfo(
                    id=str(c['id']),
                    name=c['name'],
                    bio=c.get('bio'),
                    avatar_url=c.get('avatar_url'),
                    birth_date=c.get('birthdate'),
                    visual_description=c.get('visual_description'),
                )
                for c in char_response.data
            ]

    # Re-trigger generation
    background_tasks.add_task(
        run_story_generation,
        story_id=str(story_id),
        characters_info=characters_info,
        language_code=story_data.get("language", "en"),
        num_pages=story_data.get("num_pages"),
    )

    return {"message": "Story generation retry initiated.", "story_id": str(story_id)}


# --- Stream Story Generation Endpoint ---
@router.get("/{story_id}/stream")
async def stream_story_generation(
    story_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """SSE endpoint to stream story generation progress in real-time."""
    family_id = get_required_family_id(current_supabase_user)

    # Verify story belongs to this family
    response = supabase.table("stories").select("id, status")\
        .eq("id", str(story_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()
    if response.data is None:
        raise HTTPException(status_code=404, detail="Story not found or access denied")

    # If already completed/failed, return current status as single event
    story_status = response.data.get("status")
    if story_status in ("COMPLETED", "FAILED"):
        async def single_event():
            event = "done" if story_status == "COMPLETED" else "error"
            data = {"story_id": str(story_id), "status": story_status}
            yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        return StreamingResponse(single_event(), media_type="text/event-stream")

    # Ensure queue exists for this story (graph nodes will push to it)
    get_or_create_queue(str(story_id))

    return StreamingResponse(
        sse_generator(str(story_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

# --- Deprecated/Removed Endpoints ---
# ...