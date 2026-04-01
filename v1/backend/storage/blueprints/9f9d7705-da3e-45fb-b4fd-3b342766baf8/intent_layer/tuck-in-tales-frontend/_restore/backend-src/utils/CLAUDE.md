# utils/
> Utility layer for authentication, LLM clients, and infrastructure initialization with strict single-responsibility per file.

## Patterns

- Global client instances initialized on module import with graceful degradation (Gemini, Groq, OpenAI all follow this pattern)
- Firebase token → Supabase user lookup/creation pipeline: verify_firebase_token → get_or_create_supabase_user → get_current_supabase_user
- TypedDict (UserData) bridges Firebase decoded claims to internal models without full ORM overhead
- Supabase upsert logic uses maybe_single().execute() with explicit None checks before assuming data exists
- API client initialization defers to settings object; missing keys log warnings, not crashes (except OpenAI which raises)
- HTTPException with structured logging on all auth failures; PostgrestAPIError caught separately from generic exceptions

## Navigation

**Parent:** [`backend-src/`](../CLAUDE.md)
**Peers:** [`graphs/`](../graphs/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`routes/`](../routes/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `auth.py` | Firebase token verification and Supabase user sync | Always use Depends() in route handlers; never call functions directly |
| `firebase_admin_init.py` | One-time Firebase Admin SDK setup | Import this in main.py startup; don't re-initialize per request |
| `openai_client.py` | AsyncOpenAI instance and embedding helper | Raise ValueError if OPENAI_API_KEY missing; use async_openai_client globally |
| `gemini_client.py` | Gemini image generation with reference image support | Check if async_gemini_client is None before calling; handle base64 encoding internally |
| `groq_client.py` | Groq LLM client with graceful missing-key fallback | Call get_groq_client() to check availability; None is valid return |
| `supabase.py` | Supabase client factory (not shown but imported) | Provides get_supabase_client() dependency; use in Depends() |
| `sse.py` | Server-sent events handler (not shown but present) | Likely streaming response utility; check before modifying auth flow |

## Key Imports

- `from .auth import get_current_supabase_user`
- `from .openai_client import async_openai_client, get_embedding`
- `from .supabase import get_supabase_client`

## Add new authenticated endpoint using current user

1. Import get_current_supabase_user from auth.py
2. Add parameter: user: User = Depends(get_current_supabase_user)
3. Route receives User object with id, email, display_name; use user.id for DB queries

## Usage Examples

### Typical dependency chain in a route handler
```python
async def create_story(
    user: User = Depends(get_current_supabase_user)
):
    # user.id is Firebase UID, guaranteed in Supabase
    return {"family_id": user.family_id}
```

## Don't

- Don't initialize API clients in route handlers — initialize once at module import, check None at call time
- Don't assume Supabase query returns data without calling maybe_single() — use .data check before unpacking
- Don't create family/user in auth layer — auth.py only verifies and syncs; family creation belongs in business logic

## Testing

- Mock Firebase token with auth.verify_id_token; test both existing and new user paths in Supabase
- Verify .exclude_none=True on UserCreate prevents null family_id from being inserted

## Debugging

- If user not found: check Supabase schema matches User model fields; PostgrestAPIError.message contains query details
- If Firebase init fails silently: check FIREBASE_SERVICE_ACCOUNT_KEY_PATH exists and is valid JSON

## Why It's Built This Way

- UserData as TypedDict instead of full Pydantic model: Firebase claims are optional, need flexible bridge before DB insert
- get_or_create_supabase_user is sync (not async) because Supabase SDK is blocking; wrap at route level if needed
