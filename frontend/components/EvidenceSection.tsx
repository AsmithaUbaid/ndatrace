import { RetrievedChunk } from "@/lib/api";
import { debugDetailsEnabled } from "@/lib/debugDetails";
import { selectEvidenceDisplay } from "@/lib/evidenceDisplay";
import {
  buildVerbatimContext,
  findVerbatimSourceChunk,
  formatSourceProvenance,
  technicalChunkInfo,
} from "@/lib/evidenceHighlight";

const VALIDATION_FAILED_NOTE = "Evidence could not be source-validated — human review required.";
const CONTEXT_UNAVAILABLE_NOTE = "Source context unavailable for this quote.";

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
  const display = selectEvidenceDisplay(label, evidence, sourceValid);
  const showDebugDetails = debugDetailsEnabled(process.env.NEXT_PUBLIC_SHOW_DEBUG_DETAILS);

  return (
    <div className="mt-4 flex flex-col gap-2.5">
      {display.kind !== "not-mentioned" && (
        <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#7c7373]">
          Evidence used for decision
        </span>
      )}
      {display.kind === "validation-failed" && (
        <p className="text-sm text-amber-700 dark:text-amber-400">{VALIDATION_FAILED_NOTE}</p>
      )}
      {display.kind === "no-evidence" && (
        <p className="text-sm text-[#6b7280]">No evidence quote was returned for this result.</p>
      )}
      {display.kind === "quotes" &&
        display.quotes.map((quote, i) => (
          <EvidenceQuote
            key={`${i}-${quote.slice(0, 24)}`}
            quote={quote}
            index={i}
            showIndex={display.quotes.length > 1}
            retrievedChunks={retrievedChunks}
          />
        ))}

      {showDebugDetails && retrievedChunks.length > 0 && (
        <DebugDetails retrievedChunks={retrievedChunks} />
      )}
    </div>
  );
}

function EvidenceQuote({
  quote,
  index,
  showIndex,
  retrievedChunks,
}: {
  quote: string;
  index: number;
  showIndex: boolean;
  retrievedChunks: RetrievedChunk[];
}) {
  const source = findVerbatimSourceChunk(quote, retrievedChunks);
  const provenance = formatSourceProvenance(source);
  const context = source ? buildVerbatimContext(source.text, quote, 2) : null;

  return (
    <section className="rounded-lg border border-black/5 bg-white/55 p-3 shadow-[0_1px_2px_rgba(15,23,42,0.03)]">
      {showIndex && (
        <span className="text-[10px] font-semibold uppercase tracking-wide text-[#9aa3af]">
          Evidence {index + 1}
        </span>
      )}
      <blockquote className="mt-1 font-mono text-xs leading-relaxed text-[#29313d]">{quote}</blockquote>

      <div className="mt-3 border-t border-black/5 pt-2">
        <span className="block text-[9px] font-bold uppercase tracking-[0.13em] text-[#9aa3af]">Source</span>
        <span className="mt-0.5 block text-xs font-medium text-[#5b6472]">
          {provenance ?? "Source unavailable"}
        </span>
      </div>

      <details className="group mt-2">
        <summary className="cursor-pointer list-none text-xs font-semibold text-slate-500 underline decoration-dotted underline-offset-4 transition-colors hover:text-slate-800">
          <span className="group-open:hidden">View source context ›</span>
          <span className="hidden group-open:inline">Hide source context</span>
        </summary>
        <div className="mt-2 rounded-md border border-slate-200/80 bg-slate-50/80 px-3 py-2.5">
          {context ? (
            <blockquote className="font-mono text-[11px] leading-relaxed text-[#5b6472]">
              {context.spans.map((span, spanIndex) =>
                span.matched ? (
                  <mark key={spanIndex} className="rounded-sm bg-amber-200/70 px-0.5 text-[#29313d]">
                    {span.text}
                  </mark>
                ) : (
                  <span key={spanIndex}>{span.text}</span>
                ),
              )}
            </blockquote>
          ) : (
            <p className="text-xs text-[#7c8490]">{CONTEXT_UNAVAILABLE_NOTE}</p>
          )}
        </div>
      </details>
    </section>
  );
}

function DebugDetails({ retrievedChunks }: { retrievedChunks: RetrievedChunk[] }) {
  return (
    <details className="group mt-1 border-t border-black/5 pt-3">
      <summary className="cursor-pointer list-none text-xs font-semibold text-slate-400 underline decoration-dotted underline-offset-4 transition-colors hover:text-slate-700">
        <span className="group-open:hidden">Debug details ›</span>
        <span className="hidden group-open:inline">Hide debug details</span>
      </summary>
      <div className="mt-2 flex flex-col gap-2.5 rounded-lg border border-slate-200 bg-slate-50/70 p-3">
        {technicalChunkInfo(retrievedChunks).map((chunk) => (
          <div key={chunk.chunkId} className="rounded-md border border-slate-200/80 bg-white/75 p-2.5">
            <div className="flex flex-wrap justify-between gap-x-3 gap-y-1 text-[10px] text-slate-500">
              <span>Chunk ID {chunk.chunkId} · Retrieval rank #{chunk.rank}</span>
              <span className="font-mono">Raw reranker score: {chunk.rawRerankerScore.toFixed(3)}</span>
            </div>
            <blockquote className="mt-2 border-t border-slate-100 pt-2 font-mono text-[10px] leading-relaxed text-slate-500">
              {chunk.text}
            </blockquote>
          </div>
        ))}
      </div>
    </details>
  );
}
