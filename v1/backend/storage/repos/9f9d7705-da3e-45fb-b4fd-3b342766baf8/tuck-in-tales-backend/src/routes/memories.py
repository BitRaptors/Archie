from fastapi import APIRouter, HTTPException, Depends, Response, status, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from uuid import UUID, uuid4
from typing import List, Optional
from datetime import date as date_type
from supabase import Client
import logging
import json

from src.models.memory import (
    Memory, MemoryCreate, MemoryUpdate, MemorySearchRequest, MemorySearchResult,
    MemoryConfirmRequest, ApplySuggestionRequest, CreateCharactersFromMemoryRequest,
)
from src.utils.supabase import get_supabase_client
from src.utils.image_crop import crop_image_by_face_x
from src.utils.openai_client import get_embedding
from src.utils.auth import get_current_supabase_user
from src.models.user import User
from src.utils.sse import sse_generator, get_or_create_queue, send_sse_event
from src.graphs.memory_analyzer import run_memory_analysis
from src.graphs.avatar_generator import app as avatar_generator_app, AvatarGeneratorState

MEMORY_PHOTOS_BUCKET = "memory-photos"
MEMORY_SELECT_FIELDS = "id, text, date, family_id, photo_paths, categories, summary, linked_character_ids, analysis_status, raw_analysis, suggestions, created_at"


def get_required_family_id(current_supabase_user: User) -> UUID:
    if current_supabase_user.family_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to a family. Cannot manage memories."
        )
    return current_supabase_user.family_id


router = APIRouter(
    prefix="/memories",
    tags=["memories"],
    dependencies=[Depends(get_current_supabase_user)],
    responses={404: {"description": "Not found"}, 401: {"description": "Unauthorized"}},
)


