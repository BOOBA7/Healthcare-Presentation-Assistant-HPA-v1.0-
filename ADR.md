# ADR-0007 — Evidence-Gated, Human-Validated Architecture for HPA

## Status

**Accepted — updated 2026-08-09**

This ADR supersedes the earlier agent-centric description. HPA retains one
cognitive agent, but the LLM is no longer considered the workflow authority.
Superseded decisions are intentionally retained as learning records in
[`docs/architecture-history/`](docs/architecture-history/) rather than being
rewritten as though they never existed. See
[`docs/ARCHITECTURE_EVOLUTION.md`](docs/ARCHITECTURE_EVOLUTION.md) for the
cross-stage rationale and the project owner's learning reflection.

## Context

HPA prepares healthcare presentation material from documents supplied by a
professional. A language model can generate fluent but unsupported content, so
the product must prevent unsupported scientific production rather than relying
on prompt instructions alone.

The system must be locally usable, auditable per user and project, and able to
evolve toward stronger deployment infrastructure without changing the business
rules.

HPA is FDA-oriented by design: it applies human-in-the-loop control,
traceability, evidence provenance, auditable workflow states, and risk-aware
boundaries inspired by Good Machine Learning Practice. It is not, however, a
medical device, clinical decision support system, or evidence authority, and
this ADR does not claim FDA clearance, approval, or regulatory compliance.

## Decision

### Architectural principle — the LLM is not the workflow authority

The LLM is a bounded cognitive component, not the authority for business
transitions, evidence sufficiency, provenance, approvals or export. It may
propose an action; deterministic application services decide whether that
action is permitted and executable.

```text
System decides whether generation is allowed
→ LLM generates within bounded evidence and instructions
→ System validates the output
→ Human approves the deliverable
```

### 1. One cognitive agent, bounded by deterministic services

`HealthcarePresentationAgent` is the sole LLM-facing agent. It interprets
conversation and may select an allowed production tool. It does not own
business decisions.

LangGraph orchestrates the `agent → tool → agent` loop. HPA deliberately uses
a custom guarded tool node rather than a generic `ToolNode` / tool executor.
The node permits one tool action per turn, validates its availability, catches
safe workflow errors, and returns tool outcomes to the model as `ToolMessage`s.

### 2. State has three responsibilities

| State | Responsibility | Authority |
|---|---|---|
| `GraphState` | Agent messages, durable presentation-chat transcript, compact non-authoritative continuity memory, separate resource-chat transcript, collected context, Project library, resource overview and presentation reference | Agent orchestration |
| `PresentationState` | Workflow status, validation flags, slide progress | Business lifecycle |
| `ExecutionContext` | Last tool result, safe error code/message | Technical execution only |

The presentation aggregate is the durable business object. An execution error
must never be treated as a scientific or approval decision.

### 2a. Expected domain failures use a typed hierarchy

Expected business failures use a common, safe hierarchy:

```text
ValueError
└── DomainError
    ├── ValidationError
    ├── WorkflowError
    │   └── InvalidTransition
    ├── ConcurrentModificationError
    └── ProjectJobRunningError
```

`DomainError` preserves compatibility with existing `ValueError` handling while
adding a stable code, user-facing message and retryability metadata.
`InvalidTransition` is used by `WorkflowPolicy` when an action is not permitted
in the current lifecycle state. `ValidationError` is used for deterministic
domain validation such as invalid evidence provenance.

The API maps these typed domain failures to predictable client responses. This
allows Web and Streamlit interfaces to react to an error category or code
rather than parsing an arbitrary error string. The LLM receives safe tool
outcomes, never raw stack traces.

### 3. Business state machine is the source of truth

The durable statuses are:

```text
context_collection
→ awaiting_resource_upload
→ awaiting_resource_validation
→ blueprint_generation
→ awaiting_scope_clarification (only when the professional scope requires clarification)
→ awaiting_agenda_approval
→ awaiting_blueprint_approval
→ slide_generation
→ awaiting_slide_resolution (only when one AI slide lacks sufficient PDF evidence)
→ awaiting_slide_approval
→ awaiting_final_approval
→ ready_for_export
→ exported
```

