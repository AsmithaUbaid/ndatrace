import { RequirementResult } from "@/lib/api";
import { ConfidenceBar } from "./ConfidenceBar";
import { LabelBadge } from "./LabelBadge";

export function RequirementCard({ r }: { r: RequirementResult }) {
  if (r.error) {
    return (
      <li className="rounded-lg border border-amber-300 bg-amber-50 p-4 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <span className="text-sm font-medium text-zinc-800">
            {r.hypothesis_text} <span className="text-zinc-400">({r.hypothesis_id})</span>
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border border-amber-300 bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
            {"⚠"} Failed
          </span>
        </div>
        <p className="mt-2.5 text-sm text-amber-800">
          Could not get a result for this requirement: {r.error}
        </p>
        <p className="mt-1 text-xs text-amber-700">
          The other requirements in this review completed normally &mdash; only this one failed.
        </p>
      </li>
    );
  }

  const isContradiction = r.label === "Contradiction";

  return (
    <li
      className={`rounded-lg border bg-white p-4 shadow-sm ${
        isContradiction ? "border-red-200 border-l-4 border-l-red-400" : "border-zinc-200"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <span className="text-sm font-medium text-zinc-800">
          {r.hypothesis_text} <span className="text-zinc-400">({r.hypothesis_id})</span>
        </span>
        <LabelBadge label={r.label} />
      </div>

      <div className="mt-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5">
        <ConfidenceBar confidence={r.confidence} />
        <span
          className={`text-xs ${r.agent_used ? "font-medium text-amber-700" : "text-zinc-500"}`}
        >
          {r.agent_used
            ? `⚡ Agent investigated (${r.agent_steps} step${r.agent_steps === 1 ? "" : "s"})`
            : "Direct answer, no escalation"}
        </span>
        <span className="text-xs text-zinc-400">${r.cost_usd.toFixed(6)}</span>
      </div>

      {r.explanation && <p className="mt-2.5 text-sm leading-relaxed text-zinc-700">{r.explanation}</p>}

      {r.evidence.length > 0 && (
        <div className="mt-2.5 flex flex-col gap-1.5 border-t border-zinc-100 pt-2.5">
          <span className="text-xs font-medium uppercase tracking-wide text-zinc-400">Evidence</span>
          {r.evidence.map((e, i) => (
            <blockquote key={i} className="border-l-2 border-zinc-300 pl-2.5 text-xs italic text-zinc-600">
              &ldquo;{e}&rdquo;
            </blockquote>
          ))}
        </div>
      )}
    </li>
  );
}
