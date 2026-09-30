"use client";

import { useState } from "react";
import type { ProvenanceSource } from "@/data/projectPresentation";

// Small clickable chip that expands to show a metric's methodology
// (experiment name, population, measured-vs-modeled) in plain language.
// Never renders a filesystem path or JSON filename — that detail lives only
// in the generated data and the Build tab's developer-facing artifacts.
export function ProvenanceChip({ source }: { source: ProvenanceSource }) {
  const [open, setOpen] = useState(false);
  return (
    <span className="relative inline-block align-middle">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="ml-1.5 rounded-full border border-zinc-200 bg-white px-2 py-0.5 text-[10px] font-medium text-zinc-500 shadow-sm hover:border-zinc-300 hover:text-zinc-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      >
        Measured in {source.population}
      </button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-1 w-72 rounded-xl border border-zinc-200 bg-white p-3 text-xs shadow-xl">
          <dl className="space-y-1.5">
            <Row k="Experiment" v={source.experimentId} />
            <Row k="Population" v={source.population} />
            <Row
              k="Measured/modeled"
              v={source.measured}
              badge={source.measured === "measured" ? "green" : "amber"}
            />
            {source.note ? <Row k="Note" v={source.note} /> : null}
          </dl>
        </div>
      )}
    </span>
  );
}

function Row({
  k,
  v,
  badge,
}: {
  k: string;
  v: string;
  badge?: "green" | "amber";
}) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-zinc-400">{k}</dt>
      <dd
        className={`break-words text-zinc-700 ${
          badge === "green" ? "text-emerald-700" : badge === "amber" ? "text-amber-700" : ""
        }`}
      >
        {v}
      </dd>
    </div>
  );
}
