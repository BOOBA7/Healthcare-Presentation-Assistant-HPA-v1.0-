# Phase 05 — PowerPoint evidence and extracted visuals

Status: 05.1 approved by the product owner on 2026-09-17. Phase 05 gate
approval remains pending. 05.2 was explicitly approved by the product owner on
2026-09-17 for its documented restricted subset. 05.3 has not started.

## Outcome and scope

PowerPoint evidence and extracted visuals. Requirements: FR-04 (PPTX/assets), FR-05; FR-06–FR-08; FR-18 (old decks). [PRD](../PRD.md) is authoritative.

Prerequisite: phase 04 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/domain/enums/resource_type.py`
- `app/domain/models/resource.py`
- `app/application/use_cases/add_resource.py`
- `app/application/services/resource_library.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **05.1** — Add PPTX text/image/table extraction preserving source slide numbers; screen notes and embedded metadata too.
2. **05.2** — Retain PDF/PPTX extracted images/tables with source locations, dates, rights/provenance and uncertainty review.
3. **05.3** — Separate evidence import from explicit template reuse and display the PRD warning when an old deck lacks a primary reference.

## Acceptance criteria

- [ ] Synthetic source slides and assets resolve to original locations after restart.
- [ ] All formats and derived assets obey privacy/date gates and permanent-deletion semantics.
- [ ] Evidence import never silently changes style; missing bibliographic data is not fabricated.
- [ ] DOCX, spreadsheets and DICOM remain rejected.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Approved 05.1 handoff (historical)

- Current slice: **05.1 implemented and explicitly approved by the product
  owner on 2026-09-17.**
- The restricted in-memory PPTX reader accepts native slide text and simple
  tables, preserves one-based presentation-order slide locations, inventories
  screened images/tables and retains the exact original, hash and minimal
  descriptors across restart. Evidence import does not select or change a
  presentation template. No extracted asset copy or visual-review workflow from
  05.2 was implemented.
- The complete OOXML package is bounded and screened before acceptance: notes,
  core/extended/custom properties, shape names and alternate text, filenames,
  relationships and reachable XML parts. External/dangling/unknown relations,
  opaque or orphaned parts, encrypted/malformed/ambiguous ZIP/XML, unsupported
  drawings/objects, unsafe metadata, conflicting or missing scientific dates,
  limits and format disguises fail closed without a durable raw write.
- Existing source verification now covers PPTX at service, presentation,
  repository, API, restart, owner-isolation, model and permanent-deletion
  boundaries. DOCX, spreadsheet and DICOM names remain refused. Audit payloads
  contain only descriptors, not notes or extracted text.
- Existing `python-pptx` 1.0.2 (MIT), lxml 6.1.1 (BSD-3-Clause) and Pillow
  12.3.0 (MIT-CMU) were reused in memory; no dependency or system tool was
  installed. The native image subprocess retains its no-write/no-network macOS
  sandbox and fail-closed behaviour.
- Focused verification: `venv/bin/python -m pytest -q
  app/tests/test_pptx_sources.py app/tests/test_ocr_review.py
  tests/test_evidence_provenance.py --tb=short` — **107 passed, 6 warnings**.
  Final provider-free suite: `venv/bin/python -m pytest -q app/tests tests
  -ra --tb=short` — **409 passed, 2 skipped, 6 warnings**. Ruff, Python
  compilation, dependency consistency, bundled-Node JavaScript syntax and diff
  whitespace checks also passed.
  Real native synthetic PPTX evaluation accepted one clean text image at slide
  2 and refused a possible name and schematic face; this tiny constructed set
  is not an anonymisation or detector-accuracy claim.
- Browser execution remains unavailable on macOS 10.15 and must not be counted
  as verified. No external provider, professional document, patient data,
  Streamlit edit or human validation was used.
- Implementation commit present locally during handoff: `f699481`; final
  documentation/correction commit and publication are recorded by Git history.
- Product-owner decision: **05.1 approved on 2026-09-17.** This approves the
  documented restricted slice only; it is not full phase 05 approval, scientific
  validation, an anonymisation guarantee or approval for professional data.
- Next exact action: execute 05.2 only after separate authorisation. Retain
  PDF/PPTX extracted images and tables with original locations, dates,
  rights/provenance and uncertainty review. Do not begin 05.3.
- Product-owner phase 05 gate approval: pending.


## Current session handoff — 05.2 (2026-09-17)

