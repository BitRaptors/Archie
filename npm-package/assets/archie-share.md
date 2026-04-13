# Archie Share — Upload Blueprint for Sharing

Share your architecture blueprint via a URL. Useful for showing teammates, stakeholders, or clients an analysis of your codebase without needing them to install anything.

**Prerequisites:** Requires `.archie/blueprint.json`. Run `/archie-scan` (or `/archie-deep-scan`) first if it doesn't exist.

## Run

```bash
python3 .archie/upload.py "$PWD"
```

On success, the script prints a shareable URL. Share this URL with anyone who wants to see the architecture analysis — they get a read-only view of the blueprint, health scores, rules, and architecture diagram.

If the upload fails (network issues, server down), your local blueprint is unaffected. Try again later.
