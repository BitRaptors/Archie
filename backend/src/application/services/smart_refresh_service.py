"""Smart Refresh Service — evaluates code changes against architecture blueprint.

When a developer makes changes, this service:
1. Loads the architecture blueprint for the repository
2. Identifies which blueprint-covered folders are affected
3. Calls an AI model to check alignment and detect staleness
4. Regenerates CLAUDE.md files for stale folders
5. Returns warnings and updated file paths
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import PurePosixPath
from typing import Any

import anthropic
from pydantic import BaseModel, Field

from domain.entities.analysis_settings import SOURCE_CODE_EXTENSIONS
from domain.entities.blueprint import StructuredBlueprint
from infrastructure.external.local_push_client import LocalPushClient

logger = logging.getLogger(__name__)

# ── Response Models ──────────────────────────────────────────────────────────


class ArchitectureWarning(BaseModel):
    """A warning about an architectural violation or concern."""
    severity: str = "warning"  # "error" | "warning" | "info"
    folder: str = ""
    message: str = ""
    rule_violated: str = ""
    suggestion: str = ""


class SmartRefreshResult(BaseModel):
    """Result of a smart refresh operation."""
    status: str = "no_refresh_needed"  # "refreshed" | "no_refresh_needed" | "warnings"
    updated_files: list[str] = Field(default_factory=list)
    warnings: list[ArchitectureWarning] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# ── Internal Models ──────────────────────────────────────────────────────────


class _FolderContext(BaseModel):
    """Internal: context packet for a single affected folder."""
    path: str
    component_name: str = ""
    responsibility: str = ""
    depends_on: list[str] = Field(default_factory=list)
    file_placement_rules: list[dict[str, str]] = Field(default_factory=list)
    naming_conventions: list[dict[str, str]] = Field(default_factory=list)
    changed_files: list[dict[str, str]] = Field(default_factory=list)  # [{name, content}]
    existing_claude_md: str = ""


# ── Constants ────────────────────────────────────────────────────────────────

_MAX_FILE_SNIPPET = 1500
_MAX_CLAUDE_MD_SNIPPET = 500
_MAX_FOLDERS_PER_BATCH = 8
_AI_TIMEOUT = 20.0
_AI_MODEL = "claude-haiku-4-5-20251001"


class SmartRefreshService:
    """Evaluates code changes against the architecture blueprint.

    Detects misaligned changes, generates warnings, and regenerates
    stale CLAUDE.md files when the underlying code shifts.
    """

    def __init__(self, storage, settings, intent_layer_service=None):
        self._storage = storage
        self._settings = settings
        self._intent_layer_service = intent_layer_service
        self._ai_client: anthropic.AsyncAnthropic | None = None

    # ── Public API ───────────────────────────────────────────────────────

    async def refresh(
        self,
        repo_id: str,
        changed_files: list[str],
        target_local_path: str,
    ) -> SmartRefreshResult:
        """Run the smart refresh pipeline for a set of changed files.

        Args:
            repo_id: Repository identifier (used to locate blueprint in storage).
            changed_files: List of changed file paths (relative to repo root).
            target_local_path: Absolute path to the local checkout.

        Returns:
            SmartRefreshResult with status, updated files, and warnings.
        """
        # 1. Load blueprint
        blueprint = await self._load_blueprint(repo_id)
        if blueprint is None:
            logger.info("No blueprint found for repo %s — skipping refresh", repo_id)
            return SmartRefreshResult(status="no_refresh_needed")

        # 2. Filter to source code files
        source_files = [
            f for f in changed_files
            if _is_source_file(f)
        ]
        if not source_files:
            logger.info("No source code files changed — skipping refresh")
            return SmartRefreshResult(status="no_refresh_needed")

        # 3. Compute affected folders with blueprint coverage
        covered_folders = self._get_covered_folders(blueprint)
        affected_folders = self._compute_affected_folders(source_files, covered_folders)

        # If no matches, try stripping the first path component from changed
        # files.  Many repos (especially iOS) have a layout like:
        #   RepoRoot/ProjectName/Sources/...
        # Git returns paths relative to the repo root, but blueprint locations
        # are often relative to the project subfolder, causing a prefix
        # mismatch.  Stripping the first component aligns them.
        if not affected_folders and source_files:
            first_components = {
                PurePosixPath(f).parts[0]
                for f in source_files
                if len(PurePosixPath(f).parts) > 1
            }
            if len(first_components) == 1:
                prefix = first_components.pop()
                stripped = [
                    str(PurePosixPath(*PurePosixPath(f).parts[1:]))
                    for f in source_files
                    if len(PurePosixPath(f).parts) > 1
                ]
                affected_folders = self._compute_affected_folders(stripped, covered_folders)
                if affected_folders:
                    logger.info(
                        "Matched after stripping repo root prefix '%s' — %d folder(s)",
                        prefix, len(affected_folders),
                    )
                    source_files = stripped

        if not affected_folders:
            logger.info("No blueprint-covered folders affected — skipping refresh")
            return SmartRefreshResult(status="no_refresh_needed")

        # 4. Build folder context packets
        folder_contexts = await self._build_folder_contexts(
            repo_id=repo_id,
            blueprint=blueprint,
            affected_folders=affected_folders,
            covered_folders=covered_folders,
            source_files=source_files,
            target_local_path=target_local_path,
        )
        if not folder_contexts:
            return SmartRefreshResult(status="no_refresh_needed")

        # 5. AI evaluation (batched)
        ai_results = await self._evaluate_with_ai(blueprint, folder_contexts)

        # 6. Collect warnings
        warnings: list[ArchitectureWarning] = []
        stale_folders: list[str] = []
        suggestions: list[str] = []

        for folder_result in ai_results:
            folder_path = folder_result.get("path", "")

            # Collect warnings
            for w in folder_result.get("warnings", []):
                warnings.append(ArchitectureWarning(
                    severity=w.get("severity", "warning"),
                    folder=folder_path,
                    message=w.get("message", ""),
                    rule_violated=w.get("rule_violated", ""),
                    suggestion=w.get("suggestion", ""),
                ))

            # Track stale folders
            if folder_result.get("claude_md_stale", False):
                stale_folders.append(folder_path)

            # Collect suggestions
            suggestion = folder_result.get("suggestion", "")
            if suggestion:
                suggestions.append(f"{folder_path}: {suggestion}")

        # 7. Regenerate CLAUDE.md for stale folders
        updated_files: list[str] = []
        if stale_folders:
            updated_files = await self._regenerate_claude_md(
                repo_id=repo_id,
                blueprint=blueprint,
                stale_folders=stale_folders,
                target_local_path=target_local_path,
            )

        # 8. Determine status
        if warnings:
            status = "warnings"
        elif updated_files:
            status = "refreshed"
        else:
            status = "no_refresh_needed"

        return SmartRefreshResult(
            status=status,
            updated_files=updated_files,
            warnings=warnings,
            suggestions=suggestions,
        )

    # ── Blueprint Loading ────────────────────────────────────────────────

    async def _load_blueprint(self, repo_id: str) -> StructuredBlueprint | None:
        """Load the structured blueprint from storage."""
        json_path = f"blueprints/{repo_id}/blueprint.json"
        if not await self._storage.exists(json_path):
            return None
        content = await self._storage.read(json_path)
        text = content.decode("utf-8") if isinstance(content, bytes) else content
        data = json.loads(text)
        return StructuredBlueprint.model_validate(data)

    # ── Folder Coverage ──────────────────────────────────────────────────

    @staticmethod
    def _get_covered_folders(blueprint: StructuredBlueprint) -> dict[str, dict[str, Any]]:
        """Build a mapping of folder paths to their blueprint component info.

        Returns dict keyed by folder path (normalized, no trailing slash),
        with component metadata as values.
        """
        covered: dict[str, dict[str, Any]] = {}
        for comp in blueprint.components.components:
            location = comp.location.strip().rstrip("/")
            if not location:
                continue
            covered[location] = {
                "name": comp.name,
                "responsibility": comp.responsibility,
                "depends_on": comp.depends_on,
                "exposes_to": comp.exposes_to,
            }
        return covered

    @staticmethod
    def _compute_affected_folders(
        source_files: list[str],
        covered_folders: dict[str, dict[str, Any]],
    ) -> set[str]:
        """Deduplicate changed files into parent dirs, walk ancestors,
        and filter to folders with blueprint coverage.
        """
        # Collect all candidate folder paths (file parents + ancestors)
        candidate_dirs: set[str] = set()
        for filepath in source_files:
            parent = str(PurePosixPath(filepath).parent)
            if parent == ".":
                parent = ""
            # Walk from the direct parent up to root
            current = parent
            while current:
                candidate_dirs.add(current)
                next_parent = str(PurePosixPath(current).parent)
                if next_parent == current or next_parent == ".":
                    break
                current = next_parent

        # Filter to covered folders only
        return candidate_dirs & covered_folders.keys()

    # ── Context Building ─────────────────────────────────────────────────

    async def _build_folder_contexts(
        self,
        repo_id: str,
        blueprint: StructuredBlueprint,
        affected_folders: set[str],
        covered_folders: dict[str, dict[str, Any]],
        source_files: list[str],
        target_local_path: str,
    ) -> list[_FolderContext]:
        """Build context packets for each affected folder."""
        covered = covered_folders

        # Map files to their containing covered folder
        folder_files: dict[str, list[str]] = {f: [] for f in affected_folders}
        for filepath in source_files:
            parent = str(PurePosixPath(filepath).parent)
            if parent == ".":
                parent = ""
            # Check the direct parent and ancestors
            current = parent
            while current:
                if current in affected_folders:
                    folder_files[current].append(filepath)
                    break
                next_parent = str(PurePosixPath(current).parent)
                if next_parent == current or next_parent == ".":
                    break
                current = next_parent

        # Build architecture rules lookup
        placement_rules = [
            {
                "component_type": r.component_type,
                "naming_pattern": r.naming_pattern,
                "location": r.location,
                "description": r.description,
            }
            for r in blueprint.architecture_rules.file_placement_rules
        ]
        naming_conventions = [
            {"scope": n.scope, "pattern": n.pattern, "description": n.description}
            for n in blueprint.architecture_rules.naming_conventions
        ]

        contexts: list[_FolderContext] = []
        for folder_path in sorted(affected_folders):
            comp_info = covered[folder_path]
            files_in_folder = folder_files.get(folder_path, [])

            # Read changed file contents (truncated)
            changed_files_with_content: list[dict[str, str]] = []
            for fpath in files_in_folder:
                content = _read_local_file(target_local_path, fpath)
                changed_files_with_content.append({
                    "name": fpath,
                    "content": content[:_MAX_FILE_SNIPPET] if content else "(file not found)",
                })

            # Read existing CLAUDE.md from storage
            claude_md_path = f"blueprints/{repo_id}/intent_layer/{folder_path}/CLAUDE.md"
            existing_claude_md = ""
            if await self._storage.exists(claude_md_path):
                raw = await self._storage.read(claude_md_path)
                text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                existing_claude_md = text[:_MAX_CLAUDE_MD_SNIPPET]

            # Filter placement rules relevant to this folder
            folder_placement_rules = [
                r for r in placement_rules
                if r.get("location", "").startswith(folder_path)
                or folder_path.startswith(r.get("location", "///"))
            ]

            contexts.append(_FolderContext(
                path=folder_path,
                component_name=comp_info["name"],
                responsibility=comp_info["responsibility"],
                depends_on=comp_info["depends_on"],
                file_placement_rules=folder_placement_rules or placement_rules,
                naming_conventions=naming_conventions,
                changed_files=changed_files_with_content,
                existing_claude_md=existing_claude_md,
            ))

        return contexts

    # ── AI Evaluation ────────────────────────────────────────────────────

    async def _evaluate_with_ai(
        self,
        blueprint: StructuredBlueprint,
        folder_contexts: list[_FolderContext],
    ) -> list[dict[str, Any]]:
        """Call the AI model to evaluate alignment for affected folders.

        Batches folders into groups of _MAX_FOLDERS_PER_BATCH.
        Returns list of per-folder result dicts.
        """
        all_results: list[dict[str, Any]] = []

        # Batch folders
        for i in range(0, len(folder_contexts), _MAX_FOLDERS_PER_BATCH):
            batch = folder_contexts[i:i + _MAX_FOLDERS_PER_BATCH]
            prompt = self._build_prompt(blueprint, batch)

            try:
                result = await self._call_ai(prompt)
                folders_data = result.get("folders", [])
                all_results.extend(folders_data)
            except Exception:
                logger.exception("AI evaluation failed for batch %d", i // _MAX_FOLDERS_PER_BATCH)
                # On failure, flag as incomplete so caller knows evaluation was skipped
                for ctx in batch:
                    all_results.append({
                        "path": ctx.path,
                        "aligned": True,
                        "warnings": [{
                            "severity": "info",
                            "message": "AI evaluation unavailable — alignment not verified",
                            "rule_violated": "",
                            "suggestion": "Re-run smart refresh when AI service is available",
                        }],
                        "claude_md_stale": True,
                        "suggestion": "",
                    })

        return all_results

    @staticmethod
    def _build_prompt(
        blueprint: StructuredBlueprint,
        folder_contexts: list[_FolderContext],
    ) -> str:
        """Build the evaluation prompt for a batch of folders."""
        style = blueprint.meta.architecture_style or "unknown"

        # Compact architecture rules
        rules_section = "## Blueprint Rules\n"
        rules_section += f"Architecture style: {style}\n"
        rules_section += f"Structure: {blueprint.components.structure_type}\n"

        if blueprint.architecture_rules.file_placement_rules:
            rules_section += "\nFile placement rules:\n"
            for r in blueprint.architecture_rules.file_placement_rules[:10]:
                rules_section += f"- {r.component_type}: {r.location} ({r.naming_pattern})\n"

        if blueprint.architecture_rules.naming_conventions:
            rules_section += "\nNaming conventions:\n"
            for n in blueprint.architecture_rules.naming_conventions[:8]:
                rules_section += f"- {n.scope}: {n.pattern}\n"

        if blueprint.quick_reference.where_to_put_code:
            rules_section += "\nWhere to put code:\n"
            for code_type, location in list(blueprint.quick_reference.where_to_put_code.items())[:10]:
                rules_section += f"- {code_type} -> {location}\n"

        # Affected folders section
        folders_section = "## Affected Folders\n"
        for ctx in folder_contexts:
            folders_section += f"\n### {ctx.path}\n"
            folders_section += f"Component: {ctx.component_name}\n"
            folders_section += f"Responsibility: {ctx.responsibility}\n"
            if ctx.depends_on:
                folders_section += f"Depends on: {', '.join(ctx.depends_on)}\n"

            if ctx.changed_files:
                folders_section += "Changed files:\n"
                for cf in ctx.changed_files:
                    snippet = cf["content"]
                    folders_section += f"- `{cf['name']}`:\n```\n{snippet}\n```\n"

            if ctx.existing_claude_md:
                folders_section += f"Current CLAUDE.md (first {_MAX_CLAUDE_MD_SNIPPET} chars):\n"
                folders_section += f"```\n{ctx.existing_claude_md}\n```\n"

        prompt = f"""You are an architecture reviewer for a {style} codebase.

