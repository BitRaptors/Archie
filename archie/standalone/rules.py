#!/usr/bin/env python3
"""Archie standalone rule extractor — extracts enforcement rules from blueprint.

Run: python3 rules.py /path/to/repo
Output: Writes .archie/rules.json

Zero dependencies beyond Python 3.11+ stdlib.
"""
import json
import re
import sys
from pathlib import Path


def extract_rules(blueprint: dict) -> list[dict]:
    """Extract enforcement rules from a blueprint dict."""
    rules: list[dict] = []
    arch = blueprint.get("architecture_rules", {})
    if isinstance(arch, str):
        return rules

    # File placement rules
    for i, r in enumerate(arch.get("file_placement_rules", [])):
        if not isinstance(r, dict):
            continue
        location = r.get("location", "")
        description = r.get("description", r.get("pattern", ""))
        rules.append({
            "id": f"placement-{i}",
            "check": "file_placement",
            "description": description,
            "allowed_dirs": [location] if location else [],
            "severity": "warn",
            "keywords": _extract_keywords(description),
        })

    # Naming conventions
    for i, n in enumerate(arch.get("naming_conventions", [])):
        if not isinstance(n, dict):
            continue
        scope = n.get("scope", n.get("target", ""))
        convention = n.get("pattern", n.get("convention", ""))
        examples = n.get("examples", [])
        if isinstance(examples, str):
            examples = [examples]
        example_str = examples[0] if examples else ""
        rules.append({
            "id": f"naming-{i}",
            "check": "naming",
            "description": f"{scope}: {convention}" + (f" (e.g. {example_str})" if example_str else ""),
            "pattern": _convention_to_regex(convention),
            "severity": "warn",
            "keywords": _extract_keywords(f"{scope} {convention}"),
        })

    # Component layer rules
    raw_components = blueprint.get("components", {})
    if isinstance(raw_components, list):
        comp_list = raw_components
    elif isinstance(raw_components, dict):
        comp_list = raw_components.get("components", [])
    else:
        comp_list = []
    if comp_list:
        for i, comp in enumerate(comp_list):
            if not isinstance(comp, dict):
                continue
            path = comp.get("location", comp.get("path", ""))
            name = comp.get("name", "")
            if path:
                rules.append({
                    "id": f"layer-{i}",
                    "check": "file_placement",
                    "description": f"{name} files belong in {path}",
                    "allowed_dirs": [path],
                    "severity": "warn",
                    "keywords": _extract_keywords(f"{name} {path}"),
                })

    # --- Basic architectural rules (types 1-6) ---
    rules.extend(_extract_dependency_direction_rules(blueprint))
    rules.extend(_extract_forbidden_dep_rules(blueprint))
    rules.extend(_extract_out_of_scope_rules(blueprint))
    rules.extend(_extract_dev_rules(blueprint))
    rules.extend(_extract_pattern_rules(blueprint))
    rules.extend(_extract_pitfall_rules(blueprint))

    # --- Deep architectural connection rules (types 7-12) ---
    rules.extend(_extract_chain_rules(blueprint))
    rules.extend(_extract_tradeoff_rules(blueprint))
    rules.extend(_extract_impact_rules(blueprint))
    rules.extend(_extract_scope_creep_rules(blueprint))
    rules.extend(_extract_pattern_extension_rules(blueprint))
    rules.extend(_extract_pitfall_trace_rules(blueprint))

    return rules


# ---------------------------------------------------------------------------
# Basic architectural rules
# ---------------------------------------------------------------------------

def _extract_dependency_direction_rules(bp: dict) -> list[dict]:
    """From components[].depends_on — prevent reverse dependencies."""
    rules = []
    raw = bp.get("components", {})
    comps = raw.get("components", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])

    # Build location→name map and name→location map
    name_to_loc = {}
    for c in comps:
        if isinstance(c, dict) and c.get("name") and c.get("location"):
            name_to_loc[c["name"]] = c["location"]

    # For each component, its dependencies should not import back from it
    for i, comp in enumerate(comps):
        if not isinstance(comp, dict):
            continue
        name = comp.get("name", "")
        location = comp.get("location", "")
        deps = comp.get("depends_on") or []
        if not location or not deps:
            continue
        # This component depends on deps — deps should NOT import from this component
        for dep_name in deps:
            dep_loc = name_to_loc.get(dep_name, "")
            if dep_loc and dep_loc != location:
                rules.append({
                    "id": f"dep-dir-{i}-{dep_name[:20]}",
                    "check": "dependency_direction",
                    "description": f"{dep_name} ({dep_loc}) must not import from {name} ({location})",
                    "forbidden_imports": [location],
                    "applies_to": dep_loc,
                    "severity": "warn",
                    "keywords": _extract_keywords(f"{name} {dep_name} import dependency"),
                })
    return rules


