"""Validate full analysis pipeline against gbrbks/architecture_mcp.

Runs the REAL pipeline end-to-end: clone → structure scan → embeddings →
phased AI analysis → blueprint storage. No mocks, no HTTP layer.

Usage:
    cd backend && source .venv/bin/activate
    PYTHONPATH=src python tests/integration/validate_pipeline.py
"""
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)

log = logging.getLogger("validate")


async def main():
    t0 = time.time()

    # ── 1. Boot DI container ────────────────────────────────────────
    log.info("Step 1: Initializing DI container...")
    from config.container import Container
    container = Container()
    await container.init_resources()
    db = await container.db()
    log.info("  DB type: %s", type(db).__name__)

    # ── 2. Build services (mirrors worker startup / route wiring) ───
    log.info("Step 2: Building services...")
    from infrastructure.persistence.repository_repository import RepositoryRepository
    from infrastructure.persistence.analysis_repository import AnalysisRepository
    from infrastructure.persistence.analysis_event_repository import AnalysisEventRepository
    from infrastructure.persistence.prompt_repository import PromptRepository
    from infrastructure.prompts.database_prompt_loader import DatabasePromptLoader
    from infrastructure.analysis.structure_analyzer import StructureAnalyzer
    from application.services.repository_service import RepositoryService
    from application.services.analysis_service import AnalysisService
    from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
    from application.services.analysis_data_collector import analysis_data_collector
    from application.services.intent_layer_service import IntentLayerService
    from config.settings import get_settings

    settings = get_settings()
    storage = container.storage()
    github_service = container.github_service()

    repo_repo = RepositoryRepository(db=db)
    analysis_repo = AnalysisRepository(db=db)
    event_repo = AnalysisEventRepository(db=db)
    prompt_repo = PromptRepository(db=db)
    prompt_loader = DatabasePromptLoader(prompt_repo)

    analysis_data_collector.initialize(db)

    repo_service = RepositoryService(
        repository_repo=repo_repo,
        github_service=github_service,
        storage=storage,
    )

    phased_generator = PhasedBlueprintGenerator(
        settings=settings,
        db_client=db,
        prompt_loader=prompt_loader,
    )

    intent_layer_service = IntentLayerService(storage=storage, settings=settings)

    analysis_service = AnalysisService(
        analysis_repo=analysis_repo,
        repository_repo=repo_repo,
        event_repo=event_repo,
        structure_analyzer=StructureAnalyzer(),
        persistent_storage=storage,
        phased_blueprint_generator=phased_generator,
        db_client=db,
        intent_layer_service=intent_layer_service,
    )
    log.info("  All services built OK")

    # ── 3. Ensure repository record exists ──────────────────────────
    log.info("Step 3: Ensuring repository record for gbrbks/architecture_mcp...")
    import uuid
    token = os.environ.get("GITHUB_TOKEN") or settings.github_token
    if not token:
        log.error("  GITHUB_TOKEN not set – cannot proceed")
        sys.exit(1)

    # Use the same default user ID as user_profile_repository
    default_user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "default-user"))

    repo = await repo_repo.get_by_full_name(default_user_id, "gbrbks", "architecture_mcp")
    if repo:
        log.info("  Found existing repo record: %s", repo.id)
    else:
        repo = await repo_service.create_repository(
            user_id=default_user_id, token=token, owner="gbrbks", name="architecture_mcp"
        )
        log.info("  Created repo record: %s", repo.id)

    # ── 4. Start analysis ───────────────────────────────────────────
    log.info("Step 4: Starting analysis...")
    analysis = await analysis_service.start_analysis(repo.id)
    log.info("  Analysis ID: %s, status: %s", analysis.id, analysis.status)

    # ── 5. Clone repository ─────────────────────────────────────────
    log.info("Step 5: Cloning repository...")
    from infrastructure.storage.temp_storage import TempStorage
    temp_storage = TempStorage()
    temp_dir = temp_storage.get_base_path()
    repo_path = await repo_service.clone_repository(repo, token, temp_dir)
    repo_path = Path(repo_path).resolve()
    items = list(repo_path.iterdir())
    log.info("  Cloned to %s (%d items)", repo_path, len(items))

    # ── 6. Run full analysis pipeline ───────────────────────────────
    log.info("Step 6: Running analysis pipeline (this takes several minutes)...")
    try:
        await analysis_service.run_analysis(
            analysis_id=analysis.id,
            repo_path=repo_path,
            token=token,
        )
        log.info("  Pipeline completed successfully!")
    except Exception as e:
        log.error("  Pipeline FAILED: %s", e)
        traceback.print_exc()
        # Check partial state
        analysis = await analysis_repo.get_by_id(analysis.id)
        log.error("  Analysis status: %s, progress: %s", analysis.status, analysis.progress_percentage)
        events = await event_repo.get_by_analysis_id(analysis.id)
        log.error("  Events recorded: %d", len(events))
        if events:
            for ev in events[-5:]:
                log.error("    [%s] %s", ev.event_type, ev.message[:120])
        sys.exit(1)

    # ── 7. Validate final state ─────────────────────────────────────
    log.info("Step 7: Validating final state...")
    analysis = await analysis_repo.get_by_id(analysis.id)
    assert analysis.status == "completed", f"Expected completed, got {analysis.status}"
    assert analysis.progress_percentage == 100, f"Expected progress 100, got {analysis.progress_percentage}"
    log.info("  Analysis status: %s, progress: %s%%", analysis.status, analysis.progress_percentage)

    # Events
    events = await event_repo.get_by_analysis_id(analysis.id)
    log.info("  Events recorded: %d", len(events))
    event_types = set(ev.event_type for ev in events)
    log.info("  Event types: %s", sorted(event_types))
    assert len(events) > 10, f"Expected >10 events, got {len(events)}"

    # Check created_at is valid on events
    for ev in events[:3]:
        assert ev.created_at is not None, f"Event {ev.id} has no created_at"
        log.info("  Sample event: [%s] %s (created_at=%s)", ev.event_type, ev.message[:60], ev.created_at.isoformat())

    # Blueprint exists in storage
    json_path = f"blueprints/{repo.id}/blueprint.json"
    exists = await storage.exists(json_path)
    assert exists, f"Blueprint not found at {json_path}"
    content = await storage.read(json_path)
    blueprint_data = json.loads(content.decode("utf-8") if isinstance(content, bytes) else content)
    log.info("  Blueprint JSON: %d keys, schema=%s", len(blueprint_data), blueprint_data.get("schema_version", "?"))

    # Analysis data (gathered + phases)
    analysis_data = await analysis_data_collector.get_data(analysis.id)
    has_gathered = bool(analysis_data.get("gathered"))
    phase_count = len(analysis_data.get("phases", []))
    log.info("  Analysis data: gathered=%s, phases=%d", has_gathered, phase_count)

    # Intent layer files
    il_base = f"blueprints/{repo.id}/intent_layer"
    if await storage.exists(il_base):
        il_files = await storage.list_files(il_base)
        log.info("  Intent layer files: %d", len(il_files))
    else:
        log.warning("  Intent layer directory not found (Phase 7 may have been skipped)")

    # ── 8. Simulate SSE stream (validate event format) ──────────────
    log.info("Step 8: Validating SSE event format...")
    for ev in events[:5]:
        sse_payload = {
            "id": ev.id,
            "type": ev.event_type,
            "message": ev.message,
            "created_at": ev.created_at.isoformat(),
        }
        # Verify it's JSON-serializable
        json.dumps(sse_payload)
    log.info("  SSE payload format OK (id, type, message, created_at all present)")

    # ── Cleanup ─────────────────────────────────────────────────────
    log.info("Cleaning up temp files...")
    try:
        await repo_service.cleanup_temp_repository(temp_dir)
    except Exception:
        pass

    elapsed = time.time() - t0
    log.info("=" * 60)
    log.info("VALIDATION PASSED in %.1f seconds", elapsed)
    log.info("=" * 60)

    await container.shutdown_resources()


if __name__ == "__main__":
    asyncio.run(main())
