#!/usr/bin/env python3
"""Archie AI normalizer — generates prompt for AI-based schema normalization.

Run: python3 normalize.py prompt /path/to/repo   → prints normalizer prompt to stdout
     python3 normalize.py apply /path/to/repo     → reads .archie/blueprint_normalized.json, saves as blueprint.json

The AI normalizer is a single Claude subagent call that reads blueprint_raw.json
and reshapes every field to match the canonical StructuredBlueprint schema.
This replaces deterministic alias-mapping — the AI understands semantics.

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Canonical schema definition — the single source of truth for field names
# ---------------------------------------------------------------------------

SCHEMA = """\
## StructuredBlueprint — Canonical Schema

Every field name below is EXACT. Map the raw data to these fields. Do NOT invent new fields.

### meta (object)
- repository: string — repo name
- analyzed_at: string — ISO timestamp
- schema_version: string — always "2.0.0"
- architecture_style: string — e.g. "Full-stack Next.js monolith with MVC-like layering"
- platforms: string[] — e.g. ["backend", "web-frontend"]
- executive_summary: string — 3-5 factual sentences about the codebase

### architecture_rules (object)
- file_placement_rules: array of {component_type, naming_pattern, location, example, description}
- naming_conventions: array of {scope, pattern, examples: string[], description}

### decisions (object)
- architectural_style: {title, chosen, rationale, alternatives_rejected: string[]} — THE top-level architecture decision
- key_decisions: array of {title, chosen, rationale, alternatives_rejected: string[], forced_by: string (optional), enables: string (optional)}
- trade_offs: array of {accept, benefit, caused_by: string (optional), violation_signals: string[] (optional)}
- out_of_scope: string[]
- decision_chain: object (optional) — {root: string, forces: [{decision, rationale, violation_keywords: string[], forces: [...]}]}

### components (object)
- structure_type: string — "layered" | "modular" | "feature-based" | "flat"
- components: array of {name, location, responsibility, platform, depends_on: string[], exposes_to: string[], key_interfaces: [{name, methods: string[], description}], key_files: [{path, purpose}]}
- contracts: array of {interface_name, description, methods: string[], properties: string[], implementing_files: string[]}

### communication (object)
- patterns: array of {name, when_to_use, how_it_works, examples: string[]}
- integrations: array of {service, purpose, integration_point}
- pattern_selection_guide: array of {scenario, pattern, rationale}

### quick_reference (object)
- where_to_put_code: object — {"component_type": "path", ...}
- pattern_selection: object — {"scenario": "pattern", ...}
- error_mapping: array of {error, status_code, description}

### technology (object)
- stack: array of {category, name, version, purpose}
- templates: array of {component_type, description, file_path_template, code}
- project_structure: string — ASCII directory tree
- run_commands: object — {"dev": "npm run dev", "test": "npm test", ...}

### frontend (object, empty {} if no frontend)
- framework: string
- rendering_strategy: string — "SSR" | "CSR" | "hybrid" | "SSG"
- ui_components: array of {name, location, component_type, description, props: string[], children: string[]}
- state_management: {approach, global_state: [{store, purpose}], server_state, local_state, rationale}
- routing: array of {path, component, description, auth_required: bool}
- data_fetching: array of {name, mechanism, when_to_use, examples: string[]}
- styling: string
- key_conventions: string[]

### architecture_diagram: string — Mermaid graph TD syntax

### pitfalls: array of {area, description, recommendation, stems_from: string[] (optional, causal chain), applies_to: string[] (optional, file paths)}

### implementation_guidelines: array of {capability, category, libraries: string[], pattern_description, key_files: string[], usage_example, tips: string[]}

### development_rules: array of {category, rule, source}
  category must be one of: dependency_management, testing, code_style, ci_cd, environment, git, error_handling, security, performance, general

