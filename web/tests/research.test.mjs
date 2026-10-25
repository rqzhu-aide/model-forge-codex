import test from "node:test";
import assert from "node:assert/strict";
import { TERMINAL, activityIsSettled, buildTheoryGraph, diagnosticOverview, hasExactRef, latestRunForScope, methodStatusBadge, methodUpdateMessage, normalizeModes, outcome, phaseLaunchLabel, phaseOutputStatus, relatedNodes, sameRef, scoped, shouldReconnectActivity } from "../src/research.js";

test("method evidence cannot leak into trunk or another method", () => {
  const records = [{ branch: "trunk", phase: "P2", title: "catalog" }, { branch: "method.a", phase: "P3", title: "theory a" }, { branch: "method.b", phase: "P3", title: "theory b" }];
  assert.deepEqual(scoped(records, "trunk", "P3"), []);
  assert.deepEqual(scoped(records, "method.b", "P3").map((x) => x.title), ["theory b"]);
  assert.deepEqual(scoped(null, "method.b"), []);
});
test("the latest run outcome belongs to the current phase and method, and clears after newer work", () => {
  const failed = { run_id: "old", branch_id: "method.a", phase: "P3", state: "failed", created_at: "2026-09-08T12:00:00Z" };
  const elsewhere = { run_id: "elsewhere", branch_id: "method.b", phase: "P3", state: "failed", created_at: "2026-09-08T15:00:00Z" };
  const otherPhase = { ...elsewhere, run_id: "other-phase", branch_id: "method.a", phase: "P4" };
  const newer = { ...failed, run_id: "new", state: "published", created_at: "2026-09-08T14:00:00Z" };
  assert.equal(latestRunForScope([elsewhere, otherPhase, failed], "method.a", "P3"), failed);
  assert.equal(latestRunForScope([elsewhere, failed, otherPhase, newer], "method.a", "P3"), newer);
  assert.equal(latestRunForScope([failed, elsewhere], "trunk", "P3"), undefined);
});
test("scientific outcome styling distinguishes negative, partial and unknown evidence", () => {
  assert.equal(outcome("supported")[0], "ok");
  assert.equal(outcome("contradicted")[0], "fail");
  for (const state of ["partially_supported", "inconclusive", "not_assessed", "not_applicable", "future_unknown_state"]) assert.notEqual(outcome(state)[0], "ok");
  assert.equal(outcome("not_applicable")[0], "mut");
});
test("missing statements are unresolved references, not assumptions", () => {
  const graph = buildTheoryGraph({ claims: [{ statement_id: "statement.main", proof_status: "full", depends_on: ["statement.missing", "assumption.regularity"] }] }, {}, [{ assumption_id: "assumption.regularity", text: "Continuity" }]);
  assert.equal(graph.nodes.find((n) => n.id === "statement.missing").kind, "unresolved");
  assert.equal(graph.nodes.find((n) => n.id === "assumption.regularity").kind, "assumption");
  assert.match(graph.issues.join(" "), /Unresolved dependency/);
});
test("circular proof dependencies and duplicates are visible without runaway layout", () => {
  const a = { statement_id: "statement.a", depends_on: ["statement.b"] };
  const graph = buildTheoryGraph({ claims: [a, { statement_id: "statement.b", depends_on: ["statement.a"] }, a] });
  assert.match(graph.issues.join(" "), /Duplicate/);
  assert.match(graph.issues.join(" "), /Circular dependency/);
  assert.equal(graph.nodes.length, 2);
  assert.ok(Math.max(...graph.levels.values()) < 3);
  assert.equal(relatedNodes(graph, "statement.a", "downstream").size, 2);
});
test("large valid theories have correct dependency ordering and affected-claim traversal", () => {
  const claims = Array.from({ length: 60 }, (_, i) => ({ statement_id: `statement.${i}`, depends_on: i ? [`statement.${i - 1}`] : ["assumption.base"] })).reverse();
  const graph = buildTheoryGraph({ claims }, {}, [{ assumption_id: "assumption.base" }]);
  assert.equal(graph.issues.length, 0);
  assert.equal(graph.levels.get("statement.59"), 60);
  assert.equal(relatedNodes(graph, "statement.30", "downstream").size, 30);
  assert.equal(relatedNodes(graph, "assumption.base", "downstream").size, 61);
});
test("all-row diagnostics expose instability hidden beyond the first five rows", () => {
  const rows = Array.from({ length: 6 }, (_, i) => ({ seed_flip: i === 5, n_seeds: 8 }));
  rows.push({ seed_flip: null, n_seeds: 1, assessment: "not_assessed" });
  rows.push({ seed_flip: null, n_seeds: 0, assessment: "not_applicable" });
  const summary = diagnosticOverview([{ stability: rows, solver_health: [{ n_runs: 40, n_failures: 3 }] }]);
  assert.equal(summary.unstable, 1);
  assert.equal(summary.stabilityRows, 8);
  assert.equal(summary.underRepeated, 1);
  assert.equal(summary.incompleteOrNonconverged, 3);
  assert.equal(summary.recordedChecks, 40);
});
test("target identity detects method and version changes while preserving an exact request", () => {
  const ref = { branch: "method.a", phase: "P3", family: "theory_record", generation_id: "gen.1", sha256: "a".repeat(64), run_id: "run.1" };
  assert.equal(hasExactRef(ref), true);
  assert.equal(hasExactRef({ ...ref, sha256: "" }), false);
  assert.equal(sameRef(ref, { ...ref, object_id: "statement.main" }), true);
  assert.equal(sameRef(ref, { ...ref, branch: "method.b" }), false);
  assert.equal(sameRef(ref, { ...ref, generation_id: "gen.2" }), false);
});
test("mode readiness and basis remain tied to each research scope", () => {
  const modes = normalizeModes({ ready: false, modes: [{ mode: "p4.preliminary", ready: true, basis: { sha256: "screen" } }, { mode: "p4.comprehensive", ready: false, reasons: ["Need prespecified tests"], basis: { sha256: "full" } }] });
  assert.equal(modes[0].label, "Feasibility check"); assert.equal(modes[0].ready, true);
  assert.equal(modes[1].label, "Detailed evaluation"); assert.equal(modes[1].ready, false);
  assert.notEqual(modes[0].basis.sha256, modes[1].basis.sha256);
});
test("method update message names the recorded and current versions only when stale", () => {
  assert.equal(methodUpdateMessage(null), null);
  assert.equal(methodUpdateMessage({ status: "current" }), null);
  const stale = { status: "needs_update", current_version: 2, recorded_version: 1 };
  assert.equal(methodUpdateMessage(stale), "Needs update: this work used model version 1. The current model is version 2.");
  const withIdentity = { status: "needs_update", current_version: 3, recorded_identity: { stable_id: "method.a", version: 2 } };
  assert.equal(methodUpdateMessage(withIdentity), "Needs update: this work used model version 2. The current model is version 3.");
  const unknown = { status: "unknown", message: "This model is absent from the current catalog; freshness cannot be established." };
  assert.equal(methodUpdateMessage(unknown), unknown.message);
  assert.match(methodUpdateMessage({ status: "unknown" }), /applicability cannot be established/);
});
test("method status badges distinguish stale work from unverifiable work", () => {
  assert.equal(methodStatusBadge(null), null);
  assert.equal(methodStatusBadge({ status: "current" }), null);
  assert.deepEqual(methodStatusBadge({ status: "needs_update" }), ["warn", "Needs update"]);
  assert.deepEqual(methodStatusBadge({ status: "unknown" }), ["mut", "Applicability unknown"]);
});
test("phase output status selects only this phase's dependent output", () => {
  const method = { dependent_outputs: [
    { phase: "P3", status: "needs_update", current_version: 2 },
    { phase: "P4", status: "current" },
  ] };
  assert.equal(phaseOutputStatus(method, "P3").status, "needs_update");
  assert.equal(phaseOutputStatus(method, "P4").status, "current");
  assert.equal(phaseOutputStatus(method, "P5"), null);
  assert.equal(phaseOutputStatus(null, "P3"), null);
  assert.equal(phaseOutputStatus({}, "P3"), null);
});
test("P3 launch switches to updating theory only for stale branch theory", () => {
  const stale = { phase: "P3", status: "needs_update", current_version: 2 };
  assert.equal(phaseLaunchLabel("P3", stale), "Update theory for model v2");
  assert.equal(phaseLaunchLabel("P3", { phase: "P3", status: "current" }), "Develop theory");
  assert.equal(phaseLaunchLabel("P3", null), "Develop theory");
  assert.equal(phaseLaunchLabel("P4", stale), "Prepare evaluation");
  assert.equal(phaseLaunchLabel("P1", null), "Run Phase 1 - Define and Explore");
});

test("activity resumes after waiting or correction while settled runs do not reconnect", () => {
  assert.equal(TERMINAL.has("awaiting_user"), false, "waiting work remains resumable");
  assert.equal(activityIsSettled("awaiting_user"), true, "the server closes its stream while waiting");
  assert.equal(shouldReconnectActivity("awaiting_user", "running"), true, "a resume in another tab restarts activity");
  assert.equal(shouldReconnectActivity("failed", "correcting"), true, "correction keeps its existing reconnect behavior");
  assert.equal(shouldReconnectActivity("running", "running", "awaiting_user"), true, "a fast external resume may skip the paused snapshot but not the stream-closed event");
  for (const state of ["awaiting_user", "published", "assessed", "failed", "cancelled"])
    assert.equal(shouldReconnectActivity("awaiting_user", state, "awaiting_user"), false, state);
  assert.equal(shouldReconnectActivity("running", "running"), false, "active refreshes do not create duplicate streams");
  assert.equal(shouldReconnectActivity(null, null, "awaiting_user"), false, "missing snapshots cannot restart work");
});
