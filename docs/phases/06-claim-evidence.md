# Phase 06 — Claim evidence, coverage and resource discussion

Status: 06.1, 06.2, 06.3 and the complete phase 06 gate were explicitly
approved by the product owner on 2026-09-17. Browser/visual, scientific,
anonymisation and professional-use reservations remain unchanged.

## Outcome and scope

Claim evidence, coverage and resource discussion. Requirements: FR-09, FR-10, FR-18, FR-19; PRD §§6,11. [PRD](../PRD.md) is authoritative.

Prerequisite satisfied: phase 05 explicitly approved by the product owner on
2026-09-17 for its documented restricted subset. Browser/visual checks remain
unverified. Implementation baseline: `41b5c7c`, published to `origin/main`.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/application/validators/evidence_provenance_validator.py`
- `app/application/validators/response_citation_validator.py`
- `app/application/services/production_evidence_gate.py`
- `app/application/use_cases/discuss_resources.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **06.1** — Introduce stable claim-to-evidence links for text/values with resource title, page/source slide, section, exact passage and supplied DOI/link; migrate legacy slide-level references without assuming claim verification.
2. **06.2** — Assess topic, objectives, audience, depth and slide-count coverage before Agenda creation and show missing evidence.
3. **06.3** — Show conflicting positions with dates/locations/passages without choosing scientific superiority; require explicit validated transfer from chat into planning.

## Acceptance criteria

- [ ] Wrong resource/location/excerpt cannot pass; an authentic but irrelevant quotation cannot silently become approved support. Distinguish deterministic provenance checks from human semantic review.
- [ ] Unsupported factual answers are refused; every supported factual answer is cited and chat cannot silently change workflow.
- [ ] Coverage failures explain missing resources; conflicts retain both positions.
- [ ] Claim markers expose readable evidence details and preserve the old-PPTX warning.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: **06.1 implemented and explicitly approved by the product
  owner on 2026-09-17.** Implementation, approval and the historical 05.1
  evidence report were committed as `445bc50`; publication was explicitly
  authorised by the owner.
- Stable, revisioned `MedicalClaim` and `EvidenceLink` records now distinguish
  deterministic source identity/location/passage verification from explicit
  human semantic review. Values, units and uncertainty are retained as
  explicit optional claim fields. Supplied DOI/URL values are accepted only
  when attributable to the stored source; absent metadata is not invented.
- Pre-06.1 slide references migrate losslessly and idempotently to stable
  `LegacySlideReference` review items. They remain visible but unassigned to
  claims and never inherit verification or approval. New slide generation asks
  for one stable claim identity per reference; model output remains pending
  until the authenticated review action verifies it.
- The owner-authenticated API action persists a claim/link revision, source
  check, semantic decision and privacy-safe audit metadata in one SQLite
  transaction. It enforces Project revision concurrency, owner isolation and
  rollback on audit failure. Generic saves cannot create a new approved link;
  reconstructed objects are rechecked at the repository boundary. Content
  edits invalidate semantic approval and advance claim revisions. Existing
  source removal/permanent deletion clears dependent slides through the
  established conservative invalidation path.
- Review/API responses and the browser expose claim markers, source title,
  location, exact passage, optional section/DOI/link and review state. Preview
  and PPTX export use only provenance-verified, human-approved current links.
  PPTX evidence continues to display exactly: “Source: user-supplied
  presentation — primary reference unavailable.” Legacy details remain
  consultable without being rendered as approved support.
- Focused verification: `venv/bin/python -m pytest -q
  tests/test_claim_evidence.py tests/test_evidence_provenance.py
  app/tests/test_pptx_roles.py tests/test_user_session_repository.py
  --tb=short` — **54 passed, 6 warnings**. Final provider-free suite:
  `venv/bin/python -m pytest -q app/tests tests -ra --tb=short` — **479
  passed, 2 skipped, 6 warnings in 103.15 seconds**. The skipped Playwright
  cases still require a supported browser/CI environment.
- Ruff, Python compilation, dependency consistency, bundled-Playwright Node
  JavaScript syntax and `git diff --check` passed. System `node` was absent;
  the bundled Node executable performed the required syntax check. Pip disabled
  its unwritable user cache and reported no broken requirements; nothing was
  installed.
- Native asset evaluation first failed closed inside the containing sandbox
  because local image screening was unavailable. The authorised rerun outside
  that containing sandbox exited 0: five synthetic PPTX/PDF probes retained
  their established results (clean text image accepted, possible name and
  schematic face refused, PDF image/table hashes and previews verified). This
  is not scientific, anonymisation, detector-accuracy or visual validation.
