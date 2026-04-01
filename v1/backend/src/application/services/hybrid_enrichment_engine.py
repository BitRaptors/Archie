"""Hybrid enrichment engine — per-folder AI calls for compound learning.

Processes folders bottom-up (deepest first), propagates child summaries upward.
Each folder gets a dedicated Haiku call to study its actual code and produce
actionable developer notes.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Callable, Optional

import tiktoken

from config.settings import Settings
from domain.entities.intent_layer import (
    FolderNode,
    FolderBlueprint,
    FolderEnrichment,
    KeyFileGuide,
    CommonTask,
    CodeExample,
    IntentLayerConfig,
)

logger = logging.getLogger(__name__)


class EnrichmentError(Exception):
    """Raised when all non-passthrough AI enrichment calls fail."""
    pass

# Token budgets (tiktoken cl100k_base)
_MAX_FILES_PER_FOLDER = 5
_MAX_TOKENS_PER_FILE = 1_500
_MAX_TOKENS_PER_FOLDER = 5_000

# Cached encoder — use _release_encoder() to free ~10 MB after enrichment
_encoder: tiktoken.Encoding | None = None


def _get_encoder() -> tiktoken.Encoding:
    global _encoder
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def _release_encoder() -> None:
    """Release the cached tiktoken encoder to free ~10 MB."""
    global _encoder
    _encoder = None


def _count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding."""
    return len(_get_encoder().encode(text))


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text at a token boundary."""
    enc = _get_encoder()
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens])


# File priority tiers for enrichment budget allocation
_PRIORITY_TIERS: dict[str, int] = {
    "__init__.py": 4, "app.py": 4, "main.py": 4, "index.ts": 4,
    "index.tsx": 4, "index.js": 4, "mod.rs": 4, "lib.rs": 4,
    "config.py": 3, "settings.py": 3, "routes.py": 3, "models.py": 3,
    "schema.py": 3, "urls.py": 3, "router.py": 3,
    "interfaces.py": 2, "base.py": 2, "types.py": 2, "protocols.py": 2,
    "types.ts": 2, "constants.py": 2,
}


def _prioritize_files(filenames: list[str]) -> list[str]:
    """Sort filenames by priority tier (highest first), then alphabetically."""
    def sort_key(f: str) -> tuple[int, str]:
        tier = _PRIORITY_TIERS.get(f, 0)
        return (-tier, f)
    return sorted(filenames, key=sort_key)


def _extract_json(text: str) -> str:
    """Extract JSON from AI response, handling markdown code blocks."""
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    start = text.find('{')
    if start >= 0:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
    return text.strip()


class HybridEnrichmentEngine:
    """Per-folder AI enrichment with bottom-up child summary propagation."""

    def __init__(self, settings: Settings, config: IntentLayerConfig, progress_callback=None):
        self._settings = settings
        self._config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrent or 10)
        self.total_calls = 0
        self._progress_callback = progress_callback  # async fn(message: str) -> None
        self._first_error: Exception | None = None

    async def enrich_all(
        self,
        folders: dict[str, FolderNode],
        folder_blueprints: dict[str, FolderBlueprint],
        file_reader: Callable[[str], str | None],
        previous_content: Optional[dict[str, str]] = None,
    ) -> dict[str, FolderEnrichment]:
        """Enrich all folders bottom-up, propagating child summaries upward.

        Groups folders by depth (deepest first), processes each depth level
        in parallel, then builds child summaries for the next (shallower) level.

        Args:
            previous_content: Optional mapping of folder_path -> raw CLAUDE.md content
                from a previous generation. Fed to AI as context for refinement.
        """
        previous_content = previous_content or {}
        # Group by depth (deepest first)
        depth_groups: dict[int, list[FolderNode]] = {}
        for node in folders.values():
            depth_groups.setdefault(node.depth, []).append(node)

        enrichments: dict[str, FolderEnrichment] = {}
        prompt_template = self._load_prompt_template()
        client = self._make_client()

        total_folders = len(folders)
        max_depth = max(depth_groups.keys()) if depth_groups else 0
        min_depth = min(depth_groups.keys()) if depth_groups else 0
        model = self._config.enrichment_model or self._settings.default_ai_model
        if previous_content:
            logger.info(f"Previous CLAUDE.md found for {len(previous_content)} folders")
        logger.info(
            f"Hybrid enrichment: {total_folders} folders, "
            f"depth {min_depth}-{max_depth}, model={model}, "
            f"max_concurrent={self._config.max_concurrent}"
        )

        try:
            sorted_depths = sorted(depth_groups.keys(), reverse=True)
            for depth_idx, depth in enumerate(sorted_depths):
                nodes = depth_groups[depth]
                folder_names = ', '.join(n.path.rsplit('/', 1)[-1] if n.path else 'root' for n in nodes[:5])
                suffix = '...' if len(nodes) > 5 else ''
                msg = f"Enrichment depth {depth}: {len(nodes)} folders [{folder_names}{suffix}]"
                logger.info(msg)
                if self._progress_callback:
                    await self._progress_callback(
                        f"Enriching depth {depth}: {len(nodes)} folders "
                        f"({depth_idx + 1}/{len(sorted_depths)} levels)"
                    )
                await self._enrich_depth_level(
                    client, nodes, folder_blueprints, file_reader,
                    prompt_template, enrichments, previous_content,
                )
        finally:
            await client.close()

        _release_encoder()  # Free ~10 MB tiktoken data

        ai_count = sum(1 for e in enrichments.values() if e.has_ai_content)
        total_non_passthrough = sum(
            1 for n in folders.values() if not n.is_passthrough
        )
        if ai_count == 0 and total_non_passthrough > 0:
            raise EnrichmentError(
                f"All {total_non_passthrough} enrichment calls failed: {self._first_error}"
            )

        done_msg = (
            f"Hybrid enrichment complete: {self.total_calls} API calls, "
            f"{ai_count}/{total_folders} folders enriched"
        )
        logger.info(done_msg)
        if self._progress_callback:
            await self._progress_callback(done_msg)
        return enrichments

    async def _enrich_depth_level(
        self,
        client,
        nodes: list[FolderNode],
        folder_blueprints: dict[str, FolderBlueprint],
        file_reader: Callable[[str], str | None],
        prompt_template: str,
        enrichments: dict[str, FolderEnrichment],
        previous_content: dict[str, str] | None = None,
    ) -> None:
        """Process all folders at one depth level in parallel."""
        previous_content = previous_content or {}
        tasks = []
        for node in nodes:
            if node.is_passthrough:
                enrichments[node.path] = FolderEnrichment(path=node.path, has_ai_content=False)
                continue
            fb = folder_blueprints.get(node.path, FolderBlueprint(path=node.path))
            children_summary = self._summarize_children(enrichments, node)
            prev_claude_md = previous_content.get(node.path, "")
            tasks.append(
                self._enrich_folder_with_semaphore(
                    client, node, fb, file_reader, prompt_template, children_summary,
                    prev_claude_md,
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            node = nodes[i]
            if isinstance(result, Exception):
                if self._first_error is None:
                    self._first_error = result
                logger.error(f"Enrichment failed for {node.path}: {result}")
                enrichments[node.path] = FolderEnrichment(path=node.path, has_ai_content=False)
            else:
                enrichments[node.path] = result

    async def _enrich_folder_with_semaphore(
        self,
        client,
        node: FolderNode,
        fb: FolderBlueprint,
        file_reader: Callable[[str], str | None],
        prompt_template: str,
        children_summary: str,
        previous_claude_md: str = "",
    ) -> FolderEnrichment:
        async with self._semaphore:
            return await self._enrich_single_folder(
                client, node, fb, file_reader, prompt_template, children_summary,
                previous_claude_md,
            )

    async def _enrich_single_folder(
        self,
        client,
        node: FolderNode,
        fb: FolderBlueprint,
        file_reader: Callable[[str], str | None],
        prompt_template: str,
        children_summary: str,
        previous_claude_md: str = "",
    ) -> FolderEnrichment:
        """Call AI for a single folder and parse the response."""
        self.total_calls += 1
        folder_label = node.path or "root"

        file_contents = self._read_folder_files(node, file_reader)
        logger.info(f"Enriching {folder_label}/ — {len(file_contents)} files read, {len(node.files)} total")
        prompt = self._build_prompt(prompt_template, node, fb, file_contents, children_summary, previous_claude_md)

        model = (
            self._config.enrichment_model
            or self._settings.default_ai_model
        )

        response = await client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text
        return self._parse_response(node.path, text)

    @staticmethod
    def _read_folder_files(
        node: FolderNode,
        file_reader: Callable[[str], str | None],
    ) -> dict[str, str]:
        """Read prioritized files from a folder within token budgets."""
        contents: dict[str, str] = {}
        prioritized = _prioritize_files(node.files)[:_MAX_FILES_PER_FOLDER]
        total_tokens = 0

        for filename in prioritized:
            if total_tokens >= _MAX_TOKENS_PER_FOLDER:
                break
            rel_path = f"{node.path}/{filename}" if node.path else filename
            content = file_reader(rel_path)
            if content:
                remaining = _MAX_TOKENS_PER_FOLDER - total_tokens
                max_for_file = min(_MAX_TOKENS_PER_FILE, remaining)
                truncated = _truncate_to_tokens(content, max_for_file)
                file_tokens = _count_tokens(truncated)
                contents[filename] = truncated
                total_tokens += file_tokens

        return contents

    @staticmethod
    def _build_prompt(
        template: str,
        node: FolderNode,
        fb: FolderBlueprint,
        file_contents: dict[str, str],
        children_summary: str,
        previous_claude_md: str = "",
    ) -> str:
        """Build the enrichment prompt from template and context."""
        # Format file contents
        contents_str = ""
        for filename, content in file_contents.items():
            contents_str += f"\n### {filename}\n```\n{content}\n```\n"

        # Format interfaces
        interfaces_parts = []
        for iface in fb.key_interfaces:
            name = iface.get("name", "")
            methods = iface.get("methods", [])
            if name:
                interfaces_parts.append(f"{name}: {', '.join(methods)}" if methods else name)
        interfaces_summary = "\n".join(interfaces_parts) if interfaces_parts else "None documented"

        # File listing
        file_listing = "\n".join(f"- {f}" for f in node.files) if node.files else "No files"

        prompt = template.format(
            folder_path=node.path or "root",
            component_name=fb.component_name or node.name,
            component_responsibility=fb.component_responsibility or "Not documented",
            depends_on=", ".join(fb.depends_on) if fb.depends_on else "None",
            exposes_to=", ".join(fb.exposes_to) if fb.exposes_to else "None",
            interfaces_summary=interfaces_summary,
            children_learned=children_summary or "No child folder data available.",
            file_listing=file_listing,
            file_contents=contents_str or "No file contents available.",
        )

        if previous_claude_md:
            prompt += (
                "\n\n### Previous CLAUDE.md Content\n"
                "Below is the existing documentation for this folder. "
                "KEEP the existing wording exactly as-is unless the current code "
                "contradicts it or new files/patterns were added. Only add, remove, "
                "or change lines that reflect actual code changes. Do NOT rephrase, "
                "reword, or reorganize content that is still accurate.\n\n"
                f"{previous_claude_md}\n"
            )

        return prompt

    @staticmethod
    def _summarize_children(
        enrichments: dict[str, FolderEnrichment],
        parent_node: FolderNode,
    ) -> str:
        """Produce compact summary from child enrichments for parent prompt."""
        parts = []
        for child_path in parent_node.children:
            enrichment = enrichments.get(child_path)
            if not enrichment or not enrichment.has_ai_content:
                continue
            child_name = child_path.rsplit("/", 1)[-1] if "/" in child_path else child_path
            summary = enrichment.purpose or "No purpose documented"
            # Include top 2 patterns for context
            top_patterns = enrichment.patterns[:2]
            pattern_str = ". Key patterns: " + ", ".join(top_patterns) if top_patterns else ""
            parts.append(f"{child_name}/ — {summary}{pattern_str}")
        return " | ".join(parts)

    @staticmethod
    def _parse_response(folder_path: str, text: str) -> FolderEnrichment:
        """Parse AI response into FolderEnrichment."""
        try:
            json_str = _extract_json(text)
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            return FolderEnrichment(path=folder_path, has_ai_content=False)

        if not isinstance(data, dict):
            return FolderEnrichment(path=folder_path, has_ai_content=False)

        # Parse key_file_guides
        key_file_guides = []
        for kfg in data.get("key_file_guides", []):
            if isinstance(kfg, dict) and "file" in kfg:
                key_file_guides.append(KeyFileGuide(
                    file=kfg["file"],
                    purpose=kfg.get("purpose", ""),
                    modification_guide=kfg.get("modification_guide", ""),
                ))

        # Parse common_task
        common_task = None
        ct_data = data.get("common_task")
        if isinstance(ct_data, dict) and "task" in ct_data:
            common_task = CommonTask(
                task=ct_data["task"],
                steps=ct_data.get("steps", []),
            )

        # Parse code_examples
        code_examples = []
        for ce in data.get("code_examples", []):
            if isinstance(ce, dict) and "label" in ce and "code" in ce:
                code_examples.append(CodeExample(
                    label=ce["label"],
                    code=ce["code"],
                    language=ce.get("language", ""),
                ))

        return FolderEnrichment(
            path=folder_path,
            purpose=data.get("purpose", ""),
            patterns=data.get("patterns", []),
            key_file_guides=key_file_guides,
            anti_patterns=data.get("anti_patterns", []),
            common_task=common_task,
            testing=data.get("testing", []),
            debugging=data.get("debugging", []),
            decisions=data.get("decisions", []),
            code_examples=code_examples,
            key_imports=data.get("key_imports", []),
            has_ai_content=True,
        )

    def _make_client(self):
        from anthropic import AsyncAnthropic
        return AsyncAnthropic(
            api_key=self._settings.anthropic_api_key,
            timeout=120.0,
            max_retries=2,
        )

    def _load_prompt_template(self) -> str:
        """Load enrichment prompt from prompts.json."""
        try:
            from infrastructure.prompts.prompt_loader import PromptLoader
            loader = PromptLoader()
            prompt_data = loader.get_prompt_by_key("intent_layer_enrichment")
            if prompt_data:
                return prompt_data.prompt_template
        except Exception as e:
            logger.warning(f"Failed to load intent_layer_enrichment prompt: {e}")
        return self._fallback_prompt()

    @staticmethod
    def _fallback_prompt() -> str:
        return """## Compound Learning — Folder Deep Work Session

