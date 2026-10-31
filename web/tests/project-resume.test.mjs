import test from "node:test";
import assert from "node:assert/strict";
import { goalExcerpt, sharedGoalExcerpt, waitingDecisions } from "../src/projectResume.js";
import { catalogSelectionKey, proposalKey } from "../src/methodWorkspace.js";
import { phaseQuestionAnchor } from "../src/phaseInputSummary.js";

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

test("a blank line before display math does not leave an unfinished definition in the preview", () => {
  const sentence = "Develop an offline method that maximizes reward while limiting a new patient's cumulative-cost risk.";
  for (const display of ["$$\np_C(\\pi;b)\\le\\alpha\n$$", "\\[\np_C(\\pi;b)\\le\\alpha\n\\]"]) {
    assert.equal(goalExcerpt(`${sentence} For a policy $\\pi$, define\n\n${display}`), sentence);
  }
});

test("a long single sentence is cut at a word and never inside inline mathematics", () => {
  const excerpt = goalExcerpt(`Alpha ${"word ".repeat(60)}with $\\alpha + \\beta + \\gamma$ trailing words here and more`, 310);
  assert.ok(excerpt.endsWith("with…"));
  assert.equal((excerpt.match(/\$/g) || []).length % 2, 0);
});

test("the shared setting excerpt uses only confirmed clarifications for the exact published goal", () => {
  const reference = { kind: "research_goal", branch: "trunk", phase: "P1", family: "research_basis", generation_id: "goal.current", sha256: "a".repeat(64), run_id: "run.current", package_id: "package.current", entry_pointer: "/research_setting/research_goal_markdown" };
  const item = { item_id: "goal.clarification", revision: 1, status: "confirmed", topic: "research_goal", scope: { kind: "project" }, statement: "Maximize reward with a separate new-patient cost constraint.\n\nThe complete equation stays in the setting.", source_refs: [reference] };
  const context = { items: [item] }; const before = JSON.stringify(context);
  assert.equal(sharedGoalExcerpt("Earlier target.", context, reference), "Maximize reward with a separate new-patient cost constraint.");
  for (const change of [{ status: "proposed" }, { topic: "expectation" }, { scope: { kind: "model" } }, { source_refs: [] }, { source_refs: [{ ...reference, generation_id: "goal.other" }] }]) {
    assert.equal(sharedGoalExcerpt("Earlier target.", { items: [{ ...item, ...change }] }, reference), "Earlier target.");
  }
  assert.equal(sharedGoalExcerpt("Earlier target.", context, null), "Earlier target.");
  assert.equal(JSON.stringify(context), before);
});

test("multiple current goal excerpts stay separate, bounded and preserve unknown content", () => {
  const reference = { kind: "research_goal", branch: "trunk", phase: "P1", family: "research_basis", generation_id: "goal.current", sha256: "a".repeat(64), run_id: "run.current", package_id: "package.current", entry_pointer: "/research_setting/research_goal_markdown" };
  const item = { status: "confirmed", topic: "research_goal", scope: { kind: "project" }, source_refs: [reference] };
  const long = `Maximize reward while ${"retaining the required scientific qualification ".repeat(15)}.`;
  const context = { items: [{ ...item, item_id: "one", statement: long }, { ...item, item_id: "two", origin: "unknown", statement: "The cost units remain unknown." }] };
  assert.equal(sharedGoalExcerpt("Earlier target.", context, reference), `${goalExcerpt(long)} · The cost units remain unknown.`);
  assert.ok(goalExcerpt(long).length <= 321);
});

test("waiting decisions follow their existing answer surface, including conditional report editorial choices", () => {
  const attention = [ask("setting", "P1"), ask("method", "P2"), ask("theory", "P3", "method.a"), ask("eval", "P4", "method.a"), ask("eval-2", "P4", "method.a"), ask("report", "P5", "method.a"), ask("closed", "P1", "trunk", { disposition: "resolved" })];
  assert.deepEqual(waitingDecisions({ attention, branches, methods }), [
    { phase: "P1", branch: "trunk", count: 1, methodLabel: null },
    { phase: "P2", branch: "method.a", count: 1, methodLabel: "Method A", p2ProposalKey: catalogSelectionKey(methods[0]) },
    { phase: "P3", branch: "method.a", count: 1, methodLabel: "Method A" },
    { phase: "P4", branch: "method.a", count: 2, methodLabel: "Method A" },
    { phase: "P5", branch: "method.a", count: 1, methodLabel: "Method A", anchors: [phaseQuestionAnchor(attention[5])] },
  ]);
  assert.deepEqual(waitingDecisions({ attention: [attention[5]], branches, methods }), [
    { phase: "P5", branch: "method.a", count: 1, methodLabel: "Method A", anchors: [phaseQuestionAnchor(attention[5])] },
  ]);
});

test("P5 waits only on the exact report method's unanswered editorial question and never duplicates its pause", () => {
  const modelRef = { stable_id: "method.a", version: 2, definition_sha256: "b".repeat(64) };
  const reference = { kind: "phase_issue", phase: "P5", branch: "method.a", family: "attention_items", generation_id: "report.current", sha256: "a".repeat(64) };
  const question = ask("report-editorial", "P5", "method.a", { scope: { kind: "model", branch: "method.a", model_ref: modelRef }, explanation_target: { ...reference, object_id: "report-editorial", entry_pointer: "/0" } });
  const options = { attention: [question, { ...question, attention_id: "old-model", scope: { ...question.scope, model_ref: { ...modelRef, version: 1 } } },
    ask("pause", "P5", "method.a", { explanation_target: { kind: "researcher_pause", phase: "P5", branch: "method.a" } }),
    ask("scientific", "P3", "method.a", { kind: "research_task", target_phase: "P5" })],
    methods: [{ ...methods[0], identity: modelRef }, { method_id: "method.b", branch_id: "method.b", title: "Method B" }], branches: [...branches, { branch_id: "method.b" }] };
  const expected = [{ phase: "P5", branch: "method.a", count: 1, methodLabel: "Method A", anchors: [phaseQuestionAnchor(question)] }];
  assert.deepEqual(waitingDecisions(options), expected);
  const answer = { attention_id: question.attention_id, revision: 1, attention: question, question_ref: question.explanation_target, scope: question.scope, note: "Use the retained emphasis.", origin: "researcher_reported" };
  assert.deepEqual(waitingDecisions({ ...options, answers: [answer] }), []);
  assert.deepEqual(waitingDecisions({ ...options, answers: [{ ...answer, question_ref: { ...question.explanation_target, generation_id: "report.old" } }] }), expected);
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

test("model-scoped questions targeted at a shared phase count only at their reachable model editor", () => {
  const modelRef = { stable_id: "method.a", version: 2, definition_sha256: "a".repeat(64) };
  const localMethods = [{ ...methods[0], identity: modelRef }];
  for (const phase of ["P3", "P4"]) {
    for (const target_phase of ["P1", "P2"]) {
      const question = ask("model-upstream", phase, "method.a", { target_phase, scope: { kind: "model", branch: "method.a", model_ref: modelRef } });
      assert.deepEqual(waitingDecisions({ attention: [question], methods: localMethods, branches }), [{ phase, branch: "method.a", count: 1, methodLabel: "Method A" }]);
    }
  }
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
