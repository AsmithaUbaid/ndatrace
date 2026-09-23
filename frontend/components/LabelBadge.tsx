const STYLES: Record<string, string> = {
  Entailment: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Contradiction: "bg-red-50 text-red-700 border-red-200",
  NotMentioned: "bg-zinc-100 text-zinc-600 border-zinc-200",
};

const ICONS: Record<string, string> = {
  Entailment: "✓",
  Contradiction: "✕",
  NotMentioned: "–",
};

export function LabelBadge({ label }: { label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${
        STYLES[label] ?? STYLES.NotMentioned
      }`}
    >
      <span aria-hidden>{ICONS[label] ?? ""}</span>
      {label}
    </span>
  );
}
