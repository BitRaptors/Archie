from fastapi import APIRouter, HTTPException, Depends, Response, status
from uuid import UUID
from typing import List
from supabase import Client
from openai import AsyncOpenAI
import logging # Import logging

from src.models.memory import Memory, MemoryCreate, MemoryUpdate, MemorySearchRequest, MemorySearchResult
from src.utils.supabase import get_supabase_client
from src.utils.openai_client import get_embedding # Needs to be async or refactored
from src.utils.auth import get_current_supabase_user # Import NEW dependency
from src.models.user import User # Import User model for type hint

# Helper function (consider moving to shared utils)
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
    dependencies=[Depends(get_current_supabase_user)], # Use new dependency
    responses={404: {"description": "Not found"}, 401: {"description": "Unauthorized"}},
)

# WARNING: Mixing async routes with sync DB client. create_memory, search_memories, 
# and update_memory call the async get_embedding function.
# Keeping them async for now, but ideally refactor embedding or the whole stack.

@router.post("/", response_model=Memory, status_code=201)
async def create_memory(
    memory_in: MemoryCreate, 
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Log a new memory for the user's family."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        logging.info(f"Creating memory in family {family_id}") # Use logging
        memory_data = memory_in.model_dump()
        memory_data['family_id'] = str(family_id) # Set family_id
        if memory_data.get('date'):
            memory_data['date'] = memory_data['date'].isoformat()

        # Embedding call is async
        embedding_vector = await get_embedding(memory_in.text)
        memory_data['embedding'] = embedding_vector

        # DB call is sync
        response = supabase.table("memories").insert(memory_data).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create memory in database")
        created_memory_data = response.data[0]
        return Memory(**created_memory_data)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error creating memory for family {family_id}: {str(e)}", exc_info=True) # Use logging
        raise HTTPException(status_code=500, detail=f"Error creating memory: {str(e)}")

# Make read_memories synchronous
@router.get("/", response_model=List[Memory])
def read_memories(
    skip: int = 0, limit: int = 100,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Retrieve memories for the current user's family."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        response = supabase.table("memories")\
            .select("id, text, date, family_id, created_at")\
            .eq("family_id", str(family_id))\
            .range(skip, skip + limit - 1)\
            .order("date", desc=True).execute()
        if response.data is None: return []
        memories = [Memory(**memory_data) for memory_data in response.data]
        return memories
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error reading memories for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Make read_memory synchronous
@router.get("/{memory_id}", response_model=Memory)
def read_memory(
    memory_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Retrieve a single memory by ID, checking family ownership."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        response = supabase.table("memories")\
            .select("id, text, date, family_id, created_at")\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        if response.data is None:
            raise HTTPException(status_code=404, detail="Memory not found or access denied")
        return Memory(**response.data)
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error reading memory {memory_id} for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.post("/search", response_model=List[MemorySearchResult])
async def search_memories(
    search_request: MemorySearchRequest, 
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Search memories in the user's family."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        # Embedding call is async
        query_embedding = await get_embedding(search_request.query)
        rpc_params = {
            'query_embedding': query_embedding,
            'match_threshold': search_request.match_threshold,
            'match_count': search_request.match_count,
            'filter_family_id': str(family_id)
        }
        # DB call is sync
        response = supabase.rpc('match_memories', params=rpc_params).execute()
        if response.data is None: return []
        search_results = [MemorySearchResult(**data) for data in response.data]
        return search_results
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error searching memories for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error searching memories: {str(e)}")

@router.put("/{memory_id}", response_model=Memory)
async def update_memory(
    memory_id: UUID,
    memory_update: MemoryUpdate,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Update a memory in the user's family. Regenerates embedding if text changes."""
    family_id = get_required_family_id(current_supabase_user)
    update_data = memory_update.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    new_embedding = None
    if "text" in update_data and update_data["text"] is not None:
        try:
            logging.info(f"Regenerating embedding for updated memory {memory_id}") # Use logging
            # Embedding call is async
            new_embedding = await get_embedding(update_data["text"])
            update_data["embedding"] = new_embedding
        except Exception as e:
            logging.error(f"Error regenerating embedding for memory {memory_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to regenerate embedding: {e}")

    if 'date' in update_data and update_data['date'] is not None:
        update_data['date'] = update_data['date'].isoformat()

    try:
        # DB call is sync
        update_response = supabase.table("memories")\
            .update(update_data)\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .execute()

        fetch_response = supabase.table("memories")\
            .select("id, text, date, family_id, created_at")\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()

        if fetch_response.data is None:
            raise HTTPException(status_code=404, detail="Memory not found or update failed")

        return Memory(**fetch_response.data)

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logging.error(f"Error updating memory {memory_id} for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Make delete_memory synchronous
@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: UUID,
    supabase: Client = Depends(get_supabase_client),
    current_supabase_user: User = Depends(get_current_supabase_user) # Use new dependency
):
    """(Authenticated) Delete a memory from the user's family."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        response = supabase.table("memories")\
            .delete()\
            .eq("id", str(memory_id))\
            .eq("family_id", str(family_id))\
            .execute()

        return Response(status_code=status.HTTP_204_NO_CONTENT)

    except Exception as e:
        logging.error(f"Error deleting memory {memory_id} for family {family_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# TODO: Implement GET /families/{family_id}/memories (or filter GET /)
# TODO: Integrate embedding generation 