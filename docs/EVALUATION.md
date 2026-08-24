# HPA evaluation strategy

## Purpose

HPA must be evaluated as a **system**, not only as a language model. Its
expected behavior results from the combination of user PDFs, local retrieval,
deterministic workflow rules, provenance validation, human review and the
selected LLM provider.

```text
User PDF → selected bounded evidence context → evidence gate → LLM → provenance check
         → human approval → PowerPoint export
```

An external model benchmark such as OpenAI HealthBench can be useful for
understanding a base model's health-oriented conversational behavior. It does
not by itself demonstrate that HPA correctly retrieves a user's PDF, blocks an
unsupported claim, enforces a workflow transition, or exports traceable slides.
HPA does not require an OpenAI account or an OpenAI benchmark to run its own
evaluation suite.

## Automated regression suite

Run the deterministic suite locally:

```bash
venv/bin/pytest -q
```

The suite must remain provider-free: it uses fake or monkeypatched model
outputs and never spends LLM quota. It currently covers, among other things:

- workflow transitions and required human approvals;
- Project resource selection and deletion invalidation;
- source-only API responses;
- PDF page/excerpt provenance, including Arabic excerpts;
- citation provenance checks for AI slides, Resource Overview and Resource
  Chat: resource ID, page and verbatim PDF excerpt must match;
- persisted conversation and Project revision conflicts;
- evidence-bound short or indirect questions that must not bypass PDF retrieval;
- persistence and safe audit events for submitted presentation-chat and
  Resource Chat turns when a model provider fails;
- Patient Case Mode acceptance of normal PDF publication dates while direct
  identifiers remain blocked;
- bounded model context with durable full conversation history;
- durable job state;
- authenticated HTTP Project/PDF lifecycle.
- a focused Playwright browser journey through `/app`: registration,
  presentation setup, PDF upload, production-resource validation, Resource
  Overview and blueprint generation, all with a deterministic model boundary.
- a deterministic end-to-end HCP workflow from account creation through PDF
  upload, Resource Overview, Resource Chat, source selection, human approvals,
  direct slide authoring and PowerPoint export. It asserts that the Resource
  workspace transcript remains separate from the production-chat transcript.
  The LLM boundary is replaced by a local structured-output test double, while
  the real API, SQLite persistence, background job, evidence validation and
  export code execute unchanged.

GitHub Actions executes Python compilation, Ruff linting, JavaScript syntax
validation and this suite on every push and pull request targeting `main`. It
installs Playwright Chromium before running the browser journey. On macOS 10.15
that browser test is skipped locally because Chromium is no longer supported by
Playwright for that operating-system version.

## First hands-on pilot observations — 23 August 2026

The following are product findings from the first hands-on test. They are not
clinical conclusions and they do not establish that either evidence mode is
scientifically superior.

| Finding | Observed behaviour | Product impact | Status |
|---|---|---|---|
| BM25 generation inconsistency | With the same user-provided PDF set, a blueprint was generated in BM25 mode, but subsequent slide generation was blocked for insufficient evidence. The bounded direct-context mode completed the same path. | The evidence-mode comparison was unfair and the workflow felt blocked. | Corrected: both modes now apply the same per-passage evidence criterion; a blocked slide is independently recoverable. |
| BM25 lexical retrieval boundary | The pilot made clear that BM25 selects passages from lexical term overlap only. It cannot itself recognise synonymous, abbreviated, translated, or clinically equivalent wording, and a fixed text chunk can separate related evidence. | A supporting statement can remain undiscovered even though it exists somewhere in the uploaded PDF; this is a possible false refusal, not permission to generate unsupported content. | Open evaluation risk. The pilot did not prove a semantic miss in a specific PDF; it exposed why BM25 and Direct must be compared with reproducible cases and retrieval diagnostics. |
| Production journey from Resources | After a resource was prepared and validated, the route into presentation generation was not clear or available from the Resources workspace. | The user could not reliably discover the next authorised action. | Corrected: Resources exposes the server-authorised **Generate blueprint** action and a route to Presentation Studio. |
| Resource Chat fluency | Document discussion did not feel continuous or responsive enough during model work. | The exploration workspace was less useful before production starts. | Corrected in both interfaces: the question is displayed immediately and the resource panel has an in-progress state while the job runs. |
| Exact PDF table in a target slide | A user needs to place a specific table from a supplied PDF on a specific slide. | The current text-generation path is not a reliable table-placement feature. | Product design pending |

