"""Smart Refresh Service — evaluates code changes against Archie blueprint.

When a developer makes changes, this service:
1. Loads the Archie blueprint for the repository
2. Identifies which blueprint-covered folders are affected
3. Calls an AI model to check alignment and detect staleness
4. Regenerates CLAUDE.md files for stale folders
5. Returns warnings and updated file paths
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path, PurePosixPath
from typing import Any

import anthropic
from pydantic import BaseModel, Field

from application.services.blueprint_folder_mapper import BlueprintFolderMapper
from application.services.hybrid_enrichment_engine import HybridEnrichmentEngine
from application.services.intent_layer_renderer import IntentLayerRenderer
from application.services.intent_layer_service import FolderHierarchyBuilder
from domain.entities.analysis_settings import SOURCE_CODE_EXTENSIONS
from domain.entities.blueprint import StructuredBlueprint
from domain.entities.intent_layer import FolderEnrichment, IntentLayerConfig
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
    """Evaluates code changes against the Archie blueprint.

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

        # Build a set of the actual affected folder paths so we can
        # normalise whatever the AI returns (it sometimes returns file
        # paths instead of folder paths).
        _affected_set = affected_folders  # set[str]

        for folder_result in ai_results:
            raw_path = folder_result.get("path", "")
            # Normalise: if the AI returned a file path, map it back to
            # the containing affected folder.
            folder_path = _resolve_to_affected_folder(raw_path, _affected_set)

            # Collect warnings
            for w in folder_result.get("warnings", []):
                warnings.append(ArchitectureWarning(
                    severity=w.get("severity", "warning"),
                    folder=folder_path,
                    message=w.get("message", ""),
                    rule_violated=w.get("rule_violated", ""),
                    suggestion=w.get("suggestion", ""),
                ))

            # Track stale folders — also treat folders with error/warning
            # findings as stale, since the CLAUDE.md should reflect the
            # current state of the code.
            folder_warnings = folder_result.get("warnings", [])
            has_actionable_warnings = any(
                w.get("severity") in ("error", "warning")
                for w in folder_warnings
            )
            if folder_result.get("claude_md_stale", False) or has_actionable_warnings:
                if folder_path and folder_path not in stale_folders:
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
                changed_files=source_files,
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
    def _parse_location(raw: str) -> list[str]:
        """Parse a component location string into clean folder paths.

        Blueprint locations can contain:
        - Comma-separated paths: "Foo/A/, Foo/B/"
        - Semicolon-separated paths: "Foo/ (AppDelegate); Foo/DI/"
        - Glob suffixes: "Foo/Pages/*"
        - Inline descriptions in parentheses: "Foo/ (some note)"
        """
        import re
        # Remove parenthetical descriptions BEFORE splitting, since they
        # may contain commas (e.g. "Foo/ (AppDelegate, SceneDelegate)")
        cleaned = re.sub(r"\s*\([^)]*\)", "", raw)
        # Split on comma or semicolon
        parts = re.split(r"[;,]", cleaned)
        paths: list[str] = []
        for part in parts:
            p = part.strip()
            if not p:
                continue
            # Remove glob wildcards
            p = p.rstrip("*").rstrip("/").strip()
            if p:
                paths.append(p)
        return paths

    @staticmethod
    def _get_covered_folders(blueprint: StructuredBlueprint) -> dict[str, dict[str, Any]]:
        """Build a mapping of folder paths to their blueprint component info.

        Returns dict keyed by folder path (normalized, no trailing slash),
        with component metadata as values.
        """
        covered: dict[str, dict[str, Any]] = {}
        for comp in blueprint.components.components:
            comp_info = {
                "name": comp.name,
                "responsibility": comp.responsibility,
                "depends_on": comp.depends_on,
                "exposes_to": comp.exposes_to,
            }
            for folder in SmartRefreshService._parse_location(comp.location):
                covered[folder] = comp_info
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
- Flag claude_md_stale=true if: new files are added, files are removed, the folder's purpose shifts, new patterns appear, key files change, or the existing CLAUDE.md is empty/missing
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
        changed_files: list[str] | None = None,
    ) -> list[str]:
        """Regenerate CLAUDE.md for stale folders only.

        Targeted pipeline: builds hierarchy, maps blueprint, AI-enriches,
        and renders only the stale folders (2-3 Haiku calls instead of 54).
        Falls back to deterministic rendering on failure.
        """
        updated_files: list[str] = []
        repo_name = blueprint.meta.repository or repo_id

        try:
            # 1. Build folder hierarchy (fast ~100ms filesystem walk), filter to stale only
            builder = FolderHierarchyBuilder()
            all_nodes = builder.build_from_path(Path(target_local_path))

            # stale_folders uses blueprint paths (e.g. "Sources/Features").
            # all_nodes uses filesystem-relative paths (e.g. "BabyWeather/Sources/Features").
            # Build a mapping: blueprint_path -> fs_path for lookups.
            bp_to_fs: dict[str, str] = {}  # blueprint path -> filesystem path
            for sf in stale_folders:
                if sf in all_nodes:
                    bp_to_fs[sf] = sf  # direct match

            # If no direct match, try adding a single-level prefix.
            # The refresh() pipeline may strip a repo-root prefix from
            # changed files (e.g. "BabyWeather/Sources" → "Sources") to
            # match blueprint paths.  Hierarchy keys still have the full
            # relative path, so we need to re-add the prefix here.
            if not bp_to_fs and stale_folders:
                top_dirs = {
                    p.split("/", 1)[0]
                    for p in all_nodes
                    if "/" in p
                }
                for prefix in top_dirs:
                    matched = {}
                    for sf in stale_folders:
                        fs_path = f"{prefix}/{sf}"
                        if fs_path in all_nodes:
                            matched[sf] = fs_path
                    if matched:
                        logger.info(
                            "Matched stale folders after adding prefix '%s'", prefix,
                        )
                        bp_to_fs = matched
                        break

            if not bp_to_fs:
                logger.info(
                    "No stale folders found in hierarchy (stale=%s, hierarchy_sample=%s) "
                    "— falling back to deterministic",
                    stale_folders,
                    list(all_nodes.keys())[:10],
                )
                return await self._regenerate_deterministic(
                    repo_id=repo_id,
                    blueprint=blueprint,
                    stale_folders=stale_folders,
                    target_local_path=target_local_path,
                )

            # Identify which folders DIRECTLY contain changed files (fs-relative).
            # Only these need AI re-enrichment; ancestors just need navigation fixed.
            changed_dirs: set[str] = set()
            if changed_files:
                for fpath in changed_files:
                    parent = str(PurePosixPath(fpath).parent)
                    if parent == ".":
                        parent = ""
                    if parent:
                        changed_dirs.add(parent)

            # Expand stale roots to include child sub-folders that directly
            # contain changed files.
            if changed_dirs:
                for sf, fs in list(bp_to_fs.items()):
                    for node_path in all_nodes:
                        if node_path.startswith(fs + "/") and node_path != fs:
                            if node_path not in changed_dirs:
                                continue
                            child_suffix = node_path[len(fs) + 1:]
                            child_bp = f"{sf}/{child_suffix}" if sf else child_suffix
                            if child_bp not in bp_to_fs:
                                bp_to_fs[child_bp] = node_path

            # Build stale_nodes keyed by blueprint path
            stale_nodes = {bp: all_nodes[fs] for bp, fs in bp_to_fs.items()}

            logger.info(
                "Targeted refresh: %d folders (from %d stale roots)",
                len(stale_nodes), len(stale_folders),
            )

            # 2. Map blueprint onto stale folders.  Also include their
            #    direct children from the hierarchy so that the mapper can
            #    build complete children_summaries / navigation.
            all_mapper_paths: set[str] = set(stale_nodes.keys())
            for bp_path in list(stale_nodes.keys()):
                fs_path = bp_to_fs[bp_path]
                node = all_nodes.get(fs_path)
                if node:
                    for child_fs in node.children:
                        child_suffix = child_fs[len(fs_path) + 1:] if fs_path else child_fs
                        child_bp = f"{bp_path}/{child_suffix}" if bp_path else child_suffix
                        all_mapper_paths.add(child_bp)

            mapper = BlueprintFolderMapper()
            folder_blueprints = mapper.map_all(blueprint, list(all_mapper_paths))

            # 3. File reader for enrichment engine
            def file_reader(rel_path: str) -> str | None:
                return _read_local_file(target_local_path, rel_path)

            # 4. Load previous CLAUDE.md content from storage for context.
            #    This lets the AI refine rather than regenerate from scratch.
            previous_content: dict[str, str] = {}
            for bp_path in stale_nodes:
                storage_path = f"blueprints/{repo_id}/intent_layer/{bp_to_fs[bp_path]}/CLAUDE.md"
                try:
                    if await self._storage.exists(storage_path):
                        raw = await self._storage.read(storage_path)
                        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
                        previous_content[bp_path] = text
                except Exception:
                    pass  # Missing previous content is fine

            # 5. AI enrichment — only for folders that directly contain
            #    changed files (typically 2-3 Haiku calls, not 54).
            #    The enrichment prompt preserves existing wording and only
            #    adds/removes/changes lines reflecting actual code changes.
            enrich_nodes = {
                bp: node for bp, node in stale_nodes.items()
                if bp_to_fs[bp] in changed_dirs
            }
            # Also include stale roots that directly contain changed files
            for sf in stale_folders:
                if sf in stale_nodes and sf not in enrich_nodes:
                    if bp_to_fs.get(sf, "") in changed_dirs:
                        enrich_nodes[sf] = stale_nodes[sf]
            if not enrich_nodes:
                logger.info("No folders with direct file changes to enrich — skipping")
                return updated_files

            config = IntentLayerConfig(enable_ai_enrichment=True, max_concurrent=3)
            engine = HybridEnrichmentEngine(self._settings, config)
            enrichments = await engine.enrich_all(
                enrich_nodes, folder_blueprints, file_reader, previous_content,
            )

            # 6. Render only the folders we AI-enriched
            renderer = IntentLayerRenderer()
            files_to_write: dict[str, str] = {}
            for bp_path in enrich_nodes:
                fb = folder_blueprints.get(bp_path)
                if not fb:
                    continue
                enrichment = enrichments.get(
                    bp_path, FolderEnrichment(path=bp_path),
                )
                md_path = f"{bp_to_fs[bp_path]}/CLAUDE.md" if bp_path else "CLAUDE.md"
                files_to_write[md_path] = renderer.render_hybrid(
                    enrich_nodes[bp_path], fb, enrichment, repo_name,
                )

            # 6. Write locally + persist to storage
            if files_to_write:
                try:
                    push_client = LocalPushClient(base_dir=target_local_path)
                    written = push_client.write_files(files_to_write)
                    updated_files.extend(written)
                except Exception:
                    logger.exception("Failed to write files via LocalPushClient")

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
                "Targeted enrichment failed — falling back to deterministic renderer",
                exc_info=True,
            )
            return await self._regenerate_deterministic(
                repo_id=repo_id,
                blueprint=blueprint,
                stale_folders=stale_folders,
                target_local_path=target_local_path,
            )

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


def _resolve_to_affected_folder(raw_path: str, affected_folders: set[str]) -> str:
    """Map a path returned by the AI back to one of the affected folders.

    The AI sometimes returns file paths (e.g. ``Foo/Bar/file.swift``)
    instead of the folder path (``Foo/Bar``).  Walk up from *raw_path*
    until we find a match in *affected_folders*.
    """
    if raw_path in affected_folders:
        return raw_path
    current = str(PurePosixPath(raw_path).parent)
    while current and current != ".":
        if current in affected_folders:
            return current
        next_parent = str(PurePosixPath(current).parent)
        if next_parent == current or next_parent == ".":
            break
        current = next_parent
    # No match — return as-is (best effort)
    return raw_path


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
