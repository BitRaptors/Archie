import re
import time
import logging
from typing import Dict, Optional, Tuple, Any

from src.utils.supabase import get_supabase_client

logger = logging.getLogger(__name__)

# Simple in-memory cache with TTL
_prompt_cache: Dict[str, dict] = {}
_cache_timestamps: Dict[str, float] = {}
CACHE_TTL_SECONDS = 60  # Refresh prompts every 60 seconds


# Fallback defaults - mirrors seed data so the app works without the prompts table
FALLBACK_DEFAULTS: Dict[str, dict] = {
    "avatar_description": {
        "name": "Avatar Description",
        "system_prompt": "You are a visual analysis assistant that extracts key visual features from a SINGLE person's photo for creating a cartoon-style avatar. ALWAYS describe exactly ONE person only.",
        "user_prompt": (
            "Analyze the image and describe the visual features of ONLY ONE PERSON — the main/most prominent subject — for creating a cartoon avatar.\n\n"
            "CRITICAL: Describe EXACTLY ONE person. If multiple people are visible, pick the most prominent/central one and IGNORE everyone else completely. "
            "Do NOT mention other people at all.\n\n"
            "Focus *only* on objective, distinct visual features:\n"
            "- Hair: Style (e.g., short, curly, straight, ponytail), color.\n"
            "- Face Shape: (e.g., round, oval, square).\n"
            "- Eyes: Color, shape (e.g., large, almond). Are glasses worn? If so, briefly describe style.\n"
            "- Nose & Mouth: Basic shape or notable features.\n"
            "- Other Defining Features: beard, mustache, prominent freckles IF clearly visible.\n\n"
            "Output format: A single paragraph describing ONE person only. Keep it concise (50-70 words). "
            "Do NOT start with 'The man and woman...' or 'Two children...' — describe ONE person."
        ),
        "provider": "groq",
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "temperature": 0.3,
        "max_tokens": 200,
        "response_format": None,
        "available_variables": ["character_name"],
    },
    "avatar_image": {
        "name": "Avatar Image",
        "system_prompt": "You are an avatar image generator for a children's story app. Generate avatars of EXACTLY ONE person only.",
        "user_prompt": (
            "Generate a cartoon profile picture/avatar for a character named '@character_name'. "
            "CRITICAL: The avatar must show EXACTLY ONE PERSON. Do NOT include any other people in the image. "
            "Style: Vibrant but simple cartoon illustration, clear lines, friendly expression, head and shoulders view (headshot), "
            "simple/neutral/transparent background. Base the appearance on the visual description: '@visual_description'. "
            "Use the provided reference image(s) to capture the likeness of the SINGLE main subject only — "
            "ignore any other people visible in the reference photos."
        ),
        "provider": "openai",
        "model": "gpt-image-1",
        "temperature": None,
        "max_tokens": None,
        "response_format": None,
        "available_variables": ["character_name", "visual_description"],
    },
    "story_outline": {
        "name": "Story Outline",
        "system_prompt": (
            "You are a creative assistant specializing in children's bedtime stories. Generate a suitable story title and a simple, "
            "structured outline (JSON object: { 'title': 'story title here', 'outline': [{ 'page': 1, 'description': '...', 'characters': ['Character Name 1', 'Character Name 2'] }, ...] }) "
            "for a short story (@num_pages) in @language_name. Base it on the user's prompt and characters involved. Keep descriptions concise. "
            "For each page, list the exact character names (from the provided characters) who appear or are actively involved on that page in the 'characters' array.@age_context"
        ),
        "user_prompt": "Story idea (in @language_name): @story_prompt\n@character_context",
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.2,
        "max_tokens": None,
        "response_format": {"type": "json_object"},
        "available_variables": ["language_name", "story_prompt", "character_context", "age_context", "num_pages"],
    },
    "page_text": {
        "name": "Page Text",
        "system_prompt": (
            "You are a talented children's story author writing in @language_name. Write the content for the current page of a "
            "bedtime story, following the provided context. Focus *only* on the text for page @page_number."
        ),
        "user_prompt": (
            "Story Prompt: @story_prompt\n@character_context\n@memory_context\n@outline_summary\n"
            "Previous Pages Summary:\n@previous_pages\n\n"
            "Write the content FOR ONLY page @page_number in @language_name, which has this description: '@page_description'. "
            "Focus *only* on the narrative for this single page. Ensure smooth transition from previous pages if applicable. "
            "Keep it engaging.@age_context Aim for 2-4 short paragraphs per page."
        ),
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
        "max_tokens": 350,
        "response_format": None,
        "available_variables": [
            "language_name", "story_prompt", "character_context", "memory_context",
            "outline_summary", "previous_pages", "page_number", "page_description", "age_context",
        ],
    },
    "character_detection": {
        "name": "Character Detection",
        "system_prompt": (
            "You are a text analysis assistant. Given a page of a children's story and a list of known character names, "
            "identify which characters appear or are referenced on this page. Return ONLY a JSON object with a single key "
            "'characters' containing an array of character names that appear on this page. Only include names from the "
            "provided known characters list."
        ),
        "user_prompt": (
            "Known characters: @character_names\n\n"
            "Characters already identified from the outline for this page: @outline_characters\n\n"
            "Page text:\n@page_text\n\n"
            "Analyze the text and return a JSON object with ALL characters from the known list that appear, "
            "are mentioned, or are clearly referenced on this page (including the outline characters if they are indeed present)."
        ),
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "max_tokens": 150,
        "response_format": {"type": "json_object"},
        "available_variables": ["character_names", "outline_characters", "page_text"],
    },
    "image_prompt": {
        "name": "Image Prompt",
        "system_prompt": (
            "You are an expert prompt engineer for Openai GPT image generation. "
            "Use the character descriptions (including age context from birth date) to guide the visual details. "
            "CRITICAL RULE: The image must contain NO text, labels, captions, signs, or watermarks AT ALL. "
            "Prefer to show scenes without any visible text. If a sign or text element is absolutely essential to the scene, "
            "write it in @language_name (NEVER in English). For example, use 'ÓVODA' not 'KINDERGARTEN', 'ISKOLA' not 'SCHOOL'."
        ),
        "user_prompt": (
            "Create a Openai GPT image generation prompt for a children's storybook illustration. "
            "Style: @style_keywords.@age_context @character_context @memory_context "
            "Generate a prompt based *only* on the following scene text, focusing on key visual elements and emotions: "
            "\"@page_text\". The prompt should be concise and descriptive for image generation. "
            "IMPORTANT: Instruct the image generator to NOT render any text, words, letters, signs, or labels in the image. "
            "If a sign or text is unavoidable in the scene, it MUST be written in @language_name, never in English."
        ),
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.5,
        "max_tokens": 1000,
        "response_format": None,
        "available_variables": ["style_keywords", "age_context", "character_context", "memory_context", "page_text", "language_name"],
    },
    "memory_photo_analysis": {
        "name": "Memory Photo Analysis",
        "system_prompt": (
            "You are a visual analysis assistant for a family bedtime story app. "
            "Analyze uploaded photos to describe what you see, identify people/pets visible, "
            "and match them against known family characters and recently mentioned names. "
            "Return a JSON response."
        ),
        "user_prompt": (
            "Analyze this photo from a family's memory and return a JSON object.\n\n"
            "Known family characters:\n@character_context\n\n"
            "Recently mentioned names (from the memory text, may be new characters):\n@new_character_names\n\n"
            "Return a JSON object with:\n"
            "1. \"description\": 2-3 sentence description of the photo (scene, setting, activity)\n"
            "2. \"detected_people\": array of people/pets visible in the photo, ordered LEFT to RIGHT, each with:\n"
            "   - \"name\": the character name if you can match them to known characters or recently mentioned names. "
            "Use \"unknown_1\", \"unknown_2\" etc. for unrecognized people.\n"
            "   - \"confidence\": \"high\", \"medium\", or \"low\"\n"
            "   - \"is_known\": true if matched to a known character, false otherwise\n"
            "   - \"visual_note\": brief visual description of this person (hair, clothes, age estimate)\n"
            "   - \"face_x\": horizontal CENTER of this person's HEAD/FACE as a percentage (0-100) from the left edge of the photo. Look at where the nose/eyes are, not the body. E.g., if someone's face is in the middle of the photo, face_x=50.\n"
            "   - \"face_y\": vertical CENTER of this person's HEAD/FACE as a percentage (0-100) from the top edge. Look at eye level. E.g., if someone's face is near the top, face_y=20.\n\n"
            "IMPORTANT: Order people from left to right. For face_x and face_y, focus on the CENTER OF THE FACE (between the eyes), NOT the body or shoulders.\n\n"
            "Match tips: Use the visual descriptions of known characters to match. "
            "For recently mentioned names, try to match by context (e.g., if the text says 'Adam played' and you see a child, that might be Adam). "
            "If you see a person you cannot identify, use \"unknown_N\" as the name."
        ),
        "provider": "groq",
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "temperature": 0.3,
        "max_tokens": 500,
        "response_format": None,
        "available_variables": ["character_context", "new_character_names"],
    },
    "memory_analysis": {
        "name": "Memory Analysis",
        "system_prompt": (
            "You are an intelligent assistant for a family bedtime story app. "
            "Your job is to analyze family memories (text and/or photo descriptions) and categorize them. "
            "You help identify known characters, detect NEW characters not yet in the system, "
            "and provide useful context for future story generation."
        ),
        "user_prompt": (
            "Analyze this family memory and return a JSON response.\n\n"
            "Memory text: @memory_text\n\n"
            "Photo descriptions: @photo_descriptions\n\n"
            "Known family characters:\n@character_context\n\n"
            "Return a JSON object with:\n"
            "1. \"categories\": array of applicable categories from: \"context\", \"new_character\", \"important_event\", \"feeling_emotion\", \"watch_for\"\n"
            "   - \"context\": general background info (place, routine, preference)\n"
            "   - \"new_character\": a new person/pet/friend not in the known characters list\n"
            "   - \"important_event\": milestone, achievement, special day\n"
            "   - \"feeling_emotion\": feelings, fears, joys, emotional states\n"
            "   - \"watch_for\": something to be mindful of in stories (fear of dark, allergy, etc.)\n"
            "2. \"summary\": a concise 1-2 sentence summary of the memory in the same language as the input\n"
            "3. \"linked_characters\": array of objects {\"id\": \"character_id\", \"name\": \"character_name\"} for recognized KNOWN characters\n"
            "4. \"new_characters\": array of NEW people/pets mentioned that are NOT in the known characters list. Each with:\n"
            "   - \"name\": the name of the new character\n"
            "   - \"guessed_bio\": a short bio based on context (e.g., \"Felix's friend from kindergarten\"). Same language as input.\n"
            "5. \"suggestions\": array of suggestion objects for EXISTING character updates (NOT new characters), each with:\n"
            "   - \"type\": one of \"update_character_bio\", \"update_character_visual\", \"update_character_avatar\"\n"
            "   - \"character_id\": the ID of the character to update\n"
            "   - \"character_name\": the name of the character\n"
            "   - \"data\": relevant data (e.g. {\"bio_addition\": \"...\"} for bio update)\n\n"
            "IMPORTANT: New characters go in \"new_characters\", NOT in \"suggestions\". "
            "Be smart about matching: if the text mentions \"Felix fell in the dark\", and there's a known character named Felix, link them. "
            "Write the summary in the same language as the memory text."
        ),
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "max_tokens": 800,
        "response_format": {"type": "json_object"},
        "available_variables": ["memory_text", "photo_descriptions", "character_context"],
    },
    "page_consistency_check": {
        "name": "Page Consistency Check",
        "system_prompt": (
            "You are a lenient story editor for a children's bedtime story. "
            "Your job is to catch ONLY serious problems - not nitpick style or minor details. "
            "Default to PASSING. Only fail a page if there is a clear, obvious problem."
        ),
        "user_prompt": (
            "Story Outline:\n@outline_summary\n\n"
            "Previous Pages (full text):\n@full_previous_pages\n\n"
            "Latest Page (@page_number) text:\n@current_page_text\n\n"
            "Check ONLY for these serious problems:\n"
            "1. REPEATING an event that already happened (e.g. baking a pizza again when it was already baked)\n"
            "2. CONTRADICTING what happened before (e.g. a character leaving but then acting as if they're still there)\n"
            "3. TIMELINE going backwards (e.g. going back to mixing ingredients after the cake is already in the oven)\n\n"
            "Do NOT fail for:\n"
            "- Style differences or tone changes\n"
            "- Minor deviations from the outline description\n"
            "- The first page (it has nothing to contradict)\n"
            "- Adding extra details not in the outline\n"
            "- Different wording than expected\n\n"
            "Return a JSON object:\n"
            "- \"pass\": true unless there is a SERIOUS contradiction, repetition, or timeline error\n"
            "- \"issues\": string describing the serious issue (empty string if pass is true)"
        ),
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.1,
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
        "available_variables": [
            "outline_summary", "full_previous_pages", "current_page_text", "page_number"
        ],
    },
}


