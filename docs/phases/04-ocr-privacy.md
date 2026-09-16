# Phase 04 — Scanned PDF, images and extraction review

Status: Approved by the product owner on 2026-09-16 for the restricted supported subset, with explicit language/format/privacy and browser reservations.

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

- [x] Possible identifiers or incomplete screening block processing; rejected input leaves no durable raw content or raw logs.
- [x] Unconfirmed uncertain values cannot support generation and accepted corrections remain linked to original regions after restart.
- [x] Every format obeys the date gate; limitations of automated anonymisation are shown. Patient cases remain disabled in prototype mode.
- [x] Record observed false positives/negatives; synthetic fixture success is not a guarantee of anonymisation.

Checked criteria have automated evidence for the supported subset, not full PRD
coverage or human approval. The image path is limited to clean monochrome English
text and inspectable date metadata; unsupported surfaces fail closed. See the
[current evidence and limitations](04.3-extraction-review-evidence.md).

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Current session handoff — phase 04 implementation, 2026-09-16

- Owner authorisation: “continue pour terminer la phase 4”. This supersedes
  earlier slice-only stop instructions; it does not grant phase approval.
- **04.1–04.3 implemented for the restricted subset.** Native OCR + restrictive
  pixel/name controls; PDF/PNG/JPEG originals/regions; authenticated original-side
  confirmation/correction; actor/time/history; effective text, provenance and
  cross-Project invalidation. No general image or professional-data support.
- [Final evidence, commands, changed files and limitations](04.3-extraction-review-evidence.md).
- Real native five-fixture gate: TP 4, TN 1, FP 0, FN 0. The face is rejected
  by residual pixels, not detected by Vision. Separate public-heading false
  positive and noisy-JPEG refusal remain documented. No anonymisation guarantee.
- Real PNG/JPEG/scanned-PDF fixtures with scientific metadata retain originals
  and coordinates and remain blocked for generation until explicit review.
- Final suite: **325 passed, 2 skipped, 6 warnings**, exit 0 (49.15 s),
  with `venv/bin/python -m pytest -q app/tests tests -ra`. Ruff, compilation,
  dependency consistency and diff whitespace passed. Native evaluation exited
  0 and verified the three formats plus pending-generation refusal.
- JavaScript syntax: **passed**, actually executed with bundled Node v22.18.0.
  Earlier unperformed Node checks are not retroactively counted as successes.
- Browser: **two skipped** on macOS 10.15 (installed Chromium requires macOS 12).
  No screenshots, supported-browser runtime or remote CI results obtained.
- Local compiler output ignored; no system dependency installation, model-provider
  call, real professional data, Streamlit edit, staging or commit. HEAD `ee1c87c`;
  earlier work and `docs/GRILL_ME_HPA.md` preserved.
- Product-owner gate: **approved explicitly on 2026-09-16** for the documented
  restricted subset. This does not remove the browser, scientific-validation or
  anonymisation reservations.
- **Next planned slice: 05.1**, in a fresh conversation. Browser verification on
  a supported environment remains outstanding; 05.1 has not started.

## Historical session handoff — 04.2, 2026-09-16

- Authorisation: “continue 04.2”; resumed after interruption with “reprends”.
- **04.2 partial, qualification blocked.** Memory-only raster pipeline, original
  coordinates/date metadata, typed API download and unconfirmed-OCR blockers
  implemented. Positive persistence paths tested with explicit engine doubles.
- [04.2 evidence, files and commands](04.2-raster-import-evidence.md).
- Apple Vision was found locally and exercised under no-write/no-network
  confinement. English only; observed confidence 0.5. Five real synthetic
  screening trials: TP 2, TN 1, FP 0, FN 2 (unlabelled name and schematic face).
- Production image screening remains unconditionally refused; compiling the
  adapter does not enable it. Scanned PDF/PNG/JPEG are not generally accepted.
  The final native evaluator asserts that all three imports stay blocked.
- Final checks: **305 passed, 1 skipped, 6 warnings** with
  `venv/bin/python -m pytest -q app/tests tests -ra` (115.32 s). Ruff,
  compilation, dependency consistency and diff whitespace passed. Final native
  evaluation exited 0, reproduced the two misses and verified all three
  production imports remain blocked.
- JavaScript syntax remains unverified; browser skipped on macOS 10.15.
  No human approval, scientific/privacy certification, remote CI or model call.
- Git: HEAD `ee1c87c`; 04.1 edits and owner untracked file preserved. No commit.
- **Next exact work: finish 04.2 qualification** before enabling raster imports;
  resolve the known image/face detection misses and language/date limitations.
  Do not begin 04.3 or mark phase 04 approved.

## Historical 04.1 handoff

- Current slice: **04.1 evaluation delivered**, with explicit OCR/face capability
  blockers; no complete FR-08 or anonymisation assurance claimed.
- Changes, shortlist/licences, surfaces, error measurements, commands and limits:
  [04.1 evidence](04.1-privacy-evaluation-evidence.md).
- Shared text gate strengthened; direct provider multimodal bypass refused;
  unsupported source formats remain refused. Source audit policy is v2.
- Synthetic text evaluation: 7 TP, 3 TN, 1 FP, 3 FN. Six image fixtures refused
  as incomplete; zero real OCR or face-detector trials (engines unavailable).
- Final checks/results: **272 passed, 1 skipped, 6 warnings** with
  `venv/bin/python -m pytest -q app/tests tests -ra`. Ruff, compilation,
  dependency consistency and diff whitespace checks passed.
- JavaScript syntax remains unverified (Node absent); browser remains skipped
  on macOS 10.15. Approval of phases 01–03 does not resolve these reservations.
- HEAD `ee1c87c`; owner untracked `docs/GRILL_ME_HPA.md` preserved. No commit,
  dependency installation, external model call or Streamlit change.
- Next exact planned slice: **04.2**, separately authorised, carrying forward
  real OCR/face qualification and memory-only execution blockers. No work on
  04.2 or 04.3 has started and no new format may be accepted on this evidence.
- Product-owner phase 04 gate approval: pending.
