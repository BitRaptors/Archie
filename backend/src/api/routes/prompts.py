"""Prompt management routes."""
from fastapi import APIRouter, HTTPException
from typing import List
from api.dto.requests import CreatePromptRequest, UpdatePromptRequest
from api.dto.responses import PromptResponse

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("/", response_model=List[PromptResponse])
async def list_prompts(
    user_id: str | None = None,  # Would come from auth
    category: str | None = None,
):
    """List all prompts (default + user custom)."""
    return []


@router.get("/default", response_model=List[PromptResponse])
async def list_default_prompts():
    """List default prompts."""
    from infrastructure.prompts.default_prompts import get_default_prompts
    prompts = get_default_prompts()
    return [PromptResponse(**p.__dict__) for p in prompts]


@router.get("/custom", response_model=List[PromptResponse])
async def list_custom_prompts(
    user_id: str,  # Would come from auth
):
    """List user's custom prompts."""
    return []


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: str):
    """Get prompt details."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/", response_model=PromptResponse)
async def create_prompt(
    request: CreatePromptRequest,
    user_id: str,  # Would come from auth
):
    """Create custom prompt."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str,
    request: UpdatePromptRequest,
    user_id: str,  # Would come from auth
):
    """Update custom prompt."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/{prompt_id}")
async def delete_prompt(
    prompt_id: str,
    user_id: str,  # Would come from auth
):
    """Delete custom prompt."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{prompt_id}/test")
async def test_prompt(
    prompt_id: str,
    sample_data: dict,
):
    """Test prompt with sample data."""
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/categories")
async def list_categories():
    """List available prompt categories."""
    from config.constants import PromptCategory
    return {
        "categories": [
            PromptCategory.STRUCTURE,
            PromptCategory.PATTERNS,
            PromptCategory.PRINCIPLES,
            PromptCategory.BLUEPRINT_SYNTHESIS,
            PromptCategory.DIRECTORY_SUMMARY,
            PromptCategory.PATTERN_DEEP_DIVE,
        ]
    }

