import { useState } from "react";

const ITEMS = [
  "This is an academic prototype with no authentication or access control — use sample or synthetic agreements, not real confidential documents.",
  "This is a reviewer aid, not legal advice.",
  "Final approval or rejection remains with a human.",
  "The model can misinterpret clauses even when relevant evidence is present.",
  "“Not Mentioned” results are a known weaker area of the current system.",
  "The current system is evidence-grounded but not prompt-injection-hardened; adversarial document content is a known limitation.",
  "Uploaded enterprise NDAs would require appropriate privacy and access controls in a real deployment.",
];

export function LimitationsPanel() {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200"
      >
        Limitations
        <span aria-hidden>{open ? "−" : "+"}</span>
      </button>
      {open && (
        <ul className="flex flex-col gap-1.5 border-t border-zinc-100 px-4 py-3 text-xs leading-relaxed text-zinc-600 dark:border-zinc-800 dark:text-zinc-400">
          {ITEMS.map((item, i) => (
            <li key={i} className="flex gap-2">
              <span aria-hidden className="text-zinc-400">
                &bull;
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
