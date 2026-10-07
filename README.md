# JARVIS

**Personal AI operating system.** Not a chatbot: a long-running agent platform that
understands your goals, remembers context, identifies useful actions, prepares them,
asks permission when required, executes approved actions, verifies results, and tells
you what to do next.

> **Current status: Phase 1 (Foundation) — backend, database, auth, dashboard.**
> Chat, agents, memory, tasks, goals, and every external integration are **not built
> yet** and are honestly labeled as such in the UI. See [docs/roadmap.md](docs/roadmap.md).

## Architecture at a glance

```
ANDROID (dev · chat · notifications)        no 24/7 requirement
        │
     INTERNET
        │
   CLOUD JARVIS (24/7 — Phase 9)
   ├── Frontend  Next.js + React + TS + Tailwind
   ├── API       FastAPI (Python)
   ├── Core      orchestration · memory · permissions · tools · events · scheduler
   ├── Agents    executive · opportunity · career · research · email · … 
   ├── DB        PostgreSQL (Supabase) / SQLite in dev — same schema
   └── Workers   Redis queue (prod) / in-process (dev)
```

Full design: [docs/architecture.md](docs/architecture.md) ·
Security: [docs/security.md](docs/security.md) ·
Database: [docs/database.md](docs/database.md) ·
Agents: [docs/agents.md](docs/agents.md)

## Prerequisites

- Python 3.11+ (dev box: 3.13) and `python3-venv` (`apt install python3.13-venv`)
- Node.js 18.18+ (dev box: 22)
- No Docker/PostgreSQL/Redis required for local development (SQLite + in-process services)

## Quickstart

```bash
git clone <repo> && cd jarvis
scripts/setup.sh      # venv, python deps, .env, migrations, frontend deps
scripts/dev.sh        # API on :8000 + web on :3000
```

Open http://127.0.0.1:3000 and sign in with any email
(`AUTH_MODE=dev` — local dev shim only; Supabase Auth ships in Phase 9).

## Tests

```bash
scripts/test.sh            # backend pytest + frontend production build
SKIP_WEB=1 scripts/test.sh # backend only (fast)
```

What the Phase 1 suite proves:

| Test | Asserts |
|---|---|
| `test_health` | API + DB report real status; integrations report `not_configured` (never fake "connected") |
| `test_auth_profile` | login/session/logout, failure-report contract, profile round-trip, cross-user isolation, audit rows written |
| `test_migrations` | Alembic upgrade creates exactly the ORM schema; downgrade removes it (no drift) |
| `test_layer_rules` | layer dependency rules enforced (`core` cannot import `apps`/`agents`/`integrations`); no `eval`/`exec` anywhere |

## Project structure

See [docs/architecture.md §3](docs/architecture.md) for the full monorepo layout and
the rationale for each deviation.

```
apps/web      Next.js UI (mobile-first)
apps/api      FastAPI HTTP layer
core/         domain layer: config, db, auth, audit  (Phase 2+: memory, permissions, tools, llm…)
agents/       agent specs (Phase 3+)
integrations/ external services, status registry (all not connected today)
database/     Alembic migrations
prompts/      prompt templates (Phase 2+)
tests/        pytest suite
scripts/      setup · dev · test
docs/         architecture · roadmap · security · database · agents
```

## Environment

Copy `.env.example` → `.env` (done by `scripts/setup.sh`). Never commit `.env`.
Key switches:

| Var | Values | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./data/jarvis.db` (dev) · Postgres URL (prod) | one schema, both engines |
| `AUTH_MODE` | `dev` (works now) · `supabase` (fails fast — not implemented) | |
| `LLM_PROVIDER` | empty (AI offline) · openai/anthropic/gemini/local | Phase 2 |

## Git conventions

Conventional commits (`feat:`, `fix:`, `test:`, `docs:`). Never commit secrets.
