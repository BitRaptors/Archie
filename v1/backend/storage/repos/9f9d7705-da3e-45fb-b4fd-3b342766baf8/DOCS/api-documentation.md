# Tuck-In Tales Backend

API for generating personalized bedtime stories.

**Version**: 0.1.0

## Base URL
```
http://localhost:8000
```

## Authentication
All endpoints require Firebase Authentication. Include the Firebase ID token in the Authorization header:
```
Authorization: Bearer <firebase_id_token>
```

## WebSocket Endpoints

### Story Generation Progress
```
ws://localhost:8000/ws/progress/{story_id}
```
Listen for real-time updates during story generation.

### Avatar Generation Progress  
```
ws://localhost:8000/ws/{character_id}?token=<firebase_id_token>
```
Listen for real-time updates during avatar generation.

---

## API Endpoints

## Uncategorized

### GET /

**Read Root**

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: object

---

## Characters

### POST /api/characters/

**Create Character**

(Authenticated) Create a new character for the user's family.

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [CharacterCreate](#charactercreate)

**Responses:**

**201**: Successful Response
  - Content-Type: `application/json`
  - Schema: [Character](#character)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### GET /api/characters/

**Read Characters**

(Authenticated) Retrieve characters for the current user's family.

**Parameters:**

- `skip` (query): integer (optional)
- `limit` (query): integer (optional)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: array of [Character](#character)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### GET /api/characters/{character_id}

**Read Character**

(Authenticated) Retrieve a single character by ID, checking family ownership.

**Parameters:**

- `character_id` (path): string (required)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [Character](#character)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### PUT /api/characters/{character_id}

**Update Character**

(Authenticated) Update a character in the user's family.

**Parameters:**

- `character_id` (path): string (required)

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [CharacterUpdate](#characterupdate)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [Character](#character)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### DELETE /api/characters/{character_id}

**Delete Character**

(Authenticated) Delete a character and associated photos/avatar from storage.

**Parameters:**

- `character_id` (path): string (required)

**Responses:**

**204**: Successful Response
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### POST /api/characters/{character_id}/photos

**Upload Character Photos**

(Authenticated) Upload one or more original photos for a character.

**Parameters:**

- `character_id` (path): string (required)

**Request Body:**

Required: True

Content-Type: `multipart/form-data`

Schema: [Body_upload_character_photos_api_characters__character_id__photos_post](#body_upload_character_photos_api_characters__character_id__photos_post)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [Character](#character)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### POST /api/characters/{character_id}/generate_avatar

**Generate Character Avatar Endpoint**

(Authenticated) Triggers asynchronous avatar generation based on character photos.

**Parameters:**

- `character_id` (path): string (required)

**Responses:**

**202**: Successful Response
  - Content-Type: `application/json`
  - Schema: object
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

## Stories

### GET /api/stories/

**List Stories**

(Authenticated) Retrieve all stories for the user's family.

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: array of [StoryBasic](#storybasic)
**404**: Not found
**401**: Unauthorized

---

### GET /api/stories/{story_id}

**Read Story**

(Authenticated) Retrieve a single story by ID, checking family ownership.

**Parameters:**

- `story_id` (path): string (required)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [Story](#story)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### DELETE /api/stories/{story_id}

**Delete Story**

(Authenticated) Delete a story and its associated images from storage.

**Parameters:**

- `story_id` (path): string (required)

**Responses:**

**204**: Successful Response
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### POST /api/stories/generate

**Generate Story**

(Authenticated) Creates initial story record and triggers background generation.

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [StoryGenerationRequest](#storygenerationrequest)

**Responses:**

**202**: Successful Response
  - Content-Type: `application/json`
  - Schema: object
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

## Memories

### POST /api/memories/

**Create Memory**

(Authenticated) Log a new memory for the user's family.

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [MemoryCreate](#memorycreate)

**Responses:**

**201**: Successful Response
  - Content-Type: `application/json`
  - Schema: [Memory](#memory)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### GET /api/memories/

**Read Memories**

(Authenticated) Retrieve memories for the current user's family.

**Parameters:**

- `skip` (query): integer (optional)
- `limit` (query): integer (optional)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: array of [Memory](#memory)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### GET /api/memories/{memory_id}

**Read Memory**

(Authenticated) Retrieve a single memory by ID, checking family ownership.

**Parameters:**

- `memory_id` (path): string (required)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [Memory](#memory)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### PUT /api/memories/{memory_id}

**Update Memory**

(Authenticated) Update a memory in the user's family. Regenerates embedding if text changes.

**Parameters:**

- `memory_id` (path): string (required)

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [MemoryUpdate](#memoryupdate)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [Memory](#memory)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### DELETE /api/memories/{memory_id}

**Delete Memory**

(Authenticated) Delete a memory from the user's family.

**Parameters:**

- `memory_id` (path): string (required)

**Responses:**

**204**: Successful Response
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### POST /api/memories/search

**Search Memories**

(Authenticated) Search memories in the user's family.

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [MemorySearchRequest](#memorysearchrequest)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: array of [MemorySearchResult](#memorysearchresult)
**404**: Not found
**401**: Unauthorized
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

## Families

### POST /api/families/

**Create New Family**

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [FamilyCreateRequest](#familycreaterequest)

**Responses:**

**201**: Successful Response
  - Content-Type: `application/json`
  - Schema: [FamilyBasicResponse](#familybasicresponse)
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### POST /api/families/join

**Join Existing Family**

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [FamilyJoinRequest](#familyjoinrequest)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [FamilyBasicResponse](#familybasicresponse)
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### GET /api/families/mine

**Get My Family Details**

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [FamilyDetailResponse](#familydetailresponse) | null

---

### PUT /api/families/mine

**Update My Family Settings**

(Authenticated) Update the settings (name, language) of the current user's family.

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [FamilySettingsUpdateRequest](#familysettingsupdaterequest)

**Responses:**

**200**: Successful Response
  - Content-Type: `application/json`
  - Schema: [FamilyBasicResponse](#familybasicresponse)
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### POST /api/families/mine/main_characters

**Set Main Family Character**

(Authenticated) Adds a character to the family's main character list.

**Request Body:**

Required: True

Content-Type: `application/json`

Schema: [SetMainCharacterRequest](#setmaincharacterrequest)

**Responses:**

**204**: Successful Response
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

### DELETE /api/families/mine/main_characters/{character_id}

**Remove Main Family Character**

(Authenticated) Removes a character from the family's main character list.

**Parameters:**

- `character_id` (path): string (required)

**Responses:**

**204**: Successful Response
**422**: Validation Error
  - Content-Type: `application/json`
  - Schema: [HTTPValidationError](#httpvalidationerror)

---

## Data Models

### Body_upload_character_photos_api_characters__character_id__photos_post

**Properties:**

- `files`: array of string (binary) (required)

---

### Character

**Properties:**

- `name`: string (max 100 chars) (min 1 chars) (required)
- `bio`: string (max 2000 chars) | null (optional)
- `photo_paths`: array of string | null (optional)
- `avatar_url`: string | null (optional)
- `birthdate`: string (date) | null (optional)
- `visual_description`: string | null (optional)
- `id`: string (uuid) (required)
- `family_id`: string (uuid) (required)
- `created_at`: string (date-time) (optional)
- `updated_at`: string (date-time) | null (optional)

---

### CharacterCreate

**Properties:**

- `name`: string (max 100 chars) (min 1 chars) (required)
- `bio`: string (max 2000 chars) | null (optional)
- `photo_paths`: array of string | null (optional)
- `avatar_url`: string | null (optional)
- `birthdate`: string (date) | null (optional)
- `visual_description`: string | null (optional)

---

### CharacterSummaryResponse

**Properties:**

- `id`: string (uuid) (required)
- `name`: string (required)
- `avatar_url`: string | null (optional)

---

### CharacterUpdate

**Properties:**

- `name`: string (max 100 chars) (min 1 chars) | null (optional)
- `bio`: string (max 2000 chars) | null (optional)
- `photo_paths`: array of string | null (optional)
- `avatar_url`: string | null (optional)
- `birthdate`: string (date) | null (optional)
- `visual_description`: string | null (optional)

---

### FamilyBasicResponse

**Properties:**

- `id`: string (uuid) (required)
- `name`: string | null (optional)
- `join_code`: string | null (optional)
- `default_language`: string | null (optional)

---

### FamilyCreateRequest

**Properties:**

- `name`: string (optional)

---

### FamilyDetailResponse

**Properties:**

- `id`: string (uuid) (required)
- `name`: string | null (optional)
- `join_code`: string | null (optional)
- `default_language`: string | null (optional)
- `members`: array of [FamilyMemberResponse](#familymemberresponse) (optional)
- `main_characters`: array of [CharacterSummaryResponse](#charactersummaryresponse) (optional)

---

### FamilyJoinRequest

**Properties:**

- `join_code`: string (required)

---

### FamilyMemberResponse

**Properties:**

- `id`: string (required)
- `display_name`: string | null (optional)
- `avatar_url`: string | null (optional)

---

### FamilySettingsUpdateRequest

**Properties:**

- `name`: string | null (optional)
- `default_language`: string | null (optional)

---

### HTTPValidationError

**Properties:**

- `detail`: array of [ValidationError](#validationerror) (optional)

---

### Memory

**Properties:**

- `text`: string (required)
- `date`: string (date) (required)
- `id`: string (uuid) (required)
- `family_id`: string (uuid) (required)
- `created_at`: string (date-time) (optional)

---

### MemoryCreate

**Properties:**

- `text`: string (required)
- `date`: string (date) (required)

---

### MemorySearchRequest

**Properties:**

- `query`: string (required)
- `family_id`: string (uuid) (required)
- `match_threshold`: number (default: 0.7) (optional)
- `match_count`: integer (default: 5) (optional)

---

### MemorySearchResult

**Properties:**

- `text`: string (required)
- `date`: string (date) (required)
- `id`: string (uuid) (required)
- `family_id`: string (uuid) (required)
- `created_at`: string (date-time) (optional)
- `similarity`: number (required)

---

### MemoryUpdate

**Properties:**

- `text`: string | null (optional)
- `date`: null (optional)

---

### SetMainCharacterRequest

**Properties:**

- `character_id`: string (uuid) (required)

---

### Story

**Properties:**

- `id`: string (uuid) (optional)
- `family_id`: string (uuid) (required)
- `title`: string | null (optional)
- `input_prompt`: string | null (optional)
- `pages`: array of [StoryPageProgress](#storypageprogress) (optional)
- `language`: string (optional)
- `target_age`: integer | null (optional)
- `character_ids`: array of string (uuid) | null (optional)
- `status`: string (optional)
- `created_at`: string (date-time) (optional)

---

### StoryBasic

Basic information about a story for listing.

**Properties:**

- `id`: string (uuid) (required)
- `title`: string | null (optional)
- `language`: string (required)
- `status`: string (required)
- `created_at`: string (date-time) (required)

---

### StoryGenerationRequest

Request body for triggering story generation.

**Properties:**

- `character_ids`: array of string (uuid) (required)
- `prompt`: string (max 1000 chars) | null (optional)
- `language`: string | null (optional)
- `target_age`: integer | null (optional)

---

### StoryPageProgress

**Properties:**

- `page`: integer (required)
- `description`: string | null (required)
- `text`: string | null (required)
- `image_prompt`: string | null (required)
- `image_url`: string | null (required)
- `characters_on_page`: array of string | null (required)

---

### ValidationError

**Properties:**

- `loc`: array of string | integer (required)
- `msg`: string (required)
- `type`: string (required)

---

