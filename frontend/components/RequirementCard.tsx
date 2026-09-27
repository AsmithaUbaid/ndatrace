import { useState } from "react";
import { RequirementResult } from "@/lib/api";
import { isLowConfidence, toVerdict, VERDICT_COLORS, VERDICT_ICONS, VERDICT_TITLES } from "@/lib/verdict";

export function RequirementCard({ r }: { r: RequirementResult }) {
  const [showDetails, setShowDetails] = useState(false);

  if (r.error) {
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
            Could not get a result for this requirement: {r.error}
          </p>
          <p className="mt-1 text-xs text-amber-700 dark:text-amber-500">
            The other requirements in this review completed normally — only this one failed.
          </p>
        </div>
      </li>
    );
  }

  const verdict = toVerdict(r.label);
  const colors = VERDICT_COLORS[verdict];
  const lowConfidence = isLowConfidence(r);

  return (
    <li
      className={`overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900 ${colors.tint}`}
    >
      <div className={`h-[3px] ${colors.stripe}`} />
      <div className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <span className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
            {r.hypothesis_text}{" "}
            <span className="text-zinc-400 dark:text-zinc-500">({r.hypothesis_id})</span>
          </span>
          <span
            className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${colors.badge}`}
          >
            <span aria-hidden>{VERDICT_ICONS[verdict]}</span>
            {VERDICT_TITLES[verdict]}
          </span>
        </div>

        <div className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs text-zinc-500 dark:text-zinc-400">
          <span>Confidence: {Math.round(r.confidence * 100)}%</span>
          <span className={r.agent_used ? "font-medium text-amber-700 dark:text-amber-400" : ""}>
            {r.agent_used ? "↑ Escalated for deeper review" : "Answered directly"}
          </span>
          <button
            onClick={() => setShowDetails((s) => !s)}
            className="text-zinc-400 underline decoration-dotted hover:text-zinc-600 dark:text-zinc-500 dark:hover:text-zinc-300"
          >
            {showDetails ? "Hide details" : "Details"}
          </button>
        </div>

        {lowConfidence && (
          <p className="mt-2 text-xs font-medium text-amber-700 dark:text-amber-400">
            {"⚠"} Low confidence — consider manual review
          </p>
        )}

        {r.explanation && (
          <p className="mt-2.5 text-sm leading-relaxed text-zinc-700 dark:text-zinc-300">{r.explanation}</p>
        )}

        {r.evidence.length > 0 && (
          <div className="mt-2.5 flex flex-col gap-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
              Evidence Retrieved
            </span>
            {r.evidence.map((e, i) => (
              <blockquote
                key={i}
                className={`rounded-md border-l-4 px-3 py-2 font-mono text-xs leading-relaxed text-zinc-700 dark:text-zinc-200 ${colors.evidenceBorder}`}
              >
                {e}
              </blockquote>
            ))}
          </div>
        )}

        {showDetails && (
          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-zinc-100 pt-2.5 text-xs text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
            <span>Cost: ${r.cost_usd.toFixed(6)}</span>
            <span>Latency: {Math.round(r.latency_ms)}ms</span>
            {r.agent_used && <span>Agent steps: {r.agent_steps}</span>}
          </div>
        )}
      </div>
    </li>
  );
}