### deployment (object)
- runtime_environment: string — "AWS", "Vercel", "local development", etc.
- compute_services: string[]
- container_runtime: string
- orchestration: string
- serverless_functions: string
- ci_cd: string[]
- distribution: string[]
- infrastructure_as_code: string
- supporting_services: string[]
- environment_config: string
- key_files: string[]
"""


def cmd_prompt(root: Path):
    """Generate AI normalizer prompt, output to stdout."""
    raw_path = root / ".archie" / "blueprint_raw.json"
    if not raw_path.exists():
        print("Error: .archie/blueprint_raw.json not found. Run merge first.", file=sys.stderr)
        sys.exit(1)

    raw = json.loads(raw_path.read_text())

    prompt_parts = []
    prompt_parts.append("You are a schema normalizer. Your job is to reshape a raw architecture blueprint JSON into the exact canonical schema below.")
    prompt_parts.append("")
    prompt_parts.append("RULES:")
    prompt_parts.append("1. PRESERVE all data — do not drop, summarize, or invent information")
    prompt_parts.append("2. MAP fields semantically to canonical names (e.g. raw 'decision' → canonical 'title', raw 'from'+'to'+'method' → synthesize a 'name' like 'SSE streaming from GeneratePanel to API')")
    prompt_parts.append("3. RESTRUCTURE containers (e.g. raw flat list of decisions → split into architectural_style + key_decisions)")
    prompt_parts.append("4. FILL structural fields with empty defaults if not present in raw data (empty string, empty array, empty object)")
    prompt_parts.append("5. For decisions.architectural_style: identify THE top-level architecture pattern from the decisions list and promote it")
    prompt_parts.append("6. For communication.patterns: each pattern needs a descriptive 'name', 'when_to_use', and 'how_it_works' — synthesize these from the raw fields (from/to/method/data_format or whatever the raw shape is)")
    prompt_parts.append("7. For meta.architecture_style: set it to the same value as decisions.architectural_style.title")
    prompt_parts.append("8. For deployment: map raw fields like 'method' → 'runtime_environment', 'env_vars' → 'environment_config', 'build_steps' → keep as supporting info")
    prompt_parts.append("9. For pitfalls: if raw items are plain strings, split into area (topic keyword) + description (the issue) + recommendation (what to do about it)")
    prompt_parts.append("10. For implementation_guidelines: ensure each has capability (short name), category, libraries[], pattern_description, key_files[], usage_example, tips[]")
    prompt_parts.append("11. For development_rules: ensure each has category (from allowed list), rule, source")
    prompt_parts.append("12. Return ONLY valid JSON — no markdown, no explanation, no commentary")
    prompt_parts.append("")
    prompt_parts.append(SCHEMA)
    prompt_parts.append("")
    prompt_parts.append("---")
    prompt_parts.append("")
    prompt_parts.append("## Raw Blueprint Data")
    prompt_parts.append("")
    prompt_parts.append("```json")
    prompt_parts.append(json.dumps(raw, indent=2))
    prompt_parts.append("```")
    prompt_parts.append("")
    prompt_parts.append("Normalize the above to the canonical schema. Return ONLY the complete JSON object.")

    print("\n".join(prompt_parts))


def cmd_apply(root: Path):
    """Read normalized blueprint from .archie/blueprint_normalized.json, save as blueprint.json."""
    norm_path = root / ".archie" / "blueprint_normalized.json"
    if not norm_path.exists():
        print("Error: .archie/blueprint_normalized.json not found.", file=sys.stderr)
        sys.exit(1)

    bp = json.loads(norm_path.read_text())

    # Minimal structural validation — ensure top-level sections exist
    for key in ("meta", "architecture_rules", "decisions", "components",
                "communication", "quick_reference", "technology", "frontend",
                "deployment"):
        if key not in bp or not isinstance(bp.get(key), dict):
            bp[key] = bp.get(key, {})
            if not isinstance(bp[key], dict):
                bp[key] = {}

    for key in ("pitfalls", "implementation_guidelines",
                "development_rules"):
        if key not in bp or not isinstance(bp.get(key), list):
            bp[key] = bp.get(key, [])
            if not isinstance(bp[key], list):
                bp[key] = []

    bp.setdefault("architecture_diagram", "")

    bp_path = root / ".archie" / "blueprint.json"
    bp_path.write_text(json.dumps(bp, indent=2))

    # Report stats
    comps = bp.get("components", {})
    comp_count = len(comps.get("components", [])) if isinstance(comps, dict) else 0
    pattern_count = len(bp.get("communication", {}).get("patterns", []))
    decision_count = len(bp.get("decisions", {}).get("key_decisions", []))
    pitfall_count = len(bp.get("pitfalls", []))
    guideline_count = len(bp.get("implementation_guidelines", []))
    rule_count = len(bp.get("development_rules", []))
    style = bp.get("meta", {}).get("architecture_style", "")

    print(f"Normalized blueprint saved: {bp_path}", file=sys.stderr)
    print(f"  Style: {style}", file=sys.stderr)
    print(f"  {comp_count} components, {pattern_count} patterns, {decision_count} decisions", file=sys.stderr)
    print(f"  {pitfall_count} pitfalls, {guideline_count} guidelines, {rule_count} rules", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:", file=sys.stderr)
        print("  python3 normalize.py prompt /path/to/repo   — generate normalizer prompt", file=sys.stderr)
        print("  python3 normalize.py apply /path/to/repo    — apply normalized blueprint", file=sys.stderr)
        sys.exit(1)

    subcmd = sys.argv[1]
    root = Path(sys.argv[2]).resolve()

    if subcmd == "prompt":
        cmd_prompt(root)
    elif subcmd == "apply":
        cmd_apply(root)
    else:
        print(f"Error: unknown subcommand '{subcmd}'", file=sys.stderr)
        sys.exit(1)
