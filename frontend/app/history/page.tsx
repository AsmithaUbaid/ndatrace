"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
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
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-7 px-4 py-10 sm:px-6">
      <header className="relative overflow-hidden rounded-3xl border border-zinc-200 bg-white px-6 py-8 shadow-[0_18px_50px_-36px_rgba(24,24,27,0.45)] sm:px-8">
        <div aria-hidden className="absolute -right-16 -top-20 h-52 w-52 rounded-full bg-amber-100/70 blur-3xl" />
        <div className="relative"><p className="text-[11px] font-bold uppercase tracking-[0.16em] text-amber-700">Saved reviews</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-950">Review History</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600">Open a previous NDATrace review without rerunning the model.</p>
        <p className="mt-2 text-xs text-zinc-400">Older saved records may originate from an earlier pipeline version.</p></div>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      {loading && <p className="text-sm text-zinc-400 dark:text-zinc-500">Loading&hellip;</p>}

      {!loading && reviews.length === 0 && !error && (
        <div className="rounded-lg border border-dashed border-zinc-300 bg-white p-8 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
          No reviews yet. Run one from the{" "}
          <Link href="/" className="font-medium text-zinc-800 underline dark:text-zinc-200">
            Review
          </Link>{" "}
          page.
        </div>
      )}

      {reviews.length > 0 && (
        <div className="overflow-x-auto rounded-3xl border border-zinc-200 bg-white shadow-sm">
          <table className="w-full min-w-[900px] text-left text-sm">
            <thead className="border-b border-zinc-200 bg-zinc-50/80 text-[10px] uppercase tracking-wide text-zinc-500">
              <tr>
                <th className="px-5 py-3 font-medium">Date</th>
                <th className="px-4 py-3 font-medium">Document</th>
                <th className="px-4 py-2 font-medium">Requirements</th>
                <th className="px-4 py-2 font-medium">Result summary</th>
                <th className="px-4 py-2 font-medium">Model</th>
                <th className="px-4 py-2 font-medium">Cost</th>
                <th className="px-5 py-2 font-medium">Review status</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((r) => (
                <tr
                  key={r.review_id}
                  onClick={() => openReview(r.review_id)}
                  className="cursor-pointer border-b border-zinc-100 last:border-0 hover:bg-sky-50/50"
                >
                  <td className="px-5 py-4 text-zinc-700">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-4 font-mono text-xs text-zinc-500">
                    {r.doc_id}
                  </td>
                  <td className="px-4 py-4 text-zinc-700">{r.num_requirements}</td>
                  <td className="px-4 py-4 text-zinc-500">{r.num_requirements} saved result{r.num_requirements===1?"":"s"}</td>
                  <td className="px-4 py-4 text-zinc-500">{r.model}</td>
                  <td className="px-4 py-4 text-zinc-500">
                    ${r.total_cost_usd.toFixed(6)}
                  </td>
                  <td className="px-5 py-4"><span className="rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold text-emerald-800">Saved · open</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <section className="flex flex-col gap-4 border-t border-zinc-200 pt-7">
          <div><p className="text-[10px] font-bold uppercase tracking-wide text-sky-700">Previous NDATrace review</p><h2 className="mt-1 text-xl font-semibold text-zinc-900">
            Review {selected.review_id.slice(0, 8)} · {selected.results.length} result
            {selected.results.length === 1 ? "" : "s"}
          </h2></div>
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
