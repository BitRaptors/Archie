"""
End-to-end tests for Local Postgres + SSE Event Bus + In-Process Analysis.

Validates:
1. Local Postgres CRUD via asyncpg adapter (all entity types)
2. Full analysis pipeline with real Claude API calls
3. SSE event bus (asyncio.Queue-based real-time push)
4. Intent layer Phase 7 (in-pipeline with progress events)
5. In-process analysis fallback (no Redis) via FastAPI HTTP

Requires:
- Docker Postgres running
- .env.local with DB_BACKEND=postgres, DATABASE_URL, GITHUB_TOKEN, ANTHROPIC_API_KEY
"""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from config.container import Container
from config.settings import get_settings
from application.services.repository_service import RepositoryService
from application.services.analysis_service import AnalysisService
from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
from application.services.analysis_data_collector import analysis_data_collector
from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from infrastructure.persistence.user_repository import UserRepository
from infrastructure.persistence.repository_repository import RepositoryRepository
from infrastructure.persistence.analysis_repository import AnalysisRepository
from infrastructure.persistence.analysis_event_repository import AnalysisEventRepository
from infrastructure.events.event_bus import subscribe as event_bus_subscribe
from domain.entities.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def container():
    """Initialize DI container, yield, shutdown."""
    c = Container()
    await c.init_resources()
    yield c
    await c.shutdown_resources()


@pytest.fixture
def github_token():
    """From GITHUB_TOKEN env, skip if missing."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN not set")
    return token


@pytest.fixture
async def db(container):
    """Resolve DB from container, assert it's PostgresAdapter (skip otherwise)."""
    db = await container.db()
    cls_name = type(db).__name__
    if cls_name != "PostgresAdapter":
        pytest.skip(f"DB_BACKEND is not postgres (got {cls_name})")
    return db


