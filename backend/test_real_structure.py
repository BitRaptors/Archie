#!/usr/bin/env python3
"""Test structure analyzer with real repository."""
import sys
import asyncio
import subprocess
import shutil
from pathlib import Path
from dotenv import load_dotenv
import os

# Set up paths first
backend_path = Path(__file__).parent

# Load environment variables from backend/.env.local
env_file = backend_path / ".env.local"
if env_file.exists():
    load_dotenv(str(env_file))
else:
    # Try parent directory
    env_file = backend_path.parent / ".env.local"
    if env_file.exists():
        load_dotenv(str(env_file))
load_dotenv()  # Also load from environment

# Add backend/src to path for imports
src_path = backend_path / "src"
sys.path.insert(0, str(src_path))

from infrastructure.analysis.structure_analyzer import StructureAnalyzer


async def test_real_repository():
    """Test structure analyzer with BitRaptors/Mind1.Web repository."""
    # Get GitHub token
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("ERROR: GITHUB_TOKEN not found in environment variables")
        print("Please set GITHUB_TOKEN in .env.local or environment")
        return
    
    # Test with both repositories
    repo_full_name = os.getenv("TEST_REPO", "BitRaptors/Mind1.Web")
    temp_dir = backend_path / "test_temp"
    temp_dir.mkdir(exist_ok=True)
    
    # Clean up any existing clone
    repo_path = temp_dir / repo_full_name.replace("/", "_")
    if repo_path.exists():
        print(f"Cleaning up existing clone at {repo_path}")
        shutil.rmtree(repo_path)
    
    print(f"\n{'='*60}")
    print(f"Testing Structure Analyzer with Real Repository")
    print(f"{'='*60}")
    print(f"Repository: {repo_full_name}")
    print(f"Temp directory: {temp_dir}")
    print(f"Clone path: {repo_path}")
    print()
    
    try:
        # Clone repository
        print("Step 1: Cloning repository...")
        clone_url = f"https://{token}@github.com/{repo_full_name}.git"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"✓ Repository cloned successfully")
        
        # Verify clone
        print("\nStep 2: Verifying clone...")
        if not repo_path.exists():
            print(f"ERROR: Repository path does not exist: {repo_path}")
            return
        if not repo_path.is_dir():
            print(f"ERROR: Repository path is not a directory: {repo_path}")
            return
        
        # Check what's in the directory
        items = list(repo_path.iterdir())
        print(f"✓ Repository directory contains {len(items)} items at root level")
        
        # Show first few items
        visible_items = [item.name for item in items if not item.name.startswith('.')]
        if visible_items:
            print(f"  Sample items: {', '.join(visible_items[:10])}")
        else:
            print("  WARNING: No visible items found (all may be hidden)")
        
        # Check .git directory
        git_dir = repo_path / ".git"
        print(f"  .git directory exists: {git_dir.exists()}")
        
        # Test structure analyzer
        print("\nStep 3: Running structure analyzer...")
        analyzer = StructureAnalyzer()
        structure_data = await analyzer.analyze(repo_path)
        
        print(f"\n{'='*60}")
        print(f"Structure Analyzer Results")
        print(f"{'='*60}")
        
        file_tree = structure_data.get("file_tree", [])
        file_count = len([node for node in file_tree if node.get("type") == "file"])
        dir_count = len([node for node in file_tree if node.get("type") == "directory"])
        
        print(f"Total items in file_tree: {len(file_tree)}")
        print(f"Files found: {file_count}")
        print(f"Directories found: {dir_count}")
        print(f"Technologies detected: {structure_data.get('technologies', [])}")
        
        if file_tree:
            print(f"\nFirst 20 items in file_tree:")
            for i, item in enumerate(file_tree[:20], 1):
                item_type = item.get("type", "unknown")
                item_path = item.get("path", "unknown")
                item_name = item.get("name", "unknown")
                icon = "📁" if item_type == "directory" else "📄"
                print(f"  {i:2}. {icon} {item_path} ({item_type})")
            
            if len(file_tree) > 20:
                print(f"  ... and {len(file_tree) - 20} more items")
        else:
            print("\n❌ WARNING: file_tree is EMPTY!")
            print("\nDebugging information:")
            print(f"  Repository path: {repo_path}")
            print(f"  Path exists: {repo_path.exists()}")
            print(f"  Path is directory: {repo_path.is_dir()}")
            print(f"  Items in directory: {len(items)}")
            print(f"  Visible items: {len(visible_items)}")
            print(f"  Hidden items: {len(items) - len(visible_items)}")
            
            # Try manual walk
            print("\n  Trying manual directory walk...")
            try:
                count = 0
                for root, dirs, files in repo_path.rglob('*'):
                    if count >= 20:
                        break
                    root_path = Path(root)
                    try:
                        rel_path = root_path.relative_to(repo_path)
                        # Check if path should be skipped
                        if any(part.startswith('.') and part != '.git' for part in rel_path.parts):
                            continue
                        print(f"    - {rel_path}")
                        count += 1
                    except ValueError:
                        pass
            except Exception as e:
                print(f"    ERROR in manual walk: {e}")
                import traceback
                traceback.print_exc()
        
        # Test dependency extraction
        print(f"\n{'='*60}")
        print(f"Testing Dependency Extraction")
        print(f"{'='*60}")
        
        dependencies_found = []
        for dep_file in ["package.json", "requirements.txt", "pyproject.toml", "go.mod", "Cargo.toml"]:
            dep_path = repo_path / dep_file
            if dep_path.exists():
                dependencies_found.append(dep_file)
                print(f"✓ Found {dep_file}")
        
        if not dependencies_found:
            print("⚠ No dependency files found")
        else:
            print(f"Total dependency files: {len(dependencies_found)}")
        
        # Test config file extraction
        print(f"\n{'='*60}")
        print(f"Testing Config File Extraction")
        print(f"{'='*60}")
        
        config_patterns = [".env.example", "config.py", "settings.py", "docker-compose.yml", "Dockerfile"]
        config_files_found = []
        for pattern in config_patterns:
            config_path = repo_path / pattern
            if config_path.exists():
                config_files_found.append(pattern)
                print(f"✓ Found {pattern}")
        
        if not config_files_found:
            print("⚠ No config files found (this is normal for some repos)")
        else:
            print(f"Total config files: {len(config_files_found)}")
        
        print(f"\n{'='*60}")
        if file_count == 0 and dir_count == 0:
            print("❌ TEST FAILED: Structure analyzer found 0 files/directories")
            print("   This matches the issue reported - needs further investigation")
            return False
        else:
            print("✓ TEST PASSED: Structure analyzer found files and directories")
            return True
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERROR: Git clone failed")
        print(f"  Command: {' '.join(e.cmd)}")
        print(f"  Return code: {e.returncode}")
        print(f"  stdout: {e.stdout}")
        print(f"  stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        print(f"\nCleaning up test repository...")
        if repo_path.exists():
            shutil.rmtree(repo_path)
        print("✓ Cleanup complete")


if __name__ == "__main__":
    success = asyncio.run(test_real_repository())
    sys.exit(0 if success else 1)

