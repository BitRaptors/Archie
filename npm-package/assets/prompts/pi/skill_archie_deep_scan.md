---
name: archie-deep-scan
description: Pi-native sequential deep scan for Archie. Runs scanner, four Wave-1 passes locally in sequence, then synthesizes and renders the blueprint.
---

# Archie Deep Scan For Pi

Run Archie’s deep scan end to end from Pi. Prefer the installed RPC-parallel adapter because Archie’s Wave-1 fan-out is performance-critical. The adapter is transparent to the rest of Archie: it runs the same scanner / renderer / validator pipeline and reads its job graph from `.archie/prompts/pi/deep_scan_jobs.json` plus the Wave prompts installed under `.archie/prompts/pi/`. If the adapter fails, use the sequential fallback below.

## Preconditions

- If `.archie/scanner.py`, `.archie/renderer.py`, or `.archie/validate.py` is missing, stop and tell the user to run `npx @bitraptors/archie "$PWD"` first.
- Use the repository root as the working directory for every shell command.
- Read `AGENTS.md` first if it exists. Treat it as required architectural context.

## Fast path: RPC-parallel Wave 1 with automatic fallback

First run this guard block exactly. It attempts the RPC-parallel adapter, enforces a full-scan timeout (`ARCHIE_PI_RPC_TIMEOUT`, default 1200s), detects early hangs when the adapter produces no output for 60s, validates `.archie/blueprint.json`, deletes partial output on failure, and writes `/tmp/archie_pi_deep_scan_status.json`.

```bash
python3 - <<'PY'
import json, os, subprocess, sys, time
from pathlib import Path

REQUIRED_BLUEPRINT_KEYS = [
    "meta", "architecture_rules", "decisions", "components", "communication",
    "quick_reference", "technology", "deployment", "frontend", "pitfalls",
    "implementation_guidelines", "development_rules", "architecture_diagram",
]
root = Path.cwd()
status_path = Path("/tmp/archie_pi_deep_scan_status.json")
log_path = Path("/tmp/archie_pi_parallel_deep_scan.log")
blueprint = root / ".archie" / "blueprint.json"
started = time.time()
full_timeout = int(os.environ.get("ARCHIE_PI_RPC_TIMEOUT", "1200"))
first_output_timeout = 60
reason = "unknown"

def fail(msg):
    global reason
    reason = str(msg).replace("\n", " ")[:240]
    try:
        if blueprint.exists():
            blueprint.unlink()
    except OSError:
        pass
    status_path.write_text(json.dumps({
        "path": "sequential",
        "parallel_ok": False,
        "reason": reason,
        "elapsed": round(time.time() - started, 2),
        "log": str(log_path),
    }))
    return 0

try:
    with log_path.open("w") as log:
        proc = subprocess.Popen(
            [sys.executable, ".archie/pi_parallel_deep_scan.py", str(root)],
            cwd=str(root), stdout=log, stderr=subprocess.STDOUT, text=True,
        )
        first_output_deadline = time.time() + first_output_timeout
        deadline = time.time() + full_timeout
        saw_output = False
        while proc.poll() is None:
            if log_path.exists() and log_path.stat().st_size > 0:
                saw_output = True
            now = time.time()
            if not saw_output and now > first_output_deadline:
                proc.kill(); proc.wait(timeout=5)
                raise TimeoutError(f"parallel adapter produced no output within {first_output_timeout}s")
            if now > deadline:
                proc.kill(); proc.wait(timeout=5)
                raise TimeoutError(f"parallel adapter exceeded {full_timeout}s")
            time.sleep(1)
        if proc.returncode != 0:
            raise RuntimeError(f"parallel adapter exited {proc.returncode}; see {log_path}")
    if not blueprint.exists():
        raise FileNotFoundError("parallel adapter exited 0 but .archie/blueprint.json is missing")
    try:
        data = json.loads(blueprint.read_text())
    except Exception as exc:
        raise ValueError(f"parallel adapter wrote malformed blueprint: {exc}")
    missing = [k for k in REQUIRED_BLUEPRINT_KEYS if k not in data]
    if missing:
        raise ValueError(f"parallel adapter blueprint missing keys: {missing}")
    status_path.write_text(json.dumps({
        "path": "parallel",
        "parallel_ok": True,
        "reason": "",
        "elapsed": round(time.time() - started, 2),
        "log": str(log_path),
    }))
except Exception as exc:
    fail(exc)
PY
```

Then inspect the status:

