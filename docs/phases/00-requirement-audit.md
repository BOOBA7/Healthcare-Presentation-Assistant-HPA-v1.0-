# Phase 00 — Requirement audit

Date: 2026-09-15. Authority: [PRD v1.0](../PRD.md).
Baseline: `dff973ffdd42236f2449c51464c4a78c822969ea` plus the preserved
uncommitted documentation listed in [00-baseline.md](00-baseline.md).
This is a code/test audit, not application implementation or product approval.

## Evidence conventions

All paths below are repository-relative. Test filenames refer to `tests/`.
Partial means some implementation exists, with unmet or unverified clauses;
it does not mean the requirement is accepted. Missing means no implementation
was identified in the inspected models, use cases and API/UI paths. Test names
are evidence of the current contract, including historical behaviour that
conflicts with the PRD. No row claims complete PRD compliance.

Execution evidence is the 00.2 run: 93 passed, 1 browser skip, 6 warnings;
compilation and Ruff passed. JavaScript syntax was not checked because Node
was unavailable. No new application tests or live provider calls were needed
for this documentation-only slice. Code inspection is distinct from execution.

## Functional requirements

| ID | Current code evidence | Existing test evidence | Status and gaps | Owning phase |
|---|---|---|---|---|
| FR-01 | `app/interfaces/api/routers/auth.py`; `app/interfaces/storage/user_session_repository.py` | `test_user_session_repository.py`: password hashing/tokens, SQLite restore, local password reset | Partial, conflicting recovery path: `/auth/reset-password` has no authentication and calls `reset_password_without_verification`. Profiles and persistence exist; complete validation actor/timestamp coverage remains unverified. | 01 |
| FR-02 | Repository `list_projects` returns only id/name; `app/interfaces/web/app.js` Project selector | `test_user_can_keep_independent_projects` in `test_user_session_repository.py` | Partial: full dashboard count/status/context/style/resource-type summary, recent actions and visible last-save time not established. | 02 |
| FR-03 | `app/domain/models/conversation_context.py`; `app/application/use_cases/workflow_steps.py`; web setup form | `test_context_can_create_a_presentation_without_a_live_llm`; scope-declaration tests in `test_workflow_tools.py` and `test_end_to_end_deterministic_workflow.py` | Partial: topic/audience/duration/objective and explicit scope exist. Context lacks explicit target slide count and special instructions. Multidisciplinary professor acceptance needs targeted coverage. | 02 |
| FR-04 | `app/application/use_cases/extract_pdf_resource.py`; PDF upload in `app/interfaces/api/main.py` | `test_authenticated_project_resource_lifecycle_is_durable_and_hides_pdf_text` | Partial: readable PDF only. Empty extracted text is rejected. No OCR/PPTX evidence/PNG/JPEG or extracted visual ingestion found. PPTX template upload is not evidence ingestion. | 03–05 |
| FR-05 | `app/domain/models/resource.py`; PDF extractor; normalized resource tables in repository | `test_pdf_pages_and_chunks_are_not_serialized_in_project_state`; normalized-chunk tests | Partial: filename, title, author/source, import time, text and page numbers exist. Original bytes/hash, scientific date, full media/rights metadata and extracted visual assets are missing. `path` field alone does not establish preservation. | 03–05 |
| FR-06 | PDF extractor uses `page.get_text`, rejects no-text PDF | No OCR/correction test identified | Missing: OCR, region preservation, uncertainty/correction records and confirmed-value provenance. | 04–05 |
| FR-07 | `app/application/validators/resource_validator.py` checks parsing and validation, not date; Resource lacks scientific date | No source-date gate test identified | Missing: trustworthy date extraction, date evidence and deterministic rejection of undated sources. | 03; extend 04–05 |
| FR-08 | `app/application/services/patient_case_privacy.py`; PDF screening conditional on patient-case mode | `test_patient_case_privacy.py` | Partial: text-pattern blocking and acknowledgement exist. Names/faces/image metadata/combinations are not covered; screening is conditional. Prototype currently allows acknowledged patient cases, contrary to NFR-04. | 01 boundary; 04–05, 12 |
| FR-09 | `app/application/services/production_evidence_gate.py`; `app/application/use_cases/build_blueprint.py`; evidence context builder | `test_prompt_safety.py`; BM25/direct single-passage parity test in `test_evidence_provenance.py` | Partial: lexical support gate exists. No explicit coverage assessment of all topic/objective/audience/depth/slide-count dimensions with missing-area report found. | 06 |
| FR-10 | `app/application/use_cases/discuss_resources.py`; response citation validator; separate transcript | `test_resource_discussion.py`; independent-history and provider-failure tests in `test_integration_api.py` | Partial: resource-only context and passage validation exist. Every factual claim's support is not established by citation existence; conflict comparison and explicit transfer of validated discussion to planning remain gaps. | 06 |
| FR-11 | `app/domain/models/agenda.py`; workflow steps; blueprint builder derives Agenda from slide titles | E2E Agenda approval; blueprint approval guards in workflow code | Partial: editable/approved Agenda exists. It currently derives from Blueprint, not a separately generated high-level section plan before Blueprint; targeted editing/order tests remain needed. | 07 |
| FR-12 | `app/domain/models/slide_outline.py`; blueprint/item review in workflow steps | E2E item approval; `test_user_blueprint_edit_is_traced_and_invalidates_dependent_workflow_steps` | Partial: number/title/objective/message/origin/review exist. Planned sources and planned visual are absent from outline model. | 07 |
| FR-13 | theme route in `app/interfaces/api/main.py`; template storage; web gallery; PPTX exporter | template repository test; PPTX tests | Partial: themes/templates exist. Theme route only changes theme/template and saves; it does not invalidate approval. Colour controls and stage-specific visual approval unverified. | 09 |
| FR-14 | slide generation, evidence gate, provenance validator, slide prompt | prompt safety, evidence provenance and unsupported-outline tests | Partial: bounded text generation exists. Supplied-value charts/tables/diagrams and supplied image placement missing; date/conflict/claim completeness not enforced. | 08–09; dependencies 03, 06 |
| FR-15 | `app/application/use_cases/generate_slides.py`; `ReviewSlideUseCase`; provenance validator | unsupported-outline test; user-authored export test in `test_workflow_tools.py` | Partial with critical conflict: unsupported outline pauses generation while retaining existing slides, but manually authored/edited slides may be approved/exported without evidence. No medical-claim versus nonmedical-slide gate. Continuing generation past every blocked outline is not established. | 08; global export 10 |
| FR-16 | edit/review/reject/regenerate use cases; indexed API actions | user-slide edit/invalidation test; E2E regeneration | Partial: text, notes, comments, approval and invalidation exist. Visual replacement/layout selection/deletion and complete source/data/visual invalidation need implementation or verification. Theme change demonstrably retains approval. | 08–09 |
| FR-17 | `Slide.speaker_notes` string; editing API; exporter does not write notes | E2E accepts notes during edit; no notes-export assertion | Partial storage only: no dedicated note-to-passage traceability or exported notes. Human slide review exists but note-specific completeness is unverified. | 08, 10 |
| FR-18 | slide `reference_details`; `EvidenceProvenanceValidator`; citation presentation; resources export slides | `test_evidence_provenance.py`; `test_citation_presentation.py`; resources export tests | Partial: PDF id/page/excerpt checked. No claim identifiers or exhaustive claim-to-evidence mapping; no source-slide citations/old-PPTX warning. Section/DOI completeness unverified. | 06, 10; PPTX 05 |
| FR-19 | discussion prompt asks to surface inconsistency | No dedicated conflict/date/passage comparison regression identified | Missing structured conflict handling: no guaranteed display of both dated positions and exact locations/passages. Prompt instruction is insufficient evidence of enforcement. | 06 |
| FR-20 | `app/interfaces/web/app.js` preview functions; PPTX exporter | E2E inspects PPTX structure; browser test skipped | Partial: local text/deck navigation exists. Browser and exporter render separately; custom native template styling is not previewed. Clipping/overlap/reference/visual parity not verified. | 10 |
| FR-21 | `app/application/use_cases/export_powerpoint.py`; final approval workflow | final-approval prerequisite, E2E PPTX, provenance tests | Partial: PPTX and several approvals checked. PDF absent; manually authored claims bypass evidence verification. Export use case relies on final state for some approvals rather than independently checking every current slide/Blueprint flag. | 10; claim gate 06, 08 |
| FR-22 | `manage_project_resources.py`; repository resource synchronization/deletion; exports directory | detach/reset tests, resource deletion/invalidation tests, API lifecycle | Partial: presentation detachment keeps Project library; this is not the PRD's professor-level library across Projects. Original/derived assets absent. Internal export cleanup on Project deletion not found; forensic erasure/internal transcript copies unverified. | 03; extend 04–05, 10 |

