import { RequirementResult } from "./api";

// Internal verdict keys, mapped from the real API's `label` field
// ("Entailment" | "Contradiction" | "NotMentioned") - kept distinct from
// `label` so display logic (color, icon, filter key) has one small,
// case-normalized vocabulary to switch on instead of re-deriving it in
// every component.
export type Verdict = "entailment" | "contradiction" | "notmentioned";

export function toVerdict(label: string): Verdict {
  if (label === "Contradiction") return "contradiction";
  if (label === "Entailment") return "entailment";
  return "notmentioned";
}

export const VERDICT_TITLES: Record<Verdict, string> = {
  contradiction: "Contradiction",
  entailment: "Entailment",
  notmentioned: "Not Mentioned",
};

export const VERDICT_TITLES_PLURAL: Record<Verdict, string> = {
  contradiction: "Contradictions",
  entailment: "Entailments",
  notmentioned: "Not Mentioned",
};

export const VERDICT_ICONS: Record<Verdict, string> = {
  contradiction: "✕",
  entailment: "✓",
  notmentioned: "–",
};

// Tailwind class fragments per verdict, centralized so the summary chips,
// filter tabs, and result cards can't drift out of sync with each other.
export const VERDICT_COLORS: Record<
  Verdict,
  {
    badge: string;
    chip: string;
    chipActive: string;
    stripe: string;
    dot: string;
    dotActive: string;
  }
> = {
  contradiction: {
    badge: "border-red-500 bg-red-500 text-white",
    chip: "border-red-200 bg-red-50 text-red-700 hover:bg-red-100 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300 dark:hover:bg-red-950/70",
    chipActive: "border-red-400 bg-red-600 text-white dark:border-red-500 dark:bg-red-600",
    stripe: "bg-red-400 dark:bg-red-500",
    dot: "bg-red-500",
    dotActive: "bg-white",
  },
  entailment: {
    badge: "border-emerald-600 bg-emerald-600 text-white",
    chip: "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 dark:hover:bg-emerald-950/70",
    chipActive: "border-emerald-400 bg-emerald-600 text-white dark:border-emerald-500 dark:bg-emerald-600",
    stripe: "bg-emerald-400 dark:bg-emerald-500",
    dot: "bg-emerald-500",
    dotActive: "bg-white",
  },
  notmentioned: {
    badge: "border-slate-600 bg-slate-600 text-white",
    chip: "border-zinc-200 bg-zinc-50 text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800",
    chipActive: "border-zinc-500 bg-zinc-700 text-white dark:border-zinc-500 dark:bg-zinc-700",
    stripe: "bg-slate-300 dark:bg-slate-600",
    dot: "bg-zinc-400",
    dotActive: "bg-white",
  },
};

export const LOW_CONFIDENCE_THRESHOLD = 0.5;

export function isLowConfidence(r: RequirementResult): boolean {
  return !r.error && r.confidence_available && r.confidence != null && r.confidence < LOW_CONFIDENCE_THRESHOLD;
}

export function needsAttention(r: RequirementResult): boolean {
  return !r.error && r.label != null && (
    toVerdict(r.label) === "contradiction" || r.needs_human_review || isLowConfidence(r)
  );
}

export type FilterKey = "all" | Verdict | "needs-attention";
