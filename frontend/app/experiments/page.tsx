type ComparisonRow = {
  system: string;
  role: string;
  accuracy: string;
  joint: string;
  contradictionRecall: string;
  inputTokens: string;
  apiCost: string;
  emphasis: "neutral" | "benchmark" | "runtime";
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
    inputTokens: "—",
    apiCost: "Local",
    emphasis: "neutral",
    strongest: [],
  },
  {
    system: "GPT-5-mini FULL",
    role: "Benchmark winner",
    accuracy: "77.6%",
    joint: "74.6%",
    contradictionRecall: "75.5%",
    inputTokens: "2,279",
    apiCost: "$0.00202",
    emphasis: "benchmark",
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
  neutral: "bg-white hover:bg-zinc-50/70",
  benchmark: "bg-sky-50/60 hover:bg-sky-50/90",
  runtime: "bg-orange-50/60 hover:bg-orange-50/90",
};

const roleClasses: Record<ComparisonRow["emphasis"], string> = {
  neutral: "border-zinc-200 bg-zinc-50 text-zinc-700",
  benchmark: "border-sky-200 bg-sky-50 text-sky-800",
  runtime: "border-orange-200 bg-orange-50 text-orange-800",
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
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-6 py-10">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
          Final architecture comparison
        </h1>
        <p className="mt-1 text-xs font-medium uppercase tracking-wide text-zinc-500">
          Final TEST: n=2,091
        </p>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-zinc-600">
          Four systems were evaluated across the same NDA-review task. The rule and Qwen systems
          provide deterministic/local baselines, GPT-5-mini FULL achieved the strongest benchmark
          Joint result, and GPT-5-mini RAG top-5 is the selected prototype runtime.
        </p>
      </header>

      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50/80 text-xs uppercase tracking-wide text-zinc-500">
            <tr>
              <th className="whitespace-nowrap px-4 py-3 font-medium">System</th>
              <th className="whitespace-nowrap px-4 py-3 font-medium">Role</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">Accuracy</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">Joint</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">C Recall</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">Input tokens</th>
              <th className="whitespace-nowrap px-4 py-3 text-right font-medium">
                API cost / case
              </th>
            </tr>
          </thead>
          <tbody className="text-zinc-700">
            {comparisonRows.map((row) => (
              <tr
                key={row.system}
                className={`border-b border-zinc-100 transition-colors last:border-0 ${rowClasses[row.emphasis]}`}
              >
                <td className="whitespace-nowrap px-4 py-3.5 font-medium text-zinc-900">
                  {row.system}
                </td>
                <td className="whitespace-nowrap px-4 py-3.5">
                  <span
                    className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-medium ${roleClasses[row.emphasis]}`}
                  >
                    {row.role}
                  </span>
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-right tabular-nums">
                  <Metric value={row.accuracy} strongest={row.strongest.includes("accuracy")} />
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-right tabular-nums">
                  <Metric value={row.joint} strongest={row.strongest.includes("joint")} />
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-right tabular-nums">
                  <Metric
                    value={row.contradictionRecall}
                    strongest={row.strongest.includes("contradictionRecall")}
                  />
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-right tabular-nums">
                  <Metric
                    value={row.inputTokens}
                    strongest={row.strongest.includes("inputTokens")}
                  />
                </td>
                <td className="whitespace-nowrap px-4 py-3.5 text-right tabular-nums">
                  <Metric value={row.apiCost} strongest={row.strongest.includes("apiCost")} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="text-sm leading-6 text-zinc-500">
        FULL is the benchmark winner; RAG is the production-oriented prototype architecture.
      </p>
    </main>
  );
}
