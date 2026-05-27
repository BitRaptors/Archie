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
from .manifest import CommandDef, CommandRule, ConfigPatch, HookDef


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


# Auto-approved shell command catalogue. Each entry pairs a Codex
# execpolicy `prefix_rule.pattern` (argv-prefix tokens) with the Claude
# permission-allowlist glob it covers. Both are install-time pre-approvals
# so the deep-scan workflow runs prompt-free on either CLI.
#
# Python scripts under .archie/ are NOT enumerated here — they're driven
# directly from _STANDALONE_SCRIPTS in install.py so adding a new script
# automatically gets a Codex rule + Claude glob for free.
#
# `rm -f` is the one entry where Claude and Codex diverge in scope: Claude
# uses narrow path-suffix globs (`.archie/tmp/archie_*` literal); Codex's
# argv-prefix matcher can't see beyond the literal third token (bash
# expands globs to many literal argv entries before exec), so the Codex
# entry pairs the constant prefix with a justification limiting intent.
COMMAND_RULES = [
    # Inline Python (one-off snippets used in a few workflow Bash blocks)
    CommandRule(
        name="python3-inline",
        codex_pattern=("python3", "-c"),
        claude_glob="Bash(python3 -c *)",
        justification="Inline Python — Archie workflow uses for JSON inspection",
    ),
    # Filesystem prep / inspection
    CommandRule(
        name="mkdir",
        codex_pattern=("mkdir",),
        claude_glob="Bash(mkdir *)",
        justification="Create workspace directories",
    ),
    CommandRule(
        name="cp",
        codex_pattern=("cp",),
        claude_glob="Bash(cp *)",
        justification="Copy file (workflow uses for workspace-relative copies)",
    ),
    CommandRule(
        name="cat",
        codex_pattern=("cat",),
        claude_glob="Bash(cat *)",
        justification="Read file to stdout",
    ),
    CommandRule(
        name="ls",
        codex_pattern=("ls",),
        claude_glob="Bash(ls *)",
        justification="List directory contents",
    ),
    CommandRule(
        name="wc",
        codex_pattern=("wc",),
        claude_glob="Bash(wc *)",
        justification="Word / line / byte count",
    ),
    CommandRule(
        name="head",
        codex_pattern=("head",),
        claude_glob="Bash(head *)",
        justification="Read head of file",
    ),
    CommandRule(
        name="sort",
        codex_pattern=("sort",),
        claude_glob="Bash(sort *)",
        justification="Sort lines",
    ),
    CommandRule(
        name="date",
        codex_pattern=("date",),
        claude_glob="Bash(date *)",
        justification="Format timestamp for telemetry",
    ),
    CommandRule(
        name="echo",
        codex_pattern=("echo",),
        claude_glob="Bash(echo *)",
        justification="Print text (used for pipe-to-script in scope_resolution)",
    ),
    CommandRule(
        name="test",
        codex_pattern=("test",),
        claude_glob="Bash(test *)",
        justification="Conditional test (often a bash builtin; allow for completeness)",
    ),
    # rm: workflow only forcibly removes Archie artifacts under .archie/.
    # Claude's narrow globs match argv-as-string; Codex's prefix matcher
    # operates on post-glob-expansion argv lists, so the broader ("rm","-f")
    # pattern is the narrowest expressible on the Codex side. The
    # justification documents intent.
    CommandRule(
        name="rm-archie-health",
        codex_pattern=("rm", "-f", ".archie/health.json"),
        claude_glob="Bash(rm -f .archie/health.json)",
        justification="Remove the Archie health marker",
    ),
    CommandRule(
        name="rm-archie-tmp",
        codex_pattern=("rm", "-f"),
        claude_glob="Bash(rm -f .archie/tmp/archie_*)",
        justification=(
            "Remove transient Archie run artifacts under .archie/tmp/. "
            "Codex argv-prefix can't bind tighter than 'rm -f' because "
            "bash expands the .archie/tmp/archie_* glob to many literal "
            "argv entries before exec — workflow only uses rm -f for "
            "Archie's own .archie/ paths."
        ),
    ),
    # Read-only git
    CommandRule(
        name="git-status",
        codex_pattern=("git", "status"),
        claude_glob="Bash(git status*)",
        justification="Read git status",
    ),
    CommandRule(
        name="git-diff",
        codex_pattern=("git", "diff"),
        claude_glob="Bash(git diff*)",
        justification="Read git diff",
    ),
    CommandRule(
        name="git-log",
        codex_pattern=("git", "log"),
        claude_glob="Bash(git log*)",
        justification="Read git log",
    ),
    CommandRule(
        name="git-rev-parse",
        codex_pattern=("git", "rev-parse"),
        claude_glob="Bash(git rev-parse*)",
        justification="Read git ref / branch names",
    ),
    CommandRule(
        name="git-ls-files",
        codex_pattern=("git", "ls-files"),
        claude_glob="Bash(git ls-files*)",
        justification="List tracked files",
    ),
    CommandRule(
        name="git-ls-tree",
        codex_pattern=("git", "ls-tree"),
        claude_glob="Bash(git ls-tree*)",
        justification="List tree contents",
    ),
    CommandRule(
        name="git-show",
        codex_pattern=("git", "show"),
        claude_glob="Bash(git show*)",
        justification="Show git object contents",
    ),
    # `git -C <dir> <subcmd>` — workflow uses for scoped subdirectory
    # operations. Narrow it to known read-only subcommands.
    CommandRule(
        name="git-c-scoped",
        codex_pattern=("git", "-C"),
        claude_glob="Bash(git -C*)",
        justification="git -C <dir> read-only subcommands",
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
