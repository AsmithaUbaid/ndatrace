"use client";

import { useEffect, useRef, useState } from "react";
import { api, FinalReviewResponse, Hypothesis } from "@/lib/api";
import { ResultCard } from "@/components/ResultCard";
import { LimitationsPanel } from "@/components/LimitationsPanel";

const SAMPLE_NDA = `This Non-Disclosure Agreement is entered into between Acme Corp ("Disclosing Party") and Beta LLC ("Receiving Party").

Confidential Information means any technical or business information disclosed by the Disclosing Party, whether marked as confidential or not.

Receiving Party shall not reverse engineer, decompile, or disassemble any objects which embody Disclosing Party's Confidential Information.

Receiving Party may disclose Confidential Information to its employees who need to know such information for the purposes of this Agreement.

Upon termination of this Agreement, Receiving Party shall return or destroy all Confidential Information in its possession.`;
// Demo content only - a short synthetic NDA excerpt, not a real or confidential document.

const SAMPLE_REQUIREMENT = "Receiving Party shall not reverse engineer any objects which embody Disclosing Party's Confidential Information.";

type Stage = "idle" | "ready" | "reviewing" | "done" | "error";
type InputMode = "paste" | "pdf";

export default function ReviewPage() {
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [ndaText, setNdaText] = useState(SAMPLE_NDA);
  const [requirement, setRequirement] = useState(SAMPLE_REQUIREMENT);
  const [result, setResult] = useState<FinalReviewResponse | null>(null);
  const [stage, setStage] = useState<Stage>("idle");
  const [error, setError] = useState<string | null>(null);
  const [inputMode, setInputMode] = useState<InputMode>("paste");
  const [pdfName, setPdfName] = useState<string | null>(null);
  const [extractingPdf, setExtractingPdf] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api
      .listHypotheses()
      .then((h) => {
        setHypotheses(h);
        setStage("ready");
      })
      .catch(() => {
        // The predefined-requirement dropdown is a convenience; free-text
        // requirement input still works if the backend can't be reached yet.
        setStage("ready");
      });
  }, []);

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
      const response = await api.reviewFinal(ndaText, requirement);
      setResult(response);
      setStage("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed.");
      setStage("error");
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-8 px-4 py-10 sm:px-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">NDATrace</h1>
        <p className="mt-1 text-sm font-medium text-zinc-500 dark:text-zinc-400">
          Evidence-grounded NDA requirement review
        </p>
        <p className="mt-2 max-w-xl text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
          Review a confidentiality requirement against an NDA and see the predicted relationship
          together with the supporting contract text.
        </p>
      </header>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300">
          {error}
        </div>
      )}

      <section className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <StepLabel n={1} text="Provide the NDA" />
          <div className="flex rounded-md border border-zinc-200 bg-white p-0.5 text-xs dark:border-zinc-700 dark:bg-zinc-900">
            <ModeButton active={inputMode === "paste"} onClick={() => setInputMode("paste")} label="Paste text" />
            <ModeButton active={inputMode === "pdf"} onClick={() => setInputMode("pdf")} label="Upload PDF" />
          </div>
        </div>

        {inputMode === "pdf" && (
          <div
            onClick={() => fileInputRef.current?.click()}
            className="flex cursor-pointer flex-col items-center justify-center gap-1 rounded-lg border border-dashed border-zinc-300 bg-white px-4 py-6 text-center shadow-sm hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:border-zinc-500"
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
                {"✓"} {pdfName} <span className="text-zinc-400 dark:text-zinc-500">&mdash; click to choose a different file</span>
              </span>
            ) : (
              <span className="text-sm text-zinc-500 dark:text-zinc-400">Click to choose a PDF, or drop one here</span>
            )}
          </div>
        )}

        <div className="overflow-hidden rounded-lg border border-zinc-300 bg-white shadow-sm focus-within:border-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:focus-within:border-zinc-400">
          <textarea
            className="min-h-[180px] w-full resize-y border-0 p-3 font-mono text-sm text-zinc-900 focus:outline-none dark:text-zinc-100"
            value={ndaText}
            onChange={(e) => setNdaText(e.target.value)}
          />
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-zinc-200 px-3 py-2 text-xs text-zinc-400 dark:border-zinc-800 dark:text-zinc-500">
            <span>{ndaText.length} characters</span>
            <div className="flex gap-2">
              <button onClick={() => setNdaText("")} className="rounded-md border border-zinc-200 px-2.5 py-1 font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800">
                Clear
              </button>
              <button onClick={() => setNdaText(SAMPLE_NDA)} className="rounded-md border border-zinc-200 px-2.5 py-1 font-medium text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800">
                Load demo NDA
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <StepLabel n={2} text="Provide the requirement" />
        {hypotheses.length > 0 && (
          <select
            className="rounded-md border border-zinc-300 bg-white px-2.5 py-1.5 text-sm text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
            defaultValue=""
            onChange={(e) => e.target.value && setRequirement(e.target.value)}
          >
            <option value="">Choose a standard requirement&hellip;</option>
            {hypotheses.map((h) => (
              <option key={h.hypothesis_id} value={h.hypothesis_text}>
                {h.short_description}
              </option>
            ))}
          </select>
        )}
        <textarea
          className="min-h-[70px] w-full resize-y rounded-lg border border-zinc-300 bg-white p-3 text-sm text-zinc-900 shadow-sm focus:border-zinc-500 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-400"
          placeholder="e.g. Receiving Party shall not disclose Confidential Information to any third party."
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
        />
      </section>

      <section className="flex flex-col gap-2">
        <StepLabel n={3} text="Run the review" />
        <button
          onClick={handleSubmit}
          disabled={stage === "reviewing" || ndaText.trim().length === 0 || requirement.trim().length === 0}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-zinc-900 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:bg-zinc-300 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300 dark:disabled:bg-zinc-700 dark:disabled:text-zinc-400"
        >
          {stage === "reviewing" && (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white dark:border-zinc-900/30 dark:border-t-zinc-900" />
          )}
          {stage === "reviewing" ? "Reviewing… usually a few seconds" : "Review NDA"}
        </button>
      </section>

      {result && (
        <section className="flex flex-col gap-3">
          <ResultCard result={result} />
        </section>
      )}

      <section className="flex flex-col gap-3 border-t border-zinc-100 pt-6 dark:border-zinc-800">
        <details className="rounded-lg border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-900">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400">
            How it works
          </summary>
          <ol className="mt-2 list-decimal space-y-1 pl-4 text-xs leading-relaxed text-zinc-600 dark:text-zinc-400">
            <li>The NDA and requirement are sent to the selected language model.</li>
            <li>The model returns a structured classification and supporting quotes.</li>
            <li>NDATrace verifies that quoted evidence exists in the source NDA.</li>
            <li>The reviewer checks the evidence and makes the final decision.</li>
          </ol>
        </details>

        <div className="rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs leading-relaxed text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
          Document text is treated as contract content, but adversarial document content remains a
          known limitation of this prototype.
        </div>

        <LimitationsPanel />
      </section>
    </main>
  );
}

function StepLabel({ n, text }: { n: number; text: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-900 text-[11px] font-semibold text-white dark:bg-zinc-100 dark:text-zinc-900">
        {n}
      </span>
      <span className="text-xs font-bold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">{text}</span>
    </div>
  );
}

function ModeButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-2.5 py-1 font-medium transition-colors ${
        active
          ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
          : "text-zinc-500 hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
      }`}
    >
      {label}
    </button>
  );
}