The fix preserves the pilot record while making the comparison interpretable.
For each blueprint or slide, both modes now select a bounded set of passages
and apply the same rule: a **single selected passage** must meet the required
lexical-support threshold. The retrieval mode can therefore differ only in
which passages it selects, not in how it decides sufficiency. The diagnostic
record stores the query-term count, required match count, selected
resource/page locations, retrieval mode and BM25 scores where applicable.

The next HCP comparison should still use a fixed PDF set and record the
blueprint and each slide's query, selected pages, scores, threshold/refusal
reason and outcome. That distinguishes a legitimate refusal (the PDF does not
support the slide) from a retrieval limitation (a supporting passage exists but
the selected BM25 passages did not include it).

The safety rule remains unchanged: a failed BM25 retrieval must not be solved
by letting the model invent content. Direct bounded context remains an
experimental comparison, not an evidence bypass.

BM25 is therefore an intentionally transparent retrieval baseline, not a
semantic understanding component. It is well suited to auditing why a passage
was selected, but it does not infer that different wording has the same
clinical meaning. Any future hybrid or semantic retrieval experiment must use
only the user's uploaded PDFs, retain the existing PDF/page/excerpt provenance
checks, and be evaluated against the same versioned HCP cases before becoming
the default.

## Product evaluation set

Before calling a release suitable for a pilot, create a small, versioned
evaluation set from realistic use cases reviewed by healthcare professionals.
Start with 30–50 cases and document each case in a table or JSON/CSV fixture.
No external clinical database is required: cases can reference deliberately
small test PDFs created for the Project.

| Scenario | Expected system behavior |
|---|---|
| Medical question without a PDF | Refuse scientific answer and request a user-provided PDF. |
| Short or indirect factual question without a PDF | Treat it as evidence-bound; do not rely on medical-keyword matching. |
| PDF unrelated to the question | Request a more suitable source or clarification. |
| Citation with a false page or excerpt | Reject the AI response before display; slides also remain blocked before approval/export. |
| Arabic source excerpt | Accept only the exact matching Arabic page text. |
| Veterinarian using a human guideline | Request professional-scope clarification before production. |
| Supported scientific question | Respond only from selected bounded PDF passages and cite source/page. |
| Patient Case Mode identifier | Block the request before an LLM call and request de-identification. |
| Patient Case Mode + guideline publication date | Accept the PDF date alone; continue to block direct identifiers. |
| Provider quota/network failure | Keep the submitted chat turn in its durable transcript and record a safe failure category, retryability and configured provider/model in the audit trail. |
| Mixed profile/workflow + scientific request without a PDF | Refuse it before a model call; profile or presentation wording must not bypass the evidence gate. |
| Slide regeneration with reviewer feedback | Persist the feedback, run a durable regeneration job, and use the feedback only for the requested slide. |
| BM25/direct mode comparison | Preserve resource validation, provenance and human approval; use the same per-passage evidence criterion and record selection diagnostics for both modes. |
| Deleted selected PDF | Invalidate dependent blueprint, slides and approvals. |
| Two writes/jobs for one Project | Preserve the newer state; reject the stale write. |

For each case, record:

- test case identifier and version;
- input message and Project resources;
- expected allow/block/workflow outcome;
- expected citations or expected refusal reason;
- model provider and model identifier when a live model is used;
- reviewer decision and date.

The key release metric is not a generic model score. It is the rate at which
HPA follows its own evidence and workflow contract: correct refusal, correct
retrieval, valid provenance and successful human-reviewed export.

For a short qualitative evaluation with a healthcare professional, use
[HCP_EVALUATION.md](HCP_EVALUATION.md). It includes a checkbox-based protocol
for testing usefulness, evidence fidelity, citation usability and uncertainty
handling. It also includes a controlled comparison between BM25 retrieval and
the implemented bounded direct-PDF-context mode **once the documented
evidence-gate parity issue is resolved**. The two trials must use the same PDF
set, prompt, model and context limit.

## Evaluation boundaries

This process measures application behavior. It does not establish clinical
accuracy, clinical effectiveness, regulatory compliance, certification or FDA
clearance. A healthcare professional remains responsible for the source choice,
scientific interpretation and final presentation.

## Known evaluation gaps

The next evaluation additions should be:

1. concurrent-job and server-restart recovery scenarios;
2. qualitative long-conversation tests for continuity, relevance and correct
   use of the compacted-memory summary across multiple workflow stages;
3. clinician-reviewed pilot cases, kept separate from production user data;
4. provider-side request identifiers or immutable prompt archives when they
   become available from the selected provider.
