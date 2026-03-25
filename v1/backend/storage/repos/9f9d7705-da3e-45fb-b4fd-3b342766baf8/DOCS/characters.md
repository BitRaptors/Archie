# Characters API

This document outlines the API endpoints related to characters.

## `POST /api/characters/`

Creates a new character associated with the user's family.

**Request Body** (`application/json`):
```json
{
  "name": "Barnaby the Brave Bear", // Required
  "description": "A very courageous bear who loves honey adventures.", // Optional
  "birth_date": "2020-05-10" // Optional, YYYY-MM-DD format
}
```

**Response Body (Success - 201 Created)**:
Returns the created `Character` object (see schema below).

**Error Responses**:
- **400 Bad Request**: If `name` is missing or invalid.
- **401 Unauthorized**: If the user is not authenticated.
- **403 Forbidden**: If the user does not belong to a family.
- **500 Internal Server Error**: If there's a server-side issue.

---

## `GET /api/characters/`

Retrieves a list of all characters belonging to the authenticated user's family.

**Query Parameters**:
- `skip` (int, optional, default=0): Number of characters to skip.
- `limit` (int, optional, default=100): Maximum number of characters to return.

**Response Body (Success - 200 OK)**:
An array of `Character` objects.
```json
[
  {
    "id": "char_abc123",
    "family_id": "fam_xyz789", 
    "name": "Barnaby the Brave Bear",
    "description": "A very courageous bear...",
    "photo_paths": ["fam_xyz789/char_abc123/original_uuid1.jpg"],
    "avatar_url": "fam_xyz789/char_abc123/avatar_uuid2.png",
    "birth_date": "2020-05-10",
    "created_at": "2023-10-27T10:00:00Z",
    "updated_at": "2023-10-27T10:00:00Z"
  }
  // ... more characters
]
```

**Error Responses**:
- **401 Unauthorized**
- **403 Forbidden**
- **500 Internal Server Error**

---

## `GET /api/characters/{character_id}`

Retrieves details for a specific character by its UUID, checking family ownership.

**Path Parameters**:
- `character_id` (UUID string): The ID of the character to retrieve.

**Response Body (Success - 200 OK)**:
The requested `Character` object.

**Error Responses**:
- **401 Unauthorized**
- **403 Forbidden**
- **404 Not Found**: If the character doesn't exist or doesn't belong to the user's family.
- **500 Internal Server Error**

---

## `PUT /api/characters/{character_id}`

Updates details for a specific character.

**Path Parameters**:
- `character_id` (UUID string): The ID of the character to update.

**Request Body** (`application/json`):
Include only the fields to update.
```json
{
  "name": "Barnaby the Wise Bear",
  "description": "Loves honey and solving puzzles."
  // "photo_paths": ["new/path1.jpg"], // Can update paths if needed
}
```

**Response Body (Success - 200 OK)**:
The updated `Character` object.

**Error Responses**:
- **400 Bad Request**: If no update data is provided.
- **401 Unauthorized**
- **403 Forbidden**
- **404 Not Found**
- **500 Internal Server Error**

---

## `POST /api/characters/{character_id}/photos`

Uploads one or more photos for a specific character. Photos are appended to the existing `photo_paths` array.

**Path Parameters**:
- `character_id` (UUID string): The ID of the character to associate the photos with.

**Request Body** (`multipart/form-data`):
- `files`: One or more files attached with this key.
  - Allowed Content Types: `image/jpeg`, `image/png`, `image/webp`.

**Response Body (Success - 200 OK)**:
The updated `Character` object, including the modified `photo_paths` array.

**Error Responses**:
- **400 Bad Request**: If file type is invalid.
- **401 Unauthorized**
- **403 Forbidden**
- **404 Not Found**: If the character doesn't exist.
- **500 Internal Server Error**: If file upload or database update fails.

---

## `DELETE /api/characters/{character_id}`

Deletes a specific character, including all associated photos (from `photo_paths`) and the avatar (if present) from storage.

**Path Parameters**:
- `character_id` (UUID string): The ID of the character to delete.

**Response Body (Success - 204 No Content)**:
Empty response body.

**Error Responses**:
- **401 Unauthorized**
- **403 Forbidden**
- **404 Not Found**: While the deletion attempts to proceed even if the character record isn't found (to clean up potential orphaned files), this might occur during ownership checks.
- **500 Internal Server Error**: If database deletion or file removal from storage fails.

---

## Character Schema

```json
{
  "id": "string (UUID)",
  "family_id": "string (UUID)", 
  "name": "string",
  "description": "string | null",
  "photo_paths": "array[string] | null", // Array of storage paths
  "avatar_url": "string | null", // Storage path for generated avatar
  "birth_date": "string (YYYY-MM-DD) | null",
  "created_at": "string (ISO 8601 datetime)",
  "updated_at": "string (ISO 8601 datetime)"
}
```

*Initial Frontend Usage Examples Removed - Refer to `src/api/client.ts` for current implementation.* 