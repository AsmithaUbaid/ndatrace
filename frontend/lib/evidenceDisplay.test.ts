import { test } from "node:test";
import assert from "node:assert/strict";
import { selectEvidenceDisplay } from "./evidenceDisplay.ts";

const RETRIEVED_CHUNK_TEXT =
  "This Non-Disclosure Agreement is entered into between Acme Corp... " +
  "Confidential Information means any technical or business information... " +
  "Receiving Party shall not reverse engineer...";
const VALIDATED_QUOTE =
  "Confidential Information means any technical or business information disclosed by the Disclosing Party";

test("shows the validated model evidence quote, not the retrieval chunk", () => {
  const display = selectEvidenceDisplay("Contradiction", [VALIDATED_QUOTE], true);
  assert.deepEqual(display, { kind: "quotes", quotes: [VALIDATED_QUOTE] });
  assert.ok(!("quotes" in display) || !display.quotes.includes(RETRIEVED_CHUNK_TEXT));
});

test("NotMentioned never shows a retrieved chunk as supporting evidence", () => {
  const display = selectEvidenceDisplay("NotMentioned", [], null);
  assert.deepEqual(display, { kind: "not-mentioned" });
});

test("NotMentioned suppresses evidence quotes even if the model returned some", () => {
  const display = selectEvidenceDisplay("NotMentioned", [VALIDATED_QUOTE], true);
  assert.deepEqual(display, { kind: "not-mentioned" });
});

test("failed source validation shows a review-required state, not a silent fallback to retrieval text", () => {
  const display = selectEvidenceDisplay("Contradiction", [VALIDATED_QUOTE], false);
  assert.deepEqual(display, { kind: "validation-failed" });
});

test("multiple evidence quotes are kept separate, not concatenated", () => {
  const quotes = ["First clause.", "Second clause."];
  const display = selectEvidenceDisplay("Entailment", quotes, true);
  assert.deepEqual(display, { kind: "quotes", quotes });
  assert.equal((display as { quotes: string[] }).quotes.length, 2);
});

test("no evidence returned is reported as such, not left blank or backfilled from retrieval", () => {
  const display = selectEvidenceDisplay("Entailment", [], true);
  assert.deepEqual(display, { kind: "no-evidence" });
});