def _extract_forbidden_dep_rules(bp: dict) -> list[dict]:
    """From decisions + out_of_scope — infer forbidden packages."""
    rules = []
    decisions = bp.get("decisions", {})

    # Common out-of-scope → forbidden package mapping
    scope_to_packages = {
        "authentication": ["passport", "next-auth", "jsonwebtoken", "express-jwt", "auth0"],
        "auth": ["passport", "next-auth", "jsonwebtoken", "express-jwt", "auth0"],
        "deployment": ["serverless", "aws-cdk", "pulumi"],
        "graphql": ["graphql", "apollo-server", "@apollo/server"],
        "websocket": ["socket.io", "ws"],
    }

    for item in decisions.get("out_of_scope", []):
        item_lower = item.lower() if isinstance(item, str) else ""
        for scope_key, packages in scope_to_packages.items():
            if scope_key in item_lower:
                rules.append({
                    "id": f"forbidden-{scope_key}",
                    "check": "forbidden_dependency",
                    "description": f"Out of scope: {item}. Forbidden packages: {', '.join(packages)}",
                    "forbidden_packages": packages,
                    "severity": "warn",
                    "keywords": _extract_keywords(item) + [scope_key],
                })
                break

    # From key decisions — detect "X only" patterns
    for dec in decisions.get("key_decisions", []):
        if not isinstance(dec, dict):
            continue
        chosen = (dec.get("chosen", "") or "").lower()
        alternatives = dec.get("alternatives_rejected", [])
        # Map rejected alternatives to package names
        alt_packages = []
        alt_map = {
            "prisma": ["prisma", "@prisma/client"],
            "typeorm": ["typeorm"],
            "sequelize": ["sequelize"],
            "postgres": ["pg", "postgres"],
            "mongodb": ["mongoose", "mongodb"],
            "redis": ["redis", "ioredis"],
            "redux": ["redux", "@reduxjs/toolkit"],
            "zustand": ["zustand"],
            "mobx": ["mobx"],
        }
        for alt in alternatives:
            alt_lower = alt.lower() if isinstance(alt, str) else ""
            for key, pkgs in alt_map.items():
                if key in alt_lower:
                    alt_packages.extend(pkgs)
        if alt_packages:
            rules.append({
                "id": f"forbidden-alt-{dec.get('title', '')[:30]}",
                "check": "forbidden_dependency",
                "description": f"Decision '{dec.get('title', '')}': rejected alternatives → forbidden: {', '.join(alt_packages)}",
                "forbidden_packages": alt_packages,
                "severity": "warn",
                "keywords": _extract_keywords(dec.get("title", "")),
            })
    return rules


def _extract_out_of_scope_rules(bp: dict) -> list[dict]:
    """From decisions.out_of_scope[] — boundary warnings."""
    rules = []
    for i, item in enumerate(bp.get("decisions", {}).get("out_of_scope", [])):
        if not isinstance(item, str) or not item:
            continue
        rules.append({
            "id": f"scope-{i}",
            "check": "out_of_scope",
            "description": f"Out of scope: {item}",
            "boundary": item,
            "severity": "warn",
            "keywords": _extract_keywords(item),
        })
    return rules


def _extract_dev_rules(bp: dict) -> list[dict]:
    """From development_rules[] — always/never imperatives."""
    rules = []
    for i, dr in enumerate(bp.get("development_rules", [])):
        if not isinstance(dr, dict):
            continue
        rule_text = dr.get("rule", "")
        source = dr.get("source", "")
        category = dr.get("category", "general")
        if not rule_text:
            continue
        rules.append({
            "id": f"dev-{category}-{i}",
            "check": "dev_rule",
            "description": f"{rule_text}" + (f" (source: {source})" if source else ""),
            "rule": rule_text,
            "source": source,
            "category": category,
            "severity": "warn",
            "keywords": _extract_keywords(rule_text),
        })
    return rules


def _extract_pattern_rules(bp: dict) -> list[dict]:
    """From communication.patterns[] — required patterns."""
    rules = []
    patterns = bp.get("communication", {}).get("patterns", [])
    for i, pat in enumerate(patterns):
        if not isinstance(pat, dict):
            continue
        name = pat.get("name", "")
        when = pat.get("when_to_use", "")
        how = pat.get("how_it_works", "")
        if not name:
            continue
        rules.append({
            "id": f"pattern-{i}",
            "check": "pattern_required",
            "description": f"Pattern: {name} — {when}",
            "pattern_name": name,
            "when_to_use": when,
            "how_it_works": how,
            "severity": "warn",
            "keywords": _extract_keywords(f"{name} {when}"),
        })
    return rules


