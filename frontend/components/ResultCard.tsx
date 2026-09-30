import { FinalReviewResponse } from "@/lib/api";
import { NOT_MENTIONED_MESSAGE } from "@/lib/evidenceDisplay";
import { EvidenceSection } from "@/components/EvidenceSection";
import { ReviewMetadata } from "@/components/ReviewMetadata";
import { toVerdict, VERDICT_COLORS, VERDICT_ICONS, VERDICT_TITLES } from "@/lib/verdict";

// The final architecture has no calibrated confidence score to show (the
// frozen prompt returns only {label, evidence}) - this card never invents
// one, and it never claims E15's routing research is a validated
// production escalation mechanism. `needs_human_review` only ever comes
// from a real deterministic condition (parse failure, non-source-valid
// evidence, provider error), set server-side in pipeline/final_review.py.
export function ResultCard({ result }: { result: FinalReviewResponse }) {
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

        {result.security_review_required && (
          <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900">
            <p className="font-bold uppercase tracking-wide">Security review required</p>
            <p className="mt-1 leading-5">Potential instruction-like content was detected in the submitted agreement. Human verification is mandatory.</p>
          </div>
        )}

        <p className="mt-4 text-sm leading-6 text-[#4b5563]">
          {result.label === "NotMentioned" ? NOT_MENTIONED_MESSAGE : result.explanation}
        </p>

        <ReviewMetadata
          costUsd={result.estimated_cost_usd}
          latencyMs={result.latency_ms}
          retrievedChunks={result.retrieved_chunks}
          label={result.label}
          evidence={result.evidence}
          sourceValid={result.source_valid}
        />

        <EvidenceSection
          label={result.label}
          evidence={result.evidence}
          sourceValid={result.source_valid}
          retrievedChunks={result.retrieved_chunks}
        />

        <div className="mt-4 rounded-md bg-zinc-50 px-3 py-2 text-xs text-zinc-500 dark:bg-zinc-800/60 dark:text-zinc-400">
          Decision support only. Final NDA review remains with the human reviewer.
        </div>

      </div>
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
