import { useState } from "react";
import { RetrievedChunk } from "@/lib/api";
import { selectEvidenceDisplay } from "@/lib/evidenceDisplay";
import { highlightVerbatimQuote } from "@/lib/evidenceHighlight";

const NOT_MENTIONED_NOTE = "No explicit supporting or contradicting provision was identified.";
const VALIDATION_FAILED_NOTE = "Evidence could not be source-validated — human review required.";
const RETRIEVED_CHUNK_EXPLAINER =
  "This is the larger retrieved context that contained the selected evidence above.";
const NO_VERBATIM_HIGHLIGHT_NOTE = "Selected evidence could not be highlighted verbatim in this chunk.";

// Renders the model's VALIDATED evidence quote(s) (`evidence`) as the primary
// answer. `retrievedChunks` is the RAG retrieval context - broader, ranked,
// used only as debug/context, and must never substitute for `evidence`.
export function EvidenceSection({
  label,
  evidence,
  sourceValid,
  retrievedChunks,
}: {
  label: string;
  evidence: string[];
  sourceValid: boolean | null;
  retrievedChunks: RetrievedChunk[];
}) {
  const [showRetrieval, setShowRetrieval] = useState(false);
  const display = selectEvidenceDisplay(label, evidence, sourceValid);
  const quotesForHighlight = display.kind === "quotes" ? display.quotes : [];

  return (
    <div className="mt-4 flex flex-col gap-2.5">
      <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#7c7373]">
        Evidence used for decision
      </span>
      {display.kind === "not-mentioned" && <p className="text-sm text-[#6b7280]">{NOT_MENTIONED_NOTE}</p>}
      {display.kind === "validation-failed" && (
        <p className="text-sm text-amber-700 dark:text-amber-400">{VALIDATION_FAILED_NOTE}</p>
      )}
      {display.kind === "no-evidence" && (
        <p className="text-sm text-[#6b7280]">No evidence quote was returned for this result.</p>
      )}
      {display.kind === "quotes" &&
        display.quotes.map((quote, i) => (
          <div key={i} className="flex flex-col gap-1">
            {display.quotes.length > 1 && (
              <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9aa3af]">
                Evidence {i + 1}
              </span>
            )}
            <blockquote className="result-card__evidence-quote font-mono text-xs leading-relaxed text-[#29313d]">
              {quote}
            </blockquote>
          </div>
        ))}

      {retrievedChunks.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowRetrieval((shown) => !shown)}
            aria-expanded={showRetrieval}
            className="mt-1 inline-flex items-center gap-1.5 self-start text-xs font-semibold text-slate-500 underline decoration-dotted underline-offset-4 transition-colors hover:text-slate-800"
          >
            {showRetrieval ? "Hide retrieved source chunk" : "Retrieved source chunk"}
            <span aria-hidden className="text-[10px]">{showRetrieval ? "▲" : "▼"}</span>
          </button>
          {showRetrieval && (
            <div className="flex flex-col gap-2.5">
              <p className="text-[11px] text-[#9aa3af]">{RETRIEVED_CHUNK_EXPLAINER}</p>
              {[...retrievedChunks]
                .sort((a, b) => a.rank - b.rank)
                .map((chunk) => {
                  const spans = highlightVerbatimQuote(chunk.text, quotesForHighlight);
                  return (
                    <div key={chunk.chunk_id} className="result-card__evidence-quote opacity-90">
                      <blockquote className="font-mono text-[11px] leading-relaxed text-[#5b6472]">
                        {spans
                          ? spans.map((span, i) =>
                              span.matched ? (
                                <mark key={i} className="bg-amber-200/70 text-[#29313d] dark:bg-amber-500/40">
                                  {span.text}
                                </mark>
                              ) : (
                                <span key={i}>{span.text}</span>
                              ),
                            )
                          : chunk.text}
                      </blockquote>
                      {!spans && quotesForHighlight.length > 0 && (
                        <p className="mt-1 text-[10px] italic text-[#9aa3af]">{NO_VERBATIM_HIGHLIGHT_NOTE}</p>
                      )}
                      <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-black/5 pt-2 text-[11px] text-[#6b7280]">
                        <span>Retrieved chunk {chunk.chunk_id + 1} · Rank #{chunk.rank}</span>
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
