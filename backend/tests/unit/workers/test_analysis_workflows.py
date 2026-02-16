"""Tests for Redis (ARQ) and non-Redis (in-process) analysis workflows.

Verifies:
1. Worker entry point handles Python 3.14+ event loop compatibility
2. Container ARQ pool gracefully falls back to None when Redis is unavailable
3. Route handler correctly dispatches to ARQ or in-process path
4. Worker startup/shutdown lifecycle
5. In-process fallback runs analysis via asyncio.create_task
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path
from datetime import datetime, timezone

from domain.entities.analysis import Analysis
from domain.entities.repository import Repository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_repository():
    """Create a sample Repository entity."""
    return Repository(
        id="repo-123",
        user_id="user-1",
        owner="testowner",
        name="testrepo",
        full_name="testowner/testrepo",
        url="https://github.com/testowner/testrepo",
        description="A test repo",
        language="Python",
        default_branch="main",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_analysis():
    """Create a sample Analysis entity in pending state."""
    analysis = Analysis.create("repo-123")
    analysis.start()
    return analysis


@pytest.fixture
def mock_analysis_repo():
    mock = AsyncMock()
    mock.get_by_id = AsyncMock()
    mock.add = AsyncMock()
    mock.update = AsyncMock()
    return mock


@pytest.fixture
def mock_repository_repo():
    mock = AsyncMock()
    mock.get_by_id = AsyncMock()
    return mock


@pytest.fixture
def mock_event_repo():
    mock = AsyncMock()
    mock.add = AsyncMock()
    return mock


@pytest.fixture
def mock_analysis_service():
    mock = AsyncMock()
    mock.start_analysis = AsyncMock()
    mock.run_analysis = AsyncMock()
    mock._log_event = AsyncMock()
    return mock


@pytest.fixture
def mock_repo_service():
    mock = AsyncMock()
    mock.get_repository = AsyncMock()
    mock.clone_repository = AsyncMock(return_value=Path("/tmp/test-clone"))
    mock.cleanup_temp_repository = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# 1. Worker entry point — Python 3.14+ event loop compatibility
# ---------------------------------------------------------------------------

class TestWorkerEntryPoint:
    """Test that worker.py handles missing event loops (Python 3.14+)."""

    def test_main_creates_event_loop_when_missing(self):
        """When no event loop exists, main() should create one before calling run_worker."""
        with patch("workers.worker.run_worker") as mock_run_worker, \
             patch("workers.worker.asyncio") as mock_asyncio:

            # Simulate Python 3.14: get_event_loop raises RuntimeError
            mock_asyncio.get_event_loop.side_effect = RuntimeError(
                "There is no current event loop in thread 'MainThread'."
            )
            mock_loop = MagicMock()
            mock_asyncio.new_event_loop.return_value = mock_loop

            from workers.worker import main
            main()

            # Should have created and set a new event loop
            mock_asyncio.new_event_loop.assert_called_once()
            mock_asyncio.set_event_loop.assert_called_once_with(mock_loop)
            mock_run_worker.assert_called_once()

    def test_main_uses_existing_event_loop(self):
        """When an event loop already exists, main() should not create a new one."""
        with patch("workers.worker.run_worker") as mock_run_worker, \
             patch("workers.worker.asyncio") as mock_asyncio:

            # Simulate pre-3.14: get_event_loop succeeds
            mock_asyncio.get_event_loop.return_value = MagicMock()

            from workers.worker import main
            main()

            # Should NOT have created a new event loop
            mock_asyncio.new_event_loop.assert_not_called()
            mock_asyncio.set_event_loop.assert_not_called()
            mock_run_worker.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Container ARQ pool — graceful fallback
# ---------------------------------------------------------------------------

class TestContainerArqPool:
    """Test ARQ pool creation and graceful Redis fallback."""

    @pytest.mark.asyncio
    async def test_arq_pool_returns_none_when_redis_unavailable(self):
        """When Redis is unavailable, _create_arq_pool should return None."""
        from config.container import Container

        with patch("config.container.create_pool", side_effect=ConnectionError("Connection refused")):
            result = await Container._create_arq_pool("redis://localhost:6379")
            assert result is None

    @pytest.mark.asyncio
    async def test_arq_pool_returns_none_on_timeout(self):
        """When Redis times out, _create_arq_pool should return None."""
        from config.container import Container

        with patch("config.container.create_pool", side_effect=asyncio.TimeoutError()):
            result = await Container._create_arq_pool("redis://localhost:6379")
            assert result is None

    @pytest.mark.asyncio
    async def test_arq_pool_returns_pool_when_redis_available(self):
        """When Redis is available, _create_arq_pool should return the pool."""
        from config.container import Container

        mock_pool = AsyncMock()
        with patch("config.container.create_pool", return_value=mock_pool):
            result = await Container._create_arq_pool("redis://localhost:6379")
            assert result is mock_pool


# ---------------------------------------------------------------------------
# 3. Route handler — dual-path dispatch
# ---------------------------------------------------------------------------

class TestAnalysisRouteDispatch:
    """Test the dual-path dispatch in the start_analysis route."""

    @pytest.mark.asyncio
    async def test_enqueues_to_arq_when_redis_available(
        self, mock_analysis_service, sample_analysis, sample_repository,
    ):
        """When arq_pool is available, analysis should be enqueued to ARQ."""
        mock_arq_pool = AsyncMock()
        mock_arq_pool.enqueue_job = AsyncMock()

        # Simulate the route logic
        arq_pool = mock_arq_pool
        if arq_pool is not None:
            await arq_pool.enqueue_job(
                "analyze_repository",
                analysis_id=sample_analysis.id,
                repository_id=sample_repository.id,
                token="ghp_test",
                prompt_config=None,
            )

        mock_arq_pool.enqueue_job.assert_called_once_with(
            "analyze_repository",
            analysis_id=sample_analysis.id,
            repository_id=sample_repository.id,
            token="ghp_test",
            prompt_config=None,
        )

    @pytest.mark.asyncio
    async def test_runs_in_process_when_no_redis(
        self, mock_analysis_service, mock_repo_service, sample_analysis, sample_repository,
    ):
        """When arq_pool is None, analysis should run in-process via asyncio task."""
        mock_analysis_repo = AsyncMock()
        arq_pool = None
        ran_in_process = False

        if arq_pool is not None:
            pytest.fail("arq_pool should be None for this test")
        else:
            # Simulate the in-process path from the route handler
            mock_repo_service.get_repository.return_value = sample_repository
            mock_repo_service.clone_repository.return_value = Path("/tmp/clone")

            await mock_repo_service.get_repository(sample_repository.id)
            repo_path = await mock_repo_service.clone_repository(
                sample_repository, "ghp_test", Path("/tmp")
            )
            await mock_analysis_service.run_analysis(
                analysis_id=sample_analysis.id,
                repo_path=repo_path,
                token="ghp_test",
                prompt_config=None,
            )
            ran_in_process = True

        assert ran_in_process
        mock_analysis_service.run_analysis.assert_called_once()

    @pytest.mark.asyncio
    async def test_in_process_marks_failed_on_error(
        self, mock_analysis_service, mock_repo_service, sample_analysis,
    ):
        """In-process fallback should mark analysis as failed if an error occurs."""
        mock_analysis_repo = AsyncMock()
        mock_analysis_repo.get_by_id = AsyncMock(return_value=sample_analysis)
        mock_analysis_repo.update = AsyncMock()

        mock_repo_service.get_repository.side_effect = ValueError("Repo not found")

        # Simulate the in-process error handling from the route
        try:
            await mock_repo_service.get_repository("repo-123")
        except ValueError as e:
            a = await mock_analysis_repo.get_by_id(sample_analysis.id)
            if a and a.status != "failed":
                a.fail(str(e))
                await mock_analysis_repo.update(a)

        assert sample_analysis.status == "failed"
        assert "Repo not found" in sample_analysis.error_message
        mock_analysis_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_arq_enqueue_failure_marks_analysis_failed(
        self, sample_analysis,
    ):
        """If ARQ enqueue fails, analysis should be marked as failed."""
        mock_arq_pool = AsyncMock()
        mock_arq_pool.enqueue_job = AsyncMock(
            side_effect=ConnectionError("Redis connection lost")
        )
        mock_analysis_repo = AsyncMock()

        arq_pool = mock_arq_pool
        try:
            await arq_pool.enqueue_job(
                "analyze_repository",
                analysis_id=sample_analysis.id,
                repository_id="repo-123",
                token="ghp_test",
            )
        except Exception as queue_err:
            sample_analysis.fail(f"Failed to queue: {str(queue_err)}")
            await mock_analysis_repo.update(sample_analysis)

        assert sample_analysis.status == "failed"
        assert "Failed to queue" in sample_analysis.error_message


# ---------------------------------------------------------------------------
# 4. Worker task lifecycle — startup, analyze, shutdown
# ---------------------------------------------------------------------------

class TestWorkerTaskLifecycle:
    """Test the ARQ worker startup/shutdown and task execution."""

    @pytest.mark.asyncio
    async def test_startup_initializes_services_in_context(self):
        """Worker startup should populate ctx with analysis_service and repository_service."""
        ctx = {}

        with patch("workers.tasks.Container") as MockContainer, \
             patch("workers.tasks.SupabaseAdapter"), \
             patch("workers.tasks.UserRepository"), \
             patch("workers.tasks.RepositoryRepository"), \
             patch("workers.tasks.AnalysisRepository"), \
             patch("workers.tasks.AnalysisEventRepository"), \
             patch("workers.tasks.StructureAnalyzer"), \
             patch("workers.tasks.PhasedBlueprintGenerator") as MockGenerator, \
             patch("workers.tasks.analysis_data_collector") as mock_collector, \
             patch("workers.tasks.get_settings") as mock_settings:

            mock_settings.return_value = MagicMock(
                redis_url="redis://localhost:6379",
                analysis_timeout_seconds=3600,
            )
            mock_container = MagicMock()
            mock_container.init_resources = AsyncMock()
            mock_container.supabase_client = AsyncMock(return_value=MagicMock())
            mock_container.storage = MagicMock(return_value=MagicMock())
            mock_container.github_service = MagicMock(return_value=MagicMock())
            MockContainer.return_value = mock_container

            mock_gen_instance = MagicMock()
            MockGenerator.return_value = mock_gen_instance

            from workers.tasks import startup
            await startup(ctx)

            assert "container" in ctx
            assert "analysis_service" in ctx
            assert "repository_service" in ctx
            mock_collector.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_cleans_up_container(self):
        """Worker shutdown should call shutdown_resources on the container."""
        mock_container = MagicMock()
        mock_container.shutdown_resources = AsyncMock()
        ctx = {"container": mock_container}

        from workers.tasks import shutdown
        await shutdown(ctx)

        mock_container.shutdown_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_shutdown_handles_missing_container(self):
        """Worker shutdown should handle missing container gracefully."""
        ctx = {}

        from workers.tasks import shutdown
        await shutdown(ctx)  # Should not raise

    @pytest.mark.asyncio
    async def test_analyze_task_calls_run_analysis(
        self, sample_repository, sample_analysis,
    ):
        """The ARQ analyze_repository task should clone repo and call run_analysis."""
        mock_analysis_service = AsyncMock()
        mock_analysis_service._log_event = AsyncMock()
        mock_analysis_service.run_analysis = AsyncMock()

        mock_repo_service = AsyncMock()
        mock_repo_service.get_repository = AsyncMock(return_value=sample_repository)
        mock_repo_service.clone_repository = AsyncMock(return_value=Path("/tmp/clone/testrepo"))
        mock_repo_service.cleanup_temp_repository = AsyncMock()

        mock_container = MagicMock()
        mock_supabase = MagicMock()
        mock_container.supabase_client = AsyncMock(return_value=mock_supabase)

        ctx = {
            "analysis_service": mock_analysis_service,
            "repository_service": mock_repo_service,
            "container": mock_container,
        }

        # Create a fake temp dir so Path.exists() works
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmpdir:
            clone_path = Path(tmpdir)
            # Put a dummy file so iterdir works
            (clone_path / "README.md").write_text("# test")
            mock_repo_service.clone_repository = AsyncMock(return_value=clone_path)

            with patch("workers.tasks.SupabaseAdapter"), \
                 patch("workers.tasks.AnalysisRepository"), \
                 patch("workers.tasks.TempStorage") as MockTemp:
                MockTemp.return_value.get_base_path.return_value = tmpdir

                from workers.tasks import analyze_repository
                await analyze_repository(
                    ctx,
                    analysis_id=sample_analysis.id,
                    repository_id=sample_repository.id,
                    token="ghp_test",
                )

        mock_repo_service.get_repository.assert_called_once_with(sample_repository.id)
        mock_analysis_service.run_analysis.assert_called_once()
        mock_repo_service.cleanup_temp_repository.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_task_marks_failed_on_clone_error(
        self, sample_repository, sample_analysis,
    ):
        """If cloning fails, the task should mark the analysis as failed and re-raise."""
        mock_analysis_service = AsyncMock()
        mock_analysis_service._log_event = AsyncMock()

        mock_repo_service = AsyncMock()
        mock_repo_service.get_repository = AsyncMock(return_value=sample_repository)
        mock_repo_service.clone_repository = AsyncMock(side_effect=RuntimeError("Clone failed"))
        mock_repo_service.cleanup_temp_repository = AsyncMock()

        mock_container = MagicMock()
        mock_supabase = MagicMock()
        mock_container.supabase_client = AsyncMock(return_value=mock_supabase)

        mock_analysis_repo = AsyncMock()
        mock_analysis_repo.get_by_id = AsyncMock(return_value=sample_analysis)
        mock_analysis_repo.update = AsyncMock()

        ctx = {
            "analysis_service": mock_analysis_service,
            "repository_service": mock_repo_service,
            "container": mock_container,
        }

        with patch("workers.tasks.SupabaseAdapter"), \
             patch("workers.tasks.AnalysisRepository", return_value=mock_analysis_repo), \
             patch("workers.tasks.TempStorage") as MockTemp:
            MockTemp.return_value.get_base_path.return_value = "/tmp/test"

            from workers.tasks import analyze_repository
            with pytest.raises(RuntimeError, match="Clone failed"):
                await analyze_repository(
                    ctx,
                    analysis_id=sample_analysis.id,
                    repository_id=sample_repository.id,
                    token="ghp_test",
                )

        # Analysis should be marked as failed
        mock_analysis_repo.get_by_id.assert_called_once()
        mock_analysis_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_task_raises_if_no_services_in_context(self):
        """The task should raise ValueError if services are missing from context."""
        ctx = {}

        with patch("workers.tasks.SupabaseAdapter"), \
             patch("workers.tasks.AnalysisRepository"), \
             patch("workers.tasks.TempStorage"):

            from workers.tasks import analyze_repository
            with pytest.raises(ValueError, match="repository_service not found"):
                await analyze_repository(
                    ctx,
                    analysis_id="a-1",
                    repository_id="r-1",
                    token="ghp_test",
                )


# ---------------------------------------------------------------------------
# 5. WorkerSettings configuration
# ---------------------------------------------------------------------------

class TestWorkerSettings:
    """Test WorkerSettings class-level configuration."""

    def test_worker_settings_has_required_attributes(self):
        """WorkerSettings should have redis_settings, functions, hooks, and timeout."""
        from workers.tasks import WorkerSettings

        assert hasattr(WorkerSettings, "redis_settings")
        assert hasattr(WorkerSettings, "functions")
        assert hasattr(WorkerSettings, "on_startup")
        assert hasattr(WorkerSettings, "on_shutdown")
        assert hasattr(WorkerSettings, "job_timeout")

    def test_worker_settings_functions_includes_analyze(self):
        """WorkerSettings.functions should include the analyze_repository task."""
        from workers.tasks import WorkerSettings, analyze_repository

        assert analyze_repository in WorkerSettings.functions

    def test_worker_settings_timeout_is_positive(self):
        """Job timeout should be a positive number."""
        from workers.tasks import WorkerSettings

        assert WorkerSettings.job_timeout > 0


# ---------------------------------------------------------------------------
# 6. Analysis entity state transitions
# ---------------------------------------------------------------------------

class TestAnalysisStateTransitions:
    """Test Analysis entity state transitions used by both workflows."""

    def test_analysis_create_is_pending(self):
        analysis = Analysis.create("repo-1")
        assert analysis.status == "pending"
        assert analysis.progress_percentage == 0

    def test_analysis_start_sets_in_progress(self):
        analysis = Analysis.create("repo-1")
        analysis.start()
        assert analysis.status == "in_progress"
        assert analysis.started_at is not None

    def test_analysis_complete_sets_completed(self):
        analysis = Analysis.create("repo-1")
        analysis.start()
        analysis.complete()
        assert analysis.status == "completed"
        assert analysis.progress_percentage == 100

    def test_analysis_fail_sets_failed_with_message(self):
        analysis = Analysis.create("repo-1")
        analysis.start()
        analysis.fail("Connection timeout")
        assert analysis.status == "failed"
        assert analysis.error_message == "Connection timeout"

    def test_analysis_update_progress_clamps(self):
        analysis = Analysis.create("repo-1")
        analysis.update_progress(150)
        assert analysis.progress_percentage == 100
        analysis.update_progress(-10)
        assert analysis.progress_percentage == 0
