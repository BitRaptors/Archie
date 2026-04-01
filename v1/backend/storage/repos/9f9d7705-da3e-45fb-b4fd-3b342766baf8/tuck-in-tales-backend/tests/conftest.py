import pytest
import pytest_asyncio
from httpx import AsyncClient
from unittest.mock import MagicMock, AsyncMock
from uuid import UUID, uuid4

# Import your FastAPI app instance
from src.main import app
# Import your dependency functions to override/mock
from src.utils.supabase import get_supabase_client
from src.utils.auth import get_family_id_for_user

# Define a known UUID for testing
TEST_FAMILY_ID = uuid4()
TEST_USER_ID = "test-user-firebase-uid"

@pytest.fixture(scope="session")
def anyio_backend():
    """Forces pytest-asyncio to use the asyncio backend."""
    return "asyncio"

@pytest_asyncio.fixture(scope="function")
async def test_client(mocker) -> AsyncClient:
    """Provides an async test client for the FastAPI app with mocked dependencies."""
    
    # Mock the supabase client dependency
    mock_supabase = MagicMock()
    # Mock specific table/method calls used in routes
    mock_supabase.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
        return_value=MagicMock(data=None) # Default: not found
    )
    mock_supabase.table.return_value.select.return_value.eq.return_value.range.return_value.order_by.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[]) # Default: empty list
    )
    mock_supabase.table.return_value.insert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[]) # Default: successful insert returns list
    )
    mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
         return_value=MagicMock(data=[]) # Mock update execute
    )
    mock_supabase.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
         return_value=MagicMock(data=[]) # Mock delete execute
    )
    mock_supabase.storage.from_.return_value.upload = MagicMock() # Mock storage upload (sync?)
    mock_supabase.storage.from_.return_value.create_signed_url = MagicMock(return_value={"signedURL": "http://example.com/signed"})
    mock_supabase.storage.from_.return_value.get_public_url = MagicMock(return_value="http://example.com/public")
    mock_supabase.storage.from_.return_value.remove = MagicMock()
    
    app.dependency_overrides[get_supabase_client] = lambda: mock_supabase
    
    # Mock the family ID dependency
    async def override_get_family_id() -> UUID:
        return TEST_FAMILY_ID
    app.dependency_overrides[get_family_id_for_user] = override_get_family_id
    
    # Create the test client using AsyncClient
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

    # Clean up overrides after tests
    app.dependency_overrides = {}

# Fixture to provide the mocked supabase client directly if needed in tests
@pytest.fixture
def mock_supabase_client(test_client):
    # This relies on test_client having run and set up the override
    # It retrieves the mock instance used by the overridden dependency
    return app.dependency_overrides[get_supabase_client]() 