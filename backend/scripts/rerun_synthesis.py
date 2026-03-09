"""Re-run only the synthesis phase using cached phase outputs.

Usage:
    PYTHONPATH=src python scripts/rerun_synthesis.py <repository_id> [--model MODEL]

This reads the saved phase outputs from storage/blueprints/<repo_id>/*.json,
runs only the blueprint synthesis, and saves the new blueprint.json.
Useful for iterating on the synthesis prompt without re-running the full pipeline.
"""
import argparse
import asyncio
import json
import time
from pathlib import Path

from anthropic import AsyncAnthropic

from config.settings import get_settings
from domain.entities.blueprint import StructuredBlueprint
from infrastructure.prompts.prompt_loader import PromptLoader


async def main(repo_id: str, model_override: str | None = None) -> None:
    settings = get_settings()
    storage_dir = Path("storage/blueprints") / repo_id

    if not storage_dir.exists():
        print(f"ERROR: No cached phase outputs at {storage_dir}")
        return

    # Load cached phase outputs
    phases = {}
    for phase_file in ["observation", "discovery", "layers", "patterns",
                        "communication", "technology", "frontend_analysis",
                        "implementation_analysis"]:
        path = storage_dir / f"{phase_file}.json"
        if path.exists():
            raw = path.read_text()
            # Phase outputs are stored as JSON strings or JSON objects
            try:
                parsed = json.loads(raw)
                phases[phase_file] = parsed if isinstance(parsed, str) else json.dumps(parsed, indent=2)
            except json.JSONDecodeError:
                phases[phase_file] = raw
        else:
            phases[phase_file] = ""

    print(f"Loaded {len(phases)} phase outputs from {storage_dir}")
    for k, v in phases.items():
        print(f"  {k}: {len(v):,} chars")

    # Load the blueprint to get metadata
    bp_path = storage_dir / "blueprint.json"
    old_bp = json.loads(bp_path.read_text()) if bp_path.exists() else {}
    repo_name = old_bp.get("meta", {}).get("repository", repo_id)

    # Load file tree from the repo copy
    repo_copy_dir = Path("storage/repos") / repo_id
    file_tree = ""
    if repo_copy_dir.exists():
        files = sorted(str(p.relative_to(repo_copy_dir)) for p in repo_copy_dir.rglob("*") if p.is_file())
        file_tree = "\n".join(files[:500])
        print(f"  file_tree: {len(files)} files")

    # Build file registry (same as pipeline)
    file_registry = "\n".join(files[:500]) if repo_copy_dir.exists() else ""

    # Load synthesis prompt
    loader = PromptLoader()
    prompt = loader.get_prompt_by_key("blueprint_synthesis")

    # Detect frontend
    has_frontend = bool(phases.get("frontend_analysis", "").strip())
    platform_hint = "" if has_frontend else (
        "**IMPORTANT**: No frontend/UI layer was detected. "
        "Set meta.platforms to [\"backend\"] and leave frontend section empty."
    )

    prompt_text = prompt.render({
        "repository_name": repo_name,
        "discovery": phases.get("discovery", "")[:10000],
        "layers": phases.get("layers", "")[:10000],
        "patterns": phases.get("patterns", "")[:10000],
        "communication": phases.get("communication", "")[:10000],
        "technology": phases.get("technology", "")[:10000],
        "frontend_analysis": phases.get("frontend_analysis", "")[:10000] if has_frontend else "No frontend/UI layer detected.",
        "implementation_analysis": phases.get("implementation_analysis", "")[:10000],
        "code_samples": "",
        "platform_hint": platform_hint,
        "file_tree": file_tree[:10000],
        "framework_usage": "",
        "provided_capabilities": "",
        "file_registry": file_registry[:10000],
    })

    model = model_override or settings.synthesis_ai_model
    max_tokens = settings.synthesis_max_tokens

    print(f"\nRunning synthesis with {model} (max_tokens={max_tokens})...")
    print(f"Prompt size: {len(prompt_text):,} chars")

    client = AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=600.0)

    start = time.time()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt_text}],
    )
    elapsed = time.time() - start

    raw_text = response.content[0].text
    print(f"\nSynthesis complete in {elapsed:.1f}s")
    print(f"Output: {len(raw_text):,} chars, stop_reason={response.stop_reason}")
    print(f"Tokens: input={response.usage.input_tokens}, output={response.usage.output_tokens}")

    if response.stop_reason == "max_tokens":
        print("WARNING: Output was TRUNCATED!")

    # Parse JSON
    text = raw_text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()
    brace_start = text.find("{")
    if brace_start != -1:
        text = text[brace_start:]

    try:
        structured = json.loads(text)
    except json.JSONDecodeError:
        brace_end = text.rfind("}")
        if brace_end != -1:
            structured = json.loads(text[:brace_end + 1])
        else:
            print("ERROR: Could not parse JSON!")
            (storage_dir / "synthesis_raw.txt").write_text(raw_text)
            return

    # Validate with Pydantic
    blueprint = StructuredBlueprint.model_validate(structured)
    if not blueprint.meta.repository:
        blueprint.meta.repository = repo_name
    if not blueprint.meta.repository_id:
        blueprint.meta.repository_id = repo_id

    # Save
    output = blueprint.model_dump()
    output_json = json.dumps(output, indent=2, ensure_ascii=False)
    bp_path.write_text(output_json)
    print(f"\nSaved blueprint: {len(output_json):,} chars → {bp_path}")

    # Section sizes
    print("\nSection sizes:")
    for key, val in output.items():
        size = len(json.dumps(val, indent=2))
        print(f"  {key:35s} {size:>8,} chars")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-run synthesis from cached phase outputs")
    parser.add_argument("repo_id", help="Repository ID (UUID)")
    parser.add_argument("--model", help="Override synthesis model", default=None)
    args = parser.parse_args()
    asyncio.run(main(args.repo_id, args.model))
