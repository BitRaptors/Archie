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
from src.utils.groq_client import async_groq_client, GroqError
from src.utils.prompt_resolver import resolve_prompt, get_prompt_config
from postgrest.exceptions import APIError # Import APIError

# Assuming models are in src.models, adjust if needed based on project structure
from src.models.character import Character, CharacterCreate, CharacterUpdate, CharacterRelationship, AddRelationshipRequest, UpdateRelationshipRequest
from src.utils.image_crop import crop_image_by_face_x
from pydantic import BaseModel as PydanticBaseModel
import json
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
        
        validated_character = Character(**response.data)

        # Fetch relationships (both directions)
        try:
            rels_from = supabase.table("character_relationships")\
                .select("*")\
                .eq("from_character_id", str(character_id))\
                .execute()
            rels_to = supabase.table("character_relationships")\
                .select("*")\
                .eq("to_character_id", str(character_id))\
                .execute()

            relationships = []
            # Relationships where this character is "from"
            for r in (rels_from.data or []):
                # Fetch target character name/avatar
                target = supabase.table("characters")\
                    .select("name, avatar_url")\
                    .eq("id", r["to_character_id"])\
                    .maybe_single().execute()
                relationships.append(CharacterRelationship(
                    id=r["id"],
                    from_character_id=r["from_character_id"],
                    to_character_id=r["to_character_id"],
                    to_character_name=target.data["name"] if target.data else None,
                    to_character_avatar_url=target.data.get("avatar_url") if target.data else None,
                    relationship_type=r["relationship_type"],
                    created_at=r.get("created_at"),
                ))
            # Relationships where this character is "to" (reverse direction)
            for r in (rels_to.data or []):
                target = supabase.table("characters")\
                    .select("name, avatar_url")\
                    .eq("id", r["from_character_id"])\
                    .maybe_single().execute()
                relationships.append(CharacterRelationship(
                    id=r["id"],
                    from_character_id=r["from_character_id"],
                    to_character_id=r["from_character_id"],  # swap: show the OTHER character
                    to_character_name=target.data["name"] if target.data else None,
                    to_character_avatar_url=target.data.get("avatar_url") if target.data else None,
                    relationship_type=r["relationship_type"],
                    created_at=r.get("created_at"),
                ))
            validated_character.relationships = relationships
        except Exception as rel_err:
            logging.warning(f"Failed to fetch relationships for {character_id}: {rel_err}")
            validated_character.relationships = []

        return validated_character
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

@router.post("/{character_id}/generate_visual_description")
async def generate_visual_description_endpoint(
    character_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user)
):
    """(Authenticated) Generates a visual description from the character's photo using Groq vision."""
    family_id = get_required_family_id(current_supabase_user)

    # 1. Fetch character + validate ownership
    try:
        char_response = supabase.table("characters").select("id, name, photo_paths")\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()

        if char_response is None or not hasattr(char_response, 'data') or char_response.data is None:
            raise HTTPException(status_code=404, detail="Character not found or access denied")

        character_data = char_response.data
        photo_paths = character_data.get('photo_paths') or []
        if not isinstance(photo_paths, list) or not photo_paths:
            raise HTTPException(status_code=400, detail="Character has no photos uploaded.")

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error fetching character {character_id} for visual description: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch character data: {str(e)}")

    # 2. Check Groq client
    if not async_groq_client:
        raise HTTPException(status_code=503, detail="Groq client not initialized. Check GROQ_API_KEY.")

    # 3. Create signed URL for the first photo
    try:
        signed_url_response = supabase.storage.from_("photos").create_signed_url(photo_paths[0], 300)
        signed_photo_url = signed_url_response.get('signedURL')
        if not signed_photo_url:
            raise ValueError("Failed to create signed URL for image")
    except Exception as e:
        logging.error(f"Error creating signed URL for character {character_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to access character photo: {str(e)}")

    # 4. Call Groq vision API
    try:
        character_name = character_data.get('name', 'the character')
        avatar_desc_config = get_prompt_config("avatar_description")
        _, vision_prompt = resolve_prompt("avatar_description", {
            "character_name": character_name,
        })
        groq_model_name = avatar_desc_config.get("model", "meta-llama/llama-4-scout-17b-16e-instruct")

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {"type": "image_url", "image_url": {"url": signed_photo_url}},
                ],
            }
        ]

        vision_response = async_groq_client.chat.completions.create(
            model=groq_model_name,
            messages=messages,
            max_tokens=200,
        )
        visual_desc = vision_response.choices[0].message.content

        if not visual_desc:
            raise ValueError("Groq model returned an empty description.")

        logging.info(f"[VisualDesc - {character_id}] Generated: {visual_desc}")

    except GroqError as ge:
        logging.error(f"Groq API error for character {character_id}: {ge}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Groq API error: {ge}")
    except Exception as e:
        logging.error(f"Error generating visual description for {character_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate visual description: {str(e)}")

    # 5. Save to database
    try:
        supabase.table("characters")\
            .update({"visual_description": visual_desc})\
            .eq("id", str(character_id))\
            .execute()
    except Exception as e:
        logging.error(f"Failed to save visual_description for {character_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generated but failed to save: {str(e)}")

    return {"visual_description": visual_desc}

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


