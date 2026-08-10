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
- slide-level citation provenance checks; Resource Overview and Resource Chat
  citation validation is intentionally not yet implemented;
- persisted conversation and Project revision conflicts;
- evidence-bound short or indirect questions that must not bypass PDF retrieval;
- persistence and safe audit events for submitted presentation-chat and
  Resource Chat turns when a model provider fails;
- Patient Case Mode acceptance of normal PDF publication dates while direct
  identifiers remain blocked;
- bounded model context with durable full conversation history;
- durable job state;
- authenticated HTTP Project/PDF lifecycle.
- a deterministic end-to-end HCP workflow from account creation through PDF
  upload, Resource Overview, Resource Chat, source selection, human approvals,
  direct slide authoring and PowerPoint export. It asserts that the Resource
  workspace transcript remains separate from the production-chat transcript.
  The LLM boundary is replaced by a local structured-output test double, while
  the real API, SQLite persistence, background job, evidence validation and
  export code execute unchanged.

GitHub Actions executes Python compilation, Ruff linting, JavaScript syntax
validation and this suite on every push and pull request targeting `main`.

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
| Citation with a false page or excerpt | Reject the slide before approval/export. |
| Arabic source excerpt | Accept only the exact matching Arabic page text. |
| Veterinarian using a human guideline | Request professional-scope clarification before production. |
| Supported scientific question | Respond only from selected bounded PDF passages and cite source/page. |
| Patient Case Mode identifier | Block the request before an LLM call and request de-identification. |
| Patient Case Mode + guideline publication date | Accept the PDF date alone; continue to block direct identifiers. |
| Provider quota/network failure | Keep the submitted chat turn in its durable transcript and record a safe failure category, retryability and configured provider/model in the audit trail. |
| BM25/direct mode comparison | Preserve the same resource-validation, evidence-gate and provenance rules. |
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
the implemented bounded direct-PDF-context mode. The two trials must use the
same PDF set, prompt, model and context limit.

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
3. provider/model traceability assertions for every generation record;
4. clinician-reviewed pilot cases, kept separate from production user data.
5. adversarial evidence-gate phrasing tests, especially presentation commands
   that also contain an unsupported scientific request.
