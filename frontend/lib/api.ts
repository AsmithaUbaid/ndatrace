const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Hypothesis = {
  hypothesis_id: string;
  short_description: string;
  hypothesis_text: string;
};

export type RetrievedChunk = {
  chunk_id: number;
  rank: number;
  start_char: number;
  end_char: number;
  bm25_score: number;
  reranker_score: number;
  text: string;
};

// Batch adapter for the same frozen product RAG path used by /api/review.
// Compatibility agent fields remain in saved historical responses, but the
// current runtime never invokes an agent and P0 supplies no confidence.
export type RequirementResult = {
  hypothesis_id: string;
  hypothesis_text: string;
  label: "Entailment" | "Contradiction" | "NotMentioned" | null;
  confidence: number | null;
  confidence_available: boolean;
  explanation: string;
  evidence: string[];
  source_valid: boolean | null;
  needs_human_review: boolean;
  review_reason: string | null;
  sources: RetrievedChunk[];
  retrieved_chunks: RetrievedChunk[];
  agent_used: boolean;
  agent_steps: number;
  cost_usd: number;
  latency_ms: number;
  error: string | null;
};

export type ReviewResponse = {
  review_id: string;
  doc_id: string;
  created_at: string;
  results: RequirementResult[];
  total_cost_usd: number;
  total_latency_ms: number;
  model: string;
};

export type ReviewSummary = {
  review_id: string;
  doc_id: string;
  created_at: string;
  num_requirements: number;
  total_cost_usd: number;
  model: string;
};

// Frozen product path (GPT-5-mini + P0 + retrieved top-5 context).
// No confidence score (the frozen prompt doesn't request one), no agent
// fields (no agent in the final architecture).
export type FinalReviewResponse = {
  label: "Entailment" | "Contradiction" | "NotMentioned" | null;
  evidence: string[];
  explanation: string;
  source_valid: boolean | null;
  needs_human_review: boolean;
  review_reason: string | null;
  model: string;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  trace_id: string;
  sources: RetrievedChunk[];
  retrieved_chunks: RetrievedChunk[];
};

// One row of the reconstruction-v2 final held-out TEST comparison
// (E17/E17B), read server-side from
// results/final/reconstruction_v2/full_test_comparison.csv - never
// recomputed client-side.
export type FinalTestResult = {
  system: string;
  n: number;
  accuracy: number;
  macro_f1: number;
  joint: number;
  entailment_recall: number;
  contradiction_recall: number;
  notmentioned_recall: number;
  evidence_recall: number | null;
  evidence_precision: number | null;
  source_valid_quote_rate: number | null;
  api_cost_usd: number;
  architecture_status: "benchmark" | "final" | null;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

async function requestMultipart<T>(path: string, formData: FormData): Promise<T> {
  // No Content-Type header here - the browser sets it (including the
  // multipart boundary) automatically when the body is a FormData object.
  const res = await fetch(`${API_URL}${path}`, { method: "POST", body: formData });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  listHypotheses: () => request<Hypothesis[]>("/hypotheses"),
  reviewFinal: (ndaText: string, requirement: string) =>
    request<FinalReviewResponse>("/api/review", {
      method: "POST",
      body: JSON.stringify({ nda_text: ndaText, requirement }),
    }),
  listFinalTestComparison: () => request<FinalTestResult[]>("/experiments/e20"),
  extractPdf: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestMultipart<{ text: string }>("/extract-pdf", formData);
  },
  // Batch/history adapter for the frozen product RAG path.
  createReview: (ndaText: string, hypothesisIds?: string[]) =>
    request<ReviewResponse>("/review", {
      method: "POST",
      body: JSON.stringify({ nda_text: ndaText, hypothesis_ids: hypothesisIds ?? null }),
    }),
  getReview: (reviewId: string) => request<ReviewResponse>(`/review/${reviewId}`),
  listResults: () => request<ReviewSummary[]>("/results"),
};
