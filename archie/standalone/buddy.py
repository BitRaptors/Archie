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
