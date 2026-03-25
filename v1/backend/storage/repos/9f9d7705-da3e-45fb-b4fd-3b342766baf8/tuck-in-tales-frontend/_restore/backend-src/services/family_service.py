# src/services/family_service.py
import uuid
from uuid import UUID
import random
import string
from supabase import PostgrestAPIError, Client # Use sync Client
from fastapi import HTTPException, status
import logging
from src.models.family import FamilyDetails, FamilyMember
from typing import List, Dict, Any, Optional

from ..models.family import Family
from ..models.user import User

def generate_join_code(length=8):
    """Generates a somewhat readable, unique join code (e.g., ABC-DEF)."""
    # Example: Generate XXX-XXX format
    if length < 2:
        length = 2
    parts = []
    part_length = length // 2
    remainder = length % 2
    
    parts.append(''.join(random.choices(string.ascii_uppercase, k=part_length + remainder)))
    parts.append(''.join(random.choices(string.ascii_uppercase, k=part_length)))
    
    return '-'.join(parts)

def create_family(user_id: str, family_name: str | None, supabase: Client) -> Family:
    # 1. Check if user is already in a family
    try:
        logging.info(f"Checking if user {user_id} exists and has a family_id.")
        user_response = supabase.table('users').select('family_id').eq('id', user_id).limit(1).execute()
        logging.info(f"User check response: {user_response.data}")

        if user_response.data and user_response.data[0].get('family_id') is not None:
             logging.warning(f"User {user_id} already belongs to family {user_response.data[0].get('family_id')}")
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already belongs to a family")
        elif not user_response.data:
            logging.error(f"CRITICAL: User with ID {user_id} not found in database during family creation check!")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Authenticated user ID {user_id} not found in database.")

    except PostgrestAPIError as e:
        logging.error(f"Supabase error checking user family: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database error checking user status.")
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error checking user family: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error checking user status.")

    # 2. Generate a unique join code (retry if collision, though unlikely)
    join_code = None
    try:
        for _ in range(5):
            potential_code = generate_join_code()
            logging.info(f"Checking uniqueness of potential join code: {potential_code}")
            # maybe_single() might return None if code doesn't exist.
            code_check_response = supabase.table('families').select('id').eq('join_code', potential_code).maybe_single().execute() 
            
            # Check if code is unique (response is None OR response.data is None/empty)
            if code_check_response is None or code_check_response.data is None:
                logging.info(f"Join code {potential_code} is unique.")
                join_code = potential_code
                break # Found a unique code
            else:
                logging.warning(f"Join code {potential_code} already exists. Retrying...")
                
        if not join_code:
            # Log critical error if we can't generate a unique code after retries
            logging.critical("Failed to generate a unique join code after 5 attempts.")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not generate unique join code")
            
    except PostgrestAPIError as e:
        logging.error(f"Supabase error checking join code uniqueness: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database error checking join code.")
    except Exception as e:
        # Catch unexpected errors like potential network issues during the loop
        logging.error(f"Unexpected error checking join code uniqueness: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error checking join code.")

    # 3. Create the new family
    try:
        new_family_data = {"name": family_name or "My Family", "join_code": join_code}
        family_insert_response = supabase.table('families').insert(new_family_data).execute()
        if not family_insert_response.data:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create family record")
        created_family = family_insert_response.data[0]
        new_family_id = created_family['id']
    except PostgrestAPIError as e:
        logging.error(f"Supabase error creating family: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database error creating family.")
    except Exception as e:
        logging.error(f"Unexpected error creating family: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error creating family.")

    # 4. Update the user's family_id
    try:
        user_update_response = supabase.table('users').update({"family_id": new_family_id}).eq('id', user_id).execute()
    except PostgrestAPIError as e:
        logging.error(f"Supabase error updating user family_id: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database error updating user.")
    except Exception as e:
        logging.error(f"Unexpected error updating user family_id: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error updating user.")

    return Family(**created_family)

