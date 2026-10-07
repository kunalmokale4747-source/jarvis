# JARVIS — Roadmap

**Status:** Phase 0 complete (environment analysis + architecture). No application code yet.
**Last updated:** 2026-10-07

## Gating rules

1. A phase is done only when its acceptance criteria pass automated tests **and** the app has been run and verified manually.
2. **Do not start phase N+1 while phase N is broken.**
3. No feature is marked working without a test that proves it.
4. Unavailable integrations are surfaced as `UNAVAILABLE` in UI and API — never simulated.
5. Every phase ends with: run tests → fix → run app → verify → update docs → commit → report JARVIS STATUS.

Commit style: `feat: …` / `fix: …` / `test: …` / `docs: …` (conventional commits). Never commit secrets.

---

## Phase 0 — Architecture ✅ (this stage)

**Deliverables**
- [x] Environment inspection (OS, Node, Python, Git, Docker, gh, storage, existing repo)
- [x] `docs/architecture.md`
- [x] `docs/roadmap.md`
- [x] `docs/security.md`
- [x] `docs/database.md`
- [x] `docs/agents.md`

**Acceptance:** a new developer can explain the system's components, data flow, permission model, and phasing from these docs alone.

---

## Phase 1 — Foundation (MVP skeleton)

**Goal:** a runnable, tested, honest skeleton: repo structure, backend, frontend, database, auth, basic dashboard.

**Deliverables**
- Monorepo scaffold exactly per `architecture.md` §3 (import-layer rules enforced by a test)
- FastAPI app: health endpoint, versioned `/api/v1`, error contract `{code,message,what_failed,what_happened,what_next}`
- SQLAlchemy + Alembic: initial migration for `users`, `user_profiles`, `sessions/audit` core tables (SQLite dev / Postgres prod switch via `DATABASE_URL`)
- Local auth shim (single-user signed session) + the interface Supabase Auth will plug into
- Next.js app: mobile-first shell, nav skeleton, Dashboard page rendering **real** API data only
- `.env.example`, `README.md` with setup steps, `scripts/dev.sh` to run api+web together
- Tests: API health/auth/profile round-trip, migration up/down, layer-import rule, frontend smoke (build passes)

**Explicitly NOT in Phase 1:** chat, agents, memory, tasks, integrations, fake widgets.

**Acceptance:** `scripts/test.sh` green; app boots; dashboard shows profile data entered by the user.

---

## Phase 2 — Brain

**Goal:** conversation works and JARVIS remembers.

- Chat endpoint with streaming; session history (rolling, not long-term memory)
- LLM provider abstraction with `openai | anthropic | gemini | local` + **provider-unavailable degradation** (tested by injecting a failing provider)
- User profile CRUD (editable from dashboard, stored in DB — nothing personal in source)
- Memory system: categories, curated write path, relevance retrieval, Memory UI page
- Goals + tasks CRUD with hierarchy and priorities/statuses
- Context assembly (profile + active goals + memories) feeding the LLM
- Tests: memory retrieval ranking, curated-write value test, provider fallback, goal/task API

---

## Phase 3 — Intelligence

- JARVIS CORE pipeline end-to-end (intent → plan → permission → tool → verify → memory → response)
- Tool registry + executor with schemas, timeouts, retry policies, `tool_execution` log
- Permission engine: levels 0/1/2, persisted approvals, notification of pending approval
- Executive Agent, Opportunity Agent, Research Agent
- Opportunity scoring (pure functions + fixtures) and the full opportunity report contract
- Decision engine (value score) with stored component breakdown
- Tests: permission enforcement (L1 cannot execute without approval), scoring fixtures, plan→verify happy path + failure path

---

## Phase 4 — Career

- Application tracker (statuses FOUND → OFFER/ACCEPTED), resume storage, cover-letter drafts
- Application preparation flow ending in `WAITING_APPROVAL` (submission always requires approval)
- Follow-up scheduling and deadline tracking
- Rejection-pattern analysis (only from real application data)
- Tests: state machine transitions, "no submission without approval" invariant

---

## Phase 5 — Productivity

- Email integration layer (read/categorize/summarize/draft; send = L1), marked `UNAVAILABLE` until OAuth configured
- Calendar integration (read/conflicts/reminders/briefs; create = L1)
- Daily planner (07:00) and nightly report (21:00) generated from real data
- Notifications channel (web push/email via configured provider)
- Tests: category rules, report generation from fixture data, schedule firing

---

## Phase 6 — Business

- Personal CRM (contacts, statuses, follow-up reminders)
- Business Partner Agent (decision framework PROBLEM→RESULT)
- Lead tracking and follow-up nudges
- Tests: CRM state transitions, follow-up due logic

---

## Phase 7 — Social

- LinkedIn + Instagram agents behind official APIs only (no scraping)
- Content calendar, drafts, performance analysis where API data exists
- Publishing = L1 always
- Tests: draft/publish permission boundary, no-op when API not connected

---

## Phase 8 — Autonomy

- Durable event outbox + workers; `EMAIL_RECEIVED`, `NEW_JOB_FOUND`, `TASK_OVERDUE` chains
- Scheduled agents with DB-configurable cron (07/09/12/18/21 defaults, editable)
- Proactive recommendations on the dashboard with rationale
- n8n integration interface
- Tests: outbox delivery guarantees (restart replay), schedule config, chain execution

---

## Phase 9 — Cloud

- Deploy: Vercel (web) + Railway/Render/Fly/VPS (api, workers, scheduler) + Supabase (DB/auth/storage)
- Redis-backed queue in production, health checks, structured logs, dashboards for SYSTEM STATUS
- Backups, secret rotation, rate limiting, security hardening pass vs. `security.md`
- Monitoring/alerting on failed jobs and failed agent runs
- Tests: production smoke test, health endpoint coverage, config validation (fail-fast on missing secrets)

---

## Phase 10 — Advanced

- Voice wake + voice commands (interface designed now, implemented here)
- Browser agent (tool-isolated, L1 for any state-changing action)
- Mobile-app-grade PWA, advanced memory (episodic + semantic), multi-agent collaboration
- Self-review of strategy recommendations quality

---

## Dependency map

```
P0 docs ─► P1 foundation ─► P2 brain ─► P3 intelligence ─┬─► P4 career
                                                         ├─► P5 productivity ─► P6 business ─► P7 social
                                                         └─► P8 autonomy ─► P9 cloud ─► P10 advanced
```

P4–P7 may interleave only after P3 passes; P8 requires P3+P5; P9 requires a working P8 scheduler on a real server.

---

## Current status board

| Phase | State | Evidence |
|---|---|---|
| 0 Architecture | **Complete** | docs/ present |
| 1 Foundation | Not started | — |
| 2–10 | Not started | — |

**Next action:** implement Phase 1 (project skeleton + backend + database + auth + dashboard), then test it.
