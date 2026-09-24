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

- Current slice: 08.1 completed locally; review pending. No commit.
- Result/files: supported slide and separate speaker-note claim provenance, deterministic missing-value/conflict refusal, local blockers, restart-safe provider recovery, API bypass guard and visible review details in `app/ai`, `app/application`, `app/domain`, `app/interfaces`; provider-free evidence in `tests/test_supported_slide_generation.py`.
- Checks/results: affected regression set 64 passed; final focused set 15 passed; Ruff passed on modified Python files; `compileall app`, bundled Node `--check app/interfaces/web/app.js`, and `git diff --check` passed.
- Decisions/reservations: provenance verification is not scientific approval; speaker-note approval remains deliberately pending. No browser screenshot or live-provider call was performed. Existing legacy slide citations remain readable/exportable but new generation requires claim-level evidence.
- Next action (08.2 only after explicit authorisation): direct edits/reformulation/deletion/comments in any order, explicit source-missing medical drafts, and authenticated separate content/note review actions.
- Product-owner gate approval: pending; record date, scope and explicit decision.
