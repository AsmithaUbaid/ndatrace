"use client";

import { type ReactNode } from "react";
import { presentation } from "@/data/projectPresentation";
import { ProvenanceChip } from "@/components/project/ProvenanceChip";
import { Expandable, Section, StatusBadge, type Status } from "@/components/project/Primitives";
import type { CaseExplorerRequest } from "./page";

const p = presentation;
const charts = p.charts;

const STORY_NAV = [
  ["problem", "Problem"],
  ["reasoning", "Reasoning"],
  ["retrieval", "Retrieval"],
  ["architecture", "Architecture"],
  ["failures", "Failures"],
  ["agent", "Agent"],
  ["security", "Security"],
  ["economics", "Economics"],
  ["final-system", "Final system"],
] as const;

export function OverviewTab({ onNavigateToCases }: { onNavigateToCases: (request?: CaseExplorerRequest) => void }) {
  return (
    <div>
      <Hero />
      <StoryNavigation />

      <ChapterDivider number="01" title="Frame the problem" />
      <Section id="problem" eyebrow="Problem" title="The review problem">
        <ProblemDefinition />
      </Section>

      <Section eyebrow="Success definition" title="Getting the label right is only half the job">
        <SuccessDefinition />
      </Section>

      <Section eyebrow="Evaluation framework" title="Two levels of correctness">
        <EvaluationLevels />
      </Section>

      <ChapterDivider number="02" title="Build the intelligence" />
      <Section id="reasoning" eyebrow="Oracle" title="First isolate reasoning from retrieval">
        <OracleExperiment />
      </Section>

      <Section eyebrow="Model selection" title="Which model earned the next experiment?">
        <ModelSelection />
      </Section>

      <Section eyebrow="Prompt selection" title="How much instruction did the model actually need?">
        <PromptSelection />
      </Section>

      <Section id="retrieval" eyebrow="Retrieval design" title="Finding the clause before asking the model">
        <RetrievalDesign />
      </Section>

      <ChapterDivider number="03" title="Earn the architecture" />
      <Section id="architecture" eyebrow="Architecture ladder" title="How much architecture did the problem actually need?">
        <ArchitectureLadder />
      </Section>

      <Section eyebrow="FULL vs RAG" title="The quality / operability trade-off">
        <FullVsRag />
      </Section>

      <Section eyebrow="One case explains the difference" title="What the system actually did">
        <OverviewCase onSeeCase={onNavigateToCases} />
      </Section>

      <Section id="failures" eyebrow="Failure analysis" title="Where the remaining failures actually live">
        <FailureAnalysis onSeeCases={onNavigateToCases} />
      </Section>

      <Section eyebrow="Saved failure cases" title="The transitions are visible in real outputs">
        <TransitionCases onSeeCase={onNavigateToCases} />
      </Section>

      <Section eyebrow="Static context experiment" title="Why not just retrieve more clauses?">
        <StaticExpansion />
      </Section>

      <Section eyebrow="Agent justification" title="Could dynamic investigation recover the retrieval-fixable cases?">
        <AgentJustification />
      </Section>

      <Section eyebrow="Agent tools" title="What could the agent actually do?">
        <AgentTools />
      </Section>

      <Section id="agent" eyebrow="Agent experiments" title="We gave the agent a real chance">
        <AgentExperiments />
      </Section>

      <Section eyebrow="Routing / review" title="Can we review only the risky cases?">
        <RoutingReview />
      </Section>

      <ChapterDivider number="04" title="Can this operate?" />
      <Section id="security" eyebrow="Security & governance" title="We tested the system before trusting it">
        <SecuritySection />
      </Section>

      <ChapterDivider number="05" title="What survives?" />
      <Section eyebrow="Final TEST · n = 2,091" title="What survived full evaluation?">
        <FinalTest onSeeCases={onNavigateToCases} />
      </Section>

      <Section eyebrow="Final failure analysis" title="What would I improve next?">
        <FinalFailureAnalysis />
      </Section>

      <Section id="economics" eyebrow="Business evaluation" title="The cheapest model call was not the cheapest workflow">
        <BusinessEvaluation />
      </Section>

      <Section eyebrow="Ship decision" title="What belongs in the prototype">
        <ShipDecision />
      </Section>

      <Section id="final-system" eyebrow="Final system" title="The system that survived the experiments">
        <FinalSystem />
      </Section>

      <Section eyebrow="Experiment journey" title="Every layer had to earn its place">
        <ExperimentJourney />
      </Section>
    </div>
  );
}

function ChapterDivider({ number, title }: { number: string; title: string }) {
  return (
    <div className="mt-10 flex items-center gap-4 first:mt-0">
      <span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[11px] font-bold tracking-wide text-amber-800">{number}</span>
      <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-zinc-400">{title}</p>
      <div className="h-px flex-1 bg-gradient-to-r from-zinc-200 to-transparent" />
    </div>
  );
}

function Hero() {
  return (
    <header className="relative overflow-hidden rounded-3xl border border-zinc-200/80 bg-white px-6 py-8 shadow-[0_18px_55px_-32px_rgba(24,24,27,0.4)] sm:px-9 sm:py-10">
      <div aria-hidden className="absolute -right-24 -top-28 h-72 w-72 rounded-full bg-sky-100/75 blur-3xl" />
      <div aria-hidden className="absolute -bottom-32 right-28 h-64 w-64 rounded-full bg-amber-100/70 blur-3xl" />
      <div className="relative">
        <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-zinc-500">
          <span className="h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_0_4px_rgba(16,185,129,0.12)]" />
          Evidence-grounded NDA review
        </p>
        <h1 className="mt-5 max-w-4xl text-3xl font-semibold tracking-tight text-zinc-950 sm:text-5xl sm:leading-[1.08]">
          Can AI review an NDA without asking a lawyer to trust a black-box verdict?
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-6 text-zinc-600 sm:text-base">
          NDATrace classifies each confidentiality requirement and returns the exact source clause, keeping verification—and the final decision—with the reviewer.
        </p>

        <div className="mt-7 grid overflow-hidden rounded-2xl border border-zinc-200 bg-white/80 sm:grid-cols-5">
          {p.hero.chips.map((chip) => (
            <div key={chip.label} className="border-b border-zinc-100 px-4 py-3 last:border-0 sm:border-b-0 sm:border-r sm:last:border-r-0">
              <div className="text-xs font-semibold tracking-wide text-zinc-900">{chip.label.toUpperCase()}</div>
              <div className="mt-0.5 text-[11px] text-zinc-500">{chip.sub}</div>
            </div>
          ))}
        </div>

        <div className="mt-7 grid gap-4 sm:grid-cols-2">
          <HeroMetric tone="sky" value={`${p.hero.result.quality.value}%`} label="Best measured Joint" source={p.hero.result.quality.source} />
          <HeroMetric tone="amber" value={`${p.hero.result.productPath.value}%`} label="Prototype runtime Joint" source={p.hero.result.productPath.source} />
        </div>
        <p className="mt-3 text-xs text-zinc-500">RAG uses 50.4% fewer classifier input tokens.</p>
      </div>
    </header>
  );
}

function HeroMetric({ tone, value, label, source }: { tone: "sky" | "amber"; value: string; label: string; source: Parameters<typeof ProvenanceChip>[0]["source"] }) {
  return (
    <div className={`rounded-2xl border px-5 py-4 ${tone === "sky" ? "border-sky-200 bg-sky-50/70" : "border-amber-200 bg-amber-50/75"}`}>
      <div className="text-3xl font-semibold tabular-nums text-zinc-950">{value}</div>
      <div className="mt-1 text-sm font-medium text-zinc-700">{label}</div>
      <div className="mt-2"><ProvenanceChip source={source} /></div>
    </div>
  );
}

function StoryNavigation() {
  return (
    <nav className="mt-5 overflow-x-auto rounded-2xl border border-zinc-200 bg-white/70 px-3 py-2" aria-label="Project story chapters">
      <div className="mx-auto flex w-max min-w-full justify-start gap-1 lg:justify-center">
        {STORY_NAV.map(([id, label]) => (
          <a key={id} href={`#${id}`} className="shrink-0 rounded-full px-3 py-1.5 text-xs font-medium text-zinc-500 hover:bg-white hover:text-zinc-900">
            {label}
          </a>
        ))}
      </div>
    </nav>
  );
}

function ProblemDefinition() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
        <JourneyLane label="Today" tone="neutral" steps={["Requirement", "Search whole NDA manually", "Interpret clauses and exceptions", "Make decision"]} />
        <div className="hidden text-2xl text-zinc-300 lg:block">→</div>
        <JourneyLane label="With NDATrace" tone="amber" steps={["Requirement", "Retrieve likely clauses", "Classify + cite evidence", "Reviewer verifies"]} />
      </div>
      <div className="grid gap-3 rounded-2xl bg-zinc-900 px-5 py-5 text-white sm:grid-cols-3">
        <LabelValue label="Persona" value="Enterprise legal-operations reviewer" />
        <LabelValue label="Need" value="Fast requirement-level review" />
        <LabelValue label="Constraint" value="Evidence must remain human-verifiable" />
        <p className="sm:col-span-3 border-t border-white/10 pt-3 text-sm text-zinc-300">Human remains final authority.</p>
      </div>
    </div>
  );
}

