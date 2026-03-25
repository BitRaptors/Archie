# src/routes/family.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import logging

from ..services import family_service
from ..models.family import Family # Use Family model from service layer
from ..utils.auth import get_current_supabase_user # Import the new dependency
from ..models.user import User # Import User model for type hint
from supabase import Client # Import sync Client
from ..utils.supabase import get_supabase_client

# --- ADD HELPER FUNCTION --- 
# Helper function (consider moving to shared utils)
def get_required_family_id(current_supabase_user: User) -> uuid.UUID:
    if current_supabase_user.family_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not belong to a family. Cannot perform this operation."
        )
    # Ensure the family_id is returned as a UUID object
    if isinstance(current_supabase_user.family_id, uuid.UUID):
        return current_supabase_user.family_id
    try:
        # Attempt conversion if it's stored as a string representation
        return uuid.UUID(str(current_supabase_user.family_id))
    except ValueError:
        # Handle case where conversion fails
        logging.error(f"Could not convert family_id '{current_supabase_user.family_id}' to UUID for user {current_supabase_user.id}")
        raise HTTPException(status_code=500, detail="Invalid family ID format associated with user.")
# --------------------------

router = APIRouter(
    prefix="/families",
    tags=["families"],
    dependencies=[Depends(get_current_supabase_user)],
)

# --- Request Models ---
class FamilyCreateRequest(BaseModel):
    name: str = "My Family"

class FamilyJoinRequest(BaseModel):
    join_code: str

class FamilySettingsUpdateRequest(BaseModel):
    name: Optional[str] = None
    default_language: Optional[str] = None

# --- Response Models ---
class FamilyMemberResponse(BaseModel):
    id: str # User ID (Firebase UID)
    display_name: Optional[str] = None # Renamed from 'name' to match DB/service model
    avatar_url: Optional[str] = None # Add avatar_url field

# --- NEW: Add Character Summary Response Model --- 
class CharacterSummaryResponse(BaseModel):
    id: uuid.UUID # Use UUID type for consistency
    name: str
    avatar_url: Optional[str] = None
# --------------------------------------------

class FamilyDetailResponse(BaseModel):
    id: uuid.UUID
    name: Optional[str] = None
    join_code: Optional[str] = None
    default_language: Optional[str] = None
    members: List[FamilyMemberResponse] = []
    main_characters: List[CharacterSummaryResponse] = []

class FamilyBasicResponse(BaseModel):
    id: uuid.UUID
    name: str | None = None
    join_code: str | None = None
    default_language: Optional[str] = None

# --- Endpoint for setting main character ---
class SetMainCharacterRequest(BaseModel):
    character_id: uuid.UUID

# --- Endpoints ---

@router.post("/", response_model=FamilyBasicResponse, status_code=status.HTTP_201_CREATED)
def create_new_family(
    request: FamilyCreateRequest,
    current_supabase_user: User = Depends(get_current_supabase_user),
    supabase: Client = Depends(get_supabase_client)
):
    try:
        new_family = family_service.create_family(
            user_id=current_supabase_user.id,
            family_name=request.name,
            supabase=supabase
        )
        return new_family
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error creating family: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error creating family: {e}"
        )

@router.post("/join", response_model=FamilyBasicResponse)
def join_existing_family(
    request: FamilyJoinRequest,
    current_supabase_user: User = Depends(get_current_supabase_user),
    supabase: Client = Depends(get_supabase_client)
):
    try:
        joined_family = family_service.join_family(
            user_id=current_supabase_user.id,
            join_code=request.join_code,
            supabase=supabase
        )
        return joined_family
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error joining family: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error joining family: {e}"
        )

@router.get("/mine", response_model=FamilyDetailResponse | None)
def get_my_family_details(
    current_supabase_user: User = Depends(get_current_supabase_user),
    supabase: Client = Depends(get_supabase_client)
):
    try:
        family_details = family_service.get_family_details_for_user(
            user_id=current_supabase_user.id,
            supabase=supabase
        )
        logging.info(f"Returning family_details from route: {family_details}")
        return family_details
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error fetching family details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error fetching family details: {e}"
        )

@router.put("/mine", response_model=FamilyBasicResponse)
def update_my_family_settings(
    request: FamilySettingsUpdateRequest,
    current_supabase_user: User = Depends(get_current_supabase_user),
    supabase: Client = Depends(get_supabase_client)
):
    """(Authenticated) Update the settings (name, language) of the current user's family."""
    family_id = get_required_family_id(current_supabase_user)
    
    # Prepare update data, filtering out None values
    update_data = request.model_dump(exclude_unset=True) 
    if not update_data: # Check if there's anything to update
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No settings provided for update.")

    try:
        # Assume service layer handles the update logic
        # This function name might need to change in the service layer too
        updated_family = family_service.update_family_settings(
            family_id=family_id,
            update_data=update_data, # Pass the filtered dict
            supabase=supabase
        )
        # Return the basic response, Pydantic handles field matching
        return updated_family
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error updating family settings for family {family_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error updating family settings: {e}"
        )

@router.post("/mine/main_characters", status_code=status.HTTP_204_NO_CONTENT)
def set_main_family_character(
    request: SetMainCharacterRequest,
    current_supabase_user: User = Depends(get_current_supabase_user),
    supabase: Client = Depends(get_supabase_client)
):
    """(Authenticated) Adds a character to the family's main character list."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        family_service.add_main_character(
            family_id=family_id,
            character_id=request.character_id,
            supabase=supabase
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as e:
        raise e
    except Exception as e:
        # Log unexpected errors
        logging.error(f"Error setting main character {request.character_id} for family {family_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error.")

@router.delete("/mine/main_characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_main_family_character(
    character_id: uuid.UUID, # Get character_id from path
    current_supabase_user: User = Depends(get_current_supabase_user),
    supabase: Client = Depends(get_supabase_client)
):
    """(Authenticated) Removes a character from the family's main character list."""
    family_id = get_required_family_id(current_supabase_user)
    try:
        family_service.remove_main_character(
            family_id=family_id,
            character_id=character_id,
            supabase=supabase
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Error removing main character {character_id} for family {family_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error.") 