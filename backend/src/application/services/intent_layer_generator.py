"""Intent Layer AI generator — concurrent batch generation of folder contexts.

Used only when enable_ai_enrichment is True (optional AI mode).
Contains AncestorCodeChain, ApiGenerationBackend, and budget logic.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Callable

from pydantic import BaseModel

from config.settings import Settings
from domain.entities.intent_layer import (
    FolderNode,
    FolderContext,
    IntentLayerConfig,
)

logger = logging.getLogger(__name__)

# File priority tiers — higher number = read first
_PRIORITY_TIERS: dict[str, int] = {
    "__init__.py": 4, "app.py": 4, "main.py": 4, "index.ts": 4,
    "index.tsx": 4, "index.js": 4, "mod.rs": 4, "lib.rs": 4,
    "config.py": 3, "settings.py": 3, "routes.py": 3, "models.py": 3,
    "schema.py": 3, "urls.py": 3, "router.py": 3,
    "interfaces.py": 2, "base.py": 2, "types.py": 2, "protocols.py": 2,
    "types.ts": 2, "constants.py": 2,
}

# Repo-size-aware budget tiers
_BUDGET_TIERS = [
    # (max_total_chars, per_folder, per_file_max, ancestor_chain_max)
    (300_000,    15_000, 8_000, 20_000),   # Small
    (1_000_000,  10_000, 5_000, 15_000),   # Medium
    (float("inf"), 6_000, 3_000, 10_000),  # Large
]


def prioritize_files(filenames: list[str]) -> list[str]:
    """Sort filenames by priority tier (highest first), then alphabetically."""
    def sort_key(f: str) -> tuple[int, str]:
        tier = _PRIORITY_TIERS.get(f, 0)
        return (-tier, f)
    return sorted(filenames, key=sort_key)


def _get_budgets(total_source_chars: int) -> tuple[int, int, int]:
    """Return (per_folder, per_file_max, ancestor_chain_max) for repo size."""
    per_folder, per_file, ancestor = _BUDGET_TIERS[-1][1], _BUDGET_TIERS[-1][2], _BUDGET_TIERS[-1][3]
    for max_chars, pf, pfm, anc in _BUDGET_TIERS:
        if total_source_chars <= max_chars:
            per_folder, per_file, ancestor = pf, pfm, anc
            break
    return per_folder, per_file, ancestor


# ── Ancestor Code Chain (moved from intent_layer.py, only used by AI mode) ──

class AncestorCodeEntry(BaseModel):
    """Code read at one ancestor folder."""
    folder_path: str
    files_read: dict[str, str] = {}   # {rel_path: content}
    total_chars: int = 0


class AncestorCodeChain(BaseModel):
    """Accumulated source code from root -> parent. Root-first ordering."""
    entries: list[AncestorCodeEntry] = []
    total_chars: int = 0

    def add_entry(self, folder_path: str, files_read: dict[str, str]) -> "AncestorCodeChain":
        """Return NEW chain with entry appended (immutable for concurrent safety)."""
        entry_chars = sum(len(v) for v in files_read.values())
        new_entry = AncestorCodeEntry(
            folder_path=folder_path,
            files_read=dict(files_read),
            total_chars=entry_chars,
        )
        return AncestorCodeChain(
            entries=[*self.entries, new_entry],
            total_chars=self.total_chars + entry_chars,
        )

    def format_for_prompt(self, budget_chars: int) -> str:
        """Render for prompt. Recent ancestors get full code, old ones get file listings only when budget tight."""
        if not self.entries:
            return "No ancestor code context available."

        parts: list[str] = []
        remaining = budget_chars

        # Process in reverse (most recent ancestor first gets priority)
        for entry in reversed(self.entries):
            if remaining <= 0:
                break
            header = f"#### {entry.folder_path or 'root'}/"
            if remaining >= entry.total_chars:
                # Full code fits
                file_parts = [header]
                for path, content in entry.files_read.items():
                    file_parts.append(f"**{path}**\n```\n{content}\n```")
                block = "\n".join(file_parts)
                parts.append(block)
                remaining -= entry.total_chars
            else:
                # Budget tight — file listing only
                listing = ", ".join(entry.files_read.keys())
                block = f"{header}\nFiles: {listing}"
                parts.append(block)
                remaining -= len(block)

        # Reverse back to root-first order
        parts.reverse()
        return "\n\n".join(parts)


# ── API Generation Backend (moved from generation_backend.py) ──

class _ApiGenerationBackend:
    """Uses AsyncAnthropic client directly (server-side compatible)."""

    def __init__(self, settings: Settings):
        from anthropic import AsyncAnthropic
        self._client = AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=300.0,
            max_retries=3,
        )
        model = settings.intent_layer_ai_model or settings.default_ai_model
        self._model = model

    async def generate_batch(
        self,
        folders: list[FolderNode],
        blueprint_summary: str,
        parent_context: FolderContext | None,
        file_contents: dict[str, str],
        prompt_template: str,
        ancestor_chain: AncestorCodeChain | None = None,
        ancestor_budget: int = 10_000,
    ) -> dict[str, FolderContext]:
        """Build prompt, call Claude API, parse JSON response."""
        folders_json = json.dumps(
            [f.model_dump(exclude_defaults=True) for f in folders],
            indent=2,
        )
        parent_ctx_str = ""
        if parent_context:
            parent_ctx_str = json.dumps(parent_context.model_dump(exclude_defaults=True), indent=2)

        file_contents_str = ""
        for path, content in file_contents.items():
            file_contents_str += f"\n### {path}\n```\n{content}\n```\n"

        ancestor_ctx_str = ""
        if ancestor_chain:
            ancestor_ctx_str = ancestor_chain.format_for_prompt(ancestor_budget)

        format_kwargs = {
            "blueprint_summary": blueprint_summary,
            "parent_context": parent_ctx_str or "No parent context (root level)",
            "folders_json": folders_json,
            "file_contents": file_contents_str or "No file contents available",
            "ancestor_code_context": ancestor_ctx_str or "No ancestor code context available.",
        }

        try:
            prompt = prompt_template.format(**format_kwargs)
        except KeyError:
            prompt = prompt_template.format(
                blueprint_summary=format_kwargs["blueprint_summary"],
                parent_context=format_kwargs["parent_context"],
                folders_json=format_kwargs["folders_json"],
                file_contents=format_kwargs["file_contents"],
            )

        retry_delays = [10, 30, 60]
        last_error = None

        for attempt in range(1 + len(retry_delays)):
            try:
                response = await self._client.messages.create(
                    model=self._model,
                    max_tokens=8000,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.content[0].text

                json_str = self._extract_json(text)
                data = json.loads(json_str)

                results: dict[str, FolderContext] = {}
                if isinstance(data, dict):
                    for folder_path, ctx_data in data.items():
                        if isinstance(ctx_data, dict):
                            ctx_data["path"] = folder_path
                            results[folder_path] = FolderContext.model_validate(ctx_data)
                return results

            except Exception as e:
                last_error = e
                if hasattr(e, 'status_code') and e.status_code in (400, 401, 403):
                    raise
                if attempt < len(retry_delays):
                    delay = retry_delays[attempt]
                    logger.warning(
                        f"Intent layer AI call failed (attempt {attempt + 1}), retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)

        raise RuntimeError(f"Intent layer AI call failed after all retries: {last_error}")

    @staticmethod
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


# ── Generator ──

class IntentLayerGenerator:
    """Orchestrates concurrent AI calls to generate FolderContext for each folder.

    Used only when enable_ai_enrichment is True.
    """

    def __init__(self, settings: Settings, config: IntentLayerConfig | None = None):
        self._settings = settings
        self._config = config or IntentLayerConfig()
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent)
        self.total_calls = 0

    async def generate(
        self,
        depth_groups: dict[int, list[FolderNode]],
        blueprint_summary: str,
        file_reader: Callable[[str], str | None],
        total_source_chars: int = 0,
    ) -> dict[str, FolderContext]:
        """Generate FolderContext for all folders, processing depth-by-depth."""
        from application.services.intent_layer_service import FolderHierarchyBuilder

        backend = _ApiGenerationBackend(self._settings)
        prompt_template = self._load_prompt_template()
        results: dict[str, FolderContext] = {}
        ancestor_chains: dict[str, AncestorCodeChain] = {}

        per_folder_budget, per_file_max, ancestor_budget = _get_budgets(total_source_chars)
        max_files_in_prompt = 50

        for depth in sorted(depth_groups.keys()):
            nodes_at_depth = depth_groups[depth]
            batches = FolderHierarchyBuilder.batch_siblings(
                nodes_at_depth, batch_size=4,
            )

            logger.info(f"Intent layer: processing depth {depth} — {len(batches)} batches, {len(nodes_at_depth)} folders")

            tasks = []
            batch_nodes_list = []
            for batch in batches:
                parent_ctx = None
                if batch and batch[0].parent_path in results:
                    parent_ctx = results[batch[0].parent_path]

                parent_path = batch[0].parent_path if batch else ""
                ancestor_chain = ancestor_chains.get(parent_path, AncestorCodeChain())

                file_contents = self._read_batch_files(
                    batch, file_reader,
                    budget_per_folder=per_folder_budget,
                    per_file_max=per_file_max,
                )

                prompt_batch = self._cap_file_listings(batch, max_files_in_prompt)

                tasks.append(
                    self._generate_with_semaphore(
                        backend, prompt_batch, blueprint_summary,
                        parent_ctx, file_contents, prompt_template,
                        ancestor_chain=ancestor_chain,
                        ancestor_budget=ancestor_budget,
                    )
                )
                batch_nodes_list.append((batch, file_contents, ancestor_chain))

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, batch_result in enumerate(batch_results):
                if isinstance(batch_result, Exception):
                    logger.error(f"Batch generation failed: {batch_result}")
                    continue
                contexts, files_read = batch_result
                results.update(contexts)

                batch, file_contents, parent_ancestor = batch_nodes_list[i]
                for node in batch:
                    node_prefix = f"{node.path}/" if node.path else ""
                    node_files = {
                        k: v for k, v in files_read.items()
                        if k.startswith(node_prefix) or (not node.path and "/" not in k)
                    }
                    ancestor_chains[node.path] = parent_ancestor.add_entry(
                        node.path, node_files,
                    )

        return results

    async def _generate_with_semaphore(
        self,
        backend,
        batch: list[FolderNode],
        blueprint_summary: str,
        parent_context: FolderContext | None,
        file_contents: dict[str, str],
        prompt_template: str,
        ancestor_chain: AncestorCodeChain | None = None,
        ancestor_budget: int = 10_000,
    ) -> tuple[dict[str, FolderContext], dict[str, str]]:
        async with self._semaphore:
            self.total_calls += 1
            contexts = await backend.generate_batch(
                folders=batch,
                blueprint_summary=blueprint_summary,
                parent_context=parent_context,
                file_contents=file_contents,
                prompt_template=prompt_template,
                ancestor_chain=ancestor_chain,
                ancestor_budget=ancestor_budget,
            )
            return contexts, file_contents

    @staticmethod
    def _cap_file_listings(batch: list[FolderNode], max_files: int) -> list[FolderNode]:
        if max_files <= 0:
            return batch
        capped: list[FolderNode] = []
        for node in batch:
            if len(node.files) <= max_files:
                capped.append(node)
            else:
                trimmed = prioritize_files(node.files)[:max_files]
                capped.append(node.model_copy(update={"files": trimmed}))
        return capped

    def _read_batch_files(
        self,
        batch: list[FolderNode],
        file_reader: Callable[[str], str | None],
        budget_per_folder: int = 10_000,
        per_file_max: int = 5_000,
    ) -> dict[str, str]:
        contents: dict[str, str] = {}
        for node in batch:
            folder_budget = budget_per_folder
            prioritized = prioritize_files(node.files)
            for filename in prioritized:
                if folder_budget <= 0:
                    break
                rel_path = f"{node.path}/{filename}" if node.path else filename
                content = file_reader(rel_path)
                if content:
                    truncated = content[:min(per_file_max, folder_budget)]
                    contents[rel_path] = truncated
                    folder_budget -= len(truncated)
        return contents

    def _load_prompt_template(self) -> str:
        try:
            from infrastructure.prompts.prompt_loader import PromptLoader
            loader = PromptLoader()
            prompt_data = loader.get_prompt_by_key("intent_layer_folder")
            if prompt_data and isinstance(prompt_data, dict):
                return prompt_data.get("prompt_template", self._fallback_prompt())
            if isinstance(prompt_data, str):
                return prompt_data
        except Exception as e:
            logger.warning(f"Failed to load intent_layer_folder prompt: {e}")
        return self._fallback_prompt()

    @staticmethod
    def _fallback_prompt() -> str:
        return """## Intent Layer — Folder Context Generation

### Blueprint Summary
{blueprint_summary}

### Ancestor Code Context (root -> parent chain)
{ancestor_code_context}

### Parent Context
{parent_context}

### Folders to Analyze
{folders_json}

### File Contents
{file_contents}

## Task
For each folder listed above, generate a JSON object with this structure:

```json
{{
  "folder/path": {{
    "purpose": "One-line description of what this folder is for",
    "scope": "What this folder owns and is responsible for",
    "key_files": [{{"file": "filename.ext", "description": "What this file does"}}],
    "patterns": ["Pattern 1 used in this folder", "Pattern 2"],
    "anti_patterns": ["What NOT to do in this folder"],
    "cross_references": [{{"path": "../related/", "relationship": "How they relate"}}],
    "downlinks": [{{"path": "child/", "summary": "What the child folder does"}}]
  }}
}}
```

Rules:
- Use ancestor code to understand imports, class hierarchies, and wiring
- DO NOT repeat information already in the parent context — say "Inherits X from parent" instead
- Reference ACTUAL file names from the listing
- Be concise and token-efficient
- Focus on what an AI agent needs to know to work correctly in this folder
"""
