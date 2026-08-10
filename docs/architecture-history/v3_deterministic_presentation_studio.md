# V3 — Deterministic Presentation Studio (current)

## Intent

The current architecture separates three user workspaces:

1. **Resources** — upload, attach and validate production evidence;
2. **Resource Analysis** — overview and PDF-only discussion;
3. **Presentation Studio** — create, generate, review, approve and export.

The LLM remains useful for discussion and content generation, but explicit
human interface commands start state-changing presentation operations.

## Main controls

- `WorkflowPolicy` owns allowed lifecycle transitions.
- explicit API jobs recheck Project state, validated evidence and professional
  scope before invoking the model;
- `ProductionEvidenceGate` blocks unsupported evidence-bound requests;
- `EvidenceProvenanceValidator` verifies resource ID, PDF page and evidence
  excerpt for AI-generated slides;
- failures are persisted as structured, recoverable business blockers;
- one state-writing job per Project prevents concurrent workflow writes;
- the user reviews agenda, blueprint, slides and final export.

## Retrospective

This is a strong MVP architecture for the stated objective. The key improvement
is conceptual: **the LLM is no longer the workflow authority**. The system
decides whether a model call is permitted; the model produces bounded content;
the system validates; a human approves.

The design is substantially more auditable and easier to test than V1. It is
also more understandable for HCPs because actions happen where they expect:
in a dedicated presentation workspace, not through conversational wording.

## What should improve next

- Add browser-level tests for the three workspaces and job-progress UI.
- Evaluate retrieval quality with the HCP protocol before changing the RAG.
- If usage grows, move local background jobs to a durable worker service while
  keeping the same command and state-machine contract.
- Continue to keep each business failure as a structured error code, stage and
  recovery action.

The broader history, open methodological questions and space for a senior's
feedback are in [ARCHITECTURE_EVOLUTION.md](../ARCHITECTURE_EVOLUTION.md).
