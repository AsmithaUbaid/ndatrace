"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, Hypothesis, ReviewDecision, ReviewResponse } from "@/lib/api";
import { RequirementCard } from "@/components/RequirementCard";
import { ResultsSummaryBar } from "@/components/ResultsSummaryBar";
import { LimitationsPanel } from "@/components/LimitationsPanel";
import { Checkbox } from "@/components/Checkbox";
import { FilterTabs } from "@/components/FilterTabs";
import { FilterKey, toVerdict } from "@/lib/verdict";
import { downloadFile, reviewToJson, reviewToText } from "@/lib/export";

const SAMPLE_NDA = `This Non-Disclosure Agreement is entered into between Acme Corp ("Disclosing Party") and Beta LLC ("Receiving Party").

Confidential Information means any technical or business information disclosed by the Disclosing Party, whether marked as confidential or not.

Receiving Party shall not reverse engineer, decompile, or disassemble any objects which embody Disclosing Party's Confidential Information.

Receiving Party may disclose Confidential Information to its employees who need to know such information for the purposes of this Agreement.

Upon termination of this Agreement, Receiving Party shall return or destroy all Confidential Information in its possession.`;

type Stage = "idle" | "loading-hypotheses" | "ready" | "reviewing" | "done" | "error";
type InputMode = "paste" | "pdf";

