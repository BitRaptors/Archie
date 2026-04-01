from fastapi import APIRouter, HTTPException, Depends, Response, status, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from src.utils.sse import sse_generator, get_or_create_queue
from uuid import UUID, uuid4
from typing import List, Optional
from supabase import Client
import shutil
import os
from datetime import date # <-- Import date
from src.utils.openai_client import async_openai_client # Import OpenAI client
from src.config import settings # Import settings for model names
import httpx # For downloading generated avatar
import base64 # Potentially for sending image data if URL fails
import logging
from src.graphs.avatar_generator import app as avatar_generator_app, AvatarGeneratorState # Import the graph app and state
from src.utils.sse import send_sse_event
from postgrest.exceptions import APIError # Import APIError

# Assuming models are in src.models, adjust if needed based on project structure
from src.models.character import Character, CharacterCreate, CharacterUpdate
from src.utils.supabase import get_supabase_client
from src.utils.auth import get_current_supabase_user # Import NEW dependency
from src.models.user import User # Import User model for type hint

# Allowed image types
ALLOWED_CONTENT_TYPES = ["image/jpeg", "image/png", "image/webp"]
# Private bucket for original photos
PHOTOS_BUCKET = "photos"
# Public bucket for generated avatars - REMOVED, now in settings
# AVATARS_BUCKET = "avatars"
# Expiry time for signed URLs (in seconds)
SIGNED_URL_EXPIRY = 300 # 5 minutes

router = APIRouter(
    prefix="/characters",
    tags=["characters"],
    # Use the new dependency to ensure user exists for all routes
    # Note: This dependency checks/creates the user, but doesn't guarantee they have a family_id assigned yet.
    # Routes below might need to handle cases where current_supabase_user.family_id is None.
    dependencies=[Depends(get_current_supabase_user)],
    responses={404: {"description": "Not found"}, 401: {"description": "Unauthorized"}},
)

# Helper function within the module to extract family_id or raise error
def get_required_family_id(current_supabase_user: User) -> UUID:
    if current_supabase_user.family_id is None:
        # This should ideally not happen if user creation logic requires a family,
        # but better to handle it defensively.
        # Or, perhaps character creation should be allowed without a family?
        # For now, assume family is required for character operations.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to a family. Cannot manage characters."
        )
    return current_supabase_user.family_id

