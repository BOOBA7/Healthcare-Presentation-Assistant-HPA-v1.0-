# V2 — Evidence Library and Local Retrieval (evolved into current design)

## Intent

HPA moved from sending broad PDF text to the model toward a Project-scoped
resource library. PDFs are normalised into resources, pages and chunks in
SQLite. Retrieval selects bounded passages with title, page and resource
identity retained for provenance.

## What was good

- Evidence belongs to the user and Project, not to a shared global corpus.
- Page-level text permits system verification of AI slide citations.
- BM25 is local, inspectable, reproducible and inexpensive for an MVP.
- Resource overview and PDF discussion can happen before presentation
  production, keeping exploration distinct from validated production evidence.

## Limitation discovered

BM25 is lexical. It can miss a useful passage expressed with different words.
Also, retrieval originally risked being implemented separately for overview,
resource discussion, blueprint and slides, which would make results
inconsistent and hard to evaluate.

## What would be improved today

Keep one retrieval interface for every evidence-bound feature and evaluate it
with HCPs before adding semantic retrieval. A future semantic layer should be
added only when it improves evidence fidelity and traceability, not merely
because embeddings are fashionable.

## Status

Evolved into V3. The Project library, SQLite pages/chunks, BM25 and bounded
direct-context comparison remain part of the current architecture.
