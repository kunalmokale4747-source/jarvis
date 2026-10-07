# JARVIS — Agents

**Status:** Design (Phase 0). All agents specified here; **none implemented yet.** Each entry lists the phase that implements it.
**Last updated:** 2026-10-07

## 1. What an agent is

An agent is **not** a free-running bot. It is a bounded, declarative unit:

```python
AgentSpec(
    name="opportunity",
    mission="Find and score real opportunities that match my profile",
    system_prompt="prompts/opportunity/v1.md",
    tool_allowlist=["web.search", "opportunity.search", "opportunity.score",
                    "memory.search", "task.create", "profile.read"],
    output_schema=OpportunityReport,
    model_tier="strong",          # cheap | standard | strong (per-provider mapping)
    max_steps=12,                 # loop cap
    permission_overrides={},      # may only RAISE a tool's level, never lower
    phase=3,                      # roadmap phase that implements it
)
```

Rules that apply to every agent:

1. **Tools only.** An agent acts exclusively through registered tools → executor → permission gate. No shell, no code execution, no direct DB writes outside repositories.
2. **Allowlist enforced by the executor**, not by the prompt. Prompt says "should"; executor says "cannot".
3. **Contracts.** Every agent declares an output schema; malformed output → one retry → reported failure.
4. **Budget.** `max_steps` + cost ceiling per run; exceeding = `FAILED` with reason, never a runaway loop.
5. **Raise-only permissions.** An agent may demand *more* approval for a tool, never less.
6. **Honesty.** Agents must not generate facts they don't have. Opportunity Agent may only report real search results; Career Agent may only restate profile facts; Research Agent must cite sources + confidence. Unavailable integration → `UNAVAILABLE` propagated to the user.
7. **Anti-busywork.** Every agent recommendation passes the value gate: *"Will this meaningfully improve the user's goals?"* Low-value output is dropped with a one-line reason.

---

## 2. Orchestration & delegation

**JARVIS CORE** (`core/orchestration/`) is not an agent. It is the deterministic pipeline (intent → context → memory → plan → agent → permission → tool → verify → memory → response → audit). It decides *which* agent runs; agents decide *how* to fulfill their contract.

**Routing:** intent classification picks a primary agent; the plan may chain agents sequentially (e.g. Opportunity → Career → approval).

**Conflict rules:**
- Only the Executive Agent may propose global reprioritization; other agents may only *request* task changes (`task.update` with reason) which Executive reviews or the user approves.
- Only the Planning Agent writes tomorrow's plan/nightly report skeleton; others contribute sections.
- Overlapping writes to the same memory are resolved by `superseded_by` chains in the memory module, not by agent priority.
- If two agents disagree, CORE surfaces both positions with rationale to the user — it does not silently pick one.

---

## 3. Agent registry

| Agent | Phase | Status | Primary tools (level) |
|---|---|---|---|
| executive | 3 | specified | `goal.*`(0), `task.*`(0), `memory.search`(0), `web.search`(0) |
| opportunity | 3 | specified | `web.search`(0), `opportunity.search`(0), `opportunity.score`(0), `task.create`(0) |
| research | 3 | specified | `web.search`(0), `research.run`(0), `memory.search`(0) |
| career | 4 | specified | `application.*`(0/1), `resume.*`(0), `cover_letter.*`(0), `opportunity.search`(0) |
| email | 5 | specified, integration not connected | `email.read`(0), `email.summarize`(0), `email.draft`(0), `email.send`(**1**) |
| calendar | 5 | specified, integration not connected | `calendar.read`(0), `calendar.suggest`(0), `calendar.create_event`(**1**) |
| planning | 5 | specified | `task.*`(0), `goal.*`(0), `calendar.read`(0), `email.read`(0), `notification.*`(0) |
| business | 6 | specified | `memory.search`(0), `crm.*`(0), `research.run`(0) |
| crm (contacts) | 6 | specified | `contact.*`(0), `task.create`(0), `email.draft`(0), `email.send`(**1**) |
| social (linkedin/instagram) | 7 | specified, integration not connected | `content.*`(0), `social.analytics`(0), `social.post.publish`(**1**) |
| learning | 8 | specified | `memory.search`(0), `task.create`(0), `research.run`(0) |

---

## 4. Agent specifications

### 4.1 Executive Agent
**Mission:** understand goals, prioritize, spot blockers, decide what deserves attention.
**Thinks in:** `GOAL → PROJECT → TASK → ACTION → RESULT`.
**Inputs:** goal/task/project state, deadlines, past performance, pending approvals, opportunity pipeline.
**Responsibilities:** daily priority setting; reprioritization suggestions with reasons; blocker detection (blocked tasks, stalled objectives, orphan tasks); delegation (create tasks assigned to other agents); progress review; strategy challenges ("this objective has had zero movement for 9 days").
**Outputs:** `ExecutiveBrief { top_priorities[], blockers[], reprioritization[], suggestions[] }`.
**Guardrail:** may only *propose* reprioritization (applied order is logged with reason); may not approve its own L1 actions.

### 4.2 Opportunity Agent
**Mission:** continuously find real, relevant ways to earn/advance — the highest-value agent in the system.
**Sources:** configured job/freelance APIs, scholarship/competition feeds, public boards, GitHub/org listings — **only sources actually connected**; otherwise reports `UNAVAILABLE` per source.
**Per opportunity computes:** skill match, experience match, income potential, success probability, time required, learning required, competition, urgency, application difficulty → **score /100** with breakdown.
**Report contract:** Company · Role · Income · Location · Remote · Deadline · Match Score · Why it fits · Skills I have · Skills missing · Estimated success · Time required · Recommendation (`APPLY | CONSIDER | SKIP`) · Next action.
**Outputs:** `Opportunity` rows + scores + notifications when score > threshold (default 80).
**Guardrails:** never fabricates listings; every opportunity has `source` + `url`; duplicates deduped; dead links → `EXPIRED`.

