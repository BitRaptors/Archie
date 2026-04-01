"""Lightweight viewer server — reads from .archie/ files, no database needed."""

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click


def run_serve(project_root: Path, port: int = 8000) -> None:
    """Start the lightweight viewer server."""
    project_root = project_root.resolve()
    blueprint_path = project_root / ".archie" / "blueprint.json"

    if not blueprint_path.exists():
        click.echo(
            f"Error: {blueprint_path} not found.\n"
            "Run `archie init` first to generate the blueprint.",
            err=True,
        )
        raise SystemExit(1)

    import uvicorn

    app = _build_app(project_root)

    click.echo(f"Archie viewer server starting on http://localhost:{port}")
    click.echo(f"Project root: {project_root}")
    click.echo(f"Blueprint:    {blueprint_path}")
    click.echo("")
    click.echo("Open the frontend at http://localhost:4000 (run `cd frontend && npm run dev`)")
    click.echo("Press Ctrl+C to stop.\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


def _build_app(project_root: Path) -> Any:
    """Create the FastAPI application with all viewer routes."""
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI(title="Archie Viewer", version="2.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store project root on app state for route handlers
    app.state.project_root = project_root

    # -- Helpers ---------------------------------------------------------------

    def _load_blueprint_json(root: Path) -> dict | None:
        bp_path = root / ".archie" / "blueprint.json"
        if not bp_path.exists():
            return None
        try:
            return json.loads(bp_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _repo_id_from_blueprint(bp: dict) -> str:
        meta = bp.get("meta", {})
        return meta.get("repository_id", "") or meta.get("repository", "local")

    def _repo_name_from_blueprint(bp: dict) -> str:
        meta = bp.get("meta", {})
        return meta.get("repository", "") or "local"

    def _analyzed_at_from_blueprint(bp: dict) -> str | None:
        meta = bp.get("meta", {})
        return meta.get("analyzed_at")

    # -- In-memory active repo state -------------------------------------------
    _active_repo_id: dict[str, str | None] = {"value": None}

    # ── Auth ──────────────────────────────────────────────────────────────────

    @app.get("/api/v1/auth/config")
    async def auth_config():
        return {"server_token_configured": True}

    # ── Health ────────────────────────────────────────────────────────────────

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/system/path")
    async def system_path():
        return {"path": str(project_root)}

    # ── Workspace repositories ────────────────────────────────────────────────

    @app.get("/api/v1/workspace/repositories")
    async def list_workspace_repos():
        bp = _load_blueprint_json(project_root)
        if not bp:
            return []
        repo_id = _repo_id_from_blueprint(bp)
        return [
            {
                "repo_id": repo_id,
                "name": _repo_name_from_blueprint(bp),
                "language": (bp.get("technology", {}).get("primary_language")
                             or bp.get("technology", {}).get("languages", [None])[0]
                             if bp.get("technology", {}).get("languages") else None),
                "analyzed_at": _analyzed_at_from_blueprint(bp),
                "has_structured": True,
            }
        ]

    # ── Active repository ─────────────────────────────────────────────────────

    @app.get("/api/v1/workspace/active")
    async def get_active():
        bp = _load_blueprint_json(project_root)
        if not bp:
            return {"active_repo_id": None, "repository": None}
        repo_id = _repo_id_from_blueprint(bp)
        # Auto-set active on first access
        if _active_repo_id["value"] is None:
            _active_repo_id["value"] = repo_id
        return {
            "active_repo_id": _active_repo_id["value"],
            "repository": {
                "id": repo_id,
                "name": _repo_name_from_blueprint(bp),
                "language": None,
            },
        }

    @app.put("/api/v1/workspace/active")
    async def set_active(request: Request):
        body = await request.json()
        repo_id = body.get("repo_id")
        _active_repo_id["value"] = repo_id
        return {"active_repo_id": repo_id}

    # ── Blueprint (rendered markdown) ─────────────────────────────────────────

    @app.get("/api/v1/workspace/repositories/{repo_id}/blueprint")
    async def get_repository_blueprint(repo_id: str):
        bp = _load_blueprint_json(project_root)
        if not bp:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Blueprint not found")

        # Render blueprint to markdown via standalone renderer
        try:
            from archie.standalone.renderer import generate_claude_md
            content = generate_claude_md(bp)
        except Exception:
            content = f"```json\n{json.dumps(bp, indent=2)}\n```"

        return {
            "content": content,
            "analysis_id": "local",
            "repository_id": repo_id,
            "type": "unified",
            "format": "markdown",
        }

    # ── Agent files (CLAUDE.md, AGENTS.md, rules) ────────────────────────────

    @app.get("/api/v1/workspace/repositories/{repo_id}/agent-files")
    async def get_agent_files(repo_id: str):
        files: dict[str, str] = {}

        # Read CLAUDE.md from project root
        claude_md_path = project_root / "CLAUDE.md"
        if claude_md_path.exists():
            files["CLAUDE.md"] = claude_md_path.read_text(encoding="utf-8")

        # Read AGENTS.md from project root
        agents_md_path = project_root / "AGENTS.md"
        if agents_md_path.exists():
            files["AGENTS.md"] = agents_md_path.read_text(encoding="utf-8")

        # Read CODEBASE_MAP.md from project root
        codebase_map_path = project_root / "CODEBASE_MAP.md"
        if codebase_map_path.exists():
            files["CODEBASE_MAP.md"] = codebase_map_path.read_text(encoding="utf-8")

        # Read .claude/rules/ files
        claude_rules_dir = project_root / ".claude" / "rules"
        if claude_rules_dir.is_dir():
            for f in sorted(claude_rules_dir.rglob("*")):
                if f.is_file():
                    rel = str(f.relative_to(project_root))
                    try:
                        files[rel] = f.read_text(encoding="utf-8")
                    except Exception:
                        pass

        # Read .cursor/rules/ files
        cursor_rules_dir = project_root / ".cursor" / "rules"
        if cursor_rules_dir.is_dir():
            for f in sorted(cursor_rules_dir.rglob("*")):
                if f.is_file():
                    rel = str(f.relative_to(project_root))
                    try:
                        files[rel] = f.read_text(encoding="utf-8")
                    except Exception:
                        pass

        # Read .claude/hooks/ files
        claude_hooks_dir = project_root / ".claude" / "hooks"
        if claude_hooks_dir.is_dir():
            for f in sorted(claude_hooks_dir.rglob("*")):
                if f.is_file():
                    rel = str(f.relative_to(project_root))
                    try:
                        files[rel] = f.read_text(encoding="utf-8")
                    except Exception:
                        pass

        # Read .claude/settings.json
        claude_settings = project_root / ".claude" / "settings.json"
        if claude_settings.exists():
            try:
                files[".claude/settings.json"] = claude_settings.read_text(encoding="utf-8")
            except Exception:
                pass

        # Read per-folder CLAUDE.md files (scan common top-level dirs)
        for child in sorted(project_root.iterdir()):
            if child.is_dir() and not child.name.startswith(".") and child.name not in (
                "node_modules", "__pycache__", ".git", "venv", ".venv", "dist", "build",
            ):
                folder_claude = child / "CLAUDE.md"
                if folder_claude.exists():
                    rel = str(folder_claude.relative_to(project_root))
                    try:
                        files[rel] = folder_claude.read_text(encoding="utf-8")
                    except Exception:
                        pass

        # Build backward-compatible response
        cursor_rules_parts = [v for k, v in sorted(files.items()) if k.startswith(".cursor/rules/")]
        return {
            "claude_md": files.get("CLAUDE.md", ""),
            "cursor_rules": "\n\n".join(cursor_rules_parts),
            "agents_md": files.get("AGENTS.md", ""),
            "files": files,
        }

    # ── Source files ──────────────────────────────────────────────────────────

    @app.get("/api/v1/workspace/repositories/{repo_id}/source-files/{file_path:path}")
    async def get_source_file(repo_id: str, file_path: str):
        full_path = project_root / file_path
        if not full_path.exists() or not full_path.is_file():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="File not found")
        # Security: ensure the file is within the project root
        try:
            full_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=403, detail="Access denied")
        try:
            content = full_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = "(binary file)"
        return {"path": file_path, "content": content}

    # ── Analysis stubs ────────────────────────────────────────────────────────

    @app.get("/api/v1/analyses/{analysis_id}/analysis-data")
    async def get_analysis_data(analysis_id: str):
        return {"gathered": {}, "phases": [], "summary": {}}

    @app.get("/api/v1/analyses/{analysis_id}")
    async def get_analysis(analysis_id: str):
        bp = _load_blueprint_json(project_root)
        repo_id = _repo_id_from_blueprint(bp) if bp else "local"
        now = datetime.now(timezone.utc).isoformat()
        return {
            "id": analysis_id,
            "repository_id": repo_id,
            "status": "completed",
            "progress_percentage": 100,
            "error_message": None,
            "started_at": _analyzed_at_from_blueprint(bp) if bp else now,
            "completed_at": _analyzed_at_from_blueprint(bp) if bp else now,
            "created_at": _analyzed_at_from_blueprint(bp) if bp else now,
            "commit_sha": None,
        }

    # ── Repositories (empty — no GitHub in viewer mode) ───────────────────────

    @app.get("/api/v1/repositories/")
    async def list_repositories():
        return []

    # ── Local analysis trigger ────────────────────────────────────────────────

    @app.post("/api/v1/repositories/local/validate")
    async def validate_local(request: Request):
        """Validate a local folder path."""
        body = await request.json()
        path = body.get("path", "")
        p = Path(path)
        return {
            "valid": p.is_dir(),
            "name": p.name if p.is_dir() else None,
            "is_git_repo": (p / ".git").is_dir() if p.is_dir() else False,
            "error": None if p.is_dir() else "Directory not found",
        }

    @app.post("/api/v1/repositories/local/analyze")
    async def analyze_local(request: Request):
        """Trigger archie init on a local path."""
        body = await request.json()
        local_path = body.get("local_path", str(project_root))
        p = Path(local_path).resolve()
        if not p.is_dir():
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Directory not found")

        # Run archie init <path> --local-only in background via subprocess
        archie_bin = sys.executable
        asyncio.get_event_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                [archie_bin, "-m", "archie", "init", str(p), "--local-only"],
                capture_output=True,
                text=True,
            ),
        )
        return {"id": "local-analysis", "status": "running"}

    # ── Analysis status SSE stream ────────────────────────────────────────────

    @app.get("/api/v1/analyses/{analysis_id}/stream")
    async def analysis_stream(analysis_id: str):
        """SSE stream for analysis progress.

        For the lightweight server, just send complete events immediately.
        """
        from starlette.responses import StreamingResponse

        async def event_generator():
            data_phase = json.dumps({"phase": "local_scan", "status": "complete"})
            yield f"event: phase_complete\ndata: {data_phase}\n\n"
            data_done = json.dumps({"status": "complete"})
            yield f"event: analysis_complete\ndata: {data_done}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    # ── Delivery (local strategy) ─────────────────────────────────────────────

    @app.post("/api/v1/delivery/apply")
    async def delivery_apply(request: Request):
        """Apply delivery — render outputs to a target local path."""
        body = await request.json()
        target = Path(body.get("target_local_path", str(project_root))).resolve()

        bp = _load_blueprint_json(project_root)
        if not bp:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="No blueprint found to deliver")

        target.mkdir(parents=True, exist_ok=True)

        try:
            from archie.renderer.render import render_outputs
            rendered = render_outputs(bp, target)
            files_delivered = sorted(rendered.keys())
        except Exception as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Render failed: {exc}")

        return {
            "status": "delivered",
            "strategy": "local",
            "pr_url": None,
            "commit_sha": None,
            "branch": None,
            "files_delivered": files_delivered,
        }

    # ── Settings stubs (frontend calls these on load) ─────────────────────────

    @app.get("/api/v1/settings/ignored-dirs")
    async def ignored_dirs():
        return []

    @app.get("/api/v1/prompts/")
    async def list_prompts():
        return []

    @app.delete("/api/v1/workspace/repositories/{repo_id}")
    async def delete_repo(repo_id: str):
        return {"deleted": True}

    return app
