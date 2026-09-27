export function Checkbox({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <span className="relative mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center">
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        className="peer absolute inset-0 h-full w-full cursor-pointer appearance-none rounded-md border-2 border-zinc-300 bg-white transition-colors checked:border-zinc-900 checked:bg-zinc-900 dark:border-zinc-600 dark:bg-zinc-800 dark:checked:border-zinc-100 dark:checked:bg-zinc-100"
      />
      <svg
        className="pointer-events-none absolute h-3 w-3 text-white opacity-0 peer-checked:opacity-100 dark:text-zinc-900"
        viewBox="0 0 12 12"
        fill="none"
      >
        <path
          d="M2 6L5 9L10 3"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
