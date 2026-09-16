# Phase 10 — Faithful preview, PowerPoint and PDF

Status: Planned. Implementation and product-owner gate approval: pending.

## Outcome and scope

Faithful preview, PowerPoint and PDF. Requirements: FR-20, FR-21; FR-17, FR-18, FR-22; PRD §§9,14. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 09 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/application/use_cases/export_powerpoint.py`
- `app/interfaces/api/main.py`
- `app/interfaces/web/`
- `tests/test_end_to_end_deterministic_workflow.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **10.1** — Validate a local macOS-compatible rendering/PDF approach on a small fixture and document dependencies and unavailable-tool errors.
2. **10.2** — Render preview and both exports from the same approved revision, with all structural slides, editable PPTX text, approved PPTX notes, visible markers and cited-resource reference slides.
3. **10.3** — Enforce identical deterministic export gates, close edit/export races and clean internal temporary outputs on success/failure/Project deletion.

## Acceptance criteria

- [ ] Both formats block missing resource, Agenda, Blueprint, claim, slide, notes or final approval and any privacy/evidence blocker.
- [ ] Preview exposes order, missing elements, clipping, overlap, references and theme defects on representative 10–20-slide decks.
- [ ] PPTX is editable with speaker notes; PDF is complete/readable. Inspect generated files and compare rendered output manually on macOS.
- [ ] A concurrent edit cannot release stale output; external user copies remain untouched.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: 10.1, not started.
- Changes and implementation commits: none.
- Checks/results: not run for this phase.
- Decisions/blockers: inspect current implementation; no technology choice is preapproved by this plan.
- Next action: verify prerequisites and execute the authorised slice.
- Product-owner gate approval: pending; record date, scope and explicit decision.