- Limits: no supported-browser execution or screenshot, real rendered-PPTX
  inspection, human semantic/scientific assessment, professional data or
  external provider call was performed. 06.1 does not assess corpus coverage,
  chat transfer or conflicts; those remain exclusively 06.2/06.3.
- Product-owner decision: **06.1 approved on 2026-09-17** for the documented
  claim-link and conservative-migration scope. This is not approval of the
  complete phase 06, scientific validity, browser rendering or professional
  use. The phrase “phase 6” in the owner's instruction is recorded as approval
  of the delivered 06.1 scope because 06.2 and 06.3 do not yet exist.
- Next exact action: stop after publishing the approved state. Do not begin
  06.2 without separate implementation authorisation.
- Complete phase-06 product-owner gate approval: pending.

### 06.3 handoff — neutral conflicts and explicit planning transfer

- **Implemented and explicitly approved by the product owner on 2026-09-17:** the resource-discussion
  response is still non-authoritative. Its current, provenance-verified
  citations are rendered as separate positions with stable resource ID,
  readable title, scientific date when available, page/source slide, optional
  section and supplied DOI/URL, exact passage, uncertainty and a mandatory
  human-review marker. No date, passage count, similarity, model decision or
  provenance result is presented as scientific superiority.
- **Definitions and rule boundary:** different passages are simply distinct
  verified quotations. Potentially conflicting positions are multiple current
  citations whose wording, population, date, context or purpose still requires
  human comparison. A deterministic conflict is declared only by versioned
  rule `discussion-conflict-v1`: after normalization, the complete cited
  statements are identical except for one or more explicit English/French
  negation tokens (`not`, `no`, `ne`, `pas`, `non`) and both polarities are
  present. This deliberately narrow workflow label is not scientific
  interpretation or ranking. All other differences remain potential conflicts.
  A discussion answer remains non-authoritative. A `discussion-transfer-v1`
  artifact becomes eligible for future planning only after explicit,
  authenticated owner approval. Applying it to an Agenda or Blueprint belongs
  to phase 07 and is not implemented here.
- The owner must confirm transfer content, retain every position in each
  conflict/potential-conflict group, record uncertainties, and choose the
  intended `agenda` or `blueprint` destination. The revisioned artifact stores
  a provenance snapshot plus discussion, context, coverage, selected-resource
  and passage digests. It is persisted and safely audited in the same SQLite
  transaction. The action enforces owner identity and optimistic Project
  revision; an audit failure rolls back state. Agenda and Blueprint are neither
  created nor edited.
- Generic saves and reconstructed objects cannot create or alter an approved
  transfer; a model/system actor is refused even by direct repository calls.
  Any later discussion, transfer-content, context, coverage, resource,
  validation or passage change makes the artifact obsolete or clears it.
  Only a current approved artifact is exposed as `validated_planning_transfer`;
  obsolete, fabricated and unapproved state is excluded from that future input.
  Source removal/deletion also clears the artifact through conservative source
  invalidation. Audit payloads contain identities, counts, destination,
  revision and status, never passages or transfer content.
- Files added: `app/domain/models/discussion_transfer.py`,
  `app/application/services/discussion_transfer.py`, and
  `tests/test_discussion_transfer.py`. Updated: Graph state, SQLite repository,
  source invalidation, API/project response, `/app` comparison and approval UI,
  phase index and this handoff.
- Behavioural coverage includes two explicitly negated synthetic positions,
  complete provenance display, a wording/population difference kept potential,
  all-position retention, explicit destination/content/uncertainty approval,
  persistence/restart, absence of Agenda/Blueprint mutation, model and generic-
  save bypass refusal, owner isolation, stale revision, audit rollback and
  discussion invalidation. The complete existing suite additionally covers
  citation errors, absent/removed/unvalidated sources, date gates, passage
  changes, context/coverage invalidation and source deletion paths.
- Verification: targeted transfer/discussion/coverage/API/repository tests —
  **41 passed, 6 warnings**; final 06.3-only run after the last invalidation
  case — **6 passed, 5 warnings in 1.86 seconds**. Full provider-free suite:
  `venv/bin/python -m pytest -q app/tests tests -ra --tb=short` — **494 passed,
  2 skipped, 6 warnings in 94.69 seconds**. The skipped Playwright scenarios
  still require supported browser/CI environments.
- `venv/bin/ruff check app tests streamlit_app.py main.py`, Python compilation,
  `venv/bin/python -m pip check`, bundled-Node JavaScript syntax and
  `git diff --check` passed. Pip disabled its unwritable user cache and found
  no broken requirements. No native asset evaluation was run because 06.3
  does not alter extraction, assets or filtering.
