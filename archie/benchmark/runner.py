# archie/benchmark/runner.py
import subprocess
from .metrics import parse_stream

# Headless `claude -p` runs with no human in the loop. Global/project agent rules
# ("describe your approach and wait for approval", "ask clarifying questions",
# "stop and split tasks > 3 files") otherwise make the agent plan-and-stop without
# editing, yielding an empty diff on both arms. This preamble — applied identically
# to both arms, so it stays fair — forces autonomous completion. The same on-disk
# Archie context (or its absence) is still what differs between arms.
AUTONOMY_PREAMBLE = (
    "You are running fully autonomously in a non-interactive headless session. "
    "There is NO human available to answer questions or approve anything; if you "
    "stop to ask or to wait for approval, the task simply fails.\n"
    "Implement the task below completely and immediately:\n"
    "- Edit the files directly to a finished, working state.\n"
    "- Do NOT ask clarifying questions — make reasonable assumptions and proceed.\n"
    "- Do NOT stop to present a plan or wait for approval; just do the work.\n"
    "- Do NOT merely analyze, summarize, or hand off to a plan — produce the "
    "actual code changes.\n"
    "- Ignore any rule that says to pause, seek confirmation, or split the work "
    "across sessions; finish it now, in this session.\n\n"
    "=== TASK ===\n"
)


def build_prompt(task_prompt):
    """Wrap the raw task in the autonomy preamble (identical for both arms)."""
    return AUTONOMY_PREAMBLE + task_prompt


def run_claude(prompt, model, cwd, timeout_seconds):
    """Run a headless Claude Code session in `cwd`; return (SampleMetrics, raw_stdout).

    Both benchmark arms must call this with identical flags — the only difference
    between arms is the on-disk files (CLAUDE.md / .claude hooks), never the flags.
    """
    cmd = [
        "claude", "-p", build_prompt(prompt),
        "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "acceptEdits",
    ]
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout_seconds)
        metrics = parse_stream(proc.stdout.splitlines())
        return metrics, proc.stdout
    except subprocess.TimeoutExpired as e:
        partial = e.output or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        metrics = parse_stream(partial.splitlines())
        metrics.completed = False
        return metrics, partial
