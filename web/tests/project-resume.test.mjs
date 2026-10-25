import test from "node:test";
import assert from "node:assert/strict";
import { goalExcerpt, waitingDecisions } from "../src/projectResume.js";
import { catalogSelectionKey, proposalKey } from "../src/methodWorkspace.js";

const ask = (attention_id, phase, branch = "trunk", extra = {}) => ({ attention_id, kind: "researcher_decision", phase, target_phase: phase, branch, disposition: "open", question: attention_id, ...extra });
const methods = [{ method_id: "method.a", branch_id: "method.a", title: "Method A" }];
const branches = [{ branch_id: "method.a" }];

test("the resume question restates the goal's opening paragraph without its headings", () => {
  assert.equal(goalExcerpt("## Goal\nEstimate the effect of testing.\n\nSecond paragraph."), "Estimate the effect of testing.");
  assert.equal(goalExcerpt("# Setting\n\nCompare two survival models."), "Compare two survival models.");
});

test("a sentence interrupted by a display equation is left to the full setting", () => {
  assert.equal(goalExcerpt(String.raw`Compare models with $\hat\beta$. The estimator is
\[ a \]`), String.raw`Compare models with $\hat\beta$.`);
  assert.equal(goalExcerpt(String.raw`We fit a curve and the estimator is
\[ a \]
more`), "We fit a curve and the estimator is…");
});

test("a long single sentence is cut at a word and never inside inline mathematics", () => {
  const excerpt = goalExcerpt(`Alpha ${"word ".repeat(60)}with $\\alpha + \\beta + \\gamma$ trailing words here and more`, 310);
  assert.ok(excerpt.endsWith("with…"));
  assert.equal((excerpt.match(/\$/g) || []).length % 2, 0);
});

test("waiting decisions follow each decision card and leave report clarification to Phase 5 discussions", () => {
  const attention = [ask("setting", "P1"), ask("method", "P2"), ask("theory", "P3", "method.a"), ask("eval", "P4", "method.a"), ask("eval-2", "P4", "method.a"), ask("report", "P5", "method.a"), ask("closed", "P1", "trunk", { disposition: "resolved" })];
  assert.deepEqual(waitingDecisions({ attention, branches, methods }), [
    { phase: "P1", branch: "trunk", count: 1, methodLabel: null },
    { phase: "P2", branch: "method.a", count: 1, methodLabel: "Method A", p2ProposalKey: catalogSelectionKey(methods[0]) },
    { phase: "P3", branch: "method.a", count: 1, methodLabel: "Method A" },
    { phase: "P4", branch: "method.a", count: 2, methodLabel: "Method A" },
  ]);
  assert.deepEqual(waitingDecisions({ attention: [ask("report", "P5", "method.a")], branches, methods }), []);
});

test("shared destination counts include project questions from model reports and retain unknown answers", () => {
  const source = { kind: "phase_issue", branch: "method.a", phase: "P5", family: "attention_items",
    generation_id: "generation.report", sha256: "a".repeat(64), run_id: "run.report", package_id: "package.report" };
  const questions = ["follow-up", "population", "response"].map((id, index) => ask(id, index === 0 ? "P4" : "P5", "method.a", {
    target_phase: "P1", scope: { kind: "project" }, explanation_target: { ...source, object_id: id, entry_pointer: `/${index}` } }));
  const isolated = ask("model-only", "P5", "method.a", { target_phase: "P1",
    scope: { kind: "model", branch: "method.a", model_ref: { stable_id: "method.a", version: 1, definition_sha256: "b".repeat(64) } } });
  const attention = [...questions, isolated];
  const input = { attention, branches, methods };
  const waiting = count => [{ phase: "P1", branch: "trunk", count, methodLabel: null }];
  assert.deepEqual(waitingDecisions(input), waiting(3));
  const answers = questions.map((issue, index) => ({ attention_id: issue.attention_id, revision: index + 1,
    attention: issue, question_ref: issue.explanation_target, scope: issue.scope,
    note: index === 1 ? "This remains unknown." : "Use the supplied study information.",
    origin: index === 1 ? "unknown" : "researcher_reported" }));
  assert.deepEqual(waitingDecisions({ ...input, answers: answers.slice(0, 1) }), waiting(2));
  assert.deepEqual(waitingDecisions({ ...input, answers: answers.slice(0, 2) }), waiting(1));
  assert.deepEqual(waitingDecisions({ ...input, answers }), []);
  const stale = { ...answers[0], question_ref: { ...source, generation_id: "generation.earlier" } };
  assert.deepEqual(waitingDecisions({ ...input, answers: [stale, ...answers.slice(1)] }), waiting(1));
  // Saved originals remain available in P1 after leaving the open inbox.
  assert.deepEqual(waitingDecisions({ ...input, attention: [isolated], answers }), []);
});

