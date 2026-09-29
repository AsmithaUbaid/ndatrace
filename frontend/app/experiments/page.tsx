type ComparisonRow = {
  system: string;
  role: string;
  accuracy: string;
  joint: string;
  contradictionRecall: string;
  inputTokens: string;
  apiCost: string;
  emphasis: "neutral" | "reference" | "runtime";
  strongest: Array<"accuracy" | "joint" | "contradictionRecall" | "inputTokens" | "apiCost">;
};

const comparisonRows: ComparisonRow[] = [
  {
    system: "Rule",
    role: "Baseline",
    accuracy: "59.0%",
    joint: "50.1%",
    contradictionRecall: "16.8%",
    inputTokens: "—",
    apiCost: "No API",
    emphasis: "neutral",
    strongest: [],
  },
  {
    system: "Qwen",
    role: "Local baseline",
    accuracy: "49.9%",
    joint: "39.7%",
    contradictionRecall: "25.5%",
    // The canonical reconstruction-v2 Qwen summary has no input-token field.
    inputTokens: "—",
    apiCost: "Local",
    emphasis: "neutral",
    strongest: [],
  },
  {
    system: "GPT-5-mini FULL",
    role: "Quality reference",
    accuracy: "77.6%",
    joint: "74.6%",
    contradictionRecall: "75.5%",
    inputTokens: "2,279",
    apiCost: "$0.00202",
    emphasis: "reference",
    strongest: ["accuracy", "joint"],
  },
  {
    system: "GPT-5-mini RAG top-5",
    role: "Prototype runtime",
    accuracy: "76.8%",
    joint: "72.5%",
    contradictionRecall: "77.3%",
    inputTokens: "1,131",
    apiCost: "$0.00168",
    emphasis: "runtime",
    strongest: ["contradictionRecall", "inputTokens", "apiCost"],
  },
];

const rowClasses: Record<ComparisonRow["emphasis"], string> = {
  neutral: "bg-white hover:bg-zinc-50/80",
  reference:
    "bg-sky-50/55 shadow-[inset_3px_0_0_#38bdf8] hover:bg-sky-50/90",
  runtime:
    "bg-amber-50/60 shadow-[inset_3px_0_0_#f59e0b] hover:bg-amber-50/95",
};

const roleClasses: Record<ComparisonRow["emphasis"], string> = {
  neutral: "border-zinc-200 bg-white text-zinc-600 shadow-sm",
  reference: "border-sky-200 bg-sky-100/75 text-sky-800 shadow-sm",
  runtime: "border-amber-200 bg-amber-100/75 text-amber-900 shadow-sm",
};

function Metric({ value, strongest }: { value: string; strongest: boolean }) {
  return strongest ? (
    <strong className="font-semibold text-zinc-950">{value}</strong>
  ) : (
    <span>{value}</span>
  );
}

