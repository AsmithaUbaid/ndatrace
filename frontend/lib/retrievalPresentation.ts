export type RetrievalTier = {
  label: "Strong" | "Moderate" | "Weak" | "Low" | "Unavailable";
  detail: string;
  tone: "green" | "blue" | "amber" | "neutral";
};

// Presentation-only tiers anchored to the frozen E15 top-1 score distribution:
// q10=-0.5165, q30=3.0928, median=5.0075. These are not probabilities,
// confidence values, or classification thresholds and never affect runtime logic.
const TOP_MATCH_Q10 = -0.5165155708789826;
const TOP_MATCH_Q30 = 3.0927855730056764;
const TOP_MATCH_MEDIAN = 5.00752329826355;

export function retrievalTier(score: number | null): RetrievalTier {
  if (score == null) return { label: "Unavailable", detail: "No retrieval score", tone: "neutral" };
  if (score >= TOP_MATCH_MEDIAN) return { label: "Strong", detail: "Strong relevance", tone: "green" };
  if (score >= TOP_MATCH_Q30) return { label: "Moderate", detail: "Moderate relevance", tone: "blue" };
  if (score >= TOP_MATCH_Q10) return { label: "Weak", detail: "Weak relevance", tone: "amber" };
  return { label: "Low", detail: "Low relevance", tone: "neutral" };
}

