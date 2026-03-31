#!/usr/bin/env python3
"""Archie rule checker — reads platform + project rules and checks the codebase.

Run: python3 check_rules.py /path/to/repo
Output: JSON to stdout, summary to stderr.

Rule sources (both optional):
  .archie/platform_rules.json  — predefined rules shipped with Archie
  .archie/rules.json           — project-specific rules from scans

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import ast
import fnmatch
import json
import os
import re
import sys
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────

SOURCE_EXTENSIONS = {
    ".py", ".kt", ".kts", ".java", ".js", ".jsx", ".ts", ".tsx",
    ".swift", ".go", ".rs", ".rb", ".c", ".cpp", ".cc", ".cxx", ".h",
    ".hpp", ".cs", ".php", ".scala", ".m", ".mm",
}

SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".tox", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "dist", "build", ".build", ".next", ".nuxt", ".svelte-kit",
    "coverage", ".nyc_output", ".turbo", ".parcel-cache",
    "vendor", "Pods", "DerivedData", ".gradle", ".idea", ".vscode",
    ".archie", ".claude", ".cursor",
}

# Regex decision-point patterns for non-Python languages
_DECISION_RE = re.compile(
    r"""(?x)
    \b(?:if|elif|else\s+if|elseif|for|foreach|while|do\b.*\bwhile|
        switch|case|catch|except|when|guard)\b
    | \?\s*[^?]     # ternary  ?:
    | &&             # logical AND
    | \|\|           # logical OR
    """
)

# ── Helpers ───────────────────────────────────────────────────────────────

def _load_json(path: Path) -> dict | list:
    """Load a JSON file, returning empty dict/list on failure."""
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _read_file(path: str) -> str | None:
    """Read a file, returning None on failure."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def _walk_source_files(repo: Path) -> list[tuple[str, Path]]:
    """Walk repo returning (rel_path, abs_path) for source files."""
    results: list[tuple[str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in SOURCE_EXTENSIONS:
                continue
            abs_path = Path(dirpath) / fname
            rel_path = str(abs_path.relative_to(repo))
            results.append((rel_path, abs_path))
    return results


def _matches_glob(rel_path: str, pattern: str) -> bool:
    """Check if rel_path matches a glob pattern (supports ** and *)."""
    # fnmatch doesn't support ** natively; handle it
    if "**" in pattern:
        # Convert ** glob to regex
        regex = pattern.replace(".", r"\.")
        regex = regex.replace("**", "<<<GLOBSTAR>>>")
        regex = regex.replace("*", r"[^/]*")
        regex = regex.replace("<<<GLOBSTAR>>>", ".*")
        regex = "^" + regex + "$"
        return bool(re.match(regex, rel_path))
    return fnmatch.fnmatch(rel_path, pattern)


def _matches_dir_prefix(rel_path: str, prefix: str) -> bool:
    """Check if rel_path is under the given directory prefix."""
    # Normalize: strip trailing slash
    prefix = prefix.rstrip("/")
    return rel_path.startswith(prefix + "/") or rel_path == prefix


# ── Cyclomatic Complexity (inline) ────────────────────────────────────────

def _cc_python_function(source: str, func_start: int, func_end: int) -> int:
    """Compute cyclomatic complexity of a Python function via AST."""
    lines = source.splitlines(True)
    func_lines = lines[func_start - 1 : func_end]
    if not func_lines:
        return 1

    # Dedent to column 0 so ast.parse works
    min_indent = 9999
    for ln in func_lines:
        stripped = ln.rstrip("\n\r")
        if stripped.strip():
            indent = len(stripped) - len(stripped.lstrip())
            min_indent = min(min_indent, indent)
    if min_indent == 9999:
        min_indent = 0

    dedented = "".join(ln[min_indent:] if len(ln) > min_indent else ln for ln in func_lines)

    try:
        tree = ast.parse(dedented, mode="exec")
    except SyntaxError:
        return 1

    cc = 1
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.Assert)):
            cc += 1
        elif isinstance(node, ast.BoolOp):
            cc += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            cc += 1
            cc += len(node.ifs)
    return cc


