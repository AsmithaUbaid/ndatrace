import { useState } from "react";
import { RequirementResult, ReviewDecision } from "@/lib/api";
import { NOT_MENTIONED_MESSAGE } from "@/lib/evidenceDisplay";
import { isLowConfidence, toVerdict, VERDICT_COLORS, VERDICT_ICONS, VERDICT_TITLES } from "@/lib/verdict";
import { EvidenceSection } from "@/components/EvidenceSection";
import { ReviewMetadata } from "@/components/ReviewMetadata";

const DECISION_LABELS: Record<ReviewDecision, string> = {
  approved: "Approved",
  overridden: "Overridden",
  rejected: "Rejected",
};

// The AI's classification is never final on its own - this is the reviewer's
// recorded authority to intervene, persisted server-side (backend/database.py
// review_decisions), separate from and not implied by needs_human_review.
function DecisionControls({
  r,
  onDecide,
}: {
  r: RequirementResult;
  onDecide: (itemId: number, decision: ReviewDecision, note?: string) => Promise<void>;
}) {
  const [note, setNote] = useState("");
  const [showNote, setShowNote] = useState(false);
  const [pending, setPending] = useState<ReviewDecision | null>(null);
  const [failed, setFailed] = useState(false);

  if (r.id == null) return null; // not yet persisted (e.g. single-requirement /api/review path)

  async function decide(decision: ReviewDecision) {
    setPending(decision);
    setFailed(false);
    try {
      await onDecide(r.id as number, decision, note.trim() || undefined);
      setNote("");
      setShowNote(false);
    } catch {
      setFailed(true);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="mt-4 border-t border-zinc-100 pt-3 dark:border-zinc-800">
      {r.decision ? (
        <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-600 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300">
          <span className="font-semibold">Reviewer decision: {DECISION_LABELS[r.decision]}</span>
          {r.decision_note && <p className="mt-1 leading-5">{r.decision_note}</p>}
          <p className="mt-1 text-[11px] text-zinc-400 dark:text-zinc-500">
            You can still change this decision below.
          </p>
        </div>
      ) : (
        <p className="mb-2 text-xs font-medium text-zinc-500 dark:text-zinc-400">
          Human decision required before acting on this result.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => decide("approved")}
          disabled={pending !== null}
          className="rounded-md border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 disabled:opacity-50 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300"
        >
          {pending === "approved" ? "Saving…" : "Approve"}
        </button>
        <button
          onClick={() => decide("overridden")}
          disabled={pending !== null}
          className="rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 hover:bg-amber-100 disabled:opacity-50 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300"
        >
          {pending === "overridden" ? "Saving…" : "Override"}
        </button>
        <button
          onClick={() => decide("rejected")}
          disabled={pending !== null}
          className="rounded-md border border-rose-300 bg-rose-50 px-2.5 py-1 text-xs font-semibold text-rose-800 hover:bg-rose-100 disabled:opacity-50 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300"
        >
          {pending === "rejected" ? "Saving…" : "Reject"}
        </button>
        <button
          onClick={() => setShowNote((v) => !v)}
          className="text-xs font-medium text-zinc-500 underline underline-offset-2 hover:text-zinc-700 dark:text-zinc-400"
        >
          {showNote ? "Hide note" : "Add note"}
        </button>
      </div>
      {showNote && (
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Why? (optional, recorded with the decision)"
          rows={2}
          className="mt-2 w-full rounded-md border border-zinc-200 px-2 py-1.5 text-xs text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
        />
      )}
      {failed && (
        <p className="mt-1 text-xs font-medium text-rose-600">Could not save decision. Try again.</p>
      )}
    </div>
  );
}

export function RequirementCard({
  r,
  onDecide,
}: {
  r: RequirementResult;
  onDecide?: (itemId: number, decision: ReviewDecision, note?: string) => Promise<void>;
}) {
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

        {r.security_review_required && (
          <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900">
            <p className="font-bold uppercase tracking-wide">Security review required</p>
            <p className="mt-1 leading-5">Potential instruction-like content was detected in the submitted agreement. Do not accept this result without human review.</p>
          </div>
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

        {onDecide && <DecisionControls r={r} onDecide={onDecide} />}
      </div>
    </li>
  );
}
