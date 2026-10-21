import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { issueCardEntries, issueCardState, issueDisplayState, phaseNavigationState } from "../src/phaseUiState.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-phase-ui-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Issues from '${src}/components/IssuesCard.jsx'; export const issues = props => renderToStaticMarkup(<Issues {...props}/>); export const history = props => renderToStaticMarkup(<Issues {...props} pause={<section>Earlier saved decision</section>}/>);`, resolveDir: src, loader: "jsx" }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const question = { issue_id: "decision.a", phase: "P3", branch: "method.a", target_phase: "P4", kind: "researcher_decision", title: "Which setting should be studied?", disposition: "open" };
const answer = { attention_id: question.issue_id, attention: question, revision: 2, note: "Study the dependent setting.", previously_applied_to: ["run.old"] };
const props = { projectId: "test", phase: "P3", branch: "method.a" };

test("P2 response helper follows the recorded destination rather than the displayed source phase", () => {
  for (const target_phase of ["P2", "P3", "P4", undefined]) {
    const html = render.issues({ projectId: "test", phase: "P2", branch: "trunk", issues: [{ ...question, phase: "P2", branch: "trunk", target_phase }] });
    assert.match(html, /<textarea/);
    if (!target_phase || target_phase === "P2") assert.match(html, /Saved for the lead&#x27;s next model development work/);
    else {
      assert.match(html, /Saved for the next work you explicitly start/);
      assert.doesNotMatch(html, /Saved for the lead&#x27;s next model development work/);
      assert.match(html, target_phase === "P3" ? /intended for theory development/ : /intended for numerical evaluation/);
    }
  }
});

test("request urgency comes from responsibility and disposition, never from question phrasing", () => {
  assert.equal(issueDisplayState(question).state, "response");
  assert.equal(issueDisplayState({ ...question, title: "No answer is needed" }).state, "response");
  assert.equal(issueDisplayState({ ...question, disposition: "resolved" }).state, "recorded");
  assert.equal(issueDisplayState({ ...question, kind: undefined }).state, "recorded");
  assert.equal(issueDisplayState({ ...question, researcher_answer: answer }).state, "saved");
});

test("saved responses do not resolve scientific work or claim the researcher owes an answer", () => {
  const finding = { ...question, kind: "scientific_issue", researcher_answer: answer };
  const before = JSON.stringify(finding);
  assert.equal(issueDisplayState(finding).state, "science");
  assert.equal(issueCardState({ entries: [finding] }).state, "science");
  const html = render.issues({ ...props, issues: [finding] });
  assert.match(html, /data-attention-state="science"/);
  assert.match(html, /Saved researcher instruction/);
  assert.match(html, /Earlier work used your previous response/);
  assert.doesNotMatch(html, /data-issue-state="response"|<textarea|Edit instruction|Save instruction/);
  assert.equal(JSON.stringify(finding), before);
});

test("empty, saved, scientific, waiting and correction accounts remain distinct", () => {
  const states = [
    [{}, "empty"],
    [{ entries: [{ ...question, researcher_answer: answer }] }, "history"],
    [{ savedPauseCount: 1 }, "history"],
    [{ entries: [{ ...question, kind: "research_task" }] }, "science"],
    [{ entries: [question] }, "response"],
    [{ activePause: true, savedPauseCount: 1 }, "waiting"],
    [{ correctionCount: 1 }, "correction"],
    [{ related: [question] }, "related"],
  ];
  for (const [input, state] of states) assert.equal(issueCardState(input).state, state);
  const saved = render.history({ ...props, savedPauseCount: 1 });
  assert.match(saved, /data-attention-state="history"/);
  assert.doesNotMatch(saved, /No decision is currently requested|waiting for your direction/);
  const waiting = render.history({ ...props, activePause: true, savedPauseCount: 1 });
  assert.match(waiting, /data-attention-state="waiting"/);
  const correction = render.issues({ ...props, correctionCount: 1 });
  assert.match(correction, /data-attention-state="correction"/);
  assert.doesNotMatch(correction, /No decision is currently requested|questions need your response/);
});

test("React history content is not treated as an active pause", () => {
  const html = render.history({ ...props, savedPauseCount: 1, activePause: false });
  assert.match(html, /Earlier saved decision/);
  assert.match(html, /data-attention-state="history"/);
  assert.doesNotMatch(html, /data-attention-state="waiting"/);
});

test("applicable carried questions join the response rows while retaining exact method scope", () => {
  const other = { ...question, issue_id: "decision.b", branch: "method.b" };
  const savedOnly = { ...answer, attention_id: "decision.saved", attention: { ...question, issue_id: "decision.saved" } };
  const result = issueCardEntries({ ...props, phase: "P4", issues: [other], attention: [question], answers: [savedOnly] });
  assert.deepEqual(result.entries.map((issue) => issue.issue_id), [question.issue_id, "decision.saved"]);
  assert.deepEqual(result.related, []);
  assert.equal(result.entries[1].researcher_answer, savedOnly);
  const html = render.issues({ ...props, phase: "P4", issues: [other], attention: [question], answers: [savedOnly], onNavigate: () => {} });
  assert.match(html, /data-issue-state="response"/);
  assert.match(html, /data-issue-state="saved"/);
  assert.match(html, /Raised during Phase 3 - Theory/);
  assert.doesNotMatch(html, /No decision is currently requested/);
});

test("shared P2 questions and method-specific questions stay with the intended method", () => {
  const shared = { ...question, issue_id: "shared", branch: "trunk", phase: "P2" };
  const a = { ...shared, issue_id: "a", affected_record_ids: ["method.a"] };
  const b = { ...shared, issue_id: "b", affected_record_ids: ["method.b"] };
  const result = issueCardEntries({ issues: [shared, a, b], branch: "branch.a", phase: "P2", methodId: "method.a" });
  assert.deepEqual(result.entries.map((issue) => issue.issue_id), ["shared", "a"]);
});

test("a materially changed question cannot inherit an answer under the same stable ID", () => {
  const firstTarget = { kind: "phase_issue", branch: "method.a", phase: "P3", family: "claim_map", generation_id: "generation.1", sha256: "a".repeat(64), object_id: question.issue_id, entry_pointer: "/issues/0" };
  const first = { ...question, scope: { kind: "project" }, explanation_target: firstTarget };
  const saved = { ...answer, attention: first, scope: first.scope, question_ref: firstTarget };
  const second = { ...first, title: "Is prediction for a new patient?", explanation_target: { ...firstTarget, generation_id: "generation.2", sha256: "b".repeat(64) } };
  const result = issueCardEntries({ ...props, issues: [second], answers: [saved] });
  assert.equal(result.entries[0].researcher_answer, undefined);
  assert.equal(issueDisplayState(result.entries[0]).state, "response");
  assert.deepEqual(result.earlierAnswers, [saved]);
  assert.match(render.issues({ ...props, issues: [second], answers: [saved] }), /Responses to earlier question versions/);
});

test("unchanged premises carry only the explicitly linked exact answer and revision", () => {
  const source = { kind: "phase_issue", branch: "method.a", phase: "P3", family: "claim_map", generation_id: "generation.1", sha256: "a".repeat(64), object_id: question.issue_id };
  const first = { ...question, scope: { kind: "project" }, explanation_target: source };
  const saved = { ...answer, attention: first, scope: first.scope, question_ref: source };
  const successor = { ...first, explanation_target: { ...source, generation_id: "generation.2" }, answer_applicability_refs: [{ attention_id: question.issue_id, answer_revision: answer.revision, question_ref: source, reason: "Target and collection process are unchanged." }] };
  const carry = (issue) => issueCardEntries({ ...props, issues: [issue], answers: [saved] }).entries[0].researcher_answer;
  assert.equal(carry(successor), saved);
  assert.equal(carry({ ...successor, answer_applicability_refs: [{ ...successor.answer_applicability_refs[0], answer_revision: 1 }] }), undefined);
  assert.equal(carry({ ...successor, answer_applicability_refs: [{ ...successor.answer_applicability_refs[0], reason: "" }] }), undefined);
  const scoped = { ...saved, scope: { kind: "model", branch: "method.a", model_ref: { stable_id: "method.a", version: 1, definition_sha256: "c".repeat(64) } } };
  const otherScope = { ...successor, scope: { ...scoped.scope, model_ref: { ...scoped.scope.model_ref, version: 2 } } };
  assert.equal(issueCardEntries({ ...props, modelRef: otherScope.scope.model_ref, issues: [otherScope], answers: [scoped] }).entries[0].researcher_answer, undefined);
});

const branches = [{ branch_id: "trunk", phases: { p2: ["catalog"] } }, { branch_id: "method.a", phases: {} }, { branch_id: "method.b", phases: { p4: ["summary"] } }];
const methods = [{ method_id: "method.a", title: "Method A" }, { method_id: "method.b", title: "Method B" }];
const state = (options = {}) => phaseNavigationState({ phase: "P4", branch: "method.a", branches, methods, ...options });

test("a selected model never borrows another method's results or waiting status", () => {
  const runs = [{ branch_id: "method.b", phase: "P4", state: "awaiting_user" }];
  assert.equal(state({ runs }).state, "idle");
  assert.equal(state({ branch: "method.b", runs }).state, "waiting");
  assert.equal(state({ branch: "method.b" }).state, "done");
});

test("waiting and running override older publication independently of the selected phase", () => {
  const published = { branch_id: "method.a", phase: "P4", state: "published" };
  assert.equal(state({ runs: [published, { ...published, state: "awaiting_user" }] }).state, "waiting");
  assert.equal(state({ runs: [published, { ...published, state: "running" }] }).state, "running");
  assert.equal(state({ runs: [published, { ...published, state: "awaiting_user", assessment_purpose: "explanation" }] }).state, "done");
  // UI selection is not an input to the scientific context's phase state.
  assert.equal(state({ selectedPhase: "P1", runs: [published] }).state, "done");
});

test("trunk navigation explicitly counts methods and retains identities for the chooser", () => {
  const overview = state({ branch: "trunk" });
  assert.equal(overview.state, "done"); assert.match(overview.label, /1 model/);
  assert.deepEqual(overview.contexts.map((item) => [item.branch, item.state]), [["method.a", "idle"], ["method.b", "done"]]);
  const waiting = state({ branch: "trunk", runs: [{ branch_id: "method.a", phase: "P4", state: "awaiting_user" }] });
  assert.equal(waiting.state, "waiting"); assert.match(waiting.label, /1 model needs your direction/);
  assert.equal(waiting.contexts.find((item) => item.branch === "method.a").label, "Waiting for your direction");
});

test("shared phase navigation uses trunk while keeping the supplied method selection intact", () => {
  const context = { phase: "P2", branch: "method.a", branches, methods, runs: [] };
  const before = JSON.stringify(context);
  assert.equal(phaseNavigationState(context).state, "done");
  assert.equal(JSON.stringify(context), before);
  assert.equal(phaseNavigationState({ ...context, phase: "P4" }).state, "idle");
});

test("latest failed or cancelled scientific work stays visible beside retained results", () => {
  const published = { run_id: "run.published", branch_id: "method.b", phase: "P4", state: "published", created_at: "2026-09-29T10:00:00Z" };
  for (const interruption of ["failed", "cancelled"]) {
    const runs = [published, { ...published, run_id: "run.interrupted", state: interruption, created_at: "2026-09-30T10:00:00Z" }, { ...published, run_id: "run.explanation", state: "assessed", intent: "assessment", assessment_purpose: "explanation", created_at: "2026-09-30T11:00:00Z" }];
    const status = state({ branch: "method.b", runs });
    assert.equal(status.state, "interrupted"); assert.equal(status.retained, true);
    assert.equal(status.latest_attempt.run_id, "run.interrupted");
    assert.match(status.label, new RegExp(interruption)); assert.match(status.label, /earlier results available/);
    const summary = state({ branch: "trunk", runs });
    assert.equal(summary.interruptedCount, 1); assert.equal(summary.retainedCount, 1);
  }
});

test("component assessments do not change the scientific phase state", () => {
  assert.equal(state({ runs: [{ branch_id: "method.a", phase: "P4", state: "running", intent: "assessment" }] }).state, "idle");
  assert.equal(phaseNavigationState({ phase: "P3", branch: "method.a", branches, runs: [{ branch_id: "method.a", phase: "P3", mode: "p3.assessment", state: "failed" }] }).state, "idle");
});

test("published method output freshness remains separate from an interruption or current work", () => {
  const status = { branch: "method.b", phase: "P4", status: "needs_update" };
  assert.equal(state({ branch: "method.b", outputStatuses: [status] }).state, "outdated");
  const summary = state({ branch: "trunk", outputStatuses: [status] });
  assert.equal(summary.outdatedCount, 1); assert.match(summary.label, /1 outdated/);
  const runs = [{ run_id: "run.failure", branch_id: "method.b", phase: "P4", state: "failed" }];
  const interrupted = state({ branch: "method.b", runs, outputStatuses: [status] });
  assert.equal(interrupted.state, "interrupted"); assert.equal(interrupted.outdated, true);
  assert.equal(state({ branch: "method.b", runs: [{ ...runs[0], state: "running" }], outputStatuses: [status] }).state, "running");
  assert.equal(state({ branch: "method.b", outputStatuses: [{ ...status, status: "unknown" }] }).label, "Results available · freshness unknown");
});