export default function ExperimentsPage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-7 px-4 py-8 sm:px-6 sm:py-10">
      <header className="relative overflow-hidden rounded-3xl border border-zinc-200/80 bg-white px-6 py-7 shadow-[0_16px_50px_-28px_rgba(24,24,27,0.35)] sm:px-8 sm:py-8">
        <div
          aria-hidden="true"
          className="absolute -right-20 -top-24 h-64 w-64 rounded-full bg-sky-100/70 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="absolute -bottom-28 right-24 h-56 w-56 rounded-full bg-amber-100/60 blur-3xl"
        />
        <div className="relative">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.16em] text-zinc-500">
              <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]" />
              Architecture evaluation
            </p>
            <p className="rounded-full border border-zinc-200 bg-white/80 px-3 py-1.5 text-xs font-medium text-zinc-600 shadow-sm backdrop-blur">
              Final TEST: n=2,091
            </p>
          </div>
          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-zinc-950 sm:text-4xl">
            Final architecture comparison
          </h1>
          <p className="mt-4 max-w-4xl text-sm leading-6 text-zinc-600 sm:text-[15px] sm:leading-7">
            Four systems were evaluated across the same NDA-review task. The rule and Qwen systems
            provide deterministic/local baselines, GPT-5-mini FULL achieved the strongest measured
            Joint result (quality reference), and GPT-5-mini RAG top-5 is the selected prototype runtime.
          </p>
        </div>
      </header>

      <section className="overflow-hidden rounded-2xl border border-zinc-200/90 bg-white shadow-[0_18px_50px_-32px_rgba(24,24,27,0.4)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-200 bg-gradient-to-r from-zinc-50 to-white px-5 py-4 sm:px-6">
          <div>
            <h2 className="text-sm font-medium text-zinc-900">System comparison</h2>
            <p className="mt-0.5 text-xs text-zinc-500">Shared NDA-review evaluation</p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500" aria-label="Row highlights">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-sky-400" /> Quality reference
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-400" /> Prototype
            </span>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table
            aria-label="Final architecture comparison"
            className="w-full min-w-[900px] text-left text-sm"
          >
            <thead className="border-b border-zinc-200 bg-zinc-50/70 text-[11px] uppercase tracking-[0.1em] text-zinc-500">
              <tr>
                <th className="whitespace-nowrap px-5 py-3.5 font-medium sm:px-6">System</th>
                <th className="whitespace-nowrap px-4 py-3.5 font-medium">Role</th>
                <th className="whitespace-nowrap px-4 py-3.5 text-right font-medium">Accuracy</th>
                <th className="whitespace-nowrap px-4 py-3.5 text-right font-medium">Joint</th>
                <th className="whitespace-nowrap px-4 py-3.5 text-right font-medium">C Recall</th>
                <th className="whitespace-nowrap px-4 py-3.5 text-right font-medium">Input tokens</th>
                <th className="whitespace-nowrap px-5 py-3.5 text-right font-medium sm:px-6">
                  API cost / case
                </th>
              </tr>
            </thead>
            <tbody className="text-zinc-700">
              {comparisonRows.map((row) => (
                <tr
                  key={row.system}
                  className={`border-b border-zinc-100 transition-colors duration-150 last:border-0 ${rowClasses[row.emphasis]}`}
                >
                  <td className="whitespace-nowrap px-5 py-4 font-medium text-zinc-900 sm:px-6">
                    {row.system}
                  </td>
                  <td className="whitespace-nowrap px-4 py-4">
                    <span
                      className={`inline-flex rounded-full border px-2.5 py-1 text-[11px] font-medium ${roleClasses[row.emphasis]}`}
                    >
                      {row.role}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 text-right tabular-nums">
                    <Metric value={row.accuracy} strongest={row.strongest.includes("accuracy")} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 text-right tabular-nums">
                    <Metric value={row.joint} strongest={row.strongest.includes("joint")} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 text-right tabular-nums">
                    <Metric
                      value={row.contradictionRecall}
                      strongest={row.strongest.includes("contradictionRecall")}
                    />
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 text-right tabular-nums">
                    <Metric
                      value={row.inputTokens}
                      strongest={row.strongest.includes("inputTokens")}
                    />
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-right tabular-nums sm:px-6">
                    <Metric value={row.apiCost} strongest={row.strongest.includes("apiCost")} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="flex items-start gap-3 rounded-xl border border-zinc-200/80 bg-white/70 px-4 py-3.5 text-sm leading-6 text-zinc-500 shadow-sm">
        <svg
          aria-hidden="true"
          className="mt-1 h-4 w-4 shrink-0 text-zinc-400"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 1 0 0-16 8 8 0 0 0 0 16Zm.75-11.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0ZM10 8.5a.75.75 0 0 1 .75.75v4.5a.75.75 0 0 1-1.5 0v-4.5A.75.75 0 0 1 10 8.5Z"
            clipRule="evenodd"
          />
        </svg>
        <p>FULL is the quality reference; RAG is the production-oriented prototype architecture.</p>
      </div>
    </main>
  );
}
