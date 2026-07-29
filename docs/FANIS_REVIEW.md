# Applied GenAI Review Request — Healthcare Presentation Assistant

## Why this document

Hello Fanis,

This document brings together the context, technical choices, known limitations
and open questions of my **Healthcare Presentation Assistant (HPA)** project.
Its purpose is to make a repository review faster and more useful: I am mainly
looking for feedback on architecture decisions and the evaluation protocol,
rather than a sequence of disconnected questions.

## Background and intent

My career transition has been progressive:

1. year one: data science and programming foundations;
2. year two: **AI for Healthcare** bootcamp / nanodegree;
3. year three: **Growth Gig Applied GenAI Upskilling** in industry, with
   colleagues in Thessaloniki.

HPA is my applied learning project in the healthcare domain. My intent is to
reproduce the professional process of preparing a scientific presentation while
saving time for the user, without allowing an LLM to become a scientific source
of truth or a business-workflow authority.

## Product problem

A healthcare professional uploads their own PDFs, explores those resources,
prepares a presentation, reviews the blueprint and slides, and exports a
PowerPoint. The system should not generate a scientific claim when the selected
PDFs do not support it sufficiently.

The product does not replace the user's scientific interpretation or
professional responsibility.

## Core architectural principle

> **The LLM is not the workflow authority.**

The LLM may understand a request, propose content, and call an allowed action.
Code decides whether an action is allowed, whether evidence is sufficient,
whether a workflow transition is valid, and whether an output can be exported.

```text
User + user-provided PDFs
             ↓
   Resources normalized in SQLite
             ↓
Local retrieval + deterministic evidence gate
             ↓
LLM bounded by prompts, state, and selected passages
             ↓
Provenance validation + explicit human review
             ↓
PowerPoint with resources and authorship attribution
```

## Currently implemented elements

- separation of `domain` / `application` / `ai` / `interfaces`;
- controlled presentation state and business transitions;
- LangGraph with a guarded tool node;
- the LLM cannot approve resources, blueprint, slides, or export;
- PDF library per user and per Project;
- PDF pages and chunks persisted in SQLite, outside the large `state_json`;
- local BM25 retrieval with no external document database;
- `ProductionEvidenceGate` before generation and scientific production-mode
  responses;
- system validation of slide citations: resource, page, and quoted excerpt;
- visible provenance: AI-generated, user-edited, or user-authored content;
- bounded model memory with a complete durable conversation transcript;
- local jobs with progress and one active state-writing job lock per Project;
- FastAPI API, `/app` web interface, Streamlit interface, and CLI;
- GitHub Actions CI: Python compilation and tests on every push / pull request.

## Current RAG choice: local BM25

Current retrieval is lexical: BM25 selects PDF passages that share the most
relevant terms with a question or with content to generate.

### Why I made this initial choice

- no external knowledge base or shared global document folder;
- user-provided PDFs remain the only evidence base;
- simple behavior that is explainable and reproducible;
- `resource_id`, page, and excerpt are retained;
- low cost and limited complexity for a local project;
- bounded LLM context rather than sending complete PDFs on every request.

### Recognised limitation

BM25 prioritises word overlap. It may retrieve less effectively when the PDF
uses synonyms or a semantically close but different formulation. In a healthcare
context, I believe this should be evaluated empirically rather than resolved by
an immediate theoretical decision.

## Proposed HCP evaluation: BM25 versus bounded direct PDF context

I would like a healthcare professional to test HPA with a short checkbox-based
form: [HCP_EVALUATION.md](HCP_EVALUATION.md).

The experiment would compare, with the same resources, model, question, and
context-character limit:

| Mode | Description | Status |
|---|---|---|
| A — BM25 | The system sends the best-ranked BM25 passages. | Implemented |
| B — bounded direct PDF context | The system sends a wider deterministic portion of the same PDFs without BM25 ranking. | Proposed, not implemented |

Mode B is **not currently a feature**. It is documented as a controlled
experiment so that a design choice is not confused with a demonstrated result.

The HCP evaluation dimensions would be: faithfulness to sources, relevance,
important omitted information, citation usefulness, perceived response time,
and overall preference.

## Focused questions for this review

1. Is the principle “the LLM is not the workflow authority” translated
   correctly into the code, or do you see an area where the model still has too
   much authority?
2. At this product stage, is local BM25 a reasonable choice before introducing
   embeddings, or would you recommend another minimal and explainable approach?
3. Is the BM25 versus bounded direct-context protocol methodologically useful
   for an initial HCP review? Which criteria should I add or remove?
4. Is the current evidence gate too strict or not strict enough to prevent
   unsupported claims?
5. Where would you put the next technical priority: restartable job worker,
   end-to-end tests, API decomposition, RAG evaluation, or something else?
6. Which repository elements best demonstrate Applied GenAI / AI engineering
   competence, and which ones still look too fragile?

## Known limitations and accepted technical debt

- jobs have durable SQLite state, but a server restart marks them interrupted;
  they are not automatically resumed;
- `app/interfaces/api/main.py` is still too central despite the existing routers;
- CI does not yet validate `/app` JavaScript;
- a complete PDF → workflow → PowerPoint business test with a fake LLM remains
  to be added;
- the HCP evaluation will not establish global clinical accuracy or regulatory
  compliance: it measures usefulness and adherence to the evidence contract.

## Feedback and decision log

| Date | Feedback / decision | Product consequence | Author |
|---|---|---|---|
| To be completed |  |  |  |

