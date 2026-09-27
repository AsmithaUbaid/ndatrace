"use client";

import { useEffect, useState } from "react";
import { api, FinalTestResult } from "@/lib/api";

function fmtPct(v: number | null): string {
  return v === null ? "–" : `${(v * 100).toFixed(1)}%`;
}

function fmtUsd(v: number): string {
  return v === 0 ? "$0" : `$${v.toFixed(4)}`;
}

export default function ExperimentsPage() {
  const [rows, setRows] = useState<FinalTestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listFinalTestComparison()
      .then(setRows)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Final held-out TEST comparison
        </h1>
        <p className="mt-1.5 max-w-2xl text-sm text-zinc-600 dark:text-zinc-400">
          Rule, local Qwen, and GPT-5-mini + P0 + FULL NDA context (the final selected
          architecture) measured on the identical n=2,091 official ContractNLI TEST population
          (E17/E17B) — read live from{" "}
          <code className="rounded bg-zinc-200 px-1 py-0.5 text-xs dark:bg-zinc-800">
            results/final/reconstruction_v2/
          </code>
          , never recomputed. RAG and a selective agent were evaluated during reconstruction-v2
          and not selected — see <code className="rounded bg-zinc-200 px-1 py-0.5 text-xs dark:bg-zinc-800">docs/architecture.md</code>.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-zinc-400 dark:text-zinc-500">Loading&hellip;</p>}

      {!loading && rows.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <table className="w-full min-w-[820px] text-left text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
              <tr>
                <th className="px-3 py-2 font-medium">System</th>
                <th className="px-3 py-2 font-medium">n</th>
                <th className="px-3 py-2 font-medium">Accuracy</th>
                <th className="px-3 py-2 font-medium">Macro-F1</th>
                <th className="px-3 py-2 font-medium">Joint</th>
                <th className="px-3 py-2 font-medium">Contradiction recall</th>
                <th className="px-3 py-2 font-medium">NotMentioned recall</th>
                <th className="px-3 py-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.system}
                  className="border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800"
                >
                  <td className="px-3 py-2.5 font-medium text-zinc-800 dark:text-zinc-100">{r.system}</td>
                  <td className="px-3 py-2.5 text-zinc-500 dark:text-zinc-400">{r.n}</td>
                  <td className="px-3 py-2.5 font-medium text-zinc-800 dark:text-zinc-100">
                    {fmtPct(r.accuracy)}
                  </td>
                  <td className="px-3 py-2.5 text-zinc-700 dark:text-zinc-300">{r.macro_f1.toFixed(3)}</td>
                  <td className="px-3 py-2.5 text-zinc-700 dark:text-zinc-300">{r.joint.toFixed(3)}</td>
                  <td className="px-3 py-2.5 text-zinc-700 dark:text-zinc-300">
                    {fmtPct(r.contradiction_recall)}
                  </td>
                  <td className="px-3 py-2.5 text-zinc-700 dark:text-zinc-300">
                    {fmtPct(r.notmentioned_recall)}
                  </td>
                  <td className="px-3 py-2.5 text-zinc-500 dark:text-zinc-400">{fmtUsd(r.api_cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
