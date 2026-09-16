# Phase 00 — Baseline and requirement audit

Status: Audit approved with documented verification reservations on 2026-09-15. Full CI verification remains pending.

## Outcome and scope

Baseline and requirement audit. Requirements: PRD §§15–18; NFR-06. [PRD](../PRD.md) is authoritative.

Prerequisite: none; establish the baseline.

Follow the [execution contract](README.md). Later-phase requirements and deferred PRD scope are outside this phase. Preserve working controls; do not rewrite the application.

## Targeted reading

Read referenced PRD sections and inspect these starting points (not a mandated design):

- `README.md`
- `ADR.md`
- `.github/workflows/ci.yml`
- `tests/`

## Focused implementation slices

One numbered slice per conversation. Include relevant domain, persistence, API/UI and verification within each slice. Subdivide an oversized slice before coding.

1. **00.1** — Record current HEAD, working-tree changes and relationship to dff973f; preserve user work.
2. **00.2** — Run existing CI-equivalent checks and record environment, passes, failures and skips.
3. **00.3** — Map every FR/NFR to code, tests, gaps and its owning phase; refine the next phase using findings.

## Acceptance criteria

- [x] Every requirement is mapped or explicitly unverified.
- [x] Commands and actual results are recorded without claiming skipped checks passed.
- [x] A public/synthetic end-to-end scenario and safety regression baseline are identified. No application behaviour changes.

## Validation and phase gate

Use public/synthetic fixtures and provider-free tests for critical behaviour. Cover the positive scenario and relevant refusal, bypass, failure, restart and invalidation cases above. Run existing affected regressions and applicable CI checks; inspect UI screenshots or exported artifacts when relevant. Record exact commands, actual results and checks not performed. Do not equate provenance checks with scientific validation.

Present a reviewable diff and evidence against every criterion. Record product-owner gate approval only when explicitly received. Human pilot observations and external reviews must remain pending until actually performed.

## Slice 00.1 — Git baseline evidence (2026-09-15)

Scope: record repository state and preserve existing work, under explicit
authorisation for 00.1 only. No prerequisite phase gate. No applicable
`AGENTS.md` was found in the repository or its ancestor directories.

### Starting state

- Branch: `main`.
- HEAD and reference `dff973f` both resolve to
  `dff973ffdd42236f2449c51464c4a78c822969ea`.
- Commit subject: `docs: clarify historical prompt review`.
- Commit date: `2026-09-07 12:56:30 +0100`.
- `git rev-list --left-right --count dff973f...HEAD`: `0 0`;
  HEAD equals the reference, with no commits ahead or behind.
- `git diff --stat`: only `docs/README.md`, four added lines (three links
  to the PRD, phase index and reusable prompt, plus one blank line).
- `git diff --cached --stat`: empty; no staged changes.
- `git status --porcelain=v1 --untracked-files=all`: one modified tracked
  file (`docs/README.md`) and these 17 pre-existing untracked files:

```text
docs/GRILL_ME_HPA.md
docs/PRD.md
docs/phases/00-baseline.md
docs/phases/01-prototype-boundary.md
docs/phases/02-project-resume.md
docs/phases/03-source-lifecycle.md
docs/phases/04-ocr-privacy.md
docs/phases/05-pptx-assets.md
docs/phases/06-claim-evidence.md
docs/phases/07-planning.md
docs/phases/08-slide-review.md
docs/phases/09-visual-style.md
docs/phases/10-preview-export.md
docs/phases/11-public-pilot.md
docs/phases/12-professional-mode.md
docs/phases/PROMPT.md
docs/phases/README.md
```

All observed starting changes are documentation. Untracked files are user
work and are not yet protected by a Git commit. Later-phase contents were
not loaded. No application behaviour, architecture or deterministic control
was changed. PRD §§15–18 and NFR-06 guide the remaining audit; their claims
have not been independently verified by this slice.

### Verification and limits

- Passed: `git rev-parse HEAD`, `git log -1 --format=fuller`,
  `git rev-parse --verify 'dff973f^{commit}'`, and the comparison/status/diff
  commands above established the baseline without changing Git state.
- Passed: SHA-256 comparison of all 176 tracked and non-ignored untracked
  files before/after editing: same path set; only this phase file changed;
  the other 175 files remained byte-identical.
  The original phase text was copied to a temporary file for a before/after
  unified diff, because ordinary `git diff` does not show untracked files.
  The unified diff was reviewed. `git diff --check` and a separate trailing-
  whitespace check of this untracked phase file passed. Final HEAD and
  staged diff remained unchanged.
- No application checks run or claimed successful. Compilation, Ruff,
  JavaScript syntax, pytest/browser checks and environment validation are
  intentionally deferred to 00.2; requirement mapping and scenario/safety
  baseline identification remain for 00.3. Ignored files were not inventoried
  or hashed. No dependency installation or live provider call was needed.
- The phase acceptance checkboxes remain open. No human pilot, external
  review, scientific validation or product-owner phase approval is claimed.

## Slice 00.2 — Local CI-equivalent checks (2026-09-15)

Explicit authorisation: execute 00.2 only. HEAD remains
`dff973ffdd42236f2449c51464c4a78c822969ea`; the initial working-tree
inventory is unchanged from 00.1. No staged changes. Existing documentation
edits, including the 00.1 handoff, were preserved.

### Environment

- `sw_vers`: Mac OS X 10.15.7, build 19H2026.
- `uname -sm`: Darwin x86_64.
- `venv/bin/python --version`: Python 3.12.9.
- `venv/bin/ruff --version`: ruff 0.12.11.
- `venv/bin/pytest --version`: pytest 9.1.1.
- `node --version`: command not found. No Node executable found at
  `/usr/local/bin/node` or `/opt/homebrew/bin/node`; the usual local nvm,
  Volta and fnm version directories checked were also absent.
