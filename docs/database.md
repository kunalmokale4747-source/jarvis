# JARVIS — Database Design

**Status:** Design (Phase 0). Initial migration lands in Phase 1.
**Last updated:** 2026-10-07

## 1. Engine strategy

| Environment | Engine | Why |
|---|---|---|
| Development / tests | **SQLite** | no Docker or Postgres in the Termux/proot dev box; zero-install; tests run anywhere |
| Production | **PostgreSQL (Supabase)** | requested; + Auth, Storage, Realtime, pgvector |

**One schema, one ORM.** SQLAlchemy 2.0 models + Alembic migrations are the single source of truth; `DATABASE_URL` selects the engine.

### Portability rules (enforced by tests)

1. Only portable column types: `String, Integer, Float, Boolean, DateTime(timezone=True), Text, JSON, LargeBinary, Enum`. No `JSONB`, `ARRAY`, `UUID` (store as 36-char string), `tsvector`.
2. No engine-specific SQL in model code; migrations may branch on `bind.dialect.name` when unavoidable (documented inline).
3. Booleans stored as 0/1 on SQLite — always read/write through SQLAlchemy `Boolean`, never raw SQL.
4. Timestamps always timezone-aware UTC; display timezone is an app concern.
5. Vector search: `vector(1536)` column on Postgres (pgvector) ↔ `LargeBlob` packed floats on SQLite, behind one `VectorIndex` interface with `add/search`. Retrieval degrades to Python cosine on SQLite — same results, slower (acceptable for dev).
6. Full-text: Postgres `tsvector` ↔ SQLite FTS5 behind `SearchIndex` interface; keyword fallback shipped first (Phase 2), FTS/vector upgrades later.

Migrations: Alembic, forward + rollback required for every change, generated in dev against SQLite and verified against Postgres in CI (Phase 9).

---

## 2. Entity overview

```
users ──┬── user_profiles
        ├── memories ──────────────┐
        ├── goals (self-tree)      │
        ├── projects ── tasks ─────┤  all rows carry user_id
        ├── opportunities          │  (ownership enforced in repo layer)
        ├── applications           │
        ├── contacts ── interactions
        ├── emails / calendar_events / content_items
        ├── approvals, audit_logs, tool_executions, events, jobs
        ├── schedules, notifications, integrations, settings
        └── sessions
```

---

## 3. Core tables (Phase 1)

### `users`
| col | type | notes |
|---|---|---|
| id | string(36) PK | uuid4 |
| email | string(320) unique | |
| display_name | string(120) nullable | |
| role | enum(USER,ADMIN) | default USER |
| auth_provider | enum(SUPABASE,DEV) | |
| created_at / updated_at | timestamptz | |

### `user_profiles` — editable from dashboard, **never hardcoded in source**
| col | type | notes |
|---|---|---|
| id | string(36) PK | |
| user_id | FK users.id, unique | |
| name | string(200) | |
| education | JSON | list of entries |
| skills | JSON | `[{name, level, evidence}]` |
| experience | JSON | list of entries |
| projects | JSON | summary list (authoritative projects live in `projects`) |
| career_goals / business_goals / financial_goals | JSON | |
| location | string(120) | |
| languages | JSON | |
| preferences | JSON | tone, working hours, channels |
| availability | JSON | hours/days, focus blocks |
| resume | JSON | structured resume (file itself in storage) |
| portfolio | JSON | links |
| social_profiles | JSON | `{linkedin, instagram, github, …}` |
| professional_profiles | JSON | |
| current_priorities | JSON | short list |
| is_complete | bool | drives dashboard "complete your profile" |
| updated_at | timestamptz | |

### `audit_logs` (append-only)
`id, user_id, ts, agent, action, tool, reason, input_summary(JSON, redacted), output_summary(JSON, redacted), permission_level(int), approval_id, result(enum), error, correlation_id`
Indexes: `(user_id, ts desc)`, `(correlation_id)`.

### `approvals`
`id, user_id, tool, agent, input(JSON), reason, risk_level, status(PENDING|APPROVED|DENIED|EXPIRED), created_at, decided_at, expires_at, decision_note`
Index: `(user_id, status, created_at desc)`.

---

## 4. Domain tables

### `goals` — recursive mission hierarchy
`id, user_id, parent_id (self FK, nullable), kind(MISSION|OBJECTIVE|PROJECT_LEVEL), title, description, metric, target_value, current_value, unit, status(ACTIVE|PAUSED|DONE|CANCELLED), priority, deadline, created_at, updated_at`
- Roll-up progress = query over descendants (stored `progress` cache updated by Executive Agent).
- `tasks.project_id → goals.id` (kind PROJECT) keeps the chain GOAL → OBJECTIVE → PROJECT → TASK.

### `projects`
`id, user_id, goal_id, name, description, status(BACKLOG|ACTIVE|ON_HOLD|DONE|CANCELLED), repo_url?, created_at, updated_at`

### `tasks`
`id, user_id, title, description, priority(P0|P1|P2|P3), deadline, status(TODO|IN_PROGRESS|BLOCKED|WAITING_APPROVAL|DONE|CANCELLED), estimated_minutes, category, project_id?, goal_id?, parent_task_id?, created_at, started_at, completed_at, reprioritized_reason?, score real`
- `task_dependencies(task_id, depends_on_id)` — cycle detection in service layer.
- Indexes: `(user_id, status, deadline)`, `(user_id, priority, score desc)`.

