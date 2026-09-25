# Phase 09 — Themes, layouts and supplied visuals

Status: Planned. Implementation and product-owner gate approval: pending.

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

- Current slice: 09.1 completed locally; product-owner review pending. No commit created.
- Result/files: HPA themes, finite colour palettes and explicitly imported local PPTX templates now persist through the existing Project aggregate and SQLite repository. Deterministic repository/API/use-case gates expose selection only after Blueprint approval, close it when slide generation starts, and require an explicit style before generation. The browser no longer offers evidence-library PPTX files as styles; evidence import and local-template selection remain separate actions.
- Checks/results: focused 09.1 selection/gate tests **8 passed**; one affected provider-free regression pass **31 passed, 6 warnings**. The complete legacy `app/tests/test_pptx_roles.py` run produced **19 passed, 2 unrelated failures** in older asset/export expectations; the 09.1 subset passed. Ruff on modified Python files, `compileall -q app`, and `git diff --check` passed. Node was unavailable, so `node --check` was not run.
- Decisions/blockers: palettes are a finite enum (`theme`, `teal`, `blue`, `warm`) and affect deterministic PPTX export. Style selection is persisted as an explicit boolean rather than inferred from the default theme. No 09.2 layout/visual work or additional 09.3 provenance/invalidation work was added.
- Next action: review and explicitly approve 09.1; do not start 09.2 without separate authorisation.
- Product-owner gate approval: pending; record date, scope and explicit decision.
