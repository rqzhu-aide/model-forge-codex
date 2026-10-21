import test from "node:test";
import assert from "node:assert/strict";
import { empiricalFollowupRequest, modesForRequest, targetIsStale, theoryComponent, theoryLinkDestination } from "../src/runRequests.js";

const reference = { branch: "method.a", phase: "P4", family: "protocol", generation_id: "generation.old", sha256: "a".repeat(64), run_id: "run.old" };
const target = { ...reference, kind: "empirical_question", object_id: "test.coverage", question_id: "test.coverage", test_ids: ["test.coverage"], case_ids: ["case.dependent"], statement_ids: ["statement.coverage"] };

test("P4 follow-up retains exact selectors independently of an edited instruction or a new evaluation", () => {
  const question = { title: "Does interval coverage hold?", caption: "Dependent samples", followup_target: structuredClone(target), theory_context: { state: "affected" } };
  const request = empiricalFollowupRequest(question);
  question.followup_target.case_ids.push("case.other");
  request.instructions = "Focus on the boundary case.";
  assert.deepEqual(request.target, target);
  assert.equal(request.branch, "method.a");
  assert.equal(request.phase, "P4");
  assert.equal(request.theoryContext.state, "affected");
  assert.equal(targetIsStale(request, { ...reference, generation_id: "generation.new" }), false);
  assert.equal(empiricalFollowupRequest({ title: "Unlinked narrative" }), null);
  assert.equal(empiricalFollowupRequest({ followup_target: { ...target, sha256: null } }), null);
});

test("targeted P4 keeps empirical scopes while theory assessment and repair keep their own modes", () => {
  const modes = ["p4.preliminary", "p4.comprehensive", "p3.assessment", "p3.theory_revision"].map((mode) => ({ mode }));
  assert.deepEqual(modesForRequest({ target }, modes).map((m) => m.mode), ["p4.preliminary", "p4.comprehensive"]);
  assert.deepEqual(modesForRequest({ target: { ...target, phase: "P3", kind: "statement" }, mode: "p3.assessment" }, modes).map((m) => m.mode), ["p3.assessment"]);
  assert.deepEqual(modesForRequest({ target: { ...target, phase: "P3", kind: "statement" } }, modes).map((m) => m.mode), ["p3.theory_revision"]);
});

test("P2 offers standard model development without making the researcher classify their instructions", () => {
  const modes = ["p2.full_catalog", "p2.researcher_proposal", "p2.focused_method"].map((mode) => ({ mode }));
  assert.deepEqual(modesForRequest({ phase: "P2" }, modes).map((m) => m.mode), ["p2.full_catalog"]);
  assert.deepEqual(modesForRequest({ phase: "P2", supplied_method: { title: "Existing idea" } }, modes).map((m) => m.mode), ["p2.full_catalog"]);
});

test("tested theory never silently routes an old generation into the current graph", () => {
  const tested = { ...reference, phase: "P3", family: "theory_record" };
  const current = { ...tested, generation_id: "generation.current", sha256: "b".repeat(64) };
  assert.equal(theoryLinkDestination(tested, current), "inspected_source");
  assert.equal(theoryLinkDestination(current, current), "current_graph");
  assert.equal(theoryLinkDestination(null, current), "unavailable");
  assert.equal(theoryLinkDestination({ ...tested, branch: "method.b" }, tested), "inspected_source");
  assert.equal(targetIsStale({ target: tested }, current), true);
  assert.equal(theoryComponent({ statements: [{ statement_id: "statement.coverage", text: "Earlier claim" }] }, "statement.coverage").text, "Earlier claim");
  assert.equal(theoryComponent({ statements: [] }, "statement.coverage"), undefined);
});
