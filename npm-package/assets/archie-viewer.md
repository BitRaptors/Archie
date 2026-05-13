# Archie Viewer — Blueprint Inspector

Open the blueprint viewer in your browser to inspect generated artifacts.

**Prerequisites:** Requires `.archie/viewer.py` and a built `.archie/viewer/dist/`. If either is missing, tell the user to run `npx @bitraptors/archie` first.

The viewer renders the same React UI the share flow uses (`archie-viewer.vercel.app`). It works against whatever data exists — even after just `/archie-scan`, you'll see health scores, findings, rules, and the architecture diagram. Sections that need deep-scan data (full component graph, decision chain) render sparse.

## Update notice (run before launch, silent unless action needed)

```bash
python3 .archie/update_check.py check 2>/dev/null
```

If output is non-empty:
- `UPGRADE_AVAILABLE old new` → mention once: `"Archie {new} is available (installed: {old}). Upgrade: npx @bitraptors/archie@latest \"$PWD\""`. Continue.
- `JUST_UPGRADED old new` → say `"Archie upgraded {old} → {new}."` once, then continue.

## Launch

```bash
python3 .archie/viewer.py "$PWD"
```

The viewer auto-opens in your default browser at `http://localhost:5847/local`. Press Ctrl+C to stop.

Optional flags: `--no-open` (suppress browser), `--api-only` (JSON endpoint only, for contributors running `vite dev` separately).

## Telemetry (run after the viewer command returns, silent if opted out)

```bash
python3 .archie/telemetry_sync.py record-event --command viewer --outcome success --project-root "$PWD" 2>/dev/null || true
```