## Non-functional requirements

| ID | Current code evidence | Existing test evidence | Status and gaps | Owning phase |
|---|---|---|---|---|
| NFR-01 | FastAPI `/app`; README local Uvicorn command; web profiles/languages/evidence settings | root redirect test; browser test skipped | Partial: web works at API level. UI still offers Arabic, multiple roles and BM25/direct choice. Localhost launch guidance exists; accidental exposure protection not verified. Freeze Streamlit going forward. | 01–02 |
| NFR-02 | SQLite transactional save/event, revision check, durable jobs/transcripts | repository reload/stale revision/one-active-job tests; both provider-failure API tests | Partial, strong existing foundation: durable writes and failure preservation demonstrated. Last-save display and exhaustive material-action persistence/restart semantics unverified. | 02; every material action |
| NFR-03 | owner dependencies, password hashing, safe failure events; plain `sqlite3.connect` | auth/token, scoped events/jobs, observability and provider-failure tests | Partial: encrypted sensitive storage absent; reset path unsafe; temporary export cleanup absent. All-route two-user isolation, log-content audit, secrets history and no-admin-access policy remain unverified. No secrets were read for this audit. | 01, 03–05, 10, 12 |
| NFR-04 | `app/core/config.py`; `app/ai/llm/llm.py`; evidence settings allow patient cases | patient-case enablement and provider metadata tests demonstrate historical behaviour | Missing required boundary: OpenAI/Gemini adapters exist (default is OpenAI), no enforced public/synthetic-only mode or professional no-egress mode found. External-provider disclosure is not established. Real professional use remains prohibited by the PRD. | 01, 12 |
| NFR-05 | `app/application/services/observability.py` measures model-call stage/duration and prompt size | `test_observability.py`; safe counters API test | Partial: model timing exists, but extraction/OCR/export and full operation-level duration coverage are not established. No pilot-derived performance target or measurement claimed. | 11 |
| NFR-06 | deterministic domain/use cases; injected model substitutes in tests | 00.2: 93 passed, 1 skipped | Partial: existing workflow/refusal/provenance/privacy/persistence regressions are provider-free. New PRD date/OCR/claim/PDF/deletion rules lack tests; browser skipped and JS unverified. | 00; every implementation phase |

