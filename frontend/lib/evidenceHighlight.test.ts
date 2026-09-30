import { test } from "node:test";
import assert from "node:assert/strict";
import type { RetrievedChunk } from "./api.ts";
import {
  buildVerbatimContext,
  findVerbatimSourceChunk,
  formatSourceProvenance,
  highlightVerbatimQuote,
  technicalChunkInfo,
} from "./evidenceHighlight.ts";

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

test("compact context highlights the exact quote and remains source-only", () => {
  const source =
    "Earlier sentence one. Earlier sentence two. " +
    `${QUOTE}. Later sentence one. Later sentence two. Distant sentence.`;
  const context = buildVerbatimContext(source, QUOTE, 2);
  assert.ok(context);
  assert.deepEqual(context!.spans.filter((span) => span.matched).map((span) => span.text), [QUOTE]);
  assert.equal(context!.spans.map((span) => span.text).join(""), context!.text);
  assert.ok(source.includes(context!.text), "context must be copied from source text without generation");
});

test("compact context includes only the requested surrounding sentence units", () => {
  const quote = "Selected evidence is here";
  const source =
    "Far before. Previous sentence. Selected evidence is here. Next sentence. Far after.";
  const context = buildVerbatimContext(source, quote, 1);
  assert.ok(context);
  assert.equal(context!.text, "Previous sentence. Selected evidence is here. Next sentence.");
  assert.ok(!context!.text.includes("Far before"));
  assert.ok(!context!.text.includes("Far after"));
});

test("missing verbatim evidence never fabricates source context", () => {
  assert.equal(buildVerbatimContext(CHUNK, "A paraphrase that is absent."), null);
});

test("long source text still produces a compact local window", () => {
  const quote = "The selected confidentiality sentence";
  const before = Array.from({ length: 40 }, (_, i) => `Earlier sentence ${i}.`).join(" ");
  const after = Array.from({ length: 40 }, (_, i) => `Later sentence ${i}.`).join(" ");
  const source = `${before} ${quote}. ${after}`;
  const context = buildVerbatimContext(source, quote, 2);
  assert.ok(context);
  assert.ok(context!.text.length < source.length / 4);
  assert.ok(!context!.text.includes("Earlier sentence 0."));
  assert.ok(!context!.text.includes("Later sentence 39."));
});

test("provenance compactly shows the available chunk identifier and retrieval rank", () => {
  const chunk = makeChunk(11, 1, CHUNK, 8.432);
  assert.equal(
    formatSourceProvenance(chunk),
    "Document text · Chunk 12 · Retrieval rank #1",
  );
  assert.equal(formatSourceProvenance(null), null);
});

test("multiple quotes retain separate source chunks and contexts", () => {
  const firstQuote = "First selected quote";
  const secondQuote = "Second selected quote";
  const chunks = [
    makeChunk(2, 1, `Before. ${firstQuote}. After.`, 7.1),
    makeChunk(8, 2, `Earlier. ${secondQuote}. Later.`, 5.4),
  ];
  const firstSource = findVerbatimSourceChunk(firstQuote, chunks);
  const secondSource = findVerbatimSourceChunk(secondQuote, chunks);
  assert.equal(firstSource?.chunk_id, 2);
  assert.equal(secondSource?.chunk_id, 8);
  assert.ok(buildVerbatimContext(firstSource!.text, firstQuote));
  assert.ok(buildVerbatimContext(secondSource!.text, secondQuote));
});

test("technical details preserve rank, raw score, chunk ID, and full text", () => {
  const chunks = [
    makeChunk(4, 2, "Second-ranked full chunk.", -5.63),
    makeChunk(1, 1, "Top-ranked full chunk.", 8.432),
  ];
  assert.deepEqual(technicalChunkInfo(chunks), [
    { chunkId: 1, rank: 1, rawRerankerScore: 8.432, text: "Top-ranked full chunk." },
    { chunkId: 4, rank: 2, rawRerankerScore: -5.63, text: "Second-ranked full chunk." },
  ]);
});

function makeChunk(chunkId: number, rank: number, text: string, rerankerScore: number): RetrievedChunk {
  return {
    chunk_id: chunkId,
    rank,
    start_char: 0,
    end_char: text.length,
    bm25_score: 1,
    reranker_score: rerankerScore,
    text,
  };
}
