"""
E10/E11 (reconstruction-v2) -- the NEW, minimal read-only tool set for the bounded selective
agent (A3) prototype. Does NOT modify or import `pipeline/agent.py`/`pipeline/agent_tools.py`
(T-series, historical, byte-unchanged).

All three tools are read-only and deterministic (no LLM calls anywhere in this module). Each
operates only on the current NDA's own full text, its clause_256 chunking (retrieval_v1's own
chunking method), and the SAME frozen BM25 top-20 candidate pool retrieval_v1 already computes
for this case -- never a fresh/different query, never a different chunk size or reranker, never
gold spans or evaluator annotations. Frozen per E10 Stage A
(experiments/E10_agent_design/summary.md):

  - follow_cross_reference: direct evidence from E09's one confirmed dynamic case
    (train::273::nda-1 -- an unresolved reference to "paragraphs (a) to (c) of the definition
    of Confidential Information").
  - get_definition: NOT exposed as a standalone agent action (revised after E10 Stage A review --
    E09 found no direct residual case proving a separate definition-lookup tool is needed beyond
    what follow_cross_reference already covers via its "definition of X" pattern). Kept as an
    internal helper `follow_cross_reference` delegates to, not a third top-level tool -- avoids
    adding tool surface without direct evidentiary support.
  - get_more_candidates: reveals ranks 6-10, then 11-15, then 16-20 of the ALREADY-COMPUTED
    top-20 reranked pool -- never a new BM25/dense query, never a different reranker. Stateless
    progression driven by the CALLER (pipeline/agent_v2.py's loop tracks how many windows have
    already been revealed for a case), not by a model-supplied rank argument -- this removes any
    ability for the model to request an arbitrary or duplicate window.

Every tool returns a `ToolResult` and never raises to its caller -- a failure to locate/resolve
becomes `success=False` with a structured `error`, never an exception.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pipeline.chunker import Chunk, clause_aware_chunk
from pipeline.reranker import rerank
from pipeline.retriever import RetrievalResult
from pipeline.sparse_retriever import SparseIndex

CLAUSE_CHUNK_SIZE = 256  # matches retrieval_v1 exactly -- not a new chunking config
CANDIDATE_POOL_SIZE = 20  # matches retrieval_v1's candidate_pool_size -- the hard ceiling
WINDOW_SIZE = 5  # get_more_candidates reveals 5 ranks per call (6-10, then 11-15, then 16-20)
MAX_RESULT_TEXT_CHARS = 500  # follow_cross_reference / get_definition, per E10 Stage A
MAX_CANDIDATE_CHUNK_CHARS = 300  # get_more_candidates, per chunk
MAX_CANDIDATE_RESULTS = 5  # get_more_candidates, per call -- 5 x 300 = 1500 char cap total


@dataclass
class ToolResult:
    tool: str
    success: bool
    query_or_target: str
    results: list[dict] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "tool": self.tool, "success": self.success,
            "query_or_target": self.query_or_target,
            "results": self.results, "error": self.error,
        }

    def total_text_chars(self) -> int:
        """Used by the agent loop to enforce max_cumulative_added_context_tokens."""
        return sum(len(r.get("text", "")) for r in self.results)


def _document_chunks(doc_text: str) -> list[Chunk]:
    """The SAME clause_256 chunking retrieval_v1 uses -- not a new chunking config."""
    return clause_aware_chunk(doc_text, CLAUSE_CHUNK_SIZE)


def _truncate(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[:max_chars]


# =============================================================================
# A. follow_cross_reference
# =============================================================================

# Deterministic locators only -- no semantic/LLM matching. Each pattern captures a numbering
# token (e.g. "4(b)", "7", "c") that is then searched for near the START of a chunk, matching
# how NDAs actually number provisions (a clause's own number leads its own text).
_SECTION_REF_RE = re.compile(
    r"(?:section|article|clause|paragraph)\s+([0-9]+(?:\.[0-9]+)*(?:\([a-zA-Z0-9]+\))?|\([a-zA-Z0-9]+\))",
    re.IGNORECASE,
)
_BARE_PAREN_REF_RE = re.compile(r"^\(([a-zA-Z0-9]+)\)$")
_DEFINITION_REF_RE = re.compile(r"definition\s+of\s+[\"“]?([^\"”.,;]+)", re.IGNORECASE)


def _normalize_reference(reference: str) -> tuple[str, str] | None:
    """Returns (kind, locator) or None if the reference doesn't match any known deterministic
    pattern -- kind is 'numbered' (locator is the numbering token, e.g. '4(b)', '7', 'c') or
    'definition' (locator is the referenced term, delegates to the same search get_definition
    uses)."""
    reference = reference.strip()
    m = _DEFINITION_REF_RE.search(reference)
    if m:
        return ("definition", m.group(1).strip())
    m = _SECTION_REF_RE.search(reference)
    if m:
        return ("numbered", m.group(1))
    m = _BARE_PAREN_REF_RE.match(reference)
    if m:
        return ("numbered", f"({m.group(1)})")
    return None


def _chunk_starts_with_numbering(chunk_text: str, locator: str) -> bool:
    """A clause's own numbering conventionally leads its text, e.g. '4(b) The Receiving
    Party...' or '(c) any information...' -- searched only within the first ~20 characters to
    avoid matching an unrelated in-body mention of the same digits/letters. A parenthetical
    locator (e.g. '(b)') is already self-delimiting -- no extra word-boundary check needed, and
    none is applied, since a combined form like '4(b)' legitimately has a digit immediately
    before the parenthesis. A bare alphanumeric locator (e.g. '7') DOES need boundary checks so
    it doesn't match inside an unrelated longer number."""
    head = chunk_text[:20]
    if locator.startswith("("):
        return locator in head
    escaped = re.escape(locator)
    return bool(re.search(rf"(?<![0-9a-zA-Z]){escaped}(?![0-9a-zA-Z])", head))


