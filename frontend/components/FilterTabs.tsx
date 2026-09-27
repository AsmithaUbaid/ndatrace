import { RequirementResult } from "@/lib/api";
import { FilterKey, needsAttention, toVerdict, Verdict } from "@/lib/verdict";

const TABS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "contradiction", label: "Contradictions" },
  { key: "entailment", label: "Entailments" },
  { key: "notmentioned", label: "Not Mentioned" },
  { key: "needs-attention", label: "⚠ Needs Attention" },
];

export function countForFilter(results: RequirementResult[], key: FilterKey): number {
  const counted = results.filter((r) => !r.error);
  if (key === "all") return counted.length;
  if (key === "needs-attention") return counted.filter(needsAttention).length;
  return counted.filter((r) => toVerdict(r.label) === (key as Verdict)).length;
}

export function FilterTabs({
  results,
  active,
  onChange,
}: {
  results: RequirementResult[];
  active: FilterKey;
  onChange: (key: FilterKey) => void;
}) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-lg border border-zinc-200 bg-white p-1 dark:border-zinc-800 dark:bg-zinc-900">
      {TABS.map((tab) => {
        const count = countForFilter(results, tab.key);
        const isActive = active === tab.key;
        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={`shrink-0 rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors ${
              isActive
                ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
            }`}
          >
            {tab.label} ({count})
          </button>
        );
      })}
    </div>
  );
}
