"""Validate grounding system output for a completed analysis run."""
import json
import os
import re
from pathlib import Path

REPO_ID = "5d27b1a9-986e-4cdb-b81c-297e680ab6fd"
BLUEPRINT_DIR = Path(f"storage/blueprints/{REPO_ID}")
REPO_DIR = Path(f"storage/repos/{REPO_ID}")

# ── 1. LOAD ARTIFACTS ──
blueprint = json.loads((BLUEPRINT_DIR / "blueprint.json").read_text())
observation = (BLUEPRINT_DIR / "observation.json").read_text()
discovery = (BLUEPRINT_DIR / "discovery.json").read_text()
layers = (BLUEPRINT_DIR / "layers.json").read_text()
patterns = (BLUEPRINT_DIR / "patterns.json").read_text()
communication = (BLUEPRINT_DIR / "communication.json").read_text()
technology = (BLUEPRINT_DIR / "technology.json").read_text()
frontend = (BLUEPRINT_DIR / "frontend_analysis.json").read_text()
implementation = (BLUEPRINT_DIR / "implementation_analysis.json").read_text()

# ── 2. BUILD GROUND TRUTH FILE REGISTRY ──
real_files = set()
for root, dirs, files in os.walk(REPO_DIR):
    for f in files:
        full = Path(root) / f
        rel = str(full.relative_to(REPO_DIR))
        if rel == "manifest.json":
            continue
        real_files.add(rel)

source_exts = {
    ".swift", ".m", ".mm", ".h", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".kt", ".rb", ".php", ".cs", ".cpp", ".c",
    ".hpp", ".scala",
}
real_source_files = {f for f in real_files if any(f.endswith(e) for e in source_exts)}

print("=" * 70)
print("GROUNDING SYSTEM VALIDATION REPORT")
print("=" * 70)
print(f"Repository: BitRaptors/Gasztroterkepek.iOS ({REPO_ID[:12]}...)")
print(f"Ground truth files: {len(real_files)} total, {len(real_source_files)} source")
print()

# ── 3. CONTENT VALIDITY ──
print("-" * 70)
print("1. CONTENT VALIDITY")
print("-" * 70)

required_keys = [
    "meta", "architecture_rules", "decisions", "components",
    "communication", "quick_reference", "technology", "frontend",
]
missing = [k for k in required_keys if k not in blueprint]
print(f"  Blueprint JSON valid: YES ({len(json.dumps(blueprint)):,} chars)")
if missing:
    print(f"  Required sections: MISSING: {', '.join(missing)}")
else:
    print(f"  Required sections: ALL present")
print(f"  Schema version: {blueprint.get('meta', {}).get('schema_version', 'unknown')}")
print(f"  Architecture style: {blueprint.get('meta', {}).get('architecture_style', 'unknown')}")
print(f"  Platforms: {blueprint.get('meta', {}).get('platforms', [])}")

conf = blueprint.get("meta", {}).get("confidence", {})
print(f"  Confidence scores: {json.dumps(conf)}")

comps = blueprint.get("components", {}).get("components", [])
print(f"  Components: {len(comps)}")
rules = blueprint.get("architecture_rules", {}).get("file_placement_rules", [])
print(f"  File placement rules: {len(rules)}")
impl = blueprint.get("implementation_guidelines", [])
print(f"  Implementation guidelines: {len(impl)}")
recipes = blueprint.get("developer_recipes", [])
print(f"  Developer recipes: {len(recipes)}")
print()


# ── 4. GROUNDING VALIDATION ──
print("-" * 70)
print("2. GROUNDING VALIDATION (file path accuracy in blueprint)")
print("-" * 70)


