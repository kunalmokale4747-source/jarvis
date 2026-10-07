# JARVIS — System Architecture

**Status:** Design (Phase 0)
**Last updated:** 2026-10-07

JARVIS is a personal AI operating system: a long-running agent platform that understands the user's goals, remembers context, identifies useful actions, prepares them, asks permission when required, executes approved actions, verifies results, and reports what to do next.

It is **not** a chatbot with a dashboard attached. Chat is one interface into a core orchestration engine.

---

## 1. Environment constraints (observed)

The development environment was inspected before any design decision was made:

| Item | Value |
|---|---|
| OS | Debian 13 (trixie), arm64, running in Termux → proot (uid 0 inside proot) |
| Node.js | v22.23.3 |
| npm | 12.2.0 |
| Python | 3.13.5 (pip 26.1.2) |
| Git | 2.47.3 (no user.name/user.email configured yet) |
| Docker | **Not available** |
| GitHub CLI (`gh`) | **Not available** |
| PostgreSQL / Redis | **Not installed** |
| `apt-get` | Available (Debian arm64 repos) |
| Disk | ~209 GB free |
| RAM / CPU | 7.5 GB / 8 cores |
| Existing project in `/root` | None — clean start at `/root/jarvis` |

These constraints directly shape the architecture:

1. **No Docker in dev.** `docker-compose.yml` is written for *cloud deployment and CI*, not for local dev. Local dev runs `api`, `web`, and workers as plain processes via `scripts/`.
2. **No local PostgreSQL/Redis.** Development and tests use **SQLite** (via the same SQLAlchemy ORM and Alembic migrations used in production). Production uses PostgreSQL (Supabase) and Redis. The switch is a single `DATABASE_URL`. Portability rules in `database.md` prevent SQLite-only features from leaking into the schema.
3. **Same-machine risk.** The dev device (Android/Termux) is *not* the runtime. Production runs in the cloud (Phase 9). Nothing in the design assumes the phone stays online.
4. **arm64.** All dependencies must have arm64 support or be pure Python/JS. No x86-only tooling.

---

## 2. High-level topology

```
        ANDROID (dev / control / chat / notifications)
             │  Termux · proot Debian · OpenCode
             │  JARVIS Web UI (mobile-first)
             ▼
          INTERNET
             ▼
        CLOUD JARVIS  (24/7, source of truth)
   ┌─────────┴──────────────────────────────┐
   │                                        │
FRONTEND (Vercel)                     BACKEND (Railway/Render/Fly/VPS)
  Next.js + TS + Tailwind               FastAPI + Python
   │  REST + SSE/Realtime                    │
   └──────────────┬─────────────────────────┘
                  ▼
        ┌─────────────────────────┐        ┌──────────────────────┐
        │ PostgreSQL (Supabase)   │◄──────►│ Redis                │
        │  · data · audit · jobs  │        │  · queue · cache     │
        └─────────────────────────┘        │  · pub/sub events    │
                  ▲                        └──────────┬───────────┘
                  │                                   │
        ┌─────────┴──────────┐             ┌──────────▼───────────┐
        │ Worker processes   │◄────────────│ Scheduler (Celery    │
        │  · job execution   │  enqueue    │  beat / RQ scheduler)│
        │  · agent runs      │             └──────────────────────┘
        │  · scheduled scans │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────┐      ┌────────────────────────────┐
        │ AI Provider layer  │      │ Integrations (OAuth)       │
        │ OpenAI/Anthropic/  │      │ Gmail · Calendar · GitHub  │
        │ Gemini/Local       │      │ LinkedIn · Instagram · n8n │
        └────────────────────┘      └────────────────────────────┘
```

Key rule: **the phone is a client, never a runtime dependency.**

---

## 3. Monorepo layout

