"""Tests for RAGRetriever using DatabaseClient abstraction.

Verifies:
  - _search_similar uses db.rpc()
  - Results are properly formatted
  - Graceful fallback on error
  - _batch_insert_embeddings uses db.table() with in_()
  - Empty list is a no-op
  - DB errors are silently caught
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from domain.interfaces.database import DatabaseClient, DatabaseError, QueryResult


class MockDbForRag(DatabaseClient):
    """Mock DatabaseClient for RAG retriever tests."""

    def __init__(self):
        self.rpc_mock = AsyncMock()
        self._table_mocks: dict[str, MagicMock] = {}

    def table(self, name: str):
        if name not in self._table_mocks:
            mock = MagicMock()
            # Make all chainable methods return the mock itself
            for method in ("select", "insert", "update", "delete", "upsert",
                           "eq", "neq", "in_", "range", "order", "limit", "maybe_single"):
                getattr(mock, method).return_value = mock
            mock.execute = AsyncMock(return_value=QueryResult(data=[]))
            self._table_mocks[name] = mock
        return self._table_mocks[name]

    async def rpc(self, function_name, params):
        return await self.rpc_mock(function_name, params)


@pytest.fixture
def mock_db():
    return MockDbForRag()


@pytest.fixture
def make_retriever(mock_db):
    """Create a RAGRetriever with mocked SentenceTransformer and settings."""
    def _make(rpc_data=None):
        if rpc_data is not None:
            mock_db.rpc_mock.return_value = QueryResult(data=rpc_data)
        else:
            mock_db.rpc_mock.return_value = QueryResult(data=[])

        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

        from infrastructure.analysis.rag_retriever import RAGRetriever
        retriever = RAGRetriever(db_client=mock_db)
        retriever._model = mock_model  # Bypass lazy get_model()
        return retriever

    return _make


class TestSearchSimilar:

    @pytest.mark.asyncio
    async def test_search_similar_calls_rpc(self, make_retriever, mock_db):
        retriever = make_retriever(rpc_data=[
            {
                "file_path": "src/main.py",
                "chunk_type": "module",
                "similarity": 0.9,
                "metadata": {"start_line": 1, "end_line": 50, "content_preview": "..."},
            }
        ])
        results = await retriever.retrieve_for_query("test query", "repo-123", limit=5)
        mock_db.rpc_mock.assert_called_once()
        args = mock_db.rpc_mock.call_args
        assert args[0][0] == "match_embeddings"

    @pytest.mark.asyncio
    async def test_search_similar_returns_formatted_results(self, make_retriever):
        retriever = make_retriever(rpc_data=[
            {
                "file_path": "src/main.py",
                "chunk_type": "function",
                "similarity": 0.85,
                "metadata": {"start_line": 10, "end_line": 30, "content_preview": "def main():"},
            }
        ])
        results = await retriever.retrieve_for_query("entry point", "repo-123")
        assert len(results) == 1
        assert results[0]["file_path"] == "src/main.py"
        assert results[0]["similarity"] == 0.85

    @pytest.mark.asyncio
    async def test_search_similar_graceful_fallback_on_error(self, make_retriever, mock_db):
        mock_db.rpc_mock.side_effect = DatabaseError(message="rpc failed")
        retriever = make_retriever()
        results = await retriever.retrieve_for_query("test", "repo-123")
        assert results == []


class TestBatchInsertEmbeddings:

    @pytest.mark.asyncio
    async def test_batch_insert_deletes_then_inserts(self, make_retriever, mock_db):
        retriever = make_retriever()
        embeddings = [
            {"repository_id": "repo-1", "file_path": "a.py", "chunk_type": "module", "embedding": [0.1], "metadata": {}},
            {"repository_id": "repo-1", "file_path": "b.py", "chunk_type": "module", "embedding": [0.2], "metadata": {}},
        ]
        await retriever._batch_insert_embeddings(embeddings)

        table_mock = mock_db._table_mocks.get("embeddings")
        assert table_mock is not None
        # Should have called delete and insert
        table_mock.delete.assert_called()
        table_mock.insert.assert_called()

    @pytest.mark.asyncio
    async def test_batch_insert_empty_list_noop(self, make_retriever, mock_db):
        retriever = make_retriever()
        await retriever._batch_insert_embeddings([])
        # No table calls
        assert "embeddings" not in mock_db._table_mocks

    @pytest.mark.asyncio
    async def test_batch_insert_error_does_not_raise(self, make_retriever, mock_db):
        retriever = make_retriever()
        # Make delete raise
        table_mock = mock_db.table("embeddings")
        table_mock.execute = AsyncMock(side_effect=DatabaseError(message="db error"))

        embeddings = [
            {"repository_id": "repo-1", "file_path": "a.py", "chunk_type": "module", "embedding": [0.1], "metadata": {}},
        ]
        # Should not raise
        await retriever._batch_insert_embeddings(embeddings)


class TestIndexRepositoryWipesStale:
    """Verify that index_repository deletes existing embeddings before re-indexing."""

    @pytest.mark.asyncio
    async def test_index_repository_deletes_existing_embeddings_before_indexing(
        self, make_retriever, mock_db, tmp_path,
    ):
        retriever = make_retriever()

        # Create a small repo with one file
        src = tmp_path / "main.py"
        src.write_text("print('hello')")

        await retriever.index_repository(
            repository_id="repo-1",
            repo_path=tmp_path,
        )

        table_mock = mock_db._table_mocks.get("embeddings")
        assert table_mock is not None

        # delete().eq("repository_id", "repo-1").execute() should have been called
        table_mock.delete.assert_called()
        table_mock.eq.assert_any_call("repository_id", "repo-1")

    @pytest.mark.asyncio
    async def test_index_repository_wipe_failure_does_not_block_indexing(
        self, make_retriever, mock_db, tmp_path,
    ):
        retriever = make_retriever()

        # Pre-create the embeddings table mock and make the first execute() raise
        table_mock = mock_db.table("embeddings")
        original_execute = table_mock.execute

        call_count = 0

        async def _conditional_execute():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DatabaseError(message="wipe failed")
            return await original_execute()

        table_mock.execute = _conditional_execute

        # Create a small repo with one file
        src = tmp_path / "main.py"
        src.write_text("print('hello')")

        # Should not raise
        stats = await retriever.index_repository(
            repository_id="repo-1",
            repo_path=tmp_path,
        )

        # Indexing still proceeded — at least one file was processed
        assert stats["files"] >= 1
