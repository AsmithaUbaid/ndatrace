import type { ReactNode } from "react";

export default function ProjectLayout({ children }: { children: ReactNode }) {
  return <div className="min-h-screen bg-[#faf9f7] text-zinc-950">{children}</div>;
}
