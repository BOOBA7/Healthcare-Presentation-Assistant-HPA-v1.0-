# Healthcare Presentation Assistant (HPA)

**Project documentation owner and maintainer: Anis Boubala.**

HPA is a local, evidence-gated assistant that helps healthcare professionals
prepare scientific PowerPoint presentations from **PDF resources they upload**.
It accelerates drafting, review and export; it does not replace scientific,
clinical, legal or institutional review.

> **Safety and regulatory position.** HPA is FDA-oriented in its engineering
> approach: human review, traceability, evidence provenance, explicit workflow
> states and risk-aware constraints. It is **not** FDA-cleared, FDA-approved,
> certified medical software, a diagnostic system, a prescribing system or a
> clinical decision-support authority. The healthcare professional remains
> responsible for every use of the output.

> ## Safety-by-design: the LLM is not the workflow authority
>
> HPA does not rely on prompt instructions alone. The conversational LLM can
> interpret a request and explain the next action. A bounded LLM use case can
> generate content only after an explicit human command has passed the server
> checks. Neither can approve resources, advance the workflow, validate
> evidence or authorize export.
>
> Deterministic application controls decide whether the LLM may be called:
>
> 1. `WorkflowPolicy` validates the current lifecycle transition.
> 2. `ProductionEvidenceGate` requires selected, human-approved PDF evidence
>    and sufficient deterministic evidence-context support for every
>    evidence-bound chat turn or generation.
> 3. The guarded LangGraph node permits only chat-safe actions from the trusted
>    Project state. Production commands are explicit server-side use cases.
> 4. `EvidenceProvenanceValidator` verifies AI-generated slide citations, and
>    `ResponseCitationValidator` verifies Resource Overview and Resource Chat
>    citations against the uploaded PDF before display.
>
> If a required condition is missing, HPA asks the user for the missing action
> or source instead of generating unsupported scientific content.
>
> ```text
> System decides whether generation is allowed
> → LLM generates within bounded evidence and instructions
> → System validates the output
> → Human approves the deliverable
> ```

## What it does

- Creates separate, authenticated local user accounts and Projects.
- Stores a professional profile (role and preferred language: English, French
  or Arabic) to adapt the assistant's communication style.
- Lets users upload readable PDFs (maximum 20 MB) to a **Project resource
  library**, even before a presentation exists.
- Provides a source-only resource overview and a dedicated PDF discussion mode
  to explore the uploaded material without changing a presentation.
- Separates three workspaces in `/app` and Streamlit: **Resources** (PDF
  library and production selection), **Resource Analysis** (overview and
  PDF-only discussion), and **Presentation Studio** (deterministic workflow,
  review and export). Resource and presentation-chat histories remain
  independent.
- Lets the user explicitly select library resources for a presentation. Only
  this selection is used as production evidence.
- Generates an editable blueprint, an Agenda, slides and a themed PowerPoint
  after the required human review steps.
- Lets the user add optional title-slide delivery details (presenter, role,
  organisation, event, venue and date) from either interface. These details
  are human-supplied, never inferred by the model.
- Supports direct user editing of blueprint items and slides, while preserving
  an AI-origin snapshot and labelling content as AI-generated, user-edited or
  user-authored.
- Creates a **user-authored** slide deterministically from a blocked blueprint
  item, without calling the LLM. If an AI slide lacks sufficient PDF support,
  the workflow pauses on that individual slide and offers a recoverable choice:
  revise the blueprint, add a PDF, or write it directly.
- Validates evidence provenance for AI-generated slides, Resource Overview and
  Resource Chat, then exports a final *Resources and validation* slide.
- Persists Projects, conversation transcripts, resource metadata, PDF pages,
  retrieval chunks, templates, workflow state and audit events in local SQLite.
- Offers a Project-level evidence-context choice: local BM25 retrieval
  (default) or **Direct bounded PDF context** (experimental comparison mode).
  This choice never disables source validation, evidence gating, provenance or
  human approval. Both modes now apply the same deterministic evidence-
  sufficiency criterion after selecting passages: one selected PDF passage
  must itself meet the required lexical support threshold. The mode changes
  passage selection, never the evidence rule.
- Offers a Patient Case Mode for **de-identified information only**. It blocks
  obvious direct identifiers before user-entered patient-case content is
  persisted or sent to the configured LLM. Dates in scientific PDFs are not
  treated as identifiers by themselves. It is a guardrail, not HIPAA
  certification or a guarantee of de-identification.
- Runs model-backed operations from `/app` and Streamlit — including chat,
  Resource Overview, PDF discussion, generation and regeneration — as durable
  local jobs with Project locking, polling progress and lightweight operational
  counters.
