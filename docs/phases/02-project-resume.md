# Phase 02 — Dashboard, context and recovery

Status: 02.1, 02.2 and 02.3 implemented and product-owner approved (2026-09-15), with Node/browser checks unverified.

## Outcome and scope

Dashboard, context and recovery. Requirements: FR-02, FR-03; NFR-02; PRD §7. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 01 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/interfaces/api/routers/projects.py`
- `app/interfaces/storage/user_session_repository.py`
- `app/interfaces/web/`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **02.1** — Complete topic, audience, duration, slide count, objectives and special instructions, with audited professional-scope and multidisciplinary confirmation.
2. **02.2** — Show dashboard count/list, workflow, purpose/context, theme/style, resource counts/types, recent actions and last successful save.
3. **02.3** — Autosave material actions, show next allowed action/blockers and preserve restart, provider-failure and concurrent-write protections.

## Acceptance criteria

- [ ] Restart restores context and progress; failed saves never appear successful.
- [ ] Stale jobs cannot overwrite newer human work.
- [ ] Missing required context or scope blocks dependent actions; dashboard resume works in FR/EN.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Slice 02.1 evidence

See [02.1 context implementation and verification](02.1-presentation-context-evidence.md)
for decisions, changed files, requirement mapping and actual check results.
The phase-wide acceptance checkboxes remain open: 02.1 covers context recovery,
refusals and attestation, while dashboard and general recovery work are later slices.

## Slice 02.2 evidence

See [02.2 dashboard implementation and verification](02.2-dashboard-evidence.md).
It implements the persisted Project dashboard and explicit resume path. It does
not claim the phase-wide autosave/recovery work reserved for 02.3.

## Slice 02.3 evidence

See [02.3 durable actions and recovery](02.3-recovery-evidence.md). It records
the transaction, revision and provider-failure protections already exercised by
the application and adds a server-owned next-action display to `/app`.

## Session handoff

- Current slice: **02.3 implemented**; 02.1 through 02.3 were explicitly authorised.
- Changes: 02.1 complete context/attestation and deterministic boundaries;
  02.2 persisted dashboard cards and explicit FR/EN resume path; 02.3 exposes
  the server-owned next allowed action and blockers. Existing SQLite transaction,
  provider-failure persistence and revision checks are retained.
- Decisions, file list and proofs: [02.1 evidence](02.1-presentation-context-evidence.md)
  and [02.2 evidence](02.2-dashboard-evidence.md).
- Checks: 02.1 focused suite **35 passed**; 02.2 focused suite **3 passed**;
  02.3 focused suite **48 passed, 6 warnings**; final suite **156 passed, 1
  skipped, 6 warnings**. Python compilation, Ruff and diff whitespace passed.
- Not verified: JavaScript syntax (Node unavailable, exit 127); actual browser
  rendering (Chromium test skipped on macOS 10.15); no screenshots or remote CI.
  These checks are not successful and remain open from phase 01 as well.
- Prerequisite decision: phase 01 explicitly approved on 2026-09-15 with
  Node/browser reservations. Neither full PRD compliance nor scientific validation.
- Git: HEAD `dff973f`; no implementation commit or staged changes. Existing user
  modifications preserved; incremental source diff reviewed against a pre-edit snapshot.
- Limits: human scope declarations are assertions, not proof of competence or
  automatic multidisciplinary classification. Professional and patient-case data
  remain forbidden. General context editing/invalidation is not added here.
- Next exact slice: **03.1**, extensible source/location/asset metadata,
  backward-compatible migration and fail-closed in-memory screening.
- Product-owner phase 02 gate approval: approved by the owner on 2026-09-15 to
  continue. The documented Node/browser reservations remain open. No human
  pilot, scientific or external review is recorded as obtained.
