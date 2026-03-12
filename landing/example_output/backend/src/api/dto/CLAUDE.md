# dto/
> Pydantic request/response DTOs: validate incoming API payloads, serialize database models to JSON. Single entry point for contract enforcement.

## Patterns

- All requests use Field(...) for required, Field(default=...) for optional — zero implicit None
- Response models include timestamps (datetime) and IDs as strings — immutable serialization contract
- Nested models (LibraryCapabilityInput) used for bulk operations — request complexity isolated from response
- Union types (datetime | str | None) in responses handle legacy/polymorphic data from DB
- Optional fields in updates (UpdatePromptRequest, UpdateIgnoredDirsRequest) allow partial PATCH semantics
- Dictionary fields (prompt_config, details) capture unstructured config without over-specifying schema

## Navigation

**Parent:** [`api/`](../CLAUDE.md)
**Peers:** [`middleware/`](../middleware/CLAUDE.md) | [`routes/`](../routes/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `requests.py` | Validate + document inbound API payload shape | Add Field(..., description=...) for required; use | None for optional |
| `responses.py` | Define serialization contract for all API returns | Match DB field names exactly; include timestamps; use datetime type |

## Key Imports

- `from pydantic import BaseModel, Field`
- `from datetime import datetime`
- `from typing import Any`

## Add new request/response pair for fresh endpoint

1. Create request in requests.py with all Field(...) required + Field(default=...) optional
2. Create response in responses.py matching DB schema + timestamps
3. Both inherit BaseModel; both include descriptions for OpenAPI

## Don't

- Don't use bare dict — use typed BaseModel subclass even for one-off nested structures (e.g., LibraryCapabilityInput)
- Don't mix datetime and str types unless handling legacy data — standardize on datetime in new responses
- Don't skip Field(..., description=...) on required fields — breaks OpenAPI documentation and IDE hints

## Testing

- Parse valid JSON against request model — Pydantic raises ValidationError on schema mismatch
- Serialize response model to JSON — round-trip test ensures datetime/None handling

## Why It's Built This Way

- Field(..., description=...) over docstrings — auto-generates OpenAPI schema without duplication
- Separate request/response files — requests validate untrusted input; responses control output contract independently

## Dependencies

**Depends on:** `Application Layer`, `Domain Layer`
**Exposes to:** `frontend`, `external clients`