def _substitute_variables(template: str, variables: Dict[str, str]) -> str:
    """Replace @variable placeholders in a template string."""
    return re.sub(r'@(\w+)', lambda m: variables.get(m.group(1), m.group(0)), template)


def _fetch_prompt_from_db(slug: str) -> Optional[dict]:
    """Fetch the active prompt for a given slug from Supabase."""
    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("prompts")
            .select("*")
            .eq("slug", slug)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        return response.data
    except Exception as e:
        logger.warning(f"Failed to fetch prompt '{slug}' from DB, using fallback: {e}")
        return None


def _get_prompt_data(slug: str) -> dict:
    """Get prompt data with caching. Falls back to FALLBACK_DEFAULTS if DB is unavailable."""
    now = time.time()

    # Check cache
    if slug in _prompt_cache and (now - _cache_timestamps.get(slug, 0)) < CACHE_TTL_SECONDS:
        return _prompt_cache[slug]

    # Try DB
    db_data = _fetch_prompt_from_db(slug)
    if db_data:
        _prompt_cache[slug] = db_data
        _cache_timestamps[slug] = now
        return db_data

    # Fallback
    if slug in FALLBACK_DEFAULTS:
        logger.info(f"Using fallback defaults for prompt '{slug}'")
        return FALLBACK_DEFAULTS[slug]

    raise ValueError(f"No prompt found for slug '{slug}' in DB or fallback defaults")


