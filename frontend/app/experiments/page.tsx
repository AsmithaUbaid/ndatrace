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
          Every architecture and ablation run in this project (Rule-based &rarr; Full-context &rarr;
          RAG &rarr; RAG + selective agent), read live from{" "}
          <code className="rounded bg-zinc-200 px-1 py-0.5 text-xs dark:bg-zinc-800">results/runs/</code>{" "}
          &mdash; not a static export, this reflects the real, current experiment history.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

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
