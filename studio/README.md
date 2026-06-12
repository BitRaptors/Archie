# Archie Studio (experimental)

Internal-only 3-tab local app: PRD reader, embedded archie-viewer, workflow
placeholder. Not shipped via npm; nothing here is referenced by
`manifest_data.py` or `verify_sync.py`.

## Run

    cd studio/frontend && npm install && npm run build   # once, and after frontend changes
    python3 studio/server.py /path/to/project [--prd docs/prd] [--port 5848] [--no-open]

Opens http://localhost:5848/. The Architecture tab needs the target project to
have a `.archie/` (run `/archie-deep-scan` there). The Product tab reads
markdown from `docs/prd/` or `prd/` in the target project (or `--prd <path>`).

## Develop

    python3 studio/server.py /path/to/project --no-open   # API on 5848
    cd studio/frontend && npm run dev                      # Vite proxies /api -> 5848

Tests: `python -m pytest tests/test_studio_server.py` and
`cd studio/frontend && npm test`.

## Architecture notes

- `server.py` subclasses the handler from `archie/standalone/viewer.py` --
  all viewer API endpoints are inherited; studio only adds `/api/prd/*`.
- The frontend's `@` alias points at `npm-package/assets/viewer/src` so the
  viewer's components (and their internal `@/` imports) work here unmodified.
  Studio's own code uses relative imports only. The same constraint drives
  the tsconfig `"*"` paths fallback and the vite `resolve.dedupe` list.
- The Architecture tab applies a scoped CSS shim to offset the viewer's
  fixed sidebar past the studio icon rail (see ArchitectureTab.tsx).
- Design doc: `docs/plans/2026-06-12-archie-studio-design.md` (local, gitignored).
