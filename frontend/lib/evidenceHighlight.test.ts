import { test } from "node:test";
import assert from "node:assert/strict";
import { highlightVerbatimQuote } from "./evidenceHighlight.ts";

const CHUNK =
  "Receiving Party may disclose Confidential Information to its employees who need to know such information for the purposes of this Agreement, subject to confidentiality obligations.";
const QUOTE =
  "Receiving Party may disclose Confidential Information to its employees who need to know such information for the purposes of this Agreement";

test("highlights the exact verbatim quote inside the chunk", () => {
  const spans = highlightVerbatimQuote(CHUNK, [QUOTE]);
  assert.ok(spans);
  const matched = spans!.filter((s) => s.matched).map((s) => s.text);
  assert.deepEqual(matched, [QUOTE]);
  assert.equal(spans!.map((s) => s.text).join(""), CHUNK);
});

test("returns null when no quote appears verbatim (never fabricates a highlight)", () => {
  const spans = highlightVerbatimQuote(CHUNK, ["This paraphrased sentence does not appear."]);
  assert.equal(spans, null);
});

test("returns null for an empty quote list", () => {
  assert.equal(highlightVerbatimQuote(CHUNK, []), null);
});
