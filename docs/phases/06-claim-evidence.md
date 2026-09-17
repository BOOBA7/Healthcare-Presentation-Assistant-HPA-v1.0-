# Phase 06 — Claim evidence, coverage and resource discussion

Status: 06.1 explicitly approved by the product owner on 2026-09-17. The
complete phase 06 gate remains pending; 06.2 and 06.3 have not started.

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
