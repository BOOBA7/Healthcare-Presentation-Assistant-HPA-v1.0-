# Phase 09 — Themes, layouts and supplied visuals

Status: In progress. 09.1 approved by the product owner on 2026-09-25; 09.2 approved on 2026-09-25; 09.3 completed locally and review pending.

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

- Current slice: 09.3 completed locally; product-owner review pending. No commit created and no later phase was started.
- Result/files: style, layout and visual provenance now persist as deterministic server-issued receipts over the exact theme/template identity, supplied values, or intact reviewed asset hashes. Authenticated style/visual actions retain optimistic concurrency and atomic audit; direct visual mutation or stale receipts are refused. Later style changes and visual changes invalidate affected slide, global slide and final approvals, then survive repository restart.
- Checks/results: focused provider-free 09.3 tests **3 passed** (late-style and final invalidation/restart, supplied-value provenance/invalidation, concurrency/refusal/tamper). Targeted Ruff, `compileall -q app`, and `git diff --check` passed. Node was unavailable, so `node --check` was not run. No full suite was run.
- Decisions/blockers: provenance stores identifiers and SHA-256 receipts, not copied image bytes or invented values; the existing reviewed-asset gate remains authoritative. `app/core/config.py` is a concurrent user modification and was not touched. Browser checks remain pending because Node is unavailable.
- Next action: review and explicitly approve 09.3; do not start phase 10 without separate authorisation.
- Product-owner gate approval: 09.1 and 09.2 approved 2026-09-25; 09.3 pending.
