# Archie Buddy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a pimasz ASCII ghost tamagotchi to Archie that reflects architecture health and appears after every Archie command.

**Architecture:** A single standalone Python script (`buddy.py`) calculates HP from `.archie/` data (blueprint existence, scan freshness, violation count), maps to mood, renders ASCII art with sarcastic commentary, and persists streak/achievement state to `.archie/buddy.json`. A slash command (`/archie-buddy`) shows the full view; existing commands call `--compact` for a one-liner.

**Tech Stack:** Python 3.9+ stdlib only (json, datetime, pathlib, os, random, time)

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `archie/standalone/buddy.py` | CREATE | All buddy logic: HP calc, mood, ASCII render, state, achievements |
| `tests/test_buddy.py` | CREATE | Unit tests for HP calc, mood mapping, state persistence, ASCII output |
| `.claude/commands/archie-buddy.md` | CREATE | Slash command for full buddy view |
| `.claude/commands/archie-scan.md` | MODIFY | Add compact buddy call at end (line ~479) |
| `.claude/commands/archie-deep-scan.md` | MODIFY | Add compact buddy call at end (line ~1213) |
| `.claude/commands/archie-viewer.md` | MODIFY | Add compact buddy call before viewer launch |
| `npm-package/assets/buddy.py` | CREATE | Sync copy of standalone/buddy.py |
| `npm-package/assets/archie-buddy.md` | CREATE | Sync copy of commands/archie-buddy.md |
| `npm-package/bin/archie.mjs` | MODIFY | Add buddy.py + archie-buddy.md to copy lists |

---

### Task 1: HP Calculation — Tests

**Files:**
- Create: `tests/test_buddy.py`

- [ ] **Step 1: Write failing tests for `calculate_hp`**