def follow_cross_reference(doc_text: str, reference: str) -> ToolResult:
    """Resolves an explicit cross-reference (e.g. 'Section 4(b)', 'paragraph (c)', 'Article 7',
    'definition of Confidential Information') to the matching provision within the CURRENT NDA
    only. Ambiguous (multiple equally-plausible matches) or malformed references return a
    structured not-found result, never a guess."""
    if not reference or not reference.strip():
        return ToolResult(tool="follow_cross_reference", success=False,
                           query_or_target=reference, error="EMPTY_REFERENCE")

    normalized = _normalize_reference(reference)
    if normalized is None:
        return ToolResult(tool="follow_cross_reference", success=False,
                           query_or_target=reference, error="MALFORMED_REFERENCE")

    kind, locator = normalized
    if kind == "definition":
        return get_definition(doc_text, locator, _tool_name="follow_cross_reference")

    chunks = _document_chunks(doc_text)
    matches = [c for c in chunks if _chunk_starts_with_numbering(c.text, locator)]

    if not matches:
        return ToolResult(tool="follow_cross_reference", success=False,
                           query_or_target=reference, error="NOT_FOUND")
    if len(matches) > 1:
        return ToolResult(tool="follow_cross_reference", success=False,
                           query_or_target=reference, error="AMBIGUOUS_REFERENCE",
                           results=[{"chunk_id": c.chunk_index, "text": "", "source_start": c.start_char,
                                     "source_end": c.end_char} for c in matches[:5]])

    c = matches[0]
    return ToolResult(
        tool="follow_cross_reference", success=True, query_or_target=reference,
        results=[{"chunk_id": c.chunk_index, "text": _truncate(c.text, MAX_RESULT_TEXT_CHARS),
                  "source_start": c.start_char, "source_end": c.end_char}],
    )


# =============================================================================
# B. get_definition
# =============================================================================

def _definition_pattern(term: str) -> re.Pattern:
    escaped = re.escape(term.strip())
    # Matches: "Term" means / shall mean / refers to / (the "Term") ... -- covers the standard
    # NDA definition phrasings without any semantic/LLM matching.
    return re.compile(
        rf'[“"]{escaped}[”"]\s*(?:means|shall\s+mean|refers\s+to)',
        re.IGNORECASE,
    )


def get_definition(doc_text: str, term: str, _tool_name: str = "get_definition") -> ToolResult:
    """Searches the CURRENT NDA's own text for a standard definition pattern
    ('"Term" means ...' / 'shall mean' / 'refers to'), case-insensitive, quote-style-insensitive.
    No semantic/LLM matching -- purely deterministic pattern search. Multiple genuinely distinct
    matches are returned as an ambiguous result, not arbitrated."""
    if not term or not term.strip():
        return ToolResult(tool=_tool_name, success=False, query_or_target=term,
                           error="EMPTY_TERM")

    normalized_term = term.strip().strip('"“”')
    pattern = _definition_pattern(normalized_term)
    chunks = _document_chunks(doc_text)
    matches = [c for c in chunks if pattern.search(c.text)]

    if not matches:
        return ToolResult(tool=_tool_name, success=False, query_or_target=term,
                           error="NOT_FOUND")
    if len(matches) > 1:
        return ToolResult(tool=_tool_name, success=False, query_or_target=term,
                           error="AMBIGUOUS_DEFINITION",
                           results=[{"chunk_id": c.chunk_index, "text": "", "source_start": c.start_char,
                                     "source_end": c.end_char} for c in matches[:5]])

    c = matches[0]
    return ToolResult(
        tool=_tool_name, success=True, query_or_target=term,
        results=[{"chunk_id": c.chunk_index, "text": _truncate(c.text, MAX_RESULT_TEXT_CHARS),
                  "source_start": c.start_char, "source_end": c.end_char}],
    )