@router.post("/", response_model=Character, status_code=201)
def create_character(
    character_in: CharacterCreate, 
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Create a new character for the user's family."""
    family_id = get_required_family_id(current_supabase_user) # Get family_id from user
    try:
        logging.info(f"Creating character in family {family_id}") # Use logging
        character_data = character_in.model_dump(by_alias=True)
        
        # --- Convert date object to string before sending to Supabase --- 
        if 'birthdate' in character_data and isinstance(character_data.get('birthdate'), date):
            character_data['birthdate'] = character_data['birthdate'].isoformat()
        # -----------------------------------------------------------------
        
        character_data['family_id'] = str(family_id) # Set family_id
        response = supabase.table("characters").insert(character_data).execute()
        if not response.data:
             raise HTTPException(status_code=500, detail="Failed to create character in database")
        created_character_data = response.data[0]
        return Character(**created_character_data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error creating character for family {family_id}: {str(e)}", exc_info=True) # Use logging
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/", response_model=List[Character])
def read_characters(
    skip: int = 0, limit: int = 100,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Retrieve characters for the current user's family."""
    family_id = get_required_family_id(current_supabase_user) # Get family_id from user
    try:
        response = supabase.table("characters").select("*")\
            .eq("family_id", str(family_id))\
            .range(skip, skip + limit - 1).execute()
        if response.data is None: return []
        characters = [Character(**char_data) for char_data in response.data]
        return characters
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error reading characters for family {family_id}: {str(e)}", exc_info=True) # Use logging
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/{character_id}", response_model=Character)
def read_character(
    character_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Retrieve a single character by ID, checking family ownership."""
    family_id = get_required_family_id(current_supabase_user) # Get family_id from user
    try:
        response = supabase.table("characters").select("*")\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        if response.data is None:
            raise HTTPException(status_code=404, detail="Character not found or access denied")
        
        # --- Log the validated Pydantic model --- 
        validated_character = Character(**response.data)
        logging.info(f"Validated Character data before sending: {validated_character.model_dump()}")
        # -----------------------------------------
        
        return validated_character # Return the validated model
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error reading character {character_id} for family {family_id}: {str(e)}", exc_info=True) # Use logging
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.put("/{character_id}", response_model=Character)
def update_character(
    character_id: UUID,
    character_update: CharacterUpdate,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Update a character in the user's family."""
    family_id = get_required_family_id(current_supabase_user) # Get family_id from user
    update_data = character_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")
    if 'birthdate' in update_data and update_data['birthdate'] is not None:
        update_data['birthdate'] = update_data['birthdate'].isoformat()
    try:
        response = supabase.table("characters")\
            .update(update_data)\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .execute()
        fetch_response = supabase.table("characters").select("*")\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        if fetch_response.data is None:
            raise HTTPException(status_code=404, detail="Character not found or update failed")
        return Character(**fetch_response.data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error updating character {character_id} for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(
    character_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """(Authenticated) Delete a character and associated photos/avatar from storage."""
    family_id = get_required_family_id(current_supabase_user)
    paths_to_delete = { PHOTOS_BUCKET: [], settings.AVATARS_BUCKET: [] }
    try:
        # Fetch photo_paths (array) and avatar_url
        char_response = supabase.table("characters").select("photo_paths, avatar_url")\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        
        if char_response.data:
            photo_paths = char_response.data.get('photo_paths') # Get the array
            avatar_path = char_response.data.get('avatar_url')
            
            # Add all paths from the array to the delete list
            if photo_paths and isinstance(photo_paths, list):
                paths_to_delete[PHOTOS_BUCKET].extend(photo_paths)
            
            if avatar_path: paths_to_delete[settings.AVATARS_BUCKET].append(avatar_path)
        else:
            logging.warning(f"Character {character_id} not found during pre-delete check, proceeding.")
        
        # Proceed with DB deletion
        db_delete_response = supabase.table("characters")\
            .delete()\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .execute()
        
        # Delete files from storage
        for bucket, paths in paths_to_delete.items():
            if paths:
                # Ensure paths is a list of non-empty strings before attempting removal
                valid_paths = [p for p in paths if p and isinstance(p, str)]
                if valid_paths:
                    logging.info(f"Deleting character files from bucket '{bucket}': {valid_paths}")
                    try:
                        remove_response = supabase.storage.from_(bucket).remove(valid_paths)
                    except Exception as storage_exc:
                        logging.error(f"Error deleting files from {bucket} for character {character_id}: {storage_exc}")
                else:
                    logging.warning(f"No valid paths found to delete from bucket '{bucket}' for character {character_id}.")
                    
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        logging.error(f"Error deleting character {character_id} for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/{character_id}/photos", response_model=Character)
async def upload_character_photos(
    character_id: UUID,
    files: List[UploadFile] = File(...),
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """(Authenticated) Upload one or more original photos for a character."""
    family_id = get_required_family_id(current_supabase_user)
    uploaded_file_paths = []
    errors = []
    current_photo_paths = []

    # Fetch current paths first to append
    try:
        owner_check = supabase.table("characters").select("id, photo_paths").eq("id", str(character_id)).eq("family_id", str(family_id)).maybe_single().execute()
        if not owner_check.data:
            raise HTTPException(status_code=404, detail="Character not found or access denied")
        # Ensure photo_paths is treated as a list, even if null/None from DB
        current_photo_paths = owner_check.data.get('photo_paths') or [] 
        if not isinstance(current_photo_paths, list):
             logging.warning(f"Character {character_id} photo_paths is not a list: {current_photo_paths}. Resetting to empty list.")
             current_photo_paths = []

    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Database error checking ownership/fetching paths: {e}")

    # Process uploads
    for file in files:
        # Validate file type
        if file.content_type not in ALLOWED_CONTENT_TYPES:
            errors.append(f"Invalid file type for {file.filename}: {file.content_type}")
            continue

        file_extension = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        file_path = f"{family_id}/{character_id}/original_{uuid4()}.{file_extension}"

        try:
            contents = await file.read()
            upload_response = supabase.storage.from_(PHOTOS_BUCKET).upload(
                path=file_path,
                file=contents,
                file_options={"content-type": file.content_type, "cache-control": "3600", "upsert": "false"}
            )
            uploaded_file_paths.append(file_path)
            logging.info(f"Successfully uploaded {file.filename} to {file_path}")
        except Exception as e:
            logging.error(f"Error uploading file {file.filename} for character {character_id}: {str(e)}", exc_info=True)
            errors.append(f"Failed to upload {file.filename}: {str(e)}")

    # Update character record with the combined list of paths
    if uploaded_file_paths:
        # Combine existing paths with newly uploaded ones
        updated_photo_paths = current_photo_paths + uploaded_file_paths
        try:
            update_response = supabase.table("characters")\
                .update({"photo_paths": updated_photo_paths}) \
                .eq("id", str(character_id))\
                .eq("family_id", str(family_id))\
                .execute()
            logging.info(f"Updated character {character_id} photo_paths to {updated_photo_paths}")
        except Exception as db_update_exc:
            logging.error(f"DB update failed after uploading photos for char {character_id}: {db_update_exc}")
            errors.append(f"Database update failed after uploads: {db_update_exc}")
            # Note: Files are already uploaded even if DB update fails here.
    
    # Fetch and return the character
    try:
        fetch_response = supabase.table("characters").select("*")\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        if fetch_response.data is None:
             raise HTTPException(status_code=404, detail="Character not found after photo upload process")
        
        if errors:
            logging.warning(f"Photo upload completed with errors for character {character_id}: {errors}")
        
        return Character(**fetch_response.data)
    except Exception as final_fetch_exc:
        logging.error(f"Failed to fetch character {character_id} after photo upload: {final_fetch_exc}")
        raise HTTPException(status_code=500, detail="Failed to retrieve character details after photo upload.")

# --- Helper function to run graph in background ---
async def run_avatar_generation_task(
    character_id: UUID, 
    family_id: UUID, 
    name: str, 
    character_bio: Optional[str],
    photo_paths: List[str]
):
    initial_state = AvatarGeneratorState(
        character_id=character_id,
        family_id=family_id,
        character_name=name,
        character_bio=character_bio,
        photo_paths=photo_paths,
        error_message=None,
        signed_photo_url=None,
        visual_description=None,
        dalle_prompt=None,
        generated_avatar_url=None,
        final_avatar_path=None
    )
    logging.info(f"Starting background avatar generation for character {character_id}")
    final_state = None
    try:
        final_state = await avatar_generator_app.ainvoke(initial_state)
        final_error = final_state.get('error_message')
        if final_error:
            logging.error(f"Background avatar generation failed for {character_id}: {final_error}")
            await send_sse_event(str(character_id), "error", {"message": final_error})
        else:
            logging.info(f"Background avatar generation succeeded for {character_id}. Final avatar path: {final_state.get('final_avatar_path')}")
            await send_sse_event(str(character_id), "complete", {"avatar_url": final_state.get('final_avatar_path')})
            # Optionally include final_avatar_path in the message if needed by frontend immediately
    except Exception as e:
        logging.error(f"Exception during background avatar generation task for {character_id}: {e}", exc_info=True)
        await send_sse_event(str(character_id), "error", {"message": f"Unexpected error during generation: {e}"})

@router.post("/{character_id}/generate_avatar", status_code=status.HTTP_202_ACCEPTED)
async def generate_character_avatar_endpoint( # Renamed to avoid conflict
    character_id: UUID,
    background_tasks: BackgroundTasks, # Inject background tasks
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """(Authenticated) Triggers asynchronous avatar generation based on character photos."""
    family_id = get_required_family_id(current_supabase_user)

    # 1. Fetch character data needed for the graph
    try:
        char_response = supabase.table("characters").select("id, name, bio, photo_paths")\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        
        # Check response explicitly - Postgrest might return an APIResponse object
        # even on errors sometimes, or data might be None on not found.
        if char_response is None or not hasattr(char_response, 'data') or char_response.data is None:
             logging.warning(f"Character {character_id} not found or invalid response during avatar trigger fetch.")
             raise HTTPException(status_code=404, detail="Character not found or access denied")
        
        character_data = char_response.data
        photo_paths = character_data.get('photo_paths') or []
        if not isinstance(photo_paths, list) or not photo_paths:
             # Check photo_paths *after* confirming character exists
             raise HTTPException(status_code=400, detail="Character has no photos uploaded to generate an avatar from.")

    except APIError as db_error:
        # Catch specific Postgrest errors
        logging.error(f"Supabase APIError fetching character {character_id} for avatar trigger: {db_error}", exc_info=True)
        # Try to return a more specific error message if possible
        error_detail = f"Database error fetching character details: {db_error.message} (Code: {db_error.code})"
        raise HTTPException(status_code=500, detail=error_detail)
    except HTTPException as http_exc:
        # Re-raise our own HTTPExceptions (like 404, 400)
        raise http_exc
    except Exception as e:
        # Catch any other unexpected errors
        logging.error(f"Unexpected error fetching character {character_id} for avatar trigger: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch character data before starting generation: {str(e)}")

    # 2. Add the graph execution to background tasks
    background_tasks.add_task(
        run_avatar_generation_task,
        character_id=character_id, 
        family_id=family_id, 
        name=character_data.get('name'),
        character_bio=character_data.get('bio'),
        photo_paths=photo_paths
    )

    # 3. Return Accepted immediately
    return {"message": "Avatar generation process started."}

@router.get("/{character_id}/avatar/stream")
async def stream_avatar_generation(
    character_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """SSE endpoint to stream avatar generation progress."""
    family_id = get_required_family_id(current_supabase_user)

    # Verify character belongs to family
    response = supabase.table("characters").select("id, avatar_url")\
        .eq("id", str(character_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()
    if response.data is None:
        raise HTTPException(status_code=404, detail="Character not found or access denied")

    get_or_create_queue(str(character_id))

    return StreamingResponse(
        sse_generator(str(character_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

# TODO: Implement GET /families/{family_id}/characters (or filter GET / by family_id)
# TODO: Integrate with actual database (Supabase) 