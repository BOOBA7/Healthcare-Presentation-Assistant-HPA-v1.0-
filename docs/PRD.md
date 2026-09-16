# Healthcare Presentation Assistant (HPA) — Product Requirements Document

**Version:** 1.0  
**Status:** Validated product baseline  
**Validation date:** 2026-09-15  
**Initial market:** France  
**Initial platform:** macOS, local web application at `/app`  
**Product languages:** French and English  
**Repository documentation language:** English

## 1. Product summary

Healthcare Presentation Assistant (HPA) helps a hospital-university professor create a medical presentation from resources supplied by that professor.

HPA may organise, summarise, reformulate, and visually present supported information. It must not silently add medical knowledge from the model, search for external evidence, or replace scientific review by the professor.

### Value proposition

Reduce the active work required to create a medical presentation from an observed baseline of approximately 13–20 hours to 5–8 hours, while ensuring that every exported medical claim is traceable to user-supplied evidence.

## 2. Problem statement

Hospital-university professors are heavily solicited and prepare presentations alongside clinical, teaching, and academic responsibilities. They usually possess the expertise and documents they need, but spend substantial time:

- collecting and reviewing resources;
- structuring the presentation;
- drafting slide content;
- adapting the content to the audience;
- formatting individual slides;
- checking scientific consistency and references.

In the observed vitamin D/rheumatology example, a five-slide presentation required an estimated 13–20 hours of active work distributed over roughly three calendar weeks. Formatting alone accounted for an estimated 5–6 hours.

## 3. Primary user

The MVP targets one primary persona:

- hospital-university professor in France;
- expert in the presentation's medical domain;
- personally creates and validates presentations rather than delegating them;
- creates approximately two or three presentations per month;
- normally produces 10–20 slides;
- presents mainly in courses and congresses;
- uses a MacBook;
- can perform common file-management and PowerPoint operations;
- works in French or English;
- retains final scientific responsibility.

Other healthcare professionals and other languages are outside the initial MVP interface.

## 4. Product goals

### 4.1 Primary goals

1. Make creation from a blank project clear and manageable.
2. Reduce total active presentation work to less than eight hours.
3. Prevent unsupported medical claims from reaching the final export.
4. Provide claim-level evidence traceability.
5. Preserve explicit human review of every exported slide.
6. Produce an editable PowerPoint and a PDF.
7. Preserve projects, progress, and audit information locally.
8. Allow the professor to resume an incomplete project.

### 4.2 Product-owner learning goals

The project must also help the product owner learn to:

- translate needs into acceptance criteria;
- supervise AI-assisted changes;
- review diffs and tests;
- understand the architecture and data flow;
- distinguish prompt behaviour from enforced application rules;
- use focused branches and descriptive commits.

One hour per week is reserved for learning and review.

## 5. Non-goals

HPA is not intended to:

- diagnose disease;
- prescribe or recommend individual treatment;
- make clinical decisions;
- replace professional medical judgment;
- search the web or external medical libraries automatically;
- answer from general model knowledge;
- generate medical imagery with AI;
- provide a full PowerPoint-equivalent editor;
- fully redesign an existing presentation in the MVP;
- provide multi-user collaboration in the MVP;
- independently validate scientific correctness;
- claim FDA approval, HIPAA compliance, EU certification, or medical-device status.

## 6. Product principles

### 6.1 Closed evidence corpus

Every medical statement must be grounded in a resource supplied by the user. The model may formulate titles, summaries, and transitions, but may not introduce a new medical assertion.

### 6.2 Microscopic traceability

Every exported medical claim must resolve to a specific resource, page or source slide, and exact supporting passage.

### 6.3 Deterministic authority

Application code—not an LLM prompt—must control workflow transitions, evidence gates, approvals, invalidation, deletion, and export eligibility.

### 6.4 Human accountability

The professor validates every slide and the final presentation. A disclaimer supplements safety controls; it never replaces them.

### 6.5 No silent completion of gaps

Missing, conflicting, undated, or uncertain information must be surfaced. HPA must not infer a missing medical value.

### 6.6 Local professional processing

