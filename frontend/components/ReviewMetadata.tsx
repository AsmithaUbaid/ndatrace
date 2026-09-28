import { RetrievedChunk } from "@/lib/api";
import { retrievalTier } from "@/lib/retrievalPresentation";
import { evidenceQuoteCount, selectEvidenceDisplay } from "@/lib/evidenceDisplay";

const METRIC_TONES = {
  cost: "border-violet-200/80 bg-violet-50/70 text-violet-950",
  neutral: "border-slate-200 bg-slate-50/80 text-slate-800",
  blue: "border-sky-200/80 bg-sky-50/70 text-sky-950",
  green: "border-emerald-200/80 bg-emerald-50/70 text-emerald-950",
  amber: "border-amber-200/80 bg-amber-50/70 text-amber-950",
} as const;

const RETRIEVAL_MATCH_TOOLTIP = "Cross-encoder retrieval relevance score; not prediction confidence.";

export function ReviewMetadata({
  costUsd,
  latencyMs,
  retrievedChunks,
  label,
  evidence,
  sourceValid,
}: {
  costUsd: number | null;
  latencyMs: number | null;
  retrievedChunks: RetrievedChunk[];
  label: string;
  evidence: string[];
  sourceValid: boolean | null;
}) {
  const topChunk = retrievedChunks.find((chunk) => chunk.rank === 1) ?? retrievedChunks[0];
  const retrievalMatch = retrievalTier(topChunk?.reranker_score ?? null);
  const quoteCount = evidenceQuoteCount(selectEvidenceDisplay(label, evidence, sourceValid));

  return (
    <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Review metadata">
      <MetricChip
        label="Cost / review"
        value={costUsd == null ? "–" : `$${costUsd.toFixed(6)}`}
        tone="cost"
      />
      <MetricChip
        label="Latency"
        value={latencyMs == null ? "–" : `${(latencyMs / 1000).toFixed(2)} s`}
        tone="neutral"
      />
      <MetricChip
        label="Evidence"
        value={`${quoteCount} ${quoteCount === 1 ? "quote" : "quotes"}`}
        tone="blue"
      />
      <MetricChip
        label="Retrieval match"
        value={retrievalMatch.label}
        subvalue={topChunk ? `Score ${topChunk.reranker_score.toFixed(3)}` : undefined}
        tone={retrievalMatch.tone}
        title={`${retrievalMatch.detail}. ${RETRIEVAL_MATCH_TOOLTIP}`}
      />
    </div>
  );
}

function MetricChip({
  label,
  value,
  subvalue,
  tone,
  title,
}: {
  label: string;
  value: string;
  subvalue?: string;
  tone: keyof typeof METRIC_TONES;
  title?: string;
}) {
  return (
    <div
      className={`min-w-0 rounded-lg border px-3 py-2 shadow-[0_1px_2px_rgba(15,23,42,0.03)] ${METRIC_TONES[tone]}`}
      title={title}
    >
      <span className="block text-[9px] font-bold uppercase tracking-[0.13em] opacity-55">{label}</span>
      <span className="mt-0.5 block truncate text-xs font-semibold tabular-nums sm:text-[13px]">{value}</span>
      {subvalue && (
        <span className="block truncate text-[10px] font-medium tabular-nums opacity-70">{subvalue}</span>
      )}
    </div>
  );
}
