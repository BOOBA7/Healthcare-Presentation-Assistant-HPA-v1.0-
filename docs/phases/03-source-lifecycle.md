# Phase 03 — Preserved PDF sources, dates and deletion

Status: 03.1–03.3 implemented for the supported text-PDF subset and explicitly approved by the product owner on 2026-09-16. Node/browser reservations remain open.

## Outcome and scope

Preserved PDF sources, dates and deletion. Requirements: FR-04 (text PDF), FR-05, FR-07, FR-22; NFR-03. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 02 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/domain/models/resource.py`
- `app/application/use_cases/extract_pdf_resource.py`
- `app/application/use_cases/manage_project_resources.py`
- `app/interfaces/storage/user_session_repository.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **03.1** — Define extensible source/location/asset metadata and backward-compatible migration; screen in memory before durable acceptance and fail closed if screening cannot complete.
2. **03.2** — Retain accepted original PDF bytes, hash, metadata, extracted text/pages and available bibliography/rights; expose reliable document/scientific-metadata date evidence without automatic external research.
3. **03.3** — Distinguish professor library from Project attachments; implement removal, permanent deletion and dependent approval invalidation across Projects, including internal temporary exports.

## Acceptance criteria

- [x] Filesystem dates and unsupported declarations cannot satisfy the date gate; legacy undated sources are blocked (03.2 automated evidence; bounded supported date syntax).
- [x] Original bytes/hash and exact page locations survive restart for accepted text PDFs (03.2 automated evidence).
- [x] Supported text-PDF removal preserves library content; permanent deletion removes originals, text, assets, indexes and internal copies, invalidates dependencies and preserves external user exports.
- [x] Interrupted writes/deletion recover safely without reactivating deleted evidence (03.3 automated evidence; failed physical cleanup stays pending).

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Slice 03.2 evidence

See [03.2 originals and date evidence](03.2-source-preservation-evidence.md).
The first two acceptance criteria have automated evidence for the supported
text-PDF subset. [03.3 deletion evidence](03.3-source-deletion-evidence.md)
covers the remaining criteria. Checked criteria are not product-owner approval
or scientific validation.

## Session handoff

### Current — phase 03 approved, 2026-09-16

- Explicit owner decision: “j’approuve la phase 3”. Approval covers the
  implemented 03.1–03.3 text-PDF scope and carries the documented reservations.
- Evidence: **248 passed, 1 skipped, 6 warnings** in the full provider-free
  suite; final focused repository/lifecycle run **36 passed, 6 warnings**.
  Compilation, Ruff, dependency consistency and diff whitespace checks passed.
- Still unverified: JavaScript syntax (Node unavailable), supported browser
  execution (Chromium skipped on macOS 10.15), screenshots and remote CI.
  None of these checks becomes successful through product-owner approval.
- This decision is not complete PRD compliance, scientific validation,
  anonymisation assurance, or permission to process professional/patient data.
- The owner requested one consolidated commit for previously uncommitted
  phases 01–03, with supporting requirements, plans and verification records.
  Historical “no commit” entries below describe earlier sessions only.
  Staged whitespace review found six existing Markdown hard line breaks in the
  PRD header; they were intentionally preserved. The staged whitespace check
  excluding that unchanged-authority document passed.
- **Next exact slice: 04.1**, local OCR and text/image/metadata screening
  evaluation with synthetic fixtures. Phase 04 implementation has not started.
  Use [the new-chat prompt](04.1-start-prompt.md) to authorise that slice.


### Historical implementation handoff — 2026-09-16

- Authorisation: the owner requested continuation to make phase 03 ready for
  approval. 03.3 is implemented; no phase 04 work or human approval is inferred.
- Outcome: owner library independent of Project attachments, cross-Project
  permanent deletion, dependent-content/approval invalidation, cancelled-job and
  stale-write fences, ID-only deletion markers and restartable internal cleanup.
  New web/API PPTX exports are generated in memory; external copies are preserved.
- Decisions, changed files, recovery proofs and limits:
  [03.3 evidence](03.3-source-deletion-evidence.md).
- Verification: full suite **248 passed, 1 skipped, 6 warnings**; final focused
  lifecycle/repository suite **36 passed, 6 warnings**. Ruff, compilation, dependency
  consistency and diff whitespace checks passed. Intermediate failures are
  documented in the evidence record, not counted as successes.
- Unverified: Node JavaScript syntax (Node absent), actual browser execution
  (macOS 10.15 skip), screenshots and remote CI. Phase 02's approval with those
  reservations remains unchanged. No scientific, privacy or full PRD compliance
  validation is claimed.
- Recovery: transaction failure leaves prior content intact; post-commit cleanup
  failure leaves deleted sources unavailable and returns pending status. Restart
  retries cleanup. Legacy ambiguous owner/source identities fail closed. Deleted
  IDs cannot be reused; a deliberate new import gets a new identifier.