def _cc_regex(lines: list[str]) -> int:
    """Approximate cyclomatic complexity via regex for non-Python files."""
    cc = 1
    for line in lines:
        cleaned = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
        cleaned = re.sub(r"'(?:[^'\\]|\\.)*'", "''", cleaned)
        cc += len(_DECISION_RE.findall(cleaned))
    return cc


def _compute_functions_from_skeletons(
    repo: Path, skeletons: dict
) -> list[dict]:
    """Analyze every function in skeletons for CC. Returns list of dicts."""
    results: list[dict] = []

    for rel_path, info in skeletons.items():
        symbols = info.get("symbols", [])
        line_count = info.get("line_count", 0)
        if not symbols or line_count == 0:
            continue

        ext = os.path.splitext(rel_path)[1].lower()
        if ext not in SOURCE_EXTENSIONS:
            continue

        func_symbols = [s for s in symbols if s.get("kind") in ("func", "function", "method")]
        if not func_symbols:
            continue

        abs_path = repo / rel_path
        source = _read_file(str(abs_path))
        if source is None:
            continue

        source_lines = source.splitlines()
        is_python = ext == ".py"

        all_symbols_sorted = sorted(symbols, key=lambda s: s.get("line", 0))
        sym_lines = [s.get("line", 0) for s in all_symbols_sorted]

        for sym in func_symbols:
            start_line = sym.get("line", 0)
            if start_line <= 0:
                continue

            idx_in_all = None
            for i, sl in enumerate(sym_lines):
                if sl == start_line:
                    idx_in_all = i
                    break
            if idx_in_all is not None and idx_in_all + 1 < len(sym_lines):
                end_line = sym_lines[idx_in_all + 1] - 1
            else:
                end_line = line_count

            func_lines = source_lines[start_line - 1 : end_line]

            if is_python:
                cc = _cc_python_function(source, start_line, end_line)
            else:
                cc = _cc_regex(func_lines)

            results.append({
                "path": rel_path,
                "name": sym.get("name", "?"),
                "cc": cc,
                "line": start_line,
            })

    return results


# ── Check Implementations ─────────────────────────────────────────────────

def _check_complexity_threshold(
    rule: dict,
    repo: Path,
    skeletons: dict,
    _source_files: list[tuple[str, Path]],
) -> list[dict]:
    """Check: complexity_threshold — function CC exceeds threshold."""
    threshold = rule.get("threshold", 15)
    functions = _compute_functions_from_skeletons(repo, skeletons)
    violations: list[dict] = []

    for fn in functions:
        if fn["cc"] > threshold:
            violations.append({
                "rule_id": rule["id"],
                "severity": rule.get("severity", "warn"),
                "file": fn["path"],
                "line": fn["line"],
                "message": (
                    f"Function {fn['name']}() has CC={fn['cc']}, "
                    f"exceeds threshold of {threshold}"
                ),
                "rule_description": rule.get("description", ""),
            })

    return violations


def _check_size_threshold(
    rule: dict,
    repo: Path,
    skeletons: dict,
    _source_files: list[tuple[str, Path]],
) -> list[dict]:
    """Check: size_threshold — file exceeds line count or method count."""
    max_lines = rule.get("max_lines")
    max_methods = rule.get("max_methods")
    file_pattern = rule.get("file_pattern")
    violations: list[dict] = []

    for rel_path, info in skeletons.items():
        if file_pattern and not _matches_glob(rel_path, file_pattern):
            continue

        line_count = info.get("line_count", 0)
        symbols = info.get("symbols", [])
        method_count = sum(
            1 for s in symbols if s.get("kind") in ("func", "function", "method")
        )

        if max_lines is not None and line_count > max_lines:
            violations.append({
                "rule_id": rule["id"],
                "severity": rule.get("severity", "warn"),
                "file": rel_path,
                "line": 1,
                "message": (
                    f"File has {line_count} lines, exceeds max of {max_lines}"
                ),
                "rule_description": rule.get("description", ""),
            })

        if max_methods is not None and method_count > max_methods:
            violations.append({
                "rule_id": rule["id"],
                "severity": rule.get("severity", "warn"),
                "file": rel_path,
                "line": 1,
                "message": (
                    f"File has {method_count} methods/functions, "
                    f"exceeds max of {max_methods}"
                ),
                "rule_description": rule.get("description", ""),
            })

    return violations