test("Next keeps an origin destination when the named phase has no answer card or method context", () => {
  const report = ask("report-next", "P4", "method.a", { target_phase: "P5", scope: { kind: "project" } });
  const unavailable = ask("unavailable-model", "P1", "trunk", { target_phase: "P3", scope: { kind: "project" } });
  const legacy = ask("legacy-next", "P4", "method.a", { target_phase: "future-phase" });
  assert.deepEqual(waitingDecisions({ attention: [report, legacy], branches, methods }), [
    { phase: "P4", branch: "method.a", count: 2, methodLabel: "Method A" },
  ]);
  assert.deepEqual(waitingDecisions({ attention: [unavailable] }), [
    { phase: "P1", branch: "trunk", count: 1, methodLabel: null },
  ]);
});

const identity = (id, version = 1) => ({ stable_id: `method.${id}`, version, definition_sha256: id.repeat(64) });
const catalog = (id, version = 1) => ({ method_id: `method.${id}`, branch_id: `method.${id}`, title: `Method ${id.toUpperCase()}`, identity: identity(id, version) });
const reference = (run) => ({ phase: "P2", branch: "trunk", family: "attention_items", generation_id: `attention.${run}`, sha256: "f".repeat(64), run_id: run, package_id: `package.${run}` });
const exactAsk = (name, modelRef, run = "run.current") => ask(name, "P2", "trunk", {
  generation_ref: reference(run), scope: { kind: "model", branch: "trunk", model_ref: modelRef },
});

test("P2 exact model decisions retain their catalog destination and version", () => {
  const methods = [catalog("a"), catalog("b", 3)];
  const attention = [exactAsk("exact-b", methods[1].identity), exactAsk("earlier-b", identity("b", 2))];
  assert.deepEqual(waitingDecisions({ attention, methods }), [{ phase: "P2", branch: "method.b", count: 1,
    methodLabel: "Method B · Version 3", p2ProposalKey: catalogSelectionKey(methods[1]) }]);
});

test("P2 shared and legacy multi-method decisions count once at answerable destinations", () => {
  const methods = [catalog("a"), catalog("b")];
  const attention = [ask("shared", "P2"), ask("legacy-b", "P2", "trunk", { affected_record_ids: ["method.b"] }),
    ask("legacy-both", "P2", "trunk", { affected_record_ids: ["method.a", "method.b"] })];
  assert.deepEqual(waitingDecisions({ attention, methods }), [
    { phase: "P2", branch: "method.a", count: 2, methodLabel: "Method A · Version 1", p2ProposalKey: catalogSelectionKey(methods[0]) },
    { phase: "P2", branch: "method.b", count: 1, methodLabel: "Method B · Version 1", p2ProposalKey: catalogSelectionKey(methods[1]) },
  ]);
  assert.deepEqual(waitingDecisions({ attention, methods, p2ProposalKey: catalogSelectionKey(methods[1]) }), [
    { phase: "P2", branch: "method.b", count: 3, methodLabel: "Method B · Version 1", p2ProposalKey: catalogSelectionKey(methods[1]) },
  ]);
});

test("P2 proposal decisions keep historical identities and their producing run", () => {
  const methods = [catalog("b", 3)];
  const old = { proposal_id: "proposal.old-b", is_current_package: false, role: "theorist",
    generation_ref: { run_id: "run.old" }, method: { title: "Earlier B", identity: identity("b", 2) } };
  const current = { proposal_id: "proposal.current-b", generation_ref: { run_id: "run.current" }, method: { title: "Current B", identity: methods[0].identity } };
  const attention = [exactAsk("old-b", old.method.identity, "run.old"), exactAsk("other-run-b", old.method.identity, "run.unrelated"),
    exactAsk("current-b", methods[0].identity)];
  assert.deepEqual(waitingDecisions({ attention, methods, proposals: [old, current] }), [
    { phase: "P2", branch: "method.b", count: 1, methodLabel: "Current B · Version 3", p2ProposalKey: proposalKey(current) },
    { phase: "P2", branch: "method.b", count: 1, methodLabel: "Earlier B · Version 2", p2ProposalKey: proposalKey(old) },
  ]);
});

test("P2 current answers suppress only the matching source question", () => {
  const methods = [catalog("b")]; const issue = exactAsk("exact-b", methods[0].identity);
  const answer = { attention_id: issue.attention_id, revision: 1, attention: issue, origin: "researcher_reported" };
  assert.deepEqual(waitingDecisions({ attention: [issue], answers: [answer], methods }), []);
  assert.equal(waitingDecisions({ attention: [issue], answers: [{ ...answer, attention: { ...issue, generation_ref: reference("run.older") } }], methods })[0].count, 1);
});
