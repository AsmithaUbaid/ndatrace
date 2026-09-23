const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Hypothesis = {
  hypothesis_id: string;
  short_description: string;
  hypothesis_text: string;
};

export type RequirementResult = {
  hypothesis_id: string;
  hypothesis_text: string;
  label: "Entailment" | "Contradiction" | "NotMentioned";
  confidence: number;
  explanation: string;
  evidence: string[];
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

export type CostEstimate = {
  avg_cost_per_requirement_usd: number;
  source_experiment_id: string;
  source_sample_size: number;
  model: string;
};

export type ExperimentSummary = {
  experiment_id: string;
  experiment_name: string;
  model: string;
  split: string | null;
  sample_size: number | null;
  accuracy: number | null;
  macro_f1: number | null;
  contradiction_recall: number | null;
  contradiction_recall_ci_low: number | null;
  contradiction_recall_ci_high: number | null;
  joint_label_evidence_correctness: number | null;
  total_cost_usd: number | null;
  timestamp: string | null;
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
  createReview: (ndaText: string, hypothesisIds?: string[]) =>
    request<ReviewResponse>("/review", {
      method: "POST",
      body: JSON.stringify({ nda_text: ndaText, hypothesis_ids: hypothesisIds ?? null }),
    }),
  getReview: (reviewId: string) => request<ReviewResponse>(`/review/${reviewId}`),
  listResults: () => request<ReviewSummary[]>("/results"),
  listExperiments: () => request<ExperimentSummary[]>("/experiments"),
  getCostEstimate: () => request<CostEstimate>("/cost-estimate"),
  extractPdf: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return requestMultipart<{ text: string }>("/extract-pdf", formData);
  },
};
