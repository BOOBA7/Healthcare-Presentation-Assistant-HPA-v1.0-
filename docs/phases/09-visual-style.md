# Phase 09 — Themes, layouts and supplied visuals

Status: In progress. 09.1 approved by the product owner on 2026-09-25; 09.2 completed locally and review pending.

## Outcome and scope

Themes, layouts and supplied visuals. Requirements: FR-13; FR-14, FR-16; PRD §9. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 08 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/application/use_cases/export_powerpoint.py`
- `app/domain/enums/presentation_theme.py`
- `app/interfaces/web/`
- `app/domain/models/slide.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **09.1** — Offer HPA themes, local templates and colours after Blueprint approval and before generation.
2. **09.2** — Support layout selection and supplied-image replacement/placement; build charts, tables and diagrams exclusively from supplied values.
3. **09.3** — Persist style and visual provenance; invalidate visual/final approval on style or asset change.

## Acceptance criteria

- [ ] No generated medical images or extrapolated values are introduced.
- [ ] Template evidence and style reuse remain distinct explicit actions.
- [ ] Representative layouts are legible, coherent, preserve reference markers and expose excessive text for correction.
- [ ] Visual changes cannot leave stale approvals valid.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: 09.2 completed locally; product-owner review pending. No commit created and 09.3 was not started.
- Result/files: four persisted slide layouts now place reviewed Project images or deterministic tables, bar/line charts and diagrams. Structured server models accept only supplied values; medical-image generation and missing-value completion have no supported input path. Image selection is restricted to intact, user-reviewed assets in selected Project resources. Changes autosave transactionally with optimistic concurrency and audit, survive restart, invalidate slide/global approvals, and render into PPTX; the `/app` review UI supports replacement and placement.
- Checks/results: focused provider-free 09.2 tests **3 passed** (persistence/invalidation, refusal/concurrency, exact supplied table values). Targeted 09.1 style regression **1 passed**; the known legacy export test still fails before rendering on the pre-existing audited-approval gate (`SLIDE_APPROVAL_REQUIRED`). Ruff on modified 09.2 Python files, `compileall -q app`, and `git diff --check` passed. Node was unavailable, so `node --check` was not run. No full suite was run.
- Decisions/blockers: visual kinds and layouts are finite; chart/table/diagram payloads reject incomplete dimensions and extra fields, while images reference canonical reviewed assets rather than storing a new copy. `app/core/config.py` is a concurrent user modification and is excluded from this slice. Browser/artifact visual inspection remains pending because Node is unavailable.
- Next action: review and explicitly approve 09.2; do not start 09.3 without separate authorisation.
- Product-owner gate approval: 09.1 approved 2026-09-25; 09.2 pending.