```
jarvis/
├── apps/
│   ├── web/                     # Next.js 15 + React + TypeScript + Tailwind
│   └── api/                     # FastAPI application (HTTP layer only)
├── core/                        # Pure Python domain layer (no HTTP imports)
│   ├── llm/                     # AI provider abstraction
│   ├── memory/                  # memory storage + relevance retrieval
│   ├── permissions/             # permission engine + approval workflow
│   ├── tools/                   # tool registry, schemas, executors
│   ├── events/                  # event bus + durable outbox
│   ├── scheduler/               # cron-style proactive schedules
│   ├── notifications/           # notification dispatch
│   ├── orchestration/           # JARVIS CORE: intent → plan → act → verify
│   ├── scoring/                 # decision engine & opportunity scoring
│   └── db/                      # SQLAlchemy models, session, repositories
├── agents/                      # agent definitions (prompts + tool allowlists)
│   ├── executive/  opportunity/  career/  research/
│   ├── email/      social/      business/ learning/ planning/
├── integrations/                # one module per external service, behind interface
│   ├── gmail/ calendar/ linkedin/ instagram/ github/ browser/
├── prompts/                     # versioned prompt templates (.md)
├── database/
│   ├── migrations/              # Alembic
│   └── seeds/
├── tests/                       # unit + integration + api tests
├── scripts/                     # dev orchestration, setup, deploy helpers
├── docs/
├── .env.example
├── README.md
└── docker-compose.yml           # cloud/CI only — not required for local dev
```

### Deviations from the requested structure (and why)

1. **`core/llm/`, `core/scoring/`, `core/db/` added.** The provider abstraction, decision engine, and data-access layer are cross-cutting; putting them in `core/` keeps `apps/api` a thin HTTP shell and lets agents/tools be tested without a server.
2. **Agents hold only prompts + declarative config; reusable logic lives in `core/` and `integrations/`.** Agents must not duplicate tool code. An agent = system prompt + tool allowlist + routing config + output contract. This makes agents inspectable and testable without an LLM.
3. **`integrations/` is outside `core/`.** External services change, break, and require credentials. Isolating them means an unavailable integration is a clean `IntegrationUnavailable` result, never a fake success.
4. **`docker-compose.yml` kept but demoted.** It exists for production parity and CI, documented as not usable in this dev environment (no Docker).

### Layer dependency rule

```
apps/api  →  agents, core, integrations
agents    →  core, integrations
core      →  (stdlib + infra libs only; never imports agents or apps)
integrations → core interfaces only
```

Enforced by import-linter (Phase 1 test suite). Violations fail CI.

---

## 4. JARVIS CORE — orchestration engine

The core is a deterministic pipeline. The LLM is used *inside* the pipeline for understanding and generation, but **never** for deciding whether a permission check happens.

```
USER REQUEST (chat, event, schedule)
   │
   1. INTENT          classify + extract entities (LLM, structured output)
   2. CONTEXT         load active goals, projects, time window, session state
   3. MEMORY          relevance retrieval (top-k by score, filtered by type/importance)
   4. PLANNER         produce Plan: list of Steps {agent, tool, args, permission}
   5. AGENT           agent executes its step (LLM reasoning over its contract)
   6. PERMISSION      PermissionEngine.check(tool, level)  ← cannot be skipped
   7. TOOL            executor runs with timeout + retry policy (safe retries only)
   8. VERIFICATION    step result validated against output_schema + sanity rules
   9. MEMORY UPDATE   store durable outcomes only (curated, not raw transcripts)
  10. RESPONSE        generate user-facing reply w/ citations, next actions
  11. AUDIT           append audit_log row (always, success or failure)
```

### Core data contracts

```python
Request  { user_id, message, channel, session_id, attachments }
Intent   { category, confidence, entities, requires_plan: bool }
Context  { goals[], active_projects[], today, timezone, pending_approvals[] }
Plan     { steps: [Step], estimated_cost, risk_level }
Step     { agent, tool, input, permission_level, idempotency_key }
Result   { step_id, ok, output, error?, verification }
Response { text, artifacts[], pending_approvals[], suggested_next_actions[] }
```

### Failure handling contract

Every step result is one of `OK | FAILED | BLOCKED_APPROVAL | UNAVAILABLE | TIMEOUT`.
The core never converts a failure into a success message. On failure it reports:
**what failed → why → what already happened → what needs to happen next.**
Safe (idempotent, level-0) steps may retry per `retry_policy`. Level 1–2 steps never auto-retry after dispatch.

---

## 5. Tool system

Tools are the only way anything in the system acts on the outside world.