def join_family(user_id: str, join_code: str, supabase: Client) -> Family:
    try:
        logging.info(f"Checking if user {user_id} is already in a family.")
        # maybe_single() might be okay with sync client
        user_response = supabase.table('users').select('family_id').eq('id', user_id).maybe_single().execute()
        logging.info(f"User family check response: {user_response.data}")
        if user_response.data and user_response.data.get('family_id'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already belongs to a family")
        # If maybe_single returns None data, we can proceed
        # Note: If user doesn't exist at all, this might still raise 204 error depending on library version

        logging.info(f"Finding family with join_code: {join_code}")
        family_response = supabase.table('families').select('id, name, join_code').eq('join_code', join_code).maybe_single().execute()
        logging.info(f"Family find response: {family_response.data}")
        if not family_response.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid join code")
        family_to_join = family_response.data # .maybe_single() returns dict directly
        family_id = family_to_join['id']

        logging.info(f"Updating user {user_id} with family_id: {family_id}")
        user_update_response = supabase.table('users').update({"family_id": family_id}).eq('id', user_id).execute()
        logging.info(f"User update response status: {getattr(user_update_response, 'status_code', 'N/A')}")

        return Family(**family_to_join)

    except PostgrestAPIError as e:
        logging.error(f"Supabase error joining family: Code={getattr(e, 'code', 'N/A')}, Message={e.message}, Details={getattr(e, 'details', 'N/A')}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Database error joining family: {e.message}")
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.error(f"Unexpected error joining family: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Server error joining family.")

def get_family_details_for_user(user_id: str, supabase: Client) -> Optional[Dict[str, Any]]:
    """Fetches the user's family details, including members and main character IDs."""
    try:
        # 1. Find the user's family_id
        user_response = supabase.table("users").select("family_id").eq("id", user_id).maybe_single().execute()
        if not user_response.data or not user_response.data.get("family_id"):
            logging.info(f"User {user_id} not found or has no family_id.")
            return None # User not in a family

        family_id = user_response.data["family_id"]

        # 2. Fetch family details (including name, join_code, default_language)
        family_response = (supabase.table("families")
            .select("id, name, join_code, default_language") # Add default_language back
            .eq("id", family_id)
            .maybe_single()
            .execute()
        )

        if not family_response.data:
            logging.warning(f"Family {family_id} not found for user {user_id}, though user record indicates membership.")
            # Data inconsistency? Handle appropriately.
            return None

        family_details = family_response.data

        # 3. Fetch members of that family (id, display_name, avatar_url)
        members_response = supabase.table("users")\
            .select("id, display_name, avatar_url")\
            .eq("family_id", family_id)\
            .execute()

        members = members_response.data if members_response.data else []

        # --- Fetch main character IDs --- 
        main_char_ids = []
        try:
            main_char_response = supabase.table("family_main_characters")\
                .select("character_id")\
                .eq("family_id", family_id)\
                .execute()
            if main_char_response.data:
                # Ensure IDs are converted to strings for the .in_() filter below if they are UUIDs
                main_char_ids = [str(item['character_id']) for item in main_char_response.data]
            logging.info(f"Found main character IDs for family {family_id}: {main_char_ids}")
        except Exception as mc_e:
            logging.error(f"Error fetching main character IDs for family {family_id}: {mc_e}", exc_info=True)
        # -------------------------------------

        # --- NEW: Fetch main character summary details --- 
        main_char_summaries = []
        if main_char_ids: # Only query if we have IDs
            try:
                char_summary_response = supabase.table("characters")\
                    .select("id, name, avatar_url")\
                    .in_("id", main_char_ids)\
                    .execute()
                if char_summary_response.data:
                    main_char_summaries = char_summary_response.data
                logging.info(f"Fetched summaries for {len(main_char_summaries)} main characters.")
            except Exception as cs_e:
                 # Log error fetching summaries, but don't fail the request
                 logging.error(f"Error fetching main character summaries for family {family_id}: {cs_e}", exc_info=True)
        # ----------------------------------------------

        # 4. Combine into the response structure
        family_details["members"] = members
        # --- Use the fetched summaries --- 
        family_details["main_characters"] = main_char_summaries 
        # ---------------------------------
        
        logging.info(f"Returning family details from service: {family_details}")
        return family_details

    except Exception as e:
        logging.error(f"Error fetching family details for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error fetching family details.")

# --- Update Family Settings --- 
def update_family_settings(family_id: uuid.UUID, update_data: Dict[str, Any], supabase: Client) -> Dict[str, Any]:
    """Updates specified family settings (e.g., name, default_language). Returns the updated data as a dictionary."""
    if not update_data:
         raise HTTPException(status_code=400, detail="No update data provided.")

    # Optional: Add validation for fields like default_language if needed
    if 'default_language' in update_data and update_data['default_language']:
        lang_code = update_data['default_language']
        if not isinstance(lang_code, str) or not (2 <= len(lang_code) <= 10):
            raise HTTPException(status_code=400, detail=f"Invalid language code format: {lang_code}")

    try:
        # 1. Perform the update operation
        update_response = (
            supabase.table("families")
            .update(update_data)
            .eq("id", str(family_id))
            .execute()
        )
        
        # Basic check: supabase-py v1 returns data on successful update, v2 might differ.
        # If no data or error indicated, raise an exception.
        # Note: Check specific library version documentation for robust error handling.
        if not update_response or not getattr(update_response, 'data', None):
            logging.error(f"Update operation for family {family_id} failed or returned no data. Response: {update_response}")
            # Consider checking for specific error types if the library provides them
            raise HTTPException(status_code=500, detail=f"Database error during update for family {family_id}.")
            
        logging.info(f"Update successful for family {family_id}. Fetching updated record...")

        # 2. Fetch the updated family data separately
        select_response = (
            supabase.table("families")
            .select("*") # Select all fields
            .eq("id", str(family_id))
            .single() # Expect exactly one row
            .execute()
        )

        if not select_response.data:
             # This case might indicate the family_id didn't exist even after update?
             logging.error(f"Failed to retrieve family {family_id} after successful update.")
             raise HTTPException(status_code=404, detail=f"Family with ID {family_id} not found after update.")

        # Return the raw data dictionary - let the route handler handle response model validation
        return select_response.data

    except HTTPException as e:
        raise e # Re-raise validation errors etc.
    except PostgrestAPIError as e:
        # Catch specific Supabase errors during update or select
        logging.error(f"Supabase API error updating/fetching family {family_id}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Database service error: {e.message}")
    except Exception as e:
        logging.error(f"Unexpected error updating family {family_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error updating family settings.")

# --- Main Character Management ---

def add_main_character(family_id: uuid.UUID, character_id: uuid.UUID, supabase: Client):
    """Adds a character to the family's main character list."""
    try:
        # Check if character belongs to the family first?
        char_check = supabase.table("characters")\
            .select("id")\
            .eq("id", str(character_id))\
            .eq("family_id", str(family_id))\
            .maybe_single().execute()
        if not char_check.data:
            raise HTTPException(status_code=404, detail="Character not found in this family.")

        # Insert into junction table (will error if relationship already exists due to PK)
        response = supabase.table("family_main_characters")\
            .insert({"family_id": str(family_id), "character_id": str(character_id)})\
            .execute()
        # Check for errors if needed (supabase-py v1 might require checking response.error)
        logging.info(f"Added character {character_id} as main character for family {family_id}")
    except HTTPException as e:
        raise e
    except PostgrestAPIError as e:
         # Handle potential unique constraint violation (already exists) gracefully?
         if e.code == '23505': # Unique violation code
             logging.warning(f"Character {character_id} is already a main character for family {family_id}. No action needed.")
             # Optionally return success or specific message instead of raising error
             return # Treat as success
         logging.error(f"Database error adding main character: {e}", exc_info=True)
         raise HTTPException(status_code=503, detail=f"Database error: {e.message}")
    except Exception as e:
        logging.error(f"Unexpected error adding main character: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error.")

def remove_main_character(family_id: uuid.UUID, character_id: uuid.UUID, supabase: Client):
    """Removes a character from the family's main character list."""
    try:
        # Delete from junction table
        response = supabase.table("family_main_characters")\
            .delete()\
            .eq("family_id", str(family_id))\
            .eq("character_id", str(character_id))\
            .execute()
        # Check if delete was successful (optional: check response if library provides info)
        logging.info(f"Removed character {character_id} as main character for family {family_id}")
    except Exception as e:
        logging.error(f"Error removing main character: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error removing main character.")

# Add other service functions as needed (e.g., leave_family, remove_member)