## Cross-cutting PRD clauses

- §9: exporter supplies title, Agenda, content, resources. Required conclusion
  and thank-you structure, one-idea quality and clipping/overlap remain
  unverified; phases 07, 09–10 own completion.
- §11: repository `save_with_event`, generation metadata and failure audit
  events provide a foundation. Exhaustive actor/timestamp/affected item/
  correction/provenance/blocker coverage is not proven. Every phase must
  extend events with its new operations.
- §12: competent privacy/security/regulatory/rights reviews remain pending,
  owned by phase 12 and applicable pre-commercialisation review. This audit
  makes no legal or clinical determination.
- §14: no observed pilot or active-time reduction verified here; phase 11.
- §§15–18: preserve deterministic architecture, record gaps and evidence,
  defer hardware/model/performance choices until measurement. This report
  provides baseline traceability; no architecture decision or schedule is
  preapproved. Owner learning/review time remains one hour per week.

## Reproducible scenario and safety regression baseline

Positive scenario: `tests/test_end_to_end_deterministic_workflow.py::test_end_to_end_human_controlled_workflow_without_live_model`.
It creates a synthetic account and temporary SQLite database, builds a PDF
fixture in memory, uploads/selects/validates it, explores independent resource
chat, generates and regenerates using deterministic substitutes, approves
Agenda/Blueprint/slides/final presentation and downloads a parsed five-slide
PPTX. It passed in 00.2. It checks the current API contract, not UI rendering,
real model quality or complete PRD compliance. Its user-authored edit/export
path is specifically a behaviour to tighten in phases 08/10.

