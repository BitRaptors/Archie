#!/usr/bin/env python3
"""Unit test that replicates the exact analysis pipeline to debug 0 items issue."""
import sys
import asyncio
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv
import os
import tempfile

# Set up paths
backend_path = Path(__file__).parent
env_file = backend_path / ".env.local"
if env_file.exists():
    load_dotenv(str(env_file))
load_dotenv()

# Add backend/src to path
src_path = backend_path / "src"
sys.path.insert(0, str(src_path))

from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from infrastructure.storage.temp_storage import TempStorage
from config.settings import get_settings


async def test_exact_pipeline():
    """Test the exact pipeline that runs during actual analysis."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN not found")
        return False
    
    repo_full_name = "BitRaptors/mobilfox-backend"
    
    print(f"\n{'='*70}")
    print(f"TESTING EXACT ANALYSIS PIPELINE")
    print(f"Repository: {repo_full_name}")
    print(f"{'='*70}\n")
    
    # STEP 1: Simulate what happens in worker tasks.py
    print("=" * 70)
    print("STEP 1: Worker Setup (tasks.py)")
    print("=" * 70)
    
    # Create temp storage exactly like worker does
    temp_storage = TempStorage()
    temp_dir = temp_storage.get_base_path()
    
    # Log working directory
    cwd = os.getcwd()
    print(f"Current working directory: {cwd}")
    print(f"Temp storage base path: {temp_dir}")
    print(f"Temp dir exists: {temp_dir.exists()}")
    print(f"Temp dir absolute: {temp_dir.resolve()}")
    
    # STEP 2: Clone repository (simulate clone_repository)
    print(f"\n{'='*70}")
    print("STEP 2: Clone Repository (repository_service.clone_repository)")
    print("=" * 70)
    
    repo_path = temp_dir / repo_full_name.replace("/", "_")
    print(f"Target clone path: {repo_path}")
    print(f"Target path absolute: {repo_path.resolve()}")
    
    # Clean up if exists
    if repo_path.exists():
        print(f"Cleaning up existing clone at {repo_path}")
        shutil.rmtree(repo_path)
    
    # Ensure temp_dir exists
    temp_dir.mkdir(parents=True, exist_ok=True)
    print(f"Temp dir created/verified: {temp_dir.exists()}")
    
    # Clone
    clone_url = f"https://{token}@github.com/{repo_full_name}.git"
    print(f"Cloning from: {clone_url.split('@')[1]}")  # Don't show token
    print(f"Cloning to: {repo_path}")
    
    result = subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, str(repo_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    
    print(f"✓ Git clone completed (return code: {result.returncode})")
    
    # Verify clone (exactly like clone_repository does now)
    repo_path = repo_path.resolve()  # Resolve to absolute
    print(f"\nVerifying clone...")
    print(f"  Path exists: {repo_path.exists()}")
    print(f"  Path is_dir: {repo_path.is_dir()}")
    
    if not repo_path.exists():
        print("  ❌ ERROR: Path does not exist after clone!")
        return False
    
    if not repo_path.is_dir():
        print("  ❌ ERROR: Path is not a directory!")
        return False
    
    # Check content
    items = list(repo_path.iterdir())
    print(f"  Items in directory: {len(items)}")
    if len(items) == 0:
        print("  ❌ ERROR: Directory is empty after clone!")
        return False
    
    if items:
        all_items = [item.name for item in items]
        visible = [item.name for item in items if not item.name.startswith('.')]
        print(f"  All items (first 10): {all_items[:10]}")
        print(f"  Visible items: {visible[:10]}")
        print(f"  Hidden items: {len(all_items) - len(visible)}")
    
    # Check .git
    git_dir = repo_path / ".git"
    print(f"  .git exists: {git_dir.exists()}")
    
    # STEP 3: Simulate analysis_service.run_analysis Phase 1
    print(f"\n{'='*70}")
    print("STEP 3: Analysis Service Phase 1 (analysis_service.run_analysis)")
    print("=" * 70)
    
    # This is exactly what analysis_service does:
    print(f"Input repo_path: {repo_path}")
    print(f"Input type: {type(repo_path)}")
    
    # Convert to Path if needed and resolve (like analysis_service does)
    repo_path_obj = Path(repo_path) if not isinstance(repo_path, Path) else repo_path
    repo_path_obj = repo_path_obj.resolve()
    
    print(f"After conversion: {repo_path_obj}")
    print(f"After resolve: {repo_path_obj}")
    print(f"Exists: {repo_path_obj.exists()}")
    print(f"Is_dir: {repo_path_obj.is_dir()}")
    
    # Check directory contents (like analysis_service does)
    items_check = list(repo_path_obj.iterdir())
    print(f"\nDirectory check (repo_path_obj.iterdir()):")
    print(f"  Items found: {len(items_check)}")
    if items_check:
        all_items_check = [item.name for item in items_check]
        print(f"  All items: {all_items_check[:10]}")
    
    # STEP 4: Call structure analyzer (exactly like analysis_service does)
    print(f"\n{'='*70}")
    print("STEP 4: Structure Analyzer (structure_analyzer.analyze)")
    print("=" * 70)
    
    print(f"Calling analyzer.analyze({repo_path_obj})")
    print(f"  Path type: {type(repo_path_obj)}")
    print(f"  Path value: {repo_path_obj}")
    print(f"  Path exists: {repo_path_obj.exists()}")
    print(f"  Path is_dir: {repo_path_obj.is_dir()}")
    
    analyzer = StructureAnalyzer()
    
    try:
        structure_data = await analyzer.analyze(repo_path_obj)
        print(f"\nStructure analyzer returned:")
        print(f"  Data is None: {structure_data is None}")
        print(f"  Data type: {type(structure_data)}")
        
        if structure_data:
            print(f"  Keys: {list(structure_data.keys())}")
            file_tree = structure_data.get("file_tree", [])
            print(f"  File tree length: {len(file_tree)}")
            
            if file_tree:
                file_count = len([n for n in file_tree if n.get("type") == "file"])
                dir_count = len([n for n in file_tree if n.get("type") == "directory"])
                print(f"  Files: {file_count}, Directories: {dir_count}")
                print(f"\n  First 10 items in file_tree:")
                for i, item in enumerate(file_tree[:10], 1):
                    print(f"    {i}. {item.get('path')} ({item.get('type')})")
            else:
                print("  ❌ WARNING: file_tree is empty!")
                
                # Debug why it's empty
                print("\n  Debugging empty file_tree:")
                print(f"    Path being walked: {repo_path_obj}")
                print(f"    Path exists: {repo_path_obj.exists()}")
                print(f"    Path is_dir: {repo_path_obj.is_dir()}")
                
                # Manual walk
                try:
                    manual_items = list(repo_path_obj.iterdir())
                    print(f"    Manual iterdir() items: {len(manual_items)}")
                    for item in manual_items[:10]:
                        print(f"      - {item.name} ({'dir' if item.is_dir() else 'file'})")
                except Exception as e:
                    print(f"    ERROR in manual walk: {e}")
        else:
            print("  ❌ ERROR: structure_data is None!")
            return False
            
    except Exception as e:
        print(f"  ❌ EXCEPTION in structure analyzer: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # STEP 5: Simulate Phase 2 operations
    print(f"\n{'='*70}")
    print("STEP 5: Phase 2 - Dependency/Config/Code Sample Extraction")
    print("=" * 70)
    
    # Test dependency extraction (using actual method from analysis_service)
    print("\nTesting dependency extraction...")
    print("  Searching recursively for dependency files...")
    
    ignore_patterns = {
        "node_modules", ".git", "venv", "__pycache__", ".next",
        "dist", "build", "target", ".gradle", ".idea", ".venv",
        "env", ".env", "vendor", "coverage", ".nyc_output",
    }
    
    dependency_files = []
    
    # Find all dependency files recursively
    for pattern, ext in [("requirements.txt", ""), ("package.json", "json"), ("pyproject.toml", "toml"), ("Gemfile", "ruby"), ("Cargo.toml", "toml"), ("go.mod", "")]:
        for dep_file in repo_path_obj.rglob(pattern):
            # Skip if in ignored directory
            if any(p in str(dep_file) for p in ignore_patterns):
                continue
            
            try:
                rel_path = dep_file.relative_to(repo_path_obj)
                dependency_files.append(str(rel_path))
                print(f"    ✓ Found {rel_path}")
            except Exception:
                continue
    
    print(f"  Dependencies extracted: {len(dependency_files)} files")
    if dependency_files:
        print(f"  Files found: {', '.join(dependency_files[:5])}{'...' if len(dependency_files) > 5 else ''}")
    
    # Test config file extraction (using actual method logic)
    print("\nTesting config file extraction...")
    config_files = {}
    ignore_patterns = {
        "node_modules", ".git", "venv", "__pycache__", ".next",
        "dist", "build", "target", ".gradle", ".idea", ".venv",
        "env", ".env", "vendor", "coverage", ".nyc_output",
    }
    
    exact_config_patterns = [
        ".env.example", ".env.sample", ".env.template",
        "docker-compose.yml", "docker-compose.yaml", "Dockerfile", ".dockerignore",
        "firebase.json", ".firebaserc", "firestore.rules",
        "vercel.json", "netlify.toml", ".vercelignore", ".netlifyignore",
        "config.py", "settings.py", "setup.py", "setup.cfg", "tox.ini", "pytest.ini",
        "tsconfig.json", "jsconfig.json",
        ".gitlab-ci.yml",
        ".editorconfig", ".gitignore",
    ]
    
    config_base_names = [
        "webpack.config", "vite.config", "next.config", "nuxt.config",
        "rollup.config", "esbuild.config", "swc.config",
        "tailwind.config", "postcss.config",
        "jest.config", "vitest.config",
        ".eslintrc", ".prettierrc",
        "tsconfig",
    ]
    
    config_extensions = [".json", ".js", ".ts", ".mjs", ".cjs", ".yml", ".yaml", ".toml"]
    
    # Search for exact patterns
    for pattern in exact_config_patterns:
        for config_file in repo_path_obj.rglob(pattern):
            if any(ip in str(config_file) for ip in ignore_patterns):
                continue
            try:
                rel_path = config_file.relative_to(repo_path_obj)
                config_files[str(rel_path)] = True
                print(f"  ✓ Found {rel_path}")
            except Exception:
                pass
    
    # Search for base names with extensions
    for base_name in config_base_names:
        for ext in config_extensions:
            pattern = f"{base_name}{ext}"
            for config_file in repo_path_obj.rglob(pattern):
                if any(ip in str(config_file) for ip in ignore_patterns):
                    continue
                try:
                    rel_path = config_file.relative_to(repo_path_obj)
                    if str(rel_path) not in config_files:
                        config_files[str(rel_path)] = True
                        print(f"  ✓ Found {rel_path}")
                except Exception:
                    pass
    
    # Check .github/workflows
    workflows_dir = repo_path_obj / ".github" / "workflows"
    if workflows_dir.exists():
        for wf in workflows_dir.rglob("*.yml"):
            if any(ip in str(wf) for ip in ignore_patterns):
                continue
            try:
                rel_path = wf.relative_to(repo_path_obj)
                if str(rel_path) not in config_files:
                    config_files[str(rel_path)] = True
                    print(f"  ✓ Found {rel_path}")
            except Exception:
                pass
        for wf in workflows_dir.rglob("*.yaml"):
            if any(ip in str(wf) for ip in ignore_patterns):
                continue
            try:
                rel_path = wf.relative_to(repo_path_obj)
                if str(rel_path) not in config_files:
                    config_files[str(rel_path)] = True
                    print(f"  ✓ Found {rel_path}")
            except Exception:
                pass
    
    # Check pyproject.toml
    for pyproject in repo_path_obj.rglob("pyproject.toml"):
        if any(ip in str(pyproject) for ip in ignore_patterns):
            continue
        try:
            rel_path = pyproject.relative_to(repo_path_obj)
            if str(rel_path) not in config_files:
                config_files[str(rel_path)] = True
                print(f"  ✓ Found {rel_path}")
        except Exception:
            pass
    
    print(f"  Config files extracted: {len(config_files)} files")
    
    # Test code sample extraction
    print("\nTesting code sample extraction...")
    code_samples = {}
    file_tree = structure_data.get("file_tree", []) if structure_data else []
    
    files_to_sample = []
    for node in file_tree:
        if node.get("type") == "file":
            file_path = node.get("path", node.get("name", ""))
            if any(ext in str(file_path) for ext in [".py", ".ts", ".tsx", ".js", ".jsx"]):
                files_to_sample.append(file_path)
        if len(files_to_sample) >= 50:
            break
    
    print(f"  Files eligible for sampling: {len(files_to_sample)}")
    
    for file_path in files_to_sample[:10]:
        full_path = repo_path_obj / file_path
        if full_path.exists() and full_path.is_file():
            try:
                content = full_path.read_text()
                lines = content.split('\n')[:500]
                code_samples[str(file_path)] = '\n'.join(lines)
                print(f"  ✓ Extracted {file_path}")
            except Exception as e:
                print(f"  ✗ Error reading {file_path}: {e}")
    
    print(f"  Code samples extracted: {len(code_samples)} files")
    
    # Final Results
    print(f"\n{'='*70}")
    print("FINAL RESULTS")
    print("=" * 70)
    
    if structure_data:
        file_tree = structure_data.get("file_tree", [])
        file_count = len([n for n in file_tree if n.get("type") == "file"])
        dir_count = len([n for n in file_tree if n.get("type") == "directory"])
        
        print(f"Structure scan:")
        print(f"  ✓ Files: {file_count}")
        print(f"  ✓ Directories: {dir_count}")
        print(f"  ✓ Total items: {len(file_tree)}")
        
        print(f"\nPhase 2 extraction:")
        print(f"  Dependencies: {dep_count} files")
        print(f"  Config files: {len(config_files)} files")
        print(f"  Code samples: {len(code_samples)} files")
        
        if file_count == 0 or dir_count == 0:
            print(f"\n❌ TEST FAILED: Found 0 files or 0 directories!")
            print("   This matches the issue - structure analyzer returned empty results")
            return False
        else:
            print(f"\n✓ TEST PASSED: Structure analyzer found files and directories")
            print("   If actual analysis shows 0, check path resolution differences")
            return True
    else:
        print("❌ TEST FAILED: structure_data is None")
        return False
    
    # Cleanup
    print("\nCleaning up...")
    if repo_path.exists():
        shutil.rmtree(repo_path)


if __name__ == "__main__":
    success = asyncio.run(test_exact_pipeline())
    sys.exit(0 if success else 1)

