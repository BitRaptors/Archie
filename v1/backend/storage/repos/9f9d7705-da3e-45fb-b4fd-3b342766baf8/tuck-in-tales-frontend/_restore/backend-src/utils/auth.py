from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from firebase_admin import auth
from typing import Dict, Any, TypedDict, Optional
from uuid import UUID
from supabase import Client, PostgrestAPIError
import logging

from .supabase import get_supabase_client
from ..models.user import User, UserCreate

from . import firebase_admin_init

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserData(TypedDict):
    uid: str
    email: Optional[str]
    name: Optional[str]
    picture: Optional[str]

# Renamed for clarity and focus
def verify_firebase_token(token: str = Depends(oauth2_scheme)) -> UserData:
    """
    Dependency to verify Firebase ID token and return basic user data (uid, email).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get("uid")
        email = decoded_token.get("email")
        name = decoded_token.get("name")
        picture = decoded_token.get("picture")
        if uid is None:
            raise credentials_exception
        return UserData(uid=uid, email=email, name=name, picture=picture)
    except auth.InvalidIdTokenError:
        raise credentials_exception
    except Exception as e:
        logging.error(f"Error verifying Firebase token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error validating authentication token",
        )

# New function to get or create user in Supabase
def get_or_create_supabase_user(user_data: UserData, supabase: Client) -> User:
    """
    Checks if a user exists in Supabase based on Firebase UID.
    If not found, creates the user record (without assigning a family).
    Returns the Supabase user record (as Pydantic model).
    Raises HTTPException on database errors.
    """
    user_id = user_data['uid']
    user_email = user_data.get('email')
    user_name = user_data.get('name')
    user_picture = user_data.get('picture')
    
    try:
        logging.info(f"Checking Supabase for user: {user_id}")
        user_response = supabase.table("users").select("*").eq("id", user_id).maybe_single().execute()

        if user_response and user_response.data:
            logging.info(f"Found existing user {user_id} in Supabase.")
            # Ensure data conforms to User model before returning
            # Add default/None for missing fields if necessary
            db_user_data = user_response.data
            # Make sure family_id is handled if present but potentially not needed here
            return User(**db_user_data)
        else:
            logging.info(f"User {user_id} not found in Supabase. Creating...")
            # Create the new user record WITHOUT a family_id initially
            new_user_payload = UserCreate(
                id=user_id,
                email=user_email,
                display_name=user_name,
                avatar_url=user_picture,
            ).model_dump(exclude_none=True) # Exclude None values like family_id
            
            logging.info(f"Attempting to insert user payload: {new_user_payload}")
            insert_response = supabase.table("users").insert(new_user_payload).execute()

            if not insert_response.data:
                 logging.error(f"Failed to insert new user {user_id} into Supabase.")
                 raise HTTPException(status_code=500, detail="Failed to create new user record in database")
            
            logging.info(f"Successfully created new user {user_id} in Supabase.")
            # Return the newly created user data, conforming to User model
            created_user_data = insert_response.data[0]
            return User(**created_user_data)

    except PostgrestAPIError as e:
        logging.error(f"Supabase DB error during get/create user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Database error accessing user data: {e.message}")
    except Exception as e:
        logging.error(f"Unexpected error during get/create user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Server error during user processing")

# Dependency using the new function
def get_current_supabase_user(user_data: UserData = Depends(verify_firebase_token), supabase: Client = Depends(get_supabase_client)) -> User:
    """Dependency that verifies token and ensures user exists in Supabase DB, returning the User model."""
    return get_or_create_supabase_user(user_data, supabase)

# --- REMOVED OBSOLETE/MISLEADING FUNCTION ---
# async def get_family_id_for_user(user_data: UserData = Depends(get_current_user), supabase: Client = Depends(get_supabase_client)) -> UUID:
#     """
#     Finds the family_id for the authenticated user.
#     If the user doesn't exist in the DB (first login), creates a new family
#     and user record, then returns the new family_id.
#     --- THIS IS BAD PRACTICE - REMOVED ---
#     """
#     pass # Implementation removed

# --- REMOVED OBSOLETE DEPENDENCY CHAIN ---
# Renamed dependency for clarity
# async def get_family_id_for_user(family_id: UUID = Depends(get_family_id_for_user)) -> UUID:
#     """Simple dependency that just returns the family_id obtained by get_family_id_for_user."""
#     return family_id

# --- REMOVED UserRecord related code --- 