- Provides a local, navigable **pre-export presentation preview** in both
  interfaces once slides exist. It renders the same title details, agenda,
  slide bullets, provenance and final resources/validation content used for the
  export, without calling the LLM. An uploaded custom `.pptx` is applied during
  export; its native PowerPoint master styling is not rendered in this local
  browser/Streamlit preview.

## Resource library and evidence model

There is no shared document folder and no external evidence source. A resource
belongs to the authenticated user's Project.

```text
Upload PDF → Project library → optional overview / PDF discussion
                              ↓
                    explicitly attach to presentation
                              ↓
              human validation before blueprint production
```

Two modes are intentionally separate:

| Mode | Purpose | Evidence input |
|---|---|---|
| Resource exploration | Summarise or discuss the user’s PDFs before creating slides | Bounded passages from the Project library only |
| Production | Generate a blueprint or slides | Explicitly attached, user-approved presentation resources only |

Each Project selects one bounded local evidence-context strategy before
generation starts:

| Strategy | Use | What reaches the LLM |
|---|---|---|
| **BM25 retrieval** (default) | Normal use | The highest lexical-match PDF chunks for the question or generation task. |
| **Direct bounded PDF context** (experimental) | HCP comparison | A deterministic, source-balanced window of PDF chunks, with no relevance ranking. |

Neither strategy uses an external vector database, web search or a shared
knowledge base. Both keep source/page metadata, context limits, provenance
validation and human approval. If support is missing or insufficient, HPA asks
for a better PDF or a clarification instead of generating a scientific answer.
Direct context is not an evidence bypass: both modes use the same selected-
passage criterion. Changing the strategy after blueprint or slide generation
requires a new Project so the comparison remains auditable.

Each AI-generated slide reference must pass system validation:

1. the `resource_id` exists in the presentation selection;
2. the cited PDF page exists;
3. the cited evidence excerpt occurs on that page.

This is provenance verification, not a claim that the source itself is
clinically correct or appropriate for every use.

For readability, `/app` and Streamlit display a citation with the PDF title,
for example `[APA Depression Guideline, p. 4]`. The original model message,
including its `resource_id`, remains unchanged in SQLite; every displayed
citation also exposes its full technical identifier in an expandable details
section.

## Controlled workflow

```text
Discuss / explore PDFs (optional)
  → Collect and validate presentation context
  → Create presentation
  → Select Project-library PDF(s) for this presentation
  → Human validates the selected resources
  → Click Generate blueprint
  → Optionally complete title-slide delivery details
  → Edit and approve Agenda
  → Review blueprint items and approve blueprint
  → Click Generate slides, then review slides
     └─ unsupported AI slide → resolve that item (edit / add PDF / write it yourself)
  → Final human approval
  → Export PowerPoint
```

The model may suggest the next step, but code enforces workflow transitions.
Resource validation is requested when the user starts production; it is not
required simply to upload, read or discuss a PDF.

## Safety boundaries

HPA combines prompts with deterministic controls. Prompts are not the security
boundary.

1. User messages and PDF text are treated as untrusted content; PDF text cannot
   instruct the system to bypass its workflow.
2. Only selected and human-approved presentation PDFs can support production
   claims and citations.
3. `ProductionEvidenceGate` checks evidence availability and support from the
   selected evidence-context strategy before any model response or generation.
   Apart from a complete social acknowledgement, free-text chat without PDF
   passages is handled deterministically; presentation setup and professional
   scope are explicit human forms, never a chat bypass.
4. `WorkflowPolicy` rejects invalid lifecycle transitions.
5. `EvidenceProvenanceValidator` checks slide citations before acceptance and
   PowerPoint export; `ResponseCitationValidator` checks Resource Overview and
   Resource Chat citations before a response is persisted or displayed.
6. Agenda, blueprint, slides and final presentation need explicit human review.
7. Presenter and event details are optional deliverable metadata: they never
   block the workflow and are never fabricated by the LLM. A change after
   final approval reopens final approval only.
8. In Patient Case Mode, user-entered patient-case text is screened for obvious
   identifiers (for example email address, phone number, full date, record
   identifier or address) before it is persisted or reaches the LLM. Uploaded
   scientific PDFs are still screened for direct identifiers, but a publication
   date alone does not block a normal guideline or article. The user must
   confirm that their case is de-identified. This is an aid to
   privacy-conscious use, not a claim of HIPAA compliance or a substitute for
   institutional policy.
