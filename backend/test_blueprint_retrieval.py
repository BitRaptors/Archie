"""
Quick test script to validate blueprint retrieval.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.container import Container
from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
from infrastructure.storage.local_storage import LocalStorage
from config.settings import get_settings


async def test_blueprint_retrieval(analysis_id: str):
    """Test blueprint retrieval for a specific analysis."""
    print(f"\n{'='*80}")
    print(f"Testing Blueprint Retrieval for Analysis: {analysis_id}")
    print(f"{'='*80}\n")
    
    # Initialize container
    container = Container()
    await container.init_resources()
    
    try:
        # Get analysis
        supabase_client = await container.supabase_client()
        analysis_repo = SupabaseAnalysisRepository(client=supabase_client)
        analysis = await analysis_repo.get_by_id(analysis_id)
        
        if not analysis:
            print(f"✗ Analysis not found: {analysis_id}")
            return
        
        print(f"✓ Analysis found:")
        print(f"  - ID: {analysis.id}")
        print(f"  - Repository ID: {analysis.repository_id}")
        print(f"  - Status: {analysis.status}")
        print(f"  - Progress: {analysis.progress_percentage}%")
        
        if analysis.status != "completed":
            print(f"\n✗ Analysis is not completed. Status: {analysis.status}")
            return
        
        # Check storage
        storage = container.storage()
        settings = get_settings()
        print(f"\n✓ Storage initialized:")
        print(f"  - Base path: {storage._base_path}")
        print(f"  - Settings path: {settings.storage_path}")
        
        # Check for blueprint
        blueprint_path = f"blueprints/{analysis.repository_id}/backend_blueprint.md"
        print(f"\n✓ Checking for blueprint:")
        print(f"  - Path: {blueprint_path}")
        
        file_exists = await storage.exists(blueprint_path)
        print(f"  - Exists: {file_exists}")
        
        if not file_exists:
            # Check what files exist
            from pathlib import Path
            base_path = Path(settings.storage_path)
            repo_dir = base_path / f"blueprints/{analysis.repository_id}"
            
            if repo_dir.exists():
                files = list(repo_dir.glob("*"))
                print(f"\n✗ Blueprint not found. Files in directory:")
                for f in files:
                    print(f"    - {f.name} ({f.stat().st_size} bytes)")
            else:
                print(f"\n✗ Blueprint directory does not exist: {repo_dir}")
            return
        
        # Read blueprint
        print(f"\n✓ Reading blueprint...")
        blueprint_content = await storage.read(blueprint_path)
        if isinstance(blueprint_content, bytes):
            blueprint_content = blueprint_content.decode('utf-8')
        
        print(f"✓ Blueprint retrieved successfully!")
        print(f"  - Size: {len(blueprint_content)} characters")
        print(f"  - First 200 chars: {blueprint_content[:200]}...")
        
        print(f"\n{'='*80}")
        print("✓ TEST PASSED: Blueprint retrieval works correctly!")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        await container.shutdown_resources()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_blueprint_retrieval.py <analysis_id>")
        sys.exit(1)
    
    analysis_id = sys.argv[1]
    asyncio.run(test_blueprint_retrieval(analysis_id))

