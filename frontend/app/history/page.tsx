"use client";

import { useEffect, useState } from "react";
import { api, ReviewResponse, ReviewSummary } from "@/lib/api";
import { RequirementCard } from "@/components/RequirementCard";

export default function HistoryPage() {
  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  const [selected, setSelected] = useState<ReviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listResults()
      .then(setReviews)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function openReview(reviewId: string) {
    setSelected(null);
    try {
      setSelected(await api.getReview(reviewId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load review.");
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Review history
        </h1>
        <p className="mt-1.5 text-sm text-zinc-600 dark:text-zinc-400">
          Every review submitted through this app, persisted so a past result can be pulled back up
          without re-running the model.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-zinc-400 dark:text-zinc-500">Loading&hellip;</p>}

      {!loading && reviews.length === 0 && !error && (
        <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
          No reviews yet &mdash; run one from the{" "}
          <a href="/" className="font-medium text-zinc-800 underline dark:text-zinc-200">
            Review
          </a>{" "}
          page.
        </div>
      )}

      {reviews.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
          <table className="w-full min-w-[600px] text-left text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50 text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
              <tr>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2 font-medium">Doc</th>
                <th className="px-4 py-2 font-medium">Requirements</th>
                <th className="px-4 py-2 font-medium">Model</th>
                <th className="px-4 py-2 font-medium">Cost</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((r) => (
                <tr
                  key={r.review_id}
                  onClick={() => openReview(r.review_id)}
                  className="cursor-pointer border-b border-zinc-100 last:border-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-800"
                >
                  <td className="px-4 py-2.5 text-zinc-700 dark:text-zinc-300">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-xs text-zinc-500 dark:text-zinc-400">
                    {r.doc_id}
                  </td>
                  <td className="px-4 py-2.5 text-zinc-700 dark:text-zinc-300">{r.num_requirements}</td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">{r.model}</td>
                  <td className="px-4 py-2.5 text-zinc-500 dark:text-zinc-400">
                    ${r.total_cost_usd.toFixed(6)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Review {selected.review_id.slice(0, 8)} &mdash; {selected.results.length} result
            {selected.results.length === 1 ? "" : "s"}
          </h2>
          <ul className="flex flex-col gap-3">
            {selected.results.map((r) => (
              <RequirementCard key={r.hypothesis_id} r={r} />
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