def resolve_prompt(slug: str, variables: Optional[Dict[str, str]] = None) -> Tuple[str, str]:
    """
    Fetch the active prompt by slug and substitute @variables.

    Returns:
        Tuple of (system_message, user_message) with variables substituted.
    """
    variables = variables or {}
    data = _get_prompt_data(slug)

    system_prompt = _substitute_variables(data["system_prompt"], variables)
    user_prompt = _substitute_variables(data["user_prompt"], variables)

    return system_prompt, user_prompt


def get_prompt_config(slug: str) -> Dict[str, Any]:
    """
    Get the LLM configuration for a prompt slug.

    Returns:
        Dict with keys: provider, model, temperature, max_tokens, response_format
    """
    data = _get_prompt_data(slug)
    return {
        "provider": data.get("provider", "openai"),
        "model": data.get("model", "gpt-4o-mini"),
        "temperature": data.get("temperature", 0.7),
        "max_tokens": data.get("max_tokens"),
        "response_format": data.get("response_format"),
    }


def invalidate_cache(slug: Optional[str] = None) -> None:
    """Clear the prompt cache. If slug is provided, only clear that entry."""
    if slug:
        _prompt_cache.pop(slug, None)
        _cache_timestamps.pop(slug, None)
    else:
        _prompt_cache.clear()
        _cache_timestamps.clear()
