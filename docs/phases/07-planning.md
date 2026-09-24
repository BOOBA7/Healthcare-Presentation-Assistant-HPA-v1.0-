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

- Current slice: **07.1 implemented; review/approval pending.** No commit created.
- Delivered: a dedicated evidence-grounded Agenda schema/prompt/chain and async
  `/agenda/jobs` action; resource validation plus a current sufficient coverage
  assessment are enforced before generation. It creates editable high-level
  sections only. Agenda editing/approval is exposed in `/app`; Blueprint calls
  now refuse until the Agenda is approved, and Agenda edits reset dependent
  aggregate approvals. Existing source invalidation still clears Agenda,
  Blueprint, coverage and downstream content.
- Main files: `app/ai/{chains,prompt_builders,schemas}/agenda_*`,
  `app/application/use_cases/build_agenda.py`, workflow use cases/view, job/API
  routes, `/app`, and focused provider-free tests.
- Checks: focused Agenda/coverage/workflow/API/end-to-end regressions — **44
  passed, 6 warnings**; final end-to-end scenario — **1 passed, 6 warnings**.
  Ruff (changed Python files), Python compilation and `git diff --check`
  passed. JavaScript syntax was not checked because `node` is absent from the
  current PATH; browser/screenshots and live-provider calls were not run.
- Working tree: pre-existing modified/untracked user work was preserved; the
  repository remains on `main`, one commit ahead of `origin/main`.
- Next exact slice: after explicit 07.1 approval, 07.2 may complete Blueprint
  item fields. Do not start 07.2 automatically.
- Product-owner gate approval: pending; record date, scope and explicit decision.