`WorkflowPolicy` rejects invalid transitions. API routes, human-review use
cases, and LLM tools must obey the same transitions. Prompts describe the flow,
but code is the final authority.

### 4. Evidence is user-scoped and system-verified

PDFs first belong to the authenticated user's **Project resource library**.
Users may upload, inspect, summarise and discuss library PDFs independently from
presentation production. A user must explicitly attach library resources to a
presentation; only this selection can become production evidence. There is no
global document folder and no external retrieval by default.

The UI exposes this separation as three persistent workspaces: **Resources**
for the library and production source selection, **Resource Analysis** for the
overview and PDF-only discussion, and **Presentation Studio** for deterministic
workflow commands, review and export. Resource overview and PDF discussion
turns are never appended to the presentation-assistant transcript.

Blueprint and slide generation are explicit `202` API jobs initiated by a
human click. The server rechecks the current Project revision, workflow status,
selected validated evidence and professional-scope compatibility before the LLM
is invoked. The chat can explain these actions, but cannot trigger them.

```text
Project PDF library → optional source-only exploration
                    → explicit presentation attachment
                    → human validation before blueprint production
```

Each Project explicitly selects an evidence-context strategy before generation:
local BM25 retrieval (the default) or **Direct bounded PDF context** for a
controlled HCP comparison. Direct context uses a deterministic source-balanced
window over the same normalized SQLite chunks; it does not rank passages and
does not send a complete PDF. The strategy is recorded with generation metadata.
Changing it after blueprint or slide generation requires a new Project, keeping
the experiment auditable.

`ProductionEvidenceGate` checks for sufficient deterministic support from the
selected strategy before:

- answering an evidence-bound production-scoped question;
- generating a blueprint;
- generating or regenerating a slide.

The gate uses a safe default rather than a vocabulary of medical keywords:
only clearly non-factual social, profile and presentation-workflow coordination
turns may reach the LLM without PDF passages. A short, indirect or multilingual
factual question is therefore evidence-bound by default. If there is no selected
and approved PDF, or retrieval is insufficient, HPA returns a fixed request for
a suitable PDF or clarification instead of calling the LLM. Resource validation
is contextual: it is requested when the user starts blueprint production, not
when they merely upload or discuss a PDF. Neither mode changes resource
selection, human validation, citation provenance or export approval.

### 4a. Patient Case Mode is de-identification-by-guardrail, not compliance

A Project can opt into Patient Case Mode only after the user confirms that the
case is de-identified. User-entered case text — including prior user turns,
Project context and user-edited content — is screened before it is persisted or
reaches the configured LLM. A deterministic guard blocks obvious identifiers
such as email addresses, phone numbers, full dates, medical-record identifiers,
social-security identifiers and addresses. Uploaded PDFs are screened for
direct identifiers, but publication dates are not treated as patient identifiers
by themselves, so normal guidelines and articles remain usable. Detected values
are never stored in the error or audit message.

The detector is intentionally conservative and cannot reliably detect every
identifier (for example names in arbitrary prose). Therefore this decision is
not a HIPAA compliance claim, certification, formal de-identification method,
or substitute for the user's institutional policy. It provides a clear product
boundary: patient-identifying content must not be entered or uploaded in this
mode.

Every slide reference is validated by `EvidenceProvenanceValidator`:

1. `resource_id` must exist in the presentation;
2. the cited page must exist in that resource;
3. the evidence excerpt must occur on that page.

Comparison normalisation is Unicode-safe: it removes combining marks for
accent-tolerant comparison without deleting Arabic (or another non-Latin)
letters. An Arabic excerpt therefore cannot be accepted merely because both
strings were reduced to empty ASCII text.