```python
"""Tests for archie buddy."""
from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "archie" / "standalone"))
import buddy


def _make_archie_dir(tmp: Path, *, blueprint: bool = True, scan_age_hours: float = 0,
                     violations: int = 0) -> Path:
    """Create a minimal .archie/ directory for testing."""
    archie = tmp / ".archie"
    archie.mkdir(exist_ok=True)
    if blueprint:
        (archie / "blueprint.json").write_text(json.dumps({"meta": {"version": 1}}))
    if scan_age_hours >= 0:
        report = archie / "scan_report.md"
        report.write_text(f"# Scan Report\nViolations found: {violations}\n")
        # Backdate the file modification time
        age_seconds = scan_age_hours * 3600
        mtime = time.time() - age_seconds
        import os
        os.utime(report, (mtime, mtime))
    return tmp


def test_hp_full_health():
    """Blueprint exists, fresh scan, 0 violations → 100 HP."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=0, violations=0)
        hp, _ = buddy.calculate_hp(tmp_path)
        assert hp == 100


def test_hp_no_blueprint():
    """No blueprint → 0 HP, unborn mood."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=False, scan_age_hours=-1, violations=0)
        hp, mood = buddy.calculate_hp(tmp_path)
        assert hp == 0
        assert mood == "unborn"


def test_hp_stale_scan():
    """Blueprint exists, scan 8 days old, 0 violations → 30 HP (blueprint only)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=8*24, violations=0)
        hp, _ = buddy.calculate_hp(tmp_path)
        assert hp == 60  # 30 (blueprint) + 0 (stale scan) + 30 (0 violations)


def test_hp_many_violations():
    """Blueprint, fresh scan, 25 violations → 70 HP."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=0, violations=25)
        hp, _ = buddy.calculate_hp(tmp_path)
        assert hp == 70  # 30 (blueprint) + 40 (fresh) + 0 (>20 violations)


def test_hp_medium_state():
    """Blueprint, 2-day scan, 5 violations → moderate HP."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=48, violations=5)
        hp, _ = buddy.calculate_hp(tmp_path)
        assert hp == 60  # 30 (blueprint) + 15 (3-5 day bucket) + 15 (4-7 violations)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'buddy'`

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_buddy.py
git commit -m "test: add failing tests for buddy HP calculation"
```

---

### Task 2: HP Calculation — Implementation

**Files:**
- Create: `archie/standalone/buddy.py`

- [ ] **Step 1: Implement `calculate_hp` function**

```python
#!/usr/bin/env python3
"""Archie Buddy — pimasz ASCII ghost tamagotchi.

Calculates architecture health from .archie/ data, renders ASCII ghost
with mood-specific eyes and sarcastic commentary.

Run:
  python3 buddy.py /path/to/project            # full view
  python3 buddy.py /path/to/project --compact   # one-liner (for scan/deep-scan tail)
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


# ── HP Calculation ────────────────────────────────────────────────────────────

def _blueprint_points(archie_dir: Path) -> int:
    """30 points if blueprint.json exists, else 0."""
    return 30 if (archie_dir / "blueprint.json").exists() else 0


def _scan_freshness_points(archie_dir: Path) -> int:
    """0-40 points based on scan_report.md age."""
    report = archie_dir / "scan_report.md"
    if not report.exists():
        return 0
    age_hours = (time.time() - report.stat().st_mtime) / 3600
    if age_hours < 24:
        return 40
    if age_hours < 72:
        return 30
    if age_hours < 120:
        return 15
    if age_hours < 168:
        return 5
    return 0


def _count_violations(archie_dir: Path) -> int:
    """Extract violation count from scan_report.md."""
    report = archie_dir / "scan_report.md"
    if not report.exists():
        return 0
    text = report.read_text(errors="replace")
    # Look for common violation count patterns in scan reports
    # Pattern: "N violations" or "Violations found: N" or "N findings"
    for pattern in [
        r"[Vv]iolations?\s*(?:found)?:?\s*(\d+)",
        r"(\d+)\s+violations?",
        r"(\d+)\s+findings?",
    ]:
        m = re.search(pattern, text)
        if m:
            return int(m.group(1))
    return 0


def _violation_points(violation_count: int) -> int:
    """0-30 points based on number of violations."""
    if violation_count == 0:
        return 30
    if violation_count <= 3:
        return 25
    if violation_count <= 7:
        return 15
    if violation_count <= 15:
        return 5
    return 0


def calculate_hp(project_root: Path) -> tuple[int, str]:
    """Calculate HP (0-100) and mood from .archie/ data.

    Returns (hp, mood) tuple.
    """
    archie_dir = project_root / ".archie"

    if not archie_dir.exists():
        return 0, "unborn"

    bp = _blueprint_points(archie_dir)
    if bp == 0:
        return 0, "unborn"

    scan = _scan_freshness_points(archie_dir)
    violations = _count_violations(archie_dir)
    viol = _violation_points(violations)
    hp = bp + scan + viol

    if hp >= 80:
        mood = "confident"
    elif hp >= 50:
        mood = "skeptical"
    elif hp >= 20:
        mood = "sick"
    else:
        mood = "dead"

    return hp, mood
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v`
Expected: All 5 tests PASS

- [ ] **Step 3: Commit**

```bash
git add archie/standalone/buddy.py
git commit -m "feat: implement buddy HP calculation from .archie/ data"
```

---

### Task 3: Mood System & Messages — Tests

**Files:**
- Modify: `tests/test_buddy.py`

- [ ] **Step 1: Add mood mapping and message tests**

Append to `tests/test_buddy.py`:

```python
def test_mood_confident():
    assert buddy.mood_from_hp(95) == "confident"
    assert buddy.mood_from_hp(80) == "confident"

def test_mood_skeptical():
    assert buddy.mood_from_hp(79) == "skeptical"
    assert buddy.mood_from_hp(50) == "skeptical"

def test_mood_sick():
    assert buddy.mood_from_hp(49) == "sick"
    assert buddy.mood_from_hp(20) == "sick"

def test_mood_dead():
    assert buddy.mood_from_hp(19) == "dead"
    assert buddy.mood_from_hp(0) == "dead"

def test_get_message_returns_string():
    """Each mood should produce a non-empty string message."""
    for mood in ("confident", "skeptical", "sick", "dead", "unborn"):
        msg = buddy.get_message(mood)
        assert isinstance(msg, str)
        assert len(msg) > 0

def test_eyes_for_mood():
    assert buddy.eyes_for_mood("confident") == ("◕", "◕")
    assert buddy.eyes_for_mood("skeptical") == ("¬", "¬")
    assert buddy.eyes_for_mood("sick") == ("◔", "◔")
    assert buddy.eyes_for_mood("dead") == ("×", "×")
    assert buddy.eyes_for_mood("unborn") == ("·", "·")
```

- [ ] **Step 2: Run tests to verify new ones fail**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v -k "mood or eyes or message"`
Expected: FAIL with `AttributeError: module 'buddy' has no attribute 'mood_from_hp'`

- [ ] **Step 3: Commit test additions**

```bash
git add tests/test_buddy.py
git commit -m "test: add failing tests for mood mapping, eyes, and messages"
```

---

### Task 4: Mood System & Messages — Implementation

**Files:**
- Modify: `archie/standalone/buddy.py`

- [ ] **Step 1: Add mood, eyes, and message functions**

Append to `buddy.py` after `calculate_hp`:

```python
# ── Mood & Personality ────────────────────────────────────────────────────────

def mood_from_hp(hp: int) -> str:
    """Map HP to mood string."""
    if hp >= 80:
        return "confident"
    if hp >= 50:
        return "skeptical"
    if hp >= 20:
        return "sick"
    return "dead"


def eyes_for_mood(mood: str) -> tuple[str, str]:
    """Return (left_eye, right_eye) characters for a mood."""
    return {
        "confident": ("◕", "◕"),
        "skeptical": ("¬", "¬"),
        "sick":      ("◔", "◔"),
        "dead":      ("×", "×"),
        "unborn":    ("·", "·"),
    }.get(mood, ("◉", "◉"))


MESSAGES: dict[str, list[str]] = {
    "confident": [
        "Egy violation sincs. Unatkozom.",
        "Szinte gyanúsan jó ez az architektúra.",
        "Na EZ egy codebase. Majdnem meghatódtam.",
        "Nincs dolgom. Mehetek aludni?",
        "Clean architecture. Kezdek feleslegesnek érezni magam.",
    ],
    "skeptical": [
        "Lassan rohadni kezd ez a codebase. Csak szólok.",
        "Aha, 'majd refaktorálom'. Persze.",
        "Nem akarom tudni mi lesz jövő héten.",
        "Ez még működik, de ne húzd meg az ördög farkát.",
        "Láttam már rosszabbat. De láttam jobbat is.",
    ],
    "sick": [
        "Fizikailag rosszul vagyok ettől a coupling-tól.",
        "Ez a circular dependency az én személyes pokol-köröm.",
        "Segítség. Valaki. Bárki.",
        "Futtass egy scant... ha mersz.",
        "Már a szemem is rángatózik ettől a kódtól.",
    ],
    "dead": [
        "Hivatalosan is halott vagyok. Gratulálok.",
        "Ennél egy /dev/null is jobb architektúra.",
        "A szellem szellemet adott.",
        "RIP Archie. Cause of death: technical debt.",
        "Ha ez production-ben van, akkor részvétem.",
    ],
    "unborn": [
        "Futtass egy /archie-deep-scan-t, hogy megszülessek.",
        "Helló? Van itt valaki? Sötét van.",
        "Még nem létezem. Scannelj és életre kelek!",
    ],
}


def get_message(mood: str) -> str:
    """Return a random sarcastic message for the given mood."""
    messages = MESSAGES.get(mood, MESSAGES["unborn"])
    return random.choice(messages)
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add archie/standalone/buddy.py tests/test_buddy.py
git commit -m "feat: add buddy mood system with sarcastic messages"
```

---

### Task 5: ASCII Rendering — Tests

**Files:**
- Modify: `tests/test_buddy.py`

- [ ] **Step 1: Add ASCII rendering tests**

Append to `tests/test_buddy.py`:

```python
def test_render_full_contains_ghost():
    """Full render should contain the ghost body characters."""
    output = buddy.render_full(hp=75, mood="skeptical", violations=5,
                               scan_age_text="2 napja", streak=3)
    assert "▄███████▄" in output
    assert "▀█▄▀" in output
    assert "¬" in output  # skeptical eyes
    assert "HP:" in output
    assert "75" in output


def test_render_compact_one_block():
    """Compact render should be shorter than full render."""
    full = buddy.render_full(hp=90, mood="confident", violations=0,
                             scan_age_text="ma", streak=1)
    compact = buddy.render_compact(hp=90, mood="confident")
    assert len(compact) < len(full)
    assert "▄███████▄" in compact
    assert "◕" in compact


def test_render_full_unborn():
    """Unborn render shows special message, no HP bar."""
    output = buddy.render_full(hp=0, mood="unborn", violations=0,
                               scan_age_text="soha", streak=0)
    assert "·" in output  # unborn eyes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v -k "render"`
Expected: FAIL with `AttributeError: module 'buddy' has no attribute 'render_full'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_buddy.py
git commit -m "test: add failing tests for ASCII ghost rendering"
```

---

### Task 6: ASCII Rendering — Implementation

**Files:**
- Modify: `archie/standalone/buddy.py`

- [ ] **Step 1: Add render functions**

Append to `buddy.py`:

```python
# ── ASCII Rendering ───────────────────────────────────────────────────────────

def _hp_bar(hp: int, width: int = 10) -> str:
    """Render HP bar like ████████░░."""
    filled = round(hp / 100 * width)
    return "█" * filled + "░" * (width - filled)


def _scan_age_text(archie_dir: Path) -> str:
    """Human-readable scan age."""
    report = archie_dir / "scan_report.md"
    if not report.exists():
        return "soha"
    age_hours = (time.time() - report.stat().st_mtime) / 3600
    if age_hours < 1:
        return "most"
    if age_hours < 24:
        return f"{int(age_hours)}h"
    days = int(age_hours / 24)
    if days == 1:
        return "1 napja"
    return f"{days} napja"


def render_full(hp: int, mood: str, violations: int,
                scan_age_text: str, streak: int) -> str:
    """Render full buddy view with stats and message."""
    left, right = eyes_for_mood(mood)
    msg = get_message(mood)
    bar = _hp_bar(hp)

    if mood == "unborn":
        return (
            f"    ▄███████▄\n"
            f"  ▄█         █▄\n"
            f" █   {left}     {right}   █\n"
            f" █ ╌╌╌╌╌╌╌╌╌╌╌ █\n"
            f" █               █\n"
            f" █ ╌╌╌╌╌╌╌╌╌╌╌ █     Archie Buddy\n"
            f" ▀█▄▀ ▀█▄▀ ▀█▄▀\n"
            f"\n"
            f' "{msg}"'
        )

    return (
        f"    ▄███████▄\n"
        f"  ▄█         █▄\n"
        f" █   {left}     {right}   █     Archie  ♥ HP: {bar} {hp}/100\n"
        f" █ ╌╌╌╌╌╌╌╌╌╌╌ █     Mood: {mood.capitalize()}\n"
        f" █               █     Scan: {scan_age_text}  │  Violations: {violations}\n"
        f" █ ╌╌╌╌╌╌╌╌╌╌╌ █     Streak: {streak} scans\n"
        f" ▀█▄▀ ▀█▄▀ ▀█▄▀\n"
        f"\n"
        f' "{msg}"'
    )


def render_compact(hp: int, mood: str) -> str:
    """Render compact one-block buddy for command tails."""
    left, right = eyes_for_mood(mood)
    msg = get_message(mood)
    bar = _hp_bar(hp)

    if mood == "unborn":
        return (
            f"    ▄███████▄\n"
            f"  ▄█         █▄\n"
            f' █   {left}     {right}   █   "{msg}"\n'
            f" █ ╌╌╌╌╌╌╌╌╌╌╌ █\n"
            f" ▀█▄▀ ▀█▄▀ ▀█▄▀"
        )

    return (
        f"    ▄███████▄\n"
        f"  ▄█         █▄\n"
        f' █   {left}     {right}   █   HP: {bar} {hp}  │  "{msg}"\n'
        f" █ ╌╌╌╌╌╌╌╌╌╌╌ █\n"
        f" ▀█▄▀ ▀█▄▀ ▀█▄▀"
    )
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add archie/standalone/buddy.py
git commit -m "feat: add ASCII ghost rendering with full and compact views"
```

---

### Task 7: State Persistence — Tests

**Files:**
- Modify: `tests/test_buddy.py`

- [ ] **Step 1: Add state persistence tests**

Append to `tests/test_buddy.py`:

```python
def test_load_state_missing_file():
    """Missing buddy.json returns default state."""
    with tempfile.TemporaryDirectory() as tmp:
        state = buddy.load_state(Path(tmp) / ".archie")
        assert state["streak"] == 0
        assert state["total_scans"] == 0
        assert state["best_hp"] == 0
        assert state["achievements"] == []


def test_save_and_load_state():
    """State round-trips through JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        archie = Path(tmp) / ".archie"
        archie.mkdir()
        state = buddy.default_state()
        state["streak"] = 5
        state["best_hp"] = 90
        buddy.save_state(archie, state)

        loaded = buddy.load_state(archie)
        assert loaded["streak"] == 5
        assert loaded["best_hp"] == 90