# --- Character Relationships ---

@router.post("/{character_id}/relationships", response_model=CharacterRelationship, status_code=201)
def add_relationship(
    character_id: UUID,
    req: AddRelationshipRequest,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Add a relationship between two characters."""
    family_id = get_required_family_id(current_supabase_user)

    # Verify both characters belong to this family
    for cid in [character_id, req.to_character_id]:
        check = supabase.table("characters").select("id")\
            .eq("id", str(cid)).eq("family_id", str(family_id))\
            .maybe_single().execute()
        if not check.data:
            raise HTTPException(status_code=404, detail=f"Character {cid} not found")

    if character_id == req.to_character_id:
        raise HTTPException(status_code=400, detail="Cannot create relationship with self")

    try:
        data = {
            "from_character_id": str(character_id),
            "to_character_id": str(req.to_character_id),
            "relationship_type": req.relationship_type,
            "family_id": str(family_id),
        }
        response = supabase.table("character_relationships").insert(data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create relationship")

        r = response.data[0]
        # Fetch target character info
        target = supabase.table("characters").select("name, avatar_url")\
            .eq("id", str(req.to_character_id)).maybe_single().execute()

        return CharacterRelationship(
            id=r["id"],
            from_character_id=r["from_character_id"],
            to_character_id=r["to_character_id"],
            to_character_name=target.data["name"] if target.data else None,
            to_character_avatar_url=target.data.get("avatar_url") if target.data else None,
            relationship_type=r["relationship_type"],
            created_at=r.get("created_at"),
        )
    except HTTPException:
        raise
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(status_code=409, detail="Relationship already exists")
        logging.error(f"Error creating relationship: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.put("/{character_id}/relationships/{relationship_id}", response_model=CharacterRelationship)
def update_relationship(
    character_id: UUID,
    relationship_id: UUID,
    req: UpdateRelationshipRequest,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Update the relationship type."""
    family_id = get_required_family_id(current_supabase_user)

    supabase.table("character_relationships")\
        .update({"relationship_type": req.relationship_type})\
        .eq("id", str(relationship_id))\
        .eq("family_id", str(family_id))\
        .execute()

    fetch = supabase.table("character_relationships")\
        .select("*")\
        .eq("id", str(relationship_id))\
        .maybe_single().execute()

    if not fetch.data:
        raise HTTPException(status_code=404, detail="Relationship not found")

    r = fetch.data
    target_id = r["to_character_id"] if r["from_character_id"] == str(character_id) else r["from_character_id"]
    target = supabase.table("characters").select("name, avatar_url")\
        .eq("id", target_id).maybe_single().execute()

    return CharacterRelationship(
        id=r["id"],
        from_character_id=r["from_character_id"],
        to_character_id=target_id,
        to_character_name=target.data["name"] if target.data else None,
        to_character_avatar_url=target.data.get("avatar_url") if target.data else None,
        relationship_type=r["relationship_type"],
        created_at=r.get("created_at"),
    )


@router.delete("/{character_id}/relationships/{relationship_id}", status_code=204)
def delete_relationship(
    character_id: UUID,
    relationship_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Delete a relationship."""
    family_id = get_required_family_id(current_supabase_user)

    supabase.table("character_relationships")\
        .delete()\
        .eq("id", str(relationship_id))\
        .eq("family_id", str(family_id))\
        .execute()

    return Response(status_code=204)


# --- Photo Signed URLs ---

@router.get("/{character_id}/photos/signed-urls")
def get_photo_signed_urls(
    character_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Get signed URLs for character's photos (photos bucket is private)."""
    family_id = get_required_family_id(current_supabase_user)

    char_resp = supabase.table("characters").select("photo_paths")\
        .eq("id", str(character_id)).eq("family_id", str(family_id))\
        .maybe_single().execute()
    if not char_resp.data:
        raise HTTPException(status_code=404, detail="Character not found")

    photo_paths = char_resp.data.get("photo_paths") or []
    signed_urls = []
    for path in photo_paths:
        try:
            result = supabase.storage.from_(PHOTOS_BUCKET).create_signed_url(path, SIGNED_URL_EXPIRY)
            url = result.get("signedURL")
            if url:
                signed_urls.append({"path": path, "url": url})
        except Exception as e:
            logging.warning(f"Failed to create signed URL for {path}: {e}")

    return {"signed_urls": signed_urls}


# --- Photo Person Detection & Cropping ---

class CropPhotoRequest(PydanticBaseModel):
    face_x: float  # 0-100, horizontal center of the person to keep


@router.post("/{character_id}/detect-people")
async def detect_people_in_photo(
    character_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Detect people in character's first photo using Groq vision. Returns detected_people with face positions."""
    family_id = get_required_family_id(current_supabase_user)

    char_resp = supabase.table("characters").select("name, photo_paths, visual_description")\
        .eq("id", str(character_id)).eq("family_id", str(family_id))\
        .maybe_single().execute()
    if not char_resp.data:
        raise HTTPException(status_code=404, detail="Character not found")

    photo_paths = char_resp.data.get("photo_paths") or []
    if not photo_paths:
        raise HTTPException(status_code=400, detail="Character has no photos")

    if not async_groq_client:
        raise HTTPException(status_code=503, detail="Vision model not available")

    photo_path = photo_paths[0]
    try:
        signed_url_response = supabase.storage.from_(PHOTOS_BUCKET).create_signed_url(photo_path, SIGNED_URL_EXPIRY)
        signed_url = signed_url_response.get("signedURL")
        if not signed_url:
            raise HTTPException(status_code=500, detail="Failed to create signed URL")

        # Use the memory_photo_analysis prompt for consistency
        config = get_prompt_config("memory_photo_analysis")
        _, vision_prompt = resolve_prompt("memory_photo_analysis", {
            "character_context": f"- {char_resp.data['name']}",
            "new_character_names": "None",
        })

        model_name = config.get("model", "meta-llama/llama-4-scout-17b-16e-instruct")
        response = async_groq_client.chat.completions.create(
            model=model_name,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": vision_prompt},
                    {"type": "image_url", "image_url": {"url": signed_url}},
                ],
            }],
            max_tokens=config.get("max_tokens", 500),
        )

        raw = response.choices[0].message.content or ""

        # Parse JSON from response
        result = None
        try:
            clean = raw.strip()
            if "```" in clean:
                parts = clean.split("```")
                for part in parts[1:]:
                    candidate = part.strip()
                    if candidate.startswith("json"):
                        candidate = candidate[4:].strip()
                    if candidate.startswith("{"):
                        clean = candidate
                        break
            if not clean.startswith("{"):
                start = clean.find("{")
                end = clean.rfind("}")
                if start != -1 and end > start:
                    clean = clean[start:end + 1]
            result = json.loads(clean)
        except (json.JSONDecodeError, ValueError):
            result = {"description": raw[:300], "detected_people": []}

        return {
            "description": result.get("description", ""),
            "detected_people": result.get("detected_people", []),
            "photo_path": photo_path,
        }

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error detecting people in photo for {character_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Person detection failed: {e}")


@router.post("/{character_id}/crop-photo")
async def crop_character_photo(
    character_id: UUID,
    req: CropPhotoRequest,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Crop character's first photo around a face position and replace it."""
    family_id = get_required_family_id(current_supabase_user)

    char_resp = supabase.table("characters").select("photo_paths")\
        .eq("id", str(character_id)).eq("family_id", str(family_id))\
        .maybe_single().execute()
    if not char_resp.data:
        raise HTTPException(status_code=404, detail="Character not found")

    photo_paths = char_resp.data.get("photo_paths") or []
    if not photo_paths:
        raise HTTPException(status_code=400, detail="Character has no photos")

    photo_path = photo_paths[0]
    try:
        # Download original
        photo_content = supabase.storage.from_(PHOTOS_BUCKET).download(photo_path)
        if not photo_content:
            raise HTTPException(status_code=500, detail="Failed to download photo")

        # Crop
        cropped = crop_image_by_face_x(photo_content, req.face_x)

        # Upload cropped version as a new file
        ext = photo_path.split(".")[-1] if "." in photo_path else "jpg"
        new_path = f"{str(family_id)}/{str(character_id)}/cropped_{uuid4()}.{ext}"

        supabase.storage.from_(PHOTOS_BUCKET).upload(
            path=new_path,
            file=cropped,
            file_options={"content-type": f"image/{ext}", "cache-control": "3600"},
        )

        # Update character: replace first photo path with cropped version
        new_paths = [new_path] + photo_paths[1:]
        supabase.table("characters")\
            .update({"photo_paths": new_paths})\
            .eq("id", str(character_id)).execute()

        logging.info(f"Cropped photo for character {character_id}: face_x={req.face_x}")
        return {"message": "Photo cropped", "new_photo_path": new_path}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error cropping photo for {character_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Crop failed: {e}")