The PowerPoint displays the user-validated resources and associated evidence.
The separate resource-overview and PDF-discussion features use bounded passages
from the Project library only; they do not alter the production selection.
Their citations are requested from the LLM for exploration, but do not yet
receive the slide-level system check of resource identifier, page and excerpt.
They must not be presented as provenance-verified production evidence.

The interfaces present user-facing citations with the resource title and page,
while preserving the raw model message and `resource_id` in SQLite. An
expandable technical-citation detail keeps the full identifier accessible for
audit without exposing UUIDs as the primary clinical reading experience.

Title-slide delivery details — presenter name and role, organisation, event,
venue and date — are optional human-controlled metadata. They may be entered
in either interface or explicitly recorded from the chat, but the LLM must
never infer them. They do not participate in evidence gating or block workflow
progress. Because the title slide is part of the exported deliverable, changing
these details after final approval reopens final approval only.

### 5. Prompt, harness, and loop have distinct roles

| Layer | Responsibility | Not responsible for |
|---|---|---|
| System prompt | identity, trust boundary, role/language adaptation | enforcing permissions |
| Healthcare harness | evidence, uncertainty, presentation safety | verifying evidence |
| Loop policy | concise turn behavior and tool discipline | state transitions |
| Prompt builders | blueprint/slide task instructions and retrieved excerpts | business rules |

Trusted state is injected separately from untrusted user messages and PDF
excerpts. The code enforces permissions, evidence sufficiency, provenance, and
approvals.

### 6. Human approval is mandatory

The user must explicitly validate selected production resources, Agenda,
blueprint items, complete blueprint, slides, and final presentation. The model
cannot simulate these approvals. Rejections and reviewer comments are persisted
and can drive regeneration. Users may edit blueprint items and slides; HPA
retains the original AI snapshot and labels content as AI-generated,
user-edited, or user-authored.

A `user_authored` blueprint item becomes a slide through a deterministic copy
of the user-provided title, objective and key message; it never invokes the
LLM. Conversely, an AI-owned item without sufficient retrieved evidence moves
only that Project to `awaiting_slide_resolution`. Existing slides are retained,
and the user can revise the item, add a relevant PDF, or convert it to
user-authored content before resuming the normal approval flow.

### 7. Persistence and auditability

For local use, `UserSessionRepository` persists user accounts, profile,
Projects, durable conversation transcripts, resource-library metadata,
presentation state, templates, jobs and immutable-style project events in
SQLite. Large PDF material is deliberately outside `state_json`: metadata is
stored in `project_resources`, extracted pages in `project_resource_pages`,
and retrieval chunks in `project_resource_chunks`. This avoids copying all PDF
text on every chat turn and keeps API responses metadata-only.

Each Project has an optimistic `revision`. State and audit event are written in
the same SQLite transaction and a write uses `WHERE revision = expected`.
When a human action has already changed the Project, a stale write fails as
`PROJECT_VERSION_CONFLICT` rather than overwriting the latest state. The
`project_jobs` table additionally enforces one queued or running state-writing
job per Project. A second request is rejected as `PROJECT_JOB_ALREADY_RUNNING`
before it can make a duplicate model call.

The presentation-chat and independent Resource Chat transcripts remain durable.
Each submitted user turn is committed before any provider call, so quota,
network and model failures cannot make that message disappear. The audit trail
records `USER_MESSAGE_RECEIVED` or `RESOURCE_DISCUSSION_MESSAGE_RECEIVED`, then
records a safe failure event when needed (`AGENT_TURN_FAILED` or
`RESOURCE_DISCUSSION_FAILED`). Failure payloads contain only a category,
retryability and configured provider/model identity; raw provider error text
and user source content are not copied into the audit event. Before invoking
the model, the application keeps only the 16 most recent presentation-chat
model messages and compacts older turns into a bounded, non-authoritative memory
summary. The trusted state summary and retrieved PDF excerpts remain
authoritative for workflow decisions and scientific claims.

Long-running model calls are recorded as durable local `project_jobs` entries.
The API returns `202`, then clients poll a job for stage/progress/result. The
process records content-free observability counters such as LLM duration,
prompt size, retrieval selections, generation failures and evidence refusals.
This is deliberately a local executor, not a distributed queue.