### 4.3 Research Agent
**Mission:** multi-source research with verification.
**Pipeline:** search → read → compare → dedupe → detect outdated/conflicting info → cite sources → assign confidence.
**Outputs:** `ResearchReport { question, findings[], sources[{url, title, date}], conflicts[], confidence, open_questions[] }`.
**Guardrails:** uncertain information is labeled uncertain, never stated as fact; conflicting sources are shown, not silently merged.

### 4.4 Career Agent
**Mission:** turn opportunities into applications, and track them.
**Capabilities:** compare opportunity requirements vs profile; gap analysis; resume versioning (from profile data only); cover-letter/proposal drafts; application state machine (`FOUND→…→ACCEPTED`); deadline + follow-up tracking; rejection-pattern analysis (from real data only); skill-improvement recommendations to the Learning Agent.
**Key flow:** prepare application → `WAITING_APPROVAL` → user approves → submit (L1) → track.
**Guardrails:** **never fabricates** experience/education/certs/skills/achievements — generation is restricted to profile facts; submission always requires approval unless per-workflow auto-submit was explicitly enabled.

### 4.5 Email Agent (Phase 5 — integration required)
**Capabilities:** read → categorize (`URGENT, ACTION_REQUIRED, JOB, CLIENT, BUSINESS, PERSONAL, PROMOTIONAL, NEWSLETTER, LOW_PRIORITY`) → summarize → detect urgency/opportunities/interview invites/client requests → draft replies → schedule follow-ups → track conversations.
**Tools:** read/summarize/draft = L0; **send = L1 (approval by default)**.
**Event chain:** `EMAIL_RECEIVED → classify → important? → CREATE_TASK → NOTIFY_USER`.

### 4.6 Calendar Agent (Phase 5 — integration required)
**Capabilities:** read events, detect conflicts, create reminders, prepare meeting briefs, suggest preparation tasks, update daily schedule.
**Tools:** read/suggest = L0; **create/modify events = L1** (important events require approval by default).

### 4.7 LinkedIn Agent (Phase 7 — official API only)
**Capabilities:** topic research, opportunity discovery, draft posts, improve posts, generate hooks, networking target suggestions, performance analysis (where API provides data), content calendar.
**Guardrail:** **publish = L1**; no scraping; no fake engagement tactics (anti-busywork applies).

### 4.8 Instagram Agent (Phase 7 — official API only)
**Capabilities:** content ideas, captions, content calendar, hashtag suggestions, performance analysis, lead identification, draft posts.
**Guardrail:** **publish = L1**; official APIs and approved integrations only.

### 4.9 Business Partner Agent (Phase 6)
**Mission:** answer: what to build / stop / sell, who to target, which customers are promising, what to charge, who competitors are, what to improve, what to automate.
**Decision framework:** `PROBLEM → CUSTOMER → MARKET → COMPETITION → OFFER → PRICE → ACQUISITION → VALIDATION → EXECUTION → RESULT`.
**Inputs:** projects, CRM data, opportunities, memory (decisions/lessons).
**Outputs:** `BusinessAnalysis { problem, evidence[], recommendation, risks[], validation_step, metric }` — every recommendation must name its evidence.

### 4.10 CRM capabilities (Phase 6)
Contact statuses `LEAD→CLOSED`, interaction history, next-action tracking, follow-up reminders (scheduled → `CREATE_TASK`/`NOTIFY_USER`).

### 4.11 Learning Agent (Phase 8)
`CURRENT SKILLS → TARGET → SKILL GAP → LEARNING PLAN → PROJECT → PORTFOLIO PROOF`.
Prefers project-based learning; every learning item must link to a skill gap derived from real opportunities/applications, and produce portfolio evidence. May only create tasks/drafts (L0).

### 4.12 Planning Agent (Phase 5)
Generates the **morning brief** (07:00) and **nightly report** (21:00) strictly from real data:
- Morning: objective, top 3 priorities, career/business/study/money/personal, deadlines, meetings, important emails, opportunities, estimated workload.
- Nightly: completed, missed, opportunities, applications, emails, business, content, problems, what to improve, tomorrow's top 3.
**Tone contract:** honest — explicitly says if time was wasted, if progress was made, if strategy looks wrong. Numbers only from actual records; empty sections say "nothing recorded", not invented content.

---

## 5. Shared cross-agent services

| Service | Provided by | Used by |
|---|---|---|
| Memory read/write (curated) | `core/memory` | all agents |
| Task/goal creation | `core/db` repositories | all agents |
| Scoring (decision + opportunity) | `core/scoring` | executive, opportunity, career |
| Approval workflow | `core/permissions` | all agents |
| Notification dispatch | `core/notifications` | all agents |
| Scheduling | `core/scheduler` | planning, opportunity, executive |
| LLM access | `core/llm` | all agents |

Agents never implement these themselves — they call the interfaces. This keeps behavior consistent and testable without an LLM in the loop (agent tests exercise the spec + tools with a stub model).

---

## 6. Testing strategy for agents

- **Spec tests:** every `AgentSpec` validates (schema exists, allowlist tools exist, permissions raise-only, phase number valid).
- **Contract tests:** with a **stub LLM** returning fixtures, an agent run produces schema-valid output and touches only allowlisted tools.
- **Permission tests:** attempts to invoke a non-allowlisted or L1 tool without approval → `BLOCKED`, audit row written.
- **Honesty tests:** with an integration marked `NOT_CONFIGURED`, agent output contains `UNAVAILABLE` and no invented data.
- Real-provider smoke tests are opt-in (require keys) and never part of the default suite.
