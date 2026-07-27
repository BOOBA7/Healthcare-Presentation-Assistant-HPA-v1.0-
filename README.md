# Healthcare Presentation Assistant (HPA)

HPA helps healthcare professionals prepare scientific presentations from **their
own uploaded PDF resources**. It accelerates drafting and PowerPoint creation;
it does not replace scientific, clinical, or institutional review.

> HPA follows an FDA-oriented, human-in-the-loop design: traceability,
> evidence provenance, controlled workflow, and professional validation. It is
> not a diagnostic, prescribing, or individualized clinical decision system.
> The professional remains responsible for reviewing and approving every output
> before use.

## What the application does

- Collects presentation context: topic, audience, format, language, duration,
  objective, and professional profile.
- Keeps separate projects, conversations, resources, and presentation state for
  each authenticated local user.
- Accepts user-provided PDFs up to 20 MB and extracts selectable text with
  PyMuPDF.
- Retrieves compact evidence passages from **validated PDFs only** through
  local BM25 retrieval. No external knowledge base is used.
- Generates a blueprint, editable Agenda, and slides only after the required
  human validations.
- Verifies slide provenance: each reference must have a known `resource_id`, an
  existing PDF page, and an excerpt actually present on that page.
- Exports a themed `.pptx` presentation with a mandatory Agenda slide and a
  final *Resources and user validation* slide.
- Records project audit events such as uploads, approvals, regenerations, and
  exports in SQLite.

## Safety model

HPA uses prompts, retrieval, and code-level controls together. Prompts are not
the security boundary.

1. Only user-uploaded and user-validated PDFs are treated as evidence.
2. PDF text is delimited as untrusted content to resist prompt injection.
3. A deterministic evidence gate blocks scientific answers when no validated
   PDF exists or BM25 finds insufficient support; it asks for a suitable PDF or
   a more precise question instead.
4. Blueprint and slide generation are also blocked before the model call when
   sufficient evidence cannot be retrieved.
5. Provenance is checked again before a slide is accepted and before export.
6. Agenda, blueprint items, slides, and final presentation require explicit
   human approval.

The evidence gate is lexical BM25. It is deliberately conservative: a relevant
PDF written in another language or using very different terminology can be
blocked and may require a clearer query or a better source.

## Business workflow

```text
Collect context
  → Validate context
  → Create presentation
  → Upload PDF(s)
  → Validate resources
  → Generate blueprint
  → Edit and approve Agenda
  → Approve blueprint items and blueprint
  → Generate slides
  → Approve slides
  → Final approval
  → Export PowerPoint
```

The durable workflow states are enforced in code. The model can suggest an
allowed action, but it cannot bypass a state transition or a human approval.

## Architecture

```text
Web / Streamlit / CLI
        │
        ▼
FastAPI or local agent entry point
        │
        ▼
HealthcarePresentationAgent
        │  trusted state summary + prompt / harness / loop policy
        ▼
LangGraph reasoning loop ──► application use cases ──► domain models
        │                         │
        │                         ├─ WorkflowPolicy (state transitions)
        │                         ├─ ProductionEvidenceGate (BM25 threshold)
        │                         └─ EvidenceProvenanceValidator
        ▼
SQLite: users, projects, state, templates, audit events
```

State is separated by responsibility:

- `GraphState`: conversation and agent orchestration.
- `PresentationState`: durable business workflow and approvals.
- `ExecutionContext`: last tool outcome and safe technical error.

See [ADR.txt](ADR.txt) for the current architectural decisions.

## Local setup

```bash
git clone https://github.com/BOOBA7/Healthcare-Presentation-Assistant-HPA-v1.0-.git
cd Healthcare-Presentation-Assistant-HPA-v1.0-
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure one provider in `.env`.

```env
# OpenAI example
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=your_supported_model

# Or Gemini example
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=your_key
# GEMINI_MODEL=your_supported_model
# GEMINI_THINKING_LEVEL=low

LLM_TEMPERATURE=0.2
DEBUG=True
```

Use a model identifier available to your own API account. Never commit `.env`,
API keys, session tokens, or `secrets.toml`.

## Run locally

### Web interface (recommended)

```bash
uvicorn app.interfaces.api.main:app --reload
```

Open `http://127.0.0.1:8000/app`.

The API documentation is available at `http://127.0.0.1:8000/docs`.

### Streamlit

```bash
streamlit run streamlit_app.py
```

Open `http://localhost:8501`.

### CLI

```bash
python main.py
```

## API notes

The web interface authenticates first and sends a Bearer token to the API.
Project endpoints are owner-scoped. Useful endpoints include:

- `POST /auth/register`, `POST /auth/login`
- `POST /projects`, `GET /users/{user_id}/projects`
- `POST /chat`
- `POST /resources/pdf/{user_id}/{project_id}`
- `GET /projects/{user_id}/{project_id}/audit-events`
- `GET /presentations/{user_id}/{project_id}/export/pptx`

The local password-reset route is intentionally only suitable for local
development. Do not expose it publicly. Use a real identity provider and a
secure recovery flow before deployment.

## Tests

```bash
venv/bin/pytest -q
```

The test suite does not call an LLM and does not consume provider quota.

## Current limitations and production work

- SQLite is appropriate for one local instance. Use PostgreSQL and migrations
  for concurrent or multi-instance deployment.
- PDFs with no selectable text require OCR; OCR is not implemented yet.
- BM25 is local, private, and transparent, but has no semantic multilingual
  understanding. A later embedding retrieval layer should remain scoped to the
  user’s uploaded resources.
- Authentication, audit storage, uploaded files, and logs need production-grade
  hardening before public or hospital deployment.
- HPA is FDA-oriented by design, but it is not certified medical software and
  does not by itself establish regulatory, legal, or clinical compliance.