def test_update_state_tracks_best_hp():
    """update_state should record new best HP."""
    state = buddy.default_state()
    state["best_hp"] = 50
    updated = buddy.update_state(state, hp=80)
    assert updated["best_hp"] == 80


def test_update_state_keeps_best_hp():
    """update_state should not lower best HP."""
    state = buddy.default_state()
    state["best_hp"] = 95
    updated = buddy.update_state(state, hp=60)
    assert updated["best_hp"] == 95


def test_achievement_first_scan():
    """First interaction unlocks first_scan achievement."""
    state = buddy.default_state()
    updated = buddy.update_state(state, hp=50)
    assert "first_scan" in updated["achievements"]


def test_achievement_comeback():
    """HP jumping from <20 to >=80 unlocks comeback."""
    state = buddy.default_state()
    state["last_hp"] = 15
    updated = buddy.update_state(state, hp=85)
    assert "comeback" in updated["achievements"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v -k "state or achievement"`
Expected: FAIL with `AttributeError: module 'buddy' has no attribute 'load_state'`

- [ ] **Step 3: Commit**

```bash
git add tests/test_buddy.py
git commit -m "test: add failing tests for buddy state persistence and achievements"
```

---

### Task 8: State Persistence — Implementation

**Files:**
- Modify: `archie/standalone/buddy.py`

- [ ] **Step 1: Add state management functions**

Append to `buddy.py`:

```python
# ── State Persistence ─────────────────────────────────────────────────────────

def default_state() -> dict:
    """Return a fresh buddy state dict."""
    return {
        "last_interaction": None,
        "last_hp": 0,
        "streak": 0,
        "total_scans": 0,
        "best_hp": 0,
        "achievements": [],
    }


def load_state(archie_dir: Path) -> dict:
    """Load buddy.json or return default state."""
    f = archie_dir / "buddy.json"
    if not f.exists():
        return default_state()
    try:
        data = json.loads(f.read_text(errors="replace"))
        # Merge with defaults for forward-compatibility
        state = default_state()
        state.update(data)
        return state
    except (json.JSONDecodeError, OSError):
        return default_state()


def save_state(archie_dir: Path, state: dict) -> None:
    """Write buddy state to .archie/buddy.json."""
    archie_dir.mkdir(parents=True, exist_ok=True)
    f = archie_dir / "buddy.json"
    f.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def update_state(state: dict, hp: int) -> dict:
    """Update state with current HP, track achievements and streaks."""
    now = datetime.now(timezone.utc).isoformat()

    # First scan achievement
    if state["total_scans"] == 0 and "first_scan" not in state["achievements"]:
        state["achievements"].append("first_scan")

    state["total_scans"] += 1
    state["best_hp"] = max(state["best_hp"], hp)
    state["last_interaction"] = now

    # Comeback achievement
    if state.get("last_hp", 0) < 20 and hp >= 80 and "comeback" not in state["achievements"]:
        state["achievements"].append("comeback")

    # Clean scan achievements
    if hp >= 80:
        state["streak"] += 1
        if state["streak"] >= 3 and "clean_streak_3" not in state["achievements"]:
            state["achievements"].append("clean_streak_3")
        if state["streak"] >= 7 and "clean_streak_7" not in state["achievements"]:
            state["achievements"].append("clean_streak_7")
        if hp == 100 and "first_clean" not in state["achievements"]:
            state["achievements"].append("first_clean")
    else:
        state["streak"] = 0

    state["last_hp"] = hp
    return state
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add archie/standalone/buddy.py
git commit -m "feat: add buddy state persistence with achievements"
```

---

### Task 9: CLI Entry Point — Tests

**Files:**
- Modify: `tests/test_buddy.py`

- [ ] **Step 1: Add CLI integration tests**

Append to `tests/test_buddy.py`:

```python
import subprocess

def test_cli_full_view():
    """Running buddy.py on a project with .archie/ produces full ASCII output."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=0, violations=2)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "archie" / "standalone" / "buddy.py"), str(tmp_path)],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "▄███████▄" in result.stdout
        assert "HP:" in result.stdout
        assert "Mood:" in result.stdout


def test_cli_compact_view():
    """Running buddy.py --compact produces shorter output without Mood: line."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _make_archie_dir(tmp_path, blueprint=True, scan_age_hours=0, violations=0)
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "archie" / "standalone" / "buddy.py"), str(tmp_path), "--compact"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "▄███████▄" in result.stdout
        assert "Mood:" not in result.stdout