- CI configuration: Ubuntu latest, Python 3.12, Node 22, requirements
  installation and Playwright Chromium installation. This local run used
  the existing virtual environment, not a fresh CI dependency installation.
  No packages or browser binaries were installed or upgraded.

### Commands and actual results

| Command | Result | Evidence |
|---|---|---|
| `venv/bin/python -m compileall -q app streamlit_app.py main.py` | Passed, exit 0 | No compilation errors; no output. |
| `venv/bin/ruff check app tests streamlit_app.py main.py` | Passed, exit 0 | `All checks passed!` |
| `node --check app/interfaces/web/app.js` | Could not execute, exit 127 | `zsh:1: command not found: node`; JavaScript syntax remains unverified. |
| `venv/bin/pytest -q -ra` | Passed with skip, exit 0 | `93 passed, 1 skipped, 6 warnings in 10.03s`. `-ra` adds reporting to the planned `-q` command without changing test selection. |
| `venv/bin/python -m pip check` | Passed, exit 0 | `No broken requirements found.` Pip disabled its unavailable cache and emitted a cache permission warning. |

Exact skipped test:
`tests/test_web_browser.py::test_hcp_can_upload_validate_analyze_and_generate_blueprint_in_browser`.
At line 137 the existing test explicitly skips macOS 10.x:
`Playwright Chromium is not supported on macOS 10.15; CI runs this test on Ubuntu.`
The skip was not introduced or bypassed in this session. No browser UI,
screenshot or visual export inspection was performed.

Pytest reported five SWIG type deprecation warnings (`SwigPyPacked`,
`SwigPyObject`, `swigvarlink`) and one Starlette warning about deprecated
`httpx` use in `TestClient`. A further `swigvarlink` deprecation message
appeared at interpreter shutdown. These did not fail the run. No dependency
or application changes were made to silence them.

### Interpretation and remaining verification

The existing executable Python checks pass on this machine. This is not a
complete CI pass: Node syntax validation and the real Chromium workflow
remain unverified. Run the existing CI on its configured Ubuntu/Node 22
runtime to resolve those two gaps; no remote CI run was triggered or observed
in this slice. Dependency installation/reproducibility on a fresh runner is
also unverified. No live model evaluation or human/scientific validation was
performed. Existing deterministic tests ran; this result alone does not prove
coverage of every PRD requirement. Mapping belongs to 00.3.

Preservation verification: before/after SHA-256 comparison of 176 tracked and
non-ignored untracked files; only this phase file changed, the other 175 were
byte-identical, and no paths were added or removed. Ignored generated caches
are outside this comparison. The phase file's before/after unified diff was
reviewed separately because it is untracked. `git diff --check` and a separate
phase-file whitespace check passed. No application behaviour changed and no
commit was created.

## Slice 00.3 — Requirement mapping (2026-09-15)

Authorisation: the owner's instruction to continue, following 00.2, covers
00.3 only. The session was interrupted and resumed before documentation was
written; no application edits or background test processes were left running.

Deliverable: [requirement audit](00-requirement-audit.md) maps all 22 FR and
6 NFR to code, existing tests, gaps and owning phases. It identifies a synthetic
API-to-PPTX scenario and refusal, bypass, provider failure, restart,
invalidation, privacy and local-blocking regressions. The next phase plan was
refined using concrete prototype, recovery and UI findings.

Main findings: original source preservation/date gating/OCR/PDF export are
missing; slide citations are not exhaustive claim-level evidence; user-edited
and user-authored slides may be approved/exported without evidence; theme
changes retain approval; unauthenticated password reset and external-provider
patient-case processing conflict with the PRD. These are documented findings,
not fixes performed in phase 00.

Verification: requirement identifier coverage, referenced code/test paths and
explicit test symbols were checked; before/after documentation diffs were
reviewed. SHA-256 preservation comparison covers the 176 starting tracked and
non-ignored untracked files: only this file, phase 01 and the phase index were
updated; the other 173 remain byte-identical. One audit report was added.
`git diff --check` and separate whitespace checks for edited untracked docs
passed. HEAD and the empty staged diff remain unchanged. Ignored files are
outside this comparison. No application tests were rerun for documentation
changes; 00.2 execution results remain the baseline, including its skip,
warnings and unavailable JavaScript check.

## Session handoff

- Current slice: 00.3 complete; phase 00 audit deliverables ready for review.
- Changed files: `docs/phases/00-baseline.md`,
  `docs/phases/00-requirement-audit.md` (new),
  `docs/phases/01-prototype-boundary.md`, `docs/phases/README.md`.
  No application behaviour changed and no commit was created.
- Checks/results: documentation coverage/preservation/diff checks passed.
  Application baseline: 93 passed, 1 skipped, 6 warnings; compilation/Ruff
  passed; Node unavailable. No remote CI, visual or human validation claimed.
- Decisions: AUD-01–AUD-05 in the audit. Preserve deterministic architecture;
  fix historical PRD conflicts in their owning phases, not in this audit.
- Product-owner decision (2026-09-15): explicitly approved the phase 00 audit
  deliverables in this file and `00-requirement-audit.md`, accepting continuation
  with JavaScript not executed (Node unavailable) and the browser test skipped
  on macOS 10.15. Both checks remain outstanding, not successful.
  This approval is neither full PRD compliance nor scientific validation.
- Authorised continuation: **01.1** only. Its completed implementation and
  remaining verification are now recorded in the phase 01 handoff. **01.2**
  has not started and requires separate authorisation.
