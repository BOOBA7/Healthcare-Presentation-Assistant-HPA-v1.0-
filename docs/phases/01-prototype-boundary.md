# Phase 01 — Public prototype boundary and local account

Status: Approved by the product owner with Node/browser verification reservations (2026-09-15). Phase implementation 01.1–01.3 complete; outstanding checks remain open.

## Outcome and scope

Public prototype boundary and local account. Requirements: FR-01; NFR-01, NFR-03, NFR-04. [PRD](../PRD.md) is authoritative.

Prerequisite: phase 00 completed with recorded product-owner approval.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `app/interfaces/api/routers/auth.py`
- `app/core/config.py`
- `app/ai/llm/llm.py`
- `app/interfaces/web/`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **01.1** — Enforce public/synthetic-only prototype mode and external-provider disclosure at ingestion and model boundaries; block professional and patient-case material.
2. **01.2** — Remove unauthenticated recovery paths; verify owner-scoped access and localhost defaults.
3. **01.3** — Limit MVP UI to professor and FR/EN; hide retrieval strategy and freeze new Streamlit features.

## Baseline findings to apply

See [phase 00 requirement audit](00-requirement-audit.md), especially AUD-02
and AUD-03. This refinement does not authorise implementation or approve the
phase 00 gate.

- **01.1:** inspect shared ingestion, `get_llm`, synchronous API operations,
  job execution and existing Project resume. Current settings allow external
  OpenAI/Gemini providers and acknowledged patient cases. Establish one server
  policy for public/synthetic prototype use; block professional/patient-case
  requests, including direct API requests and legacy persisted states. Persist
  the required declaration and display external-processing disclosure in `/app`.
  Treat declarations as user assertions, not proof of anonymisation. Test
  allowed synthetic input and refused patient/professional input before storage
  or provider invocation, plus restart and queued-job bypass attempts. Keep
  professional mode unavailable; no new Streamlit UI features.
- **01.2:** remove the unauthenticated reset route, its web action and unsafe
  repository entry point; revise the historical reset-success test. Add direct
  unauthenticated and cross-user attempts for Projects, resources, templates,
  jobs, events and exports. Verify localhost startup and exposure controls.
- **01.3:** limit visible role/language choices to professor and FR/EN and hide
  evidence strategy controls. Preserve backend evidence enforcement. Check
  existing-profile resume rather than assuming all accounts are newly created.
- Preserve passing deterministic workflow/provenance/persistence regressions.
  Do not silently broaden this phase into OCR, claim-level export enforcement
  or professional-mode implementation. Node syntax and browser verification
  need the supported CI environment; local macOS 10.15 skipped the browser test.

## Acceptance criteria

- [x] Direct API calls cannot bypass mode restrictions or reset another account.
- [x] Two synthetic users cannot access each other’s Projects or resources.
- [x] External processing is disclosed in `/app` and professional mode remains disabled.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Slice 01.1 evidence

See [01.1 implementation and verification](01.1-prototype-boundary-evidence.md).
Mode restrictions are tested at direct API, shared ingestion, model and queued
execution boundaries. Disclosure and declaration are implemented in `/app`;
actual browser rendering remains unverified. The combined phase checkboxes
above remain open: reset removal and comprehensive two-user isolation belong
to 01.2, and supported-environment UI verification remains outstanding.

## Slice 01.2 evidence

See [01.2 account-boundary evidence](01.2-account-boundary-evidence.md).
The unauthenticated reset endpoint, UI action and repository method are removed.
Provider-free regression tests cover unauthenticated and cross-user denial for
Projects, resources, templates, jobs, events and exports. The application
launcher and documented command now use a loopback-only host; a configuration
validator rejects network bind addresses. Browser/Node verification remains
unverified on this machine.

## Slice 01.3 evidence

See [01.3 MVP interface-scope evidence](01.3-mvp-interface-scope-evidence.md).
`/app` now registers only the professor persona and exposes FR/EN-only account
and presentation choices. The retrieval strategy is absent from the UI while
the server endpoint and deterministic enforcement remain. Existing non-MVP
profiles and Projects can resume without silent data rewrite; their UI falls
back to English and does not expose their old role/language as a choice.

## Session handoff

- Current slice: **01.3 implemented**; all phase implementation slices are complete. Local Python acceptance
  evidence is complete; JavaScript syntax and browser acceptance are unverified.
- Prerequisite: owner explicitly approved phase 00 audit deliverables on
  2026-09-15 with Node/browser reservations. This is neither full PRD compliance
  nor scientific validation. Decision recorded in phase 00 and the phase index.
- Changes: 01.1 policy/declaration/disclosure boundaries; 01.2 recovery-route
  removal and account isolation; 01.3 professor/FR-EN UI restriction and
  retrieval-control hiding. Evidence: [01.1](01.1-prototype-boundary-evidence.md),
  [01.2](01.2-account-boundary-evidence.md), and
  [01.3](01.3-mvp-interface-scope-evidence.md).
- Checks/results: compilation, Ruff and dependency consistency passed;
  focused 01.3 suite 12 passed, 1 skipped; final full suite **117 passed, 1 skipped,
  6 warnings**. Node command not executable (exit 127). Browser test skipped
  on macOS 10.15; no screenshot, remote CI or live model validation claimed.
  Diff/whitespace review completed; existing user documentation preserved.
- Implementation commits: none. HEAD remains `dff973f`; no staged changes.
- Limits: declarations are user assertions. Explicit text-marker screening
  cannot classify all documents or prove anonymisation; no image/OCR privacy
  assurance. Real professional/patient-case use remains forbidden.
  Legacy patient Projects stay blocked; old undeclared templates require
  reupload. Streamlit receives shared safety restrictions, no new UI features.
- Product-owner decision (2026-09-15): explicitly approved phase 01 and
  authorised continuation to phase 02. Node JavaScript syntax and Chromium
  browser checks remain **unverified**, not successful. This decision is not
  full PRD compliance or scientific validation.
- Next exact slice: **02.1**, in a new focused conversation. No human pilot,
  scientific or external assessment is recorded as obtained.