def test_cli_no_archie_dir():
    """Running on a project with no .archie/ still returns 0 and shows unborn."""
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "archie" / "standalone" / "buddy.py"), tmp],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "·" in result.stdout  # unborn eyes
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v -k "cli"`
Expected: FAIL (buddy.py has no `main()` or `if __name__` block yet)

- [ ] **Step 3: Commit**

```bash
git add tests/test_buddy.py
git commit -m "test: add failing CLI integration tests for buddy"
```

---

### Task 10: CLI Entry Point — Implementation

**Files:**
- Modify: `archie/standalone/buddy.py`

- [ ] **Step 1: Add main function and CLI entry point**

Append to `buddy.py`:

```python
# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main() -> None:
    """CLI: python3 buddy.py <project_root> [--compact]"""
    if len(sys.argv) < 2:
        print("Usage: python3 buddy.py <project_root> [--compact]", file=sys.stderr)
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    compact = "--compact" in sys.argv

    archie_dir = project_root / ".archie"

    hp, mood = calculate_hp(project_root)
    violations = _count_violations(archie_dir) if archie_dir.exists() else 0
    scan_age = _scan_age_text(archie_dir) if archie_dir.exists() else "soha"

    # Load and update state
    state = load_state(archie_dir)
    state = update_state(state, hp)
    if archie_dir.exists():
        save_state(archie_dir, state)

    if compact:
        print(render_compact(hp, mood))
    else:
        print(render_full(hp, mood, violations, scan_age, state["streak"]))

    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run ALL tests to verify they pass**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/test_buddy.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add archie/standalone/buddy.py
