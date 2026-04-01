# utils/
> Authentication, LLM client initialization, and image utilities. All clients init globally on import with graceful degradation if keys missing.

## Patterns

- Global client initialization on module import (gemini, groq) with None fallback if API keys missing
- Firebase token verification returns TypedDict with optional fields (email, name, picture); never assume presence
- Supabase user get-or-create pattern: query with maybe_single(), check data presence, insert if missing
- All LLM clients (groq, gemini) exposed as module-level Optional variables; callers must null-check before use
- Image utilities work directly with bytes/BytesIO; always handle both types (read() vs direct)
- HTTP exceptions raised with appropriate status codes: 401 auth, 503 Supabase errors, 500 unexpected

## Navigation

**Parent:** [`src/`](../CLAUDE.md)
**Peers:** [`graphs/`](../graphs/CLAUDE.md) | [`models/`](../models/CLAUDE.md) | [`routes/`](../routes/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `auth.py` | Firebase token verification and Supabase user sync | Update get_or_create_supabase_user if user fields change; keep UserData TypedDict in sync |
| `firebase_admin_init.py` | One-time Firebase Admin SDK setup via import | Check settings.FIREBASE_SERVICE_ACCOUNT_KEY_PATH; runs once on first import |
| `gemini_client.py` | Gemini image generation with reference image support | Base64-encode reference images; check response.candidates[0].content.parts for inline_data |
| `groq_client.py` | Global Groq LLM client via API key | Use get_groq_client() getter; null-check before calling inference |
| `image_crop.py` | Crop image around detected face x-coordinate | face_x is percentage (0-100); crop_width_pct is fraction (0.0-1.0); converts RGBA→RGB for JPEG |
| `supabase.py` | Supabase client dependency injection | Exposes get_supabase_client(); used by auth.py for user operations |

## Key Imports

- `from src.utils.auth import get_current_supabase_user, verify_firebase_token`
- `from src.utils.supabase import get_supabase_client`
- `from src.utils.groq_client import get_groq_client`

## Add new LLM client or API integration

1. Create new_client.py with global Optional[ClientType] variable initialized on import
2. Add conditional init: if API_KEY exists, initialize; else log warning and set to None
3. Export getter function (get_new_client()) that returns Optional and warns if None
4. Callers must null-check before use: if client: await client.call(...)

## Usage Examples

### Get-or-create user pattern (auth.py)
```python
user_response = supabase.table("users").select("*").eq("id", user_id).maybe_single().execute()
if user_response.data:
    return User(**user_response.data)
else:
    insert_response = supabase.table("users").insert(new_user_payload).execute()
    return User(**insert_response.data[0])
```

## Don't

- Don't assume Firebase token fields exist (email/name/picture) — use .get() with Optional return type
- Don't create user WITHOUT checking existence first — always query maybe_single() before insert
- Don't skip null-check on global LLM clients — gemini_client and async_groq_client can be None if init failed

## Testing

- Auth: mock verify_id_token to return test uid; mock supabase.table().select() to test get-or-create flow
- Image crop: test with 1000x800 image, face_x=50, verify center crop; test crop_width_pct clipping at edges

## Debugging

- If Gemini returns text instead of image: response.candidates[0].content.parts loops over parts; text part appears instead of inline_data
- Supabase insert fails silently if schema mismatch: check insert_response.data presence and log new_user_payload before insert

## Why It's Built This Way

- Global client init on import (not lazy) ensures fast first-call response; trade-off is startup overhead if keys invalid
- TypedDict for UserData instead of Pydantic to avoid validation overhead on token decode; User model used only for DB records

## Dependencies

**Depends on:** `Configuration`
**Exposes to:** `Graph Layer`