```python
Tool(
    name="search_opportunities",
    description="Search configured sources for opportunities",
    input_schema={...JSON Schema...},
    output_schema={...JSON Schema...},
    permission_level=0,          # 0 auto | 1 approval | 2 explicit confirm
    risk_level="low",            # low | medium | high | critical
    timeout_s=30,
    retry_policy=RetryPolicy(max_attempts=3, backoff="exp", safe_only=True),
    handler=callable,            # registered Python callable, NOT LLM-generated code
)
```

Rules:

- **The LLM never emits executable code or shell commands.** It emits a tool *name* + JSON arguments. The registry validates arguments against `input_schema` before the handler runs.
- Handlers run with: no ambient credentials, scoped config, hard timeout, and captured structured logs.
- Tool output is returned to the LLM as **marked untrusted data** (see `security.md` §Prompt injection).
- Every execution writes a `tool_execution` row (input hash, output size, duration, status).
- Tools whose integration is not configured return `UNAVAILABLE` with a machine-readable reason. **Never simulated output.**

Initial tool inventory (Phase 1–3):

| Tool | Level | Risk |
|---|---|---|
| `memory.search` / `memory.store` | 0 | low |
| `task.create` / `task.update` | 0 | low |
| `goal.create` / `goal.update` | 0 | low |
| `profile.read` / `profile.update` | 0/1 | medium (public fields) |
| `web.search` | 0 | low |
| `opportunity.search` | 0 | low |
| `opportunity.score` | 0 | low |
| `research.run` | 0 | medium |
| `email.read` / `email.summarize` | 0 | medium |
| `email.send` | **1** | high |
| `application.submit` | **1–2** | critical |
| `calendar.read` | 0 | medium |
| `calendar.create_event` | **1** | medium |
| `social.post.publish` | **1** | high |
| `financial.transaction` | **2** | critical |
| `account.delete` | **2** | critical |

---

## 6. Permission engine (mandatory, non-bypassable)

| Level | Name | Behavior | Examples |
|---|---|---|---|
| 0 | AUTOMATIC | Execute immediately, log it | read, search, analyze, draft, internal task/memory writes |
| 1 | USER APPROVAL | Create `approval_request`, halt step, notify user; execute only on explicit Approve | send email, apply to job, contact client, publish post, modify public profile |
| 2 | EXPLICIT CONFIRMATION | Level 1 plus typed confirmation of the specific action + fresh re-auth if session is stale | money movement, purchases, contracts, deletion, irreversible or sensitive disclosure |

Implementation invariants:

- The check happens in the **executor**, not in the planner or agent. A hallucinated plan cannot skip it.
- Approvals are persisted rows with full context (what, why, tool, args, risk), so they survive restarts and are visible on mobile.
- Deny / timeout (default 24 h) → step becomes `CANCELLED`, audit-logged, and the core tells the user it did *not* act.
- Users can tighten (never loosen) levels per tool via settings.
- Workflow-specific opt-in for auto-submission exists but must be set **per workflow, per tool**, and is revoked on config change.

---

## 7. Memory system

**Storage policy: curated, not transcript dumping.** A candidate memory must pass a value test — "will this help future assistance?" — before it is stored. Raw chat transcripts are kept separately as short-lived session history (rolling window), not as long-term memory.

### Categories
`PROFILE, GOAL, PROJECT, TASK, PREFERENCE, CONTACT, OPPORTUNITY, DECISION, LESSON, CONVERSATION, FACT`

### Record shape
```
id, user_id, type, content, structured_ref?, importance (0-1),
confidence (0-1), source (agent|tool|user|import), embedding?,
created_at, updated_at, expires_at?, superseded_by?
```

### Retrieval
Score = `w1·cosine(embedding) + w2·importance + w3·recency_decay + w4·type_affinity(intent) − penalties(stale, superseded)`
Top-k with per-type caps; the planner receives a compact digest, not raw dumps.

### Write path
Agent/tool proposes `MemoryWrite` → memory module validates type, deduplicates against existing (semantic near-dup check), applies importance/confidence → stores. Low-value proposals are dropped silently (counted in metrics, visible in agent logs).

**Dev portability:** embeddings stored in a `vector` column on Postgres (pgvector) and as packed BLOB + Python cosine fallback on SQLite. Same repository interface either way.

---