```bash
python3 - <<'PY'
import json
print(json.load(open('/tmp/archie_pi_deep_scan_status.json'))['path'])
PY
```

If it prints `parallel`, skip the sequential fallback and finish with the diagnostic line `deep-scan completed via parallel adapter in Xs`, using the `elapsed` value from `/tmp/archie_pi_deep_scan_status.json`.

If it prints `sequential`, continue immediately with the sequential fallback below. Do not stop and do not ask the user for a flag. At the end, include the diagnostic line `deep-scan completed via sequential fallback in Xs (parallel adapter failed: <one-line reason>)`, using the `reason` value from `/tmp/archie_pi_deep_scan_status.json`.

Optional tuning:

- Set `ARCHIE_PI_RPC_ARGS` to pass model/provider flags to child Pi workers, for example `ARCHIE_PI_RPC_ARGS="--provider anthropic --model sonnet"`.
- Set `ARCHIE_PI_RPC_TIMEOUT` to increase the full adapter timeout seconds.
- Edit `.archie/prompts/pi/deep_scan_jobs.json` when the Wave job list changes; prompt wording changes usually only require editing the referenced prompt files.

## Sequential fallback

### Step 1: Run the deterministic scanner

Run:

```bash
python3 .archie/scanner.py "$PWD" >/tmp/archie_deep_scan_stdout.json
```

This must leave `.archie/scan.json` and `.archie/skeletons.json` in place.

### Step 2: Load shared inputs

Read:

- `AGENTS.md` if it exists
- `.archie/scan.json`
- `.archie/skeletons.json`
- `.archie/prompts/pi/wave1_structure.md`
- `.archie/prompts/pi/wave1_patterns.md`
- `.archie/prompts/pi/wave1_technology.md`
- `.archie/prompts/pi/wave1_ui.md`
- `.archie/prompts/pi/wave2_reasoning.md`

The Wave prompt files are Pi-owned copies so Pi deep-scan stays independent from Codex prompt routing.

### Step 3: Run Wave 1 sequentially

Perform exactly four local analysis passes, in this order:

1. `archie-wave1-structure` — components, layers, file placement. Follow `.archie/prompts/pi/wave1_structure.md`.
2. `archie-wave1-patterns` — communication, design patterns, integrations. Follow `.archie/prompts/pi/wave1_patterns.md`.
3. `archie-wave1-technology` — stack, deployment, development rules. Follow `.archie/prompts/pi/wave1_technology.md`.
4. `archie-wave1-ui` — UI components, state, routing, only if the scanner indicates a meaningful frontend/UI surface; otherwise record a skipped UI pass with the reason. Follow `.archie/prompts/pi/wave1_ui.md` when applicable.

For each pass, write a JSON object with keys:

- `agent`
- `focus`
- `cwd`
- `saw_agents_md`
- `summary`
- `findings`

Set `cwd` to the project root. Set `saw_agents_md` to true only if you actually read `AGENTS.md`.

Save the four objects as a JSON array to `/tmp/archie_wave1_results.json`. Also write `/tmp/archie_wave1_results.csv` with equivalent columns for compatibility with the Codex workflow notes.

### Step 4: Wave 2 synthesis

Read `/tmp/archie_wave1_results.json`, scanner outputs, `AGENTS.md` if present, and `.archie/prompts/pi/wave2_reasoning.md`. Perform the reasoning pass locally and produce a structurally complete Archie blueprint JSON containing:

- `meta`
- `architecture_rules`
- `decisions`
- `components`
- `communication`
- `quick_reference`
- `technology`
- `deployment`
- `frontend`
- `pitfalls`
- `implementation_guidelines`
- `development_rules`
- `architecture_diagram`

Save the returned JSON to `.archie/blueprint.json`. The result should be structurally equivalent to Claude/Codex deep-scan output; only wall-clock time should differ.

### Step 5: Render and validate

Run:

```bash
python3 .archie/renderer.py "$PWD"
python3 .archie/validate.py all "$PWD"
```

If validation fails, report the failing validator and the error output.

## Completion

Your final response must include:

- whether the run completed via RPC-parallel adapter or sequential fallback
- if sequential fallback ran: whether each pass reported `saw_agents_md = true`
- if sequential fallback ran: whether the pass `cwd` values matched the project root
- whether render and validation completed successfully
- the one-line diagnostic: `deep-scan completed via parallel adapter in Xs` or `deep-scan completed via sequential fallback in Xs (parallel adapter failed: <one-line reason>)`