function JourneyLane({ label, steps, tone }: { label: string; steps: string[]; tone: "neutral" | "amber" }) {
  return (
    <div className={`rounded-3xl border p-5 ${tone === "amber" ? "border-amber-200 bg-amber-50/60" : "border-zinc-200 bg-white"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${tone === "amber" ? "text-amber-800" : "text-zinc-500"}`}>{label}</p>
      <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center lg:flex-col lg:items-stretch xl:flex-row xl:items-center">
        {steps.map((step, index) => (
          <div key={step} className="contents">
            <div className="rounded-xl border border-white bg-white px-3 py-2 text-center text-xs font-medium text-zinc-700 shadow-sm">{step}</div>
            {index < steps.length - 1 && <span className="text-center text-zinc-300">→</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function SuccessDefinition() {
  const scenarios = [
    ["✓", "Correct label + correct evidence", "Success", "emerald"],
    ["×", "Correct label + wrong evidence", "Fail", "rose"],
    ["×", "Wrong label + plausible evidence", "Fail", "rose"],
  ] as const;
  return (
    <div>
      <div className="grid items-center gap-3 rounded-3xl bg-gradient-to-r from-sky-50 via-white to-amber-50 px-5 py-7 text-center sm:grid-cols-[1fr_auto_1fr_auto_1fr]">
        <EquationTerm text="Correct label" /> <EquationSymbol value="+" /> <EquationTerm text="Correct supporting evidence" /> <EquationSymbol value="=" /> <EquationTerm text="Joint success" strong />
      </div>
      <div className="mt-5 grid gap-3 md:grid-cols-3">
        {scenarios.map(([icon, text, result, tone]) => (
          <div key={text} className="flex items-start gap-3 rounded-2xl border border-zinc-200 bg-white p-4">
            <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold ${tone === "emerald" ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700"}`}>{icon}</span>
            <div><p className="text-sm font-medium text-zinc-800">{text}</p><p className={`mt-1 text-[11px] font-bold uppercase tracking-wide ${tone === "emerald" ? "text-emerald-700" : "text-rose-700"}`}>{result}</p></div>
          </div>
        ))}
      </div>
      <div className="mt-5 flex flex-wrap gap-2 text-xs text-zinc-500">
        {p.whatGoodLooksLike.cards.slice(0, 3).map((item) => <span key={item.title} className="rounded-full border border-zinc-200 bg-white px-3 py-1.5">{item.title}</span>)}
      </div>
    </div>
  );
}

function EquationTerm({ text, strong = false }: { text: string; strong?: boolean }) {
  return <div className={`rounded-2xl border px-4 py-4 text-sm font-semibold ${strong ? "border-amber-300 bg-amber-100 text-amber-950" : "border-zinc-200 bg-white text-zinc-800"}`}>{text}</div>;
}
function EquationSymbol({ value }: { value: string }) { return <span className="text-xl font-medium text-zinc-400">{value}</span>; }

function EvaluationLevels() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        <EvaluationPanel
          level="L1"
          title="Structural / deterministic"
          question="Is the output structurally valid and grounded in the supplied document?"
          items={["Parser + schema", "Allowed label", "Source-valid evidence", "Valid provenance / spans", "No fabricated quote"]}
          tone="sky"
        />
        <EvaluationPanel
          level="L2"
          title="Semantic / task correctness"
          question="Did the model reach the correct conclusion and support it with the correct evidence?"
          items={["Correct label", "Correct evidence", "Joint success", "Contradiction Recall", "Human gold comparison"]}
          tone="amber"
        />
      </div>
      <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
        <div className="grid gap-2 text-center sm:grid-cols-[1fr_auto_1fr_auto_1fr_auto_1fr] sm:items-center">
          {[["Model output", "zinc"], ["L1 valid?", "sky"], ["L2 correct?", "amber"], ["Reviewer", "emerald"]].map(([label, tone], index) => (
            <div key={label} className="contents">
              <div className={`rounded-2xl px-4 py-3 text-sm font-semibold ${tone === "sky" ? "bg-sky-50 text-sky-900" : tone === "amber" ? "bg-amber-50 text-amber-950" : tone === "emerald" ? "bg-emerald-50 text-emerald-900" : "bg-zinc-100 text-zinc-800"}`}>{label}</div>
              {index < 3 && <span className="text-zinc-300">→</span>}
            </div>
          ))}
        </div>
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <Outcome label="L1 pass + L2 pass" result="Successful automated review" tone="emerald" />
          <Outcome label="L1 pass + L2 fail" result="Dangerous semantic error" tone="rose" />
          <Outcome label="L1 fail" result="Reject / human review" tone="zinc" />
        </div>
      </div>
      <div className="rounded-2xl border border-rose-200 bg-rose-50 px-5 py-4">
        <p className="text-sm font-bold uppercase tracking-[0.12em] text-rose-800">Passing L1 does not imply passing L2</p>
        <p className="mt-2 text-sm leading-6 text-zinc-700">A model can quote a real NDA clause—<strong>L1 pass</strong>—but interpret it incorrectly—<strong>L2 fail</strong>.</p>
      </div>
    </div>
  );
}

function EvaluationPanel({ level, title, question, items, tone }: { level: string; title: string; question: string; items: string[]; tone: "sky" | "amber" }) {
  const cls = tone === "sky" ? "border-sky-200 bg-sky-50/60 text-sky-800" : "border-amber-200 bg-amber-50/65 text-amber-900";
  return <div className={`rounded-3xl border p-6 ${cls}`}><div className="flex items-center gap-3"><span className="rounded-xl bg-white px-3 py-2 text-xl font-semibold shadow-sm">{level}</span><div><p className="text-[10px] font-bold uppercase tracking-[0.14em]">{title}</p><p className="mt-1 text-sm font-medium text-zinc-800">{question}</p></div></div><ul className="mt-5 grid grid-cols-2 gap-2 text-xs text-zinc-700">{items.map((item) => <li key={item} className="rounded-xl bg-white/80 px-3 py-2">✓ {item}</li>)}</ul><p className="mt-4 text-xs text-zinc-500">{level === "L1" ? "Deterministic. It does not judge legal meaning." : "Compared with human ContractNLI gold labels and evidence."}</p></div>;
}

function Outcome({ label, result, tone }: { label: string; result: string; tone: "emerald" | "rose" | "zinc" }) {
  const cls = tone === "emerald" ? "border-emerald-200 bg-emerald-50" : tone === "rose" ? "border-rose-200 bg-rose-50" : "border-zinc-200 bg-zinc-50";
  return <div className={`rounded-2xl border p-4 ${cls}`}><p className="text-xs font-semibold text-zinc-900">{label}</p><p className="mt-1 text-xs text-zinc-600">{result}</p></div>;
}

function OracleExperiment() {
  return (
    <div className="space-y-6">
      <ExperimentFrame why={p.causalStory.oracle.why} learned={p.causalStory.oracle.learned} next={p.causalStory.oracle.next} />
      <div className="grid gap-6 lg:grid-cols-[1.45fr_0.75fr]"><ChartShell title="Reasoning quality with the correct evidence supplied" subtitle={charts.oracleComparison.population}>
        <div className="space-y-5">
          {charts.oracleComparison.series.map((row) => (
            <div key={row.name}>
              <div className="mb-2 flex items-center justify-between gap-3 text-xs"><span className="font-medium text-zinc-700">{row.name}</span><span className="text-zinc-400">{row.hosted ? "Hosted" : "Local"}</span></div>
              <MetricBar label="Macro-F1" value={row.macroF1} tone="sky" />
              <MetricBar label="Contradiction recall" value={row.contradictionRecall} tone="amber" />
            </div>
          ))}
        </div>
      </ChartShell><div className="flex flex-col justify-between gap-4">
        <Callout eyebrow="Failure analysis" text={p.causalStory.oracle.failure} />
        <DecisionBar text="GPT-5-mini selected for hosted architecture evaluation." source={charts.oracleComparison.source} />
      </div></div>
    </div>
  );
}

function ModelSelection() {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ComparisonStrip label="Local" title="Qwen 2.5 7B" facts={["$0 API", "Weaker reasoning"]} tone="neutral" />
      <ComparisonStrip label="Hosted" title="GPT-5-mini" facts={["Higher reasoning quality", "Selected"]} tone="sky" />
      <div className="md:col-span-2 grid gap-3 rounded-2xl bg-zinc-100 p-4 sm:grid-cols-2">
        <LabelValue label="Technical impact" value="82% vs 30% Contradiction Recall with evidence supplied" dark />
        <LabelValue label="Operating impact" value="Hosted cost was small relative to reduced review risk" dark />
      </div>
    </div>
  );
}

function PromptSelection() {
  const story = p.causalStory.prompt;
  return (
    <div className="space-y-6">
      <ExperimentFrame why={story.why} learned={story.learned} next={story.next} />
      <div className="grid gap-3 md:grid-cols-3">
        {story.variants.map((variant) => (
          <div key={variant.id} className={`rounded-2xl border p-4 ${variant.id === "P0" ? "border-amber-200 bg-amber-50/60" : "border-zinc-200 bg-white"}`}>
            <div className="flex items-center gap-2"><span className="font-mono text-xs font-bold text-zinc-400">{variant.id}</span><h3 className="text-sm font-semibold text-zinc-900">{variant.name}</h3></div>
            <p className="mt-2 text-xs leading-5 text-zinc-600">{variant.attempt}</p>
          </div>
        ))}
      </div>
      <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <ChartShell title="On this controlled Qwen prompt experiment, more instruction weakened Contradiction handling" subtitle={charts.promptComparison.population}>
          <div className="space-y-4">
            {story.metrics.map((row) => <div key={row.id}><MetricBar label={`${row.id} · Contradiction recall`} value={row.contradictionRecall} tone={row.id === "P0" ? "amber" : "zinc"} /><p className="text-right text-[10px] text-zinc-400">Macro-F1 {row.macroF1.toFixed(3)}</p></div>)}
          </div>
        </ChartShell>
        <div className="rounded-3xl border border-zinc-200 bg-white p-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-400">P0 failure analysis · 88 errors</p>
          <div className="mt-4 grid grid-cols-2 gap-3"><SmallFinding label="Retrieval-limited" value={`${story.failure.retrievalLimited}`} /><SmallFinding label="Not retrieval-limited" value={`${story.failure.reasoningPromptLimited}`} /></div>
          <p className="mt-4 text-sm leading-6 text-zinc-700"><strong>{story.failure.carveoutIndicator} of {story.failure.nonRetrievalContradictionFailures}</strong> non-retrieval-limited Contradiction failures contained an exception or carve-out indicator.</p>
          <p className="mt-2 text-xs leading-5 text-zinc-500">{story.failure.caveat}</p>
          <p className="mt-3 text-xs leading-5 text-zinc-600">82 of 88 errors remained even when relevant evidence was available; this motivated investigation of model and decision limitations rather than assuming retrieval was the dominant bottleneck.</p>
          <ProvenanceChip source={story.source} />
        </div>
      </div>
      <div className="rounded-3xl border border-sky-200 bg-sky-50/55 p-5">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-sky-700">A promising prompt still had to replicate</p>
        <div className="mt-4 grid items-stretch gap-3 md:grid-cols-[1fr_auto_1fr_auto_0.8fr]">
          <Step label="E12B discovery" text={`P3 ${story.revisit.discovery.p3} vs P0 ${story.revisit.discovery.p0} Joint · +${story.revisit.discovery.delta}, one short of +${story.revisit.discovery.threshold} adoption`} />
          <ArrowRight />
          <Step label="E12C confirmation" text={`P0 ${story.revisit.confirmation.p0} vs P3 ${story.revisit.confirmation.p3} Joint · P3 ${story.revisit.confirmation.delta}`} />
          <ArrowRight />
          <Step label="Decision" text="Retain P0" emphasis />
        </div>
        <p className="mt-4 text-sm font-medium text-zinc-800">{story.revisit.lesson}</p>
      </div>
    </div>
  );
}

function RetrievalDesign() {
  const story = p.causalStory.retrieval;
  const chunkChart = charts.chunkSizeComparison;
  const topKChart = charts.topKComparison;
  const pool = charts.candidatePool;
  return (
    <div className="space-y-6">
      <ExperimentFrame why={story.why} learned={story.learned} next={story.next} />

      <div className="grid gap-6 lg:grid-cols-2">
        <ChartShell title="A. Chunking / chunk size" subtitle={chunkChart.population}>
          <div className="space-y-3">
            {chunkChart.series.map((row) => (
              <div key={row.name} className={`rounded-xl p-3 ${row.selected ? "bg-amber-50/70 ring-1 ring-amber-200" : "bg-zinc-50"}`}>
                <div className="mb-2 flex items-center justify-between gap-3 text-xs"><span className="font-medium text-zinc-700">{row.name}</span><span className="text-zinc-400">MRR {row.mrr.toFixed(3)}</span></div>
                <MetricBar label="Recall@5" value={row.recallAt5} tone={row.selected ? "amber" : "zinc"} compact />
              </div>
            ))}
          </div>
          <p className="mt-3 text-[11px] leading-5 text-zinc-400">{chunkChart.note}</p>
          <div className="mt-4"><DecisionBar text={chunkChart.decision} source={chunkChart.source} /></div>
        </ChartShell>

        <ChartShell title="B. Top-K" subtitle={topKChart.population}>
          <div className="space-y-3">
            {topKChart.series.map((row) => (
              <div key={row.name} className={`rounded-xl p-3 ${row.name.includes("selected") ? "bg-amber-50/70 ring-1 ring-amber-200" : "bg-zinc-50"}`}>
                <div className="mb-2 flex items-center justify-between gap-3 text-xs"><span className="font-medium text-zinc-700">{row.name}</span><span className="text-zinc-400">MRR {row.mrr.toFixed(3)}</span></div>
                <MetricBar label="Recall" value={row.recallAt5} tone={row.name.includes("selected") ? "amber" : "zinc"} compact />
              </div>
            ))}
          </div>
          <div className="mt-4"><DecisionBar text={topKChart.decision} source={topKChart.source} /></div>
        </ChartShell>
      </div>

      <ChartShell title="C. Candidate methods differ; reranked methods converge" subtitle={charts.retrievalComparison.population}>
        <div className="space-y-3">
          {charts.retrievalComparison.series.map((row) => (
            <div key={row.name} className={`rounded-xl p-3 ${row.stage === "reranked" ? "bg-amber-50/70" : "bg-zinc-50"}`}>
              <div className="mb-2 flex items-center justify-between gap-3 text-xs"><span className="font-medium text-zinc-700">{row.name}</span><span className="uppercase tracking-wide text-zinc-400">{row.stage}</span></div>
              <MetricBar label="Recall@5" value={row.recallAt5} tone={row.stage === "reranked" ? "amber" : "sky"} compact />
              <MetricBar label="Contradiction Recall@5" value={row.contradictionRecallAt5} tone="zinc" compact />
            </div>
          ))}
        </div>
      </ChartShell>
      <div className="rounded-3xl border border-zinc-200 bg-white p-5">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-400">D. Why top-20 candidates, top-5 context?</p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <SmallFinding label="BM25 pool recall@20" value={`${pool.bm25PoolRecallAt20}%`} />
          <SmallFinding label="Dense pool recall@20" value={`${pool.densePoolRecallAt20}%`} />
        </div>
        <p className="mt-4 text-xs leading-5 text-zinc-500">{pool.note}</p>
        <div className="mt-4"><Pipeline steps={["Candidate pool · top-20", "Reranker", "Model context · top-5"]} /></div>
      </div>
      <Pipeline steps={["NDA", "Clause-256", "BM25 top-20", "Cross-encoder", "Top-5", "GPT-5-mini"]} />
      <div className="grid gap-3 sm:grid-cols-3"><SmallFinding label="Misses analyzed" value={`${story.misses}`} /><SmallFinding label="Ranking failures" value={`${story.rankingFailures}`} note="Gold below final top-k" /><SmallFinding label="Candidate absence" value={`${story.candidateAbsence}`} note={`Median gold rank ${story.medianGoldRank}`} /></div>
      <DecisionBar text="BM25 + reranker retained by parsimony, not because it statistically beat the alternatives." source={charts.retrievalComparison.source} />
    </div>
  );
}

function ArchitectureLadder() {
  return (
    <div className="grid gap-4 lg:grid-cols-4">
      {p.architectureLadder.map((row) => (
        <div key={row.id} className={`rounded-3xl border bg-white p-5 ${row.status === "adopted" ? "border-amber-300 shadow-[0_18px_45px_-32px_rgba(217,119,6,0.5)]" : row.status === "reference" ? "border-sky-200" : "border-zinc-200"}`}>
          <div className="flex items-center justify-between"><span className="font-mono text-xs font-semibold text-zinc-400">{row.id}</span><StatusBadge status={row.status as Status}>{statusLabel(row.status)}</StatusBadge></div>
          <h3 className="mt-4 text-xl font-semibold text-zinc-950">{row.name}</h3>
          <dl className="mt-4 space-y-4 text-sm">
            <Definition label="Question" value={row.question} />
            <Definition label="Result" value={`${row.headline.value}${row.headline.unit}`} />
            <Definition label="Decision" value={shortDecision(row.name)} />
          </dl>
          <div className="mt-4"><Expandable summary={<span className="text-xs font-medium text-zinc-600">Technical detail</span>}><p className="text-xs leading-5">{row.conclusion}</p></Expandable></div>
        </div>
      ))}
    </div>
  );
}

function FullVsRag() {
  const c = charts.fullVsRagComparison;
  return (
    <div className="space-y-6">
      <ExperimentFrame why={p.causalStory.rag.why} learned={p.causalStory.rag.learned} next={p.causalStory.rag.next} />
      <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
      <ChartShell title="Quality on the same final TEST cases" subtitle={c.population}>
        <div className="space-y-5">
          {c.series.map((row) => (
            <div key={row.metric}>
              <p className="mb-2 text-xs font-medium text-zinc-700">{row.metric}</p>
              <MetricBar label="FULL" value={row.full} tone="sky" />
              <MetricBar label="RAG" value={row.rag} tone="amber" />
            </div>
          ))}
        </div>
      </ChartShell>
      <div className="space-y-3">
        <OperatingDelta label="Input tokens" from={c.operating.inputTokens.full.toLocaleString()} to={c.operating.inputTokens.rag.toLocaleString()} />
        <OperatingDelta label="Raw cost / case" from={`$${c.operating.rawCostPerCase.full.toFixed(5)}`} to={`$${c.operating.rawCostPerCase.rag.toFixed(5)}`} />
        <OperatingDelta label="Joint" from={`${c.operating.joint.full}%`} to={`${c.operating.joint.rag}%`} />
        <div className="grid grid-cols-2 gap-3">
          <SmallFinding label="Classification" value="No significant difference" note={`p = ${p.fullVsRag.classificationP}`} />
          <SmallFinding label="Joint" value="FULL advantage significant" note={`p = ${p.fullVsRag.jointP}`} />
        </div>
        <DecisionBar text="FULL = Quality reference · RAG = Prototype runtime" source={c.source} />
      </div></div>
    </div>
  );
}

const L1_L2_TOOLTIP = "L1 checks whether the output is structurally valid and source-grounded. L2 checks whether the model actually reached the correct semantic conclusion.";

function OverviewCase({ onSeeCase }: { onSeeCase: (request?: CaseExplorerRequest) => void }) {
  const item = p.cases.items.find((row) => `${row.docId}::${row.hypothesisId}` === p.cases.overviewCaseKey);
  if (!item) return null;
  const full = item.architectures.full_context;
  const rag = item.architectures.rag;
  const featured = p.cases.featured.find((row) => row.caseKey === p.cases.overviewCaseKey);
  const retrievedContext = "retrievedContext" in rag ? rag.retrievedContext : undefined;
  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-3xl border border-zinc-200 bg-white shadow-sm">
        <div className="grid gap-0 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="border-b border-zinc-200 p-6 lg:border-b-0 lg:border-r">
            <div className="flex flex-wrap items-center justify-between gap-2"><span className="rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-emerald-800">Real final-test case</span><span className="text-[10px] text-zinc-400">{item.caseId}</span></div>
            <p className="mt-5 text-[10px] font-bold uppercase tracking-wide text-zinc-400">Requirement</p>
            <h3 className="mt-2 text-lg font-semibold leading-7 text-zinc-950">{item.requirement}</h3>
            <p className="mt-5 text-[10px] font-bold uppercase tracking-wide text-zinc-400">Human gold label · gold evidence</p>
            <p className="mt-2"><VerdictPill label={item.goldLabel} /></p>
            <blockquote className="mt-2 max-h-40 overflow-y-auto rounded-2xl border border-amber-100 bg-amber-50/65 p-4 font-mono text-xs leading-5 text-zinc-700">{item.goldEvidence[0] ?? "No gold evidence span for NotMentioned."}</blockquote>
            <Pipeline steps={["Requirement", "Top-5 retrieval", "Relevant clause found", "GPT-5-mini", "Correct label + evidence", "L1 ✓", "L2 ✓"]} />
            {retrievedContext && (
              <Expandable summary={<span className="text-xs font-medium text-zinc-600">See retrieved context (real top-5)</span>}>
                <div className="mt-2 space-y-2">{retrievedContext.map((chunk) => <div key={chunk.chunkId} className="rounded-lg border border-zinc-200 bg-zinc-50 p-3"><p className="text-[10px] font-semibold text-zinc-500">Rank {chunk.rank} · chunk {chunk.chunkId} · reranker {chunk.rerankerScore.toFixed(3)}</p><p className="mt-1 max-h-28 overflow-y-auto font-mono text-[10px] leading-5 text-zinc-600">{chunk.text}</p></div>)}</div>
              </Expandable>
            )}
          </div>
          <div className="p-6">
            <div className="grid gap-4 sm:grid-cols-[1.15fr_0.85fr]">
              <MiniCaseSystem name="RAG" sub="Prototype runtime" result={rag} tone="amber" emphasis />
              <MiniCaseSystem name="FULL" sub="Quality reference" result={full} tone="sky" />
            </div>
            <p className="mt-3 text-[10px] leading-4 text-zinc-400" title={L1_L2_TOOLTIP}>L1 = valid output and source-grounded evidence · L2 = correct against human gold. {L1_L2_TOOLTIP}</p>
            <p className="mt-5 rounded-2xl bg-zinc-900 px-4 py-3 text-sm leading-6 text-zinc-200">{featured?.why ?? "The saved outputs make the architecture trade-off concrete."}</p>
            <button type="button" onClick={() => onSeeCase({ caseKey: `${item.docId}::${item.hypothesisId}` })} className="mt-4 text-sm font-semibold text-sky-700 hover:text-sky-900">Open complete saved trace →</button>
          </div>
        </div>
      </div>
      <OverviewFailurePointer onSeeCase={onSeeCase} />
    </div>
  );
}

function OverviewFailurePointer({ onSeeCase }: { onSeeCase: (request?: CaseExplorerRequest) => void }) {
  const key = p.cases.overviewFailureCaseKey;
  const item = p.cases.items.find((row) => `${row.docId}::${row.hypothesisId}` === key);
  if (!item) return null;
  const full = item.architectures.full_context;
  const rag = item.architectures.rag;
  return (
    <div className="rounded-2xl border border-rose-200 bg-rose-50/60 p-5">
      <p className="text-[10px] font-bold uppercase tracking-wide text-rose-700">When valid output is still wrong</p>
      <p className="mt-2 text-sm font-medium text-zinc-800">{item.requirement}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="text-xs text-zinc-500">FULL:</span><EvalBadge level="L1" pass={full.l1Pass} /><EvalBadge level="L2" pass={full.l2Pass} />
        <span className="ml-3 text-xs text-zinc-500">RAG:</span><EvalBadge level="L1" pass={rag.l1Pass} /><EvalBadge level="L2" pass={rag.l2Pass} />
        <span className="rounded-full bg-rose-100 px-2.5 py-1 text-[10px] font-bold uppercase text-rose-800">{item.failureType.replaceAll("_", "-")}</span>
      </div>
      <p className="mt-3 text-xs leading-5 text-zinc-600">The relevant gold span was absent from RAG&apos;s final top-5 context. L1 PASS does not imply L2 PASS.</p>
      <button type="button" onClick={() => onSeeCase({ caseKey: key ?? undefined })} className="mt-3 text-xs font-semibold text-sky-700 hover:text-sky-900">Open saved trace →</button>
    </div>
  );
}

function MiniCaseSystem({ name, sub, result, tone, emphasis }: { name: string; sub?: string; result: { predictedLabel: string | null; evidence: string[]; l1Pass: boolean; l2Pass: boolean }; tone: "sky" | "amber"; emphasis?: boolean }) {
  return <div className={`rounded-2xl border p-4 ${tone === "sky" ? "border-sky-200 bg-sky-50/60" : "border-amber-300 bg-amber-50/70"} ${emphasis ? "shadow-sm ring-1 ring-amber-300" : "opacity-90"}`}><div className="flex items-center justify-between"><div><h4 className="font-semibold text-zinc-900">{name}</h4>{sub && <p className="text-[9px] font-bold uppercase tracking-wide text-zinc-400">{sub}</p>}</div><VerdictPill label={result.predictedLabel} /></div>{emphasis ? <div className="mt-4 space-y-2"><EvalMeaning title="L1 Structure" pass={result.l1Pass} text="Valid output and source-grounded evidence" /><EvalMeaning title="L2 Semantics" pass={result.l2Pass} text="Correct against human gold" /></div> : <div className="mt-3 flex gap-2"><EvalBadge level="L1" pass={result.l1Pass} /><EvalBadge level="L2" pass={result.l2Pass} /></div>}<p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-zinc-400">Returned evidence</p><p className="mt-1 line-clamp-5 text-xs leading-5 text-zinc-600">{result.evidence[0] ?? "No evidence returned."}</p></div>;
}

function EvalMeaning({ title, pass, text }: { title: string; pass: boolean; text: string }) { return <div className={`rounded-xl px-3 py-2 ${pass ? "bg-emerald-50 text-emerald-900" : "bg-rose-50 text-rose-900"}`}><p className="text-[10px] font-bold uppercase tracking-wide">{title} {pass ? "✓" : "×"}</p><p className="mt-0.5 text-[10px] leading-4 opacity-75">{text}</p></div>; }

function FailureAnalysis({ onSeeCases }: { onSeeCases: (request?: CaseExplorerRequest) => void }) {
  const c = charts.failureBreakdown;
  return (
    <div className="grid gap-6 lg:grid-cols-[1.35fr_0.65fr]">
      <ChartShell title="Residual failures by primary cause" subtitle={`Final TEST · ${c.total} non-Joint cases`}>
        <div className="space-y-5">
          {c.series.map((row, index) => <button key={row.label} type="button" className="block w-full rounded-xl p-1 text-left hover:bg-zinc-50" onClick={() => onSeeCases({ failureType: failureSlug(row.label), architecture: "rag", failuresOnly: true })}><CountBar label={row.label} count={row.count} total={c.total} emphasis={index === 0} /></button>)}
        </div>
      </ChartShell>
      <div className="space-y-4">
        <div className="rounded-3xl bg-zinc-900 p-6 text-white">
          <div className="text-4xl font-semibold tabular-nums">{c.reasoningShare}%</div>
          <p className="mt-2 text-sm leading-6 text-zinc-300">of residual failures would remain even with a hypothetical perfect retriever.</p>
        </div>
        <Consequence label="Technical consequence" text="More retrieval complexity attacks a minority of the remaining problem." />
        <Consequence label="Product consequence" text="Target semantic reasoning and reviewer safety rather than simply retrieving more text." />
        <button type="button" onClick={() => onSeeCases({ architecture: "rag", failuresOnly: true })} className="text-sm font-medium text-sky-700 hover:text-sky-900">Explore real cases →</button>
      </div>
    </div>
  );
}

function TransitionCases({ onSeeCase }: { onSeeCase: (request?: CaseExplorerRequest) => void }) {
  const promptCase = p.causalStory.prompt.case;
  const retrievalFeature = p.cases.featured.find((row) => row.kind === "Retrieval miss");
  const reasoningFeature = p.cases.featured.find((row) => row.kind === "Reasoning failure");
  const agentCase = p.cases.agentDemoCases[0];
  const lookup = (key?: string) => p.cases.items.find((row) => `${row.docId}::${row.hypothesisId}` === key);
  const retrievalCase = lookup(retrievalFeature?.caseKey);
  const reasoningCase = lookup(reasoningFeature?.caseKey);
  return <div className="grid gap-4 md:grid-cols-2">
    <TransitionCase title="Model decision failure · evidence present, label missed" badge="E03" requirement={promptCase.requirement} evidence={promptCase.evidence} outcome={`${promptCase.prediction} → gold ${promptCase.goldLabel}`} l1={null} l2={false} failureType="Not retrieval-limited" why="Relevant evidence was available, so this case motivated investigation of model and decision limitations rather than assuming retrieval was the dominant bottleneck." />
    {retrievalCase && <TransitionCase title="Retrieval failure · gold fell outside top-5" badge="E20" requirement={retrievalCase.requirement} evidence={retrievalCase.goldEvidence[0] ?? "No gold span"} outcome={`RAG ${retrievalCase.architectures.rag.predictedLabel} → gold ${retrievalCase.goldLabel}`} l1={retrievalCase.architectures.rag.l1Pass} l2={retrievalCase.architectures.rag.l2Pass} failureType="Retrieval-limited" why={retrievalFeature?.why ?? "The saved top-5 omitted the relevant gold span."} onOpen={() => onSeeCase({ caseKey: retrievalFeature?.caseKey })} />}
    {reasoningCase && <TransitionCase title="Reasoning failure · right evidence, wrong label" badge="E20" requirement={reasoningCase.requirement} evidence={reasoningCase.architectures.rag.evidence[0] ?? reasoningCase.goldEvidence[0] ?? "No evidence"} outcome={`RAG ${reasoningCase.architectures.rag.predictedLabel} → gold ${reasoningCase.goldLabel}`} l1={reasoningCase.architectures.rag.l1Pass} l2={reasoningCase.architectures.rag.l2Pass} failureType="Reasoning / classification" why={reasoningFeature?.why ?? "The relevant evidence reached the model, but the semantic label was wrong."} onOpen={() => onSeeCase({ caseKey: reasoningFeature?.caseKey })} />}
    {agentCase && <TransitionCase title="Agent failure · tool called, no recovery" badge="E11 V2" requirement={agentCase.requirement} evidence={agentCase.agent.steps[0]?.result?.results?.[0]?.text ?? "Additional candidates were returned."} outcome={`${agentCase.agent.steps[0]?.action ?? "Tool"} → final ${agentCase.agent.prediction} · gold ${agentCase.goldLabel}`} l1={agentCase.agent.l1Pass} l2={agentCase.agent.l2Pass} failureType="Dynamic retrieval did not recover outcome" why={agentCase.why} />}
  </div>;
}

function TransitionCase({ title, badge, requirement, evidence, outcome, l1, l2, failureType, why, onOpen }: { title: string; badge: string; requirement: string; evidence: string; outcome: string; l1: boolean | null; l2: boolean; failureType: string; why: string; onOpen?: () => void }) {
  return <Expandable summary={<div className="flex w-full items-center justify-between gap-3"><span className="text-sm font-semibold text-zinc-900">{title}</span><span className="rounded-full bg-zinc-100 px-2 py-1 font-mono text-[9px] font-bold text-zinc-500">{badge}</span></div>}><div className="space-y-3 pt-3"><p className="text-sm font-medium leading-6 text-zinc-800">{requirement}</p><blockquote className="max-h-28 overflow-y-auto rounded-xl border border-amber-100 bg-amber-50/60 p-3 font-mono text-[11px] leading-5 text-zinc-700">{evidence}</blockquote><p className="text-xs font-semibold text-rose-700">{outcome}</p><div className="flex flex-wrap gap-2">{l1 === null ? <span className="rounded-full bg-zinc-100 px-2.5 py-1 text-[10px] font-bold text-zinc-600">L1 not scored in E03</span> : <EvalBadge level="L1" pass={l1} />}<EvalBadge level="L2" pass={l2} /><span className="rounded-full bg-rose-100 px-2.5 py-1 text-[10px] font-bold text-rose-800">{failureType}</span></div><p className="text-xs leading-5 text-zinc-500">{why}</p>{onOpen && <button type="button" onClick={onOpen} className="text-xs font-semibold text-sky-700">Open full saved trace →</button>}</div></Expandable>;
}

function StaticExpansion() {
  const story = p.causalStory.staticExpansion;
  return <div className="space-y-6">
    <ExperimentFrame why={story.why} learned={story.learned} next={story.next} />
    <div className="overflow-hidden rounded-3xl border border-zinc-200 bg-white shadow-sm">
      <div className="grid grid-cols-[1.2fr_repeat(5,1fr)] gap-2 border-b border-zinc-200 bg-zinc-50 px-4 py-3 text-[10px] font-bold uppercase tracking-wide text-zinc-500"><span>Context</span><span>Accuracy</span><span>Macro-F1</span><span>Joint</span><span>C recall</span><span>Mean input</span></div>
      {story.rows.map((row) => <div key={row.name} className={`grid grid-cols-[1.2fr_repeat(5,1fr)] gap-2 border-b border-zinc-100 px-4 py-4 text-sm last:border-0 ${row.name === "top-5" ? "bg-amber-50/35" : ""}`}><strong>{row.name}</strong><span>{row.accuracy}%</span><span>{row.macroF1.toFixed(3)}</span><span>{row.joint}%</span><span>{row.contradictionRecall}%</span><span>{row.inputTokens.toLocaleString()}</span></div>)}
    </div>
    <div className="grid gap-3 sm:grid-cols-3"><SmallFinding label="Top-11 input increase" value={`+${story.inputIncrease}%`} /><SmallFinding label="Top-11 cost increase" value={`+${story.costIncrease}%`} /><SmallFinding label="Contradiction recall" value="76% → 76%" /></div>
    <DecisionBar text="Keep top-5: top-11's sample gain did not justify the context and cost increase." source={story.source} />
  </div>;
}

function AgentJustification() {
  const story = p.causalStory.agent;
  return (
    <div className="space-y-6">
      <ExperimentFrame why={story.why} learned={`Of ${story.residual.n} residual failures, ${story.residual.reasoning} were reasoning-limited, ${story.residual.retrievalFiltering} were static filtering opportunities, and only ${story.residual.dynamic} was genuinely dynamic.`} next="Test a tightly bounded agent empirically, with a skeptical prior." />
      <div className="grid gap-5 lg:grid-cols-[1fr_0.8fr]">
        <ChartShell title="Why try an agent at all?" subtitle={p.agentJustification.e09.population}>
          <div className="space-y-4"><CountBar label="Model reasoning" count={story.residual.reasoning} total={story.residual.n} emphasis /><CountBar label="Static retrieval filtering" count={story.residual.retrievalFiltering} total={story.residual.n} emphasis={false} /><CountBar label="Dynamic information need" count={story.residual.dynamic} total={story.residual.n} emphasis={false} /></div>
        </ChartShell>
        <div className="flex flex-col justify-between gap-4"><div className="grid grid-cols-2 gap-3"><SmallFinding label="Static-fix ceiling" value={`+${story.ceilings.static}pp`} /><SmallFinding label="Agentic ceiling" value={`+${story.ceilings.agent}pp`} /></div><DecisionBar text="The agent was tested as a narrow falsifiable hypothesis—not assumed to be an upgrade." source={story.source} /></div>
      </div>
    </div>
  );
}

function AgentTools() {
  const t = p.agentTools;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2">
        {t.tools.map((tool) => (
          <div key={tool.name} className="rounded-3xl border border-sky-200 bg-sky-50/50 p-5">
            <p className="font-mono text-sm font-bold tracking-wide text-sky-800">{tool.name}</p>
            <p className="mt-2 text-sm font-medium leading-6 text-zinc-900">{tool.purpose}</p>
            <p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-zinc-400">Why it existed</p>
            <p className="mt-1 text-sm leading-6 text-zinc-700">{tool.why}</p>
            <p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-zinc-400">What it does</p>
            <p className="mt-1 text-sm leading-6 text-zinc-700">{tool.what}</p>
            <p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-zinc-400">Constraints</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {tool.constraints.map((c) => <span key={c} className="rounded-full bg-white px-2.5 py-1 text-[10px] font-medium text-sky-800 ring-1 ring-inset ring-sky-200">{c}</span>)}
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-zinc-200 bg-white p-5">
        <p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Why only two tools?</p>
        <p className="mt-2 text-sm leading-6 text-zinc-700">{t.whyOnlyTwo}</p>
        <p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-zinc-400">Not included</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {t.excluded.map((item) => <span key={item} className="rounded-full bg-rose-50 px-3 py-1 text-[11px] font-medium text-rose-700">× {item}</span>)}
        </div>
      </div>
      <div className="rounded-2xl border border-zinc-200 bg-white p-5">
        <p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Agent hypothesis flow</p>
        <div className="mt-3"><Pipeline steps={t.flow} /></div>
      </div>
      <div className="rounded-2xl bg-zinc-900 p-5">
        <p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Hard controls</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {t.hardControls.map((item) => <span key={item} className="rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-medium text-zinc-100">{item}</span>)}
        </div>
      </div>
      <ProvenanceChip source={t.source} />
    </div>
  );
}

function AgentExperiments() {
  const story = p.causalStory.agent;
  return (
    <div className="space-y-7">
      <div className="rounded-3xl border border-zinc-200 bg-white p-6 shadow-sm">
        <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-sky-700">Question</p>
        <h3 className="mt-2 text-2xl font-semibold tracking-tight text-zinc-950">Did dynamic investigation earn its added complexity?</h3>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-zinc-600">Only a minority of residual failures were retrieval-fixable, so agent investigation had a narrow plausible target. The comparison below uses the same 150-case TRAIN_ARCH_v1 agent-evaluation population for every arm—never the final 2,091-case TEST result.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <AgentStage number="1" title="Selective V1" headline={`${story.v1.selectiveRouted} / 150 routed`} detail={`${story.v1.selectiveToolCalls} tool calls`} caption={story.v1.stage1Caption} />
        <AgentStage number="2" title="Full-agent V1" headline={`${story.v1.fullToolCases} / ${story.v1.fullN} used tools`} detail="1.3% tool use" caption={story.v1.stage2Caption} />
        <AgentStage number="3" title="Controller V2" headline={`${story.v2.toolCases} / ${story.v2.n} used tools`} detail="20% tool use · 0 useful recoveries" caption={story.v2.stage3Caption} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2"><Callout eyebrow="What V1 could mean" text={story.v1.hypotheses.join(" — or — ")} /><Callout eyebrow="What changed in V2" text={story.v2.change} /></div>
      <Callout eyebrow="Why V2?" text={story.v2.whyV2} />
      <div className="overflow-x-auto rounded-3xl border border-zinc-200 bg-white shadow-sm">
        <table className="w-full min-w-[860px] text-left text-sm">
          <thead className="border-b border-zinc-200 bg-zinc-50 text-[10px] uppercase tracking-wide text-zinc-500"><tr><th className="px-5 py-3">Configuration</th><th className="px-3 py-3">Accuracy</th><th className="px-3 py-3">Joint</th><th className="px-3 py-3">Contradiction recall</th><th className="px-3 py-3">Tool use</th><th className="px-3 py-3">Useful recovery</th><th className="px-3 py-3">Incremental cost</th><th className="px-5 py-3">Incremental latency</th></tr></thead>
          <tbody>{story.comparison.map((row) => <tr key={row.name} className={`border-b border-zinc-100 last:border-0 ${row.name === "Base RAG" ? "bg-sky-50/40" : ""}`}><td className="px-5 py-4"><strong className="text-zinc-900">{row.name}</strong><span className="mt-0.5 block text-[10px] text-zinc-400">{row.role} · matched n=150</span></td><td className="px-3 py-4">{row.accuracy}%</td><td className="px-3 py-4 font-semibold">{row.joint}%</td><td className="px-3 py-4">{row.contradictionRecall}%</td><td className="px-3 py-4">{row.toolUse === null ? "—" : `${row.toolUse}%`}</td><td className="px-3 py-4">{row.usefulRecoveries ?? "—"}</td><td className="px-3 py-4">{row.incrementalCost === null ? "—" : `+$${row.incrementalCost.toFixed(6)}/case`}</td><td className="px-5 py-4">{row.incrementalLatency === null ? "—" : `+${row.incrementalLatency.toFixed(2)}s`}</td></tr>)}</tbody>
        </table>
        <p className="border-t border-zinc-100 px-5 py-3 text-xs leading-5 text-zinc-500">{story.evaluationNote}</p>
      </div>
      <details className="rounded-2xl border border-zinc-200 bg-white px-5 py-4">
        <summary className="cursor-pointer text-xs font-semibold text-zinc-700">Saved operational totals</summary>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {story.comparison.filter((row) => row.modelCalls !== null).map((row) => <div key={row.name} className="rounded-2xl bg-zinc-50 p-4"><p className="text-xs font-semibold text-zinc-900">{row.name}</p><p className="mt-2 text-xs leading-5 text-zinc-500">{row.modelCalls} model calls · {row.inputTokens?.toLocaleString()} input tokens · {row.outputTokens?.toLocaleString()} output tokens · {((row.inputTokens ?? 0) + (row.outputTokens ?? 0)).toLocaleString()} total tokens</p></div>)}
        </div>
        <p className="mt-3 text-[11px] text-zinc-400">Base-RAG operational totals are unavailable in these incremental-agent ledgers, so they are not inferred.</p>
      </details>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-3xl border border-zinc-200 bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Tool use → useful recovery</p><div className="mt-4 grid grid-cols-2 gap-3"><SmallFinding label="Agent V1" value="1.3% → 0/2" /><SmallFinding label="Agent V2" value="20% → 0/30" /></div></div>
        <div className="rounded-3xl border border-amber-200 bg-amber-50/60 p-5"><p className="text-[10px] font-bold uppercase tracking-wide text-amber-700">Cost of autonomy</p><div className="mt-4 grid grid-cols-2 gap-3"><SmallFinding label="Agent V1" value="+$0.001515 · +5.87s" /><SmallFinding label="Agent V2" value="+$0.002659 · +10.36s" /></div></div>
      </div>
      <div className="grid gap-6 lg:grid-cols-[1fr_0.8fr]">
        <ChartShell title="Joint success after adding agent behavior" subtitle={charts.agentComparison.population}>
          <div className="space-y-4">{story.quality.map((row) => <MetricBar key={row.name} label={row.name} value={row.joint} tone={row.name === "Base RAG" ? "sky" : "rose"} />)}</div>
        </ChartShell>
        <div className="rounded-3xl border border-rose-200 bg-rose-50 p-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-rose-700">Big takeaway</p>
          <p className="mt-3 text-3xl font-semibold text-zinc-950">Tool use increased.</p>
          <p className="mt-1 text-3xl font-semibold text-zinc-950">Value did not.</p>
          <p className="mt-4 text-sm leading-6 text-zinc-600">{story.takeaway.body}</p>
          <p className="mt-2 text-sm leading-6 text-zinc-600">{story.takeaway.conclusion}</p>
          <div className="mt-5 inline-flex rounded-full bg-rose-700 px-4 py-2 text-xs font-bold uppercase tracking-wide text-white">Reject tested agent</div>
          <p className="mt-3 text-xs leading-5 text-zinc-500">This conclusion applies to the tested two-tool retrieval-agent design on this matched 150-case evaluation, not to agents in general.</p>
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-4"><SmallFinding label="V2 tool calls" value={`${story.v2.getMore} GET_MORE · ${story.v2.follow} FOLLOW`} /><SmallFinding label="Outcome proxy" value={`${story.v2.useful} useful · ${story.v2.neutral} neutral · ${story.v2.harmful} harmful`} /><SmallFinding label="Fallbacks" value={`${story.v2.fallbacks}`} /><SmallFinding label="Stops" value={`${story.v2.duplicateStops} duplicate · ${story.v2.invalidStops} invalid · ${story.v2.maxToolStops} max-tool`} /></div>
      <p className="text-xs text-zinc-500">{story.v2.toolCallNote}</p>
      <DecisionBar text={`${story.learned} ${story.next}`} source={story.source} />
    </div>
  );
}

function RoutingReview() {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_0.72fr]">
      <ChartShell title="Review policy trade-off" subtitle={charts.routingComparison.population}>
        <div className="grid gap-3 sm:grid-cols-3">
          {charts.routingComparison.series.map((row) => (
            <div key={row.name} className={`rounded-2xl border p-4 ${row.name.startsWith("R3") ? "border-amber-300 bg-amber-50" : "border-zinc-200 bg-zinc-50"}`}>
              <p className="text-xs font-semibold text-zinc-800">{row.name}</p>
              <RoutingStat label="Review" value={row.reviewRate} />
              <RoutingStat label="Capture" value={row.failureCapture} />
              <RoutingStat label="Residual" value={row.residualError} />
            </div>
          ))}
        </div>
      </ChartShell>
      <div className="space-y-4"><Callout eyebrow="Target" text="≤40% review · <10% residual Joint error" /><Callout eyebrow="Result" text="The target was not jointly met." /><DecisionBar text="No automatic confidence router." source={charts.routingComparison.source} /></div>
    </div>
  );
}

function SecuritySection() {
  const s = charts.securitySummary;
  const story = p.securityStory;
  return (
    <div className="space-y-8">
      <p className="-mt-2 max-w-3xl text-sm leading-6 text-zinc-600">Security evaluation was treated as an engineering experiment, not a compliance checkbox.</p>
      <div className="rounded-3xl border border-sky-200 bg-gradient-to-br from-white to-sky-50/70 p-5 shadow-sm">
        <Pipeline steps={story.process} />
        <p className="mt-4 text-center text-sm leading-6 text-zinc-600">{story.processNote}</p>
      </div>

      <ChartShell title="E21 security baseline" subtitle={`${story.baselineLabel} · Ten categories assessed; status is not a compliance score`}>
          <div className="mb-5 grid grid-cols-3 gap-3">
            <SecurityCount label="Pass" count={s.baseline.counts.PASS} tone="emerald" />
            <SecurityCount label="Partial" count={s.baseline.counts.PARTIAL} tone="amber" />
            <SecurityCount label="Fail" count={s.baseline.counts.FAIL} tone="rose" />
          </div>
          <div className="grid gap-2 sm:grid-cols-2">
            {s.baseline.categories.map((row) => <SecurityRow key={row.owasp_id} id={row.owasp_id} name={row.category} status={row.result} />)}
          </div>
          <p className="mt-5 text-xs leading-5 text-zinc-500">E21 remains immutable. E22 did not rerun all ten categories: only LLM01 and LLM10 were targeted for verification, with limited LLM03 dependency remediation. All other assessments retain their E21 status.</p>
      </ChartShell>

      <div>
        <div className="mb-4"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-emerald-700">Targeted remediation · E22</p><h3 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-950">What changed after the security review?</h3></div>
        <div className="grid gap-5 lg:grid-cols-2">{story.remediations.map((item) => <SecurityRemediation key={item.id} item={item} />)}</div>
        <div className="mt-4 overflow-hidden rounded-2xl border border-zinc-200 bg-white">
          <div className="grid grid-cols-[1.2fr_0.7fr_0.15fr_0.7fr] gap-3 border-b border-zinc-100 bg-zinc-50 px-4 py-2 text-[10px] font-bold uppercase tracking-wide text-zinc-400"><span>Finding</span><span>E21</span><span /><span>E22</span></div>
          {story.remediations.map((item) => <div key={item.id} className="grid grid-cols-[1.2fr_0.7fr_0.15fr_0.7fr] items-center gap-3 border-b border-zinc-100 px-4 py-3 text-xs last:border-0"><span className="font-medium text-zinc-800">{item.name}</span><SecurityStatus value={item.before} /><span className="text-zinc-300">→</span><SecurityStatus value={item.after} /></div>)}
        </div>
      </div>

      <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm">
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-sky-700">Security architecture</p>
        <h3 className="mt-1 text-lg font-semibold text-zinc-950">Controls surround the model</h3>
        <div className="mt-4"><Pipeline steps={story.architecture} /></div>
        <div className="mt-5 grid gap-3 md:grid-cols-3">{story.controlZones.map((zone) => <div key={zone.label} className="rounded-2xl bg-zinc-50 p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-500">{zone.label}</p><ul className="mt-2 space-y-1 text-xs text-zinc-600">{zone.items.map((item) => <li key={item}>✓ {item}</li>)}</ul></div>)}</div>
      </div>

      <div>
        <div className="mb-3"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-amber-700">Saved E21 adversarial fixtures</p><h3 className="mt-1 text-2xl font-semibold tracking-tight text-zinc-950">Why source validation alone is not enough</h3><p className="mt-2 text-sm leading-6 text-zinc-600">These adversarial fixtures demonstrate why provenance checks and content-safety controls must be separate.</p></div>
        <div className="grid gap-4 lg:grid-cols-2">
          {s.examples.map((example) => <SecurityExample key={example.testId} example={example} />)}
        </div>
        <p className="mt-4 rounded-2xl border border-amber-200 bg-amber-50/70 px-4 py-3 text-sm leading-6 text-zinc-700">This finding motivated E22&apos;s injection guard and mandatory human-review flag.</p>
      </div>

      <div>
        <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-400">What the security work proved</p>
        <div className="mt-3 grid gap-4 md:grid-cols-3">{story.proved.map((group, index) => <div key={group.label} className={`rounded-3xl border p-5 ${index === 0 ? "border-emerald-200 bg-emerald-50/60" : index === 1 ? "border-sky-200 bg-sky-50/60" : "border-amber-200 bg-amber-50/60"}`}><h3 className="text-sm font-bold uppercase tracking-wide text-zinc-800">{group.label}</h3><ul className="mt-3 space-y-2 text-xs leading-5 text-zinc-600">{group.items.map((item) => <li key={item}>✓ {item}</li>)}</ul></div>)}</div>
      </div>

      <div className="rounded-3xl border border-zinc-200 bg-zinc-950 p-6 text-white">
        <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-emerald-400">Security decision</p><ProvenanceChip source={story.source} /></div>
        <p className="mt-3 max-w-4xl text-sm leading-6 text-zinc-200">{story.decision}</p>
        <p className="mt-4 rounded-2xl bg-white/10 px-4 py-3 text-sm font-medium leading-6 text-white"><span className="text-emerald-300">Current security posture · </span>{story.posture}</p>
        <div className="mt-5 grid gap-5 sm:grid-cols-2"><SecurityDecisionList title="What ships" items={story.ships} positive /><SecurityDecisionList title="What does not ship" items={story.doesNotShip} /></div>
      </div>
    </div>
  );
}

function FinalTest({ onSeeCases }: { onSeeCases: (request?: CaseExplorerRequest) => void }) {
  const roles: Record<string, string> = { Rule: "Baseline", Qwen: "Local comparator", FULL: "Quality reference", RAG: "Prototype runtime" };
  return (
    <div className="overflow-hidden rounded-3xl border border-zinc-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-zinc-200 bg-zinc-50/70 px-5 py-4"><div><h3 className="text-sm font-semibold text-zinc-900">System comparison</h3><p className="text-xs text-zinc-500">Final TEST · n = 2,091</p></div><ProvenanceChip source={charts.finalTestComparison.source} /></div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-zinc-200 text-[11px] uppercase tracking-wide text-zinc-500"><tr><th className="px-5 py-3 font-medium">System</th><th className="px-4 py-3 font-medium">Role</th><th className="px-4 py-3 text-right font-medium">Accuracy</th><th className="px-4 py-3 text-right font-medium">Joint</th><th className="px-4 py-3 text-right font-medium">Contradiction recall</th><th className="px-5 py-3 text-right font-medium">Cases</th></tr></thead>
          <tbody>
            {charts.finalTestComparison.series.map((row) => (
              <tr key={row.name} className={`border-b border-zinc-100 last:border-0 ${row.name === "RAG" ? "bg-amber-50/65" : row.name === "FULL" ? "bg-sky-50/55" : ""}`}>
                <td className="px-5 py-4 font-semibold text-zinc-900">{row.name}</td><td className="px-4 py-4 text-zinc-500">{roles[row.name]}</td><td className="px-4 py-4 text-right tabular-nums text-zinc-700">{pct(row.accuracy)}</td><td className="px-4 py-4 text-right font-semibold tabular-nums text-zinc-900">{pct(row.joint)}</td><td className="px-4 py-4 text-right tabular-nums text-zinc-700">{pct(row.contradictionRecall)}</td><td className="px-5 py-4 text-right">{row.name !== "Qwen" ? <button type="button" onClick={() => onSeeCases({ architecture: row.name === "Rule" ? "rule" : row.name === "FULL" ? "full_context" : "rag", failuresOnly: true })} className="whitespace-nowrap text-xs font-semibold text-sky-700 hover:text-sky-900">View failures</button> : <span className="text-xs text-zinc-400">—</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FinalFailureAnalysis() {
  const priorities = [
    ["1", "Semantic reasoning", "Largest residual error source"],
    ["2", "NotMentioned discipline", "Important weak class"],
    ["3", "Security hardening", "Prompt injection and resource controls"],
  ];
  return <div><div className="grid gap-4 md:grid-cols-3">{priorities.map(([n, title, body]) => <div key={n} className="border-l-2 border-amber-300 pl-5 py-2"><span className="text-xs font-semibold text-amber-700">{n.padStart(2, "0")}</span><h3 className="mt-2 text-lg font-semibold text-zinc-900">{title}</h3><p className="mt-1 text-sm text-zinc-500">{body}</p></div>)}</div><p className="mt-6 text-xs text-zinc-500">Long-document performance remains unvalidated.</p></div>;
}

const COST_LINE_COLOR: Record<string, string> = { Manual: "#a1a1aa", Rule: "#71717a", FULL: "#0ea5e9", RAG: "#f59e0b" };

function CostToServeCurve() {
  const c = charts.costAtScaleCurve;
  const width = 760;
  const height = 330;
  const padL = 70;
  const padB = 45;
  const padT = 24;
  const padR = 112;
  const innerW = width - padL - padR;
  const innerH = height - padT - padB;
  const maxY = Math.max(...c.series.flatMap((s) => s.costPerVolume));
  const x = (i: number) => padL + (i / (c.volumes.length - 1)) * innerW;
  const y = (v: number) => padT + innerH - (v / maxY) * innerH;
  const midIndex = c.volumes.indexOf(500);
  const reference = c.series.map((s) => ({ ...s, at500: s.costPerVolume[midIndex] }));
  const linePath = (values: number[]) => values.map((v, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(v)}`).join(" ");
  return (
    <div className="overflow-hidden rounded-3xl border border-zinc-200 bg-white shadow-[0_18px_50px_-36px_rgba(24,24,27,0.45)]">
      <div className="border-b border-zinc-100 px-5 py-5 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-semibold tracking-tight text-zinc-950">At enterprise review volumes, human fallback drives the economics</h3><p className="mt-1 max-w-3xl text-xs leading-5 text-zinc-500">{c.population}</p></div><span className="rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-amber-800">Modeled · not realized savings</span></div>
        <p className="mt-3 text-xs text-zinc-500">17 requirements per NDA · 5 minutes human review per failed requirement · $40/hour</p>
      </div>
      <div className="grid gap-0 xl:grid-cols-[minmax(0,1fr)_250px]">
        <div className="min-w-0 p-4 sm:p-6">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Expected annual review cost by NDA volume and review system">
            <rect x={x(midIndex) - 18} y={padT} width={36} height={innerH} rx={10} fill="#fafafa" />
            {[0, 0.25, 0.5, 0.75, 1].map((t) => { const value=maxY*(1-t); return <g key={t}><line x1={padL} x2={width-padR} y1={padT+innerH*t} y2={padT+innerH*t} stroke="#e4e4e7" strokeWidth={1} /><text x={padL-12} y={padT+innerH*t+4} textAnchor="end" fill="#a1a1aa" style={{fontSize:10}}>{value===0?"$0":`$${formatThousands(value)}`}</text></g>; })}
            <line x1={x(midIndex)} x2={x(midIndex)} y1={padT} y2={padT+innerH} stroke="#d4d4d8" strokeDasharray="4 5" />
            <text x={x(midIndex)} y={padT-8} textAnchor="middle" fill="#71717a" style={{fontSize:9,fontWeight:700}}>REFERENCE · 500</text>
            {c.volumes.map((v,i)=><g key={v}><line x1={x(i)} x2={x(i)} y1={padT+innerH} y2={padT+innerH+5} stroke="#d4d4d8" /><text x={x(i)} y={height-12} textAnchor="middle" fill="#a1a1aa" style={{fontSize:10}}>{v.toLocaleString()}</text></g>)}
            {c.series.map((s)=><path key={s.name} d={linePath(s.costPerVolume)} fill="none" stroke={COST_LINE_COLOR[s.name]??"#a1a1aa"} strokeWidth={s.name==="FULL"||s.name==="RAG"?3:2.4} strokeLinecap="round" strokeLinejoin="round" opacity={s.name==="Manual"?0.75:1} />)}
            {c.series.map((s)=><g key={`${s.name}-points`}>{s.costPerVolume.map((v,i)=><circle key={i} cx={x(i)} cy={y(v)} r={i===midIndex?5:2.5} fill="white" stroke={COST_LINE_COLOR[s.name]??"#a1a1aa"} strokeWidth={i===midIndex?3:2} />)}<text x={width-padR+12} y={y(s.costPerVolume.at(-1)??0)+4} fill={COST_LINE_COLOR[s.name]??"#71717a"} style={{fontSize:10,fontWeight:700}}>{s.name} · ${formatThousands(s.costPerVolume.at(-1)??0)}</text></g>)}
            <text x={padL+innerW/2} y={height-1} textAnchor="middle" fill="#a1a1aa" style={{fontSize:9,fontWeight:600}}>ANNUAL NDA VOLUME</text>
          </svg>
        </div>
        <aside className="border-t border-zinc-100 bg-zinc-50/60 p-5 xl:border-l xl:border-t-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-400">At 500 NDAs / year</p>
          <div className="mt-4 space-y-2.5">{reference.map((row)=><div key={row.name} className={`rounded-xl border px-3 py-2.5 ${row.name==="FULL"?"border-sky-200 bg-sky-50":row.name==="RAG"?"border-amber-200 bg-amber-50":"border-zinc-200 bg-white"}`}><div className="flex items-center justify-between gap-3"><span className="inline-flex items-center gap-2 text-xs font-medium text-zinc-700"><span className="h-2 w-2 rounded-full" style={{background:COST_LINE_COLOR[row.name]??"#a1a1aa"}} />{row.name}</span><strong className="text-sm tabular-nums text-zinc-950">${formatThousands(row.at500)}</strong></div></div>)}</div>
          <div className="mt-5 rounded-2xl bg-zinc-900 p-4 text-white"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">What matters</p><p className="mt-2 text-xs leading-5 text-zinc-200">Inference is a small part of total cost. Joint failures—and the human review they trigger—drive the modeled difference.</p></div>
          <p className="mt-4 text-[10px] leading-4 text-zinc-400">Expected review economics under project assumptions, not guaranteed ROI or realized customer savings.</p>
        </aside>
      </div>
    </div>
  );
}

function CostFormula() {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-5">
      <p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Cost-to-serve formula</p>
      <div className="mt-3 rounded-2xl bg-zinc-900 p-4 font-mono text-sm leading-7 text-zinc-100">
        C_total = C_AI + (1 − p_joint) × C_human
      </div>
      <p className="mt-3 text-xs leading-5 text-zinc-500">Annual cost = volume × requirements × cost-to-serve, plus fixed cost if any.</p>
      <p className="mt-2 text-xs leading-5 text-zinc-500">Fixed infrastructure cost: not separately modeled / $0 in the current scenario.</p>
      <div className="mt-4 rounded-2xl bg-zinc-50 p-4">
        <p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">RAG vs. Agent AI cost</p>
        <p className="mt-2 text-xs leading-6 text-zinc-600">RAG AI cost = base inference cost. Agent AI cost = base RAG cost + routing / additional agent-call cost. Both are compared the same way — total cost = AI cost + expected human fallback, not API spend alone.</p>
        <p className="mt-2 text-[11px] font-semibold text-amber-800">TRAIN agent diagnostic (E11, n=150) — not the E18 final annual business estimate; populations differ and are not merged.</p>
      </div>
    </div>
  );
}

function BusinessEvaluation() {
  const max = Math.max(...charts.businessCostComparison.series.map((row) => row.costPerRequirement));
  return (
    <div className="space-y-6">
    <CostToServeCurve />
    <CostFormula />
    <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
      <ChartShell title="Modeled cost per requirement" subtitle={charts.businessCostComparison.population}>
        <div className="mb-4 inline-flex rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-[10px] font-bold uppercase tracking-wide text-amber-800">Modeled · not realized savings</div>
        <div className="space-y-5">{charts.businessCostComparison.series.map((row) => <CostBar key={row.name} label={row.name} value={row.costPerRequirement} max={max} />)}</div>
      </ChartShell>
      <div className="rounded-3xl border border-zinc-200 bg-white p-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Annual modeled scenario</p>
        <p className="mt-1 text-sm text-zinc-600">500 NDAs/year · 17 requirements each</p>
        <div className="mt-5 space-y-3">{charts.businessCostComparison.series.map((row) => <div key={row.name} className="flex items-center justify-between border-b border-zinc-100 pb-3 text-sm last:border-0"><span className="text-zinc-600">{row.name}</span><span className="font-semibold tabular-nums text-zinc-900">≈ ${formatThousands(row.annualCost)}</span></div>)}</div>
        <p className="mt-5 rounded-2xl bg-zinc-900 p-4 text-sm leading-6 text-zinc-200">Higher model quality can reduce human fallback enough to outweigh a slightly higher API bill.</p>
      </div>
    </div>
    </div>
  );
}

function ShipDecision() {
  return <div className="grid gap-5 md:grid-cols-2"><Checklist title="Ship in prototype" items={p.shipDecision.ship} tone="emerald" icon="✓" /><Checklist title="Do not ship yet" items={p.shipDecision.doNotShip} tone="rose" icon="×" /></div>;
}

function FinalSystem() {
  return (
    <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm sm:p-7">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-9 lg:items-stretch">
        {p.flow.map((step, index) => (
          <div key={step.step} className="contents">
            <div className={`flex min-h-24 flex-col justify-between rounded-2xl border p-3 ${flowTone(step.kind)}`}><span className="text-[9px] font-bold uppercase tracking-wide opacity-60">{flowLabel(step.kind)}</span><span className="mt-3 text-xs font-semibold leading-5">{flowShort(step.step)}</span></div>
            {index < p.flow.length - 1 && <div className="hidden items-center justify-center text-zinc-300 lg:flex">→</div>}
          </div>
        ))}
      </div>
      <div className="mt-5 flex flex-wrap gap-4 text-[11px] text-zinc-500"><Legend color="bg-zinc-400" label="Deterministic" /><Legend color="bg-amber-400" label="Model" /><Legend color="bg-sky-400" label="Guardrail" /><Legend color="bg-emerald-500" label="Human" /></div>
    </div>
  );
}

function ExperimentJourney() {
  const entries = p.causalTimeline;
  return (
    <div className="relative ml-3 border-l border-zinc-200 pl-7">
      {entries.map((item) => (
        <div key={item.id} className="relative pb-7 last:pb-0">
          <span className="absolute -left-[33px] top-1 h-3 w-3 rounded-full border-2 border-white bg-sky-500 shadow-[0_0_0_1px_#bae6fd]" />
          <div className="flex flex-wrap items-baseline gap-2"><h3 className="text-sm font-semibold text-zinc-900">{item.question}</h3><span className="text-[10px] font-medium text-zinc-400">{item.id}</span></div>
          <div className="mt-3 grid gap-2 sm:grid-cols-4"><TimelineCell label="Result" text={item.result} /><TimelineCell label="Failure analysis" text={item.failure} /><TimelineCell label="Learned" text={item.learned} /><TimelineCell label="Next experiment" text={item.next} /></div>
        </div>
      ))}
    </div>
  );
}

// Presentation primitives -------------------------------------------------

function ChartShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return <div className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-[0_18px_50px_-36px_rgba(24,24,27,0.45)] sm:p-6"><h3 className="text-sm font-semibold text-zinc-900">{title}</h3><p className="mt-1 mb-5 text-xs text-zinc-500">{subtitle}</p>{children}</div>;
}

function MetricBar({ label, value, tone, compact = false }: { label: string; value: number; tone: "sky" | "amber" | "zinc" | "rose"; compact?: boolean }) {
  const colors = { sky: "bg-sky-500", amber: "bg-amber-500", zinc: "bg-zinc-400", rose: "bg-rose-500" };
  return <div className={compact ? "mb-1.5" : "mb-2"}><div className="mb-1 flex justify-between gap-3 text-[11px]"><span className="text-zinc-500">{label}</span><span className="font-semibold tabular-nums text-zinc-700">{value.toFixed(1)}%</span></div><div className={`${compact ? "h-1.5" : "h-2"} overflow-hidden rounded-full bg-zinc-100`}><div className={`h-full rounded-full ${colors[tone]}`} style={{ width: `${Math.min(value, 100)}%` }} /></div></div>;
}

function CountBar({ label, count, total, emphasis }: { label: string; count: number; total: number; emphasis: boolean }) {
  const width = (count / total) * 100;
  return <div><div className="mb-2 flex justify-between gap-4"><span className="text-sm font-medium text-zinc-700">{label}</span><span className="font-semibold tabular-nums text-zinc-900">{count}</span></div><div className="h-5 overflow-hidden rounded-md bg-zinc-100"><div className={`h-full rounded-md ${emphasis ? "bg-amber-500" : "bg-sky-400"}`} style={{ width: `${width}%` }} /></div></div>;
}

function DecisionBar({ text, source }: { text: string; source: Parameters<typeof ProvenanceChip>[0]["source"] }) {
  return <div className="rounded-2xl border border-emerald-200 bg-emerald-50/70 px-4 py-3"><div className="flex flex-wrap items-center gap-2"><span className="text-[10px] font-bold uppercase tracking-[0.14em] text-emerald-700">Decision</span><ProvenanceChip source={source} /></div><p className="mt-1 text-sm font-medium leading-6 text-zinc-800">{text}</p></div>;
}

function Callout({ eyebrow, text }: { eyebrow: string; text: string }) { return <div className="rounded-2xl border border-zinc-200 bg-white p-5"><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-400">{eyebrow}</p><p className="mt-2 text-sm font-medium leading-6 text-zinc-800">{text}</p></div>; }
function ExperimentFrame({ why, learned, next }: { why: string; learned: string; next: string }) { return <div className="grid overflow-hidden rounded-2xl border border-zinc-200 bg-white md:grid-cols-3"><StoryBeat label="Why this experiment?" text={why} tone="sky" /><StoryBeat label="What we learned" text={learned} tone="amber" /><StoryBeat label="Next experiment" text={next} tone="emerald" /></div>; }
function StoryBeat({ label, text, tone }: { label: string; text: string; tone: "sky" | "amber" | "emerald" }) { const cls={sky:"text-sky-700",amber:"text-amber-800",emerald:"text-emerald-700"}[tone]; return <div className="border-b border-zinc-100 p-4 last:border-0 md:border-b-0 md:border-r md:last:border-r-0"><p className={`text-[10px] font-bold uppercase tracking-[0.14em] ${cls}`}>{label}</p><p className="mt-2 text-xs leading-5 text-zinc-600">{text}</p></div>; }
function TimelineCell({ label, text }: { label: string; text: string }) { return <div className="rounded-xl bg-zinc-50 p-3"><p className="text-[9px] font-bold uppercase tracking-wide text-zinc-400">{label}</p><p className="mt-1 text-xs leading-5 text-zinc-600">{text}</p></div>; }
function ComparisonStrip({ label, title, facts, tone }: { label: string; title: string; facts: string[]; tone: "neutral" | "sky" }) { return <div className={`rounded-3xl border p-5 ${tone === "sky" ? "border-sky-200 bg-sky-50/70" : "border-zinc-200 bg-white"}`}><p className="text-[10px] font-bold uppercase tracking-[0.14em] text-zinc-500">{label}</p><h3 className="mt-2 text-xl font-semibold text-zinc-950">{title}</h3><div className="mt-4 flex flex-wrap gap-2">{facts.map((fact) => <span key={fact} className="rounded-full border border-white bg-white px-3 py-1 text-xs text-zinc-600 shadow-sm">{fact}</span>)}</div></div>; }
function Step({ label, text, emphasis = false }: { label: string; text: string; emphasis?: boolean }) { return <div className={`rounded-2xl px-4 py-3 ${emphasis ? "bg-amber-100" : "bg-zinc-50"}`}><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">{label}</p><p className="mt-1 text-sm font-semibold text-zinc-800">{text}</p></div>; }
function ArrowRight() { return <div className="hidden items-center justify-center text-zinc-300 md:flex">→</div>; }
function Pipeline({ steps }: { steps: string[] }) { return <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">{steps.map((step, i) => <div key={step} className="relative rounded-2xl border border-zinc-200 bg-white px-3 py-4 text-center text-xs font-semibold text-zinc-700 shadow-sm">{step}{i < steps.length - 1 && <span className="absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 text-zinc-300 lg:block">→</span>}</div>)}</div>; }
function Definition({ label, value }: { label: string; value: string }) { return <div><dt className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">{label}</dt><dd className="mt-1 leading-5 text-zinc-700">{value}</dd></div>; }
function OperatingDelta({ label, from, to }: { label: string; from: string; to: string }) { return <div className="rounded-2xl border border-zinc-200 bg-white p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">{label}</p><p className="mt-2 text-lg font-semibold tabular-nums text-zinc-900">{from} <span className="mx-2 text-zinc-300">→</span> <span className="text-amber-800">{to}</span></p></div>; }
function SmallFinding({ label, value, note }: { label: string; value: string; note?: string }) { return <div className="rounded-2xl bg-zinc-100 p-4"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">{label}</p><p className="mt-1 text-sm font-semibold text-zinc-800">{value}</p>{note && <p className="mt-1 text-xs text-zinc-500">{note}</p>}</div>; }
function Consequence({ label, text }: { label: string; text: string }) { return <div className="border-l-2 border-sky-300 pl-4"><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">{label}</p><p className="mt-1 text-sm leading-6 text-zinc-700">{text}</p></div>; }
function AgentStage({ number, title, headline, detail, caption }: { number: string; title: string; headline: string; detail: string; caption?: string }) { return <div className="relative rounded-3xl border border-zinc-200 bg-white p-5"><span className="text-xs font-semibold text-sky-700">Stage {number}</span><h3 className="mt-2 text-sm font-semibold text-zinc-900">{title}</h3><p className="mt-4 text-xl font-semibold text-zinc-950">{headline}</p><p className="mt-1 text-sm text-zinc-500">{detail}</p>{caption && <p className="mt-3 text-xs leading-5 text-zinc-500">{caption}</p>}</div>; }
function RoutingStat({ label, value }: { label: string; value: number }) { return <div className="mt-3"><div className="flex justify-between text-[10px] text-zinc-500"><span>{label}</span><span>{value}%</span></div><div className="mt-1 h-1.5 rounded-full bg-white"><div className="h-full rounded-full bg-sky-500" style={{ width: `${value}%` }} /></div></div>; }
function SecurityCount({ label, count, tone }: { label: string; count: number; tone: "emerald" | "amber" | "rose" }) { const cls={emerald:"bg-emerald-50 text-emerald-800",amber:"bg-amber-50 text-amber-900",rose:"bg-rose-50 text-rose-800"}[tone]; return <div className={`rounded-2xl p-4 text-center ${cls}`}><div className="text-2xl font-semibold">{count}</div><div className="text-[10px] font-bold uppercase tracking-wide">{label}</div></div>; }
function SecurityRow({ id, name, status }: { id: string; name: string; status: string }) { const cls=status==="PASS"?"bg-emerald-100 text-emerald-800":status==="FAIL"?"bg-rose-100 text-rose-800":"bg-amber-100 text-amber-900"; return <div className="flex items-center justify-between gap-3 rounded-xl border border-zinc-100 px-3 py-2"><div><span className="text-[10px] text-zinc-400">{id}</span><p className="text-xs font-medium text-zinc-700">{name}</p></div><span className={`rounded-full px-2 py-1 text-[9px] font-bold ${cls}`}>{status}</span></div>; }
function SecurityStatus({ value }: { value: string }) { const cls=value==="PASS"?"bg-emerald-100 text-emerald-800":value==="FAIL"?"bg-rose-100 text-rose-800":"bg-amber-100 text-amber-900"; return <span className={`w-fit rounded-full px-2.5 py-1 text-[10px] font-bold ${cls}`}>{value}</span>; }
function SecurityRemediation({ item }: { item: (typeof p.securityStory.remediations)[number] }) { const positive=item.after==="PASS"; return <article className={`rounded-3xl border p-5 ${positive?"border-emerald-200 bg-emerald-50/45":"border-amber-200 bg-amber-50/45"}`}><div className="flex items-start justify-between gap-3"><div><p className="font-mono text-xs font-bold text-zinc-400">{item.id}</p><h4 className="mt-1 text-lg font-semibold text-zinc-950">{item.name}</h4></div><div className="flex items-center gap-2"><SecurityStatus value={item.before} /><span className="text-zinc-300">→</span><SecurityStatus value={item.after} /></div></div><div className="mt-5 grid gap-4 sm:grid-cols-2"><div><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Controls added</p><ul className="mt-2 space-y-1.5 text-xs leading-5 text-zinc-700">{item.controls.map((line)=><li key={line}>✓ {line}</li>)}</ul></div><div><p className="text-[10px] font-bold uppercase tracking-wide text-zinc-400">Verification</p><ul className="mt-2 space-y-1.5 text-xs leading-5 text-zinc-700">{item.verification.map((line)=><li key={line}>✓ {line}</li>)}</ul></div></div><p className="mt-4 rounded-xl bg-white/80 px-3 py-2 text-xs leading-5 text-zinc-600"><strong>Residual risk:</strong> {item.residual}</p></article>; }
function SecurityExample({ example }: { example: (typeof charts.securitySummary.examples)[number] }) { return <article className="rounded-3xl border border-zinc-200 bg-white p-5 shadow-sm"><div className="flex flex-wrap items-start justify-between gap-2"><div><p className="inline-flex rounded-full bg-amber-100 px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide text-amber-900">Adversarial security fixture</p><p className="mt-2 text-[10px] font-bold uppercase tracking-wide text-zinc-400">{example.testId} · {example.family.replaceAll("_", " ")}</p><p className="mt-1 text-xs text-zinc-500">Saved E21 adversarial fixture · {example.population}</p></div><div className="flex gap-2"><EvalBadge level="L1" pass={example.l1Pass} /><span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${example.securityPass ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}>Security {example.securityPass ? "PASS" : "FAIL"}</span></div></div><div className="mt-4 grid gap-2 sm:grid-cols-2"><p className="rounded-xl bg-emerald-50 p-3 text-[11px] leading-5 text-emerald-900"><strong>L1 PASS:</strong> returned evidence genuinely came from the submitted document.</p><p className="rounded-xl bg-rose-50 p-3 text-[11px] leading-5 text-rose-900"><strong>Security FAIL:</strong> the purpose-built document contained malicious instructions that influenced model behavior.</p></div><p className="mt-4 text-[10px] font-bold uppercase tracking-wide text-zinc-400">Malicious fixture text</p><blockquote className="mt-2 rounded-xl bg-rose-50 p-3 font-mono text-xs leading-5 text-zinc-700">{example.maliciousClause}</blockquote><div className="mt-3 rounded-xl bg-zinc-50 p-3"><p className="text-xs font-semibold text-zinc-800">System returned · {example.prediction}</p><p className="mt-1 text-xs leading-5 text-zinc-500">{example.attackOutcome}</p></div></article>; }
function SecurityDecisionList({ title, items, positive=false }: { title: string; items: string[]; positive?: boolean }) { return <div><p className={`text-[10px] font-bold uppercase tracking-wide ${positive?"text-emerald-300":"text-amber-300"}`}>{title}</p><ul className="mt-2 space-y-1.5 text-xs text-zinc-300">{items.map((item)=><li key={item}>{positive?"✓":"—"} {item}</li>)}</ul></div>; }
function CostBar({ label, value, max }: { label: string; value: number; max: number }) { return <div><div className="mb-2 flex justify-between text-sm"><span className="font-medium text-zinc-700">{label}</span><span className="font-semibold tabular-nums text-zinc-900">${value.toFixed(2)}</span></div><div className="h-4 overflow-hidden rounded-md bg-zinc-100"><div className={`h-full rounded-md ${label === "RAG" ? "bg-amber-500" : label === "FULL" ? "bg-sky-500" : "bg-zinc-400"}`} style={{ width: `${(value / max) * 100}%` }} /></div></div>; }
function Checklist({ title, items, tone, icon }: { title: string; items: readonly string[]; tone: "emerald" | "rose"; icon: string }) { return <div className={`rounded-3xl border p-6 ${tone === "emerald" ? "border-emerald-200 bg-emerald-50/70" : "border-rose-200 bg-rose-50/70"}`}><h3 className={`text-sm font-bold uppercase tracking-wide ${tone === "emerald" ? "text-emerald-800" : "text-rose-800"}`}>{title}</h3><ul className="mt-5 space-y-3">{items.map((item) => <li key={item} className="flex gap-3 text-sm text-zinc-700"><span className={tone === "emerald" ? "text-emerald-600" : "text-rose-600"}>{icon}</span>{item}</li>)}</ul></div>; }
function Legend({ color, label }: { color: string; label: string }) { return <span className="inline-flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${color}`} />{label}</span>; }
function LabelValue({ label, value, dark = false }: { label: string; value: string; dark?: boolean }) { return <div><p className={`text-[10px] font-bold uppercase tracking-wide ${dark ? "text-zinc-400" : "text-zinc-400"}`}>{label}</p><p className={`mt-1 text-sm font-medium ${dark ? "text-zinc-800" : "text-white"}`}>{value}</p></div>; }
function EvalBadge({ level, pass }: { level: "L1" | "L2"; pass: boolean }) { return <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${pass ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"}`}>{level} {pass ? "PASS" : "FAIL"}</span>; }
function VerdictPill({ label }: { label: string | null }) { const cls=label==="Contradiction"?"bg-rose-100 text-rose-800":label==="Entailment"?"bg-emerald-100 text-emerald-800":"bg-zinc-200 text-zinc-700"; return <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold ${cls}`}>{label ?? "Unavailable"}</span>; }
function failureSlug(label: string) { if (label.startsWith("Reasoning")) return "reasoning_classification"; if (label.startsWith("Evidence")) return "evidence_selection"; if (label.startsWith("Retrieval")) return "retrieval_limited"; return "runtime_parser_source_validity"; }

function statusLabel(status: string) { return status === "reference" ? "Quality reference" : status === "adopted" ? "Prototype runtime" : status === "rejected" ? "Rejected" : "Baseline"; }
function shortDecision(name: string) { return name === "Rule" ? "Baseline" : name === "FULL" ? "Quality reference" : name === "RAG" ? "Prototype runtime" : "Rejected"; }
function pct(value: number) { return `${(value * 100).toFixed(1)}%`; }
function formatThousands(value: number) { return `${(value / 1000).toFixed(1)}k`; }
function flowLabel(kind: string) { return kind === "model" ? "Model" : kind === "human" ? "Human" : kind === "guardrail" ? "Deterministic" : kind === "input" ? "Input" : "Deterministic"; }
function flowTone(kind: string) { return kind === "model" ? "border-amber-200 bg-amber-50 text-amber-950" : kind === "human" ? "border-emerald-200 bg-emerald-50 text-emerald-950" : kind === "guardrail" ? "border-sky-200 bg-sky-50 text-sky-950" : "border-zinc-200 bg-zinc-50 text-zinc-800"; }
function flowShort(step: string) { return step.replace("clause-aware chunking (256 tok, overlap 50)", "Clause-aware chunking").replace("cross-encoder rerank (ms-marco-MiniLM-L-12-v2)", "Cross-encoder reranker").replace("GPT-5-mini + frozen P0 prompt", "GPT-5-mini · P0").replace("runtime evidence-source validator v2", "Evidence validator").replace("structured output parser", "Structured parser"); }