- **05.2 implemented for the restricted subset described in
  [05.2 evidence](05.2-asset-review-evidence.md), explicitly approved by the
  product owner on 2026-09-17.** Starting HEAD was `cfc7dde`, matching the authorised
  resumption point; no initial modifications/untracked files were present.
  Implementation initially ended without a commit; the product owner subsequently
  authorised committing and publishing the implementation and approval record.
- Images and canonical table cells now remain in private source records with
  original/derivative hashes, occurrence identities and page/slide rectangles.
  Date evidence stays attached to the original source. No bibliographic data
  is invented. Attributable metadata candidates and explicit uncertainty states
  accompany a local owner-authenticated review with append-only corrections.
- Review and legacy-inventory enrichment are atomic with linked Project
  invalidation/audit. Concurrent or fabricated confirmations and substituted
  bytes/locations are rejected. Pending assets block scientific/model use of
  the source; the derivatives themselves are never automatic textual evidence.
  Existing OCR review remains a separate requirement. Restart, removal,
  permanent deletion and owner isolation retain their existing authority.
- PDF review renders the original region. PPTX review provides original
  embedded bytes/native cells and exact shape location plus original download;
  it does not reproduce full-slide rendering. PDF table detection is limited
  to simple aligned native-text columns; mixed PDF surfaces, vector/grid or
  complex tables and opaque objects remain outside the qualified subset.
- Full final command: `venv/bin/python -m pytest -q app/tests tests -ra
  --tb=short` — **446 passed, 2 skipped, 6 warnings** (92.52 seconds).
  Focused command: `venv/bin/python -m pytest -q
  app/tests/test_source_assets.py app/tests/test_ocr_review.py
  app/tests/test_pptx_sources.py --tb=short` — **134 passed, 6 warnings**;
  the later API-query privacy regression is included in the final full suite.
- Real native command: `venv/bin/python -m app.tests.evaluate_assets_native`
  — **passed**, five synthetic probes: PPTX clean text image accepted, possible
  name and schematic face refused, PDF image and native table retained with
  verified hashes and original-region previews. Containing-sandbox attempts
  failed closed; approved execution succeeded while preserving the native
  helper's no-write/no-network sandbox. No detector accuracy, anonymisation,
  visual-fidelity or scientific-validity guarantee follows from these probes.
- Ruff, compilation, dependency consistency, bundled-Node syntax and final
  whitespace/diff review: see the final verification record below.
- Development failures were resolved, including false PDF-table detections,
  automatic image filenames misread as captions and invalid-query text echoed
  in API validation errors. No final test failure remains. Two existing
  browser tests were **skipped** because macOS 10.15 cannot run the required
  Chromium. The new browser review flow, screenshots and product-owner manual
  validation remain **not performed**; no pass is inferred from API tests.
- No dependency/system tool was installed. Existing package licences and
  in-memory processing were checked. No professional data, patient case,
  external provider or Streamlit change was used. Theme/template selection is
  unaffected, and 05.3's old-deck warning/reuse workflow was not implemented.
- Product-owner decision: **05.2 approved on 2026-09-17** for the documented
  restricted subset. This records acceptance of the handoff; it does not claim
  that the browser/manual checklist was executed, establish scientific validity
  or guarantee anonymisation. Professional data remains forbidden.
- Next exact action: **05.3**, after separate explicit implementation
  authorisation: separate evidence import from explicit template reuse and
  surface the FR-18 warning for old decks without a supplied primary reference.
  The current request authorises the 05.2 commit/push and a 05.3 prompt only.
  The complete phase 05 gate remains **pending**.

### Final static verification record

All commands below exited with status 0 after the final implementation changes:

- `venv/bin/ruff check app tests streamlit_app.py main.py` — passed.
- `venv/bin/python -m compileall -q app streamlit_app.py main.py` — passed.
- `venv/bin/python -m pip check` — no broken requirements. Pip warned that its
  user cache was unavailable and disabled it; nothing was installed.
- `venv/lib/python3.12/site-packages/playwright/driver/node --check
  app/interfaces/web/app.js` — passed (syntax only, not browser execution).
- `git diff --check` — passed. Reviewed tracked diff and the four new files;
  final scope is 20 changed/new files, listed in the evidence report.

The final full suite includes the new asset-budget and safe-query-error tests.
Subsequent edits only clarified browser labels/candidate display and documented
results; JavaScript syntax and static checks were rerun afterwards.
