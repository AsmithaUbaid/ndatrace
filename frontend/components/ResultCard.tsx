import { useState } from "react";
import { FinalReviewResponse } from "@/lib/api";
import { toVerdict, VERDICT_COLORS, VERDICT_ICONS, VERDICT_TITLES } from "@/lib/verdict";

const NOTMENTIONED_NOTE =
  "No explicit supporting or contradicting provision was identified in the agreement. This does not mean the NDA definitely omits the requirement; the relevant language may simply not have been found.";

// The final architecture has no calibrated confidence score to show (the
// frozen prompt returns only {label, evidence}) - this card never invents
// one, and it never claims E15's routing research is a validated
// production escalation mechanism. `needs_human_review` only ever comes
// from a real deterministic condition (parse failure, non-source-valid
// evidence, provider error), set server-side in pipeline/final_review.py.
export function ResultCard({ result }: { result: FinalReviewResponse }) {
  const [showDetails, setShowDetails] = useState(false);

  if (!result.label) {
    return (
      <div className="overflow-hidden rounded-lg border border-amber-300 bg-amber-50 shadow-sm dark:border-amber-800 dark:bg-amber-950/40">
        <div className="h-[3px] bg-amber-400 dark:bg-amber-600" />
        <div className="p-5">
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800 dark:border-amber-700 dark:bg-amber-900 dark:text-amber-300">
            Human review required
          </span>
          <p className="mt-2.5 text-sm text-amber-800 dark:text-amber-300">
            {result.review_reason ?? "The system could not produce a result for this request."}
          </p>
        </div>
      </div>
    );
  }

  const verdict = toVerdict(result.label);
  const colors = VERDICT_COLORS[verdict];

  return (
    <div className="result-card" data-verdict={verdict}>
      <div className={`result-card__accent ${colors.stripe}`} />
      <div className="result-card__content p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold shadow-sm ${colors.badge}`}>
            <span aria-hidden>{VERDICT_ICONS[verdict]}</span>
            {VERDICT_TITLES[verdict]}
          </span>
          <SourceValidBadge validated={result.source_valid} label={result.label} />
        </div>

        {result.needs_human_review && (
          <div className="mt-3 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
            {"⚠"} Human review required{result.review_reason ? `: ${result.review_reason}` : ""}
          </div>
        )}

        <p className="mt-4 text-sm leading-6 text-[#4b5563]">
          {result.label === "NotMentioned" ? NOTMENTIONED_NOTE : result.explanation}
        </p>

        {result.evidence.length > 0 && (
          <div className="result-card__evidence-panel mt-4 flex flex-col gap-2.5">
            <span className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#7c7373]">
              Supporting clause{result.evidence.length > 1 ? "s" : ""} (verbatim from the NDA)
            </span>
            {result.evidence.map((e, i) => (
              <blockquote
                key={i}
                className="result-card__evidence-quote font-mono text-xs leading-relaxed text-[#29313d]"
              >
                {e}
              </blockquote>
            ))}
            {result.sources.length > 0 && (
              <div className="flex flex-wrap gap-x-3 gap-y-1 border-t border-black/5 pt-2 text-[11px] text-[#6b7280]">
                {result.sources.map((source) => (
                  <span key={source.chunk_id}>
                    Source clause {source.chunk_id + 1} · rank {source.rank}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="mt-4 rounded-md bg-zinc-50 px-3 py-2 text-xs text-zinc-500 dark:bg-zinc-800/60 dark:text-zinc-400">
          Decision support only. Final NDA review remains with the human reviewer.
        </div>

        <button
          onClick={() => setShowDetails((s) => !s)}
          className="mt-3 text-xs text-zinc-400 underline decoration-dotted hover:text-zinc-600 dark:text-zinc-500 dark:hover:text-zinc-300"
        >
          {showDetails ? "Hide system details" : "System details"}
        </button>
        {showDetails && (
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 border-t border-zinc-100 pt-2.5 text-xs text-zinc-500 dark:border-zinc-800 dark:text-zinc-400 sm:grid-cols-3">
            <Detail label="Model" value={result.model} />
            <Detail label="Latency" value={result.latency_ms != null ? `${Math.round(result.latency_ms)} ms` : "–"} />
            <Detail label="Input tokens" value={result.input_tokens ?? "–"} />
            <Detail label="Output tokens" value={result.output_tokens ?? "–"} />
            <Detail label="Est. cost" value={result.estimated_cost_usd != null ? `$${result.estimated_cost_usd.toFixed(6)}` : "–"} />
            <Detail label="Trace ID" value={result.trace_id} mono />
            <Detail label="Clauses retrieved" value={result.retrieved_chunks.length} />
          </dl>
        )}
      </div>
    </div>
  );
}

function Detail({ label, value, mono }: { label: string; value: string | number; mono?: boolean }) {
  return (
    <div>
      <dt className="text-zinc-400 dark:text-zinc-500">{label}</dt>
      <dd className={mono ? "font-mono text-[11px] text-zinc-600 dark:text-zinc-300" : "text-zinc-700 dark:text-zinc-200"}>{value}</dd>
    </div>
  );
}

function SourceValidBadge({ validated, label }: { validated: boolean | null; label: string }) {
  if (label === "NotMentioned" && validated === null) {
    return <span className="text-xs text-zinc-400 dark:text-zinc-500">No evidence expected</span>;
  }
  if (validated === true) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-zinc-50 px-2.5 py-0.5 text-xs font-medium text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
        ✓ Verified in source
      </span>
    );
  }
  if (validated === false) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
        Validation failed
      </span>
    );
  }
  return null;
}
