import test from "node:test";
import assert from "node:assert/strict";
import { api } from "../src/api.js";

test("project reader transports share the caller's abort signal without changing their URLs", async () => {
  const original = globalThis.fetch;
  const controller = new AbortController();
  const seen = [];
  globalThis.fetch = async (url, options) => {
    seen.push({ url, options });
    return { ok: true, status: 200, json: async () => ({}) };
  };
  try {
    const options = { signal: controller.signal };
    await Promise.all([
      api.project("p", options), api.branches("p", options), api.listRuns("p", options),
      api.artifacts("p", "method.a", options), api.decisionsPending("p", options),
      api.readiness("p", "method.a", "P3", undefined, options),
      api.records("p", "method.a", "P3", options), api.assessments("p", "method.a", options),
      api.methods("p", options), api.run("p", "run.a", options),
    ]);
    assert.deepEqual(seen.map(({ url }) => url), [
      "/api/v1/projects/p", "/api/v1/projects/p/branches", "/api/v1/projects/p/runs",
      "/api/v1/projects/p/artifacts?branch=method.a", "/api/v1/projects/p/decisions-pending",
      "/api/v1/projects/p/branches/method.a/phases/P3/readiness",
      "/api/v1/projects/p/branches/method.a/phases/P3/records",
      "/api/v1/projects/p/assessments?branch=method.a", "/api/v1/projects/p/methods",
      "/api/v1/projects/p/runs/run.a",
    ]);
    for (const request of seen) assert.equal(request.options.signal, controller.signal);
    controller.abort();
    assert.ok(seen.every(({ options }) => options.signal.aborted));
    await api.readiness("p", "trunk", "P1", "p1.literature_update");
    assert.equal(seen.at(-1).url, "/api/v1/projects/p/branches/trunk/phases/P1/readiness?mode=p1.literature_update");
    assert.equal(seen.at(-1).options.signal, undefined, "Existing callers remain valid.");
  } finally { globalThis.fetch = original; }
});
