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
but may miss semantic similarity. The first hands-on pilot exposed an unfair
comparison in the evidence gate between BM25 and Direct bounded context; I
corrected that implementation issue so both modes now apply the same
single-passage sufficiency criterion. Separately, the pilot made the remaining
BM25 boundary more concrete: lexical retrieval does not understand synonyms,
abbreviations, translations, brand/generic medication names, or clinically
equivalent wording, and bounded chunks can separate related evidence. This
does not make HPA generate unsupported content: it creates a safe false refusal
when the supporting passage is not selected. I would value your view on whether
I should first quantify this risk with a small HCP evaluation set before adding
semantic retrieval, and what evidence would justify that architectural change.

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

## First hands-on pilot finding: BM25 generated a blueprint but blocked slides

During the first hands-on test on 23 August 2026, I observed an inconsistency
that I would like to understand before treating the BM25/direct comparison as a
meaningful HCP evaluation. With the same user-provided PDF set and Project,
BM25 mode allowed blueprint generation, then slide generation stopped because
the system found insufficient evidence. With bounded direct PDF context, the
same route completed.

I do **not** interpret this as proof that BM25 is unsuitable, that direct
context is better, or that the evidence gate should be weakened. The blueprint
uses a broad presentation query while an individual slide uses a more specific
query. The discrepancy could therefore come from query wording, chunking,
ranking, a threshold, the slide-level gate, or a difference in selected
resources/state. Direct context may simply contain a supporting passage that a
lexical search missed; it does not demonstrate that every generated statement
is better supported.

On code review, I found one concrete reason this can happen: BM25 assessed the
best single ranked chunk, whereas Direct assessment pooled matching terms over
its selected source-balanced chunks. The modes therefore differed not only in
retrieval but also in how they passed the evidence-sufficiency gate. I treated
the comparison as invalid and corrected that invariant before collecting more
HCP preference data.

The correction now applies the same deterministic rule after either retrieval
strategy: one selected PDF passage must meet the required lexical-support
threshold. The diagnostics retain the retrieval mode, query-term count,
required match count, selected resource/page locations, anchor passage and
BM25 scores where relevant. A regression test covers the case where two
separate passages each contain a partial term match: neither mode may pass by
pooling them. The safety rule is unchanged: an insufficient slide is not sent
to the model for invention.

For the next HCP comparison, I plan to use a fixed resource set and keep an
execution record for the blueprint and each slide: exact retrieval query, top
chunk IDs and scores, source pages, selected passages, threshold/refusal reason,
and the corresponding direct-context selection. This should separate:

1. a legitimate safety refusal because the PDF does not support that exact
   slide; from
2. a retrieval defect because an appropriate supporting passage exists in the
   PDF but BM25 fails to select it.

I would especially value your advice on these questions:

1. Is a same-rule, single selected-passage evidence invariant a sound basis for
   comparing two passage-selection strategies in this MVP?
2. If BM25 misses a source-supported slide, would you first try a transparent
   slide-query reformulation or a bounded retrieval retry, rather than a silent
   fallback to Direct context?
3. What minimal regression fixture and telemetry would make a retrieval miss
   explainable and prevent it from returning?
4. What would make the HCP comparison methodologically useful without claiming
   that either mode is a clinical benchmark?

### Related first-pilot product observations

The same test also showed two workflow/UX gaps:

- after resource validation, the Resources workspace did not make the next
  authorised route into Presentation Studio clear enough;
- Resource Chat did not feel sufficiently fluid while the model was working.

I implemented both corrections without moving workflow authority into chat.
Resources now shows the server-authorised **Generate blueprint** command and a
route to Presentation Studio once the selected PDFs are validated. Resource
Chat displays the user question immediately and a local in-progress state while
its job runs. I would welcome feedback on whether this is the right boundary:
the UI exposes an authorised action, but server-side status checks still decide
whether the action may run.

### Proposed feature: use a precise PDF table in a precise slide

