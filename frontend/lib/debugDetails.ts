// Public Next.js environment variables are embedded at build time. Requiring
// the exact string "true" keeps reviewer-facing builds hidden by default.
export function debugDetailsEnabled(value: string | undefined): boolean {
  return value === "true";
}
