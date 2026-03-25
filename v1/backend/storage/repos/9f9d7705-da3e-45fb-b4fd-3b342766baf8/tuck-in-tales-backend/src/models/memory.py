from uuid import UUID, uuid4
from datetime import date, datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from enum import Enum


class AnalysisStatus(str, Enum):
    PENDING = "PENDING"
    ANALYZING = "ANALYZING"
    ANALYZED = "ANALYZED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class MemoryCategory(str, Enum):
    CONTEXT = "context"
    NEW_CHARACTER = "new_character"
    IMPORTANT_EVENT = "important_event"
    FEELING_EMOTION = "feeling_emotion"
    WATCH_FOR = "watch_for"


class SuggestionType(str, Enum):
    NEW_CHARACTER = "new_character"
    UPDATE_CHARACTER_BIO = "update_character_bio"
    UPDATE_CHARACTER_VISUAL = "update_character_visual"
    UPDATE_CHARACTER_AVATAR = "update_character_avatar"


class MemorySuggestion(BaseModel):
    type: SuggestionType
    character_id: Optional[str] = None
    character_name: Optional[str] = None
    data: dict = Field(default_factory=dict)


class MemoryBase(BaseModel):
    text: Optional[str] = None
    date: date
    # family_id: UUID # Removed - Determined by auth
    # embedding: vector(1536) - Handled internally, not part of API model


class MemoryCreate(BaseModel):
    text: Optional[str] = None
    date: Optional[date] = None  # defaults to today in route


class MemoryUpdate(BaseModel):
    text: Optional[str] = None
    date: Optional[date] = None
    # family_id and embedding cannot be changed directly via API


class Memory(BaseModel):
    id: UUID
    family_id: UUID
    text: Optional[str] = None
    date: date
    photo_paths: List[str] = Field(default_factory=list)
    categories: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    linked_character_ids: List[str] = Field(default_factory=list)
    analysis_status: str = AnalysisStatus.PENDING
    raw_analysis: Optional[Any] = None
    suggestions: Optional[List[MemorySuggestion]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class MemoryConfirmRequest(BaseModel):
    categories: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    linked_character_ids: List[str] = Field(default_factory=list)


class ApplySuggestionRequest(BaseModel):
    suggestion_index: int
    approved: bool = True


class NewCharacterFromMemory(BaseModel):
    name: str
    bio: Optional[str] = None
    photo_index: Optional[int] = None  # which memory photo to copy as character photo
    face_x: Optional[float] = None  # 0-100, for cropping multi-person photos


class CreateCharactersFromMemoryRequest(BaseModel):
    characters: List[NewCharacterFromMemory]


# Models for RAG Search
class MemorySearchRequest(BaseModel):
    query: str
    match_threshold: float = 0.7
    match_count: int = 5


class MemorySearchResult(Memory):
    similarity: float
