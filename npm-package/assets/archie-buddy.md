# Archie Buddy

Show the Archie ghost buddy — a sarcastic tamagotchi that reflects your architecture health.

## Run

```bash
python3 .archie/buddy.py "$PROJECT_ROOT"
```

Display the output as-is (it contains ASCII art). The buddy calculates HP from:
- Blueprint existence (30 pts)
- Scan freshness (0-40 pts)
- Violation count (0-30 pts)

If `.archie/buddy.py` doesn't exist, tell the user to run `npx @bitraptors/archie` first.
