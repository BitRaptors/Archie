# Handoff to the Pi agent — Archie PiConnector

**Target branch:** `feature/agent_connectors`
**Your tasks:** Stage 4 (#15) + Stage 5 (#16) in TaskList — `PiConnector` (commands only first, then TS extension for in-session hooks).
**Design spec:** `docs/plans/2026-05-18-multi-agent-connector-architecture.md` — this is the contract. Read §9.3 (PiConnector responsibilities), §10 (the canonical TS extension), §17 (Q-P1..Q-P5 open questions), §14 Stages 4-5 (acceptance gates).

## What is already done

- Connector framework: `archie/connectors/base.py`, `archie/manifest.py`, `archie/manifest_data.py`.
- Install loop: `archie/install.py` — iterates `ALL_CONNECTORS`. Just register yourself in `archie/connectors/__init__.py::ALL_CONNECTORS`.
- Canonical hook scripts (shared with Claude/Codex): `archie/assets/hook_scripts/*.sh`. Your TS extension shells out to these.
- ClaudeConnector reference at `archie/connectors/claude.py` (same shape).
- Codex agent may have landed CodexConnector by the time you start — your connector can inherit `install_command` from it (both Pi and Codex read `.agents/skills/*/SKILL.md`).

## Your deliverables

### Stage 4: `archie/connectors/pi.py` (commands only)

```python
class PiConnector(CodexConnector):
    name = "pi"
    capabilities = frozenset({
        "commands",
        "hooks:pre-commit",
    })

    def home_dir(self):
        return Path.home() / ".pi" / "agent"

    def install_hook(self, project_root, hook):
        return  # no shell-hook contract; pre-commit handled universally

    def patch_config(self, patches):
        return
```

`install_command` inherits from `CodexConnector` verbatim (both write `.agents/skills/<name>/SKILL.md` — verified by probe).

If `CodexConnector` hasn't landed yet, inherit directly from `Connector` and implement `install_command` yourself with the same body as Codex's expected version (see HANDOFF_CODEX.md §1).

**Acceptance (Stage 4):**
- Fresh project with Pi installed. `npx @bitraptors/archie .` writes `.agents/skills/archie-*/SKILL.md`.
- `/skill:archie-scan` in Pi runs end-to-end. Same AGENTS.md output as Claude/Codex.
- Deep-scan runs Wave-1 sequentially (Pi has no sub-agents). Document wall-clock vs Codex parallel.

**Resolve Q-P5:** measure sequential Wave-1 time on a real fixture (BabyWeather.Android per memory). If sequential is > 5× Codex parallel, flag for the Stage 5b spike (RPC parallel adapter via `pi --mode rpc`).

### Stage 5: TS extension for in-session enforcement

Expand `PiConnector.capabilities` to include `"hooks:pre-tool-use"`. Add:

```python
def __init__(self):
    self._pending_hooks: list[HookDef] = []

def install_hook(self, project_root, hook):
    if not self.supports_event(hook.event):
        return
    self._pending_hooks.append(hook)

def finalize(self, project_root):
    if not self._pending_hooks:
        return
    template = (ASSETS_ROOT / "pi_extension" / "archie-hooks.ts.template").read_text()
    hooks_json = json.dumps([asdict(h) for h in self._pending_hooks], indent=2)
    rendered = template.replace("{{HOOKS_JSON}}", hooks_json)
    dest = project_root / ".pi" / "extensions" / "archie-hooks.ts"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(rendered)
    # If Pi expects an extension manifest, also copy package.json.
    pkg_src = ASSETS_ROOT / "pi_extension" / "package.json"
    if pkg_src.exists():
        shutil.copy(pkg_src, dest.parent / "package.json")
```

### TS template content (write to `archie/assets/pi_extension/archie-hooks.ts.template`)

The canonical template body — copy verbatim from §10 of the design doc:

```typescript
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { spawnSync } from "node:child_process";

const HOOKS: Array<{
  event: string;
  tool_match: string | null;
  script_path: string;
  blocking: boolean;
}> = {{HOOKS_JSON}};

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event, ctx) => {
    for (const h of HOOKS) {
      if (h.event !== "pre-tool-use") continue;
      if (h.tool_match && !new RegExp(h.tool_match).test(event.tool_name)) continue;

      const res = spawnSync("bash", [h.script_path], {
        input: JSON.stringify({
          tool_name: event.tool_name,
          tool_input: event.tool_input,
          cwd: ctx.cwd,
          session_id: ctx.session_id,
          hook_event_name: "PreToolUse",
        }),
        encoding: "utf8",
        cwd: ctx.cwd,
        timeout: 30_000,
      });

      if (h.blocking && (res.status === 2 || res.status === 1)) {
        return {
          decision: "deny",
          reason: res.stderr?.trim() || "Archie hook blocked this action.",
        };
      }
    }
  });
}
```

**Key design point:** the TS extension is GLUE. All validation lives in `archie/assets/hook_scripts/pre-validate.sh` (already extracted). Pi's TS code just routes Pi's `tool_call` event to the existing shell script. Updates to validation rules touch zero Pi files.

### Resolve Q-P1..Q-P4 during Stage 5

These need Pi-specific local knowledge that probes couldn't resolve:

- **Q-P1**: Does Pi auto-discover `.pi/extensions/*.ts` on session start, or does the user need to run `pi install /path/to/extension`? Read Pi's extension loader source at https://github.com/earendil-works/pi/tree/main/packages/coding-agent or test directly. If `pi install` is required, the install loop's final output must print the one-line instruction.
- **Q-P2**: Pi docs document `pi.on("tool_call", ...)` — does Pi also expose `pi.on("post_tool_call", ...)`, `pi.on("prompt_submit", ...)`, `pi.on("stop", ...)`? Each additional event = one more capability you can declare. Read the `ExtensionAPI` type definition.
- **Q-P3**: Does Pi resolve `@earendil-works/pi-coding-agent` from its global install, or does our extension need a local `node_modules` (which means we need to ship `package.json` and the user needs `npm install` after install)? Test in a clean Pi session.
- **Q-P4**: Does `pi.on("tool_call", ...)` support async returns (an `async` handler that resolves to a denial), or does the denial need to be synchronous? Affects whether `spawnSync` is the right call or whether we should use `spawn` with await.

Document your findings in the commit messages for Stage 5.

### Stage 5 acceptance gate

- Edit a forbidden file in Pi → TS extension intercepts, runs `.archie/hooks/pre-validate.sh`, denies the edit with the hook's reason message.
- Allowed edit goes through with < 50ms overhead.
- `pi list` in an installed project shows `archie-hooks` as a loaded extension.
- `archie/connectors/pi.py` is < 50 lines of Python (the constraint that gates the design).

## What you can drop without it being a problem

Per the design (and Gabor's explicit approval): Pi can have FEWER features than Claude/Codex. The unsupported events are:

- `hooks:post-tool-use` — Pi's extension API has no documented post-tool event
- `hooks:user-prompt-submit` — same, no documented event
- `hooks:stop` — same
- `parallel-agents` — Pi explicitly has no sub-agents

These are declared by NOT including them in `capabilities`. The install loop respects the declaration and skips those hook entries. No "stub method that does nothing" needed — the base class default raises NotImplementedError, and the loop filters via `supports_event` before calling.

If Q-P2 reveals that Pi DOES support more events, simply add them to `capabilities` and extend the TS template's handler list. Zero other code changes.

## Validation findings

Validated on Pi CLI 0.75.3 (`/opt/homebrew/bin/pi`) on 2026-05-18.

### Q-P1 — extension discovery

Pi auto-discovers project-local extensions from `<project>/.pi/extensions/*.ts`. Evidence: `discoverAndLoadExtensions([], cwd)` loaded `/private/tmp/pi-validation/.pi/extensions/archie-hooks.ts` with no errors and registered `tool_call`; `pi list` only reports settings-installed packages and remains `No packages installed`, so it is not the right signal for project-local auto-discovery. No `pi install` step is required.

### Q-P2 — lifecycle event ceiling

The installed `ExtensionAPI` type exposes many events, including `tool_call`, `tool_result`, `before_agent_start`, `input`, `agent_end`, session events, turn/message events, and model events. Archie now claims the Pi events that map cleanly to its hook scripts: `hooks:pre-tool-use` via `tool_call`, `hooks:post-tool-use` via `tool_result`, `hooks:user-prompt-submit` via `input`, and `hooks:stop` via `agent_end`. `agent_end` is the closest semantic match for Claude/Codex Stop in Archie's use case: run a non-blocking cleanup/finalization hook after an agent turn finishes.

### Q-P3 — module resolution

No local `node_modules` is required. Pi's extension loader provides `@earendil-works/pi-coding-agent` as a bundled alias/virtual module; loading the rendered Archie extension from `.pi/extensions/archie-hooks.ts` succeeded with only the copied `package.json` present.

### Q-P4 — handler returns and denial shape

`tool_call` handlers may be synchronous or async; Pi awaits handler results. The working denial shape is `{ block: true, reason }`, not Claude-style `{ decision: "deny" }`. The Archie template uses `spawnSync` and returns synchronously on the blocking path. Real-session evidence: in `/tmp/pi-validation`, a blocking rule on `forbidden/**` caused `pi --mode json --tools write --print ...` to emit a `tool_execution_end` with `isError: true` and the Archie BLOCKED reason, and `forbidden/test.txt` was not created. An allowed write to `allowed.txt` succeeded. Follow-up audit corrected the earlier ceiling: Pi hooks are real extension events, not absent; Archie maps pre-tool, post-tool, user-prompt, and stop hooks to Pi-native events.

### Event firing evidence — tool_result / input / agent_end

Validated on Pi CLI 0.75.3 in `/tmp/pi-event-evidence` with a fresh Archie install and temporary tracers added only to the installed test-project hook scripts. The rendered Pi extension loaded handlers `tool_call`, `tool_result`, `input`, and `agent_end`.

- `input` / user-prompt-submit parity: before running `pi --offline --mode json --tools write --print "Use the write tool to create evidence.txt with content ok"`, a `/tmp/.archie_turn_$HASH` marker was created. The trace line was `1779177628 FIRED: pre-turn.sh hook_event_name=UserPromptSubmit prompt=Use the write tool to create evidence.txt with content ok marker_exists_after=no`; the marker was absent after the run, confirming the canonical pre-turn cleanup semantics fired at prompt submission.
- `tool_result` / post-tool-use parity: the same run created `evidence.txt`, and the trace line was `1779177630 FIRED: post-lint.sh hook_event_name=PostToolUse tool_name=Write is_error=False`. The Pi JSON stream also contained `tool_execution_end` for `write` with `Successfully wrote 2 bytes to evidence.txt`, confirming the post-tool hook fired after a successful tool result.
- `agent_end` / stop parity: after the turn completed, the trace line was `1779177632 FIRED: stop.sh hook_event_name=Stop message_count=4`; the Pi JSON stream contained the final `agent_end` event for the same run. This validates Pi's `agent_end` mapping as Archie's non-blocking Stop hook equivalent.

### Q-P5 — sequential deep-scan wall-clock

Attempted on `/tmp/BabyWeather.Android.pi` (rsync copy of `BabyWeather.Android`) after a fresh Archie install. The first run with the configured OpenAI Codex provider failed after 18.89s with `usage_limit_reached` (429; primary usage 100%). A fallback run with `google/gemini-2.5-flash` failed because the available Google key was invalid for the Generative Language API. No trustworthy Pi-vs-Codex wall-clock ratio was produced in that session. Follow-up work added `.archie/pi_parallel_deep_scan.py`, a transparent RPC-parallel adapter that runs Wave 1 through child `pi --mode rpc --no-session` workers using the declarative job graph at `.archie/prompts/pi/deep_scan_jobs.json`, then writes the standard `.archie/blueprint.json` and runs renderer/validator. It was validated with a fake Pi RPC binary for orchestration and install packaging; real wall-clock benchmarking still needs provider quota.

## Workflow

1. `git checkout feature/agent_connectors && git pull`
2. **Stage 4 first**: implement `archie/connectors/pi.py` with commands-only. Register in `ALL_CONNECTORS`. Test.
3. **Stage 5 next**: write `archie/assets/pi_extension/archie-hooks.ts.template`. Extend `PiConnector` with `install_hook` accumulator + `finalize`. Test.
4. Validate Q-P1..Q-P5 in real Pi sessions. Document findings in commit messages.
5. Push to `feature/agent_connectors`. Do not merge to `main`.

## Hard constraints

- No edits outside `archie/connectors/pi.py`, `archie/assets/pi_extension/`, `archie/connectors/__init__.py`. Do not touch ClaudeConnector or CodexConnector unless coordinating.
- TS extension is glue only. NEVER write validation logic in TypeScript — call `.archie/hooks/*.sh`.
- Honor your `capabilities` set: if you declare `hooks:pre-tool-use`, your finalize must produce a working TS extension that wires it. If you don't declare an event, don't fake supporting it.
- Pi-specific Python code (`archie/connectors/pi.py`) under 50 lines. If it grows, you're putting logic in the wrong place.
