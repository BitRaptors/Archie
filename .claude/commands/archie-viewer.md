# Archie Viewer — Blueprint Inspector

Open the blueprint viewer in your browser to inspect all generated artifacts.

**Prerequisites:** Requires `.archie/viewer.py`. If it doesn't exist, tell the user to run `npx archie` first.

The viewer works with whatever data exists — it does NOT require a deep scan. After just `/archie-scan`, it shows health scores, scan reports, rules, and the dependency graph. Tabs that need deep scan data (Blueprint, Files) show what's available and what needs `/archie-deep-scan`.

## Launch

```bash
python3 .archie/viewer.py "$PWD"
```

The viewer opens automatically in your default browser. Press Ctrl+C to stop.