# =============================================================================
# C. get_more_candidates
# =============================================================================

def get_more_candidates(doc_text: str, hypothesis_text: str, already_revealed_count: int) -> ToolResult:
    """Reveals the next WINDOW_SIZE (5) ranks of the ALREADY-COMPUTED frozen retrieval_v1
    candidate pool (BM25 top-20, reranked by the same cross-encoder), beyond whatever has already
    been shown to the agent for this case. `already_revealed_count` is maintained by the CALLER
    (pipeline/agent_v2.py's loop state) -- e.g. 5 after the initial A2 top-5, 10 after one prior
    call to this tool, etc. -- never taken from a model-supplied argument, so the model cannot
    request an arbitrary or duplicate window.

    Does NOT re-query BM25 with different terms, does NOT use a different embedding model or
    reranker -- this exposes more of retrieval_v1's OWN already-deterministic ranking, capped at
    CANDIDATE_POOL_SIZE (20)."""
    if already_revealed_count >= CANDIDATE_POOL_SIZE:
        return ToolResult(tool="get_more_candidates", success=False,
                           query_or_target=hypothesis_text, error="POOL_EXHAUSTED")

    chunks = _document_chunks(doc_text)
    index = SparseIndex(chunks)
    hits = index.search(hypothesis_text, top_k=CANDIDATE_POOL_SIZE)
    candidates = [RetrievalResult(chunk=c, score=s) for c, s in hits]
    reranked = rerank(hypothesis_text, candidates, top_k=CANDIDATE_POOL_SIZE)

    window_start = already_revealed_count  # 0-indexed into `reranked`
    window_end = min(window_start + WINDOW_SIZE, CANDIDATE_POOL_SIZE, len(reranked))
    window = reranked[window_start:window_end]

    if not window:
        return ToolResult(tool="get_more_candidates", success=False,
                           query_or_target=hypothesis_text, error="POOL_EXHAUSTED")

    results = [
        {"chunk_id": r.chunk.chunk_index,
         "text": _truncate(r.chunk.text, MAX_CANDIDATE_CHUNK_CHARS),
         "source_start": r.chunk.start_char, "source_end": r.chunk.end_char}
        for r in window[:MAX_CANDIDATE_RESULTS]
    ]
    return ToolResult(tool="get_more_candidates", success=True,
                       query_or_target=hypothesis_text, results=results)


def demo() -> None:
    """Smallest runnable self-check -- no network, no model calls."""
    # Each clause is individually padded well past the 256-token chunk budget so
    # clause_aware_chunk cannot merge it with a neighboring clause -- guarantees 4 separate,
    # deterministic chunks for this self-check.
    filler = (" Additional recital language padding this individual clause out well past the "
              "two hundred fifty six token chunk budget so it cannot be merged with any "
              "neighboring clause during chunking.") * 6
    doc = (
        f"1. Definitions.{filler}\n\n"
        f'"Confidential Information" means any and all information disclosed by either '
        f"party.{filler}\n\n"
        f"4(b) The Receiving Party shall not copy Confidential Information without "
        f"consent.{filler}\n\n"
        f"7. This Agreement shall be governed by the laws of Delaware.{filler}\n"
    )

    r1 = follow_cross_reference(doc, "Section 4(b)")
    assert r1.success and "Receiving Party" in r1.results[0]["text"]

    r2 = follow_cross_reference(doc, "Article 99")
    assert not r2.success and r2.error == "NOT_FOUND"

    r3 = follow_cross_reference(doc, "")
    assert not r3.success and r3.error == "EMPTY_REFERENCE"

    r4 = follow_cross_reference(doc, "!!!not a reference!!!")
    assert not r4.success and r4.error == "MALFORMED_REFERENCE"

    r5 = get_definition(doc, "Confidential Information")
    assert r5.success and "means any and all information" in r5.results[0]["text"]

    r6 = get_definition(doc, "Nonexistent Term")
    assert not r6.success and r6.error == "NOT_FOUND"

    r7 = get_more_candidates(doc, "governing law", already_revealed_count=0)
    assert r7.success  # small doc, but at least the initial window returns something or exhausts cleanly

    r8 = get_more_candidates(doc, "governing law", already_revealed_count=20)
    assert not r8.success and r8.error == "POOL_EXHAUSTED"

    print("pipeline/agent_tools_v2.py self-check OK")


if __name__ == "__main__":
    demo()