@router.post("/", response_model=Memory, status_code=201)
async def create_memory(
    background_tasks: BackgroundTasks,
    text: Optional[str] = Form(None),
    date: Optional[str] = Form(None),
    files: List[UploadFile] = File(default=[]),
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Create a new memory with optional text and/or photos. Triggers analysis in background."""
    family_id = get_required_family_id(current_supabase_user)

    if not text and not files:
        raise HTTPException(status_code=400, detail="At least text or a photo is required.")

    # Parse date
    memory_date = date_type.today()
    if date:
        try:
            memory_date = date_type.fromisoformat(date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Upload photos
    photo_paths = []
    for file in files:
        if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum 5MB.")

        ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "jpg"
        storage_path = f"{str(family_id)}/{str(uuid4())}.{ext}"

        try:
            supabase.storage.from_(MEMORY_PHOTOS_BUCKET).upload(
                path=storage_path,
                file=content,
                file_options={"content-type": file.content_type, "cache-control": "3600"},
            )
            photo_paths.append(storage_path)
            logging.info(f"Uploaded memory photo: {storage_path}")
        except Exception as e:
            logging.error(f"Error uploading photo: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to upload photo: {e}")

    # Create memory record
    try:
        memory_data = {
            "family_id": str(family_id),
            "text": text,
            "date": memory_date.isoformat(),
            "photo_paths": photo_paths,
            "analysis_status": "PENDING",
        }

        # Generate initial embedding if text is provided
        if text:
            embedding = await get_embedding(text)
            memory_data["embedding"] = embedding

        response = supabase.table("memories").insert(memory_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create memory in database")

        created = response.data[0]
        memory_id = str(created["id"])

        # Pre-create SSE queue so stream endpoint can connect
        get_or_create_queue(memory_id)

        # Trigger analysis in background
        background_tasks.add_task(
            run_memory_analysis,
            memory_id=memory_id,
            family_id=str(family_id),
            text=text,
            photo_paths=photo_paths,
        )

        return Memory(**created)

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error creating memory for family {family_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error creating memory: {e}")


@router.get("/", response_model=List[Memory])
def read_memories(
    skip: int = 0, limit: int = 100,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Retrieve memories for the current user's family."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        response = supabase.table("memories")\
            .select(MEMORY_SELECT_FIELDS)\
            .eq("family_id", str(family_id))\
            .range(skip, skip + limit - 1)\
            .order("date", desc=True).execute()
        if response.data is None:
            return []
        return [Memory(**m) for m in response.data]
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error reading memories for family {family_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.get("/{memory_id}", response_model=Memory)
def read_memory(
    memory_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Retrieve a single memory by ID."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        response = supabase.table("memories")\
            .select(MEMORY_SELECT_FIELDS)\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        if response.data is None:
            raise HTTPException(status_code=404, detail="Memory not found or access denied")
        return Memory(**response.data)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error reading memory {memory_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.get("/{memory_id}/stream")
async def stream_memory_analysis(
    memory_id: UUID,
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """SSE stream for memory analysis progress."""
    return StreamingResponse(
        sse_generator(str(memory_id)),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{memory_id}/analyze")
async def trigger_analysis(
    memory_id: UUID,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Trigger (re-)analysis for an existing memory."""
    family_id = get_required_family_id(current_supabase_user)

    response = supabase.table("memories")\
        .select(MEMORY_SELECT_FIELDS)\
        .eq("id", str(memory_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory_data = response.data

    # Pre-create SSE queue
    get_or_create_queue(str(memory_id))

    background_tasks.add_task(
        run_memory_analysis,
        memory_id=str(memory_id),
        family_id=str(family_id),
        text=memory_data.get("text"),
        photo_paths=memory_data.get("photo_paths", []),
    )

    return {"message": "Analysis started", "memory_id": str(memory_id)}


@router.post("/{memory_id}/photos", response_model=Memory)
async def upload_memory_photos(
    memory_id: UUID,
    files: List[UploadFile] = File(...),
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Upload additional photos to an existing memory."""
    family_id = get_required_family_id(current_supabase_user)

    response = supabase.table("memories")\
        .select(MEMORY_SELECT_FIELDS)\
        .eq("id", str(memory_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Memory not found")

    existing_paths = response.data.get("photo_paths", []) or []
    new_paths = []

    for file in files:
        if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum 5MB.")

        ext = file.filename.split(".")[-1].lower() if file.filename and "." in file.filename else "jpg"
        storage_path = f"{str(family_id)}/{str(uuid4())}.{ext}"

        supabase.storage.from_(MEMORY_PHOTOS_BUCKET).upload(
            path=storage_path,
            file=content,
            file_options={"content-type": file.content_type, "cache-control": "3600"},
        )
        new_paths.append(storage_path)

    all_paths = existing_paths + new_paths
    supabase.table("memories")\
        .update({"photo_paths": all_paths})\
        .eq("id", str(memory_id)).execute()

    fetch = supabase.table("memories")\
        .select(MEMORY_SELECT_FIELDS)\
        .eq("id", str(memory_id))\
        .maybe_single().execute()

    return Memory(**fetch.data)


@router.post("/{memory_id}/confirm", response_model=Memory)
async def confirm_memory(
    memory_id: UUID,
    confirm_req: MemoryConfirmRequest,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Confirm/edit analysis results. Regenerates embedding from enriched content."""
    family_id = get_required_family_id(current_supabase_user)

    response = supabase.table("memories")\
        .select(MEMORY_SELECT_FIELDS)\
        .eq("id", str(memory_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory_data = response.data

    # Build enriched text for embedding
    text = memory_data.get("text") or ""
    summary = confirm_req.summary or ""
    embedding_text = " ".join(filter(None, [text, summary]))

    update_data = {
        "categories": confirm_req.categories,
        "summary": confirm_req.summary,
        "linked_character_ids": confirm_req.linked_character_ids,
        "analysis_status": "CONFIRMED",
    }

    if embedding_text.strip():
        embedding = await get_embedding(embedding_text)
        update_data["embedding"] = embedding

    supabase.table("memories")\
        .update(update_data)\
        .eq("id", str(memory_id)).execute()

    fetch = supabase.table("memories")\
        .select(MEMORY_SELECT_FIELDS)\
        .eq("id", str(memory_id))\
        .maybe_single().execute()

    return Memory(**fetch.data)


@router.post("/{memory_id}/apply-suggestion")
async def apply_suggestion(
    memory_id: UUID,
    req: ApplySuggestionRequest,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Apply a suggestion from memory analysis (create character, update character, etc.)."""
    family_id = get_required_family_id(current_supabase_user)

    response = supabase.table("memories")\
        .select(MEMORY_SELECT_FIELDS)\
        .eq("id", str(memory_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Memory not found")

    suggestions = response.data.get("suggestions", []) or []
    if req.suggestion_index < 0 or req.suggestion_index >= len(suggestions):
        raise HTTPException(status_code=400, detail="Invalid suggestion index")

    suggestion = suggestions[req.suggestion_index]
    suggestion_type = suggestion.get("type")
    suggestion_data = suggestion.get("data", {})
    character_id = suggestion.get("character_id")

    if not req.approved:
        return {"message": "Suggestion rejected", "suggestion_index": req.suggestion_index}

    if suggestion_type == "new_character":
        # Create a new character
        char_data = {
            "family_id": str(family_id),
            "name": suggestion.get("character_name") or suggestion_data.get("name", "New Character"),
            "bio": suggestion_data.get("bio"),
        }
        char_response = supabase.table("characters").insert(char_data).execute()
        if not char_response.data:
            raise HTTPException(status_code=500, detail="Failed to create character")

        new_char = char_response.data[0]
        return {
            "message": "Character created",
            "suggestion_index": req.suggestion_index,
            "character": new_char,
        }

    elif suggestion_type == "update_character_bio" and character_id:
        bio_addition = suggestion_data.get("bio_addition", "")
        if bio_addition:
            # Fetch current bio and append
            char_resp = supabase.table("characters")\
                .select("bio")\
                .eq("id", character_id)\
                .eq("family_id", str(family_id))\
                .maybe_single().execute()
            if char_resp.data:
                current_bio = char_resp.data.get("bio") or ""
                new_bio = f"{current_bio}\n{bio_addition}".strip() if current_bio else bio_addition
                supabase.table("characters")\
                    .update({"bio": new_bio})\
                    .eq("id", character_id).execute()

        return {"message": "Character bio updated", "suggestion_index": req.suggestion_index}

    elif suggestion_type == "update_character_visual" and character_id:
        visual_desc = suggestion_data.get("visual_description")
        if visual_desc:
            supabase.table("characters")\
                .update({"visual_description": visual_desc})\
                .eq("id", character_id)\
                .eq("family_id", str(family_id)).execute()

        return {"message": "Character visual description updated", "suggestion_index": req.suggestion_index}

    elif suggestion_type == "update_character_avatar" and character_id:
        return {
            "message": "Avatar update suggested. Use the character avatar generation endpoint.",
            "suggestion_index": req.suggestion_index,
            "character_id": character_id,
        }

    return {"message": "Unknown suggestion type", "suggestion_index": req.suggestion_index}


@router.post("/{memory_id}/create-characters")
async def create_characters_from_memory(
    memory_id: UUID,
    req: CreateCharactersFromMemoryRequest,
    background_tasks: BackgroundTasks,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Batch create new characters from memory analysis. Optionally copies memory photos to character photos."""
    family_id = get_required_family_id(current_supabase_user)

    # Verify memory exists and belongs to family
    mem_resp = supabase.table("memories")\
        .select("photo_paths, raw_analysis")\
        .eq("id", str(memory_id))\
        .eq("family_id", str(family_id))\
        .maybe_single().execute()

    if not mem_resp.data:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory_photo_paths = mem_resp.data.get("photo_paths", []) or []
    raw_analysis = mem_resp.data.get("raw_analysis") or {}
    photo_results = raw_analysis.get("photo_results", [])
    created_characters = []

    for char_req in req.characters:
        # Create character
        char_data = {
            "family_id": str(family_id),
            "name": char_req.name,
            "bio": char_req.bio,
        }

        # If photo_index is specified, copy the memory photo (cropped if multi-person)
        char_photo_paths = []
        if char_req.photo_index is not None and 0 <= char_req.photo_index < len(memory_photo_paths):
            source_path = memory_photo_paths[char_req.photo_index]
            try:
                photo_content = supabase.storage.from_(MEMORY_PHOTOS_BUCKET).download(source_path)
                if photo_content:
                    ext = source_path.split(".")[-1] if "." in source_path else "jpg"

                    # Try to crop based on face_x
                    face_x = char_req.face_x  # Prefer explicitly provided face_x from frontend
                    if face_x is None:
                        # Fallback: try to find from raw_analysis
                        pr = next((p for p in photo_results if p.get("photo_index") == char_req.photo_index), None)
                        if pr:
                            people = pr.get("detected_people", [])
                            if len(people) > 1:
                                # Try by name match or pick first unknown
                                person = next((p for p in people if p.get("name", "").lower() == char_req.name.lower()), None)
                                if not person:
                                    # Try unknowns - user tagged this photo to this character
                                    unknowns = [p for p in people if p.get("name", "").startswith("unknown")]
                                    if len(unknowns) == 1:
                                        person = unknowns[0]
                                if person and person.get("face_x") is not None:
                                    face_x = person["face_x"]

                    if face_x is not None:
                        try:
                            photo_content = crop_image_by_face_x(photo_content, face_x)
                            ext = "jpg"  # cropped images are always JPEG
                            logging.info(f"Cropped photo for {char_req.name} at face_x={face_x}")
                        except Exception as crop_err:
                            logging.warning(f"Failed to crop photo for {char_req.name}: {crop_err}")

                    char_photo_paths.append({"content": photo_content, "ext": ext, "source": source_path})
            except Exception as e:
                logging.warning(f"Failed to download memory photo {source_path}: {e}")

        char_response = supabase.table("characters").insert(char_data).execute()
        if not char_response.data:
            logging.error(f"Failed to create character {char_req.name}")
            continue

        new_char = char_response.data[0]
        char_id = new_char["id"]

        # Upload copied photos to character's photos bucket
        if char_photo_paths:
            photos_bucket = "photos"
            uploaded_paths = []
            for photo_info in char_photo_paths:
                dest_path = f"{str(family_id)}/{char_id}/{str(uuid4())}.{photo_info['ext']}"
                try:
                    supabase.storage.from_(photos_bucket).upload(
                        path=dest_path,
                        file=photo_info["content"],
                        file_options={"content-type": f"image/{photo_info['ext']}", "cache-control": "3600"},
                    )
                    uploaded_paths.append(dest_path)
                except Exception as e:
                    logging.warning(f"Failed to upload photo for character {char_req.name}: {e}")

            if uploaded_paths:
                supabase.table("characters")\
                    .update({"photo_paths": uploaded_paths})\
                    .eq("id", char_id).execute()
                new_char["photo_paths"] = uploaded_paths

        created_characters.append(new_char)

        # Trigger avatar generation in background if character has photos
        final_photo_paths = new_char.get("photo_paths", [])
        if final_photo_paths:
            async def _run_avatar(cid, fid, cname, cbio, cpaths):
                try:
                    initial_state = AvatarGeneratorState(
                        character_id=cid,
                        family_id=fid,
                        character_name=cname,
                        character_bio=cbio,
                        photo_paths=cpaths,
                        error_message=None,
                        signed_photo_url=None,
                        visual_description=None,
                        dalle_prompt=None,
                        generated_avatar_url=None,
                        final_avatar_path=None,
                    )
                    get_or_create_queue(str(cid))
                    final_state = await avatar_generator_app.ainvoke(initial_state)
                    final_path = final_state.get("final_avatar_path")
                    final_error = final_state.get("error_message")
                    if final_error:
                        await send_sse_event(str(cid), "error", {"message": final_error})
                    elif final_path:
                        await send_sse_event(str(cid), "complete", {"avatar_url": final_path})
                    else:
                        await send_sse_event(str(cid), "complete", {"avatar_url": None})
                except Exception as e:
                    logging.error(f"Avatar generation failed for {cid}: {e}", exc_info=True)
                    await send_sse_event(str(cid), "error", {"message": str(e)})

            background_tasks.add_task(
                _run_avatar,
                cid=char_id,
                fid=family_id,
                cname=char_req.name,
                cbio=char_req.bio,
                cpaths=final_photo_paths,
            )

    # After all characters are created, parse @mentions in bios to create relationships
    import re
    # Build name→id map for all characters (existing + newly created)
    all_chars_resp = supabase.table("characters").select("id, name")\
        .eq("family_id", str(family_id)).execute()
    name_to_id = {c["name"].lower(): c["id"] for c in (all_chars_resp.data or [])}

    for new_char in created_characters:
        bio = new_char.get("bio") or ""
        if "@{" not in bio:
            continue
        char_id = new_char["id"]
        for match in re.finditer(r'@\{([^}]+)\}', bio):
            mentioned_name = match.group(1)
            target_id = name_to_id.get(mentioned_name.lower())
            if not target_id or target_id == char_id:
                continue
            # Extract relationship type from surrounding text
            full = bio
            start, end = match.start(), match.end()
            before = full[max(0, start - 30):start].strip().split()[-3:] if start > 0 else []
            after = full[end:end + 30].strip().split(".")[:1][0].strip() if end < len(full) else ""
            rel_type = after or " ".join(before) or "connected"
            rel_type = rel_type.strip(" '\".,;:")
            if not rel_type:
                rel_type = "connected"
            try:
                supabase.table("character_relationships").insert({
                    "from_character_id": char_id,
                    "to_character_id": target_id,
                    "relationship_type": rel_type,
                    "family_id": str(family_id),
                }).execute()
                logging.info(f"Created relationship: {new_char.get('name')} -> {mentioned_name} ({rel_type})")
            except Exception as rel_err:
                logging.warning(f"Failed to create relationship from bio mention: {rel_err}")

    return {"message": f"Created {len(created_characters)} character(s)", "characters": created_characters}


@router.post("/search", response_model=List[MemorySearchResult])
async def search_memories(
    search_request: MemorySearchRequest,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Search memories semantically."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        query_embedding = await get_embedding(search_request.query)
        rpc_params = {
            "query_embedding": query_embedding,
            "match_threshold": search_request.match_threshold,
            "match_count": search_request.match_count,
            "filter_family_id": str(family_id),
        }
        response = supabase.rpc("match_memories", params=rpc_params).execute()
        if response.data is None:
            return []
        return [MemorySearchResult(**data) for data in response.data]
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error searching memories for family {family_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error searching memories: {e}")


@router.put("/{memory_id}", response_model=Memory)
async def update_memory(
    memory_id: UUID,
    memory_update: MemoryUpdate,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Update a memory. Regenerates embedding if text changes."""
    family_id = get_required_family_id(current_supabase_user)
    update_data = memory_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    if "text" in update_data and update_data["text"] is not None:
        try:
            embedding = await get_embedding(update_data["text"])
            update_data["embedding"] = embedding
        except Exception as e:
            logging.error(f"Error regenerating embedding for memory {memory_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to regenerate embedding: {e}")

    if "date" in update_data and update_data["date"] is not None:
        update_data["date"] = update_data["date"].isoformat()

    try:
        supabase.table("memories")\
            .update(update_data)\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .execute()

        fetch = supabase.table("memories")\
            .select(MEMORY_SELECT_FIELDS)\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()

        if fetch.data is None:
            raise HTTPException(status_code=404, detail="Memory not found or update failed")

        return Memory(**fetch.data)
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error updating memory {memory_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user),
):
    """Delete a memory and its photos."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        # Fetch to get photo_paths before deleting
        fetch = supabase.table("memories")\
            .select("photo_paths")\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()

        if fetch.data:
            photo_paths = fetch.data.get("photo_paths", []) or []
            for path in photo_paths:
                try:
                    supabase.storage.from_(MEMORY_PHOTOS_BUCKET).remove([path])
                except Exception as e:
                    logging.warning(f"Failed to delete photo {path}: {e}")

        supabase.table("memories")\
            .delete()\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .execute()

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logging.error(f"Error deleting memory {memory_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
