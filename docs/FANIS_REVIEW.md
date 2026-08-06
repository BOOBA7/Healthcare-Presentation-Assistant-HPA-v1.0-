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
- project-level local BM25 retrieval or experimental bounded direct-PDF context,
  with no external document database;
- de-identified Patient Case Mode with deterministic obvious-identifier
  blocking before eligible user-entered content reaches the configured LLM;
  normal PDF publication dates are allowed, while direct identifiers remain
  blocked; this is a guardrail, not a HIPAA compliance claim;
- `ProductionEvidenceGate` before generation and scientific production-mode
  responses, using a safe default rather than a medical-keyword list;
- system validation of slide citations: resource, page, and quoted excerpt;
- visible provenance: AI-generated, user-edited, or user-authored content;
- bounded model memory with a complete durable conversation transcript;
- persistence of every submitted user presentation-chat turn before provider
  work, so provider failures cannot erase it from the transcript;
- local jobs with progress and one active state-writing job lock per Project;
- FastAPI API, `/app` web interface, Streamlit interface, and CLI;
- GitHub Actions CI: Python compilation, Ruff linting, JavaScript syntax check
  and provider-free tests on every push / pull request.

## Personal learning reflection and request for guidance

I understand the core idea behind HPA: an LLM should operate inside a system of
trusted context, business rules, evidence gates, workflow states, human review,
and auditable outputs. I am increasingly comfortable with the product and
healthcare reasoning behind these decisions.

However, I am still developing confidence with software-engineering terminology
and technical trade-offs. I can identify the questions I care about — for
example, whether a solution is robust, whether a retrieval approach is
appropriate, or how to prevent inconsistent workflow behavior — but I do not
yet always know how to translate those questions into the right technical
requirements or implementation choices.

At present, given my background, I am not yet able to independently determine
whether code proposed by Codex is technically sound, robust, or the most
appropriate technical choice. I can validate some outcomes through tests and
user behaviour, but I cannot always assess architectural quality, hidden
trade-offs, or long-term maintainability on my own.

This is the main capability I want to develop: not merely writing code faster,
but becoming able to review an implementation critically, identify when a
solution is fragile, and explain why one technical option is preferable to
another in a given context.

For instance, I now understand that BM25 is transparent, local, and auditable,
but may miss semantic similarity. My first instinct was to replace it because
meaning matters in healthcare. I now think the more disciplined approach is to
define an evaluation protocol, test it with an HCP, and use the results before
changing the retrieval architecture.

I also use coding assistance to accelerate implementation, but I do not want to
remain dependent on it for architectural judgment. My goal is to become able to
define the problem, constraints, failure behavior, acceptance criteria, and
tests clearly enough to review an implementation critically.

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

## Open question: hospital-owned learning materials and remote LLMs

I realised that "user-provided PDFs" does not automatically mean that a user is
authorised to disclose those PDFs to an external AI provider. A healthcare
professional may upload an internal hospital course, teaching material, or
institutional document that contains no patient information but is still
confidential or subject to the hospital's intellectual-property policy.

In the current HPA architecture, PDF extraction and SQLite persistence occur
locally. However, when the user requests a resource overview, resource
discussion, blueprint, or AI-generated slide, HPA sends a bounded selection of
the relevant PDF passages to the configured remote LLM provider. BM25 reduces
the amount of material sent; it does **not** make the material local-only.

My current understanding is that there is no purely technical way to use a
remote LLM without disclosing the passages given to it. Apart from a fully local
model, the product would need a clear governance decision. A possible future
resource classification could be:

| Resource classification | Behaviour |
|---|---|
| Approved for external AI | Bounded passages may be sent to the configured LLM. |
| Confidential — local only | The PDF remains in local storage but is excluded from all LLM overview, discussion and generation calls. |
| Sanitised copy approved for external AI | Only a human-reviewed de-identified/redacted copy may be used for LLM calls. |

This is not implemented yet. I would value feedback on whether this is the
right product boundary, where such a classification should live in the domain
model, and how to ensure no retrieval or workflow path can bypass it. I also
want to understand how far a small project should go before requiring an
institutionally approved provider contract, data-processing terms, retention
controls, and regional processing commitments.

## Proposed HCP evaluation: BM25 versus bounded direct PDF context

I would like a healthcare professional to test HPA with a short checkbox-based
form: [HCP_EVALUATION.md](HCP_EVALUATION.md).

The experiment would compare, with the same resources, model, question, and
context-character limit:

| Mode | Description | Status |
|---|---|---|
| A — BM25 | The system sends the best-ranked BM25 passages. | Implemented |
| B — bounded direct PDF context | The system sends a deterministic, source-balanced bounded portion of the same PDFs without BM25 ranking. | Implemented — experimental |

Mode B is an implemented **experimental comparison**. It must be tested with
the same PDF set, question, model and context limit as BM25 so that a user
preference is not confused with a change in evidence boundaries.

The HCP evaluation dimensions would be: faithfulness to sources, relevance,
important omitted information, citation usefulness, perceived response time,
and overall preference.

## What I would like you to review

I would especially value feedback on the following review materials.

### 1. Current automated system tests

The repository currently has a provider-free automated suite covering workflow
transitions, human approvals, evidence provenance (resource / page / excerpt),
resource deletion invalidation, conversation memory, SQLite persistence, API
flows, and job state. The suite currently passes 71 tests.

I would like to know whether these tests cover the most important failure modes
for the current stage of the product, and which missing test would provide the
highest value next.

### 2. The primary business scenario

```text
User-provided PDF
→ human resource validation
→ blueprint generation
→ Agenda review and approval
→ slide generation
→ human final approval
→ PowerPoint export
```

I would like you to assess whether this workflow is coherent and whether you
see a route through which an LLM, user action, or implementation detail could
incorrectly bypass an evidence or human-review rule.

### 3. Evaluation matrix

The broader system evaluation matrix is documented in
[EVALUATION.md](EVALUATION.md). It includes cases such as:

- a scientific question with no PDF;
- an unrelated PDF;
- a false citation page or excerpt;
- a veterinarian using a human-health guideline;
- deletion of a selected PDF;
- concurrent state-writing jobs for one Project.

I would value your opinion on whether these cases are well chosen and which
additional scenario should be required before an HCP pilot.

### 4. HCP evaluation and retrieval comparison

The exploratory HCP form is available in
[HCP_EVALUATION.md](HCP_EVALUATION.md). I can use its general usability,
evidence-fidelity, citation, and uncertainty sections immediately on the
current BM25 implementation.

The BM25 versus bounded direct-PDF-context comparison is now implemented as a
Project-level setting. The current question is:

> Is this proposed comparison sufficient for an initial HCP evaluation, and
> what would you change before or during a first controlled HCP comparison?

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
7. How would you recommend that I build stronger technical judgment when
   choosing between approaches, rather than only learning terminology?

## Known limitations and accepted technical debt

- jobs have durable SQLite state, but a server restart marks them interrupted;
  they are not automatically resumed;
- `app/interfaces/api/main.py` is still too central despite the existing routers;
- CI validates JavaScript syntax but does not yet run browser interaction tests;
- a complete PDF → workflow → PowerPoint business test with a fake LLM remains
  to be added;
- the HCP evaluation will not establish global clinical accuracy or regulatory
  compliance: it measures usefulness and adherence to the evidence contract.

## Feedback and decision log

| Date | Feedback / decision | Product consequence | Author |
|---|---|---|---|
| To be completed |  |  |  |
