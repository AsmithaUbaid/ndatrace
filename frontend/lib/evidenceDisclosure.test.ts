import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const componentSource = readFileSync(
  new URL("../components/EvidenceSection.tsx", import.meta.url),
  "utf8",
);
const metadataSource = readFileSync(
  new URL("../components/ReviewMetadata.tsx", import.meta.url),
  "utf8",
);

test("source context remains available and collapsed by default", () => {
  assert.match(componentSource, /View source context/);
  assert.doesNotMatch(componentSource, /<details\s+open/);
});

test("the normal evidence flow does not label a full retrieved chunk as decision evidence", () => {
  assert.match(componentSource, /Evidence used for decision/);
  assert.doesNotMatch(componentSource, /Retrieved source chunk/);
  assert.doesNotMatch(componentSource, /Hide retrieved source chunk/);
});

test("technical details are absent from the normal reviewer flow", () => {
  const normalFlow = componentSource.split("function DebugDetails")[0];
  assert.doesNotMatch(normalFlow, /Raw reranker score/);
  assert.doesNotMatch(normalFlow, /Chunk ID/);
  assert.doesNotMatch(normalFlow, /full retrieved chunk/i);
  assert.doesNotMatch(componentSource, /Technical details/);
});

test("the reranker score has one primary location in normal mode", () => {
  const normalFlow = componentSource.split("function DebugDetails")[0];
  assert.doesNotMatch(normalFlow, /reranker score/i);
  assert.match(metadataSource, /subvalue=\{topChunk \? `Score /);
  assert.match(
    metadataSource,
    /Cross-encoder retrieval relevance score; not prediction confidence\./,
  );
});

test("raw retrieval diagnostics remain available only in the gated debug disclosure", () => {
  assert.match(componentSource, /debugDetailsEnabled\(process\.env\.NEXT_PUBLIC_SHOW_DEBUG_DETAILS\)/);
  assert.match(componentSource, /showDebugDetails && retrievedChunks\.length > 0/);
  assert.match(componentSource, /Debug details/);
  const debugDisclosure = componentSource.split("function DebugDetails")[1];
  assert.match(debugDisclosure, /Raw reranker score/);
  assert.match(debugDisclosure, /Retrieval rank/);
  assert.match(debugDisclosure, /Chunk ID/);
});
