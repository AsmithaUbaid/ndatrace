"use client";

import { useState, type ReactNode } from "react";

export type Status = "baseline" | "reference" | "adopted" | "rejected" | "authority" | "neutral";

const STATUS_STYLES: Record<Status, string> = {
  baseline: "border-zinc-200 bg-zinc-100 text-zinc-600",
  reference: "border-sky-200 bg-sky-50 text-sky-800",
  adopted: "border-amber-200 bg-amber-50 text-amber-900",
  rejected: "border-rose-200 bg-rose-50 text-rose-700",
  authority: "border-emerald-200 bg-emerald-50 text-emerald-800",
  neutral: "border-zinc-200 bg-white text-zinc-500",
};

// Human-facing label for each status — never render the raw internal key.
export const STATUS_LABEL: Record<Status, string> = {
  baseline: "Baseline",
  reference: "Quality reference",
  adopted: "Prototype runtime",
  rejected: "Rejected",
  authority: "Final authority",
  neutral: "Neutral",
};

export function StatusBadge({ status, children }: { status: Status; children: ReactNode }) {
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${STATUS_STYLES[status]}`}
    >
      {children}
    </span>
  );
}

export function Section({
  id,
  title,
  eyebrow,
  children,
}: {
  id?: string;
  title: string;
  eyebrow?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-28 py-12 sm:py-16 first:pt-0">
      {eyebrow ? (
        <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700">{eyebrow}</div>
      ) : null}
      <h2 className="mb-6 max-w-3xl text-2xl font-semibold tracking-tight text-zinc-950 sm:text-3xl">{title}</h2>
      {children}
    </section>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-zinc-200/80 bg-white p-5 shadow-[0_14px_35px_-28px_rgba(24,24,27,0.45)] ${className}`}>{children}</div>
  );
}

export function Expandable({
  summary,
  children,
  defaultOpen = false,
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="overflow-hidden rounded-2xl border border-zinc-200/80 bg-white shadow-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left hover:bg-zinc-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
      >
        <div className="min-w-0 flex-1">{summary}</div>
        <span className={`shrink-0 text-zinc-400 transition-transform ${open ? "rotate-180" : ""}`}>▾</span>
      </button>
      {open && <div className="border-t border-zinc-100 bg-zinc-50/50 px-5 py-4 text-sm text-zinc-600">{children}</div>}
    </div>
  );
}

export function BarRow({
  label,
  count,
  total,
  color = "bg-blue-600",
}: {
  label: string;
  count: number;
  total: number;
  color?: string;
}) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="mb-2.5">
      <div className="mb-1.5 flex items-center justify-between gap-3 text-xs text-zinc-600">
        <span>{label}</span>
        <span className="shrink-0 font-medium tabular-nums text-zinc-700">
          {count} ({pct.toFixed(1)}%)
        </span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-zinc-100">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