def _extract_pitfall_rules(bp: dict) -> list[dict]:
    """From pitfalls[] — area-based warnings."""
    rules = []
    for i, pit in enumerate(bp.get("pitfalls", [])):
        if not isinstance(pit, dict):
            continue
        area = pit.get("area", "")
        desc = pit.get("description", "")
        rec = pit.get("recommendation", "")
        if not area and not desc:
            continue
        rules.append({
            "id": f"pitfall-{i}",
            "check": "pitfall",
            "description": f"Pitfall ({area}): {desc}",
            "area": area,
            "recommendation": rec,
            "severity": "warn",
            "keywords": _extract_keywords(f"{area} {desc}"),
        })
    return rules


# ---------------------------------------------------------------------------
# Deep architectural connection rules
# ---------------------------------------------------------------------------

def _extract_chain_rules(bp: dict) -> list[dict]:
    """From decisions.decision_chain — cascade violation warnings."""
    rules = []
    chain = bp.get("decisions", {}).get("decision_chain", {})
    if not isinstance(chain, dict) or not chain.get("root"):
        return rules

    # Flatten the chain into a list of decisions
    def _flatten(node, acc=None):
        if acc is None:
            acc = []
        for f in (node.get("forces") or []):
            acc.append(f.get("decision", ""))
            _flatten(f, acc)
        return acc

    all_decisions = _flatten(chain)
    if all_decisions:
        all_kw = []
        for d in all_decisions:
            all_kw.extend(_extract_keywords(d))
        rules.append({
            "id": "chain-root",
            "check": "chain_violation",
            "description": f"Root constraint: {chain['root']}. Downstream: {', '.join(all_decisions[:6])}",
            "root": chain["root"],
            "chain": all_decisions,
            "severity": "error",
            "keywords": _extract_keywords(chain["root"]) + all_kw[:20],
        })
    return rules


def _extract_tradeoff_rules(bp: dict) -> list[dict]:
    """From trade_offs[].caused_by — trade-off consistency."""
    rules = []
    for i, to in enumerate(bp.get("decisions", {}).get("trade_offs", [])):
        if not isinstance(to, dict):
            continue
        accept = to.get("accept", "") or to.get("accepted", "")
        benefit = to.get("benefit", "") or to.get("gained", "")
        caused_by = to.get("caused_by", "")
        if not accept:
            continue
        rules.append({
            "id": f"tradeoff-{i}",
            "check": "tradeoff_violation",
            "description": f"Trade-off: accept '{accept}' for benefit '{benefit}'" + (f" (from: {caused_by})" if caused_by else ""),
            "accept": accept,
            "benefit": benefit,
            "caused_by": caused_by,
            "severity": "warn",
            "keywords": _extract_keywords(f"{accept} {benefit}"),
        })
    return rules


def _extract_impact_rules(bp: dict) -> list[dict]:
    """From components dependency graph — blast radius warnings."""
    rules = []
    raw = bp.get("components", {})
    comps = raw.get("components", []) if isinstance(raw, dict) else (raw if isinstance(raw, list) else [])

    # Build reverse dependency map: component → list of dependents
    reverse_deps: dict[str, list[str]] = {}
    for comp in comps:
        if not isinstance(comp, dict):
            continue
        name = comp.get("name", "")
        for dep in (comp.get("depends_on") or []):
            if dep not in reverse_deps:
                reverse_deps[dep] = []
            reverse_deps[dep].append(name)

    # Create impact rules for components with 2+ dependents
    for i, comp in enumerate(comps):
        if not isinstance(comp, dict):
            continue
        name = comp.get("name", "")
        location = comp.get("location", "")
        dependents = reverse_deps.get(name, [])
        if len(dependents) >= 2 and location:
            rules.append({
                "id": f"impact-{i}",
                "check": "impact_radius",
                "description": f"{name} changes impact {len(dependents)} dependents: {', '.join(dependents[:6])}",
                "component": name,
                "location": location,
                "depended_on_by": dependents,
                "severity": "warn",
                "keywords": _extract_keywords(f"{name} {location}"),
            })
    return rules


def _extract_scope_creep_rules(bp: dict) -> list[dict]:
    """From out_of_scope — detect multi-signal scope creep."""
    rules = []
    # Map scope boundaries to indicator patterns
    scope_indicators = {
        "authentication": ["userId", "user_id", "currentUser", "login", "signup", "password", "jwt", "token", "session"],
        "auth": ["userId", "user_id", "currentUser", "login", "signup", "password", "jwt", "token"],
        "multi-user": ["userId", "user_id", "currentUser", "tenant", "workspace", "organization"],
        "deployment": ["deploy", "vercel", "netlify", "docker", "kubernetes", "aws", "gcp"],
        "hosting": ["deploy", "ssl", "domain", "cdn", "certificate"],
    }
    for item in bp.get("decisions", {}).get("out_of_scope", []):
        if not isinstance(item, str):
            continue
        item_lower = item.lower()
        for scope_key, indicators in scope_indicators.items():
            if scope_key in item_lower:
                rules.append({
                    "id": f"creep-{scope_key}",
                    "check": "scope_creep",
                    "description": f"Scope creep detection: '{item}'. Watch for: {', '.join(indicators[:5])}",
                    "boundary": item,
                    "indicator_patterns": indicators,
                    "threshold": 2,
                    "severity": "warn",
                    "keywords": _extract_keywords(item) + indicators[:5],
                })
                break
    return rules