git commit -m "feat: add buddy CLI entry point with full and compact modes"
```

---

### Task 11: Slash Command & Command Integration

**Files:**
- Create: `.claude/commands/archie-buddy.md`
- Modify: `.claude/commands/archie-scan.md` (line ~479)
- Modify: `.claude/commands/archie-deep-scan.md` (line ~1213)
- Modify: `.claude/commands/archie-viewer.md` (line ~15)

- [ ] **Step 1: Create `/archie-buddy` slash command**

Create `.claude/commands/archie-buddy.md`:

```markdown
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
```

- [ ] **Step 2: Add compact buddy to archie-scan.md**

Append to the end of `.claude/commands/archie-scan.md` (after line 479):

```markdown

---

## Buddy

After presenting scan results, show the Archie buddy in compact mode:

```bash
python3 .archie/buddy.py "$PROJECT_ROOT" --compact
```

Include its output at the end of the scan results.
```

- [ ] **Step 3: Add compact buddy to archie-deep-scan.md**

Append to the end of `.claude/commands/archie-deep-scan.md` (after line 1213):

```markdown

---

## Buddy

After the completion message, show the Archie buddy in compact mode:

```bash
python3 .archie/buddy.py "$PROJECT_ROOT" --compact
```

Include its output at the end.
```

- [ ] **Step 4: Add compact buddy to archie-viewer.md**

Append to the end of `.claude/commands/archie-viewer.md` (after line 15):

```markdown

