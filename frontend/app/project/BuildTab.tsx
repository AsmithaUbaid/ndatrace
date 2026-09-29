"use client";

import { presentation } from "@/data/projectPresentation";
import { Expandable, Section } from "@/components/project/Primitives";
import { ProvenanceChip } from "@/components/project/ProvenanceChip";

const p = presentation;

export function BuildTab() {
  return (
    <div>
      <header className="relative overflow-hidden rounded-3xl border border-zinc-200 bg-white px-6 py-7 shadow-[0_18px_50px_-34px_rgba(24,24,27,0.4)] sm:px-8">
        <div aria-hidden className="absolute -right-20 -top-24 h-56 w-56 rounded-full bg-sky-100/70 blur-3xl" />
        <div className="relative"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Implementation view</p><h1 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-950">Build & Architecture</h1><p className="mt-2 max-w-2xl text-sm leading-6 text-zinc-600">A technical view of the frozen runtime, controls, ownership boundaries, and reproducibility trail.</p></div>
      </header>

      <Section eyebrow="Runtime" title="The implementation stack">
        <RuntimeFlow />
      </Section>

      <Section eyebrow="Minimum viable path" title="Smallest working product slice">
        <SmallestSlice />
      </Section>

      <Section eyebrow="Build vs rent" title="Where each responsibility lives">
        <BuildVsBuy />
      </Section>

      <Section eyebrow="Configuration" title="Frozen runtime choices">
        <FrozenConfiguration />
      </Section>

      <Section eyebrow="Modules" title="What runs in the product path">
        <ModuleInventory />
      </Section>

      <Section eyebrow="Controls" title="Guardrails and observability">
        <Controls />
      </Section>

      <Section eyebrow="Reproducibility" title="Data and experiment lineage">
        <Reproducibility />
      </Section>

      <Section eyebrow="Scope" title="Intended use and boundaries">
        <IntendedUse />
      </Section>

      <Section eyebrow="Developer details" title="Files and full experiment log">
        <DeveloperDetails />
      </Section>
    </div>
  );
}

function RuntimeFlow() {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {p.flow.map((item, index) => (
          <div key={item.step} className="relative rounded-2xl border border-zinc-200 bg-zinc-50 p-4">
            <span className="text-[9px] font-bold uppercase tracking-wide text-zinc-400">{index + 1} · {item.kind}</span>
            <p className="mt-2 text-sm font-semibold leading-5 text-zinc-800">{item.step}</p>
          </div>
        ))}
      </div>
      <p className="mt-4 text-xs text-zinc-500">HTTP request → frozen RAG pipeline → structured response → reviewer confirmation.</p>
    </div>
  );
}

const SLICE_STEPS = ["NDA + requirement", "Retrieve", "One model call", "Structured result", "Evidence validation", "Reviewer output"];

function SmallestSlice() {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
      <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
        {SLICE_STEPS.map((step, index) => (
          <div key={step} className="contents">
            <div className="rounded-2xl border border-amber-200 bg-amber-50/60 px-3 py-4 text-center text-xs font-semibold text-amber-900">{step}</div>
            {index < SLICE_STEPS.length - 1 && <div className="hidden items-center justify-center text-zinc-300 lg:flex">→</div>}
          </div>
        ))}
      </div>
      <p className="mt-4 rounded-2xl bg-zinc-900 px-4 py-3 text-sm leading-6 text-zinc-200">
        A real NDA requirement returns a valid label and source-grounded evidence that the reviewer can inspect.
      </p>
    </div>
  );
}

function BuildVsBuy() {
  return (
    <div className="overflow-hidden rounded-3xl border border-zinc-200 bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-[10px] uppercase tracking-wide text-zinc-500"><tr><th className="px-5 py-3 font-medium">Layer</th><th className="px-4 py-3 font-medium">Ownership</th><th className="px-4 py-3 font-medium">Technology</th><th className="px-5 py-3 font-medium">Why</th></tr></thead>
          <tbody>{p.buildVsBuy.map((row) => <tr key={row.layer} className="border-b border-zinc-100 align-top last:border-0"><td className="px-5 py-4 font-semibold text-zinc-900">{row.layer}</td><td className="px-4 py-4 text-zinc-600">{row.ownRentReuse}</td><td className="px-4 py-4 font-mono text-xs text-zinc-600">{row.technology}</td><td className="px-5 py-4 leading-6 text-zinc-500">{row.why}</td></tr>)}</tbody>
        </table>
      </div>
    </div>
  );
}

function FrozenConfiguration() {
  return <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">{p.frozenConfig.map((row) => <div key={row.key} className="rounded-2xl border border-zinc-200 bg-white p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">{row.key}</p><p className="mt-2 break-words font-mono text-sm font-semibold text-zinc-800">{row.value}</p><p className="mt-2 text-[10px] text-sky-700">{row.experiment}</p></div>)}</div>;
}

function ModuleInventory() {
  return <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">{p.componentInventory.map((item) => <div key={item.name} className="rounded-2xl border border-zinc-200 bg-white p-5"><div className="flex items-start justify-between gap-2"><h3 className="font-semibold text-zinc-900">{item.name}</h3><span className={`rounded-full px-2 py-1 text-[9px] font-semibold ${item.runtimeOrExperimentOnly.startsWith("Runtime") ? "bg-emerald-100 text-emerald-800" : "bg-zinc-100 text-zinc-500"}`}>{item.runtimeOrExperimentOnly}</span></div><p className="mt-3 text-sm leading-6 text-zinc-600">{item.does}</p><p className="mt-3 text-xs text-zinc-400">{item.lineage}</p></div>)}</div>;
}

