"""Single source of truth: every command, hook, config patch, and agent
Archie installs. Connectors consume these lists at install time.

Adding a feature = one entry here + one body/script/template file under
archie/assets/. No connector files need to change.

Paths use ".archie/..." prefixes because they point at where the asset
WILL live in the installed project (after the install loop copies
archie/assets/* into <project>/.archie/). See
docs/plans/2026-05-18-multi-agent-connector-architecture.md §12 for the
asset migration map.
"""
from .manifest import AgentDef, CommandDef, ConfigPatch, HookDef


COMMANDS = [
    CommandDef(
        "archie-scan",
        "Architecture health check (1-3 min).",
        ".archie/prompts/skill_archie_scan.md",
    ),
    CommandDef(
        "archie-deep-scan",
        "Comprehensive architecture baseline (15-20 min).",
        ".archie/prompts/skill_archie_deep_scan.md",
    ),
    CommandDef(
        "archie-intent-layer",
        "Generate per-folder CLAUDE.md context via bottom-up DAG.",
        ".archie/prompts/skill_archie_intent_layer.md",
    ),
    CommandDef(
        "archie-viewer",
        "Open the blueprint inspector in the browser.",
        ".archie/prompts/skill_archie_viewer.md",
    ),
    CommandDef(
        "archie-share",
        "Upload the blueprint and return a share link.",
        ".archie/prompts/skill_archie_share.md",
    ),
]


HOOKS = [
    HookDef(
        "pre-tool-use",
        "Edit|Write|MultiEdit",
        ".archie/hooks/pre-validate.sh",
        blocking=True,
    ),
    HookDef(
        "pre-tool-use",
        "Bash",
        ".archie/hooks/pre-commit-review.sh",
        blocking=True,
    ),
    HookDef(
        "pre-tool-use",
        "Glob|Grep",
        ".archie/hooks/blueprint-nudge.sh",
        blocking=False,
    ),
    HookDef(
        "post-tool-use",
        "ExitPlanMode",
        ".archie/hooks/post-plan-review.sh",
        blocking=False,
    ),
    HookDef(
        "post-tool-use",
        "Edit|Write|MultiEdit",
        ".archie/hooks/post-lint.sh",
        blocking=False,
    ),
    HookDef(
        "user-prompt-submit",
        None,
        ".archie/hooks/pre-turn.sh",
        blocking=False,
    ),
]


CONFIG_PATCHES = [
    ConfigPatch("codex", "project_doc_max_bytes", 131072),
    ConfigPatch("codex", "project_doc_fallback_filenames", ["CLAUDE.md"]),
]


AGENTS = [
    AgentDef(
        "archie-wave1-structure",
        "Wave-1 structure pass: components, layers, file placement.",
        ".archie/prompts/wave1_structure.md",
    ),
    AgentDef(
        "archie-wave1-patterns",
        "Wave-1 patterns pass: communication, design patterns, integrations.",
        ".archie/prompts/wave1_patterns.md",
    ),
    AgentDef(
        "archie-wave1-technology",
        "Wave-1 technology pass: stack, deployment, dev rules.",
        ".archie/prompts/wave1_technology.md",
    ),
    AgentDef(
        "archie-wave1-ui",
        "Wave-1 UI pass: components, state, routing (only when frontend_ratio >= 0.20).",
        ".archie/prompts/wave1_ui.md",
    ),
    AgentDef(
        "archie-wave2-reasoning",
        "Wave-2 reasoning pass: synthesizes Wave-1 outputs into decision chain, pitfalls, trade-offs.",
        ".archie/prompts/wave2_reasoning.md",
        model="opus",
    ),
]