## 8. Goal → mission hierarchy

```
MISSION / GOAL            "Earn ₹50,000/month"
   └── OBJECTIVE          "Get freelance clients"
         └── PROJECT      "Freelancing"
               └── TASK   "Send 5 proposals this week"
```

- Stored as a **recursive `goals` table** (`parent_id`, `kind: mission|objective`, `metric`, `target`, `progress`), so depth is unlimited and roll-up progress is a query, not a calculation duplicated in UI.
- Every project/task carries `goal_id`; dashboard roll-ups derive from it.
- The Executive Agent reads roll-ups to detect: stalled objectives, orphan tasks (no goal), and blockers.

---

## 9. Task & decision systems

**Task fields:** title, description, priority (P0–P3), deadline, status (`TODO · IN_PROGRESS · BLOCKED · WAITING_APPROVAL · DONE · CANCELLED`), estimated_duration, category, project_id, goal_id, dependencies, created_at, completed_at.

**Reprioritization** is a deterministic scoring pass (not an LLM whim), recomputed on schedule and on relevant events:

```
urgency     = f(deadline proximity, is_dependency_of_blocking_work)
goal_weight = distance/rank of the parent goal in the mission tree
value       = decision-engine score (below)
score       = normalize(urgency, goal_weight, value, effort_inverse)
```

The LLM can *suggest* reordering with a stated reason; the applied order is always logged with the reason.

**Decision engine** (used for tasks, opportunities, and "what should I do next"):

```
VALUE = GoalImpact + IncomePotential + SuccessProbability + Urgency + LearningValue
        − TimeCost − Risk − Complexity
```

Each factor is 0–10 from an explicit rubric; the component breakdown is stored with the score so recommendations are explainable. **Optimization target: meaningful outcomes, not tasks-completed count.**

**Anti-busywork gate:** any proposed action must answer *"Will this meaningfully improve the user's goals?"* If the projected goal impact is below threshold, the core downgrades it, merges it, or refuses it — with a one-line explanation. Mass applications, spam DMs, and fake engagement are structurally excluded (never generated as options).

---

## 10. Opportunity scoring

Per opportunity: `SkillMatch, ExperienceMatch, IncomePotential, SuccessProbability, TimeRequired, LearningRequired, Competition, Urgency, ApplicationDifficulty` → **Opportunity Score /100** plus a per-factor breakdown.

Report contract (exactly what the user specified): Company, Role, Income, Location, Remote, Deadline, Match Score, Why it fits, Skills I have, Skills missing, Estimated success, Time required, Recommendation (`APPLY | CONSIDER | SKIP`), Next action.

Scoring is implemented as pure functions in `core/scoring/` with fixtures — fully unit-testable without any LLM or network.

---

## 11. LLM abstraction layer

```python
class AIProvider(Protocol):
    name: str
    def complete(self, req: LLMRequest) -> LLMResponse: ...
    def structured(self, req: LLMRequest, schema: dict) -> dict: ...
    def embedding(self, text: str) -> list[float]: ...
```

- Providers: `openai`, `anthropic`, `gemini`, `local` (any OpenAI-compatible endpoint, e.g. Ollama). Selected by `LLM_PROVIDER` env var; per-agent override allowed (e.g. cheap model for classification, strong model for planning).
- `LLMRequest` carries: messages, tools, schema, temperature, max_tokens, timeout, cost ceiling.
- The layer normalizes: tool-call format, structured output, usage/cost accounting, retries on transient errors, and **provider outage → `UNAVAILABLE`** (the app degrades honestly; it does not hallucinate answers).
- Cost per request is recorded and surfaced in Analytics.
- No provider SDK types leak past `core/llm/`.

---

## 12. Events & scheduled proactivity

**Durable event outbox.** Domain events are written to a DB table in the same transaction as the state change, then published to the bus and consumed by workers. Guarantees: at-least-once delivery, survives restarts, replayable.

Standard envelope:
```
{ event_id, type, occurred_at, user_id, payload, correlation_id, causation_id }
```

Example chains:

```
EMAIL_RECEIVED → email_agent → important? → CREATE_TASK → NOTIFY_USER
NEW_JOB_FOUND  → match_profile → score > 80 → CREATE_OPPORTUNITY → NOTIFY_USER
TASK_OVERDUE   → executive_agent → replan → SUGGEST_REPLAN
```