def _extract_pattern_extension_rules(bp: dict) -> list[dict]:
    """From patterns + implementation_guidelines — extension touch points."""
    rules = []
    guidelines = bp.get("implementation_guidelines", [])
    for i, gl in enumerate(guidelines):
        if not isinstance(gl, dict):
            continue
        capability = gl.get("capability", "")
        key_files = gl.get("key_files", [])
        if not capability or len(key_files) < 2:
            continue
        rules.append({
            "id": f"extend-{i}",
            "check": "pattern_extension",
            "description": f"Extending '{capability}' requires changes in: {', '.join(key_files[:5])}",
            "capability": capability,
            "required_touch_points": key_files,
            "severity": "warn",
            "keywords": _extract_keywords(capability),
        })
    return rules


def _extract_pitfall_trace_rules(bp: dict) -> list[dict]:
    """From pitfalls[].stems_from — link pitfalls to decision chain."""
    rules = []
    chain = bp.get("decisions", {}).get("decision_chain", {})
    # Flatten chain for lookup
    chain_decisions = []
    def _flatten(node):
        for f in (node.get("forces") or []):
            chain_decisions.append(f.get("decision", ""))
            _flatten(f)
    if isinstance(chain, dict):
        _flatten(chain)

    for i, pit in enumerate(bp.get("pitfalls", [])):
        if not isinstance(pit, dict):
            continue
        stems_from = pit.get("stems_from", "")
        if not stems_from:
            continue
        area = pit.get("area", "")
        desc = pit.get("description", "")
        rec = pit.get("recommendation", "")
        # Find the chain path to this pitfall's source
        related_chain = [d for d in chain_decisions if stems_from.lower() in d.lower() or d.lower() in stems_from.lower()]
        rules.append({
            "id": f"pitfall-trace-{i}",
            "check": "pitfall_trace",
            "description": f"Pitfall ({area}): {desc} — stems from: {stems_from}",
            "area": area,
            "pitfall": desc,
            "stems_from": stems_from,
            "decision_chain": [chain.get("root", "")] + related_chain if chain.get("root") else [],
            "recommendation": rec,
            "severity": "warn",
            "keywords": _extract_keywords(f"{area} {desc} {stems_from}"),
        })
    return rules


def _convention_to_regex(convention: str) -> str:
    patterns = {
        "snake_case": r"^[a-z][a-z0-9_]*(\.[a-z]+)?$",
        "camelCase": r"^[a-z][a-zA-Z0-9]*(\.[a-z]+)?$",
        "PascalCase": r"^[A-Z][a-zA-Z0-9]*(\.[a-z]+)?$",
        "kebab-case": r"^[a-z][a-z0-9-]*(\.[a-z]+)?$",
    }
    return patterns.get(convention, "")


def _extract_keywords(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    stop = {"the", "and", "for", "are", "this", "that", "with", "from", "use", "must", "files", "belong"}
    return [w for w in words if w not in stop]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 rules.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    bp_path = root / ".archie" / "blueprint.json"

    if not bp_path.exists():
        print("No .archie/blueprint.json found", file=sys.stderr)
        sys.exit(1)

    bp = json.loads(bp_path.read_text())

    # Preserve promoted rules from existing rules.json
    old_severities: dict[str, str] = {}
    old_rules_path = root / ".archie" / "rules.json"
    if old_rules_path.exists():
        try:
            old = json.loads(old_rules_path.read_text())
            for r in old.get("rules", []):
                if r.get("severity") == "error":
                    old_severities[r["id"]] = "error"
        except (json.JSONDecodeError, OSError):
            pass

    rules = extract_rules(bp)

    # Restore promoted severities
    for r in rules:
        if r["id"] in old_severities:
            r["severity"] = old_severities[r["id"]]

    # Save
    (root / ".archie").mkdir(exist_ok=True)
    with open(root / ".archie" / "rules.json", "w") as f:
        json.dump({"rules": rules}, f, indent=2)

    promoted = sum(1 for r in rules if r["severity"] == "error")
    print(f"Extracted {len(rules)} rules ({promoted} promoted to error)", file=sys.stderr)
