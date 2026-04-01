from fastapi import APIRouter, HTTPException, Depends
from typing import List
from supabase import Client
import logging

from src.models.prompt import Prompt, PromptUpdate, PromptTestRequest, PromptTestResponse
from src.utils.supabase import get_supabase_client
from src.utils.prompt_resolver import invalidate_cache
from src.utils.openai_client import async_openai_client
from src.utils.groq_client import async_groq_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["Prompts"])


@router.get("/", response_model=List[Prompt])
def list_prompts(supabase: Client = Depends(get_supabase_client)):
    """List all active prompts."""
    try:
        response = (
            supabase.table("prompts")
            .select("*")
            .eq("is_active", True)
            .order("slug")
            .execute()
        )
        if not response.data:
            return []
        return [Prompt(**p) for p in response.data]
    except Exception as e:
        logger.error(f"Error listing prompts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{slug}", response_model=Prompt)
def get_prompt(slug: str, supabase: Client = Depends(get_supabase_client)):
    """Get the active prompt by slug."""
    try:
        response = (
            supabase.table("prompts")
            .select("*")
            .eq("slug", slug)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if response.data is None:
            raise HTTPException(status_code=404, detail=f"Prompt with slug '{slug}' not found")
        return Prompt(**response.data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prompt '{slug}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/{slug}/history", response_model=List[Prompt])
def get_prompt_history(slug: str, supabase: Client = Depends(get_supabase_client)):
    """Get all versions of a prompt, ordered by version descending."""
    try:
        response = (
            supabase.table("prompts")
            .select("*")
            .eq("slug", slug)
            .order("version", desc=True)
            .execute()
        )
        if not response.data:
            raise HTTPException(status_code=404, detail=f"No prompts found with slug '{slug}'")
        return [Prompt(**p) for p in response.data]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prompt history for '{slug}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.put("/{slug}", response_model=Prompt)
def update_prompt(
    slug: str,
    prompt_update: PromptUpdate,
    supabase: Client = Depends(get_supabase_client),
):
    """Update a prompt: deactivate current active version, create new version with is_active=true."""
    try:
        # 1. Find the current active version to get the version number
        current_response = (
            supabase.table("prompts")
            .select("*")
            .eq("slug", slug)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )

        if current_response.data is None:
            raise HTTPException(status_code=404, detail=f"Active prompt with slug '{slug}' not found")

        current_version = current_response.data["version"]

        # 2. Deactivate the current active version
        supabase.table("prompts").update({"is_active": False}).eq(
            "id", current_response.data["id"]
        ).execute()

        # 3. Create new version
        new_prompt_data = prompt_update.model_dump()
        new_prompt_data["slug"] = slug
        new_prompt_data["version"] = current_version + 1
        new_prompt_data["is_active"] = True

        insert_response = supabase.table("prompts").insert(new_prompt_data).execute()

        if not insert_response.data:
            raise HTTPException(status_code=500, detail="Failed to create new prompt version")

        # 4. Invalidate cache for this slug
        invalidate_cache(slug)

        return Prompt(**insert_response.data[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating prompt '{slug}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.post("/test", response_model=PromptTestResponse)
async def test_prompt(request: PromptTestRequest):
    """Playground: call the appropriate LLM provider and return the response."""
    try:
        if request.provider == "openai":
            messages = [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ]
            kwargs = {
                "model": request.model,
                "messages": messages,
                "temperature": request.temperature,
            }
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens

            completion = await async_openai_client.chat.completions.create(**kwargs)

            return PromptTestResponse(
                response=completion.choices[0].message.content,
                provider=request.provider,
                model=request.model,
                usage={
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                } if completion.usage else None,
            )

        elif request.provider == "groq":
            if not async_groq_client:
                raise HTTPException(
                    status_code=503,
                    detail="Groq client is not initialized. Check GROQ_API_KEY.",
                )

            messages = [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ]
            kwargs = {
                "model": request.model,
                "messages": messages,
                "temperature": request.temperature,
            }
            if request.max_tokens:
                kwargs["max_tokens"] = request.max_tokens

            completion = async_groq_client.chat.completions.create(**kwargs)

            return PromptTestResponse(
                response=completion.choices[0].message.content,
                provider=request.provider,
                model=request.model,
                usage={
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                } if completion.usage else None,
            )

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported provider: {request.provider}. Supported: openai, groq",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing prompt: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"LLM call failed: {str(e)}")