Real professional documents must not leave the professor's computer. External Gemini access is limited to public or synthetic prototype data.

## 7. Target workflow

```text
Personal dashboard
  → Create or resume Project
  → Enter presentation context
  → Import resources
  → Validate privacy, dates, and evidence coverage
  → Explore resources through source-only chat
  → Generate and approve Agenda
  → Generate and approve slide-by-slide Blueprint
  → Select visual style or template
  → Generate supported slides
  → Review and explicitly approve each slide
  → Preview complete presentation
  → Final approval
  → Export editable PowerPoint and PDF
```

The interface must continuously expose the current step, next allowed action, evidence coverage, blockers, slide approval state, and last save time.

## 8. Functional requirements

### FR-01 — Local account

- Create and authenticate a local account.
- Store the professor profile and preferred language.
- Associate validations with the authenticated identity and timestamp.
- Resume Projects after the application closes.
- Do not expose an unauthenticated password-reset mechanism.

### FR-02 — Personal dashboard

The dashboard must show:

- presentation count and list;
- current workflow status;
- presentation purpose and context;
- theme and style;
- associated resource count and types;
- summary of recent actions;
- last save time;
- action to resume the Project.

Advanced usage analytics, sponsor views, and restorable version history are deferred.

### FR-03 — Presentation context

The user must provide:

- topic;
- audience;
- duration;
- target number of slides;
- learning objectives;
- special instructions.

The professor declares the relevant professional scope. A multidisciplinary topic requires an explicit, audited confirmation that the presentation is within the professor's competence.

### FR-04 — Accepted resources

The MVP accepts:

- text-readable PDF;
- scanned PDF;
- PowerPoint `.pptx`;
- PNG;
- JPEG;
- images and tables extracted from PDF or PowerPoint resources.

DOCX, spreadsheet formats, and DICOM are excluded from the MVP.

### FR-05 — Source preservation and metadata

For every resource, HPA must retain locally:

- original file;
- file hash;
- filename and media type;
- title;
- author, organisation, or publisher when available;
- scientific publication or update date;
- extracted text;
- page or PowerPoint slide location;
- extracted images and tables;
- available rights and provenance information;
- import timestamp.

A PowerPoint used as evidence must preserve its slide numbers. Its visual template may be reused through a separate, explicit action.

### FR-06 — OCR and extraction uncertainty

- Apply OCR to scanned PDFs.
- Preserve the original page or image region used for extraction.
- Flag uncertain values before use.
- Require explicit user confirmation for uncertain values.
- Record the extracted value, user correction, actor, and timestamp.
- Mark the final content locally as user-confirmed when a manual correction is used.

### FR-07 — Source date gate

A resource is acceptable only when a reliable publication or last-update date is present in the document or trustworthy scientific metadata.

The filesystem date and an unsupported user declaration do not satisfy this requirement. An undated resource must be blocked and replaced.

### FR-08 — Patient-identifier gate

Before storage or model processing, HPA must screen supported text, images, and metadata for possible identifiers, including:

- names and contact details;
- record and administrative identifiers;
- identifying dates;
- faces;
- sensitive embedded metadata;
- combinations that create a re-identification risk.

A possible identifier must block processing and request anonymisation. The professor must also confirm that patient-case material is anonymised. HPA must clearly state that automated detection cannot guarantee anonymisation.

### FR-09 — Evidence coverage assessment

Before Agenda generation, HPA must determine whether the selected resources provide sufficient support for:

- the topic;
- learning objectives;
- audience;
- requested presentation depth;
- target slide count.

When evidence is insufficient, HPA must identify the missing area and request an appropriate additional resource.

### FR-10 — Project resource discussion

The contextual chat must:

- operate inside the Project;
- answer only from imported resources;
- cite every factual answer;
- compare conflicting passages without choosing for the professor;
- refuse questions unsupported by the resources;
- explain what evidence is missing;
- allow validated discussion output to inform the Agenda or Blueprint.

Chat must not silently execute workflow-changing operations.

### FR-11 — Agenda

- Represent the high-level presentation sections.
- Be editable by the professor.
- Require approval before final Blueprint approval.

