// Decides what the "Evidence" section shows. Must never fall back to
// retrieval-chunk text - retrieved chunks are a separate, always-secondary
// concern (see EvidenceSection.tsx's "Retrieval details").
export type EvidenceDisplay =
  | { kind: "not-mentioned" }
  | { kind: "validation-failed" }
  | { kind: "no-evidence" }
  | { kind: "quotes"; quotes: string[] };

export function selectEvidenceDisplay(
  label: string,
  evidence: string[],
  sourceValid: boolean | null,
): EvidenceDisplay {
  if (label === "NotMentioned") return { kind: "not-mentioned" };
  if (sourceValid === false) return { kind: "validation-failed" };
  if (evidence.length === 0) return { kind: "no-evidence" };
  return { kind: "quotes", quotes: evidence };
}
