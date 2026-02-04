#!/usr/bin/env python3
"""Test script to debug structure analyzer."""
import sys
import asyncio
from pathlib import Path

# Add backend/src to path for imports
backend_path = Path(__file__).parent
src_path = backend_path / "src"
sys.path.insert(0, str(src_path))

from infrastructure.analysis.structure_analyzer import StructureAnalyzer


async def test_structure_analyzer(repo_path: Path):
    """Test structure analyzer with a repository path."""
    print(f"Testing structure analyzer with path: {repo_path}")
    print(f"Path exists: {repo_path.exists()}")
    print(f"Path is directory: {repo_path.is_dir() if repo_path.exists() else 'N/A'}")
    
    if not repo_path.exists():
        print("ERROR: Repository path does not exist!")
        return
    
    if not repo_path.is_dir():
        print("ERROR: Repository path is not a directory!")
        return
    
    # Check what's actually in the directory
    try:
        items = list(repo_path.iterdir())
        print(f"\nFound {len(items)} items in root directory:")
        for item in items[:20]:  # Show first 20
            print(f"  - {item.name} ({'dir' if item.is_dir() else 'file'})")
    except Exception as e:
        print(f"ERROR listing directory: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test the analyzer
    analyzer = StructureAnalyzer()
    try:
        result = await analyzer.analyze(repo_path)
        
        print(f"\n=== Structure Analyzer Results ===")
        print(f"File tree count: {len(result.get('file_tree', []))}")
        print(f"Technologies: {result.get('technologies', [])}")
        print(f"Directory structure keys: {list(result.get('directory_structure', {}).keys())}")
        
        # Show first few files
        file_tree = result.get('file_tree', [])
        if file_tree:
            print(f"\nFirst 10 items in file_tree:")
            for item in file_tree[:10]:
                print(f"  - {item.get('path')} ({item.get('type')})")
        else:
            print("\nWARNING: file_tree is empty!")
            
            # Try manual walk to see what's wrong
            print("\n=== Manual Directory Walk ===")
            try:
                count = 0
                for root, dirs, files in repo_path.rglob('*'):
                    if count >= 20:
                        break
                    root_path = Path(root)
                    rel_path = root_path.relative_to(repo_path)
                    if not any(part.startswith('.') and part != '.git' for part in rel_path.parts):
                        print(f"  - {rel_path}")
                        count += 1
            except Exception as e:
                print(f"ERROR in manual walk: {e}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"ERROR analyzing structure: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test structure analyzer")
    parser.add_argument("path", type=str, help="Path to repository")
    args = parser.parse_args()
    
    repo_path = Path(args.path).resolve()
    asyncio.run(test_structure_analyzer(repo_path))