### `memories`
`id, user_id, type(enum 11 categories), content text, structured_ref (table,id) nullable, importance float 0-1, confidence float 0-1, source(agent|tool|user|import), embedding BLOB/vector nullable, created_at, updated_at, expires_at?, superseded_by?`
- Indexes: `(user_id, type, importance desc)`, `(user_id, updated_at desc)`.
- Dedup: near-duplicate check at write time (content hash + cosine threshold).

### `opportunities`
`id, user_id, source, external_id?, title, organization, role?, income_text?, income_value?, location, remote bool, url, deadline?, description, raw(JSON), status(NEW|CONSIDERING|APPLIED|REJECTED|SKIPPED|EXPIRED), created_at, updated_at`
Unique: `(user_id, source, external_id)` or `(user_id, url hash)` to prevent duplicates.

### `opportunity_scores` — one per evaluation, kept for explainability
`id, opportunity_id, score int 0-100, skill_match, experience_match, income_potential, success_probability, time_required, learning_required, competition, urgency, application_difficulty (each 0-10), breakdown JSON, rationale text, model, created_at`

### `applications`
`id, user_id, opportunity_id?, status(FOUND|REVIEWING|READY|APPROVAL_REQUIRED|APPLIED|FOLLOW_UP|INTERVIEW|REJECTED|OFFER|ACCEPTED), resume_version_id?, cover_letter_id?, resume_snapshot JSON, cover_letter_text, submitted_at?, follow_up_dates JSON, rejection_reason?, notes, created_at, updated_at`
State machine validated in service layer; `→APPLIED` transition requires an approved approval row (Phase 4 invariant test).

### `contacts` (CRM) + `interactions`
`contacts: id, user_id, name, company, role, email, phone, social JSON, status(LEAD|CONTACTED|REPLIED|INTERESTED|FOLLOW_UP|CUSTOMER|PARTNER|CLOSED), last_contact_at, next_action, next_action_at, notes, created_at, updated_at`
`interactions: id, contact_id, kind(email|call|meeting|dm|note), direction, summary, occurred_at`

### `emails` / `calendar_events` / `content_items` (Phase 5/7)
- `emails: id, user_id, external_id, thread_id, direction, from_addr, to_addrs JSON, subject, snippet, body_ref, category(9 enums), is_urgent, summary, detected_opportunity_id?, status(UNREAD|ARCHIVED|DRAFTED|REPLIED), received_at, processed_at`
- `calendar_events: id, user_id, external_id, title, start_at, end_at, attendees JSON, location, conflict_group?, brief JSON, source, created_at`
- `content_items: id, user_id, platform(LINKEDIN|INSTAGRAM|…), kind(post|story|reel), title, body, hooks JSON, hashtags JSON, media_ref, status(IDEA|DRAFT|APPROVAL_REQUIRED|SCHEDULED|PUBLISHED|FAILED), scheduled_at, published_at, performance JSON`

---

## 5. Platform tables

### `events` (durable outbox)
`event_id PK, type, user_id, payload JSON, correlation_id, causation_id, occurred_at, published_at?, attempts int`
- Written in the same transaction as the domain change; dispatcher marks `published_at`.
- At-least-once delivery; consumers idempotent via `event_id`.

### `jobs`
`id, queue, name, payload JSON, status(QUEUED|RUNNING|SUCCEEDED|FAILED|DEAD), attempts, max_attempts, run_at, started_at, finished_at, error, idempotency_key unique`
- Backs `JobQueue`; Redis holds the hot queue in prod, DB is the record either way (Phase 8 can read DB directly in dev).

### `schedules`
`id, user_id, name, cron, timezone, agent, enabled bool, config JSON, last_run_at, next_run_at, created_at`
Defaults seeded: 07:00 daily analysis · 09:00 opportunity scan · 12:00 task review · 18:00 email/opportunity update · 21:00 daily review (all editable).

### `notifications`
`id, user_id, channel(WEB|EMAIL|PUSH), title, body, severity(INFO|ACTION_REQUIRED|URGENT), read_at?, link, created_at`

### `tool_executions`
`id, user_id, agent, tool, input_hash, input_summary JSON, output_size, status, duration_ms, error, permission_level, approval_id?, created_at`

### `integrations`
`id, user_id, provider(GMAIL|CALENDAR|LINKEDIN|INSTAGRAM|GITHUB|N8N|BROWSER), status(NOT_CONFIGURED|PENDING_OAUTH|CONNECTED|ERROR|REVOKED), scopes JSON, token_ref (encrypted), last_sync_at, error, created_at`
- Tokens encrypted at rest (§security). UI reads `status` to render **"Not connected"** honestly.

### `sessions` / `settings`
- `sessions` — dev-mode session tokens (Phase 1); production uses Supabase JWT (stateless) + refresh handled by Supabase.
- `settings(user_id, key, value JSON)` — permission tightening, schedule config, budget caps, notification prefs.

---

## 6. Data-volume & indexing notes

- All list queries paginated (keyset where possible); hard caps on `memories.content` and audit summaries.
- High-churn tables: `tool_executions`, `events`, `jobs` — monthly partition-ready (Postgres) but not implemented until real load appears.
- Soft deletes via `status`/`expires_at` on user data; hard delete = L2 flow (Phase 9).
- Backup: Supabase PITR (Phase 9) + nightly logical dump to object storage; restore drill documented in `deployment.md` (future doc).

---

## 7. Seed policy

`database/seeds/` contains **only** structural defaults: schedules, enum reference, demo-safe fixtures for tests. **No personal data of the user is ever committed** — profile is created at runtime through the dashboard or imported via a private, git-ignored seed script.