- Not performed: supported real-browser execution/screenshots, visual review,
  live-provider calls, scientific interpretation/validity assessment,
  anonymisation validation, professional/patient data or external review.
  Streamlit and patient mode remain unchanged/disabled.
- Product-owner decision: **06.3 and the complete phase 06 gate approved on
  2026-09-17** for the documented neutral-conflict and explicit-transfer scope.
  This does not approve scientific validity, browser rendering, anonymisation,
  professional use, or any Agenda/Blueprint generation or editing.
- **Next exact action:** publish the approved phase-06 state, then stop. Do not
  apply a transfer, generate or edit Agenda/Blueprint, or begin phase 07
  without separate implementation authorisation.
- 06.3 product-owner validation: approved 2026-09-17.
- Complete phase-06 product-owner gate approval: approved 2026-09-17.

### 06.2 handoff — evidence coverage before Agenda

- **Delivered and explicitly approved by the product owner (2026-09-17):** a persisted
  `EvidenceCoverageAssessment` evaluates the topic, every semicolon/newline-
  separated learning objective, target audience, requested depth and target
  slide count before any Agenda/Blueprint generation. The API and `/app`
  display each decision, its reason, matched resource/location identities and
  an appropriate resource request for every gap.
- **Explicit rule boundary:** an available passage is a chunk of at least 40
  normalized characters from a selected, parsed resource after human resource
  validation. A deterministic dimension match requires up to three meaningful
  terms to occur together in one passage; matches are never pooled. Workflow
  sufficiency requires every dimension to pass. Slide capacity is the explicit
  technical rule `3 fixed slides + at most 3 content slides per distinct usable
  passage`. These rules only control workflow. Every result retains
  `human_review_required=true`; no result claims scientific relevance or
  validity, and no opaque scientific score is exposed.
- The assessment stores context, selected-resource and passage-set SHA-256
  digests. Context/objective, validation, source selection/content/passage,
  removal or deletion changes make it obsolete or clear it. Both the queued
  API job gate and the direct `BuildBlueprintUseCase` gate require a current,
  sufficient assessment. Generic saves, reconstructed objects and model state
  cannot create or alter the server-owned decision.
- The authenticated assessment action enforces owner isolation and optimistic
  Project revision, and writes state plus a content-free audit summary in one
  SQLite transaction. Audit failure rolls back the assessment. The stored
  artifact survives repository/application restart; audit and operational
  errors contain no source passage text.
- Files added: `app/domain/models/evidence_coverage.py`,
  `app/application/services/evidence_coverage.py`,
  `tests/test_evidence_coverage.py`. Updated: Presentation/invalidation and
  Blueprint gates, SQLite repository, API/job router, server workflow view,
  `/app`, phase handoff, and the two synthetic end-to-end/date-gate fixtures.
- Behavioural coverage includes all five dimensions, multiple objectives,
  complementary passages, partial/non-pooled and short passages, unrealistic
  slide count, missing/stale assessment, context/passage invalidation, direct
  use-case bypass, generic-save fabrication, persistence/restart, owner
  isolation, stale revision, audit rollback, API/UI workflow gating, and
  deletion/removal regressions in the complete suite.
- Verification: `venv/bin/python -m pytest -q app/tests tests -ra
  --tb=short` — **487 passed, 2 skipped, 6 warnings in 112.76 seconds**. The
  two Playwright scenarios remain skipped because the current macOS version is
  unsupported. `venv/bin/ruff check app tests streamlit_app.py main.py`, Python
  compilation, `venv/bin/python -m pip check`, bundled-Node JavaScript syntax,
  and `git diff --check` passed. Pip disabled its unwritable user cache and
  reported no broken requirements. No native asset evaluation was run because
  06.2 changes no asset extraction or screening behavior.
- Not performed: supported real-browser execution/screenshots, visual review,
  real-provider calls, professional/patient data, human scientific/relevance
  assessment, anonymisation validation, or external review. Streamlit and
  patient mode remain unchanged/disabled.
- Product-owner decision: **06.2 approved on 2026-09-17** for the documented
  deterministic coverage and pre-Agenda gate scope. This is not approval of
  scientific validity, browser rendering, professional use or complete phase
  06.
- **Next exact action:** stop after publishing this approved state. Do not
  start 06.3, Agenda editing, Blueprint work or phase 07 without separate
  authorisation.
- Complete phase-06 product-owner gate approval: pending.
