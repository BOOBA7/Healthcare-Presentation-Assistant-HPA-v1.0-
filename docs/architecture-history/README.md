# Architecture History

This folder preserves decisions that were replaced during HPA's development.
They are retained as learning artefacts, not as descriptions of the current
runtime architecture.

| Stage | Main idea | Outcome |
|---|---|---|
| [V1 — Agent-led chat workflow](v1_agent_led_chat.md) | Let the conversational agent coordinate the presentation lifecycle through tools. | Useful prototype; too much workflow authority was coupled to the LLM. |
| [V2 — Evidence library and local retrieval](v2_evidence_library_and_rag.md) | Put user PDFs, page provenance and bounded retrieval at the centre. | Established the evidence boundary and durable Project data model. |
| [V3 — Deterministic Presentation Studio](v3_deterministic_presentation_studio.md) | Move lifecycle commands to explicit interface actions and server jobs. | Current architecture. The LLM is a bounded cognitive component, not the workflow authority. |

For the cross-stage narrative and learning reflection, see
[Architecture Evolution](../ARCHITECTURE_EVOLUTION.md). The current decision
record is [ADR-0007](../../ADR.md).
