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

- Current slice: 08.3 completed locally; phase review pending. No commit.
- Result/files: slide and speaker-note approvals now persist authenticated actor/time. Content, claim/data, source-set and visual/style changes invalidate affected slide/final approvals at use-case and SQLite persistence boundaries. One deterministic export policy is enforced during slide-set approval, final approval, API download and PowerPoint generation for AI, edited and authored content; medical human content needs approved claim evidence, every slide needs audited approval, and every non-empty note needs separate audited approval.
- Checks/results: focused provider-free file 7 passed; affected regression pass initially 58 passed/5 failed, then all five corrected cases passed; closest invalidation test passed again. Ruff on all modified Python files, `compileall -q app`, and `git diff --check` passed. Node/JavaScript check was unavailable because `node` is not installed.
- Decisions/reservations: legacy AI slides retain their existing exact-provenance export path; this does not let edited/authored medical content inherit AI evidence. No provider, browser or external source was used. Product-owner gate approval remains pending.
- Next action: review and explicitly approve phase 08; do not start phase 09 automatically.