export default function ReviewPage() {
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [ndaText, setNdaText] = useState(SAMPLE_NDA);
  const [draftRestored, setDraftRestored] = useState(false);
  const [result, setResult] = useState<ReviewResponse | null>(null);
  const [stage, setStage] = useState<Stage>("loading-hypotheses");
  const [error, setError] = useState<string | null>(null);
  const [inputMode, setInputMode] = useState<InputMode>("paste");
  const [pdfName, setPdfName] = useState<string | null>(null);
  const [extractingPdf, setExtractingPdf] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [copied, setCopied] = useState(false);

  const DRAFT_KEY = "ndatrace_nda_draft";

  useEffect(() => {
    // Per-viewer convenience only - restores a draft if the tab was closed
    // or refreshed mid-edit. Never assumed to be present; wrapped in
    // try/catch since localStorage can throw (private browsing, blocked
    // site data) and this must never break the page if it does. One-time
    // hydration from an external store (not React state), so the
    // set-state-in-effect lint rule doesn't apply the way it would for
    // syncing two pieces of React state.
    try {
      const saved = window.localStorage.getItem(DRAFT_KEY);
      if (saved && saved !== SAMPLE_NDA) {
        // eslint-disable-next-line react-hooks/set-state-in-effect
        setNdaText(saved);
        setDraftRestored(true);
      }
    } catch {
      // ignore - draft restore is a convenience, not a requirement
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(DRAFT_KEY, ndaText);
    } catch {
      // ignore - see above
    }
  }, [ndaText]);

  useEffect(() => {
    api
      .listHypotheses()
      .then((h) => {
        setHypotheses(h);
        setSelected(new Set(h.map((x) => x.hypothesis_id)));
        setStage("ready");
      })
      .catch((e) => {
        setError(
          `Could not reach the NDATrace API at ${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}. ` +
            `Is the backend running? (${e.message})`
        );
        setStage("error");
      });
  }, []);

  const allSelected = useMemo(
    () => hypotheses.length > 0 && selected.size === hypotheses.length,
    [hypotheses, selected]
  );

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function handlePdfSelected(file: File) {
    setPdfName(file.name);
    setExtractingPdf(true);
    setError(null);
    try {
      const { text } = await api.extractPdf(file);
      setNdaText(text);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not extract text from that PDF.");
      setPdfName(null);
    } finally {
      setExtractingPdf(false);
    }
  }

  async function handleSubmit() {
    setStage("reviewing");
    setError(null);
    setResult(null);
    try {
      const ids = allSelected ? undefined : Array.from(selected);
      const response = await api.createReview(ndaText, ids);
      setResult(response);
      setStage("done");
      // Auto-switch to Contradictions if any exist, since that's the
      // highest-risk class - otherwise show everything.
      const hasContradiction = response.results.some(
        (r) => !r.error && r.label != null && toVerdict(r.label) === "contradiction"
      );
      setFilter(hasContradiction ? "contradiction" : "all");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed.");
      setStage("error");
    }
  }

  async function handleCopy() {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(reviewToText(result));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Could not copy to clipboard - your browser may have blocked it.");
    }
  }

  function handleDownloadJson() {
    if (!result) return;
    downloadFile(reviewToJson(result), `ndatrace-review-${result.doc_id}.json`, "application/json");
  }

  async function handleDecide(itemId: number, decision: ReviewDecision, note?: string) {
    if (!result) return;
    const updated = await api.recordDecision(result.review_id, itemId, decision, note);
    setResult({
      ...result,
      results: result.results.map((r) => (r.id === itemId ? updated : r)),
    });
  }

  const filteredResults = useMemo(() => {
    if (!result) return [];
    if (filter === "all") return result.results;
    if (filter === "needs-attention") {
      return result.results.filter(
        (r) => !r.error && r.label != null && (
          toVerdict(r.label) === "contradiction" || r.needs_human_review
        )
      );
    }
    return result.results.filter((r) => !r.error && r.label != null && toVerdict(r.label) === filter);
  }, [result, filter]);

  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-10 px-4 py-10 sm:px-6">
      <header className="relative overflow-hidden rounded-3xl border border-zinc-200 bg-white px-6 py-8 shadow-[0_18px_50px_-36px_rgba(24,24,27,0.45)] sm:px-8">
        <div aria-hidden className="absolute -right-20 -top-24 h-56 w-56 rounded-full bg-sky-100/70 blur-3xl" />
        <div className="relative"><p className="text-[11px] font-bold uppercase tracking-[0.16em] text-sky-700">NDATrace</p><h1 className="mt-2 text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl">Evidence-grounded NDA review</h1>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-zinc-600">Review confidentiality requirements against the source agreement.</p>
        <div className="mt-6 grid overflow-hidden rounded-2xl border border-zinc-200 bg-zinc-50/70 sm:grid-cols-3">{[["01","Provide NDA"],["02","Choose requirements"],["03","Review results"]].map(([n,label])=><div key={n} className="flex items-center gap-3 border-b border-zinc-200 px-4 py-3 last:border-0 sm:border-b-0 sm:border-r sm:last:border-r-0"><span className="font-mono text-xs font-bold text-zinc-400">{n}</span><span className="text-sm font-medium text-zinc-800">{label}</span></div>)}</div></div>
      </header>

      {stage === "error" && !result && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-[11px] font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
              1
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Provide the NDA</span>
          </div>
          <div className="flex rounded-md border border-zinc-200 bg-white p-0.5 text-xs dark:border-zinc-700 dark:bg-zinc-900">
            <button
              onClick={() => setInputMode("paste")}
              className={`rounded px-2.5 py-1 font-medium transition-colors ${
                inputMode === "paste"
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
              }`}
            >
              Paste text
            </button>
            <button
              onClick={() => setInputMode("pdf")}
              className={`rounded px-2.5 py-1 font-medium transition-colors ${
                inputMode === "pdf"
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
              }`}
            >
              Upload PDF
            </button>
          </div>
        </div>

        {inputMode === "pdf" && (
          <div className="flex flex-col gap-2">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-2xl border border-dashed border-sky-300 bg-sky-50/40 px-4 py-8 text-center hover:border-sky-500 hover:bg-sky-50"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handlePdfSelected(e.target.files[0])}
              />
              {extractingPdf ? (
                <span className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-700 dark:border-zinc-600 dark:border-t-zinc-200" />
                  Extracting text&hellip;
                </span>
              ) : pdfName ? (
                <span className="text-sm text-zinc-700 dark:text-zinc-300">
                  {"✓"} {pdfName}{" "}
                  <span className="text-zinc-400 dark:text-zinc-500">
                    (click to choose a different file)
                  </span>
                </span>
              ) : (
                <span className="text-sm text-zinc-500 dark:text-zinc-400">
                  Choose a PDF
                </span>
              )}
            </div>
            {pdfName && !extractingPdf && (
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Extracted text below. Review or edit it before running the review.
              </p>
            )}
          </div>
        )}

        {draftRestored && (
          <div className="rounded-md bg-blue-50 px-3 py-1.5 text-xs text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
            Restored your unsaved draft from last time.
          </div>
        )}

        <div className="overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm focus-within:border-sky-400 focus-within:ring-2 focus-within:ring-sky-100">
          <textarea
            id="nda-text"
            className="min-h-[200px] w-full resize-y border-0 p-3 font-mono text-sm text-zinc-900 focus:outline-none dark:text-zinc-100"
            value={ndaText}
            onChange={(e) => {
              setNdaText(e.target.value);
              setDraftRestored(false);
            }}
          />
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-200 px-3 py-2 text-xs text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
            <span>{ndaText.length} characters</span>
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setNdaText("");
                  setDraftRestored(false);
                }}
                className="rounded-md border border-zinc-200 px-2.5 py-1 font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Clear
              </button>
              <button
                onClick={() => {
                  setNdaText(SAMPLE_NDA);
                  setDraftRestored(false);
                }}
                className="rounded-md border border-zinc-200 px-2.5 py-1 font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Load sample
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-[11px] font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
              2
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              Choose requirements to check ({selected.size}/{hypotheses.length})
            </span>
          </div>
          <button
            className="text-xs font-medium text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
            onClick={() =>
              setSelected(allSelected ? new Set() : new Set(hypotheses.map((h) => h.hypothesis_id)))
            }
          >
            {allSelected ? "Clear all" : "Select all"}
          </button>
        </div>
        <div className="grid max-h-64 grid-cols-1 gap-1.5 overflow-y-auto rounded-2xl border border-zinc-200 bg-white p-3 shadow-sm sm:grid-cols-2">
          {stage === "loading-hypotheses" && (
            <p className="col-span-2 p-2 text-sm text-zinc-400 dark:text-zinc-500">
              Loading requirements&hellip;
            </p>
          )}
          {hypotheses.map((h) => (
            <label
              key={h.hypothesis_id}
              className="flex cursor-pointer items-start gap-2.5 rounded-md p-2 text-sm hover:bg-zinc-50 dark:hover:bg-zinc-800"
            >
              <Checkbox checked={selected.has(h.hypothesis_id)} onChange={() => toggle(h.hypothesis_id)} />
              <span className="text-zinc-800 dark:text-zinc-200">
                <span className="font-medium">{h.short_description}</span>{" "}
                <span className="text-zinc-400 dark:text-zinc-500">({h.hypothesis_id})</span>
              </span>
            </label>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-[11px] font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
              3
            </span>
            <span className="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">Review results</span>
          </div>
        </div>
        <button
          onClick={handleSubmit}
          disabled={stage === "reviewing" || ndaText.trim().length === 0 || selected.size === 0}
          className="flex w-full items-center justify-center gap-2 rounded-2xl bg-zinc-900 py-3 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:bg-zinc-300"
        >
          {stage === "reviewing" && (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white dark:border-zinc-900/30 dark:border-t-zinc-900" />
          )}
          {stage === "reviewing"
            ? "Reviewing selected requirements…"
            : "Run review"}
        </button>
        {stage === "reviewing" && (
          <div
            className="rounded-2xl border border-zinc-200 bg-white px-4 py-3 shadow-sm"
            aria-live="polite"
            aria-atomic="true"
          >
            <div className="flex items-center gap-2.5">
              <span
                aria-hidden="true"
                className="h-2 w-2 shrink-0 animate-pulse rounded-full bg-zinc-500 dark:bg-zinc-400"
              />
              <p className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
                Reviewing against the retrieval + classification pipeline…
              </p>
            </div>
            <p className="mt-1 pl-[18px] text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
              Retrieval, reranking, and classification run per requirement; this can take a few
              seconds to over a minute for a full batch.
            </p>
          </div>
        )}
        {stage === "error" && result === null && error && (
          <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
        )}
      </section>

      {result && (
        <section className="flex flex-col gap-4">
          <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-medium text-zinc-800 dark:text-zinc-100">
                {result.results.length} requirement{result.results.length === 1 ? "" : "s"} checked
                with{" "}
                <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs dark:bg-zinc-800">
                  {result.model}
                </code>
              </span>
              <span className="text-zinc-500 dark:text-zinc-400">
                ${result.total_cost_usd.toFixed(6)} &middot; {(result.total_latency_ms / 1000).toFixed(1)}s
              </span>
            </div>
            <ResultsSummaryBar results={result.results} activeFilter={filter} onSelect={setFilter} />
            <div className="mt-3 flex gap-2 border-t border-zinc-100 pt-3 dark:border-zinc-800">
              <button
                onClick={handleCopy}
                className="rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                {copied ? "✓ Copied" : "Copy as text"}
              </button>
              <button
                onClick={handleDownloadJson}
                className="rounded-md border border-zinc-200 px-2.5 py-1 text-xs font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
              >
                Download JSON
              </button>
            </div>
          </div>

          <FilterTabs results={result.results} active={filter} onChange={setFilter} />

          {filteredResults.length === 0 ? (
            <p className="rounded-lg border border-dashed border-zinc-300 bg-white p-6 text-center text-sm text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
              No requirements match this filter.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {filteredResults.map((r) => (
                <RequirementCard key={r.hypothesis_id} r={r} onDecide={handleDecide} />
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="flex flex-col gap-3 border-t border-zinc-100 pt-6 dark:border-zinc-800">
        <details className="rounded-lg border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            How it works
          </summary>
          <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
            <li>The NDA is split into clauses and the most relevant clauses for each selected requirement are retrieved and reranked.</li>
            <li>The five highest-ranked clauses are reviewed by the classifier using the frozen product prompt.</li>
            <li>Every returned evidence quote is checked against the retrieved source text.</li>
            <li>The reviewer checks the evidence and makes the final decision.</li>
          </ol>
        </details>

        <LimitationsPanel />
      </section>
    </main>
  );
}