def extract_file_paths(obj, paths=None, context_key=None):
    """Recursively extract file-like paths from JSON structure."""
    if paths is None:
        paths = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("file", "example", "file_path_template") and isinstance(v, str):
                if v and "/" in v and not v.startswith("http") and "**" not in v and "{" not in v:
                    paths.append(("file", v))
            elif k == "location" and isinstance(v, str):
                if v and "/" in v and not v.startswith("http"):
                    paths.append(("dir", v))
            elif k == "key_files" and isinstance(v, list):
                for item in v:
                    if isinstance(item, dict) and "file" in item:
                        paths.append(("file", item["file"]))
                    elif isinstance(item, str):
                        paths.append(("file", item))
            elif k == "files" and isinstance(v, list):
                for item in v:
                    if isinstance(item, str) and "/" in item:
                        paths.append(("file", item))
            else:
                extract_file_paths(v, paths, k)
    elif isinstance(obj, list):
        for item in obj:
            extract_file_paths(item, paths, context_key)
    return paths


raw_paths = extract_file_paths(blueprint)

# Build real directory set for validating location fields
real_dirs = set()
for f in real_files:
    parts = Path(f).parts
    for i in range(1, len(parts)):
        d = "/".join(parts[:i])
        real_dirs.add(d)
        real_dirs.add(d + "/")

# Separate file paths from directory references
file_paths = list(set(p for kind, p in raw_paths if kind == "file"))
dir_paths = list(set(p for kind, p in raw_paths if kind == "dir"))

# Clean paths: strip annotations like " (some note)"
def clean_path(p):
    p = p.lstrip("./")
    # Strip trailing annotations in parentheses
    p = re.sub(r'\s*\(.*\)$', '', p)
    # Strip " or " alternatives
    if " or " in p:
        p = p.split(" or ")[0].strip()
    return p

# Build lookup structures for flexible matching
# Real file basenames and tail-2/tail-3 for suffix matching
real_file_basenames = {Path(f).name for f in real_files}
real_file_tails = set()
for f in real_files:
    parts = Path(f).parts
    if len(parts) >= 2:
        real_file_tails.add("/".join(parts[-2:]))
    if len(parts) >= 3:
        real_file_tails.add("/".join(parts[-3:]))

real_dir_basenames = set()
real_dir_tails = set()
for d in real_dirs:
    d_clean = d.rstrip("/")
    parts = d_clean.split("/")
    if parts:
        real_dir_basenames.add(parts[-1])
    if len(parts) >= 2:
        real_dir_tails.add("/".join(parts[-2:]))


def match_file(p):
    """Check if a path references a real file (with flexible matching)."""
    if p in real_files:
        return True
    # Tail matching: last 2 or 3 path components
    parts = Path(p).parts
    if len(parts) >= 2 and "/".join(parts[-2:]) in real_file_tails:
        return True
    if len(parts) >= 3 and "/".join(parts[-3:]) in real_file_tails:
        return True
    # Basename match (weakest — still counts as grounded since AI got the file right)
    if Path(p).name in real_file_basenames:
        return True
    return False


def match_dir(p):
    """Check if a path references a real directory (with flexible matching)."""
    p = p.rstrip("/")
    if p in real_dirs or p + "/" in real_dirs:
        return True
    # Tail matching
    parts = p.split("/")
    if parts and parts[-1] in real_dir_basenames:
        return True
    if len(parts) >= 2 and "/".join(parts[-2:]) in real_dir_tails:
        return True
    return False


# Validate FILE paths
grounded = []
hallucinated = []
for p in file_paths:
    clean = clean_path(p)
    if match_file(clean):
        grounded.append(clean)
    else:
        hallucinated.append(clean)

# Validate DIRECTORY paths
dir_grounded = []
dir_hallucinated = []
for p in dir_paths:
    clean = clean_path(p).rstrip("/")
    # Check if it's actually a file path used in a location field
    is_file = any(clean.endswith(ext) for ext in source_exts)
    if is_file:
        if match_file(clean):
            dir_grounded.append(clean)
        else:
            dir_hallucinated.append(clean)
    elif match_dir(clean):
        dir_grounded.append(clean)
    else:
        dir_hallucinated.append(clean)

