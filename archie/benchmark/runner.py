# archie/benchmark/runner.py
import subprocess
from .metrics import parse_stream


def run_claude(prompt, model, cwd, timeout_seconds):
    """Run a headless Claude Code session in `cwd`; return (SampleMetrics, raw_stdout).

    Both benchmark arms must call this with identical flags — the only difference
    between arms is the on-disk files (CLAUDE.md / .claude hooks), never the flags.
    """
    cmd = [
        "claude", "-p", prompt,
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
