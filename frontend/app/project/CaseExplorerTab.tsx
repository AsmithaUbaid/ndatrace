"use client";

import { useMemo, useState } from "react";
import { presentation } from "@/data/projectPresentation";
import { Expandable } from "@/components/project/Primitives";
import type { CaseExplorerRequest } from "./page";

const p = presentation;
type CaseItem = (typeof p.cases.items)[number];
type ArchId = "rule" | "full_context" | "rag";
type AgentDemo = (typeof p.cases.agentDemoCases)[number];

const ARCHITECTURES: { id: ArchId; label: string; role: string }[] = [
  { id: "rule", label: "Rule", role: "Baseline" },
  { id: "full_context", label: "FULL", role: "Quality reference" },
  { id: "rag", label: "RAG", role: "Prototype runtime" },
];

const START_HERE = [
  ["simpleCorrect", "Clean success", "All systems pass L1 and L2"],
  ["retrievalMiss", "Retrieval miss", "FULL succeeds; RAG top-5 misses gold"],
  ["reasoningFailure", "Reasoning failure", "Source-valid output, wrong meaning"],
  ["evidenceFailure", "Evidence failure", "Correct label, insufficient evidence"],
  ["contradictionSuccess", "Contradiction", "Both model paths succeed"],
] as const;

function caseKey(c: CaseItem) { return `${c.docId}::${c.hypothesisId}`; }

// Quick filters — one-click presets over the same real fields the dropdowns below already
// filter on (failureType/outcome/architecture/contradictionOnly/agentOnly). "Agent tool-used"
// reuses the existing TRAIN agent demo toggle since no rag_agent architecture is joined to the
// TEST population (see populationNote) — it's a real, working view, not a placeholder.
const QUICK_FILTERS = [
  ["Successful RAG", { architecture: "rag" as ArchId, outcome: "success", failureType: "all", agentOnly: false }],
  ["Reasoning failures", { architecture: "rag" as ArchId, outcome: "failure", failureType: "reasoning_classification", agentOnly: false }],
  ["Retrieval failures", { architecture: "rag" as ArchId, outcome: "failure", failureType: "retrieval_limited", agentOnly: false }],
  ["Evidence failures", { architecture: "rag" as ArchId, outcome: "failure", failureType: "evidence_selection", agentOnly: false }],
  ["Contradictions", { failureType: "all", outcome: "all", contradictionOnly: true, agentOnly: false }],
  ["Agent tool-used", { agentOnly: true }],
] as const satisfies readonly (readonly [string, Partial<QuickFilterState>])[];

type QuickFilterState = {
  architecture: ArchId;
  outcome: string;
  failureType: string;
  contradictionOnly: boolean;
  agentOnly: boolean;
};