### FR-12 — Blueprint

Each proposed slide must include:

- slide number;
- title;
- objective;
- key message;
- planned supporting sources;
- planned visual;
- content origin;
- validation state.

All Blueprint items must be reviewed before slide generation.

### FR-13 — Visual style

After Blueprint approval and before slide generation, the professor may:

- select an HPA theme;
- select a locally stored PowerPoint template;
- choose available colours and styling.

A later style change invalidates the previous visual approval.

### FR-14 — Supported generation

HPA may:

- organise evidence;
- summarise and reformulate supported content;
- create titles and transitions;
- create an audience-adapted narrative;
- build tables, charts, and diagrams from supplied values;
- use medical images supplied in the Project.

HPA must not:

- add an unsupported medical assertion;
- extrapolate a missing value;
- silently resolve a source conflict;
- generate a medical image;
- claim that a source is current without verified date evidence.

### FR-15 — Local slide blocking and global export gate

- Generate slides that have sufficient evidence.
- Block only the unsupported slide.
- Allow the professor to continue reviewing other slides.
- Allow manual draft text with an explicit “user-provided, source missing” warning.
- Prevent scientific approval of that draft.
- Prevent final export until an acceptable source supports it.
- Permit an unsourced slide only when it contains no medical assertion, such as a thank-you slide.

### FR-16 — Slide editing and validation

For each slide, the professor may:

- edit text directly;
- request reformulation;
- replace a visual;
- select another layout;
- delete the slide;
- add review comments;
- approve or reject the slide.

The professor may inspect slides in any order. Any content, data, source, or visual change must invalidate the affected approval and require new review.

### FR-17 — Speaker notes

Speaker notes must:

- use only Project evidence;
- have traceable supporting passages;
- require human approval;
- be exported into PowerPoint;
- remain separate from visible slide content.

### FR-18 — Claim-level citations

Every material medical claim must have a visible reference marker linked to:

- resource identifier and human-readable title;
- PDF page or PowerPoint slide;
- section when available;
- exact evidence passage;
- DOI or bibliographic link when present in the supplied resource.

Final reference slides must collect all cited resources.

An old PowerPoint with no primary reference may still serve as evidence, but the relevant claim must display: “Source: user-supplied presentation — primary reference unavailable.”

### FR-19 — Conflicting resources

When resources conflict, HPA must show both supported positions, their dates, their source locations, and their exact passages. The professor makes the final interpretation. HPA must not automatically rank one as scientifically superior.

### FR-20 — Preview

The preview must represent the export accurately enough to detect:

- slide order errors;
- missing text or visuals;
- text clipping and overlap;
- incorrect references;
- theme inconsistencies;
- unapproved content.

### FR-21 — Export

Export is allowed only when:

- resources are validated;
- Agenda and Blueprint are approved;
- every medical claim has verified evidence;
- every slide is approved;
- no privacy or evidence blocker remains;
- final approval is recorded.

Required outputs:

- editable `.pptx`;
- `.pdf`.

### FR-22 — Removal and deletion

HPA must distinguish:

- **Remove from Project:** stop using the resource in the Project but keep it in the professor's local library.
- **Delete permanently:** remove the original, extracted text, derived images, indexes, and other internal copies.

Removing or deleting a source invalidates dependent content and approvals. Deleting a Project also removes internal temporary exports. Copies exported elsewhere by the professor remain untouched.

## 9. Presentation quality requirements

Every slide should:

- communicate one main idea;
- remain legible during projection;
- avoid unnecessary text density;
- contain no clipped or overlapping elements;
- use a visual only when it supports the message;
- match the audience and duration;
- remain visually coherent with the deck.

The normal deck structure is:

1. Title.
2. Agenda.
3. Main content.
4. Conclusion.
5. References.
6. Thank-you slide.

The conclusion must not introduce a new assertion or recommendation.

## 10. Non-functional requirements

### NFR-01 — Platform and interface

- macOS first.
- Local FastAPI web application at `/app`.
- Bind to localhost by default.
- Freeze Streamlit as a legacy interface; do not implement new MVP features in it.
- Show only French and English and the professor persona in the MVP interface.
- Do not expose BM25/direct-context selection to the professor.

