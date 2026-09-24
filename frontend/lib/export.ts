import { ReviewResponse } from "./api";
import { toVerdict, VERDICT_TITLES } from "./verdict";

export function reviewToText(review: ReviewResponse): string {
  const lines: string[] = [];
  lines.push("NDATrace — NDA Requirement Review");
  lines.push(`Generated: ${new Date(review.created_at).toLocaleString()}`);
  lines.push(`Model: ${review.model}`);
  lines.push(
    `Cost: $${review.total_cost_usd.toFixed(6)}  ·  Latency: ${(review.total_latency_ms / 1000).toFixed(1)}s`
  );
  lines.push("");
  lines.push("=".repeat(70));
  lines.push("");

  for (const r of review.results) {
    if (r.error) {
      lines.push(`[FAILED] ${r.hypothesis_text} (${r.hypothesis_id})`);
      lines.push(`  Error: ${r.error}`);
      lines.push("");
      continue;
    }
    const verdict = VERDICT_TITLES[toVerdict(r.label)];
    lines.push(`[${verdict.toUpperCase()}] ${r.hypothesis_text} (${r.hypothesis_id})`);
    lines.push(`  Confidence: ${Math.round(r.confidence * 100)}%`);
    lines.push(`  ${r.agent_used ? `Escalated for deeper review (${r.agent_steps} steps)` : "Answered directly"}`);
    if (r.explanation) lines.push(`  Explanation: ${r.explanation}`);
    for (const e of r.evidence) lines.push(`  Evidence: "${e}"`);
    lines.push("");
  }

  return lines.join("\n");
}

export function reviewToJson(review: ReviewResponse): string {
  return JSON.stringify(review, null, 2);
}

export function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