export function CaseExplorerTab({ initialRequest = {} }: { initialRequest?: CaseExplorerRequest }) {
  const [query, setQuery] = useState("");
  const [label, setLabel] = useState("all");
  const [outcome, setOutcome] = useState(initialRequest.failuresOnly ? "failure" : "all");
  const [failureType, setFailureType] = useState(initialRequest.failureType ?? "all");
  const [architecture, setArchitecture] = useState<ArchId>(initialRequest.architecture ?? "rag");
  const [l1, setL1] = useState("all");
  const [l2, setL2] = useState("all");
  const [contradictionOnly, setContradictionOnly] = useState(false);
  const [agentOnly, setAgentOnly] = useState(false);
  const [selectedKey, setSelectedKey] = useState<string | null>(initialRequest.caseKey ?? p.cases.startHere.simpleCorrect);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(p.cases.agentDemoCases[0]?.caseId ?? null);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return p.cases.items.filter((item) => {
      const result = item.architectures[architecture];
      if (label !== "all" && item.goldLabel !== label) return false;
      if (contradictionOnly && item.goldLabel !== "Contradiction") return false;
      if (outcome === "success" && !result.jointPass) return false;
      if (outcome === "failure" && result.jointPass) return false;
      if (failureType !== "all" && item.failureType !== failureType) return false;
      if (l1 !== "all" && result.l1Pass !== (l1 === "pass")) return false;
      if (l2 !== "all" && result.l2Pass !== (l2 === "pass")) return false;
      return !needle || `${item.caseId} ${item.requirement}`.toLowerCase().includes(needle);
    });
  }, [architecture, contradictionOnly, failureType, l1, l2, label, outcome, query]);

  const selected = filtered.find((item) => caseKey(item) === selectedKey) ?? filtered[0] ?? null;
  const agent = p.cases.agentDemoCases.find((item) => item.caseId === selectedAgent) ?? p.cases.agentDemoCases[0] ?? null;

  function applyQuickFilter(preset: Partial<QuickFilterState>) {
    if (preset.architecture !== undefined) setArchitecture(preset.architecture);
    if (preset.outcome !== undefined) setOutcome(preset.outcome);
    if (preset.failureType !== undefined) setFailureType(preset.failureType);
    if (preset.contradictionOnly !== undefined) setContradictionOnly(preset.contradictionOnly);
    if (preset.agentOnly !== undefined) setAgentOnly(preset.agentOnly);
  }

  return (
    <div className="space-y-6">
      <header className="relative overflow-hidden rounded-3xl border border-zinc-200 bg-white px-6 py-7 shadow-[0_18px_50px_-34px_rgba(24,24,27,0.4)] sm:px-8">
        <div aria-hidden className="absolute -right-20 -top-24 h-56 w-56 rounded-full bg-amber-100/70 blur-3xl" />
        <div className="relative"><p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Saved final outputs</p><h1 className="mt-3 text-3xl font-semibold tracking-tight text-zinc-950">Case Explorer</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-zinc-600">Inspect genuine TEST outputs or switch to the separate TRAIN agent demo. No architecture is joined across splits.</p><p className="mt-3 text-xs text-zinc-500">{p.cases.matchedCaseCount.toLocaleString()} TEST cases safely matched · {p.cases.browserCaseCount.toLocaleString()} examples loaded for browsing</p></div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[310px_minmax(0,1fr)]">
        <aside className="space-y-4 lg:sticky lg:top-28 lg:self-start">
          <div className="rounded-2xl border border-amber-200 bg-amber-50/35 p-4 shadow-sm"><p className="mb-3 text-[10px] font-bold uppercase tracking-[0.14em] text-amber-800">Start here</p><div className="space-y-2">{START_HERE.map(([key, title, hint]) => { const id=p.cases.startHere[key]; if(!id) return null; return <button key={key} type="button" onClick={() => { setAgentOnly(false); setQuery(""); setLabel("all"); setOutcome("all"); setFailureType("all"); setL1("all"); setL2("all"); setContradictionOnly(false); setSelectedKey(id); }} className={`w-full rounded-xl border bg-white px-3 py-2.5 text-left ${selectedKey===id&&!agentOnly?"border-amber-400 ring-1 ring-amber-200":"border-zinc-200 hover:bg-zinc-50"}`}><span className="block text-xs font-semibold text-zinc-800">{title}</span><span className="mt-0.5 block text-[10px] leading-4 text-zinc-500">{hint}</span></button>; })}<button type="button" onClick={()=>setAgentOnly(true)} className={`w-full rounded-xl border bg-white px-3 py-2.5 text-left ${agentOnly?"border-amber-400 ring-1 ring-amber-200":"border-zinc-200 hover:bg-zinc-50"}`}><span className="block text-xs font-semibold text-zinc-800">Saved agent tool trace</span><span className="mt-0.5 block text-[10px] leading-4 text-zinc-500">Experimental TRAIN case · not in shipped runtime</span></button></div></div>

          <Expandable summary={<span className="text-xs font-semibold text-zinc-700">Browse and filter all cases</span>}><div className="pt-3"><div className="flex flex-wrap gap-2">{QUICK_FILTERS.map(([qlabel, preset]) => <button key={qlabel} type="button" onClick={() => applyQuickFilter(preset)} className="rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1.5 text-[11px] font-medium text-zinc-700 hover:bg-zinc-100">{qlabel}</button>)}</div></div></Expandable>

          <details className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm"><summary className="cursor-pointer text-xs font-semibold text-zinc-700">Advanced filter console</summary><div className="mt-3 space-y-2">
            <input aria-label="Search cases" type="search" value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Search ID or requirement…" className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm" />
            <FilterSelect label="Gold label" value={label} onChange={setLabel} options={[["all","All labels"],["Entailment","Entailment"],["Contradiction","Contradiction"],["NotMentioned","Not Mentioned"]]} />
            <FilterSelect label="Success / failure" value={outcome} onChange={setOutcome} options={[["all","All outcomes"],["success","Joint success"],["failure","Joint failure"]]} />
            <FilterSelect label="Failure type" value={failureType} onChange={setFailureType} options={[["all","All failure types"],["reasoning_classification","Reasoning / classification"],["evidence_selection","Evidence selection"],["retrieval_limited","Retrieval-limited"],["runtime_parser_source_validity","Runtime / parser / source"]]} />
            <FilterSelect label="Architecture" value={architecture} onChange={(v)=>setArchitecture(v as ArchId)} options={[["rule","Rule"],["full_context","FULL"],["rag","RAG"]]} />
            <div className="grid grid-cols-2 gap-2"><FilterSelect label="L1" value={l1} onChange={setL1} options={[["all","Any L1"],["pass","L1 pass"],["fail","L1 fail"]]} /><FilterSelect label="L2" value={l2} onChange={setL2} options={[["all","Any L2"],["pass","L2 pass"],["fail","L2 fail"]]} /></div>
            <Check label="Contradiction only" checked={contradictionOnly} onChange={setContradictionOnly} />
            <Check label="Agent tool used · TRAIN" checked={agentOnly} onChange={setAgentOnly} />
          </div></details>

          <div className="max-h-[310px] overflow-y-auto rounded-2xl border border-zinc-200 bg-white shadow-sm">{(agentOnly ? p.cases.agentDemoCases : filtered).slice(0,120).map((item) => { const id=agentOnly?(item as AgentDemo).caseId:caseKey(item as CaseItem); const active=agentOnly?selectedAgent===id:selectedKey===id; return <button key={id} type="button" onClick={()=>agentOnly?setSelectedAgent(id):setSelectedKey(id)} className={`block w-full border-b border-zinc-100 px-4 py-3 text-left last:border-0 ${active?"bg-sky-50":"hover:bg-zinc-50"}`}><span className="block text-xs font-medium text-zinc-700">{id}</span><span className="mt-0.5 block truncate text-[10px] text-zinc-400">{agentOnly?(item as AgentDemo).requirement:`${(item as CaseItem).goldLabel} · ${(item as CaseItem).failureType.replaceAll("_"," ")}`}</span></button>; })}{!agentOnly&&filtered.length===0&&<p className="p-4 text-xs text-zinc-500">No cases match these filters.</p>}</div>
        </aside>

        <main className="min-w-0">{agentOnly ? (agent ? <AgentDemoDetail item={agent} /> : null) : (selected ? <CaseDetail item={selected} /> : null)}</main>
      </div>
      <Expandable summary={<span className="text-xs font-medium text-zinc-600">Population and matching safeguards</span>}><p className="text-xs leading-5 text-zinc-500">{p.cases.populationNote}</p></Expandable>
    </div>
  );
}

