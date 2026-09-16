# Phase 06 — Claim evidence, coverage and resource discussion

Status: Planned. Implementation and product-owner gate approval: pending.

## Outcome and scope

Claim evidence, coverage and resource discussion. Requirements: FR-09, FR-10, FR-18, FR-19; PRD §§6,11. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 05 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/application/validators/evidence_provenance_validator.py`
- `app/application/validators/response_citation_validator.py`
- `app/application/services/production_evidence_gate.py`
- `app/application/use_cases/discuss_resources.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **06.1** — Introduce stable claim-to-evidence links for text/values with resource title, page/source slide, section, exact passage and supplied DOI/link; migrate legacy slide-level references without assuming claim verification.
2. **06.2** — Assess topic, objectives, audience, depth and slide-count coverage before Agenda creation and show missing evidence.
3. **06.3** — Show conflicting positions with dates/locations/passages without choosing scientific superiority; require explicit validated transfer from chat into planning.

## Acceptance criteria

- [ ] Wrong resource/location/excerpt cannot pass; an authentic but irrelevant quotation cannot silently become approved support. Distinguish deterministic provenance checks from human semantic review.
- [ ] Unsupported factual answers are refused; every supported factual answer is cited and chat cannot silently change workflow.
- [ ] Coverage failures explain missing resources; conflicts retain both positions.
- [ ] Claim markers expose readable evidence details and preserve the old-PPTX warning.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: 06.1, not started.
- Changes and implementation commits: none.
- Checks/results: not run for this phase.
- Decisions/blockers: inspect current implementation; no technology choice is preapproved by this plan.
- Next action: verify prerequisites and execute the authorised slice.
- Product-owner gate approval: pending; record date, scope and explicit decision.
