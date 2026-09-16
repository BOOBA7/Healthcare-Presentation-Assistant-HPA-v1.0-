# Phase 05 — PowerPoint evidence and extracted visuals

Status: Planned. Implementation and product-owner gate approval: pending.

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

- Current slice: 05.1, not started.
- Changes and implementation commits: none.
- Checks/results: not run for this phase.
- Decisions/blockers: inspect current implementation; no technology choice is preapproved by this plan.
- Next action: verify prerequisites and execute the authorised slice.
- Product-owner gate approval: pending; record date, scope and explicit decision.