function CaseDetail({ item }: { item: CaseItem }) {
  const featured = p.cases.featured.find((row) => row.caseKey === caseKey(item));
  return <div className="space-y-5"><section className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm sm:p-6"><div className="flex flex-wrap items-center justify-between gap-3"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-400">{item.split} evaluation case</p><span className="text-[10px] text-zinc-400">{item.caseId}</span></div><h2 className="mt-3 text-xl font-semibold leading-8 text-zinc-950">{item.requirement}</h2><div className="mt-5 flex flex-wrap items-center gap-3 rounded-2xl bg-zinc-100 px-4 py-3"><span className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Human gold answer</span><Verdict label={item.goldLabel} /></div><div className="mt-5"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Actual gold clause</p>{item.goldEvidence.length?<div className="mt-2 space-y-2">{item.goldEvidence.map((quote)=><blockquote key={quote} className="rounded-xl border border-amber-100 bg-amber-50/60 p-3 font-mono text-xs leading-5 text-zinc-700">{quote}</blockquote>)}</div>:<p className="mt-2 text-sm text-zinc-500">NotMentioned has no positive gold evidence span.</p>}</div></section><section><div className="mb-3"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-sky-700">Saved architecture outputs</p><h2 className="mt-1 text-xl font-semibold text-zinc-950">What each system actually returned</h2></div><div className="grid gap-4 xl:grid-cols-3">{ARCHITECTURES.map((arch)=><ArchitectureResult key={arch.id} arch={arch} item={item} />)}</div></section><section className="grid gap-4 md:grid-cols-2"><div className="rounded-2xl border border-zinc-200 bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Failure classification · RAG</p><p className="mt-2 text-lg font-semibold capitalize text-zinc-900">{item.failureType.replaceAll("_"," ")}</p><p className="mt-2 text-xs leading-5 text-zinc-500">Derived with the frozen E20 taxonomy: retrieval coverage first, then source/parser validity, label correctness, and evidence success.</p></div><div className="rounded-2xl border border-sky-200 bg-sky-50/60 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-sky-700">Why this case matters</p><p className="mt-2 text-sm leading-6 text-zinc-700">{featured?.why ?? "This saved case exposes a concrete difference between architecture outputs without inferring unavailable behavior."}</p></div></section></div>;
}

