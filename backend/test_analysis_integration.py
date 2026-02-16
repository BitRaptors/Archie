#!/usr/bin/env python3
"""Integration test to simulate actual analysis flow."""
import sys
import asyncio
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv
import os

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


async def test_analysis_flow():
    """Test the actual analysis flow to see where it breaks."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN not found")
        return False
    
    repo_full_name = "BitRaptors/mobilfox-backend"
    
    print(f"\n{'='*60}")
    print(f"Testing Analysis Flow Integration")
    print(f"{'='*60}\n")
    
    # Step 1: Create temp storage (like worker does)
    print("Step 1: Creating temp storage...")
    temp_storage = TempStorage()
    temp_dir = temp_storage.get_base_path()
    print(f"  Temp dir: {temp_dir}")
    print(f"  Temp dir exists: {temp_dir.exists()}")
    print(f"  Temp dir absolute: {temp_dir.resolve()}")
    
    # Step 2: Clone repository directly (simulating worker behavior)
    print("\nStep 2: Cloning repository...")
    repo_path = temp_dir / repo_full_name.replace("/", "_")
    
    if repo_path.exists():
        shutil.rmtree(repo_path)
    
    clone_url = f"https://{token}@github.com/{repo_full_name}.git"
    result = subprocess.run(
        ["git", "clone", "--depth", "1", clone_url, str(repo_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    
    repo_path = repo_path.resolve()
    print(f"  Cloned to: {repo_path}")
    print(f"  Path exists: {repo_path.exists()}")
    print(f"  Path is_dir: {repo_path.is_dir()}")
    
    items = list(repo_path.iterdir())
    print(f"  Items in directory: {len(items)}")
    if items:
        print(f"  Sample: {[item.name for item in items[:5]]}")
    
    # Step 3: Test structure analyzer (like analysis_service does)
    print("\nStep 3: Testing structure analyzer...")
    print(f"  Calling with path: {repo_path}")
    print(f"  Path type: {type(repo_path)}")
    print(f"  Path exists: {repo_path.exists()}")
    print(f"  Path is_dir: {repo_path.is_dir()}")
    
    analyzer = StructureAnalyzer()
    structure_data = await analyzer.analyze(repo_path)
    
    print(f"\n  Structure data returned: {bool(structure_data)}")
    if structure_data:
        file_tree = structure_data.get("file_tree", [])
        print(f"  File tree items: {len(file_tree)}")
        file_count = len([n for n in file_tree if n.get("type") == "file"])
        dir_count = len([n for n in file_tree if n.get("type") == "directory"])
        print(f"  Files: {file_count}, Directories: {dir_count}")
        
        if file_tree:
            print(f"  First 5 items: {[item.get('path') for item in file_tree[:5]]}")
        else:
            print("  WARNING: File tree is empty!")
            return False
    else:
        print("  ERROR: Structure data is None!")
        return False
    
    # Step 4: Test dependency extraction (simplified)
    print("\nStep 4: Testing dependency extraction...")
    dependencies = []
    requirements_file = repo_path / "requirements.txt"
    if requirements_file.exists():
        content = requirements_file.read_text()
        dependencies.append(f"**requirements.txt:**\n```\n{content[:1000]}\n```")
    package_json = repo_path / "package.json"
    if package_json.exists():
        content = package_json.read_text()
        dependencies.append(f"**package.json:**\n```json\n{content[:1000]}\n```")
    deps_text = "\n\n".join(dependencies) if dependencies else "No dependency files found"
    dep_count = deps_text.count("**") // 2 if deps_text and "No dependency files found" not in deps_text else 0
    print(f"  Dependencies found: {dep_count}")
    print(f"  Dependency text (first 200 chars): {deps_text[:200]}")
    
    # Cleanup
    print("\nCleaning up...")
    if repo_path.exists():
        shutil.rmtree(repo_path)
    
    print(f"\n{'='*60}")
    if file_count > 0:
        print("✓ TEST PASSED")
        return True
    else:
        print("❌ TEST FAILED: No files found")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_analysis_flow())
    sys.exit(0 if success else 1)

