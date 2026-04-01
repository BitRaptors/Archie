from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from typing import List, Optional # Import List and Optional
from datetime import datetime

class FamilyBase(BaseModel):
    name: str | None = None # Name might be optional initially

class FamilyCreate(FamilyBase):
    pass

class Family(FamilyBase):
    id: UUID = Field(default_factory=uuid4)
    join_code: str | None = None # Add join_code field
    created_at: datetime
    default_language: Optional[str] = None # Add language setting

    class Config:
        from_attributes = True

# New models for detailed view
class FamilyMember(BaseModel):
    id: UUID
    email: Optional[str] = None # Email might not always be available
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None # Add avatar URL

class FamilyDetails(BaseModel):
    id: UUID
    name: Optional[str] = None
    join_code: Optional[str] = None
    members: List[FamilyMember] = []

    class Config:
        from_attributes = True

class FamilyUpdate(BaseModel):
    name: Optional[str] = None
    default_language: Optional[str] = None # Add language setting

# Response model including members 