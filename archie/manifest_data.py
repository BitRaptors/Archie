"""Single source of truth: every command, hook, and config patch
Archie installs. Connectors consume these lists at install time.

Adding a feature = one entry here + one body/script/template file under
archie/assets/. No connector files need to change.

Paths use ".archie/..." prefixes because they point at where the asset
WILL live in the installed project (after the install loop copies
archie/assets/* into <project>/.archie/). See
docs/plans/2026-05-18-multi-agent-connector-architecture.md §12 for the
asset migration map.
"""
from .manifest import CommandDef, ConfigPatch, HookDef


# body_path is the command's SKILL.md *inside the rendered workflow tree*,
# relative to that tree's per-CLI root. Connectors prepend their own
# .archie/workflow/<cli>/ root (the {{WORKFLOW_ROOT}} token) at install time.
COMMANDS = [
    CommandDef(
        "archie-scan",
        "Architecture health check (1-3 min).",
        "scan/SKILL.md",
    ),
    CommandDef(
        "archie-deep-scan",
        "Comprehensive architecture baseline (15-20 min).",
        "deep-scan/SKILL.md",
    ),
    CommandDef(
        "archie-intent-layer",
        "Generate per-folder CLAUDE.md context via bottom-up DAG.",
        "intent-layer/SKILL.md",
    ),
    CommandDef(
        "archie-viewer",
        "Open the blueprint inspector in the browser.",
        "viewer/SKILL.md",
    ),
    CommandDef(
        "archie-share",
        "Upload the blueprint and return a share link.",
        "share/SKILL.md",
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
    HookDef(
        "stop",
        None,
        ".archie/hooks/stop.sh",
        blocking=False,
    ),
]


CONFIG_PATCHES = [
    ConfigPatch("codex", "project_doc_max_bytes", 131072),
    ConfigPatch("codex", "project_doc_fallback_filenames", ["CLAUDE.md"]),
    # [agents] section keys (documented in Codex docs under ~/.codex/config.toml).
    # max_threads default is 6; max_depth default is 1. Archie needs depth 2 to
    # support the documented call chain root → workspace worker → Wave-1 worker
    # on monorepo deep-scans (SCOPE=per-package or hybrid). max_threads stays at
    # the default 6 to be explicit and survive any future Codex default change.
    ConfigPatch("codex", "max_threads", 6, section="agents"),
    ConfigPatch("codex", "max_depth", 2, section="agents"),
]
