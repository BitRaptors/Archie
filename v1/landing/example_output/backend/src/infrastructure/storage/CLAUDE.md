# storage/
> Abstract storage layer supporting local and temporary file operations via unified async interface.

## Patterns

- All implementations use Path.relative_to(self._base_path) to return normalized, safe paths — never expose full filesystem paths
- Both LocalStorage and TempStorage duplicate save/read/exists/delete logic identically — signals need for shared base class
- Path traversal prevention implicit: constructor enforces base_path, all operations constrained within it via pathlib
- Async method signatures throughout despite synchronous Path I/O — caller expects async but implementation blocks; use run_in_executor if latency matters
- get_url() returns different types: local storage returns absolute filesystem path, temp storage same — contract unclear for cloud implementations
- list_files() only in LocalStorage via rglob('*') — missing from TempStorage despite identical interface requirement

## Navigation

**Parent:** [`infrastructure/`](../CLAUDE.md)
**Peers:** [`analysis/`](../analysis/CLAUDE.md) | [`events/`](../events/CLAUDE.md) | [`external/`](../external/CLAUDE.md) | [`mcp/`](../mcp/CLAUDE.md) | [`persistence/`](../persistence/CLAUDE.md) | [`prompts/`](../prompts/CLAUDE.md)

## Key Files

| File | What It Does | How to Modify |
|------|-------------|---------------|
| `storage_interface.py` | Abstract base defining storage contract. | Add method signatures only, never implementation. Update all concrete classes. |
| `local_storage.py` | Persistent storage against settings.storage_path. | Mirror changes to interface. Watch get_url() contract for clients expecting URLs vs paths. |
| `temp_storage.py` | Ephemeral storage with explicit cleanup semantics. | Resolve paths to absolute (see __init__). Implement list_files() to match LocalStorage. |

## Key Imports

- `from infrastructure.storage.storage_interface import IStorage`

## Add new storage backend (e.g., S3Storage)

1. Inherit from IStorage, implement all 6 abstract methods
2. Ensure save() returns path normalized relative to logical root
3. Test path traversal: save('../../../etc/passwd', ...) must fail or be contained

## Usage Examples

### Safe path handling pattern used in both implementations
```python
full_path = self._base_path / path
full_path.parent.mkdir(parents=True, exist_ok=True)
full_path.write_bytes(content)
return str(full_path.relative_to(self._base_path))
```

## Don't

- Don't accept relative paths in __init__ without resolving — TempStorage.resolve() prevents pwd-context bugs
- Don't return full_path directly — always return relative_to(base_path) to prevent leaking filesystem structure
- Don't skip parent mkdir — both implementations call mkdir(parents=True, exist_ok=True) before writes to handle nested paths

## Testing

- Unit test both implementations with identical test suite — they share interface, behavior should be interchangeable
- Test path traversal safety: attempt save('../../etc', ...) and verify it stays within base_path

## Why It's Built This Way

- Async signatures despite sync Path I/O: future-proofs for cloud storage (S3, GCS) where I/O is truly async
- get_url() returns filesystem path not URL: local storage has no HTTP server; callers must know storage type to use result

## Dependencies

**Depends on:** `Domain Layer`
**Exposes to:** `Application Layer`, `DI Container`
