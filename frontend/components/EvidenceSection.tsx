import { useState } from "react";
import { RetrievedChunk } from "@/lib/api";
import { selectEvidenceDisplay } from "@/lib/evidenceDisplay";

const NOT_MENTIONED_NOTE = "No explicit supporting or contradicting provision was identified.";
const VALIDATION_FAILED_NOTE = "Evidence could not be source-validated — human review required.";

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

  return (
    <div className="mt-4 flex flex-col gap-2.5">
      <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#7c7373]">
        Evidence
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
          <blockquote
            key={i}
            className="result-card__evidence-quote font-mono text-xs leading-relaxed text-[#29313d]"
          >
            {quote}
          </blockquote>
        ))}

      {retrievedChunks.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setShowRetrieval((shown) => !shown)}
            aria-expanded={showRetrieval}
            className="mt-1 inline-flex items-center gap-1.5 self-start text-xs font-semibold text-slate-500 underline decoration-dotted underline-offset-4 transition-colors hover:text-slate-800"
          >
            {showRetrieval ? "Hide retrieval details" : "Retrieval details"}
            <span aria-hidden className="text-[10px]">{showRetrieval ? "▲" : "▼"}</span>
          </button>
          {showRetrieval && (
            <div className="flex flex-col gap-2.5">
              {[...retrievedChunks]
                .sort((a, b) => a.rank - b.rank)
                .map((chunk) => (
                  <div key={chunk.chunk_id} className="result-card__evidence-quote">
                    <blockquote className="font-mono text-xs leading-relaxed text-[#29313d]">
                      {chunk.text}
                    </blockquote>
                    <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-t border-black/5 pt-2 text-[11px] text-[#6b7280]">
                      <span>Retrieved chunk {chunk.chunk_id + 1} · Rank #{chunk.rank}</span>
                      <span className="font-mono text-[#8a9099]">
                        Raw reranker score: {chunk.reranker_score.toFixed(3)}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
