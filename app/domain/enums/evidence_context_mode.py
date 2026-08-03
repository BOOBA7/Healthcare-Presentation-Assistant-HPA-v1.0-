from enum import Enum


class EvidenceContextMode(str, Enum):
    """How validated user-PDF passages are selected before an LLM call."""

    BM25 = "bm25"
    DIRECT_BOUNDED = "direct_bounded"
