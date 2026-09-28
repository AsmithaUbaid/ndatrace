export type HighlightSpan = { text: string; matched: boolean };

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
