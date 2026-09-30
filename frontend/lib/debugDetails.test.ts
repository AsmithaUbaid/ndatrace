import { test } from "node:test";
import assert from "node:assert/strict";
import { debugDetailsEnabled } from "./debugDetails.ts";

test("debug details are hidden by default and for non-exact flag values", () => {
  assert.equal(debugDetailsEnabled(undefined), false);
  assert.equal(debugDetailsEnabled(""), false);
  assert.equal(debugDetailsEnabled("false"), false);
  assert.equal(debugDetailsEnabled("TRUE"), false);
});

test("debug details are exposed when the developer flag is enabled", () => {
  assert.equal(debugDetailsEnabled("true"), true);
});
