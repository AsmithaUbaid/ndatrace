import { RequirementResult } from "@/lib/api";
import {
  FilterKey,
  needsAttention,
  toVerdict,
  VERDICT_COLORS,
  VERDICT_TITLES_PLURAL,
  Verdict,
} from "@/lib/verdict";

export function ResultsSummaryBar({
  results,
  activeFilter,
  onSelect,
}: {
  results: RequirementResult[];
  activeFilter: FilterKey;
  onSelect: (filter: FilterKey) => void;
}) {
  const counted = results.filter((r) => !r.error);
  const counts: Record<Verdict, number> = { contradiction: 0, entailment: 0, notmentioned: 0 };
  for (const r of counted) counts[toVerdict(r.label)]++;
  const issues = counted.filter(needsAttention).length;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
        {issues === 0
          ? `No issues found across ${counted.length} requirement${counted.length === 1 ? "" : "s"}`
          : `${issues} issue${issues === 1 ? "" : "s"} found across ${counted.length} requirement${
              counted.length === 1 ? "" : "s"
            }`}
      </p>
      <div className="flex flex-wrap gap-2">
        {(["contradiction", "entailment", "notmentioned"] as Verdict[]).map((v) => (
          <button
            key={v}
            onClick={() => onSelect(activeFilter === v ? "all" : v)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
              activeFilter === v ? VERDICT_COLORS[v].chipActive : VERDICT_COLORS[v].chip
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                activeFilter === v ? VERDICT_COLORS[v].dotActive : VERDICT_COLORS[v].dot
              }`}
              aria-hidden
            />
            {counts[v]} {VERDICT_TITLES_PLURAL[v]}
          </button>
        ))}
      </div>
    </div>
  );
}