### 7a. Evaluation is system-level and provider-independent

HPA evaluates its own contract with deterministic, provider-free tests and a
small clinician-reviewed product evaluation set. The target is not merely a
generic medical-chat score. Evaluation must exercise the complete path:

```text
Project PDF → retrieval → evidence gate → workflow → provenance → human review
```

Each product-evaluation case records expected allow/refuse behavior, workflow
transition, citation/provenance outcome and, when a live model is used, the
provider and model identifier. The initial evaluation set can be built from
small controlled PDFs and 30–50 realistic scenarios; it does not require an
external data source or an OpenAI account.

External benchmarks can inform base-model choice, but they do not certify HPA's
retrieval, workflow or provenance behavior. The detailed strategy is maintained
in `docs/EVALUATION.md`.

The audit API is:

```text
GET /projects/{user_id}/{project_id}/audit-events
```

SQLite is a local deployment choice, not a multi-instance production
architecture.

### 8. Interfaces, API composition and authentication

FastAPI serves the local JavaScript interface at `/app`; Streamlit and CLI are
additional local interfaces. API Project access requires a bearer token and is
owner-scoped. The current password reset route is intentionally local-only and
is not acceptable for public deployment.

The application repository is the durable source of Project state. A legacy
`InMemorySaver` adapter remains available for experimentation, but the durable
Project workflow does not rely on it.

FastAPI composition is separated by bounded API domain. `main.py` owns
application creation, shared dependencies and workflow compatibility routes;
authentication, Project/template, versioned platform and asynchronous-job
routes are provided by modules in `interfaces/api/routers/`. This keeps a
stable public surface while allowing the remaining resource/review routes to
migrate without breaking either local interface.

## Consequences

### Positive

- The model cannot advance a prohibited workflow stage.
- Unsupported scientific generation is blocked before a model request.
- Citations are verifiable against user-provided PDF pages.
- The project has reproducible generation metadata and an audit trail.
- The architecture keeps user responsibility and provenance within scope.

### Trade-offs

- Users must select and validate sources before scientific production.
- BM25 can reject a concept that is present under different wording or language.
- More gates mean more explicit user interactions and less apparent autonomy.
- SQLite and local files must be replaced for concurrent production deployment.
- The local job executor provides persistence and progress, not worker retries
  or horizontal scaling.
- BM25 reads normalized persisted chunks directly, but lexical terms and scores
  are recomputed per request; extremely large libraries may need an indexed
  lexical implementation.
- Conversation history is durable and model context is bounded. Its compact
  memory is deliberately non-authoritative and may lose fine-grained wording
  from old turns.
- One state-writing job is serialized per Project. It remains a local executor
  without distributed workers or automatic job retry.
- Generation records include version metadata, but provider-accurate model
  capture must be completed before treating them as fully reproducible records.
- The deterministic evidence gate uses explicit text patterns to distinguish
  non-factual coordination from evidence-bound content. It is intentionally
  conservative, but this classifier needs regression coverage for phrasing
  that combines presentation commands with scientific requests.
- Resource Overview and Resource Chat are source-bounded exploratory features;
  unlike AI-generated slides, their displayed citations are not yet validated
  programmatically against a resource page and excerpt.

## Explicit non-decisions

The following are intentionally not claimed as implemented:

- OCR for scanned PDFs;
- external PubMed, guideline, or web retrieval;
- semantic/vector retrieval, embeddings, or a global knowledge base;
- distributed job queue, worker retries, or distributed execution;
- a clinical benchmark score, clinical validation, or an external benchmark
  certification of HPA;
- PostgreSQL migration and object storage;
- enterprise SSO, MFA, secure public password recovery, or role-based access;
- clinical validation, regulatory certification, FDA clearance/approval, or
  hospital compliance.

These additions must preserve the existing evidence, provenance, workflow, and
human-approval boundaries.
