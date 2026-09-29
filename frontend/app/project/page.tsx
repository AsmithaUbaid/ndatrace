"use client";

import { useState } from "react";
import { OverviewTab } from "./OverviewTab";
import { CaseExplorerTab } from "./CaseExplorerTab";
import { BuildTab } from "./BuildTab";

const TABS = [
  { id: "overview", label: "Overview & Story" },
  { id: "cases", label: "Case Explorer" },
  { id: "build", label: "Build & Architecture" },
] as const;

type TabId = (typeof TABS)[number]["id"];
export type CaseExplorerRequest = {
  caseKey?: string;
  failureType?: string;
  architecture?: "rule" | "full_context" | "rag";
  failuresOnly?: boolean;
};

export default function ProjectPage() {
  const [tab, setTab] = useState<TabId>("overview");
  const [caseRequest, setCaseRequest] = useState<CaseExplorerRequest>({});

  function openCases(request: CaseExplorerRequest = {}) {
    setCaseRequest(request);
    setTab("cases");
  }

  return (
    <div className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
      <div className="sticky top-0 z-40 -mx-4 mb-8 border-b border-zinc-200/80 bg-[#faf9f7]/95 px-4 backdrop-blur-xl sm:-mx-6 sm:px-6">
        <nav className="flex gap-1 overflow-x-auto py-3" aria-label="Project story sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              aria-current={tab === t.id ? "page" : undefined}
              className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
                tab === t.id
                  ? "bg-zinc-900 text-white shadow-sm"
                  : "text-zinc-500 hover:bg-white hover:text-zinc-900"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </div>

      {tab === "overview" && <OverviewTab onNavigateToCases={openCases} />}
      {tab === "cases" && <CaseExplorerTab initialRequest={caseRequest} />}
      {tab === "build" && <BuildTab />}
    </div>
  );
}