### NFR-02 — Persistence and recovery

- Autosave every material user action.
- Display last-save time.
- Preserve work through application restarts and model-provider failures.
- Prevent stale or concurrent writes from overwriting newer Project state.

### NFR-03 — Security before professional data

- Encrypt sensitive local data at rest.
- Keep secrets outside Git.
- Restrict Project access to its owner.
- Avoid support or administrator access to Project content.
- Keep raw medical content out of telemetry and operational logs.
- remove temporary source and export artefacts safely;
- protect the local server from accidental network exposure;
- remove unauthenticated account-recovery paths.

### NFR-04 — Model execution modes

**Public prototype mode**

- Gemini may be used.
- Only public or synthetic resources are allowed.
- Patient-case material and confidential professional documents are forbidden.
- The interface must state that content is sent to an external provider.

**Professional mode**

- No resource or generated content may leave the professor's computer.
- A locally executed model or another approved no-egress architecture is required.
- Real professional documents remain blocked until this mode passes verification.

### NFR-05 — Performance measurement

No maximum latency is set for the initial pilot. HPA must separately record duration for:

- extraction and OCR;
- evidence analysis;
- Blueprint generation;
- slide generation;
- individual regeneration;
- export.

Targets will be set from observed data.

### NFR-06 — Testability

Critical rules must be testable without a live paid model:

- workflow transitions;
- unsupported-answer refusal;
- evidence and citation validation;
- approval invalidation;
- privacy blocking;
- removal and permanent deletion;
- PowerPoint and PDF export gates;
- audit persistence.

## 11. Audit requirements

The private Project audit trail must record:

- actor identity;
- timestamp;
- event and workflow stage;
- approval or rejection;
- affected resource or slide;
- human corrections;
- model provider and model identifier;
- workflow and retrieval versions;
- provenance-check result;
- blocker reason.

Audit data should avoid duplicating raw medical text unless required for verified provenance.

## 12. Privacy and regulatory position

HPA's declared intended purpose is assistance with drafting educational or scientific presentations. It must not be marketed as diagnostic, therapeutic, prescribing, or clinical decision-support software.

Regulatory qualification depends in part on the product's declared intended purpose and actual functionality. A formal assessment is required before commercialisation:

