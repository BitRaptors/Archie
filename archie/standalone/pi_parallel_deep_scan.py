#!/usr/bin/env python3
"""Pi RPC parallel deep-scan adapter.

Thin orchestration layer only: scanner -> parallel Wave 1 Pi RPC workers ->
Wave 2 Pi RPC synthesis -> renderer/validator. Workflow details live in
.archie/prompts/pi/deep_scan_jobs.json and prompt markdown files.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shlex
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

REQUIRED_BLUEPRINT_KEYS = [
    "meta", "architecture_rules", "decisions", "components", "communication",
    "quick_reference", "technology", "deployment", "frontend", "pitfalls",
    "implementation_guidelines", "development_rules", "architecture_diagram",
]

DEFAULT_TIMEOUT = int(os.environ.get("ARCHIE_PI_RPC_TIMEOUT", "1200"))


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def _load_jobs(root: Path) -> dict[str, Any]:
    path = root / ".archie" / "prompts" / "pi" / "deep_scan_jobs.json"
    if not path.exists():
        raise FileNotFoundError(f"Pi deep-scan job file missing: {path}")
    return json.loads(path.read_text())


def _pi_base_cmd() -> list[str]:
    extra = shlex.split(os.environ.get("ARCHIE_PI_RPC_ARGS", ""))
    return ["pi", "--mode", "rpc", "--no-session", *extra]


def _extract_text(message: dict[str, Any]) -> str:
    parts = []
    for item in message.get("content", []):
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
    return "\n".join(parts).strip()


def _parse_json_from_text(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = min([i for i in (text.find("{"), text.find("[")) if i >= 0], default=-1)
        if start < 0:
            raise
        opener = text[start]
        closer = "}" if opener == "{" else "]"
        end = text.rfind(closer)
        if end <= start:
            raise
        return json.loads(text[start:end + 1])


def _rpc_prompt(root: Path, prompt: str, label: str, out_dir: Path, timeout: int) -> Any:
    out_dir.mkdir(parents=True, exist_ok=True)
    stdout_log = out_dir / f"{label}.jsonl"
    stderr_log = out_dir / f"{label}.stderr.log"
    proc = subprocess.Popen(
        _pi_base_cmd(),
        cwd=str(root),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_log.open("w"),
        text=True,
        bufsize=1,
    )
    assert proc.stdin and proc.stdout
    proc.stdin.write(json.dumps({"id": label, "type": "prompt", "message": prompt}) + "\n")
    proc.stdin.flush()

    deadline = time.monotonic() + timeout
    last_agent_end: dict[str, Any] | None = None
    with stdout_log.open("w") as log:
        while True:
            if time.monotonic() > deadline:
                proc.kill()
                raise TimeoutError(f"{label} timed out after {timeout}s; see {stdout_log} and {stderr_log}")
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.05)
                continue
            log.write(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "response" and event.get("success") is False:
                proc.kill()
                raise RuntimeError(f"{label} RPC prompt failed: {event.get('error')}")
            if event.get("type") == "agent_end":
                last_agent_end = event
                break

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()

    if not last_agent_end:
        raise RuntimeError(f"{label} produced no agent_end; see {stdout_log} and {stderr_log}")
    assistants = [m for m in last_agent_end.get("messages", []) if m.get("role") == "assistant"]
    if not assistants:
        raise RuntimeError(f"{label} produced no assistant response; see {stdout_log}")
    raw = _extract_text(assistants[-1])
    (out_dir / f"{label}.final.txt").write_text(raw)
    return _parse_json_from_text(raw)


def _wave1_prompt(root: Path, job: dict[str, Any]) -> str:
    return f"""Project root: {root}
You are the {job['agent']} worker for Archie deep-scan.
Use the project root as cwd. Read AGENTS.md if it exists, then read:
- .archie/scan.json
- .archie/skeletons.json
- {job['prompt_path']}

