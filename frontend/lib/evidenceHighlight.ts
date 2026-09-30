import type { RetrievedChunk } from "./api";

export type HighlightSpan = { text: string; matched: boolean };

export type EvidenceContext = {
  spans: HighlightSpan[];
  text: string;
};

export type TechnicalChunkInfo = {
  chunkId: number;
  rank: number;
  rawRerankerScore: number;
  text: string;
};

// Splits `chunkText` around the first EXACT verbatim occurrence of any of
// `quotes`. No fuzzy/paraphrase matching - if no quote appears verbatim,
// returns null and the caller must not fabricate a highlight.
export function highlightVerbatimQuote(chunkText: string, quotes: string[]): HighlightSpan[] | null {
  for (const quote of quotes) {
    if (!quote) continue;
    const idx = chunkText.indexOf(quote);
    if (idx === -1) continue;
    const spans: HighlightSpan[] = [];
    if (idx > 0) spans.push({ text: chunkText.slice(0, idx), matched: false });
    spans.push({ text: chunkText.slice(idx, idx + quote.length), matched: true });
    if (idx + quote.length < chunkText.length) {
      spans.push({ text: chunkText.slice(idx + quote.length), matched: false });
    }
    return spans;
  }
  return null;
}

// Derives a compact source-only window: at most two sentence/clause units
// before and after the exact quote. Semicolons and paragraph breaks count as
// boundaries because NDA clauses frequently use long semicolon-separated lists.
export function buildVerbatimContext(
  sourceText: string,
  quote: string,
  surroundingUnits = 2,
): EvidenceContext | null {
  if (!quote) return null;
  const quoteStart = sourceText.indexOf(quote);
  if (quoteStart === -1) return null;

  const starts = sentenceStarts(sourceText);
  const quoteEnd = quoteStart + quote.length - 1;
  const firstUnit = unitIndexAt(starts, quoteStart);
  const lastUnit = unitIndexAt(starts, quoteEnd);
  const contextFirst = Math.max(0, firstUnit - surroundingUnits);
  const contextLast = Math.min(starts.length - 1, lastUnit + surroundingUnits);
  const rawStart = starts[contextFirst];
  const rawEnd = contextLast + 1 < starts.length ? starts[contextLast + 1] : sourceText.length;
  const rawContext = sourceText.slice(rawStart, rawEnd);
  const leadingWhitespace = rawContext.length - rawContext.trimStart().length;
  const contextText = rawContext.trim();
  const relativeQuoteStart = quoteStart - rawStart - leadingWhitespace;

  return {
    text: contextText,
    spans: splitAroundMatch(contextText, relativeQuoteStart, quote.length),
  };
}

export function findVerbatimSourceChunk(
  quote: string,
  chunks: RetrievedChunk[],
): RetrievedChunk | null {
  return chunks.find((chunk) => chunk.text.includes(quote)) ?? null;
}

export function formatSourceProvenance(chunk: RetrievedChunk | null): string | null {
  return chunk
    ? `Document text · Chunk ${chunk.chunk_id + 1} · Retrieval rank #${chunk.rank}`
    : null;
}

export function technicalChunkInfo(chunks: RetrievedChunk[]): TechnicalChunkInfo[] {
  return [...chunks]
    .sort((a, b) => a.rank - b.rank)
    .map((chunk) => ({
      chunkId: chunk.chunk_id,
      rank: chunk.rank,
      rawRerankerScore: chunk.reranker_score,
      text: chunk.text,
    }));
}

function sentenceStarts(text: string): number[] {
  const starts = [0];
  const boundary = /(?:[.!?;]+["')\]]*\s+|\n{2,})/g;
  for (const match of text.matchAll(boundary)) {
    const next = (match.index ?? 0) + match[0].length;
    if (next < text.length && starts[starts.length - 1] !== next) starts.push(next);
  }
  return starts;
}

function unitIndexAt(starts: number[], position: number): number {
  let index = 0;
  for (let i = 1; i < starts.length && starts[i] <= position; i += 1) index = i;
  return index;
}

function splitAroundMatch(text: string, start: number, length: number): HighlightSpan[] {
  const spans: HighlightSpan[] = [];
  if (start > 0) spans.push({ text: text.slice(0, start), matched: false });
  spans.push({ text: text.slice(start, start + length), matched: true });
  if (start + length < text.length) {
    spans.push({ text: text.slice(start + length), matched: false });
  }
  return spans;
}
