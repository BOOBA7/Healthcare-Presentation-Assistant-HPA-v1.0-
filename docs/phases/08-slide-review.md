# Phase 08 — Supported generation, editing and speaker notes

Status: Planned. Implementation and product-owner gate approval: pending.

## Outcome and scope

Supported generation, editing and speaker notes. Requirements: FR-14–FR-17; FR-18; PRD §11. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 07 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/application/use_cases/generate_slides.py`
- `app/domain/models/slide.py`
- `app/domain/value_objects/speaker_note.py`
- `app/application/services/workflow_policy.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **08.1** — Generate supported claims and notes with local slide blockers, without inventing values or resolving conflicts silently.
2. **08.2** — Allow direct edits, reformulation, deletion, comments and review in any order; mark unsourced medical drafts as user-provided/source-missing and prevent scientific approval.
3. **08.3** — Invalidate affected approvals on content/data/source/visual changes; record actor/time and enforce global export rules for every content origin.

## Acceptance criteria

- [ ] One blocked slide does not prevent reviewing others but prevents export.
- [ ] Manual authorship never bypasses medical evidence rules; nonmedical thank-you content can be unsourced.
- [ ] Notes have traceable evidence and human approval separate from visible content.
- [ ] Provider failures preserve work; source changes/removal invalidate affected content and final approval.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: 08.2 completed locally; review pending. No commit.
- Result/files: direct edit, accepted reformulation, independent comments, deletion and out-of-order review are exposed through authenticated API/UI actions. `Slide` persists an explicit medical/nonmedical classification and the exact `user-provided, source missing` warning; both the use case and repository forbid scientific approval of such medical drafts while allowing declared nonmedical content. Content and evidence-backed speaker-note approvals are separate, authenticated and audited. Changes are in `app/application/use_cases/workflow_steps.py`, `app/domain/models/slide.py`, `app/interfaces/api/main.py`, `app/interfaces/storage/user_session_repository.py`, `app/interfaces/web/app.js`; provider-free coverage extends `tests/test_supported_slide_generation.py` with one compatibility update in `tests/test_end_to_end_deterministic_workflow.py`.
- Checks/results: focused tests 7 passed. Affected regressions initially reported 46 passed/3 failed for newly required classification; after the safe-default/explicit-nonmedical correction, the three failures passed on targeted rerun. Ruff on modified Python files, `compileall -q app`, and `git diff --check` passed. JavaScript syntax check was not run because `node` is unavailable in this environment.
- Decisions/reservations: classification is explicit at the API/UI boundary and defaults conservatively to medical only for internal legacy callers. Reformulation persists human-accepted text without a provider call or implied evidence. No browser screenshot or live-provider call was performed. Approval invalidation beyond the edits handled here remains 08.3.
- Next action (08.3 only after explicit authorisation): invalidate affected approvals on every content/data/source/visual change, record actor/time consistently, and enforce global export rules for every content origin.
- Product-owner gate approval: pending; record date, scope and explicit decision.