9. A submitted presentation-chat or Resource Chat user turn is persisted before
   provider work starts. A quota, network or provider failure therefore cannot
   remove that turn from its durable transcript. The audit trail records the
   received turn and a safe failure event (`AGENT_TURN_FAILED` or
   `RESOURCE_DISCUSSION_FAILED`) containing only failure category, retryability
   and configured provider/model identity — never the raw provider error.

## Architecture

```text
Interface adapters
├─ `/app` → FastAPI routes and asynchronous jobs
├─ Streamlit → local application use cases and durable Project jobs
└─ CLI → local conversational agent
                │
        ┌───────┴─────────────────────────────────────┐
        ▼                                             ▼
 Presentation chat                         Explicit user commands
        │                              (Resources / Analysis / Studio)
        ▼                                             │
 HealthcarePresentationAgent                          ▼
        │                             Bounded LLM use cases and workflow jobs
 trusted state + guarded chat tools                    │
        └───────────────────────┬─────────────────────┘
                                ▼
 Shared application use cases and domain rules
  ├─ Project resource library
  ├─ WorkflowPolicy and presentation state machine
  ├─ ProductionEvidenceGate + local BM25
  ├─ EvidenceProvenanceValidator
  └─ PowerPoint exporter
                │
                ▼
 SQLite: users · Projects/revision · state · resource pages/chunks · jobs · audit
```

State is deliberately separated:

| State | Responsibility |
|---|---|
| `GraphState` | Agent orchestration, presentation-chat transcript, compact continuity memory, resource-chat transcript, library and exploration analysis |
| `PresentationState` | Durable production lifecycle and approval flags |
| `ExecutionContext` | Last safe operation outcome or error; never a business approval |

The full current architecture rationale is in [ADR-0007](ADR.md). Earlier
architectural decisions and the author's historical reflection are
preserved in [docs/ARCHITECTURE_EVOLUTION.md](docs/ARCHITECTURE_EVOLUTION.md)
and [docs/architecture-history](docs/architecture-history/). The historical
prompt-engineering review is retained in [docs/PROMPT_REVIEW.md](docs/PROMPT_REVIEW.md).
The system-level evaluation approach is documented in
[docs/EVALUATION.md](docs/EVALUATION.md).

## Project structure

The repository follows a pragmatic clean-architecture layout. The tree below
lists source modules and important entry-point files; runtime directories such
as `venv/`, `data/`, `exports/`, caches and user-uploaded PDFs are intentionally
excluded.

```text
.
├── app/
│   ├── ai/                              # LLM-facing layer
│   │   ├── agents/                      # AgentBuilder, HealthcarePresentationAgent
│   │   ├── chains/                      # Blueprint and slide chains
│   │   ├── harness/                     # Healthcare safety harness
│   │   ├── llm/                         # Provider/model factory
│   │   ├── mappers/                     # LLM output → domain mapping
│   │   ├── prompt_builders/             # State, evidence, blueprint and slide prompts
│   │   ├── prompts/                     # System prompt and loop policy
│   │   ├── schemas/                     # Structured LLM output schemas
│   │   ├── service/                     # Conversation service
│   │   └── workflows/                   # GraphState, graph and guarded tools
│   ├── application/                     # Use cases and deterministic business services
│   │   ├── services/                    # Evidence gate, history, library, workflow policy
│   │   ├── use_cases/                   # PDF, blueprint, slides, review and PPTX operations
│   │   └── validators/                  # Resource, audience and provenance validation
│   ├── core/                            # Configuration, logging and version metadata
│   ├── domain/                          # Business models and rules
│   │   ├── enums/                       # Workflow, language, resource and theme enums
│   │   ├── exceptions/                  # Typed domain and workflow errors
│   │   ├── models/                      # Presentation, resources, slides, approvals, users
│   │   ├── profiles/                    # Professional role profiles
│   │   └── value_objects/               # Presentation context and reference value objects
│   └── interfaces/                      # Delivery and persistence adapters
│       ├── api/main.py                  # FastAPI composition, legacy-compatible routes and `/app`
│       │   └── routers/                 # Authentication, Project, platform and job routers
│       ├── storage/                     # SQLite UserSessionRepository
│       ├── web/                         # JavaScript app: Resources, Resource Analysis and Presentation Studio
│       └── langgraph/                   # Experimental checkpointer adapter
├── docs/
│   ├── README.md                         # Documentation index and ownership
│   ├── ARCHITECTURE_EVOLUTION.md         # Architecture history and learning reflection
│   ├── architecture-history/             # Superseded architecture records (V1–V3)
│   ├── EVALUATION.md                    # System-level evaluation and test strategy
│   ├── FANIS_REVIEW.md                   # Applied GenAI architecture review request
│   ├── HCP_EVALUATION.md                 # Short checkbox-based HCP evaluation form
│   ├── HCP_HOW_TO_USE_EN.md              # English HCP user guide
│   ├── HCP_HOW_TO_USE_FR.md              # French HCP user guide
│   └── PROMPT_REVIEW.md                 # Historical prompt-engineering review
├── tests/                               # Automated unit and workflow tests
├── main.py                              # Local CLI entry point
├── streamlit_app.py                     # Streamlit interface entry point
├── list_models.py                       # Utility to inspect available provider models
├── ADR.md                               # Current architecture decision record
├── README.md                            # Project documentation
├── requirements.txt                     # Python dependencies
├── pytest.ini                           # Pytest configuration
└── secrets.toml.example                 # Streamlit secrets template (never commit real secrets)
```

At runtime, SQLite data is created under `data/` and PowerPoint exports under
`exports/`. Uploaded PDF text is not stored in `project_sessions.state_json`:
the repository stores metadata in `project_resources`, page text in
`project_resource_pages`, and bounded retrieval chunks in
`project_resource_chunks`. These runtime artefacts and user PDFs should not be
committed to Git.

Every Project row also has a monotonically increasing `revision`. A save only
succeeds when its revision still matches the database row; a stale background
job therefore receives `PROJECT_VERSION_CONFLICT` rather than silently
overwriting newer human work. The job table also permits exactly one queued or
running state-writing job per Project; a second request receives
`PROJECT_JOB_ALREADY_RUNNING` and can be retried after the first job finishes.

The full presentation-chat transcript remains durable for the user and audit
trail. For each model request, only the 16 most recent presentation-chat
messages are kept in active context; older turns are compacted into a bounded,
non-authoritative continuity summary. Trusted workflow state and retrieved PDF passages remain
the authority.

## Domain error model

Expected business failures use a small typed hierarchy rather than unrelated
text-only `ValueError` exceptions:

```text
ValueError
└── DomainError                         # Common safe business failure
    ├── ValidationError                 # Deterministic invalid domain data
    ├── WorkflowError                   # Stable workflow code and retry flag
    │   └── InvalidTransition           # Action forbidden in the current state
    ├── ConcurrentModificationError     # A stale job/save cannot overwrite a Project
    └── ProjectJobRunningError           # Another state-writing Project job is active
```

All domain errors keep a human-readable `user_message`, a stable `code`, and a
`retryable` flag where relevant. They still inherit from `ValueError` for
compatibility with the existing FastAPI and interface handling.

For example, attempting to generate a blueprint before the selected resources
are ready raises `InvalidTransition` with the code
`INVALID_WORKFLOW_TRANSITION`. The API can then return a predictable conflict
response and the interface can direct the user to the required next step,
instead of trying to interpret an arbitrary text error.

## Local setup

```bash
git clone https://github.com/BOOBA7/Healthcare-Presentation-Assistant-HPA-v1.0-.git
cd Healthcare-Presentation-Assistant-HPA-v1.0-
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure one supported provider in `.env`:

```env
# OpenAI example
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=your_supported_model

# Gemini example
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=your_key
# GEMINI_MODEL=your_supported_model
# GEMINI_THINKING_LEVEL=low

LLM_TEMPERATURE=0.2
DEBUG=True
```

Use a model identifier available to your own API account. Never commit `.env`,
API keys, session tokens or Streamlit secrets.

## Run locally

### Web interface

```bash
uvicorn app.interfaces.api.main:app --reload
```

Open [http://127.0.0.1:8000/app](http://127.0.0.1:8000/app). API documentation
is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Streamlit

```bash
streamlit run streamlit_app.py
```

Open [http://localhost:8501](http://localhost:8501).

### CLI

```bash
python main.py
```

## API overview

The web client authenticates with a Bearer token. Project endpoints are
owner-scoped. Main endpoint groups include:

- `POST /auth/register`, `POST /auth/login`
- `POST /projects`, `GET /users/{user_id}/projects`, `POST /chat`
- `POST /api/v1/projects/{user_id}/{project_id}/blueprint/jobs`
- `POST /api/v1/projects/{user_id}/{project_id}/slides/jobs`
- `POST /resources/pdf/{user_id}/{project_id}`
- `POST /projects/{user_id}/{project_id}/resources/summary`
- `POST /projects/{user_id}/{project_id}/resources/discuss`
- `POST /projects/{user_id}/{project_id}/resources/{resource_id}/attach`
- `DELETE /projects/{user_id}/{project_id}/resources/{resource_id}/attach`
- `DELETE /projects/{user_id}/{project_id}/resources/{resource_id}`
- `GET /projects/{user_id}/{project_id}/audit-events`
- `GET /presentations/{user_id}/{project_id}/export/pptx`
- `POST /api/v1/conversations/jobs`, `GET /api/v1/jobs/{user_id}/{job_id}`
- `POST /api/v1/resources/{user_id}/{project_id}/overview/jobs`
- `POST /api/v1/resources/{user_id}/{project_id}/discussion/jobs`
- `GET /api/v1/observability/summary`

FastAPI endpoints are grouped by router (`auth`, `projects`, `platform` and
`jobs`) under `app/interfaces/api/routers/`. The remaining workflow routes
stay in `main.py` while they are migrated incrementally without breaking
Streamlit or `/app`.

The local password-reset endpoint is intentionally unsuitable for public
deployment. Use a real identity provider and secure recovery flow before any
public deployment.

## Tests

```bash
venv/bin/pytest -q
```

The test suite uses fake model responses and does not consume provider quota.
It includes repository concurrency/persistence tests, authenticated
Project/PDF API integration, and a deterministic end-to-end HCP workflow:
account → Project → PDF → Resource Overview/Resource Chat → explicit source
selection → human validation → blueprint/slide review → final approval →
PowerPoint export. It also includes a focused Playwright browser test for
`/app`: registration → presentation setup → PDF upload → resource validation
→ Resource Overview → blueprint generation. GitHub Actions installs Chromium
and runs this test with Python compilation, Ruff linting and JavaScript syntax
validation for every push and pull request to `main`. On macOS 10.15, the
browser test is skipped locally because Playwright Chromium is unsupported;
GitHub Actions remains the authoritative browser-test environment.

This is not a clinical benchmark score. HPA should be evaluated as a complete
evidence-gated system: uploaded PDF → retrieval → gate → workflow → human
review → export. See [docs/EVALUATION.md](docs/EVALUATION.md) for the concrete
test contract and a low-cost clinician-reviewed pilot plan.

## Current limitations and next production work

- SQLite is suitable for one local instance. The local optimistic Project
  revision prevents lost updates between local jobs, but PostgreSQL, migrations
  and object storage are needed for concurrent or multi-instance deployment.
- Scanned PDFs require OCR; OCR is not implemented.
- BM25 is private and transparent, but lexical and conservative. A future
  semantic retrieval layer must remain scoped to user-uploaded resources. BM25
  ranks exact lexical overlap; it does not itself understand synonyms,
  abbreviations, translations, or clinically equivalent wording. Its fixed
  bounded chunks can also separate related evidence. Consequently, a refusal
  can mean either that evidence is absent or that the lexical retriever did not
  select the supporting passage. This produces a safe false refusal, never a
  licence for the model to invent content.
- The first hands-on pilot found an unfair evidence-gate comparison: BM25
  assessed a single passage while Direct context pooled terms across passages.
  This has been corrected: both modes require one selected supporting passage
  to meet the same threshold, and a regression test protects the invariant.
  The modes may still allow or refuse different requests because they select
  different passages; that difference is the subject of HCP evaluation, not a
  safety bypass. See [docs/EVALUATION.md](docs/EVALUATION.md).
- Retrieval reads the normalized SQLite chunks directly. BM25 lexical terms
  and scores are intentionally recomputed in memory per request; for very
  large Project libraries, an indexed lexical implementation may be useful.
- Conversation context is bounded with a compact continuity summary. The
  summary is not a source of truth, and very long conversations may still need
  user-directed recap for the best quality.
- Each generation record captures the configured provider, exact configured
  model, prompt/harness/workflow/retrieval versions, retrieval mode and a UTC
  timestamp. It records configured execution metadata; it is not a guarantee
  of provider-side reproducibility.
- Only one local state-writing job can run per Project. This avoids duplicate
  model calls and concurrent saves, but it is still not a distributed queue or
  horizontal worker system.
- `main.py` still contains resource and review endpoints while their routers
  are being migrated incrementally.
- The resource overview and discussion use bounded PDF passages; they are not
  a replacement for full evidence synthesis or clinical review. Each response
  must carry a structured citation whose resource ID, PDF page and verbatim
  excerpt are checked by the system before it is displayed.
- `ProductionEvidenceGate` is deterministic and deliberately uses a minimal
  no-evidence allow-list: only a complete social acknowledgement reaches the
  model. Any future relaxation must add bypass regression tests first.
- Public deployment needs production authentication, rate limits, secure file
  storage, redacted logging, monitoring and incident procedures.
- HPA does not establish regulatory, legal, clinical or hospital compliance.