---

## Buddy

Before launching the viewer, show the Archie buddy in compact mode:

```bash
python3 .archie/buddy.py "$PROJECT_ROOT" --compact
```

Include its output, then proceed with the viewer launch.
```

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/archie-buddy.md .claude/commands/archie-scan.md .claude/commands/archie-deep-scan.md .claude/commands/archie-viewer.md
git commit -m "feat: add /archie-buddy command and compact buddy to all Archie commands"
```

---

### Task 12: NPM Package Sync

**Files:**
- Create: `npm-package/assets/buddy.py` (copy of `archie/standalone/buddy.py`)
- Create: `npm-package/assets/archie-buddy.md` (copy of `.claude/commands/archie-buddy.md`)
- Modify: `npm-package/bin/archie.mjs` (line 98 and line 108)

- [ ] **Step 1: Copy buddy.py to assets**

```bash
cp archie/standalone/buddy.py npm-package/assets/buddy.py
```

- [ ] **Step 2: Copy archie-buddy.md to assets**

```bash
cp .claude/commands/archie-buddy.md npm-package/assets/archie-buddy.md
```

- [ ] **Step 3: Add buddy.py to script copy list in archie.mjs**

In `npm-package/bin/archie.mjs` line 108, add `"buddy.py"` to the scripts array:

