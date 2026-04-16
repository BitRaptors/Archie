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
