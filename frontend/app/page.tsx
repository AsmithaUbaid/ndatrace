"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { api, CostEstimate, Hypothesis, ReviewResponse } from "@/lib/api";
import { RequirementCard } from "@/components/RequirementCard";

const LABEL_ORDER = ["Contradiction", "NotMentioned", "Entailment"] as const;
const LABEL_TITLES: Record<string, string> = {
  Failed: "Failed",
  Contradiction: "Contradiction",
  NotMentioned: "Not Mentioned",
  Entailment: "Entailment",
};

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
  const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null);

  const DRAFT_KEY = "ndatrace_nda_draft";

  useEffect(() => {
    api.getCostEstimate().then(setCostEstimate).catch(() => {
      // Non-critical - if no rag_agent experiment record exists yet, just
      // skip showing the estimate rather than blocking the review flow.
    });
  }, []);

  useEffect(() => {
    // Per-viewer convenience only - restores a draft if the tab was closed
    // or refreshed mid-edit. Never assumed to be present; wrapped in
    // try/catch since localStorage can throw (private browsing, blocked
    // site data) and this must never break the page if it does.
    try {
      const saved = window.localStorage.getItem(DRAFT_KEY);
      if (saved && saved !== SAMPLE_NDA) {
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
      next.has(id) ? next.delete(id) : next.add(id);
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
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed.");
      setStage("error");
    }
  }

  const summary = result
    ? {
        entailment: result.results.filter((r) => !r.error && r.label === "Entailment").length,
        contradiction: result.results.filter((r) => !r.error && r.label === "Contradiction").length,
        notMentioned: result.results.filter((r) => !r.error && r.label === "NotMentioned").length,
        failed: result.results.filter((r) => r.error).length,
        agentUsed: result.results.filter((r) => r.agent_used).length,
      }
    : null;

  const grouped = result
    ? [
        { label: "Failed", items: result.results.filter((r) => r.error) },
        ...LABEL_ORDER.map((label) => ({
          label,
          items: result.results.filter((r) => !r.error && r.label === label),
        })),
      ].filter((g) => g.items.length > 0)
    : [];

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col gap-8 px-6 py-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">Review an NDA</h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-zinc-600">
          Paste an NDA and pick the standard confidentiality requirements to check. Each result comes
          with a label, a confidence score, and the exact evidence text it was based on &mdash; not
          just a verdict.
        </p>
      </header>

      {stage === "error" && !result && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>
      )}

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-[11px] font-semibold text-white">
              1
            </span>
            <span className="text-sm font-medium text-zinc-700">Provide the NDA</span>
          </div>
          <div className="flex rounded-md border border-zinc-200 bg-white p-0.5 text-xs">
            <button
              onClick={() => setInputMode("paste")}
              className={`rounded px-2.5 py-1 font-medium transition-colors ${
                inputMode === "paste" ? "bg-zinc-900 text-white" : "text-zinc-500 hover:text-zinc-800"
              }`}
            >
              Paste text
            </button>
            <button
              onClick={() => setInputMode("pdf")}
              className={`rounded px-2.5 py-1 font-medium transition-colors ${
                inputMode === "pdf" ? "bg-zinc-900 text-white" : "text-zinc-500 hover:text-zinc-800"
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
              className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-zinc-300 bg-white px-4 py-6 text-center shadow-sm hover:border-zinc-400"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handlePdfSelected(e.target.files[0])}
              />
              {extractingPdf ? (
                <span className="flex items-center gap-2 text-sm text-zinc-500">
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-zinc-300 border-t-zinc-700" />
                  Extracting text&hellip;
                </span>
              ) : pdfName ? (
                <span className="text-sm text-zinc-700">
                  {"✓"} {pdfName}{" "}
                  <span className="text-zinc-400">&mdash; click to choose a different file</span>
                </span>
              ) : (
                <span className="text-sm text-zinc-500">Click to choose a PDF, or drop one here</span>
              )}
            </div>
            {pdfName && !extractingPdf && (
              <p className="text-xs text-zinc-500">
                Extracted text below &mdash; review or edit it before running the review.
              </p>
            )}
          </div>
        )}

        {draftRestored && (
          <div className="flex items-center justify-between rounded-md bg-blue-50 px-3 py-1.5 text-xs text-blue-700">
            <span>Restored your unsaved draft from last time.</span>
            <button
              onClick={() => {
                setNdaText(SAMPLE_NDA);
                setDraftRestored(false);
              }}
              className="font-medium underline hover:text-blue-900"
            >
              Discard, use sample instead
            </button>
          </div>
        )}

        <textarea
          id="nda-text"
          className="min-h-[200px] rounded-lg border border-zinc-300 bg-white p-3 font-mono text-sm shadow-sm focus:border-zinc-500 focus:outline-none focus:ring-1 focus:ring-zinc-500"
          value={ndaText}
          onChange={(e) => {
            setNdaText(e.target.value);
            setDraftRestored(false);
          }}
        />
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-[11px] font-semibold text-white">
              2
            </span>
            <span className="text-sm font-medium text-zinc-700">
              Choose requirements to check ({selected.size}/{hypotheses.length})
            </span>
          </div>
          <button
            className="text-xs font-medium text-zinc-500 hover:text-zinc-800"
            onClick={() =>
              setSelected(allSelected ? new Set() : new Set(hypotheses.map((h) => h.hypothesis_id)))
            }
          >
            {allSelected ? "Clear all" : "Select all"}
          </button>
        </div>
        <div className="grid max-h-56 grid-cols-1 gap-1 overflow-y-auto rounded-lg border border-zinc-200 bg-white p-2 shadow-sm sm:grid-cols-2">
          {stage === "loading-hypotheses" && (
            <p className="col-span-2 p-2 text-sm text-zinc-400">Loading requirements&hellip;</p>
          )}
          {hypotheses.map((h) => (
            <label
              key={h.hypothesis_id}
              className="flex cursor-pointer items-start gap-2 rounded-md p-1.5 text-sm hover:bg-zinc-50"
            >
              <input
                type="checkbox"
                className="mt-0.5"
                checked={selected.has(h.hypothesis_id)}
                onChange={() => toggle(h.hypothesis_id)}
              />
              <span>
                <span className="font-medium">{h.short_description}</span>{" "}
                <span className="text-zinc-400">({h.hypothesis_id})</span>
              </span>
            </label>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-[11px] font-semibold text-white">
              3
            </span>
            <span className="text-sm font-medium text-zinc-700">Run the review</span>
          </div>
          {costEstimate && selected.size > 0 && (
            <span className="text-xs text-zinc-500">
              Estimated cost: ~${(costEstimate.avg_cost_per_requirement_usd * selected.size).toFixed(4)} for{" "}
              {selected.size} requirement{selected.size === 1 ? "" : "s"}{" "}
              <span className="text-zinc-400">
                (measured avg, {costEstimate.source_experiment_id})
              </span>
            </span>
          )}
        </div>
        <button
          onClick={handleSubmit}
          disabled={stage === "reviewing" || ndaText.trim().length === 0 || selected.size === 0}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:bg-zinc-300"
        >
          {stage === "reviewing" && (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white" />
          )}
          {stage === "reviewing"
            ? "Reviewing… this calls the real model, usually a few seconds per requirement"
            : "Run review"}
        </button>
        {stage === "error" && result === null && error && (
          <p className="text-xs text-red-600">{error}</p>
        )}
      </section>

      {result && summary && (
        <section className="flex flex-col gap-4">
          <div className="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <span className="font-medium text-zinc-800">
                {result.results.length} requirement{result.results.length === 1 ? "" : "s"} checked
                with <code className="rounded bg-zinc-100 px-1 py-0.5 text-xs">{result.model}</code>
              </span>
              <span className="text-zinc-500">
                ${result.total_cost_usd.toFixed(6)} &middot; {(result.total_latency_ms / 1000).toFixed(1)}s
              </span>
            </div>
            <div className="mt-3 flex flex-wrap gap-4 text-xs text-zinc-600">
              <span>{summary.entailment} Entailment</span>
              <span>{summary.contradiction} Contradiction</span>
              <span>{summary.notMentioned} Not Mentioned</span>
              <span className="text-amber-700">{summary.agentUsed} escalated to agent</span>
              {summary.failed > 0 && (
                <span className="font-medium text-amber-800">{summary.failed} failed</span>
              )}
            </div>
          </div>

          {grouped.map(({ label, items }) => (
            <div key={label} className="flex flex-col gap-2">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-zinc-700">
                {LABEL_TITLES[label]}
                <span className="rounded-full bg-zinc-200 px-2 py-0.5 text-xs font-medium text-zinc-600">
                  {items.length}
                </span>
              </h2>
              <ul className="flex flex-col gap-3">
                {items.map((r) => (
                  <RequirementCard key={r.hypothesis_id} r={r} />
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