function ArchitectureResult({ arch, item }: { arch: (typeof ARCHITECTURES)[number]; item: CaseItem }) {
  const result=item.architectures[arch.id];
  return <article className={`rounded-2xl border bg-white p-5 shadow-sm ${arch.id==="rag"?"border-amber-300":arch.id==="full_context"?"border-sky-200":"border-zinc-200"}`}><div className="flex flex-wrap items-start justify-between gap-2"><div><h3 className="font-semibold text-zinc-900">{arch.label}</h3><p className="text-[10px] text-zinc-400">{arch.role}</p></div><Verdict label={result.predictedLabel} /></div><div className="mt-4 flex flex-wrap gap-2"><EvalBadge level="L1" value={result.l1Pass} /><EvalBadge level="L2" value={result.l2Pass} /><EvalBadge level="Joint" value={result.jointPass} /></div><div className="mt-5"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Evidence</p>{result.evidence.length?<div className="mt-2 space-y-2">{result.evidence.map((quote)=><blockquote key={quote} className="max-h-36 overflow-y-auto rounded-xl border border-amber-100 bg-amber-50/60 p-3 font-mono text-xs leading-5 text-zinc-700">{quote}</blockquote>)}</div>:<p className="mt-2 text-sm text-zinc-400">No evidence returned.</p>}</div><dl className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-zinc-50 p-3 text-xs"><TraceValue label="Latency" value={result.latencyMs==null?"Unavailable":`${Math.round(result.latencyMs)} ms`} /><TraceValue label="Input tokens" value={result.tokensIn==null?"Unavailable":result.tokensIn.toLocaleString()} /><TraceValue label="Cost" value={result.costUsd==null?"Unavailable":`$${result.costUsd.toFixed(6)}`} /><TraceValue label="Source valid" value={result.sourceValid?"Yes":"No"} /></dl><Expandable summary={<span className="text-xs font-medium text-zinc-600">Technical trace</span>}><p className="text-xs text-zinc-500">Parser: {result.parseStatus} · model: {result.model}</p>{"retrievedContext" in result && result.retrievedContext && <div className="mt-3 space-y-2">{result.retrievedContext.map((chunk)=><div key={chunk.chunkId} className="rounded-lg border border-zinc-200 bg-zinc-50 p-3"><p className="text-[10px] font-semibold text-zinc-500">Rank {chunk.rank} · chunk {chunk.chunkId} · reranker {chunk.rerankerScore.toFixed(3)}</p><p className="mt-1 max-h-28 overflow-y-auto font-mono text-[10px] leading-5 text-zinc-600">{chunk.text}</p></div>)}</div>}<details className="mt-4"><summary className="cursor-pointer text-[10px] font-semibold uppercase tracking-wide text-zinc-400">Developer details · raw structured output</summary><pre className="mt-2 max-h-60 overflow-auto rounded-lg bg-zinc-900 p-3 text-[10px] leading-5 text-zinc-300">{result.rawStructuredOutput ?? "Not recorded for this deterministic system."}</pre></details></Expandable></article>;
}

