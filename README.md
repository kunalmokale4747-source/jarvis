# JARVIS

**Personal AI operating system.** Not a chatbot: a long-running agent platform that
understands your goals, remembers context, identifies useful actions, prepares them,
asks permission when required, executes approved actions, verifies results, and tells
you what to do next.

> **Current status: Phase 9 — real AI integration, optional Groq hosted free-tier configuration, Android/Termux APIs, and all earlier phases.**
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

## Phase 5: Termux and Android integration

### Capabilities checked on this device

Termux:API commands are checked at runtime. On this development device,
`termux-notification`, `termux-tts-speak`, `termux-battery-status`, and
`termux-toast` were not installed. The JARVIS API reports that honestly via:

```bash
GET /api/v1/android/capabilities
```

Only `termux-wake-lock` and `termux-open-url` were available. Browser
notifications and notification history continue to work when native commands
are unavailable.

### Optional Termux:API setup

```bash
pkg install termux-api
```

On Android, also install the matching **Termux:API** companion app from
F-Droid if required by your Termux installation. Grant any Android
permissions it requests. Then verify:

```bash
command -v termux-notification
command -v termux-tts-speak
command -v termux-battery-status
```

### Safety model

- Only allowlisted Termux commands can run.
- Commands are executed with argument arrays and `shell=False`.
- Parameters are validated for length, language, URL scheme, and unsafe characters.
- Destructive/consequential actions such as opening a URL require `confirm=true`.
- No arbitrary AI-generated shell command is ever executed.
- Delivery attempts are stored in notification history with success/failure status.

### Scheduler behavior

- One scheduler thread starts with the API.
- On startup it safely processes overdue reminders and due briefings once.
- Repeated runs use `last_fired_at`, `last_*_run_on`, and run records to prevent duplicates.
- Android may still kill Termux or the backend process. Guaranteed background delivery requires a native Android app or additional device configuration and is not claimed here.

### Troubleshooting

- If native notifications fail, use browser notifications and check `/api/v1/android/capabilities`.
- If speech is unavailable in the browser, use the text input on `/voice`.
- If microphone permission is denied, grant it in browser settings or continue with text input.
- Check API logs without secrets; JARVIS does not log API keys.

## Phase 6: reliability and diagnostics

### Diagnostics

```bash
curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/v1/diagnostics
```

The diagnostics response reports database connectivity, scheduler thread state,
configured AI provider mode, counts, Android integration capabilities, and the
missed-job policies. It never exposes API keys, secrets, memories, or user
content beyond aggregate counts.

### Operational policies

- One-time reminders older than the catch-up window are marked as failed instead
  of replaying every overdue item after downtime.
- Recurring reminders skip missed intermediate occurrences and schedule only the
  next future occurrence.
- Briefings are generated only for the current configured day/time and only once
  per day.
- The scheduler thread is started with the API process and stopped during API
  shutdown. If multiple API workers are configured, each worker gets its own
  in-process scheduler; coordinate workers or use a single scheduler owner.
- Android may stop Termux or the backend. Back up data and monitor `/health`
  or `/api/v1/diagnostics`; guaranteed background delivery is not claimed.


## Phase 9: real AI and Android Integration

### Recommended hosted provider

Groq (`openai/gpt-oss-20b`) is recommended when a free hosted tier is desired.
It uses an OpenAI-compatible endpoint, supports tool/function calling for JARVIS tool
definitions, and has publicly documented per-model rate limits. Quotas and model
support change; verify current docs before production use. Groq free tiers are
per-model allowances, not pooled tokens. Set pricing/spend limits before high-volume use.

### Configure a real provider

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=your-key-here
LLM_MODEL=openai/gpt-oss-20b
```

Local/compatible providers remain supported:

```bash
LLM_PROVIDER=local
LLM_BASE_URL=http://localhost:11434/v1
```

Stub/offline mode remains the default with no key:

```bash
LLM_PROVIDER=
```

Only text is sent to the selected hosted model. Voice audio is not uploaded.
JARVIS warns and continues in offline mode if the provider is rate-limited or unavailable.

### Termux and native Android APIs

Only commands present in PATH are reported as available through:

```bash
GET /api/v1/android/capabilities
```

Native notification, speech, battery status, toast, and wake lock endpoints live under
`/api/v1/android/*`. `POST /api/v1/android/open-url` still requires `confirm=true`.
Native notifications and wake locks are recorded honestly and may fail due to missing
Termux:API components.

### Termux:API setup

```bash
pkg install termux-api
```

Install the matching Termux:API companion app and grant requested permissions.
Verify:

```bash
command -v termux-notification
command -v termux-tts-speak
command -v termux-battery-status
```

Do not run a persistent wake lock automatically; it increases battery use and Android
can still terminate the process.

### Privacy and security notes

- API keys stay in backend environment configuration.
- The diagnostics response and provider status do not expose secrets.
- Android output language and speech text are validated for length and allowlisted languages.
- Native notification and task actions remain individually audited and user-scoped.
- Tool calls proposed by models use untrusted output validation and confirmation rules.


## Phase 11: Android and Termux deployment notes

### Device discovery

Do not assume a public IP address. The API may be reachable from the phone browser at:

```bash
hostname               # device hostname
hostname -I            # address used when reachable from another device
```

On the same phone, use:

```bash
http://127.0.0.1:3000
http://127.0.0.1:8000/api/v1/health
```

Bind the backend to all interfaces only when access from another device is required:

```bash
cd /root/jarvis
API_HOST=0.0.0.0 API_PORT=8000 ./scripts/dev.sh
```

### Provider verification without exposing secrets

1. Configure `.env` with placeholder values only at rest.
2. Verify status:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/auth/login   -H 'Content-Type: application/json'   -d '{"email":"you@example.com"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')

curl -H "Authorization: Bearer $TOKEN"   "http://127.0.0.1:8000/api/v1/diagnostics/provider?live=true"
```

The response reports `provider` and `live_status`, but never the key.

### End-to-end reality checks

```bash
# natural-language reminder
curl -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:8000/api/v1/chat \
  -d '{"message":"Remind me to test JARVIS tomorrow at 7 PM"}'

# independent persistence check
curl -H "Authorization: Bearer $TOKEN"   http://127.0.0.1:8000/api/v1/reminders

# ambiguous date should ask instead of inventing a time
curl -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -X POST http://127.0.0.1:8000/api/v1/chat \
  -d '{"message":"Remind me to test JARVIS tomorrow"}'
```

### Android capability reporting

```bash
curl -H "Authorization: Bearer $TOKEN"   http://127.0.0.1:8000/api/v1/android/capabilities
```

JARVIS reports each Termux command as available or missing. It does not simulate
notification or TTS delivery. Native wake-lock commands, if present, must
still be requested explicitly and are not activated during application startup.