| Scenario | Existing regression evidence | Limit |
|---|---|---|
| Missing/unsupported evidence refusal before model call | `tests/test_prompt_safety.py::test_missing_pdf_evidence_returns_before_the_model_workflow_is_invoked` | Does not prove full semantic support of every claim. |
| Disguised factual request/workflow bypass | `tests/test_prompt_safety.py::test_evidence_gate_rejects_a_scientific_request_hidden_in_profile_or_workflow_text`; `tests/test_state_summary.py::test_human_validation_is_not_an_agent_tool` | Prototype mode bypass has no regression yet. |
| Invalid resource/page/excerpt | `tests/test_evidence_provenance.py::test_invalid_evidence_reference_is_rejected`; Arabic excerpt test | Provenance, not scientific validation. |
| Provider failure | `tests/test_integration_api.py::test_chat_persists_user_turn_when_the_model_provider_fails`; resource discussion failure test | Deterministic provider failure simulation. |
| Restart and concurrency | `tests/test_user_session_repository.py::test_user_session_is_restored_from_sqlite`; stale revision and active-job tests | Full UI/process-crash recovery remains unverified. |
| Approval invalidation | `tests/test_workflow_tools.py::test_user_slide_edit_requires_new_human_approval_without_inheriting_ai_evidence`; resource deletion reset test | Visual/theme invalidation gap remains. |
| Privacy refusal | `tests/test_patient_case_privacy.py::test_patient_case_guard_reports_categories_without_exposing_matched_value` | Conditional text patterns only. |
| Local slide blocking | `tests/test_workflow_tools.py::test_unsupported_ai_outline_blocks_only_that_slide_and_keeps_supported_user_output` | Does not establish the stricter PRD global medical-claim export gate. |

## Decisions and next-phase refinement

- AUD-01: retain working deterministic controls and provider-free tests.
  A passing historical test may require deliberate revision when the PRD
  tightens its contract; never preserve an evidence bypass merely to keep it green.
- AUD-02: prioritise prototype restrictions, recovery removal and UI scope
  in phase 01. Apply restrictions at server ingestion and all model entry
  paths, including existing Projects, jobs and legacy shared use cases.
  Hiding a checkbox is not sufficient. No new Streamlit features.
- AUD-03: distinguish prototype data declaration from actual anonymisation:
  an acknowledgement cannot prove a document is public or identifier-free.
  Professional/patient-case paths must remain blocked; professional mode
  requires phase 12 verification.
- AUD-04: retain claim/export gaps as explicit phase 06/08/10 work. Phase 01
  does not promise to deliver claim-level scientific safety.
- AUD-05: resolve or explicitly review the missing Node/browser verification
  evidence at the phase gate. No Ubuntu CI run has been observed here.

## Phase gate

All 22 FR and 6 NFR identifiers are mapped, with gaps or unverified clauses
explicit. Commands/results are recorded in the baseline. A synthetic E2E
scenario and safety regressions are identified. No application behaviour was
changed. Phase 00 audit deliverables were approved with verification reservations on
2026-09-15 (decision below); full CI verification remains pending. Completion of this
audit is not completion of the PRD implementation.

Owner decision (2026-09-15): audit deliverables explicitly approved with the
Node/browser reservations above. These checks remain outstanding. Approval
permits authorised 01.1 work; it is not full PRD compliance or scientific validation.