def _check_forbidden_import(
    rule: dict,
    repo: Path,
    skeletons: dict,
    source_files: list[tuple[str, Path]],
) -> list[dict]:
    """Check: forbidden_import — file in directory X must not import from Y."""
    applies_to = rule.get("applies_to", "")
    forbidden_patterns = rule.get("forbidden_patterns", [])
    if not forbidden_patterns:
        return []

    compiled = [re.compile(p) for p in forbidden_patterns]
    violations: list[dict] = []

    for rel_path, abs_path in source_files:
        if applies_to and not _matches_dir_prefix(rel_path, applies_to):
            continue

        content = _read_file(str(abs_path))
        if content is None:
            continue

        for line_no, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            # Quick filter: only check lines that look like imports
            if not (
                stripped.startswith("import ")
                or stripped.startswith("from ")
                or stripped.startswith("require(")
                or stripped.startswith("require ")
                or "import " in stripped
                or stripped.startswith("#include")
                or stripped.startswith("use ")
            ):
                continue

            for pat in compiled:
                if pat.search(stripped):
                    violations.append({
                        "rule_id": rule["id"],
                        "severity": rule.get("severity", "warn"),
                        "file": rel_path,
                        "line": line_no,
                        "message": (
                            f"Forbidden import pattern '{pat.pattern}' "
                            f"matched: {stripped[:120]}"
                        ),
                        "rule_description": rule.get("description", ""),
                    })
                    break  # one violation per line

    return violations


def _check_required_pattern(
    rule: dict,
    repo: Path,
    skeletons: dict,
    source_files: list[tuple[str, Path]],
) -> list[dict]:
    """Check: required_pattern — file matching glob must contain content."""
    file_pattern = rule.get("file_pattern")
    required_in_content = rule.get("required_in_content", [])
    if not file_pattern or not required_in_content:
        return []

    violations: list[dict] = []

    for rel_path, abs_path in source_files:
        if not _matches_glob(rel_path, file_pattern):
            continue

        content = _read_file(str(abs_path))
        if content is None:
            continue

        for required in required_in_content:
            if required not in content:
                violations.append({
                    "rule_id": rule["id"],
                    "severity": rule.get("severity", "warn"),
                    "file": rel_path,
                    "line": 1,
                    "message": (
                        f"Required content '{required[:80]}' not found in file"
                    ),
                    "rule_description": rule.get("description", ""),
                })

    return violations


def _check_forbidden_content(
    rule: dict,
    repo: Path,
    skeletons: dict,
    source_files: list[tuple[str, Path]],
) -> list[dict]:
    """Check: forbidden_content — code must not contain certain patterns."""
    applies_to = rule.get("applies_to")
    forbidden_patterns = rule.get("forbidden_patterns", [])
    if not forbidden_patterns:
        return []

    compiled = [re.compile(p) for p in forbidden_patterns]
    violations: list[dict] = []

    for rel_path, abs_path in source_files:
        if applies_to and not _matches_dir_prefix(rel_path, applies_to):
            continue

        content = _read_file(str(abs_path))
        if content is None:
            continue

        for line_no, line in enumerate(content.splitlines(), 1):
            for pat in compiled:
                if pat.search(line):
                    violations.append({
                        "rule_id": rule["id"],
                        "severity": rule.get("severity", "warn"),
                        "file": rel_path,
                        "line": line_no,
                        "message": (
                            f"Forbidden pattern '{pat.pattern}' "
                            f"matched: {line.strip()[:120]}"
                        ),
                        "rule_description": rule.get("description", ""),
                    })
                    break  # one violation per line per rule

    return violations


