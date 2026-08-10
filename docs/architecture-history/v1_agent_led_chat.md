# V1 — Agent-led Chat Workflow (superseded)

## Intent

The first architecture used a conversational LangGraph agent and application
tools to collect presentation context, create a presentation, build a
blueprint, generate slides and guide reviews. The goal was to reproduce a
natural professional discussion while avoiding a simple one-shot prompt.

## What was good

- It introduced explicit state, rather than treating a presentation as plain
  chat text.
- It separated prompt, harness, graph, tools and application use cases.
- It made human validation visible as a product requirement.
- It revealed the real healthcare problem early: fluent generation is not
  evidence or approval.

## Limitation discovered

Even with a guarded tool node, letting the model choose lifecycle tools made
the product fragile. A user could ask for generation in chat while the
interface expected another validation step. The model also had to remember
which tool was appropriate, which produced repeated prompts and confusing
recovery paths.

The core issue was architectural, not prompt quality: the LLM was too close to
the authority that changes business state.

## What would be improved today

Define the state machine and explicit commands before implementing the chat.
The chat should collect context, explain blockers and support discussion, but
should not own a transition such as create presentation, generate blueprint,
generate slides, approve or export.

## Status

Superseded by V3. Some useful components remain: bounded chat memory, trusted
state summaries, a guarded graph, and safe tool-result handling.