@pytest.fixture
async def services(container, db, github_token):
    """Build all repos + services mirroring repositories.py route wiring."""
    user_repo = UserRepository(db=db)
    repo_repo = RepositoryRepository(db=db)
    analysis_repo = AnalysisRepository(db=db)
    event_repo = AnalysisEventRepository(db=db)

    storage = container.storage()
    github_service = container.github_service()
    settings = get_settings()

    repo_service = RepositoryService(
        repository_repo=repo_repo,
        github_service=github_service,
        storage=storage,
    )

    structure_analyzer = StructureAnalyzer()
    prompt_loader = container.database_prompt_loader()
    phased_blueprint_generator = PhasedBlueprintGenerator(
        settings=settings,
        db_client=db,
        prompt_loader=prompt_loader,
    )

    intent_layer_service = container.intent_layer_service()
    analysis_service = AnalysisService(
        analysis_repo=analysis_repo,
        repository_repo=repo_repo,
        event_repo=event_repo,
        structure_analyzer=structure_analyzer,
        persistent_storage=storage,
        phased_blueprint_generator=phased_blueprint_generator,
        db_client=db,
        intent_layer_service=intent_layer_service,
    )

    # Initialize analysis_data_collector with DB for persistence
    analysis_data_collector.initialize(db)

    return {
        "user_repo": user_repo,
        "repo_repo": repo_repo,
        "analysis_repo": analysis_repo,
        "event_repo": event_repo,
        "repo_service": repo_service,
        "analysis_service": analysis_service,
        "storage": storage,
        "intent_layer_service": intent_layer_service,
        "settings": settings,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TEST_OWNER = "BitRaptors"
TEST_REPO = "raptamagochi"
TEST_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-user-postgres-e2e"))


async def ensure_user(user_repo, user_id: str = TEST_USER_ID) -> User:
    """Create or fetch the test user."""
    user = await user_repo.get_by_id(user_id)
    if not user:
        user = User.create(github_token_encrypted="test_token")
        user.id = user_id
        user = await user_repo.add(user)
    return user


async def ensure_repo(repo_service, user_id: str, token: str):
    """Create or fetch the test repository."""
    repo = await repo_service.get_repository_by_full_name(user_id, TEST_OWNER, TEST_REPO)
    if not repo:
        repo = await repo_service.create_repository(user_id, token, TEST_OWNER, TEST_REPO)
    return repo


# ---------------------------------------------------------------------------
# Test 1: CRUD Operations
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_postgres_crud_operations(container, db, services, github_token):
    """Quick validation of all DB operations before the expensive pipeline."""
    print("\n" + "=" * 80)
    print("TEST 1: POSTGRES CRUD OPERATIONS")
    print("=" * 80)

    user_repo = services["user_repo"]
    repo_service = services["repo_service"]
    analysis_repo = services["analysis_repo"]
    event_repo = services["event_repo"]

    # --- Users ---
    print("\n[Users] Create & get_by_id...")
    user = await ensure_user(user_repo)
    fetched = await user_repo.get_by_id(user.id)
    assert fetched is not None
    assert fetched.id == user.id
    print(f"  OK: user {user.id[:8]}...")

    # --- Repositories ---
    print("\n[Repositories] Create & get_by_full_name...")
    repo = await ensure_repo(repo_service, user.id, github_token)
    assert repo is not None
    assert repo.full_name == f"{TEST_OWNER}/{TEST_REPO}"
    print(f"  OK: repo {repo.full_name} (id={repo.id[:8]}...)")

    # --- Analyses ---
    print("\n[Analyses] Create, update status/progress, get_by_id...")
    from domain.entities.analysis import Analysis
    analysis = Analysis.create(repository_id=repo.id)
    analysis = await analysis_repo.add(analysis)
    assert analysis.id is not None

    analysis.update_progress(42)
    await analysis_repo.update(analysis)
    refreshed = await analysis_repo.get_by_id(analysis.id)
    assert refreshed.progress_percentage == 42
    print(f"  OK: analysis {analysis.id[:8]}... progress=42")

    # --- Events ---
    print("\n[Events] Add event, get_by_analysis_id...")
    from domain.entities.analysis_event import AnalysisEvent
    evt = AnalysisEvent.create(analysis.id, "TEST_EVENT", "hello from test")
    await event_repo.add(evt)
    events = await event_repo.get_by_analysis_id(analysis.id)
    assert len(events) >= 1
    assert any(e.event_type == "TEST_EVENT" for e in events)
    print(f"  OK: {len(events)} events for analysis")

    # --- Analysis Data ---
    print("\n[Analysis Data] Upsert gathered + phase data, get_data...")
    analysis_data_collector.initialize(db)
    await analysis_data_collector.capture_gathered_data(analysis.id, {
        "file_tree_raw": "src/\n  main.py\n  utils.py",
        "dependencies_raw": "flask==2.0\nreact@18",
        "config_files": {"config.py": "DEBUG = True"},
        "code_samples": {"main.py": "print('hello')"},
    })
    await analysis_data_collector.capture_phase_data(
        analysis_id=analysis.id,
        phase_name="discovery",
        gathered={"file_tree_raw": "test tree"},
        sent={"prompt": "test prompt", "char_count": 100},
        output="test response",
    )
    data = await analysis_data_collector.get_data(analysis.id)
    assert data.get("gathered") is not None
    assert len(data.get("phases", [])) >= 1
    print(f"  OK: gathered keys={list(data['gathered'].keys())}, phases={len(data['phases'])}")

    # --- Prompts ---
    print("\n[Prompts] get_all_defaults (verify seed data)...")
    prompt_loader = container.database_prompt_loader()
    prompts = await prompt_loader.get_all_defaults()
    assert len(prompts) > 0, "No prompts found — did you run seed_prompts.py?"
    print(f"  OK: {len(prompts)} prompts loaded from DB")

    # --- RPC: match_embeddings ---
    print("\n[RPC] match_embeddings with dummy 384-dim vector...")
    dummy_vector = [0.0] * 384
    try:
        result = await db.rpc("match_embeddings", {
            "query_embedding": dummy_vector,
            "match_threshold": 0.0,
            "match_count": 1,
            "filter_repo_id": repo.id,
        })
        # The function exists and returns — content doesn't matter for a dummy vector
        print(f"  OK: match_embeddings returned (rows={len(result.data if result.data else [])})")
    except Exception as e:
        # If the function doesn't exist, that's a schema issue — fail the test
        if "does not exist" in str(e).lower():
            pytest.fail(f"match_embeddings stored function missing: {e}")
        # Other errors (empty results etc) are acceptable
        print(f"  OK: match_embeddings callable (got: {type(e).__name__}: {e})")

    print("\n" + "=" * 80)
    print("TEST 1 PASSED: All CRUD operations validated")
    print("=" * 80)


# ---------------------------------------------------------------------------
# Test 2: Full Pipeline with SSE Events
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_full_pipeline_with_sse_events(container, db, services, github_token):
    """Full analysis pipeline with SSE event bus validation (~3-5 min, real API)."""
    print("\n" + "=" * 80)
    print("TEST 2: FULL PIPELINE WITH SSE EVENTS")
    print("=" * 80)

    user_repo = services["user_repo"]
    repo_service = services["repo_service"]
    analysis_service = services["analysis_service"]
    analysis_repo = services["analysis_repo"]
    event_repo = services["event_repo"]
    storage = services["storage"]

    # --- Setup ---
    print("\n[Setup] Ensuring user + repo records...")
    user = await ensure_user(user_repo)
    repo = await ensure_repo(repo_service, user.id, github_token)
    print(f"  User: {user.id[:8]}..., Repo: {repo.full_name}")

    # --- Start analysis ---
    print("\n[Start] Creating analysis record...")
    analysis = await analysis_service.start_analysis(repo.id)
    print(f"  Analysis: {analysis.id[:8]}... status={analysis.status}")
    assert analysis.status == "in_progress"

    # --- Clone repo ---
    print("\n[Clone] Cloning repository...")
    import tempfile
    temp_dir = Path(tempfile.mkdtemp(prefix="test_pg_e2e_"))
    repo_path = await repo_service.clone_repository(repo, github_token, temp_dir)
    print(f"  Cloned to: {repo_path}")
    assert repo_path.exists()

    # --- Subscribe to event bus BEFORE running pipeline ---
    collected_events: list[dict] = []
    pipeline_done = asyncio.Event()

    async def drain_events(analysis_id: str):
        """Collect all events from the bus until 'complete' arrives."""
        async with event_bus_subscribe(analysis_id) as queue:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=600)
                    collected_events.append(event)
                    evt_name = event.get("event", "unknown")
                    # Print progress for visibility
                    if evt_name == "status":
                        print(f"    [SSE] status: {event.get('status')} progress={event.get('progress')}")
                    elif evt_name == "log":
                        msg = event.get("message", "")
                        if "PHASE_START" in event.get("type", "") or "PHASE_END" in event.get("type", ""):
                            print(f"    [SSE] {event.get('type')}: {msg}")
                        elif "[Intent Layer]" in msg:
                            print(f"    [SSE] {msg}")
                    elif evt_name == "gathered":
                        print(f"    [SSE] gathered data received")
                    elif evt_name == "phase":
                        phase_name = event.get("data", {}).get("phase", "?")
                        print(f"    [SSE] phase data: {phase_name}")
                    elif evt_name == "complete":
                        print(f"    [SSE] COMPLETE: status={event.get('status')}")
                        pipeline_done.set()
                        return
                except asyncio.TimeoutError:
                    print("    [SSE] TIMEOUT waiting for events (600s)")
                    pipeline_done.set()
                    return

    # Start draining events in background
    drain_task = asyncio.create_task(drain_events(analysis.id))

    # --- Run pipeline ---
    print("\n[Pipeline] Running full analysis (real Claude API calls)...")
    try:
        await analysis_service.run_analysis(
            analysis_id=analysis.id,
            repo_path=repo_path,
            token=github_token,
            prompt_config=None,
        )
        print("  Pipeline completed successfully")
    except Exception as e:
        print(f"  Pipeline FAILED: {e}")
        import traceback
        traceback.print_exc()
        raise

    # Wait for drain task to finish (it should stop on 'complete' event)
    await asyncio.wait_for(pipeline_done.wait(), timeout=30)
    drain_task.cancel()
    try:
        await drain_task
    except asyncio.CancelledError:
        pass

    # --- Validate events received via bus ---
    print(f"\n[Events] Validating {len(collected_events)} events from SSE bus...")

    event_names = [e.get("event", "unknown") for e in collected_events]
    log_types = [e.get("type", "") for e in collected_events if e.get("event") == "log"]

    # Status events with progress
    status_events = [e for e in collected_events if e.get("event") == "status"]
    assert len(status_events) >= 1, f"Expected status events, got {len(status_events)}"
    print(f"  status events: {len(status_events)}")

    # Log events: PHASE_START / PHASE_END
    phase_starts = [t for t in log_types if t == "PHASE_START"]
    phase_ends = [t for t in log_types if t == "PHASE_END"]
    assert len(phase_starts) >= 4, f"Expected >=4 PHASE_START events, got {len(phase_starts)}"
    assert len(phase_ends) >= 4, f"Expected >=4 PHASE_END events, got {len(phase_ends)}"
    print(f"  PHASE_START: {len(phase_starts)}, PHASE_END: {len(phase_ends)}")

    # Gathered event from analysis_data_collector
    gathered_events = [e for e in collected_events if e.get("event") == "gathered"]
    assert len(gathered_events) >= 1, "Expected gathered event from analysis_data_collector"
    print(f"  gathered events: {len(gathered_events)}")

    # Phase events from analysis_data_collector
    phase_events = [e for e in collected_events if e.get("event") == "phase"]
    assert len(phase_events) >= 1, "Expected phase events from analysis_data_collector"
    print(f"  phase events: {len(phase_events)}")

    # Intent Layer log events (Phase 7)
    il_logs = [e for e in collected_events if "[Intent Layer]" in e.get("message", "")]
    print(f"  [Intent Layer] log events: {len(il_logs)}")
    # Intent layer is non-fatal so we don't assert, just log

    # Complete event
    complete_events = [e for e in collected_events if e.get("event") == "complete"]
    assert len(complete_events) == 1, f"Expected exactly 1 complete event, got {len(complete_events)}"
    assert complete_events[0].get("status") == "completed"
    print(f"  complete event: status={complete_events[0].get('status')}")

    # --- Validate DB state ---
    print("\n[DB] Validating persisted state...")

    # Analysis status
    completed_analysis = await analysis_repo.get_by_id(analysis.id)
    assert completed_analysis.status == "completed", f"Expected completed, got {completed_analysis.status}"
    assert completed_analysis.progress_percentage == 100
    print(f"  Analysis: status={completed_analysis.status}, progress={completed_analysis.progress_percentage}%")

    # Events persisted in DB
    db_events = await event_repo.get_by_analysis_id(analysis.id)
    assert len(db_events) > 10, f"Expected >10 persisted events, got {len(db_events)}"
    print(f"  Persisted events: {len(db_events)}")

    # Blueprint JSON in storage
    blueprint_path = f"blueprints/{repo.id}/blueprint.json"
    assert await storage.exists(blueprint_path), f"Blueprint not found at {blueprint_path}"
    content = await storage.read(blueprint_path)
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    bp_data = json.loads(text)
    assert "meta" in bp_data
    print(f"  Blueprint: {len(text)} chars, has meta={bool(bp_data.get('meta'))}")

    # Analysis data persisted via analysis_data_collector
    ad = await analysis_data_collector.get_data(analysis.id)
    assert ad.get("gathered"), "No gathered data persisted"
    assert len(ad.get("phases", [])) >= 1, "No phase data persisted"
    print(f"  Analysis data: gathered keys={list(ad['gathered'].keys())[:5]}, phases={len(ad['phases'])}")

    # --- Validate intent layer files ---
    print("\n[Intent Layer] Checking generated files...")
    il_dir = Path(services["settings"].storage_path) / "blueprints" / str(repo.id) / "intent_layer"
    if il_dir.exists():
        il_files = list(il_dir.rglob("*"))
        claude_md_files = [f for f in il_files if f.name == "CLAUDE.md"]
        print(f"  Intent layer files: {len(il_files)} total, {len(claude_md_files)} CLAUDE.md files")
        if claude_md_files:
            print(f"  Sample: {claude_md_files[0].relative_to(il_dir)}")
    else:
        print(f"  Intent layer directory not found at {il_dir} (non-fatal)")

    # --- Cleanup ---
    print("\n[Cleanup] Removing temp directory...")
    await repo_service.cleanup_temp_repository(temp_dir)
    print("  Done")

    print("\n" + "=" * 80)
    print("TEST 2 PASSED: Full pipeline + SSE events validated")
    print("=" * 80)


