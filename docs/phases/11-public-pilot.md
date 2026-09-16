# Phase 11 — Measured public-resource pilot

Status: Planned. Implementation and product-owner gate approval: pending.

## Outcome and scope

Measured public-resource pilot. Requirements: NFR-05, NFR-06; PRD §§4,11,14,17,18. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 10 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `docs/EVALUATION.md`
- `docs/HCP_EVALUATION.md`
- `docs/HCP_HOW_TO_USE_FR.md`
- `tests/test_observability.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **11.1** — Record separate extraction/OCR, evidence analysis, Blueprint, slides, individual regeneration and export durations without raw-content telemetry.
2. **11.2** — Prepare observed public-resource pilot with one professor on the owner’s MacBook; separate active work, app manipulation, reading/review, waiting and post-export correction.
3. **11.3** — Record actual interventions, blockers/recoveries, regenerations, citation rejections, major rewrites and reuse intent; set performance targets from observations.

## Acceptance criteria

- [ ] Report every PRD §14 criterion: complete PPTX/PDF, under eight hours active work, all medical claims traceable, all slides approved, at least 90% without major rewrite and explained reuse intent.
- [ ] Invented claims, incorrect citations, privacy incidents, data loss and unapproved medical exports are critical failures.
- [ ] Unperformed human observations remain pending; never invent results or claim independent scientific review or professor-machine installation validation.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: 11.1, not started.
- Changes and implementation commits: none.
- Checks/results: not run for this phase.
- Decisions/blockers: inspect current implementation; no technology choice is preapproved by this plan.
- Next action: verify prerequisites and execute the authorised slice.
- Product-owner gate approval: pending; record date, scope and explicit decision.
