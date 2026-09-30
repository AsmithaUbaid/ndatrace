"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Review" },
  { href: "/project", label: "Project Story" },
  { href: "/history", label: "Review History" },
];

export function NavBar() {
  const pathname = usePathname();

  return (
    <header className="border-b border-zinc-200/80 bg-white/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4 sm:justify-between sm:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-zinc-900 text-sm font-bold text-white shadow-sm">
            N
          </span>
          <span className="text-base font-semibold tracking-tight text-zinc-900">
            NDATrace
          </span>
        </Link>
        <nav className="ml-auto flex min-w-0 gap-1 overflow-x-auto">
          {LINKS.map((link) => {
            const active = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`shrink-0 rounded-xl px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-zinc-900 text-white shadow-sm"
                    : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
                }`}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
