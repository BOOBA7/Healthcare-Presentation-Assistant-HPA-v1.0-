# Phase 07 — Agenda and Blueprint approval

Status: Planned. Implementation and product-owner gate approval: pending.

## Outcome and scope

Agenda and Blueprint approval. Requirements: FR-11, FR-12; FR-09; PRD §§7,9. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 06 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/domain/models/agenda.py`
- `app/domain/models/blueprint.py`
- `app/ai/schemas/blueprint_schema.py`
- `app/application/services/workflow_policy.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **07.1** — Gate Agenda generation on evidence coverage and resource validation; support editable high-level sections and approval.
2. **07.2** — Complete Blueprint items with slide number, title, objective, message, sources, planned visual, origin and validation state.
3. **07.3** — Require item review and downstream invalidation; represent normal deck structure and resolve structural-slide counting against target count.

## Acceptance criteria

- [ ] Direct API calls cannot bypass Agenda approval, Blueprint approval or per-item review.
- [ ] Agenda/source changes invalidate dependent approvals.
- [ ] Title, Agenda, conclusion, references and thank-you slides have explicit review representation; conclusion introduces no new unsupported assertion.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: **07.2 implemented; review/approval pending.** 07.1 was
  explicitly approved on 2026-09-24. No commit created; 07.3 was not started.
- Delivered: every generated Blueprint item now carries its slide number,
  title, objective, key message, validated supporting-resource IDs, planned
  visual, content origin and validation state. Unknown generated or edited
  resource IDs are refused. `/app` displays and edits the complete item; edits
  retain the original AI snapshot and existing downstream invalidation.
- Main files: Blueprint domain/schema/mapper/prompt/build use case, Blueprint
  edit API/use case, `/app`, and focused Blueprint tests.
- Checks: focused Blueprint/workflow/prompt/Agenda/API/end-to-end/resource
  regressions — **58 passed, 6 warnings**. Ruff on changed
  Python, Python compilation and `git diff --check` passed. `node` is absent,
  so JavaScript syntax and browser/screenshots were not run; no live provider
  call was made.
- Working tree: started clean on `main` synchronized with `origin/main`; only
  the uncommitted 07.2 files listed above and this handoff are changed.
- Next exact slice: after explicit 07.2 approval, 07.3 may require item review,
  downstream invalidation and structural-slide counting. Do not start it
  automatically.
- Product-owner phase gate approval: pending; record only an explicit decision.