function AgentDemoDetail({ item }: { item: AgentDemo }) {
  return <div className="space-y-5"><section className="rounded-3xl border border-amber-200 bg-amber-50/45 p-6"><div className="flex flex-wrap items-center justify-between gap-2"><div><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-amber-800">Experimental · not in shipped runtime</p><p className="mt-1 text-[10px] text-zinc-500">Separate saved E11 TRAIN trace</p></div><span className="text-[10px] text-zinc-500">{item.caseId}</span></div><h2 className="mt-3 text-xl font-semibold leading-8 text-zinc-950">{item.requirement}</h2><div className="mt-5 grid gap-2 sm:grid-cols-5"><TraceStep label="Why agent?" value="Current evidence might be insufficient" /><TraceStep label="Tool used" value={item.agent.steps.map((s)=>s.action).join(" + ")} /><TraceStep label="Observation" value="Additional saved context returned" /><TraceStep label="Final result" value={item.agent.prediction ?? "Unavailable"} /><TraceStep label="Recovered?" value={item.agent.jointPass?"Yes":"No"} /></div><div className="mt-4 flex flex-wrap gap-2"><Verdict label={item.agent.prediction} /><EvalBadge level="L1" value={item.agent.l1Pass} /><EvalBadge level="L2" value={item.agent.l2Pass} /></div><p className="mt-4 text-sm leading-6 text-zinc-600">{item.why}</p></section><section className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Saved structured actions</p><div className="mt-4 space-y-4">{item.agent.steps.map((step)=><div key={step.step} className="rounded-2xl border border-zinc-200 p-4"><p className="text-xs font-semibold text-sky-800">Step {step.step} · {step.action}</p>{step.arguments&&<p className="mt-2 font-mono text-xs text-zinc-600">Arguments: {JSON.stringify(step.arguments)}</p>}<Expandable summary={<span className="text-xs text-zinc-600">Inspect bounded tool output</span>}><p className="mt-2 max-h-56 overflow-y-auto whitespace-pre-wrap rounded-xl bg-zinc-50 p-3 font-mono text-[10px] leading-5 text-zinc-600">{JSON.stringify(step.result,null,2)}</p></Expandable></div>)}<div className="rounded-2xl bg-zinc-900 p-4 text-white"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Final</p><p className="mt-1 text-sm">{item.agent.finalAction} → {item.agent.prediction} · Joint {item.agent.jointPass?"PASS":"FAIL"}</p></div></div></section></div>;
}

function TraceStep({ label, value }: { label:string; value:string }) { return <div className="rounded-xl border border-amber-200 bg-white p-3"><p className="text-[9px] font-bold uppercase tracking-wide text-zinc-400">{label}</p><p className="mt-1 text-[11px] font-medium leading-4 text-zinc-700">{value}</p></div>; }

function FilterSelect({ label, value, onChange, options }: { label:string; value:string; onChange:(value:string)=>void; options:readonly (readonly [string,string])[] }) { return <label className="block"><span className="sr-only">{label}</span><select aria-label={label} value={value} onChange={(e)=>onChange(e.target.value)} className="w-full rounded-xl border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-700">{options.map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></label>; }
function Check({ label, checked, onChange }: { label:string; checked:boolean; onChange:(value:boolean)=>void }) { return <label className="flex items-center gap-2 rounded-xl bg-zinc-50 px-3 py-2 text-xs text-zinc-700"><input type="checkbox" checked={checked} onChange={(e)=>onChange(e.target.checked)} className="accent-zinc-900" />{label}</label>; }
function Verdict({ label }: { label:string|null }) { const cls=label==="Contradiction"?"bg-rose-100 text-rose-800":label==="Entailment"?"bg-emerald-100 text-emerald-800":"bg-zinc-200 text-zinc-700"; return <span className={`inline-flex rounded-full px-3 py-1.5 text-xs font-semibold ${cls}`}>{label??"Unavailable"}</span>; }
function EvalBadge({ level, value }: { level:"L1"|"L2"|"Joint"; value:boolean }) { return <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${value?"bg-emerald-100 text-emerald-800":"bg-rose-100 text-rose-800"}`}>{level} {value?"PASS":"FAIL"}</span>; }
function TraceValue({ label, value }: { label:string; value:string }) { return <div><dt className="text-[9px] font-bold uppercase tracking-wide text-zinc-400">{label}</dt><dd className="mt-1 font-medium tabular-nums text-zinc-700">{value}</dd></div>; }