**Scheduler:** configurable cron entries (defaults 07:00 daily analysis, 09:00 opportunity scan, 12:00 task review, 18:00 email/opportunity update, 21:00 daily review) stored in DB, editable in Settings, timezone-aware. Scheduled runs emit `SCHEDULE_TRIGGERED` and flow through the same core pipeline as chat — one code path, one audit trail.

**Job queue:** interface `JobQueue` with two implementations — `InProcessQueue` (dev/test, no Redis needed) and `RedisQueue` (production, Celery/RQ). Chosen by env var.

---

## 13. API & frontend

- **API:** FastAPI, versioned (`/api/v1`), OpenAPI-generated client types for the frontend. Endpoints grouped: auth, chat, tasks, goals, memory, opportunities, applications, contacts, email, calendar, approvals, notifications, settings, health, analytics.
- **Async + realtime:** long operations return `202 + job_id`; progress via SSE stream (`/api/v1/stream`). Approvals appear in real time on the active device.
- **Frontend:** Next.js App Router, mobile-first Tailwind, dark UI. Routes mirror the nav: Dashboard, Chat, Tasks, Goals, Calendar, Opportunities, Applications, Email, CRM, Business, Social, Projects, Research, Memory, Analytics, Settings.
- Dashboard widgets show only data that exists; unavailable integrations render an explicit **"Not connected"** state with a connect action — never placeholder numbers.
- All API errors map to a `{ code, message, what_failed, what_happened, what_next }` contract so the UI can be honest.

---

## 14. Authentication & tenancy

- **Supabase Auth** (email magic link + Google OAuth) in production; a local dev auth shim (single-user, signed session token) in Phase 1 so the app runs before Supabase is configured.
- The API trusts `Authorization: Bearer <jwt>`; JWT verified against Supabase JWKS, `user_id` derived server-side — never taken from request body.
- Row-level ownership: every domain table has `user_id`; repositories require it. Multi-user ready from day one even though the product is personal.

---

## 15. Technology choices (with rationale)

| Layer | Choice | Why | Alternative considered |
|---|---|---|---|
| Frontend | Next.js + TS + Tailwind | requested; strong mobile SSR, Vercel deploy | Vite SPA (weaker SSR) |
| Backend | FastAPI + Python 3.13 | requested; async, typed, great AI ecosystem | Node/Nest (weaker AI libs) |
| ORM/migrations | SQLAlchemy 2 + Alembic | one schema for SQLite dev & Postgres prod | Prisma (Node-only) |
| DB (dev) | SQLite | zero-install given no Docker/Postgres locally | apt-install Postgres (heavier, service mgmt in proot) |
| DB (prod) | Supabase Postgres (+Auth, +Storage, +Realtime) | requested; one vendor for DB/auth/storage | plain RDS |
| Queue | `JobQueue` interface: in-proc → Redis/Celery | dev without Redis, prod reliability | APScheduler only (no durable retries) |
| Scheduler | DB-stored cron + worker | configurable from UI, survives restarts | system crontab |
| AI | Provider abstraction | no vendor lock-in; local fallback | single-vendor SDK |
| Automation | n8n via integration module (Phase 8) | requested; mature workflow ecosystem | hand-rolled rules |
| Auth | Supabase Auth | requested, OAuth + JWT | self-hosted Keycloak (ops cost) |

---

## 16. Honest capability map (as of this document)

| Area | State |
|---|---|
| Architecture & docs | **Designed** (this doc set) |
| Application code | **Not started** |
| Every integration (Gmail, Calendar, LinkedIn, Instagram, GitHub, browser, n8n) | **Not connected — interface designed only** |
| Every agent | **Specified in `agents.md`, none implemented** |
| AI providers | **Abstraction designed, no keys configured in environment** |

Nothing in this repository will claim a feature works until a test proves it.

---

## 17. Related documents

- `roadmap.md` — phases, acceptance criteria, gating rules, status
- `security.md` — threat model, permission levels, audit, prompt-injection defense
- `database.md` — schema, portability rules, migration policy
- `agents.md` — agent contracts, tool allowlists, delegation rules