I also need a way for a user to request a specific table from an uploaded PDF
on a specific slide. I do not think this should rely only on a natural-language
prompt. My proposed first version is a deterministic selection flow:

```text
Choose resource → choose page/table or figure → choose target slide
→ choose “insert original” or “summarise as editable table” → review
```

For the first safe version, HPA would insert the original table/figure as an
image or a defined PDF crop, retain its source title, resource ID, page and
crop coordinates, and optionally let the LLM draft a caption. It would not ask
the LLM to retype numerical cells. An editable extracted table should be a
separate phase, with cell-level validation against the source before use.

Do you agree that this is the right 80/20 boundary for the feature?

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
flows, safe provider-failure audit events, asynchronous regeneration, evidence
gate bypass attempts and job state. It runs without consuming an LLM provider
quota.

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

## New product reflection: evidence-based Learning Mode

I am considering a future educational feature for students and residents who
provide their own learning resources. I do not think it should be merged into
the existing **Resource Overview** feature:

- Resource Overview is a one-off synthesis of the PDF library;
- Resource Chat is an open question-and-answer exploration of the PDFs;
- a future **Learning Mode** would be a structured pedagogical interaction.

My current product hypothesis is to expose Learning Mode as a separate,
persistent workspace under Resources, with its own transcript:

```text
Resources
├── PDF Library
├── Resource Overview
├── Resource Chat
└── Learning Mode (proposed)
```

It would reuse the existing user-scoped SQLite resources, BM25 or bounded direct
context, evidence gate and professional/language adaptation. It would not use
an external knowledge base. Its possible interactions would include:

- explanation at student or resident level;
- step-by-step teaching of a concept contained in the PDFs;
- Socratic questioning before an explanation;
- PDF-grounded quizzes or flashcards;
- recap of the learning session;
- an explicit request for a better PDF or clarification when the source does
  not support an answer.

The intended invariant would remain:

> No user-PDF evidence → no factual educational answer.

### Evidence-integrity improvement implemented

The slide-generation path validates each AI citation against the selected
resource, PDF page and quoted excerpt before approval and PowerPoint export.
I have now extended the same provenance pattern to Resource Overview and
Resource Chat through `ResponseCitationValidator`. A PDF-grounded response
must include structured citations such as:

```text
resource_id + page + evidence excerpt
```

The system verifies that the resource exists in the permitted scope, the page
exists, and the quoted excerpt occurs on that page before rendering the
citation. A failed validation rejects the generated response rather than
presenting it as an evidence-grounded answer.

I understand that this proves citation *provenance*, not that the model's wider
interpretation is clinically correct or fully entailed by that excerpt. The HCP
remains responsible for scientific interpretation.

### Questions for your feedback

1. Would you make Learning Mode a separate workspace and transcript, or make it
   a pedagogical view of Resource Chat?
2. Is a generic citation validator the right next abstraction before adding a
   Learning Mode?
3. Would you require structured LLM output for every PDF-grounded response, or
   introduce that incrementally starting with Resource Chat?
4. What is the smallest useful educational workflow to validate with students
   or residents before adding quizzes, flashcards and several teaching modes?

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
8. Do you agree with the proposed Learning Mode boundary and generic citation
   validator, or would you sequence these product and technical decisions
   differently?

## Known limitations and accepted technical debt

- jobs have durable SQLite state, but a server restart marks them interrupted;
  they are not automatically resumed;
- `app/interfaces/api/main.py` is still too central despite the existing routers;
- CI validates JavaScript syntax and runs a focused Playwright browser journey
  on GitHub Actions; macOS 10.15 skips that browser locally because Chromium is
  unsupported there;
- the end-to-end business workflow is covered with a fake LLM; broader
  resilience and real-HCP evaluation cases remain to be added;
- the HCP evaluation will not establish global clinical accuracy or regulatory
  compliance: it measures usefulness and adherence to the evidence contract.

## Feedback and decision log

| Date | Feedback / decision | Product consequence | Author |
|---|---|---|---|
| To be completed |  |  |  |
