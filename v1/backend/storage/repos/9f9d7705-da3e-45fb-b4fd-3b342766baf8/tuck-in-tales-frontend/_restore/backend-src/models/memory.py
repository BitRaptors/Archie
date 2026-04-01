from uuid import UUID, uuid4
from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Optional

class MemoryBase(BaseModel):
    text: str
    date: date
    # family_id: UUID # Removed - Determined by auth
    # embedding: vector(1536) - Handled internally, not part of API model

class MemoryCreate(MemoryBase):
    pass

# Model for updating a memory
class MemoryUpdate(BaseModel):
    text: Optional[str] = None
    date: Optional[date] = None
    # family_id and embedding cannot be changed directly via API

class Memory(MemoryBase):
    id: UUID
    family_id: UUID # Add family_id back for the full model
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True

# Models for RAG Search
class MemorySearchRequest(BaseModel):
    query: str
    family_id: UUID
    match_threshold: float = 0.7  # Default similarity threshold
    match_count: int = 5          # Default number of results

class MemorySearchResult(Memory):
    similarity: float # Add similarity score to the result