def _check_architectural_constraint(
    rule: dict,
    repo: Path,
    skeletons: dict,
    source_files: list[tuple[str, Path]],
) -> list[dict]:
    """Check: architectural_constraint — file matching glob + forbidden regex."""
    file_pattern = rule.get("file_pattern")
    forbidden_patterns = rule.get("forbidden_patterns", [])
    if not file_pattern or not forbidden_patterns:
        return []

    compiled = [re.compile(p) for p in forbidden_patterns]
    rationale = rule.get("rationale", "")
    violations: list[dict] = []

    for rel_path, abs_path in source_files:
        if not _matches_glob(rel_path, file_pattern):
            continue

        content = _read_file(str(abs_path))
        if content is None:
            continue

        for line_no, line in enumerate(content.splitlines(), 1):
            for pat in compiled:
                if pat.search(line):
                    msg = (
                        f"Architectural constraint violated: "
                        f"pattern '{pat.pattern}' matched: {line.strip()[:120]}"
                    )
                    if rationale:
                        msg += f" — {rationale}"
                    violations.append({
                        "rule_id": rule["id"],
                        "severity": rule.get("severity", "error"),
                        "file": rel_path,
                        "line": line_no,
                        "message": msg,
                        "rule_description": rule.get("description", ""),
                    })
                    break  # one violation per line per rule

    return violations


# ── Dispatcher ────────────────────────────────────────────────────────────

_CHECK_DISPATCH: dict[str, object] = {
    "complexity_threshold": _check_complexity_threshold,
    "size_threshold": _check_size_threshold,
    "forbidden_import": _check_forbidden_import,
    "required_pattern": _check_required_pattern,
    "forbidden_content": _check_forbidden_content,
    "architectural_constraint": _check_architectural_constraint,
}


# ── Main ──────────────────────────────────────────────────────────────────

def run_checks(repo: Path) -> dict:
    """Run all rule checks against the repo. Returns result dict."""
    archie_dir = repo / ".archie"

    # Load rules from both sources
    platform_rules_path = archie_dir / "platform_rules.json"
    project_rules_path = archie_dir / "rules.json"

    platform_rules = _load_json(platform_rules_path)
    project_rules = _load_json(project_rules_path)

    # Normalize: each source can be a list or a dict with a "rules" key
    def _extract_rules(data: dict | list) -> list[dict]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "rules" in data:
            rules = data["rules"]
            return rules if isinstance(rules, list) else []
        return []

    all_rules = _extract_rules(platform_rules) + _extract_rules(project_rules)

    if not all_rules:
        return {"violations": [], "rules_checked": 0, "violations_count": 0}

    # Load skeletons (needed for complexity + size checks)
    skeletons = _load_json(archie_dir / "skeletons.json")
    if not isinstance(skeletons, dict):
        skeletons = {}

    # Walk source files once (cached for all content-based checks)
    source_files = _walk_source_files(repo)

    # Run each rule
    all_violations: list[dict] = []
    rules_checked = 0

    for rule in all_rules:
        check_type = rule.get("check")
        if not check_type:
            continue
        checker = _CHECK_DISPATCH.get(check_type)
        if checker is None:
            print(
                f"Warning: unknown check type '{check_type}' in rule '{rule.get('id', '?')}'",
                file=sys.stderr,
            )
            continue

        rules_checked += 1
        violations = checker(rule, repo, skeletons, source_files)
        all_violations.extend(violations)

    return {
        "violations": all_violations,
        "rules_checked": rules_checked,
        "violations_count": len(all_violations),
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 check_rules.py /path/to/repo", file=sys.stderr)
        sys.exit(1)

    repo = Path(sys.argv[1]).resolve()
    if not repo.is_dir():
        print(f"Error: {repo} is not a directory", file=sys.stderr)
        sys.exit(1)

    result = run_checks(repo)

    # Print JSON to stdout
    print(json.dumps(result, indent=2))

    # Print summary to stderr
    violations = result["violations"]
    error_count = sum(1 for v in violations if v.get("severity") == "error")
    warn_count = sum(1 for v in violations if v.get("severity") == "warn")
    info_count = sum(1 for v in violations if v.get("severity") == "info")

    parts = []
    if error_count:
        parts.append(f"{error_count} error")
    if warn_count:
        parts.append(f"{warn_count} warn")
    if info_count:
        parts.append(f"{info_count} info")

    severity_str = f" ({', '.join(parts)})" if parts else ""
    print(
        f"Rules: {result['rules_checked']} checked, "
        f"{result['violations_count']} violations{severity_str}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
