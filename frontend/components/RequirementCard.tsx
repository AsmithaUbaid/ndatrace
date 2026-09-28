import { RequirementResult } from "@/lib/api";
import { NOT_MENTIONED_MESSAGE } from "@/lib/evidenceDisplay";
import { isLowConfidence, toVerdict, VERDICT_COLORS, VERDICT_ICONS, VERDICT_TITLES } from "@/lib/verdict";
import { EvidenceSection } from "@/components/EvidenceSection";
import { ReviewMetadata } from "@/components/ReviewMetadata";

export function RequirementCard({ r }: { r: RequirementResult }) {
  if (r.error || !r.label) {
    return (
      <li className="overflow-hidden rounded-lg border border-amber-300 bg-amber-50 shadow-sm dark:border-amber-800 dark:bg-amber-950/40">
        <div className="h-[3px] bg-amber-400 dark:bg-amber-600" />
        <div className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <span className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
              {r.hypothesis_text}{" "}
              <span className="text-zinc-400 dark:text-zinc-500">({r.hypothesis_id})</span>
            </span>
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800 dark:border-amber-700 dark:bg-amber-900 dark:text-amber-300">
              {"⚠"} Failed
            </span>
          </div>
          <p className="mt-2.5 text-sm text-amber-800 dark:text-amber-300">
            Could not get a result for this requirement: {r.review_reason ?? r.error ?? "Human review is required."}
          </p>
          <p className="mt-1 text-xs text-amber-700 dark:text-amber-500">
            The other requirements in this review completed normally; only this one failed.
          </p>
        </div>
      </li>
    );
  }

  const verdict = toVerdict(r.label);
  const colors = VERDICT_COLORS[verdict];
  const lowConfidence = isLowConfidence(r);
  const confidencePercent = r.confidence == null ? null : Math.round(r.confidence * 100);

  return (
    <li
      className="result-card"
      data-verdict={verdict}
    >
      <div className={`result-card__accent ${colors.stripe}`} />
      <div className="result-card__content p-5 sm:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h3 className="text-base font-semibold leading-snug tracking-[-0.01em] text-[#1f2937]">
              {r.hypothesis_text}
            </h3>
            <p className="mt-1 text-xs font-medium text-[#6b7280]">({r.hypothesis_id})</p>
          </div>
          <span
            className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold shadow-sm ${colors.badge}`}
          >
            <span aria-hidden>{VERDICT_ICONS[verdict]}</span>
            {VERDICT_TITLES[verdict]}
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-[#6b7280]">
          {r.confidence_available && confidencePercent != null && (
            <div
              className="flex items-center gap-2"
              role="progressbar"
              aria-label="Confidence"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={confidencePercent}
            >
              <span className="result-card__confidence-track" aria-hidden>
                <span
                  className="result-card__confidence-fill"
                  style={{ width: `${Math.min(100, Math.max(0, confidencePercent))}%` }}
                />
              </span>
              <span className="font-semibold tabular-nums text-[#4b5563]">{confidencePercent}%</span>
            </div>
          )}
          <span>Reviewed against retrieved evidence chunks</span>
        </div>

        {lowConfidence && (
          <p className="mt-2 text-xs font-medium text-amber-700 dark:text-amber-400">
            {"⚠"} Low confidence, consider manual review
          </p>
        )}

        {r.needs_human_review && (
          <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800">
            {"⚠"} Human review required{r.review_reason ? `: ${r.review_reason}` : ""}
          </p>
        )}

        {(r.explanation || r.label === "NotMentioned") && (
          <p className="mt-4 text-sm leading-6 text-[#4b5563]">
            {r.label === "NotMentioned" ? NOT_MENTIONED_MESSAGE : r.explanation}
          </p>
        )}

        <ReviewMetadata
          costUsd={r.cost_usd}
          latencyMs={r.latency_ms}
          retrievedChunks={r.retrieved_chunks}
          label={r.label}
          evidence={r.evidence}
          sourceValid={r.source_valid}
        />

        <EvidenceSection
          label={r.label}
          evidence={r.evidence}
          sourceValid={r.source_valid}
          retrievedChunks={r.retrieved_chunks}
        />
      </div>
    </li>
  );
}