Focus only on: {job['focus']}.
Return ONLY valid JSON, no markdown fences, with keys:
agent, focus, cwd, saw_agents_md, summary, findings.
Set agent={job['agent']!r}, focus={job['focus']!r}, cwd to your observed cwd,
and saw_agents_md true only if you actually read AGENTS.md.
"""


def _wave2_prompt(root: Path, job: dict[str, Any], wave1_path: Path) -> str:
    keys = ", ".join(REQUIRED_BLUEPRINT_KEYS)
    return f"""Project root: {root}
You are the Archie Wave-2 reasoning worker.
Read AGENTS.md if it exists, .archie/scan.json, .archie/skeletons.json,
{wave1_path}, and {job['prompt_path']}.

Synthesize a complete Archie blueprint. Return ONLY valid JSON, no markdown
fences, with these top-level keys: {keys}.
Save nothing yourself; the orchestrator writes .archie/blueprint.json.
"""


def _write_wave1_csv(results: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["agent", "focus", "cwd", "saw_agents_md", "summary", "findings"])
        writer.writeheader()
        for row in results:
            writer.writerow({
                "agent": row.get("agent", ""),
                "focus": row.get("focus", ""),
                "cwd": row.get("cwd", ""),
                "saw_agents_md": row.get("saw_agents_md", False),
                "summary": row.get("summary", ""),
                "findings": json.dumps(row.get("findings", []), ensure_ascii=False),
            })


def run(root: Path, timeout: int = DEFAULT_TIMEOUT) -> int:
    root = root.resolve()
    archie = root / ".archie"
    for name in ("scanner.py", "renderer.py", "validate.py"):
        if not (archie / name).exists():
            raise FileNotFoundError(f"Missing .archie/{name}; run npx @bitraptors/archie first")

    jobs = _load_jobs(root)
    out_dir = archie / "pi_rpc_deep_scan"
    out_dir.mkdir(parents=True, exist_ok=True)

    _run([sys.executable, str(archie / "scanner.py"), str(root)], root)

    wave1_jobs = list(jobs.get("wave1", []))
    max_workers = max(1, min(int(jobs.get("max_concurrency", 4)), len(wave1_jobs) or 1))
    results_by_agent: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {
            pool.submit(_rpc_prompt, root, _wave1_prompt(root, job), job["agent"], out_dir, timeout): job
            for job in wave1_jobs
        }
        for fut in as_completed(futs):
            job = futs[fut]
            result = fut.result()
            if not isinstance(result, dict):
                raise TypeError(f"{job['agent']} returned {type(result).__name__}, expected object")
            results_by_agent[job["agent"]] = result

    wave1_results = [results_by_agent[j["agent"]] for j in wave1_jobs]
    wave1_json = Path("/tmp/archie_wave1_results.json")
    wave1_csv = Path("/tmp/archie_wave1_results.csv")
    wave1_json.write_text(json.dumps(wave1_results, indent=2, ensure_ascii=False))
    _write_wave1_csv(wave1_results, wave1_csv)
    (out_dir / "archie_wave1_results.json").write_text(wave1_json.read_text())

    blueprint = _rpc_prompt(root, _wave2_prompt(root, jobs["wave2"], wave1_json), "archie-wave2-reasoning", out_dir, timeout)
    if not isinstance(blueprint, dict):
        raise TypeError("Wave 2 returned non-object blueprint")
    missing = [k for k in REQUIRED_BLUEPRINT_KEYS if k not in blueprint]
    if missing:
        raise ValueError(f"Wave 2 blueprint missing keys: {missing}")
    (archie / "blueprint.json").write_text(json.dumps(blueprint, indent=2, ensure_ascii=False) + "\n")

    _run([sys.executable, str(archie / "renderer.py"), str(root)], root)
    _run([sys.executable, str(archie / "validate.py"), "all", str(root)], root)
    print(f"Pi RPC deep-scan completed: {len(wave1_results)} Wave-1 jobs at concurrency {max_workers}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args()
    try:
        return run(args.project_root, args.timeout)
    except Exception as exc:
        print(f"[archie/pi-rpc] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