```javascript
for (const script of ["_common.py", "scanner.py", "refresh.py", "intent_layer.py", "renderer.py", "install_hooks.py", "merge.py", "finalize.py", "validate.py", "viewer.py", "drift.py", "extract_output.py", "arch_review.py", "measure_health.py", "check_rules.py", "detect_cycles.py", "upload.py", "buddy.py"]) {
```

- [ ] **Step 4: Add archie-buddy.md to commands copy list in archie.mjs**

In `npm-package/bin/archie.mjs` line 98, add `"archie-buddy.md"` to the commands array:

```javascript
for (const cmd of ["archie-scan.md", "archie-deep-scan.md", "archie-viewer.md", "archie-share.md", "archie-buddy.md"]) {
```

- [ ] **Step 5: Also sync the modified command files to assets**

```bash
cp .claude/commands/archie-scan.md npm-package/assets/archie-scan.md
cp .claude/commands/archie-deep-scan.md npm-package/assets/archie-deep-scan.md
cp .claude/commands/archie-viewer.md npm-package/assets/archie-viewer.md
```

- [ ] **Step 6: Run sync verification**

Run: `cd /Users/csacsi/DEV/Archie && python3 scripts/verify_sync.py`
Expected: All files in sync, exit code 0

- [ ] **Step 7: Commit**

```bash
git add npm-package/assets/buddy.py npm-package/assets/archie-buddy.md npm-package/assets/archie-scan.md npm-package/assets/archie-deep-scan.md npm-package/assets/archie-viewer.md npm-package/bin/archie.mjs
git commit -m "feat: sync buddy files to npm package and update installer"
```

---

### Task 13: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/csacsi/DEV/Archie && python -m pytest tests/ -v`
Expected: All tests pass, no regressions

- [ ] **Step 2: Run sync verification**

Run: `cd /Users/csacsi/DEV/Archie && python3 scripts/verify_sync.py`
Expected: Exit 0, all in sync

- [ ] **Step 3: Manual smoke test — full view**

Run: `cd /Users/csacsi/DEV/Archie && python3 archie/standalone/buddy.py .`
Expected: Shows unborn ghost (no .archie/ in this repo) with `·` eyes and unborn message

- [ ] **Step 4: Manual smoke test — compact view**

Run: `cd /Users/csacsi/DEV/Archie && python3 archie/standalone/buddy.py . --compact`
Expected: Shows compact unborn ghost

- [ ] **Step 5: Manual smoke test — with .archie/ data**

```bash
mkdir -p /tmp/buddy-test/.archie
echo '{"meta":{"version":1}}' > /tmp/buddy-test/.archie/blueprint.json
echo 'Violations found: 3' > /tmp/buddy-test/.archie/scan_report.md
python3 archie/standalone/buddy.py /tmp/buddy-test
python3 archie/standalone/buddy.py /tmp/buddy-test --compact
rm -rf /tmp/buddy-test
```
Expected: Full view shows ~85 HP, confident mood, `◕` eyes. Compact shows one-block.
