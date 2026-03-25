from uuid import UUID
from pydantic import BaseModel, Field
from typing import Optional

class UserBase(BaseModel):
    # Assuming users.id maps to Firebase UID (string)
    id: str # Firebase UID
    email: Optional[str] = None
    # Make family_id optional for user creation before family assignment
    family_id: Optional[UUID] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

class UserCreate(UserBase):
    pass

class User(UserBase):
    # No longer need display_name here as it's in Base
    # display_name: Optional[str] = None
    class Config:
        from_attributes = True 