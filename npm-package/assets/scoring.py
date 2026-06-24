#!/usr/bin/env python3
"""Architecture Integrity Score (AIS) — the scoring engine.

The composite blends four headline axes — Reconciliation (R), Product-Law
Coverage (C), Findings Burndown (B), Freshness (F) — as a weighted arithmetic
*body*, capped by a weighted geometric mean over the two correctness axes
{R, C}. The cap (the "ceiling") is what makes a broken/blind contract drag the
headline down natively, with no hand-tuned floor/drag constant:

    body    = 0.45*R + 0.30*C + 0.20*B + 0.05*F
    ceiling = 100 * exp((45*ln(R/100) + 30*ln(C/100)) / 75)
    AIS     = min(body, ceiling)

Determinism: pure arithmetic, no wall-clock, no randomness; explicit rounding at
the headline boundary. Zero dependencies beyond the Python 3.9+ stdlib.

Aggregation rationale (documented, not bespoke): non-compensatory geometric
aggregation over the correctness axes follows the composite-indicator method
(the UN HDI's 2010 arithmetic->geometric switch); the size-normalized sub-scores
are defect-density style. The headline is 75% the two contract axes — the only
axes that are grounded, attributable, and actionable.
"""
from __future__ import annotations

import math

# Headline-axis weights (sum to 1.0). Structural Health is intentionally NOT a
# headline axis — it is an informational hygiene panel only.
WEIGHT_RECONCILIATION = 0.45
WEIGHT_COVERAGE = 0.30
WEIGHT_BURNDOWN = 0.20
WEIGHT_FRESHNESS = 0.05

# Geometric correctness-ceiling exponents over {Reconciliation, Coverage}.
CEILING_EXP_RECONCILIATION = 45
CEILING_EXP_COVERAGE = 30
CEILING_EXP_DENOM = CEILING_EXP_RECONCILIATION + CEILING_EXP_COVERAGE  # 75

# Clamp each health to >= this before ln() for numerical stability (a fully
# unreconciled repo -> AIS ~ 0, correctly).
HEALTH_FLOOR = 0.02


def grade(ais: float) -> str:
    """A 90+ / B 75-89 / C 50-74 / D 25-49 / F <25."""
    if ais >= 90:
        return "A"
    if ais >= 75:
        return "B"
    if ais >= 50:
        return "C"
    if ais >= 25:
        return "D"
    return "F"


def composite(reconciliation, coverage, burndown, freshness, coverage_measured=True):
    """Blend the four headline axes (each 0-100) into the AIS headline.

    Returns {ais, grade, body, ceiling}. When ``coverage_measured`` is False
    (laws were sought but none found in a domain-bearing repo, or there are no
    laws to find), Coverage drops out of the ceiling, which is then computed
    over Reconciliation alone — never read as a free 100.
    """
    R, C, B, F = reconciliation, coverage, burndown, freshness

    if coverage_measured:
        body = (
            WEIGHT_RECONCILIATION * R
            + WEIGHT_COVERAGE * C
            + WEIGHT_BURNDOWN * B
            + WEIGHT_FRESHNESS * F
        )
    else:
        # Coverage drops out of the body too — renormalize over {R, B, F} so an
        # unmeasured Coverage neither penalizes nor is credited.
        denom = WEIGHT_RECONCILIATION + WEIGHT_BURNDOWN + WEIGHT_FRESHNESS
        body = (
            WEIGHT_RECONCILIATION * R
            + WEIGHT_BURNDOWN * B
            + WEIGHT_FRESHNESS * F
        ) / denom

    r_health = max(HEALTH_FLOOR, R / 100.0)
    if coverage_measured:
        c_health = max(HEALTH_FLOOR, C / 100.0)
        log_mean = (
            CEILING_EXP_RECONCILIATION * math.log(r_health)
            + CEILING_EXP_COVERAGE * math.log(c_health)
        ) / CEILING_EXP_DENOM
        ceiling = 100.0 * math.exp(log_mean)
    else:
        # Ceiling over Reconciliation alone: 100 * exp(ln(r_health)) = 100 * r_health.
        ceiling = 100.0 * r_health

    ais = round(min(body, ceiling), 1)
    return {
        "ais": ais,
        "grade": grade(ais),
        "body": round(body, 2),
        "ceiling": round(ceiling, 2),
    }


# ── Axis derivations from parsed .archie/ artifacts ──────────────────────────
#
# Each axis is a *rate*, never a raw count — repo size must not determine the
# score. Reconciliation and Burndown are size-normalized saturating decays
# (defect-density style); Coverage is enforced/total over identified laws, with
# an explicit measured flag so detector silence never reads as a free 100.

# Violation severity weights (check_rules maps severity_class -> error/warning/info).
VIOLATION_SEVERITY_WEIGHT = {"error": 3.0, "warning": 1.5, "info": 0.5}
# Findings severity weights (findings.json uses high/medium/low or error/warning/info).
FINDING_SEVERITY_WEIGHT = {
    "error": 3.0, "high": 3.0, "warning": 1.5, "medium": 1.5, "info": 0.5, "low": 0.5,
}
# Saturating-decay scale (per-KLOC weighted density at which the axis falls to ~e^-1).
DENSITY_SCALE = 2.0


def _law_list(blueprint, key):
    v = blueprint.get(key)
    return v if isinstance(v, list) else []


def _is_enforced(law):
    """A law is enforced when it cites an enforcing site (enforced_at)."""
    ea = law.get("enforced_at") if isinstance(law, dict) else None
    return bool(ea) and str(ea).strip() != ""


def derive_coverage(blueprint):
    """Product-Law Coverage from the blueprint's invariant sections.

    Returns (coverage_0_100, measured). ``measured`` is False when there are no
    identified laws at all — Coverage is then *unmeasured*, never a free 100
    (the absent-vs-unmeasured rule).
    """
    domain = _law_list(blueprint, "domain_invariants")
    derived = _law_list(blueprint, "derived_invariants")
    unenforced = _law_list(blueprint, "unenforced_invariants")
    total = len(domain) + len(derived) + len(unenforced)
    if total == 0:
        return (0.0, False)
    enforced = sum(1 for law in (domain + derived) if _is_enforced(law))
    return (round(100.0 * enforced / total, 1), True)


def derive_reconciliation(open_violations, kloc):
    """Reconciliation from OPEN (unreconciled) contract violations.

    Only open divergences are passed in (accepted ones are filtered upstream).
    Severity-weighted, size-normalized saturating decay: 0 open -> 100.
    """
    weighted = sum(
        VIOLATION_SEVERITY_WEIGHT.get(str(v.get("severity", "info")), 0.5)
        for v in open_violations
    )
    density = weighted / max(kloc, 1.0)
    return round(100.0 * math.exp(-density / DENSITY_SCALE), 1)


def derive_burndown(open_findings, kloc):
    """Findings Burndown from open verified findings — size-normalized decay."""
    weighted = sum(
        FINDING_SEVERITY_WEIGHT.get(str(f.get("severity", "info")).lower(), 0.5)
        for f in open_findings
    )
    density = weighted / max(kloc, 1.0)
    return round(100.0 * math.exp(-density / DENSITY_SCALE), 1)
