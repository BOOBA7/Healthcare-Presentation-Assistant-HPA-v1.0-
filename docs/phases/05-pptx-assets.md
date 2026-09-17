# Phase 05 — PowerPoint evidence and extracted visuals

Status: 05.1 approved by the product owner on 2026-09-17. Phase 05 gate
approval remains pending; 05.2 and 05.3 have not started.

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

## Session handoff

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