You just completed a deep work session in this folder. Write down everything you learned so your future self can write correct code immediately next time.

Your notes should read like auto-memory from an experienced developer — NOT generated documentation.

### Folder
{folder_path}

### Component Context
Name: {component_name}
Responsibility: {component_responsibility}
Depends on: {depends_on}
Exposes to: {exposes_to}

### Interfaces Summary
{interfaces_summary}

### What Children Taught Us
{children_learned}

### Files in This Folder
{file_listing}

### File Contents
{file_contents}

## Task

Study the actual code above. Write compound learning notes — everything a developer needs to write correct code in this folder on day one.

Return ONLY valid JSON:

{{"purpose": "One dense sentence: what this folder IS + its primary constraint (max 20 words)", "patterns": ["Pattern from actual code (max 6 items, one line each)"], "key_file_guides": [{{"file": "filename.ext", "purpose": "10 words max", "modification_guide": "15 words max"}}], "anti_patterns": ["Don't X -- Y instead (max 3 items)"], "common_task": {{"task": "Most frequent modification", "steps": ["Terse step (max 4 steps)"]}}, "testing": ["How to test (max 2 items)"], "debugging": ["Debug insight (max 2 items)"], "decisions": ["Why this design choice (max 2 items)"], "code_examples": [{{"label": "Short description", "code": "3-8 lines max", "language": "python"}}], "key_imports": ["from module import Name (max 3 items)"]}}

## Line Budget

Output renders into a CLAUDE.md with a HARD 200-line cap. AI content gets ~120 lines. Every line must earn its place.
Prioritize: purpose > patterns > key_files > common_task > anti_patterns > testing.
Omit fields where you have nothing code-grounded to say.

## Rules

1. Derive patterns from ACTUAL code — not generic best practices
2. Every pattern must be mechanically verifiable by a code reviewer
3. Reference ONLY files in the listing
4. Prefer density over completeness: one precise sentence beats three vague ones
5. If Previous CLAUDE.md Content is provided below, preserve accurate insights and update outdated ones. Improve, don't copy.
"""
