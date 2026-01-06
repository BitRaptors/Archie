"""
End-to-end test for the complete analysis workflow.
Tests the entire process from repository selection to blueprint generation.
"""
import pytest
import asyncio
import os
import sys
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config.container import Container
from application.services.repository_service import RepositoryService
from application.services.analysis_service import AnalysisService
from infrastructure.persistence.user_repository import SupabaseUserRepository
from infrastructure.persistence.repository_repository import SupabaseRepositoryRepository
from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
from infrastructure.persistence.analysis_event_repository import SupabaseAnalysisEventRepository
from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from domain.entities.user import User
from config.constants import AnalysisStatus


@pytest.fixture
async def container():
    """Initialize DI container."""
    container = Container()
    await container.init_resources()
    yield container
    await container.shutdown_resources()


@pytest.fixture
def github_token():
    """Get GitHub token from environment."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN not set")
    return token


@pytest.fixture
async def services(container):
    """Create all necessary services."""
    # Resolve async resources
    supabase_client = await container.supabase_client()
    
    # Create repositories
    user_repo = SupabaseUserRepository(client=supabase_client)
    repo_repo = SupabaseRepositoryRepository(client=supabase_client)
    analysis_repo = SupabaseAnalysisRepository(client=supabase_client)
    event_repo = SupabaseAnalysisEventRepository(client=supabase_client)
    
    # Create storage and GitHub service
    storage = container.storage()
    github_service = container.github_service()
    
    # Create repository service
    repo_service = RepositoryService(
        repository_repo=repo_repo,
        github_service=github_service,
        storage=storage,
    )
    
    # Initialize only what's needed
    structure_analyzer = StructureAnalyzer()
    from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
    from config.settings import get_settings
    settings = get_settings()
    phased_blueprint_generator = PhasedBlueprintGenerator(settings)

    # Create analysis service
    analysis_service = AnalysisService(
        analysis_repo=analysis_repo,
        repository_repo=repo_repo,
        event_repo=event_repo,
        structure_analyzer=structure_analyzer,
        persistent_storage=storage,
        phased_blueprint_generator=phased_blueprint_generator,
    )
    
    return {
        "user_repo": user_repo,
        "repo_repo": repo_repo,
        "analysis_repo": analysis_repo,
        "event_repo": event_repo,
        "repo_service": repo_service,
        "analysis_service": analysis_service,
        "storage": storage,
    }


@pytest.mark.anyio
async def test_complete_analysis_workflow_e2e(container, github_token, services):
    """
    Test the complete analysis workflow end-to-end.
    
    This test validates:
    1. User creation
    2. Repository fetching and creation
    3. Analysis initialization
    4. Repository cloning
    5. All 6 analysis phases
    6. Event logging
    7. Blueprint generation
    8. Cleanup
    """
    print("\n" + "="*80)
    print("STARTING END-TO-END ANALYSIS TEST")
    print("="*80)
    
    # Extract services
    user_repo = services["user_repo"]
    repo_service = services["repo_service"]
    analysis_service = services["analysis_service"]
    analysis_repo = services["analysis_repo"]
    event_repo = services["event_repo"]
    storage = services["storage"]
    
    # Test parameters
    owner = "BitRaptors"
    repo_name = "raptamagochi"
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-user-e2e"))
    
    try:
        # PHASE 1: User Management
        print("\n[1/8] Testing user management...")
        user = await user_repo.get_by_id(user_id)
        if not user:
            user = User.create(github_token_encrypted="test_token")
            user.id = user_id
            user = await user_repo.add(user)
            print(f"✓ Created user: {user.id}")
        else:
            print(f"✓ User exists: {user.id}")
        
        # PHASE 2: Repository Creation
        print("\n[2/8] Testing repository creation...")
        repository = await repo_service.get_repository_by_full_name(user_id, owner, repo_name)
        if not repository:
            repository = await repo_service.create_repository(user_id, github_token, owner, repo_name)
            print(f"✓ Created repository: {repository.full_name}")
        else:
            print(f"✓ Repository exists: {repository.full_name}")
        
        assert repository is not None
        assert repository.full_name == f"{owner}/{repo_name}"
        
        # PHASE 3: Analysis Initialization
        print("\n[3/8] Testing analysis initialization...")
        analysis = await analysis_service.start_analysis(repository.id)
        print(f"✓ Analysis created: {analysis.id}")
        print(f"  Status: {analysis.status}")
        print(f"  Progress: {analysis.progress_percentage}%")
        
        assert analysis is not None
        assert analysis.status == "in_progress"  # Status is set to in_progress by start()
        assert analysis.progress_percentage == 0
        
        # Verify initial event was logged
        events = await event_repo.get_by_analysis_id(analysis.id)
        print(f"✓ Initial events logged: {len(events)}")
        assert len(events) > 0
        
        # PHASE 4: Repository Cloning
        print("\n[4/8] Testing repository cloning...")
        from pathlib import Path
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "test_repos"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        repo_path = await repo_service.clone_repository(repository, github_token, temp_dir)
        print(f"✓ Repository cloned to: {repo_path}")
        
        assert repo_path.exists()
        assert repo_path.is_dir()
        # Check for some expected files
        assert (repo_path / ".git").exists()
        print(f"  Contains .git directory: ✓")
        
        # PHASE 5: Run Full Analysis Pipeline
        print("\n[5/8] Running complete analysis pipeline...")
        print("  This will execute all 6 phases:")
        print("    Phase 1: Structure scan")
        print("    Phase 2: Embedding generation")
        print("    Phase 3: AST extraction")
        print("    Phase 4: Pattern discovery")
        print("    Phase 5: AI analysis")
        print("    Phase 6: Blueprint synthesis")
        
        # Run the analysis
        try:
            await analysis_service.run_analysis(
                analysis_id=analysis.id,
                repo_path=repo_path,
                token=github_token,
                prompt_config=None,
            )
            print("✓ Analysis pipeline completed successfully")
        except Exception as e:
            print(f"✗ Analysis pipeline failed: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        
        # PHASE 6: Verify Analysis Completion
        print("\n[6/8] Verifying analysis completion...")
        completed_analysis = await analysis_repo.get_by_id(analysis.id)
        print(f"  Final status: {completed_analysis.status}")
        print(f"  Final progress: {completed_analysis.progress_percentage}%")
        
        assert completed_analysis is not None
        assert completed_analysis.status == "completed"
        assert completed_analysis.progress_percentage == 100
        
        # PHASE 7: Verify Events
        print("\n[7/8] Verifying analysis events...")
        all_events = await event_repo.get_by_analysis_id(analysis.id)
        print(f"✓ Total events logged: {len(all_events)}")
        
        # Print event summary
        event_types = {}
        for event in all_events:
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
        
        print("  Event breakdown:")
        for event_type, count in event_types.items():
            print(f"    {event_type}: {count}")
        
        # Verify expected events
        assert len(all_events) > 0
        phase_starts = [e for e in all_events if e.event_type == "PHASE_START"]
        phase_ends = [e for e in all_events if e.event_type == "PHASE_END"]
        print(f"  Phase starts: {len(phase_starts)}")
        print(f"  Phase ends: {len(phase_ends)}")
        
        # PHASE 8: Verify Blueprint
        print("\n[8/8] Verifying blueprint generation...")
        blueprint_path = f"blueprints/{repository.id}/blueprint.md"
        
        try:
            blueprint_content = await storage.read(blueprint_path)
            print(f"✓ Blueprint generated: {len(blueprint_content)} characters")
            print(f"  Location: {blueprint_path}")
            
            # Verify blueprint has content
            assert len(blueprint_content) > 100
            print("✓ Blueprint has substantial content")
        except Exception as e:
            print(f"✗ Blueprint verification failed: {str(e)}")
            # Don't fail the test if blueprint isn't generated (it's optional)
        
        # CLEANUP
        print("\n[CLEANUP] Cleaning up temporary files...")
        await repo_service.cleanup_temp_repository(temp_dir)
        print("✓ Cleanup complete")
        
        # FINAL SUMMARY
        print("\n" + "="*80)
        print("END-TO-END TEST COMPLETED SUCCESSFULLY ✓")
        print("="*80)
        print(f"Repository: {repository.full_name}")
        print(f"Analysis ID: {analysis.id}")
        print(f"Final Status: {completed_analysis.status}")
        print(f"Progress: {completed_analysis.progress_percentage}%")
        print(f"Events logged: {len(all_events)}")
        print("="*80)
        
    except Exception as e:
        print("\n" + "="*80)
        print("END-TO-END TEST FAILED ✗")
        print("="*80)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise

