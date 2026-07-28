# Healthcare Presentation Assistant (HPA)

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

## What it does

- Creates separate, authenticated local user accounts and Projects.
- Stores a professional profile (role and preferred language: English, French
  or Arabic) to adapt the assistant's communication style.
- Lets users upload readable PDFs (maximum 20 MB) to a **Project resource
  library**, even before a presentation exists.
- Provides a source-only resource overview and a dedicated PDF discussion mode
  to explore the uploaded material without changing a presentation.
- Lets the user explicitly select library resources for a presentation. Only
  this selection is used as production evidence.
- Generates an editable blueprint, an Agenda, slides and a themed PowerPoint
  after the required human review steps.
- Supports direct user editing of blueprint items and slides, while preserving
  an AI-origin snapshot and labelling content as AI-generated, user-edited or
  user-authored.
- Validates evidence provenance for AI-generated slides and exports a final
  *Resources and validation* slide.
- Persists Projects, conversation transcripts, extracted PDF text, templates,
  workflow state and audit events in local SQLite storage.

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

For production, HPA uses a local lexical BM25 retrieval layer over extracted
PDF-page chunks. It selects a small, bounded evidence context; it does not use
an external vector database, web search or a global knowledge base. If support
is missing or insufficient, the deterministic evidence gate asks for a better
PDF or a clarification instead of generating a scientific answer.

Each AI-generated slide reference must pass system validation:

1. the `resource_id` exists in the presentation selection;
2. the cited PDF page exists;
3. the cited evidence excerpt occurs on that page.

This is provenance verification, not a claim that the source itself is
clinically correct or appropriate for every use.

## Controlled workflow

```text
Discuss / explore PDFs (optional)
  → Collect and validate presentation context
  → Create presentation
  → Select Project-library PDF(s) for this presentation
  → Request blueprint generation
  → Human validates the selected resources
  → Generate blueprint
  → Edit and approve Agenda
  → Review blueprint items and approve blueprint
  → Generate and review slides
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
3. `ProductionEvidenceGate` checks evidence availability and BM25 support
   before model generation.
4. `WorkflowPolicy` rejects invalid lifecycle transitions.
5. `EvidenceProvenanceValidator` checks citations before slide acceptance and
   PowerPoint export.
6. Agenda, blueprint, slides and final presentation need explicit human review.

## Architecture

```text
Web app (/app) · Streamlit · CLI
                │
                ▼
              FastAPI
                │
                ▼
    HealthcarePresentationAgent
                │
     trusted state summary + prompts
                ▼
  LangGraph guarded agent/tool loop
                │
                ▼
 Application use cases and domain rules
  ├─ Project resource library
  ├─ WorkflowPolicy and presentation state machine
  ├─ ProductionEvidenceGate + local BM25
  ├─ EvidenceProvenanceValidator
  └─ PowerPoint exporter
                │
                ▼
 SQLite: users · Projects · state · transcripts · templates · audit events
```

State is deliberately separated:

| State | Responsibility |
|---|---|
| `GraphState` | Agent orchestration, conversation transcript, Project library and exploration analysis |
| `PresentationState` | Durable production lifecycle and approval flags |
| `ExecutionContext` | Last safe tool outcome or error; never a business approval |

The full architecture rationale is in [ADR-0007](ADR.txt). The historical
prompt-engineering review is retained in [docs/PROMPT_REVIEW.md](docs/PROMPT_REVIEW.md).

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
│       ├── api/main.py                  # FastAPI API and `/app` routes
│       ├── storage/                     # SQLite UserSessionRepository
│       ├── web/                         # JavaScript web app: HTML, CSS and client logic
│       └── langgraph/                   # Experimental checkpointer adapter
├── docs/
│   └── PROMPT_REVIEW.md                 # Historical prompt-engineering review
├── tests/                               # Automated unit and workflow tests
├── main.py                              # Local CLI entry point
├── streamlit_app.py                     # Streamlit interface entry point
├── list_models.py                       # Utility to inspect available provider models
├── ADR.txt                              # Current architecture decision record
├── README.md                            # Project documentation
├── requirements.txt                     # Python dependencies
├── pytest.ini                           # Pytest configuration
└── secrets.toml.example                 # Streamlit secrets template (never commit real secrets)
```

At runtime, SQLite data is created under `data/`, PowerPoint exports under
`exports/`, and uploaded resource content is stored in the Project state. These
runtime artefacts and user PDFs should not be committed to Git.

## Domain error model

Expected business failures use a small typed hierarchy rather than unrelated
text-only `ValueError` exceptions:

```text
ValueError
└── DomainError                         # Common safe business failure
    ├── ValidationError                 # Deterministic invalid domain data
    └── WorkflowError                   # Stable workflow code and retry flag
        └── InvalidTransition           # Action forbidden in the current state
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
- `POST /resources/pdf/{user_id}/{project_id}`
- `POST /projects/{user_id}/{project_id}/resources/summary`
- `POST /projects/{user_id}/{project_id}/resources/discuss`
- `POST /projects/{user_id}/{project_id}/resources/{resource_id}/attach`
- `DELETE /projects/{user_id}/{project_id}/resources/{resource_id}/attach`
- `DELETE /projects/{user_id}/{project_id}/resources/{resource_id}`
- `GET /projects/{user_id}/{project_id}/audit-events`
- `GET /presentations/{user_id}/{project_id}/export/pptx`

The local password-reset endpoint is intentionally unsuitable for public
deployment. Use a real identity provider and secure recovery flow before any
public deployment.

## Tests

```bash
venv/bin/pytest -q
```

The test suite uses fake model responses and does not consume provider quota.

## Current limitations and next production work

- SQLite is suitable for one local instance. Use PostgreSQL, migrations and
  object storage for concurrent or multi-instance deployment.
- Scanned PDFs require OCR; OCR is not implemented.
- BM25 is private and transparent, but lexical and conservative. A future
  semantic retrieval layer must remain scoped to user-uploaded resources.
- The resource overview and discussion use bounded PDF passages; they are not
  a replacement for full evidence synthesis or clinical review.
- Public deployment needs production authentication, rate limits, secure file
  storage, redacted logging, monitoring and incident procedures.
- HPA does not establish regulatory, legal, clinical or hospital compliance.
