# HPA implementation phases

## Authority and starting point

This proposed sequence derives from [PRD v1.0](../PRD.md), validated 2026-09-15. It does not change requirements or claim features are implemented. Reference baseline: `dff973f`; inspect current HEAD and user changes before work. Architecture decisions belong in [ADR.md](../../ADR.md).

Planning read the complete PRD, documentation index, project overview, CI and selected domain/export code. No application tests or complete code audit were performed. Phase 00 establishes verified coverage. Existing untracked `docs/PRD.md` and `docs/GRILL_ME_HPA.md` must be preserved.

## Ordered gates

| Phase | Outcome | Status |
|---|---|---|
| [00](00-baseline.md) | Baseline and requirement audit | Audit approved with Node/browser reservations (2026-09-15); checks outstanding |
| [01](01-prototype-boundary.md) | Public prototype boundary and local account | Approved with Node/browser reservations (2026-09-15); checks outstanding |
| [02](02-project-resume.md) | Dashboard, context and recovery | Approved 2026-09-15; Node/browser checks remain unverified |
| [03](03-source-lifecycle.md) | Preserved PDF sources, dates and deletion | Approved 2026-09-16; Node/browser checks remain unverified |
| [04](04-ocr-privacy.md) | Scanned PDF, images and extraction review | Approved 2026-09-16 for restricted subset; browser/scope reservations remain |
| [05](05-pptx-assets.md) | PowerPoint evidence and extracted visuals | Approved 2026-09-17 for documented restricted subset; browser/visual reservations remain |
| [06](06-claim-evidence.md) | Claim evidence, coverage and resource discussion | 06.1 approved 2026-09-17; 06.2–06.3 not started; phase gate pending |
| [07](07-planning.md) | Agenda and Blueprint approval | Planned |
| [08](08-slide-review.md) | Supported generation, editing and speaker notes | Planned |
| [09](09-visual-style.md) | Themes, layouts and supplied visuals | Planned |
| [10](10-preview-export.md) | Faithful preview, PowerPoint and PDF | Planned |
| [11](11-public-pilot.md) | Measured public-resource pilot | Planned |
| [12](12-professional-mode.md) | Verified professional local execution | Planned |

Phases 00–11 deliver and evaluate the public/synthetic prototype. Phase 12 is mandatory before real professional data; it is part of the PRD roadmap, not silently deferred scope. Schedule follows baseline findings and observed progress.

Current-code verification update (2026-09-16): phase 04 actually ran and passed
JavaScript syntax checking with bundled Node v22.18.0. Earlier historical Node
reservations do not become past test successes. Browser execution remains
unverified; phase 04's two browser scenarios are skipped on this Mac.

## Execution contract

1. Read this index, the selected phase/handoff, applicable repository instructions and relevant PRD sections. Inspect code as needed; do not reload all phases or all chat history.
2. Verify prerequisite gates and preserve user work. An explicit request to implement a slice authorises routine work within that slice; do not repeatedly request confirmation. Do not invent previous gate approval.
3. Execute one coherent, testable slice per conversation. A phase may span several sessions. Split oversized work into demonstrable behaviour across required layers, not separate database/backend/frontend projects.
4. Preserve the architecture and deterministic safety controls. New MVP UI work belongs in `/app`; freeze Streamlit. Use English documents and French explanations. Use public/synthetic artifacts only.
5. Complete authorised changes, suitable tests and diff review. Link requirement IDs to actual tests and commits when available. Never invent results or weaken gates to make tests pass.
6. Update the phase handoff with changed files, decisions, commands/results, blockers and next exact slice. Keep it concise; link larger evidence reports separately. Preserve before/after evidence and relevant screenshots without secrets or private content.
7. Present completed phase evidence before seeking its product-owner gate approval (PRD §18). Record approval only when explicit; do not start the next phase automatically. This planning request does not authorise application implementation (PRD §19).
8. Use focused branches/commits within user authorisation. Explain one useful engineering concept at each gate; reserve the owner’s planned weekly learning/review hour. The agent cannot supply human pilot feedback or competent external assessments.

## Existing CI checks

Verify tool availability during phase 00. Do not install dependencies just to write these plans.

```sh
venv/bin/python -m compileall -q app streamlit_app.py main.py
venv/bin/ruff check app tests streamlit_app.py main.py
node --check app/interfaces/web/app.js
venv/bin/pytest -q
```

Run focused tests during changes and applicable CI checks at gates. Unsupported macOS browser tests may need CI; explicitly distinguish skipped checks from passes.

## Requirement ownership

| Requirements | Phases |
|---|---|
| FR-01 | 01 |
| FR-02–FR-03 | 02 |
| FR-04–FR-05 | 03–05 |
| FR-06 | 04–05 |
| FR-07 | 03; every added format in 04–05 |
| FR-08 | 04–05, 12; prototype boundary 01 |
| FR-09–FR-10 | 06 |
| FR-11–FR-12 | 07 |
| FR-13 | 09 |
| FR-14 | 08–09 |
| FR-15–FR-17 | 08; visual editing 09; notes export 10 |
| FR-18 | 06, 10; old-PPTX warning 05 |
| FR-19 | 06 |
| FR-20–FR-21 | 10 |
| FR-22 | 03; extend cleanup for new formats/assets in 04–05, 10 |
| NFR-01 | 01–02; maintained throughout |
| NFR-02 | 02; every new material action |
| NFR-03 | 01, 03–05, 10, 12 |
| NFR-04 | 01, 12 |
| NFR-05 | 11 |
| NFR-06 | 00 and every implementation phase |
| PRD §9 quality | 07, 09–10 |
| PRD §11 audit | Every phase adding actions, claims or approvals |
| PRD §12 competent reviews | 12, before professional use/commercialisation as applicable |
| PRD §14 pilot | 11 |
| PRD §18 traceability | Every phase |

Phase 00 expands this ownership map into requirement-to-code/test evidence.

## Context and prompting

Use [PROMPT.md](PROMPT.md) for a selected slice. Small context helps only when relevant requirements, code and validation evidence are retained. No model-independent “smart zone” threshold guarantees quality. Start a fresh conversation at a coherent handoff boundary; keep the same chat while resolving the same bounded problem.

Sources checked 2026-09-15:

- [Matt Pocock: Smart zone](https://www.aihero.dev/ai-coding-dictionary/smart-zone): focused sessions and handoffs when context grows; numerical boundaries are debated.
- [Matt Pocock: engineering skills](https://www.aihero.dev/skills-post): PRDs and independently executable vertical slices.
- [Official OpenAI documentation: best practices](https://learn.chatgpt.com/guides/best-practices): goal, context, constraints, completion criteria, testing and coherent chats.
