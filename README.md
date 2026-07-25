# Healthcare Presentation Assistant (HPA)

HPA is an AI-assisted workflow for preparing scientific healthcare presentations from validated PDF resources. It collects a presentation context, generates a blueprint and slides, requires human approval at critical stages, then exports a PowerPoint file.

> HPA supports healthcare professionals; it does not provide medical advice or replace expert review. Generated content must be reviewed before use.

## Features

- Conversational collection of topic, audience, format, language, duration and objective.
- PDF extraction with PyMuPDF and resource validation.
- Structured blueprint and slide generation with LangChain, LangGraph and Gemini/OpenAI.
- Mandatory human approval for the blueprint, slides and final presentation.
- PowerPoint (`.pptx`) export.
- Streamlit interface with click-to-approve validation controls and user-scoped SQLite memory.
- FastAPI endpoints.

## Architecture

```text
User → HealthcarePresentationAgent → LangGraph → Tool → Use case → Domain
```

`GraphState` is the workflow state. Tools only delegate to application use cases; domain models do not depend on LangChain, LangGraph or an LLM provider. The architectural decision record is available in [ADR.txt](ADR.txt).

Before each model call, HPA injects a trusted workflow summary (context completeness, resource validation, blueprint and slide approvals). This prevents the model from inferring workflow state only from chat history.

## Local setup

```bash
git clone https://github.com/BOOBA7/Healthcare-Presentation-Assistant-HPA-v1.0-.git
cd Healthcare-Presentation-Assistant-HPA-v1.0-
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Configure `.env` with one provider:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-3.6-flash
GEMINI_THINKING_LEVEL=low
LLM_TEMPERATURE=0.2
DEBUG=True
```

Never commit `.env` or an API key.

For Gemini 3.6 Flash, `GEMINI_THINKING_LEVEL=low` reduces latency for conversation and tool routing. Use `medium` or `high` only when deeper reasoning is worth the slower response time.

## Run

### Streamlit

```bash
streamlit run streamlit_app.py
```

Open `http://localhost:8501`.

### API

```bash
uvicorn app.interfaces.api.main:app --reload
```

Open `http://127.0.0.1:8000/docs`.

### CLI

```bash
python main.py
```

## Recommended workflow

1. Describe the presentation in the chat.
2. Let HPA collect and validate the context, then create the presentation.
3. Upload a PDF resource and validate it.
4. Generate the blueprint and explicitly approve it.
5. Generate slides and explicitly approve them.
6. Approve the final presentation.
7. Download the PowerPoint.

The Streamlit sidebar handles user identification, PDF upload, explicit approval buttons and PowerPoint download. Reuse the same identifier on the same machine to restore the saved workflow. API users can use `POST /resources/pdf/{thread_id}` and `GET /presentations/{thread_id}/export/pptx`.

## Tests

```bash
pytest -q
```

Tests are designed to run without consuming LLM quota.

## Deployment on Streamlit Community Cloud

Set the main file to `streamlit_app.py`. In Streamlit secrets, set `LLM_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL` and `LLM_TEMPERATURE`; do not add them to GitHub.

## Limitations

- Streamlit sessions are persisted locally in SQLite per user identifier. The API session store is still in memory and is lost on restart.
- Output quality and availability depend on the LLM provider and its quota.
- PDF extraction supports selectable text; scanned PDFs need OCR, which is not yet implemented.
- Clinical claims and references require human review.

See [docs/PROMPT_REVIEW.md](docs/PROMPT_REVIEW.md) for a senior engineering review of the prompt design.
