import pytest
from httpx import AsyncClient
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import TEST_FAMILY_ID # Import shared test constants

# Mark all tests in this module to use the asyncio backend
pytestmark = pytest.mark.anyio

# --- Test Data --- 
CHARACTER_ID_1 = uuid4()
CHARACTER_ID_2 = uuid4()

CHARACTER_DATA_1 = {
    "id": str(CHARACTER_ID_1),
    "family_id": str(TEST_FAMILY_ID),
    "name": "Sir Reginald",
    "bio": "A brave knight.",
    "photo_url": None,
    "avatar_url": None,
    "birth_date": "2020-01-15",
    "created_at": "2024-01-01T10:00:00+00:00"
}
CHARACTER_DATA_2 = {
    "id": str(CHARACTER_ID_2),
    "family_id": str(TEST_FAMILY_ID),
    "name": "Princess Petunia",
    "bio": "Loves flowers.",
    "photo_url": f"{TEST_FAMILY_ID}/{CHARACTER_ID_2}/original_photo.jpg",
    "avatar_url": f"{TEST_FAMILY_ID}/{CHARACTER_ID_2}/avatar_img.png",
    "birth_date": "2021-03-20",
    "created_at": "2024-01-02T11:00:00+00:00"
}

# --- Tests --- 

# def test_read_characters_empty(test_client: TestClient, mock_supabase_client):
async def test_read_characters_empty(test_client: AsyncClient, mock_supabase_client):
    """Test getting characters when none exist for the family."""
    # Mock setup: select().eq().range().order_by().execute() returns empty list (default)
    # NOTE: Mock still needs to be AsyncMock if the *original* function is async
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.range.return_value.order_by.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )
    
    # response = test_client.get("/characters/") <-- Add await back
    response = await test_client.get("/characters/")
    
    assert response.status_code == 200
    assert response.json() == []
    # Check that the mock was called with the correct family_id
    # Asserting calls on AsyncMocks might need careful handling if done outside async context,
    # but let's see if pytest handles it.
    mock_supabase_client.table.return_value.select.return_value.eq.assert_called_with("family_id", str(TEST_FAMILY_ID))

# def test_read_characters_success(test_client: TestClient, mock_supabase_client):
async def test_read_characters_success(test_client: AsyncClient, mock_supabase_client):
    """Test getting a list of characters successfully."""
    # Mock setup: return list of characters
    mock_supabase_client.table.return_value.select.return_value.eq.return_value.range.return_value.order_by.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[CHARACTER_DATA_1, CHARACTER_DATA_2])
    )
    
    # response = test_client.get("/characters/") <-- Add await back
    response = await test_client.get("/characters/")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Check if IDs match (adjust based on actual fields returned)
    assert data[0]['id'] == str(CHARACTER_ID_1)
    assert data[1]['id'] == str(CHARACTER_ID_2)
    assert data[0]['family_id'] == str(TEST_FAMILY_ID)
    # Check mock call
    mock_supabase_client.table.return_value.select.return_value.eq.assert_called_with("family_id", str(TEST_FAMILY_ID))

# def test_create_character_success(test_client: TestClient, mock_supabase_client):
async def test_create_character_success(test_client: AsyncClient, mock_supabase_client):
    """Test creating a character successfully."""
    new_char_data = {
        "name": "Dragon Doug",
        "bio": "A friendly dragon.",
        "birth_date": "2022-05-01"
    }
    # Mock setup: insert() returns the created data
    created_db_record = {
        **new_char_data, 
        "id": str(uuid4()), 
        "family_id": str(TEST_FAMILY_ID),
        "photo_url": None,
        "avatar_url": None,
        "created_at": "2024-07-26T12:00:00+00:00" # Example timestamp
    }
    # NOTE: Mock still needs to be AsyncMock if the *original* function is async
    mock_supabase_client.table.return_value.insert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[created_db_record])
    )
    
    # response = test_client.post("/characters/", json=new_char_data) <-- Add await back
    response = await test_client.post("/characters/", json=new_char_data)
    
    assert response.status_code == 201
    data = response.json()
    assert data['name'] == new_char_data['name']
    assert data['bio'] == new_char_data['bio']
    assert data['family_id'] == str(TEST_FAMILY_ID)
    assert "id" in data
    # Check mock insert call data
    insert_call_args = mock_supabase_client.table.return_value.insert.call_args[0][0]
    assert insert_call_args['name'] == new_char_data['name']
    assert insert_call_args['family_id'] == str(TEST_FAMILY_ID)
    assert insert_call_args['birth_date'] == "2022-05-01"

# TODO: Add tests for GET /{id}, PUT /{id}, DELETE /{id}
# TODO: Add tests for photo upload and avatar generation (requires mocking file uploads, vision/dall-e calls)
# TODO: Add tests for error conditions (e.g., 404 Not Found, database errors) 