function Controls() {
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <div className="rounded-3xl border border-emerald-200 bg-emerald-50/60 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-emerald-800">Guardrails</p><ul className="mt-4 space-y-3 text-sm text-zinc-700"><li>✓ Structured output parser</li><li>✓ Verbatim evidence-source validation</li><li>✓ Human final authority</li><li>✓ No agent in the live path</li><li>✓ Bounded top-5 classifier context</li></ul></div>
      <div className="rounded-3xl border border-sky-200 bg-sky-50/60 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-sky-800">Observability</p><ul className="mt-4 space-y-3 text-sm text-zinc-700"><li>Review-level latency</li><li>Review-level API cost</li><li>Model and trace identifier</li><li>Retrieved clause provenance</li><li>Source-validation state</li></ul></div>
      <div className="lg:col-span-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{p.auditableMechanisms.map((item) => <div key={item.name} className="rounded-2xl border border-zinc-200 bg-white p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">{item.name}</p><p className="mt-2 text-xl font-semibold text-zinc-900">{item.value}{item.unit && <span className="ml-1 text-xs font-normal text-zinc-500">{item.unit}</span>}</p><div className="mt-2"><ProvenanceChip source={item.source} /></div></div>)}</div>
    </div>
  );
}

function Reproducibility() {
  const data = p.dataProvenance.contractnli;
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_0.8fr]">
      <div className="rounded-3xl border border-zinc-200 bg-white p-5"><div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold text-zinc-900">ContractNLI</h3><ProvenanceChip source={p.dataProvenance.source} /></div><p className="mt-2 text-sm text-zinc-500">{data.ndaCount} NDAs · {data.hypotheses} requirements · {data.examples.toLocaleString()} cases</p><div className="mt-5 grid grid-cols-3 gap-2">{(["train", "dev", "test"] as const).map((split) => <div key={split} className="rounded-xl bg-zinc-50 p-3"><p className="text-[9px] font-bold uppercase tracking-wide text-zinc-400">{split}</p><p className="mt-1 text-lg font-semibold tabular-nums text-zinc-900">{data.splits[split].cases.toLocaleString()}</p><p className="text-[10px] text-zinc-500">cases</p></div>)}</div></div>
      <div className="rounded-3xl border border-amber-200 bg-amber-50/70 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-amber-900">Evaluation discipline</p><p className="mt-3 text-sm leading-6 text-zinc-700">Gold labels and evidence are withheld from every inference architecture.</p><p className="mt-3 text-xs leading-5 text-zinc-500">{p.dataProvenance.reconstructionV2ProtocolCaveat}</p></div>
    </div>
  );
}

function IntendedUse() {
  return <div className="grid gap-5 md:grid-cols-2"><ScopeList title="Intended" items={p.intendedUse.intended} tone="emerald" /><ScopeList title="Not intended" items={p.intendedUse.notIntended} tone="rose" /></div>;
}

function ScopeList({ title, items, tone }: { title: string; items: readonly string[]; tone: "emerald" | "rose" }) {
  return <div className={`rounded-3xl border p-5 ${tone === "emerald" ? "border-emerald-200 bg-emerald-50/60" : "border-rose-200 bg-rose-50/60"}`}><h3 className={`text-xs font-bold uppercase tracking-wide ${tone === "emerald" ? "text-emerald-800" : "text-rose-800"}`}>{title}</h3><ul className="mt-4 space-y-3 text-sm text-zinc-700">{items.map((item) => <li key={item} className="flex gap-2"><span>{tone === "emerald" ? "✓" : "×"}</span>{item}</li>)}</ul></div>;
}

function DeveloperDetails() {
  return (
    <div className="space-y-3">
      <Expandable summary={<span className="text-sm font-medium text-zinc-700">Configuration file references</span>}>
        <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="text-[9px] uppercase tracking-wide text-zinc-400"><tr><th className="pb-2">Parameter</th><th className="pb-2">Value</th><th className="pb-2">Artifact</th></tr></thead><tbody>{p.frozenConfig.map((row) => <tr key={row.key} className="border-t border-zinc-200"><td className="py-2 pr-4 text-zinc-500">{row.key}</td><td className="py-2 pr-4 font-mono text-zinc-700">{row.value}</td><td className="py-2 font-mono text-zinc-400">{row.artifact}</td></tr>)}</tbody></table></div>
      </Expandable>
      <Expandable summary={<span className="text-sm font-medium text-zinc-700">Build / rent evidence references</span>}>
        <div className="space-y-2">{p.buildVsBuy.map((row) => <div key={row.layer} className="rounded-xl border border-zinc-200 bg-white p-3"><p className="text-xs font-semibold text-zinc-700">{row.layer}</p><p className="mt-1 font-mono text-[10px] text-zinc-400">{row.evidence}</p></div>)}</div>
      </Expandable>
      <Expandable summary={<span className="text-sm font-medium text-zinc-700">Full experiment log</span>}>
        <div className="space-y-6">{p.timeline.map((phase) => <div key={phase.phase}><h3 className="mb-2 text-[10px] font-bold uppercase tracking-wide text-zinc-400">{phase.phase}</h3><div className="space-y-2">{phase.experiments.map((item) => <details key={item.id} className="rounded-xl border border-zinc-200 bg-white p-3"><summary className="cursor-pointer text-xs font-medium text-zinc-700"><span className="mr-2 font-mono text-sky-700">{item.id}</span>{item.name}</summary><dl className="mt-3 space-y-2 text-xs"><Field label="Question" value={item.question} /><Field label="Changed" value={item.changed} /><Field label="Evidence" value={item.evidence} /><Field label="Decision" value={item.decision} /></dl></details>)}</div></div>)}</div>
      </Expandable>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) { return <div><dt className="text-[9px] font-bold uppercase tracking-wide text-zinc-400">{label}</dt><dd className="mt-0.5 text-zinc-600">{value}</dd></div>; }