# ---------------------------------------------------------------------------
# Test 3: In-process Fallback via FastAPI HTTP
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_inprocess_fallback_via_api(db, github_token):
    """Validate in-process fallback through actual FastAPI app (HTTP-level)."""
    print("\n" + "=" * 80)
    print("TEST 3: IN-PROCESS FALLBACK VIA API")
    print("=" * 80)

    try:
        import httpx
    except ImportError:
        pytest.skip("httpx not installed")

    from api.app import create_app

    app = create_app()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=httpx.Timeout(600.0),
    ) as client:
        # --- POST to start analysis ---
        print(f"\n[POST] /{TEST_OWNER}/{TEST_REPO}/analyze")
        resp = await client.post(
            f"/api/v1/repositories/{TEST_OWNER}/{TEST_REPO}/analyze",
            headers={"Authorization": f"Bearer {github_token}"},
        )
        assert resp.status_code == 200, f"Start analysis failed: {resp.status_code} {resp.text}"
        analysis_data = resp.json()
        analysis_id = analysis_data["id"]
        print(f"  Analysis started: {analysis_id[:8]}...")

        # --- GET SSE stream ---
        print(f"\n[SSE] Connecting to /analyses/{analysis_id[:8]}…/stream")
        sse_events: list[dict] = []
        got_complete = False

        async with client.stream(
            "GET",
            f"/api/v1/analyses/{analysis_id}/stream",
        ) as sse_resp:
            assert sse_resp.status_code == 200
            buffer = ""
            async for chunk in sse_resp.aiter_text():
                buffer += chunk
                # Parse SSE frames from the buffer
                while "\n\n" in buffer:
                    frame, buffer = buffer.split("\n\n", 1)
                    event_name = "message"
                    event_data = ""
                    for line in frame.strip().split("\n"):
                        if line.startswith("event:"):
                            event_name = line[len("event:"):].strip()
                        elif line.startswith("data:"):
                            event_data = line[len("data:"):].strip()

                    if not event_data:
                        continue

                    try:
                        parsed = json.loads(event_data)
                    except json.JSONDecodeError:
                        parsed = {"raw": event_data}

                    sse_events.append({"event": event_name, **parsed})

                    if event_name == "status":
                        print(f"    [SSE] status: {parsed.get('status')} progress={parsed.get('progress')}")
                    elif event_name == "log":
                        msg = parsed.get("message", "")
                        if "PHASE_START" in parsed.get("type", "") or "PHASE_END" in parsed.get("type", ""):
                            print(f"    [SSE] {parsed.get('type')}: {msg}")
                    elif event_name == "complete":
                        print(f"    [SSE] COMPLETE: {parsed.get('status')}")
                        got_complete = True
                    elif event_name == "analysis_complete":
                        print(f"    [SSE] analysis_complete received")

                    if got_complete and event_name == "analysis_complete":
                        break
                if got_complete:
                    break

        # --- Validate ---
        print(f"\n[Validate] {len(sse_events)} SSE events collected")
        event_types = [e["event"] for e in sse_events]
        assert "complete" in event_types, f"Missing 'complete' event. Got: {set(event_types)}"

        # Check final analysis state via API
        status_resp = await client.get(f"/api/v1/analyses/{analysis_id}")
        assert status_resp.status_code == 200
        final = status_resp.json()
        assert final["status"] == "completed", f"Expected completed, got {final['status']}"
        assert final["progress_percentage"] == 100
        print(f"  Final status: {final['status']}, progress: {final['progress_percentage']}%")

        # Check blueprint exists via API
        bp_resp = await client.get(
            f"/api/v1/analyses/{analysis_id}/blueprint",
            params={"format": "json"},
        )
        assert bp_resp.status_code == 200
        bp_json = bp_resp.json()
        assert "structured" in bp_json
        assert "meta" in bp_json["structured"]
        print(f"  Blueprint: has meta, type={bp_json.get('type')}")

    print("\n" + "=" * 80)
    print("TEST 3 PASSED: In-process fallback via API validated")
    print("=" * 80)
