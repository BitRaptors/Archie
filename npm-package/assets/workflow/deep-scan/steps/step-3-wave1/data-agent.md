### Data agent (only if `has_persistence_signal == true`)

> **CRITICAL INSTRUCTIONS:**
> You are analyzing a codebase to inventory its data models, persistence stores, and the lifecycle of each model (how to add a new one, how to modify, how to read, what the backup posture is, what tests exist, which business logic references it).
>
> Your goal is to OBSERVE and DESCRIBE what exists, NOT to invent procedures or fabricate backup/test claims. Empty fields are correct when the evidence is absent — do NOT pad.
>
> **DO NOT:**
> - Fabricate backup strategies, test coverage, or migration procedures that aren't visible in the codebase or infra config.
> - Assume a stack convention. The same ORM is used wildly differently across projects — describe what you see.
> - Read every migration file. The orchestration step's bulk-content rule applies: `migration` is a bulk category. You MAY surgically Read 1-2 recent migration files per store to extract the observed procedure — this is a stated exception, not a license to enumerate.
>
> **DO:**
> - Cite a code artifact or config file for every claim. `how_to_add: "Write an alembic migration"` is filler; `how_to_add: "Write an alembic migration under backend/alembic/versions/ (latest example: 2026_03_01_add_idempotency_key.py:14-22 — uses op.add_column with server_default), then regenerate models via 'make types'"` is grounded.
> - Use the codebase's actual vocabulary. If the project calls them "schemas" not "models", reflect that.
> - Report mobile-only / stateless / pure-frontend cases honestly: empty `data_models` and `persistence_stores` arrays are valid output.
>
> Read all source files relevant to data: schema files (`schema.prisma`, `*.sql`, `*.proto`, `*.graphql`, `*.fbs`), ORM model files, config files (`alembic.ini`, `database.yml`, `Settings.toml`, Spring `application.yml`, Room `@Database` declarations, CoreData `*.xcdatamodeld` references, app DB init code), Terraform / Helm / Compose blocks that declare DBs, scheduled-backup scripts, repository/DAO classes that read and mutate models.
>
> ### 1. Persistence Stores
>
> Enumerate every store. A "store" is anywhere data lives across a process or session boundary. Categories to check:
> - **Primary databases**: PostgreSQL, MySQL, SQLite, Oracle, SQL Server, MongoDB, DynamoDB, Cassandra, etc.
> - **Caches**: Redis, Memcached, in-memory LRU, browser localStorage/IndexedDB.
> - **Search**: Elasticsearch, OpenSearch, Meilisearch, Algolia, Typesense, sqlite FTS.
> - **Queues / streams**: RabbitMQ, Kafka, SQS, Redis Streams, NATS.
> - **Object storage with schema/config**: S3, GCS, R2 — only when the repo declares prefixes/lifecycles/access policies (otherwise list as integration, not a store).
> - **Mobile local persistence**: UserDefaults / NSUbiquitousKeyValueStore (iOS), SharedPreferences / DataStore (Android), Room, CoreData, Realm, sqflite, Hive, AsyncStorage, MMKV.
> - **App-level files**: SQLite databases bundled with the app, JSON/CSV/YAML data files treated as authoritative state.
>
> For each store record:
> - **name**: stable identifier you can reference from `data_models[*].store` (e.g. `primary_postgres`, `redis_cache`, `room_db`, `shared_preferences`). Lowercase snake_case.
> - **engine**: actual engine + version when visible (e.g. `PostgreSQL 15`, `Redis 7`, `Room 2.6.1`, `SQLite (bundled)`).
> - **role**: one of `primary | cache | search | queue | local | analytics | object_storage`.
> - **migrations_dir**: directory path relative to project root, or empty string when the store has no migrations (caches, local prefs).
> - **backup_strategy**: extract from infra config, scheduled jobs, README/runbook references. Empty string when no evidence exists in the repo — do NOT invent.
> - **owned_models**: array of `data_models[*].name` values (filled in section 2). May be empty for stores that hold only ephemeral/non-modeled data.
>
> ### 2. Data Models Inventory
>
> Every entity that maps to a store, every DTO that crosses an API boundary, every value object the codebase treats as a contract. For each:
>
> - **name**: the class / type / table name as it appears in code (e.g. `Order`, `users`, `UserDocument`). Don't normalize casing — match the source.
> - **location**: file path relative to project root. MUST exist in the scan's file_tree. For multi-file models (e.g. a Room `@Entity` declared in one file with DAO in another) cite the entity declaration file.
> - **kind**: one of:
>   - `table` — relational DB row (SQLAlchemy Base, ActiveRecord, Django Model, Ent Schema, Room @Entity, etc.)
>   - `document` — schemaless or document DB (MongoDB, DynamoDB, Firestore)
>   - `entity` — domain entity not strictly mapped to a single table (DDD aggregates, event-sourced types)
>   - `dto` — wire-format data transfer object (REST/GraphQL/gRPC payloads, OpenAPI schemas)
>   - `value_object` — immutable value (Money, Address, Coordinate) referenced widely but not persisted on its own
>   - `key_value` — single key-value entry in a KV store (e.g. UserDefaults key, SharedPreferences key, Redis hash)
>   - `local_persistence` — mobile/desktop local store entries that don't fit table/document (a CoreData entity, a Realm object, a Room entity for local-only data)
> - **store**: the `persistence_stores[*].name` this model lives in. Empty string for pure DTOs / value objects that are not persisted.
> - **key_fields**: 3-8 most-significant fields by code reference frequency, plus any field that participates in a `key_fields` invariant (PK, FK, unique index). Don't enumerate every column — pick what callers actually touch.
> - **invariants**: array of strings declaring schema-level guarantees grounded in code. Examples:
>   - `"PK id"` (always include the primary key)
>   - `"UNIQUE(user_id, idempotency_key)"`
>   - `"FK user_id → users.id ON DELETE CASCADE"`
>   - `"NOT NULL email"`
>   - `"INDEX created_at"`
>   - `"soft_delete (deleted_at)"`
>   - `"audit (created_at, updated_at)"`
>   Each invariant MUST be readable from a concrete schema artifact (migration file, ORM column declaration, schema.prisma block). Cite the file:line at the end when the source is non-obvious: `"UNIQUE(ns, customer_id) — backend/alembic/versions/2025_11_add_customer.py:18"`.
> - **owned_by_component**: best-effort attribution to a component you can name from this codebase. Since the Structure agent runs in parallel and you cannot read its output, use a heuristic: nearest enclosing folder whose name matches a component-typical pattern (`services`, `repositories`, `repository`, `models`, `entities`, `domain`, `page_<feature>`, `feature_<name>`, `<feature>/data`). If no clear owner, leave as empty string — Wave 2 reconciles ownership in synthesis.
> - **lifecycle**: an object with the six fields below. Each field is a single human sentence (or short paragraph) grounded in observed code. Empty string when no evidence exists.
>
>   - **how_to_add**: the observed procedure for adding a new field/column/property to this model. Walk the most recent 1-2 migrations (or the equivalent in your stack) and describe the actual steps a maintainer takes. *Bad:* "Use a migration." *Good:* "Write an alembic migration under `backend/alembic/versions/` (latest example: `2026_03_01_add_idempotency_key.py`), then add the SQLAlchemy column on `Order` in `backend/models/order.py`, and regenerate API types via `make types`."
>
>   - **how_to_modify**: the observed procedure for changing an existing field (type change, rename, default change). *Bad:* "Update the model." *Good:* "Add a new alembic migration; never edit historical migrations. Renames require the 2-step compatibility migration documented in `backend/alembic/README.md` — add the new column, dual-write in app code, drop the old column in a follow-up migration."
>
>   - **how_to_read**: which class/repository/DAO callers use to read this model in practice. Cite ≥2 example callers. Call out anti-patterns observed (raw SQL in handlers, direct ORM access bypassing the repository, etc.). *Good:* "Always via `OrderRepository.find_by_user_id()` / `OrderRepository.find_pending()` (see `backend/repositories/orders.py`). Direct `db.query(Order)` in handlers (`backend/handlers/admin.py:42`) is a legacy anti-pattern documented in [pitfalls]."
>
>   - **backup_strategy**: backup, retention, PITR posture for the data in this model. Source: infra config, Terraform RDS blocks, Supabase config, scheduled backup scripts in the repo. *Empty string when no evidence exists in the repository — do NOT infer from the engine name alone.*
>
>   - **related_business_logic**: 3-5 files (paths in file_tree) that mutate or read this model heavily, ranked by import-then-call frequency. These are the files a maintainer touching the model needs to know about.
>
>   - **tests**: array of test file paths that exercise this model or its repository/DAO. Empty array when no tests reference the model's class name.
>
> ### 3. Cross-Model Relationships
>
> Record FK edges, embedding, and ownership relationships **inline in each model's `invariants` array** (e.g. `"FK user_id → users.id"`, `"embeds shipping_address (Address value object)"`). Do NOT emit a separate relationships graph in this pass — Wave 2 synthesis builds the cross-cutting view.
>
> ### 4. Draft Findings (sent to Wave 2)
>
> When you notice problems only this agent can see, capture them as **draft findings** in a top-level `findings` array. Wave 2 upgrades them to canonical (fills `root_cause` and `fix_direction` with architectural grounding). Examples of data-shaped draft findings:
>
> - Model referenced by code but no schema declaration found: *"Model `LegacyOrder` referenced in `services/checkout.py:42` and `handlers/orders.py:88` but no `@Entity` / `Base` subclass / `model` block in any schema file."*
> - Migration file exists for a table that has no ORM model: *"Migration `2024_07_add_audit_log.py` creates table `audit_log` but no model file references it — orphan table or external consumer?"*
> - Schema vs business-code mismatch: *"`User.email` declared `NOT NULL` in `backend/alembic/versions/2024_01_init.py:34` but `services/onboarding.py:67` writes empty string when the OAuth provider returns no email."*
> - Two models share a column name with semantically different types or constraints: *"`User.id UUID` (PK) but `events.user_id TEXT` (FK target?) — type mismatch on the FK boundary."*
>
> Draft finding shape (mirror the Structure agent's pattern):
>
> ```json
> {
>   "problem_statement": "<one-sentence description>",
>   "evidence": ["<file:line — quote>", "<file:line — quote>"],
>   "root_cause": "",
>   "fix_direction": "",
>   "severity": "error|warn|info",
>   "confidence": 0.8,
>   "applies_to": ["<file_path_or_component>"],
>   "source": "scan:data",
>   "depth": "draft"
> }
> ```
>
> Leave `root_cause` and `fix_direction` empty — Wave 2 fills them when it upgrades the draft to canonical.
>
> ### 5. Return JSON
>
> ```json
> {
>   "data_models": [
>     {
>       "name": "",
>       "location": "",
>       "kind": "table|document|entity|dto|value_object|key_value|local_persistence",
>       "store": "",
>       "key_fields": [],
>       "invariants": [],
>       "owned_by_component": "",
>       "lifecycle": {
>         "how_to_add": "",
>         "how_to_modify": "",
>         "how_to_read": "",
>         "backup_strategy": "",
>         "related_business_logic": [],
>         "tests": []
>       }
>     }
>   ],
>   "persistence_stores": [
>     {
>       "name": "",
>       "engine": "",
>       "role": "primary|cache|search|queue|local|analytics|object_storage",
>       "migrations_dir": "",
>       "backup_strategy": "",
>       "owned_models": []
>     }
>   ],
>   "findings": []
> }
> ```
>
> Empty arrays are valid output when the codebase genuinely has no persistence layer at the surface you analyzed (pure-frontend SPA, stateless library, CLI with no state). Do NOT fabricate models to fill the section.
