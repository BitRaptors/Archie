from uuid import UUID, uuid4
from datetime import datetime, date
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List

class CharacterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=2000)
    photo_paths: Optional[List[str]] = None
    avatar_url: str | None = None
    birth_date: Optional[date] = Field(None, alias='birthdate')
    visual_description: Optional[str] = None
    # family_id: UUID # Removed - Determined by auth

class CharacterCreate(CharacterBase):
    pass

# Model for updating an existing character (all fields optional)
class CharacterUpdate(CharacterBase):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = Field(None, max_length=2000)
    photo_paths: Optional[List[str]] = None
    avatar_url: str | None = None
    birth_date: Optional[date] = Field(None, alias='birthdate')
    visual_description: Optional[str] = None
    # family_id cannot be changed

class CharacterRelationship(BaseModel):
    id: UUID
    from_character_id: UUID
    to_character_id: UUID
    to_character_name: Optional[str] = None
    to_character_avatar_url: Optional[str] = None
    relationship_type: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AddRelationshipRequest(BaseModel):
    to_character_id: UUID
    relationship_type: str = Field(..., min_length=1, max_length=100)


class UpdateRelationshipRequest(BaseModel):
    relationship_type: str = Field(..., min_length=1, max_length=100)


class Character(CharacterBase):
    id: UUID
    family_id: UUID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    relationships: Optional[List[CharacterRelationship]] = None

    class Config:
        from_attributes = True
        populate_by_name = True