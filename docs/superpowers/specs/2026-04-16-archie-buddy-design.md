# Archie Buddy — Design Spec

## Overview

Pimasz ASCII szellem tamagotchi az Archie CLI-hez. Standalone `/archie-buddy` slash command a teljes nézethez, plusz kompakt megjelenés minden Archie parancs (`/archie-scan`, `/archie-deep-scan`, `/archie-viewer`) végén.

A buddy a `.archie/` könyvtár adataiból (blueprint, scan report, rules) számolja az állapotát, és szarkasztikus kommentárral kíséri az architektúra egészségét.

## ASCII Art

Az SVG ghost logóra (`v1/frontend/public/archie-logo.svg`) épül: kupola tető, két nagy szem, blueprint rácsvonalak, három hullám az alján.

### Teljes nézet (`/archie-buddy`)

```
    ▄███████▄
  ▄█         █▄
 █   ◉     ◉   █     Archie  ♥ HP: ██████░░░░ 58/100
 █ ╌╌╌╌╌╌╌╌╌╌╌ █     Mood: Skeptical
 █               █     Scan: 2 napja  │  Violations: 7
 █ ╌╌╌╌╌╌╌╌╌╌╌ █     Streak: 3 scans
 ▀█▄▀ ▀█▄▀ ▀█▄▀

 "7 violation. Hét. Nem akarom tudni mi lesz jövő héten."
```

### Kompakt nézet (parancs végén)

```
    ▄███████▄
  ▄█         █▄
 █   ◕     ◕   █   HP: ████████░░ 82  │  "Csak 2 violation? Szinte gyanús."
 █ ╌╌╌╌╌╌╌╌╌╌╌ █
 ▀█▄▀ ▀█▄▀ ▀█▄▀
```

### Mood-specifikus szemek

| Mood | Szemek | HP tartomány |
|------|--------|--------------|
| Confident | `◕ ◕` | 80-100 |
| Skeptical | `¬ ¬` | 50-79 |
| Sick | `◔ ◔` | 20-49 |
| Dead | `× ×` | 0-19 |
| Unborn | `· ·` | Nincs blueprint |

## HP/Mood Rendszer

Három input határozza meg a HP-t (0-100):

### 1. Blueprint létezése (0 vagy 30 pont)

- `.archie/blueprint.json` létezik → +30 HP
- Nem létezik → 0 HP, mood: `unborn`

### 2. Scan frissesség (0-40 pont)

Az utolsó `.archie/scan_report.md` módosítási ideje alapján:

| Frissesség | Pont |
|------------|------|
| < 1 nap | 40 |
| 1-3 nap | 30 |
| 3-5 nap | 15 |
| 5-7 nap | 5 |
| > 7 nap | 0 |

### 3. Violation szám (0-30 pont)

Az utolsó scan report-ból kiolvasott violation-ök száma:

| Violations | Pont |
|------------|------|
| 0 | 30 |
| 1-3 | 25 |
| 4-7 | 15 |
| 8-15 | 5 |
| > 15 | 0 |

### Mood mapping

| HP tartomány | Mood | Szemek | Személyiség |
|-------------|------|--------|-------------|
| 80-100 | Confident | `◕ ◕` | Pimasz, unatkozik mert minden rendben |
| 50-79 | Skeptical | `¬ ¬` | Szkeptikus, figyelmeztet |
| 20-49 | Sick | `◔ ◔` | Rosszul van, panaszkodik |
| 0-19 | Dead | `× ×` | Halottnak nyilvánítja magát |
| N/A | Unborn | `· ·` | Még nem született meg |

## Személyiség: Szarkasztikus/Pimasz

Mood-onként 5-10 random üzenet, példák:

**Confident (80-100):**
- "47 fájl és egy violation sincs. Unatkozom."
- "Csak 2 violation? Szinte gyanús."
- "Na EZ egy architektúra. Majdnem meghatódtam."

**Skeptical (50-79):**
- "7 violation. Hét. Nem akarom tudni mi lesz jövő héten."
- "Lassan rohadni kezd ez a codebase. Csak szólok."
- "Aha, 'majd refaktorálom'. Persze."

**Sick (20-49):**
- "Fizikailag rosszul vagyok ettől a coupling-tól."
- "Ez a circular dependency az én személyes pokol-köröm."
- "Segítség. Valaki. Bárki."

**Dead (0-19):**
- "Hivatalosan is halott vagyok. Gratulálok."
- "Ennél egy /dev/null is jobb architektúra."
- "👻 < igen, ez az én szellemem. A szellem szellem."

**Unborn:**
- "Futtass egy /archie-deep-scan-t, hogy megszülessek."
- "Helló? Van itt valaki? Sötét van."

## Persisted State

### Fájl: `.archie/buddy.json`

```json
{
  "last_interaction": "2026-04-16T14:30:00Z",
  "streak": 3,
  "total_scans": 12,
  "best_hp": 95,
  "achievements": ["first_scan", "clean_streak_3"]
}
```

### Mezők

- `last_interaction` — utolsó `/archie-buddy` hívás ideje
- `streak` — egymás utáni napok amikor volt scan
- `total_scans` — összes scan szám (deep + regular)
- `best_hp` — valaha elért legjobb HP
- `achievements` — feloldott achievement-ek listája

### Achievements (v1)

| ID | Feltétel | Üzenet |
|----|----------|--------|
| `first_scan` | Első scan lefut | "Végre! Azt hittem soha." |
| `first_clean` | 0 violation scan | "Tiszta scan? Csípj meg." |
| `clean_streak_3` | 3 egymás utáni clean scan | "3x clean. Kezdek hinni benned." |
| `clean_streak_7` | 7 egymás utáni clean scan | "Egy hét clean. Ki vagy te?" |
| `comeback` | HP 20 alól 80 fölé | "A feltámadás megtörtént." |

## Implementáció

### Fájlok

| Fájl | Szerep |
|------|--------|
| `archie/standalone/buddy.py` | Fő logika: HP számítás, mood, ASCII renderelés, buddy.json kezelés |
| `.claude/commands/archie-buddy.md` | Slash command: teljes nézet |
| `npm-package/assets/buddy.py` | Sync másolat |
| `npm-package/assets/archie-buddy.md` | Sync másolat |

### buddy.py interface

```
# Teljes nézet
python3 archie/standalone/buddy.py /path/to/project

# Kompakt nézet (parancsok végéhez)
python3 archie/standalone/buddy.py /path/to/project --compact
```

**Stdout:** renderelt ASCII + szöveg (a slash command beilleszti a kimenetbe)
**Exit code:** 0 mindig (a buddy soha nem buktatja el a parent parancsot)

### Meglévő parancsokba integráció

Az `/archie-scan`, `/archie-deep-scan`, `/archie-viewer` markdown fájlok végére kerül egy sor:
```
Run `python3 archie/standalone/buddy.py $ARGUMENTS --compact` and include its output at the end.
```

### Dependency

Nulla külső dependency — pure Python 3.9+, csak stdlib (json, datetime, pathlib, os, random). Illeszkedik a standalone scripts filozófiájához.

## Scope — ami NEM része v1-nek

- Nem animált (nincs frame-by-frame terminál animáció)
- Nem interaktív (nincs "etesd meg" parancs — a scan az etetés)
- Nincs színes output (plain ASCII, terminál kompatibilitás)
- Nincs hangeffekt
- Nincs hálózati hívás