{rules_section}

{folders_section}

## Task
For each affected folder, evaluate:
1. Are the changes aligned with the component's responsibility and the architecture rules?
2. Are there any violations of file placement rules, naming conventions, or dependency rules?
3. Is the current CLAUDE.md stale given these changes (does it need regeneration)?

## Respond with JSON only (no markdown fences):
{{"folders": [{{"path": "folder/path", "aligned": true, "warnings": [{{"severity": "warning", "message": "description", "rule_violated": "rule name", "suggestion": "how to fix"}}], "claude_md_stale": false, "suggestion": "optional improvement suggestion"}}]}}

Rules:
- severity must be "error", "warning", or "info"
- Only flag claude_md_stale=true if the changes meaningfully alter the folder's purpose, add new patterns, or change key files
- Keep warnings actionable and specific
- If everything looks good, return aligned=true with empty warnings"""

        return prompt

    def _get_ai_client(self) -> anthropic.AsyncAnthropic:
        """Lazy-init and return the cached Anthropic client."""
        if self._ai_client is None:
            self._ai_client = anthropic.AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        return self._ai_client

    async def _call_ai(self, prompt: str) -> dict[str, Any]:
        """Make a single AI call and parse the JSON response."""
        client = self._get_ai_client()

        response = await client.messages.create(
            model=_AI_MODEL,
            max_tokens=4096,
            timeout=_AI_TIMEOUT,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text

        # Parse JSON — strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            # Remove opening fence (```json or ```)
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        return json.loads(text)

    # ── CLAUDE.md Regeneration ───────────────────────────────────────────

    async def _regenerate_claude_md(
        self,
        repo_id: str,
        blueprint: StructuredBlueprint,
        stale_folders: list[str],
        target_local_path: str,
    ) -> list[str]:
        """Regenerate CLAUDE.md for stale folders.

        Uses IntentLayerService if available, otherwise falls back to
        deterministic IntentLayerRenderer.
        """
        updated_files: list[str] = []

        # Try the full IntentLayerService pipeline first (handles everything)
        if self._intent_layer_service is not None:
            try:
                output = await self._intent_layer_service.preview(
                    source_repo_id=repo_id,
                    local_path=target_local_path,
                    incremental=True,
                )
                # Filter to only the stale folders and write them
                files_to_write: dict[str, str] = {}
                for file_path, content in output.claude_md_files.items():
                    # Check if this file belongs to a stale folder
                    for stale_folder in stale_folders:
                        if file_path.startswith(stale_folder) and file_path.endswith("CLAUDE.md"):
                            files_to_write[file_path] = content
                            break

                if files_to_write:
                    # Write to local filesystem
                    try:
                        push_client = LocalPushClient(base_dir=target_local_path)
                        written = push_client.write_files(files_to_write)
                        updated_files.extend(written)
                    except Exception:
                        logger.exception("Failed to write files via LocalPushClient")

                    # Also persist to storage
                    for file_path, content in files_to_write.items():
                        storage_path = f"blueprints/{repo_id}/intent_layer/{file_path}"
                        try:
                            await self._storage.save(
                                storage_path,
                                content.encode("utf-8") if isinstance(content, str) else content,
                            )
                        except Exception:
                            logger.exception("Failed to persist %s to storage", storage_path)

                return updated_files
            except Exception:
                logger.warning(
                    "IntentLayerService.preview() failed — falling back to deterministic renderer",
                    exc_info=True,
                )

        # Fallback: deterministic rendering with IntentLayerRenderer
        updated_files = await self._regenerate_deterministic(
            repo_id=repo_id,
            blueprint=blueprint,
            stale_folders=stale_folders,
            target_local_path=target_local_path,
        )
        return updated_files

    async def _regenerate_deterministic(
        self,
        repo_id: str,
        blueprint: StructuredBlueprint,
        stale_folders: list[str],
        target_local_path: str,
    ) -> list[str]:
        """Deterministic fallback: re-render CLAUDE.md using IntentLayerRenderer."""
        from application.services.intent_layer_renderer import IntentLayerRenderer
        from domain.entities.intent_layer import FolderNode, FolderBlueprint

        renderer = IntentLayerRenderer()
        covered = self._get_covered_folders(blueprint)
        repo_name = blueprint.meta.repository or repo_id
        files_to_write: dict[str, str] = {}

        for folder_path in stale_folders:
            comp_info = covered.get(folder_path)
            if not comp_info:
                continue

            # Build minimal FolderNode
            folder_name = PurePosixPath(folder_path).name or repo_name
            parent_path = str(PurePosixPath(folder_path).parent)
            if parent_path == ".":
                parent_path = ""

            folder_node = FolderNode(
                path=folder_path,
                name=folder_name,
                depth=len(PurePosixPath(folder_path).parts),
                parent_path=parent_path,
            )

            # Build FolderBlueprint from component data
            folder_blueprint = FolderBlueprint(
                path=folder_path,
                component_name=comp_info["name"],
                component_responsibility=comp_info["responsibility"],
                depends_on=comp_info["depends_on"],
                exposes_to=comp_info.get("exposes_to", []),
                file_placement_rules=[
                    {
                        "component_type": r.component_type,
                        "naming_pattern": r.naming_pattern,
                        "description": r.description,
                    }
                    for r in blueprint.architecture_rules.file_placement_rules
                    if r.location.startswith(folder_path)
                    or folder_path.startswith(r.location)
                ],
                naming_conventions=[
                    {"scope": n.scope, "pattern": n.pattern}
                    for n in blueprint.architecture_rules.naming_conventions
                ],
            )

            content = renderer.render_from_blueprint(folder_node, folder_blueprint, repo_name)
            claude_md_rel = f"{folder_path}/CLAUDE.md"
            files_to_write[claude_md_rel] = content

        if not files_to_write:
            return []

        updated: list[str] = []

        # Write to local filesystem
        try:
            push_client = LocalPushClient(base_dir=target_local_path)
            written = push_client.write_files(files_to_write)
            updated.extend(written)
        except Exception:
            logger.exception("Failed to write regenerated CLAUDE.md files locally")

        # Persist to storage
        for file_path, content in files_to_write.items():
            storage_path = f"blueprints/{repo_id}/intent_layer/{file_path}"
            try:
                await self._storage.save(
                    storage_path,
                    content.encode("utf-8") if isinstance(content, str) else content,
                )
            except Exception:
                logger.exception("Failed to persist %s to storage", storage_path)

        return updated


# ── Helpers ──────────────────────────────────────────────────────────────────


def _is_source_file(filepath: str) -> bool:
    """Check if a file is a source code file based on its extension."""
    ext = PurePosixPath(filepath).suffix.lower()
    return ext in SOURCE_CODE_EXTENSIONS


def _read_local_file(base_dir: str, relative_path: str) -> str | None:
    """Read a file from the local checkout, returning None if missing or outside base."""
    base = os.path.realpath(base_dir)
    full_path = os.path.realpath(os.path.join(base, relative_path))
    if not full_path.startswith(base + os.sep) and full_path != base:
        return None
    try:
        with open(full_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, IOError):
        return None