- Git: HEAD `dff973f`; existing owner edits preserved, no staging/commit.
  Application diff reviewed against `/tmp/hpa033-active-before/app`.
- **Next exact action: review and explicitly approve phase 03**, deciding whether
  to carry the documented Node/browser reservations. Approval is pending.
  Stop here; do not start phase 04 automatically.


### Historical resumption — 03.2 reconciled, 2026-09-15

Following the scoped resumption below, the owner's next “on continue” is
applied to the explicitly identified next slice, **03.2 only**. Reviewed the
already-present implementation against FR-05/FR-07: atomic original storage,
metadata integrity, date evidence, legacy blockers, owner-scoped download and
queued-work gates. No application correction was needed or made in this turn.
Existing owner changes remain intact; no staging or commit occurred.

Fresh focused verification: `venv/bin/python -m pytest -q
app/tests/test_source_preservation.py app/tests/test_source_lifecycle.py -ra`
returned **70 passed, 6 warnings**, exit 0, with no failures or skips.
Ruff, Python compilation and Git diff whitespace checks passed again.
The immediately preceding resumption's combined run remains **226 passed,
1 skipped, 6 warnings**; application/test code has not changed since that run.
Node syntax and browser execution remain unverified. This is implementation
evidence, not scientific validation or product-owner phase gate approval.

**Next exact slice: 03.3**, library versus Project attachment, removal,
permanent deletion and dependency invalidation, including temporary exports.
Requires separate authorisation. Stop after 03.2; 03.3 has not started.

### Scoped resumption check — 2026-09-15

The explicit instruction available for this resumption authorises **03.1 only**
and excludes 03.2 and 03.3. The working tree already contains the 03.2 code and
evidence described below. Those existing changes were preserved, not newly
implemented or treated as authorised by a generic continuation message.
No application code was changed during this resumption and no 03.3 work began.

Reviewed the 03.1 metadata, memory upload, screening, repository guards and
regression tests on the existing combined working tree. Re-ran
`venv/bin/python -m pytest -q app/tests tests -ra`: **226 passed, 1 skipped,
6 warnings**, exit 0. Ruff, Python compilation, dependency consistency and
Git diff whitespace checks passed. No test failure occurred in this resumption.
Node remains unavailable; JavaScript syntax remains unverified. The macOS
10.15 browser test was skipped, not passed. No scientific validation, complete
PRD compliance, phase gate approval or external-provider result is inferred.

Next exact slice after the authorised 03.1 boundary: **03.2**, requiring explicit
scope reconciliation with its already-present implementation before further
work. The historical 03.2 handoff below describes repository content, not new
authorisation to proceed to 03.3. HEAD remains `dff973f`; no staging or commit.

### Previously recorded implementation handoff

- Current slice: **03.2 implemented**; 03.1 remains preserved.
- Changes: atomic SQLite original PDF BLOBs and SHA-256, retained PDF/XMP and
  available bibliography/rights, explicit scientific-date provenance, immutable
  original identities, shared date/original gates, owner-scoped download and
  escaped FR/EN date/blocker display in `/app`.
- Decisions, changed files and proofs: [03.2 evidence](03.2-source-preservation-evidence.md).
  Earlier [03.1 evidence](03.1-source-screening-evidence.md) remains historical.
- Final checks: **226 passed, 1 skipped, 6 warnings** with
  `venv/bin/python -m pytest -q app/tests tests -ra`. Compilation, Ruff,
  dependency consistency and diff whitespace passed. Intermediate failures and
  their corrections are recorded separately; no final Python failure remains.
- Not verified: Node JavaScript syntax check (Node unavailable, exit 127),
  actual browser rendering (Chromium skipped on macOS 10.15), screenshots,
  remote CI and live providers. Phase 02's approval with these reservations is
  unchanged and is neither full PRD compliance nor scientific validation.
- Recovery: old records remain readable/saveable unchanged. Missing dates or
  originals block scientific use and require reimport. No fabricated original,
  scientific date, exact legacy page location or new human approval is created.
- Boundaries: supported ISO-precision dates with explicit EN/FR labels or
  recognized PRISM metadata only; no automatic research, OCR/assets, new format,
  professional mode or permanent-deletion work. Existing removal behavior remains.
- Git: HEAD `dff973f`; existing owner edits preserved, no staging or commit.
  Application/test diff reviewed against `/tmp/hpa032-before`.
- Test discovery: include `app/tests` explicitly; default pytest only includes
  `tests/`. Existing regression fixtures were updated with actual dated
  synthetic originals without bypassing deterministic gates.
- Next exact slice: **03.3** — professor library versus Project attachments;
  removal, permanent deletion and dependent approval invalidation across
  Projects, including internal temporary exports. Requires separate authorisation.
- Product-owner phase 03 gate approval: pending. No human pilot, scientific,
  privacy or external competent validation is recorded as obtained.