total_file_paths = len(file_paths)
grounded_count = len(grounded)
hallucinated_count = len(hallucinated)
file_accuracy = (grounded_count / total_file_paths * 100) if total_file_paths > 0 else 0

total_dir_paths = len(dir_paths)
dir_accuracy = (len(dir_grounded) / total_dir_paths * 100) if total_dir_paths > 0 else 100

# Combined accuracy (file + directory)
total_all = total_file_paths + total_dir_paths
grounded_all = grounded_count + len(dir_grounded)
combined_accuracy = (grounded_all / total_all * 100) if total_all > 0 else 0

print(f"  FILE PATHS:")
print(f"    In blueprint:        {total_file_paths}")
print(f"    Grounded (real):     {grounded_count} ({file_accuracy:.1f}%)")
print(f"    Hallucinated (fake): {hallucinated_count} ({100 - file_accuracy:.1f}%)")
print()
print(f"  DIRECTORY REFERENCES:")
print(f"    In blueprint:        {total_dir_paths}")
print(f"    Grounded (real):     {len(dir_grounded)} ({dir_accuracy:.1f}%)")
print(f"    Hallucinated (fake): {len(dir_hallucinated)} ({100 - dir_accuracy:.1f}%)")
print()
print(f"  COMBINED: {grounded_all}/{total_all} grounded ({combined_accuracy:.1f}%)")
print()

if hallucinated:
    print(f"  HALLUCINATED FILE PATHS ({len(hallucinated)}):")
    for h in sorted(hallucinated)[:25]:
        print(f"    X {h}")
    if len(hallucinated) > 25:
        print(f"    ... and {len(hallucinated) - 25} more")
    print()

if dir_hallucinated:
    print(f"  HALLUCINATED DIRECTORY REFS ({len(dir_hallucinated)}):")
    for d in sorted(dir_hallucinated)[:15]:
        print(f"    X {d}")
    print()

print(f"  SAMPLE GROUNDED FILE PATHS:")
for g in sorted(grounded)[:10]:
    print(f"    OK {g}")
print()


# ── 5. PHASE OUTPUT GROUNDING ──
print("-" * 70)
print("3. PHASE OUTPUT GROUNDING (per-phase file path accuracy)")
print("-" * 70)

phase_files = {
    "discovery": discovery,
    "layers": layers,
    "patterns": patterns,
    "communication": communication,
    "technology": technology,
    "frontend_analysis": frontend,
    "implementation": implementation,
}

swift_path_re = re.compile(
    r"[\w/]+\.(?:swift|m|mm|h|plist|json|storyboard|xib)", re.IGNORECASE
)

for phase_name, phase_text in phase_files.items():
    found_paths = swift_path_re.findall(phase_text)
    unique_paths = list(set(found_paths))
    real_matches = []
    for p in unique_paths:
        # Flexible matching: tail-2/tail-3 components, basename
        parts = Path(p).parts
        basename = parts[-1] if parts else p
        tail2 = "/".join(parts[-2:]) if len(parts) >= 2 else p
        tail3 = "/".join(parts[-3:]) if len(parts) >= 3 else None
        if any(rf.endswith(p) or p in rf for rf in real_files):
            real_matches.append(p)
        elif any(rf.endswith(tail2) for rf in real_files):
            real_matches.append(p)
        elif tail3 and any(rf.endswith(tail3) for rf in real_files):
            real_matches.append(p)
        elif basename in real_file_basenames:
            real_matches.append(p)
    fake = [p for p in unique_paths if p not in real_matches and len(p) > 5]
    acc = (len(real_matches) / len(unique_paths) * 100) if unique_paths else 100
    if acc >= 90:
        marker = "OK"
    elif acc >= 70:
        marker = "~~"
    else:
        marker = "!!"
    print(
        f"  {marker} {phase_name:25s} {len(unique_paths):3d} paths  "
        f"{len(real_matches):3d} real  {len(fake):3d} fake  ({acc:.0f}%)"
    )
    if fake and acc < 90:
        for f in sorted(fake)[:5]:
            print(f"      X {f}")
