"use client";

import { useEffect, useMemo, useState } from "react";
import { api, ExperimentSummary } from "@/lib/api";

function fmtPct(v: number | null): string {
  return v === null ? "–" : `${(v * 100).toFixed(1)}%`;
}

function fmtUsd(v: number | null): string {
  return v === null ? "–" : `$${v.toFixed(4)}`;
}

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<ExperimentSummary[]>([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listExperiments()
      .then((exps) =>
        setExperiments(
          [...exps].sort((a, b) => (b.timestamp ?? "").localeCompare(a.timestamp ?? ""))
        )
      )
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered = useMemo(
    () =>
      experiments.filter((e) =>
        `${e.experiment_id} ${e.experiment_name} ${e.model}`.toLowerCase().includes(query.toLowerCase())
      ),
    [experiments, query]
  );

  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Experiment register
        </h1>
        <p className="mt-1.5 max-w-2xl text-sm text-zinc-600 dark:text-zinc-400">
          Every architecture and ablation run in this project&apos;s history (Rule-based &rarr;
          Full-context &rarr; RAG &rarr; RAG + selective agent), read live from{" "}
          <code className="rounded bg-zinc-200 px-1 py-0.5 text-xs dark:bg-zinc-800">results/runs/</code>{" "}
          &mdash; not a static export, this reflects the real, current experiment history. These are
          research runs; the final selected architecture and TEST result are summarized above.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      <FinalTestComparison />

      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
        Full experiment log
      </p>

      <input
        type="text"
        placeholder="Filter by experiment, architecture, or model…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        className="rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
      />

      {loading && <p className="text-sm text-zinc-400 dark:text-zinc-500">Loading&hellip;</p>}

      {!loading && filtered.length === 0 && !error && (
        <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
          No experiments match &ldquo;{query}&rdquo;.
        </div>
      )}

      {filtered.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
              <tr>
                <th className="px-3 py-2 font-medium">Experiment</th>
                <th className="px-3 py-2 font-medium">Model</th>
                <th className="px-3 py-2 font-medium">Split</th>
                <th className="px-3 py-2 font-medium">Accuracy</th>
                <th className="px-3 py-2 font-medium">Macro-F1</th>
                <th className="px-3 py-2 font-medium">Contradiction recall</th>
                <th className="px-3 py-2 font-medium">Joint (label+evidence)</th>
                <th className="px-3 py-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <tr
                  key={`${e.experiment_id}-${e.timestamp}`}
                  className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800"
                >
                  <td className="px-3 py-2.5">
                    <div className="font-medium text-zinc-800 dark:text-zinc-100">
                      {e.experiment_name || e.experiment_id}
                    </div>
                    <div className="font-mono text-xs text-zinc-400 dark:text-zinc-500">
                      {e.experiment_id}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 text-zinc-500 dark:text-zinc-400">{e.model || "–"}</td>
                  <td className="px-3 py-2.5 text-zinc-500 dark:text-zinc-400">
                    {e.split ?? "–"}
                    {e.sample_size ? ` (n=${e.sample_size})` : ""}
                  </td>
                  <td className="px-3 py-2.5 font-medium text-zinc-800 dark:text-zinc-100">
                    {fmtPct(e.accuracy)}
                  </td>
                  <td className="px-3 py-2.5 text-zinc-700 dark:text-zinc-300">
                    {e.macro_f1?.toFixed(3) ?? "–"}
                  </td>
                  <td className="px-3 py-2.5 text-zinc-700 dark:text-zinc-300">
                    {fmtPct(e.contradiction_recall)}
                    {e.contradiction_recall_ci_low !== null && e.contradiction_recall_ci_high !== null && (
                      <span className="ml-1 text-xs text-zinc-400 dark:text-zinc-500">
                        [{fmtPct(e.contradiction_recall_ci_low)}, {fmtPct(e.contradiction_recall_ci_high)}]
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-zinc-700 dark:text-zinc-300">
                    {e.joint_label_evidence_correctness?.toFixed(3) ?? "–"}
                  </td>
                  <td className="px-3 py-2.5 text-zinc-500 dark:text-zinc-400">{fmtUsd(e.total_cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

// Static, cited summary of the final one-shot held-out TEST evaluation
// (E17/E17B; docs/experiment_registry.md), all three systems on the
// identical n=2,091 case population. Deliberately NOT fetched from the
// live experiment log above - it's a fixed historical result, not
// something that changes as new experiments run.
const FINAL_TEST_ROWS: { system: string; accuracy: string; macroF1: string; joint: string; contradiction: string; note: string }[] = [
  { system: "Rule baseline", accuracy: "59.0%", macroF1: "0.479", joint: "50.1%", contradiction: "16.8%", note: "$0 · deterministic keyword rules" },
  { system: "Local Qwen (ctx16k)", accuracy: "49.9%", macroF1: "0.431", joint: "39.7%", contradiction: "25.5%", note: "$0 API — local compute not monetized" },
  { system: "GPT-5-mini + P0 + FULL (final)", accuracy: "77.6%", macroF1: "0.727", joint: "74.6%", contradiction: "75.5%", note: "≈$4.23 total for all 2,091 cases" },
];

function FinalTestComparison() {
  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
          Final held-out TEST comparison
        </h2>
        <span className="text-xs text-zinc-400 dark:text-zinc-500">n = 2,091 TEST cases, identical population for all three</span>
      </div>
      <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
        GPT-5-mini + P0 + FULL NDA context is the final selected architecture. RAG and the selective
        agent were measured, evaluated, and not selected — see the full log below for that history.
      </p>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full min-w-[560px] text-left text-sm">
          <thead className="border-b border-zinc-200 text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:text-zinc-400">
            <tr>
              <th className="py-1.5 pr-3 font-medium">System</th>
              <th className="py-1.5 pr-3 font-medium">Accuracy</th>
              <th className="py-1.5 pr-3 font-medium">Macro-F1</th>
              <th className="py-1.5 pr-3 font-medium">Joint</th>
              <th className="py-1.5 pr-3 font-medium">Contradiction recall</th>
              <th className="py-1.5 font-medium">Cost</th>
            </tr>
          </thead>
          <tbody>
            {FINAL_TEST_ROWS.map((row) => (
              <tr key={row.system} className="border-b border-zinc-100 last:border-0 dark:border-zinc-800">
                <td className="py-1.5 pr-3 font-medium text-zinc-800 dark:text-zinc-100">{row.system}</td>
                <td className="py-1.5 pr-3 text-zinc-700 dark:text-zinc-300">{row.accuracy}</td>
                <td className="py-1.5 pr-3 text-zinc-700 dark:text-zinc-300">{row.macroF1}</td>
                <td className="py-1.5 pr-3 text-zinc-700 dark:text-zinc-300">{row.joint}</td>
                <td className="py-1.5 pr-3 text-zinc-700 dark:text-zinc-300">{row.contradiction}</td>
                <td className="py-1.5 text-zinc-500 dark:text-zinc-400">{row.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