- [European Commission guidance on qualification and classification of medical software](https://health.ec.europa.eu/document/download/b45335c5-1679-4c71-a91c-fc7a4d37f12b_en?filename=md_mdcg_2019_11_guidance_qualification_classification_software_en.pdf&prefLang=cs)
- [EU Artificial Intelligence Act](https://eur-lex.europa.eu/eli/reg/2024/1689/2026-07-27/eng)

Pseudonymised data may remain personal data; only genuinely anonymised information is outside the corresponding GDPR scope:

- [CNIL guidance on anonymisation and pseudonymisation](https://www.cnil.fr/fr/comment-prevenir-les-risques-et-organiser-la-securite-de-vos-donnees)

Health data requires safeguards proportionate to its sensitivity:

- [CNIL guidance on health-data security](https://www.cnil.fr/fr/securite-des-donnees-de-sante)

Local-only operation avoids external hosting, but any future remote storage or synchronisation requires a new assessment, including the French HDS framework:

- [French Digital Health Agency — HDS](https://esante.gouv.fr/produits-services/hds)

Before real professional use, competent review is required for GDPR, anonymisation, possible impact assessment, the AI Act, possible MDR qualification, security, copyright, image rights, and model-provider terms.

## 13. MVP boundaries and deferred scope

Deferred beyond the MVP:

- Windows;
- Arabic;
- profiles other than hospital-university professor;
- DOCX, spreadsheets, and DICOM;
- full PowerPoint-equivalent editing;
- complete redesign of an old deck;
- independent research workspace;
- collaboration and comments between users;
- restorable version history;
- advanced analytics;
- sponsor and investor interfaces;
- laboratory-funded access model.

## 14. Pilot protocol and success metrics

The first pilot:

- uses one professor;
- is observed directly by the product owner;
- runs on the product owner's MacBook;
- uses a real medical topic with public resources only;
- does not validate installation on the professor's computer;
- does not provide independent scientific review.

Measure separately:

- total active work;
- time manipulating HPA;
- reading and validation time;
- model waiting time;
- post-export correction time;
- observer interventions;
- blockers and recoveries;
- regenerations;
- citation rejections;
- slides requiring major rewrite;
- stated intention to reuse HPA.

### Success criteria

- A complete editable PowerPoint and PDF are exported.
- Total active work is less than eight hours.
- 100% of exported medical claims are traceable.
- Zero invented medical claims.
- Zero incorrect citations.
- Zero privacy incidents.
- 100% of exported slides have recorded approval.
- At least 90% of slides require no major rewrite.
- The professor states an intention to use HPA again and explains why.

Any invented claim, false citation, privacy incident, data loss, or unapproved medical export is a critical pilot failure.

## 15. Current technical baseline

The repository already contains valuable foundations:

- deterministic workflow states and guards;
- PDF page/excerpt provenance validation;
- local SQLite Projects, accounts, jobs, and audit events;
- asynchronous model-backed jobs;
- provider-free automated tests;
- FastAPI and Streamlit interfaces;
- PowerPoint generation;
- architecture and evaluation documentation;
- CI for compilation, lint, JavaScript syntax, browser, and Python tests.

Known gaps against this PRD include:

- no OCR;
- no PowerPoint evidence ingestion;
- no medical-image ingestion or placement;
- no PDF export;
- no verified claim-level citation model;
- no source-date gate;
- original PDF bytes not currently retained;
- speaker notes not exported;
- limited text-pattern privacy detection;
- unencrypted SQLite;
- unsafe local password reset if network-exposed;
- possible retained temporary exports;
- duplicated Streamlit and web implementation;
- several large modules that increase maintenance risk.

This baseline does not justify a total rewrite. Changes should preserve working safety controls and proceed incrementally.

## 16. Risks

| Risk | Consequence | Required response |
|---|---|---|
| MVP scope exceeds available weekly time | Long schedule and unfinished work | Deliver in gated phases; keep scope/date trade-offs explicit |
| Retrieval misses relevant evidence | False refusal | Measure with reproducible cases; never bypass the evidence gate |
| Traceable source is scientifically weak | False confidence | Show source type/date and retain professor responsibility |
| OCR changes a value | Scientific error | Original-region display and explicit correction audit |
| Identifier detection misses a patient | Privacy incident | Block risky content, require confirmation, and avoid claiming guaranteed anonymisation |
| Gemini receives confidential content | Confidentiality breach | Public/synthetic-only prototype mode |
| Local model is too weak or too large | Professional mode unavailable | Hardware inventory and model evaluation before selection |
| References overload the slide | Poor readability | Visible compact markers plus detailed evidence panel and appendix |
| One evaluator reviews their own work | Biased pilot result | Limit claims to exploratory usefulness and technical evidence behaviour |
| Two interfaces diverge | Maintenance and UX defects | Develop `/app` only and freeze Streamlit |

## 17. Open decisions and external dependencies

- Local model and minimum Mac hardware.
- Realistic completion schedule after baseline tests.
- Performance targets after measurement.
- Formal French and EU regulatory assessment.
- Future price and willingness-to-pay validation.
- Independent scientific review, currently unavailable.

## 18. Traceability policy

- Use English for committed reference documents.
- Use French for product-owner discussion and teaching.
- Anchor the initial state to Git commit `dff973f`.
- Assign stable identifiers to requirements and decisions.
- Link implementation commits and tests to requirements.
- Use the existing ADR for architecture decisions only.
- Preserve before/after test evidence and screenshots.
- Use only public or synthetic content in repository artefacts.
- Record product-owner approval at each phase gate.

## 19. Approval record

The product-owner interview synthesis was explicitly validated. The discussion-version PRD, including the local-slide-block/global-export-gate rule, was explicitly validated on 2026-09-15.

Implementation remains subject to a separate explicit authorisation.
