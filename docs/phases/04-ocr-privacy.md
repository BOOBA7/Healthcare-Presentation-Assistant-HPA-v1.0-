# Phase 04 — Scanned PDF, images and extraction review

Status: Planned. Implementation and product-owner gate approval: pending.

## Outcome and scope

Scanned PDF, images and extraction review. Requirements: FR-04 (scans/PNG/JPEG), FR-06, FR-08; FR-05, FR-07. [PRD](../PRD.md) is authoritative.

Prerequisite met: phase 03 explicitly approved on 2026-09-16, with Node/browser
checks still unverified. See its [current handoff](03-source-lifecycle.md).

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/application/services/patient_case_privacy.py`
- `app/application/use_cases/extract_pdf_resource.py`
- `tests/test_patient_case_privacy.py`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **04.1** — Evaluate local OCR and text/image/metadata screening with synthetic fixtures; screen names, contacts, identifiers, identifying dates, faces and risky combinations before durable acceptance or model calls.
2. **04.2** — Support scanned PDF, PNG and JPEG with original-region coordinates, date evidence and safe temporary-file cleanup.
3. **04.3** — Display uncertain values beside originals and require confirmation/correction; preserve extracted value, correction, actor, time and user-confirmed provenance.

## Acceptance criteria

- [ ] Possible identifiers or incomplete screening block processing; rejected input leaves no durable raw content or raw logs.
- [ ] Unconfirmed uncertain values cannot support generation and accepted corrections remain linked to original regions after restart.
- [ ] Every format obeys the date gate; limitations of automated anonymisation are shown. Patient cases remain disabled in prototype mode.
- [ ] Record observed false positives/negatives; synthetic fixture success is not a guarantee of anonymisation.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Session handoff

- Current slice: 04.1, not started.
- Changes and implementation commits: none.
- Checks/results: not run for this phase.
- Decisions/blockers: inspect current implementation; no technology choice is preapproved by this plan.
- Next action: start a fresh chat with [the 04.1 prompt](04.1-start-prompt.md),
  verify prerequisites and execute only that authorised slice.
- Product-owner gate approval: pending; record date, scope and explicit decision.
