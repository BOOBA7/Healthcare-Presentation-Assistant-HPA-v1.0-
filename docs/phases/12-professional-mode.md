# Phase 12 — Verified professional local execution

Status: Planned. Implementation and product-owner gate approval: pending.

## Outcome and scope

Verified professional local execution. Requirements: NFR-03, NFR-04; FR-08; PRD §§6.6,12,17. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 11 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/ai/llm/llm.py`
- `app/core/config.py`
- `app/interfaces/storage/user_session_repository.py`
- `app/application/services/patient_case_privacy.py`
- `ADR.md`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **12.1** — Inventory Mac hardware and evaluate local model candidates with public/synthetic fixtures before selecting supported requirements.
2. **12.2** — Enforce no-egress execution across extraction/models/rendering/telemetry; encrypt sensitive databases, originals, assets and temporary content with documented key handling, migration and recovery.
3. **12.3** — Verify privacy controls and explicit patient-case anonymisation confirmation; record required competent external reviews before enabling professional data.

## Acceptance criteria

- [ ] Network-denied end-to-end execution succeeds; outbound attempts are blocked without external fallback.
- [ ] Encryption/restart/key-unavailable/migration tests pass without raw-content leaks or admin/support content access.
- [ ] Real-data capability stays blocked until technical verification and required competent reviews from PRD §12 pass.
- [ ] Document hardware/model limitations and review evidence without claiming regulatory certification or guaranteed anonymisation.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: 12.1, not started.
- Changes and implementation commits: none.
- Checks/results: not run for this phase.
- Decisions/blockers: inspect current implementation; no technology choice is preapproved by this plan.
- Next action: verify prerequisites and execute the authorised slice.
- Product-owner gate approval: pending; record date, scope and explicit decision.