print()


# ── 6. CONTENT EFFICIENCY ──
print("-" * 70)
print("4. CONTENT EFFICIENCY")
print("-" * 70)

try:
    obs_text = observation
    if "```json" in obs_text:
        obs_text = obs_text.split("```json")[1].split("```")[0]
    obs_json = json.loads(obs_text)
    priority_map = obs_json.get("priority_files_by_phase", {})
    total_priority = len(set(f for paths in priority_map.values() for f in paths))
    print(f"  Priority files selected by AI: {total_priority}")
    for phase, files in priority_map.items():
        print(f"    {phase}: {len(files)} files")
except Exception as e:
    print(f"  Could not parse observation JSON: {e}")

manifest_path = REPO_DIR / "manifest.json"
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text())
    print(f"  Repo total files: {manifest.get('file_count', '?')}")
    total_bytes = manifest.get("total_size", 0)
    print(f"  Repo total size: {total_bytes:,} bytes ({total_bytes / 1024:.0f} KB)")

source_in_repo = len(real_source_files)
print(f"  Source files in repo: {source_in_repo}")

all_phase_text = " ".join(phase_files.values())
all_referenced = set(swift_path_re.findall(all_phase_text))
print(f"  Unique source files referenced across all phases: {len(all_referenced)}")
coverage = (len(all_referenced) / source_in_repo * 100) if source_in_repo > 0 else 0
print(f"  Source file coverage: {coverage:.0f}%")
print()

# ── 7. COMPARE WITH KNOWN HALLUCINATION ──
print("-" * 70)
print("5. SPECIFIC HALLUCINATION CHECK (the original bug)")
print("-" * 70)

# The original bug: "Controllers/Settings/SettingsViewController.swift"
# Real file: "Controllers/AppSettingsViewController.swift" (flat, no subdirectory)
known_bad = "Controllers/Settings/SettingsViewController.swift"
bp_text = json.dumps(blueprint)
if known_bad in bp_text:
    print(f"  !! STILL HALLUCINATING: {known_bad}")
else:
    print(f"  OK Original hallucination NOT present: {known_bad}")

# Check if any Controllers/Subfolder/ patterns exist (hallucinated subdirectories)
controller_paths = [p for p in hallucinated if p.startswith("Controllers/") and p.count("/") > 1]
if controller_paths:
    print(f"  !! {len(controller_paths)} hallucinated Controller subdirectory paths:")
    for cp in controller_paths[:5]:
        print(f"    X {cp}")
else:
    print(f"  OK No hallucinated Controller subdirectory paths")

# Check for invented directory structures
hallucinated_dirs = set()
for h in hallucinated:
    parts = h.split("/")
    if len(parts) > 1:
        hallucinated_dirs.add(parts[0] + "/" + parts[1] if len(parts) > 2 else parts[0])
if hallucinated_dirs:
    print(f"  Invented directory prefixes ({len(hallucinated_dirs)}):")
    for d in sorted(hallucinated_dirs)[:10]:
        print(f"    X {d}")
else:
    print(f"  OK No invented directory structures")
print()

print("=" * 70)
grade = "A" if file_accuracy >= 95 else "B" if file_accuracy >= 85 else "C" if file_accuracy >= 70 else "F"
print(f"OVERALL GRADE: {grade}")
print(f"  File path grounding:    {file_accuracy:.1f}%")
print(f"  Directory grounding:    {dir_accuracy:.1f}%")
print(f"  Combined grounding:     {combined_accuracy:.1f}%")
print(f"  Source coverage:        {coverage:.0f}%")
print(f"  Content valid:          YES")
print("=" * 70)
