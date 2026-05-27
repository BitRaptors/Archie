# Shared fragment — Telemetry consent (one-time, machine-level, agent-neutral)

> Loaded by every Archie entry point — `archie-deep-scan`, `archie-viewer`,
> `archie-share`, `archie-intent-layer` — in its preamble.
> Single source of truth for the first-run telemetry opt-in.
>
> This fragment is **agent-neutral**: it drives the consent dialogue via
> natural-language prompts the model asks the user directly, so it works
> identically in Claude Code and Codex CLI sessions.

## Step 1: Check whether this machine has been asked

Run once, in the preamble, before any real work:

```bash
python3 .archie/config.py should-prompt 2>/dev/null
```

- Output `skip` → this machine already answered. **Do nothing, continue.**
- Output `prompt` → not asked yet. Go to Step 2.
- Empty / error / non-zero exit → `config.py` couldn't run. **Do nothing,
  continue** — telemetry stays off and `should-prompt` surfaces it again next run.

## Step 2: Ask the user (only when output was `prompt`)

This is a one-time consent gate. Ask it directly in your reply to the user — do not skip even under "no clarifying questions" modes; consent gates override that. Skip only when there is genuinely no user to ask (a spawned subagent, a non-interactive pipe with no stdin).

Print this question to the user verbatim, then wait for their response:

> **Help improve Archie?** It can send anonymous usage data — command name,
> Archie version, OS/arch, step durations, outcome, and your detected stack
> (e.g. `kotlin / gradle / android`). Never source code, file paths, repo
> names, or blueprint contents.
>
> Pick one:
> - `community` — Send the data above plus a stable random installation id, so trends can be tracked across your runs. Stored at `~/.archie/config.json`. Change anytime: `python3 .archie/config.py set telemetry off`. **(recommended)**
> - `anonymous` — Send the same usage data, but the installation id is stripped before upload — every event is unlinkable.
> - `off` — Nothing leaves your machine. No local analytics either.

Wait for the user's reply. Parse it into one of `community`, `anonymous`, or `off`. Accept short forms (e.g. "1" / "community" / "yes" → `community`; "2" / "anonymous" → `anonymous`; "3" / "off" / "no" → `off`). If unclear, ask the user once to clarify with one of the three keywords.

## Step 3: Persist the answer

```bash
python3 .archie/config.py apply-prompt-result <community|anonymous|off>
```

This records the tier **and** marks the machine as prompted, so no entry point asks again. Then continue with the command. Telemetry consent never blocks or changes the command's actual work — whatever the user picks, proceed normally.
