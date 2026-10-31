import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { issueCardEntries, issueCardState, issueDisplayState, issueUrgency, phaseNavigationState } from "../src/phaseUiState.js";
import { issueSourceIdentity, issueVersionKey } from "../src/phaseWorkflow.js";
import { phaseInputSummary, phaseQuestionAnchor } from "../src/phaseInputSummary.js";
import { answerSourceNavigation } from "../src/researcherAnswerNavigation.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-phase-ui-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Issues from '${src}/components/IssuesCard.jsx'; export const issues = props => renderToStaticMarkup(<Issues {...props}/>); export const history = props => renderToStaticMarkup(<Issues {...props} pause={<section>Earlier saved decision</section>}/>);`, resolveDir: src, loader: "jsx" }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const question = { issue_id: "decision.a", phase: "P3", branch: "method.a", target_phase: "P3", kind: "researcher_decision", title: "Which setting should be studied?", disposition: "open" };
const answer = { attention_id: question.issue_id, attention: question, revision: 2, note: "Study the dependent setting.", previously_applied_to: ["run.old"] };
const props = { projectId: "test", phase: "P3", branch: "method.a" };

test("P2 response helper follows the recorded destination rather than the displayed source phase", () => {
  for (const target_phase of ["P2", "P3", "P4", undefined]) {
    const html = render.issues({ projectId: "test", phase: "P2", branch: "trunk", issues: [{ ...question, phase: "P2", branch: "trunk", target_phase }] });
    assert.match(html, /<textarea/);
    if (!target_phase || target_phase === "P2") {
      assert.match(html, /After you save, the Lead can use it for the next model development work/);
    }
    else {
      assert.match(html, /After you save, it is available to the next work you start/);
      assert.doesNotMatch(html, /After you save, the Lead can use it for the next model development work/);
      assert.match(html, target_phase === "P3" ? /intended for theory development/ : /intended for numerical evaluation/);
    }
  }
});

test("a refreshed upstream question has one owner while its published context remains readable", () => {
  const source = { kind: "phase_issue", branch: "trunk", phase: "P2", family: "attention_items", generation_id: "generation.refresh", sha256: "a".repeat(64), object_id: "attention.cost", entry_pointer: "/0" };
  const cost = { attention_id: "attention.cost", attention_version_id: "attention.cost.v2", phase: "P2", target_phase: "P1", branch: "trunk",
    kind: "researcher_decision", scope: { kind: "project" }, disposition: "open", question: "Which cost units are intended?",
    context_markdown: "The pooled target is fixed; the cost is still undefined.", likely_consequence: "All proposed models still require the cost definition.",
    explanation_target: source, generation_ref: source };
  const logging = { ...cost, attention_id: "attention.logging", target_phase: "P2", question: "Which logging information is available?", explanation_target: { ...source, object_id: "attention.logging", entry_pointer: "/1" } };
  const earlier = { attention_id: cost.attention_id, revision: 1, note: "An earlier saved account.", question_ref: { ...source, phase: "P1", generation_id: "generation.earlier" }, attention: { ...cost, phase: "P1" } };
  const input = { projectId: "test", phase: "P2", branch: "trunk", attention: [cost, logging], answers: [earlier], onNavigate() {}, onSource() {} };
  const before = structuredClone({ cost, logging, earlier });
  const p2 = issueCardEntries(input);
  assert.deepEqual(p2.entries.map(item => item.attention_id), [logging.attention_id]);
  assert.deepEqual(p2.related.map(item => item.attention_id), [cost.attention_id]);
  assert.deepEqual(p2.earlierAnswers, []);
  assert.equal(issueCardState(p2).label, "1 unanswered question");
  const p1 = issueCardEntries({ ...input, phase: "P1" });
  assert.deepEqual(p1.entries.map(item => item.attention_id), [cost.attention_id]);
  assert.deepEqual(p1.earlierAnswers, [earlier]);
  assert.equal(p1.entries[0].researcher_answer, undefined);
  assert.equal(p1.entries[0].explanation_target, source);
  const html = render.issues(input);
  assert.equal((html.match(/<textarea/g) || []).length, 1);
  const linked = html.slice(html.indexOf('<section class="related-phase-questions">'));
  assert.match(linked, /Which cost units are intended/);
  assert.match(linked, /The pooled target is fixed; the cost is still undefined/);
  assert.match(linked, /All proposed models still require the cost definition/);
  assert.match(linked, /Read the scientific context/);
  assert.match(linked, /Go to Phase 1 - Define and Explore questions/);
  assert.doesNotMatch(linked, /<textarea|Save answer|Edit your answer|Responses to earlier question versions/);
  assert.deepEqual({ cost, logging, earlier }, before);
});

test("model-scoped questions keep their reachable source editor when a shared target cannot host them", () => {
  const modelRef = { stable_id: "method.a", version: 2, definition_sha256: "b".repeat(64) };
  for (const phase of ["P2", "P3", "P4"]) {
    const branch = phase === "P2" ? "trunk" : "method.a";
    for (const target_phase of ["P1", "P2"]) {
      const source = { kind: "phase_issue", phase, branch, family: "attention_items", generation_id: "generation.model", sha256: "c".repeat(64), object_id: "question.model", entry_pointer: "/0" };
      const item = { attention_id: "question.model", phase, branch, target_phase, kind: "researcher_decision", question: "Which model regime applies?",
        scope: { kind: "model", branch, model_ref: modelRef }, explanation_target: source };
      const input = { projectId: "test", branch, methodId: modelRef.stable_id, modelRef, attention: [item] };
      const original = issueCardEntries({ ...input, phase });
      assert.equal(original.entries.length, 1);
      assert.equal(phaseInputSummary({ ...input, phase }).questions.unanswered, 1);
      assert.equal(original.entries[0].explanation_target, source);
      assert.match(render.issues({ ...input, phase }), /<textarea/);
      if (phase !== target_phase) {
        const target = issueCardEntries({ ...input, phase: target_phase, ...(target_phase === "P1" ? { branch: "trunk" } : {}) });
        assert.deepEqual(target.entries, []);
        assert.equal(phaseInputSummary({ ...input, phase: target_phase, ...(target_phase === "P1" ? { branch: "trunk" } : {}) }).questions.total, 0);
      }
      const route = answerSourceNavigation({ projectId: "test", question: original.entries[0] });
      assert.equal(route.change.phase, phase);
      assert.deepEqual(route.anchors, [phaseQuestionAnchor(original.entries[0])]);
    }
  }
});

test("a changed target keeps old answers at the current owner's history with the original exact source", () => {
  const source = { kind: "phase_issue", phase: "P3", branch: "method.a", family: "attention_items", generation_id: "generation.old", sha256: "d".repeat(64), object_id: "question.target", entry_pointer: "/0" };
  const old = { attention_id: source.object_id, phase: "P3", branch: "method.a", target_phase: "P4", kind: "researcher_decision", scope: { kind: "project" }, question: "Which setting applies?", explanation_target: source };
  const current = { ...old, target_phase: "P3", explanation_target: { ...source, generation_id: "generation.current", sha256: "e".repeat(64) } };
  const saved = { attention_id: old.attention_id, revision: 1, question_ref: source, attention: old, note: "The original setting." };
  const input = { ...props, issues: [current], answers: [saved] };
  const owner = issueCardEntries(input);
  assert.deepEqual(owner.earlierAnswers, [saved]);
  assert.deepEqual(issueCardEntries({ ...input, phase: "P4" }).earlierAnswers, []);
  const route = answerSourceNavigation({ projectId: "test", source, questions: [current], answers: [saved] });
  assert.deepEqual(route.change, { phase: "P3", branch: "method.a" });
  assert.deepEqual(route.anchors, [phaseQuestionAnchor(old)]);
  const html = render.issues(input);
  assert.match(html, /Responses to earlier question versions/);
  assert.ok(html.includes(`data-reading-anchor="${route.anchors[0].replaceAll('"', '&quot;')}"`));
  assert.equal(saved.question_ref, source);
  assert.equal(saved.attention.explanation_target, source);
});

test("request urgency comes from responsibility and disposition, never from question phrasing", () => {
  assert.equal(issueDisplayState(question).state, "response");
  assert.equal(issueDisplayState({ ...question, title: "No answer is needed" }).state, "response");
  assert.equal(issueDisplayState({ ...question, disposition: "resolved" }).state, "recorded");
  assert.equal(issueDisplayState({ ...question, kind: undefined }).state, "recorded");
  assert.equal(issueDisplayState({ ...question, researcher_answer: answer }).state, "saved");
});

test("unanswered researcher questions remain neutral while scientific severity stays authored", () => {
  for (const severity of ["blocking", "reassessment_required", undefined]) {
    const issue = { ...question, severity };
    const before = structuredClone(issue);
    assert.deepEqual(issueDisplayState(issue), { state: "response", label: "Open question" });
    assert.deepEqual(issueUrgency(issue), { state: "attention", label: "Open question" });
    assert.equal(issueCardState({ entries: [issue] }).label, "1 unanswered question");
    const html = render.issues({ ...props, issues: [issue] });
    assert.match(html, /data-urgency="attention"/);
    assert.doesNotMatch(html, /data-urgency="blocking"|data-urgency="reassess"|I need your answer/);
    assert.deepEqual(issue, before);
  }
  for (const [severity, state] of [["blocking", "blocking"], ["reassessment_required", "reassess"]]) {
    assert.equal(issueUrgency({ ...question, kind: "scientific_issue", severity }).state, state);
  }
});

test("saved unknown, closed unanswered and active pause states make separate claims", () => {
  const unknown = { ...question, researcher_answer: { ...answer, origin: "unknown" } };
  assert.deepEqual(issueDisplayState(unknown), { state: "saved", label: "Answer saved · still unknown" });
  assert.deepEqual(issueUrgency(unknown), { state: "unknown", label: "Answer saved · still unknown" });
  const closed = { ...question, disposition: "resolved" };
  assert.deepEqual(issueDisplayState(closed), { state: "recorded", label: "Closed question" });
  assert.deepEqual(issueUrgency(closed), { state: "recorded", label: "Closed question" });
  const legacy = { ...question, kind: undefined };
  assert.deepEqual(issueDisplayState(legacy), { state: "recorded", label: "Open question" });
  assert.deepEqual(issueDisplayState({ ...legacy, researcher_answer: unknown.researcher_answer }), { state: "recorded", label: "Answer saved · still unknown" });
  assert.equal(issueCardState({ entries: [legacy] }).state, "history", "A copy change does not reclassify legacy counts.");
  assert.equal(issueCardState({ entries: [unknown] }).state, "history");
  assert.equal(issueCardState({ entries: [question, unknown], activePause: true, activePauseKind: "researcher" }).label, "Work is paused");
});

test("saved responses do not resolve scientific work or claim the researcher owes an answer", () => {
  const finding = { ...question, kind: "scientific_issue", researcher_answer: answer };
  const before = JSON.stringify(finding);
  assert.equal(issueDisplayState(finding).state, "science");
  assert.equal(issueCardState({ entries: [finding] }).state, "science");
  const html = render.issues({ ...props, issues: [finding] });
  assert.match(html, /data-attention-state="science"/);
  assert.match(html, /Your saved answer/);
  assert.match(html, /Earlier work used your previous response/);
  assert.doesNotMatch(html, /data-issue-state="response"|<textarea|Edit your answer|Save your answer/);
  assert.equal(JSON.stringify(finding), before);
});

test("partial shared team work reaches other models in the same phase with its exact source and authored assessment", () => {
  const shared = { ...question, issue_id: "shared-reference-check", kind: "research_task", target_phase: "P3", disposition: "partially_fixed",
    scope: { kind: "project" }, disposition_reason: "Only Method A has been checked. The shared task is not closed.",
    generation_ref: { branch: "method.a", phase: "P3", family: "attention_items", generation_id: "generation.partial", sha256: "a".repeat(64), entry_pointer: "/1" } };
  const before = JSON.stringify(shared);
  for (const branch of ["method.a", "method.b", "method.c"]) {
    // A branch-specific artifacts response can omit shared work published on
    // another branch; the cumulative pending projection still supplies it.
    const input = { ...props, branch, issues: [], attention: [shared] };
    const { entries, related } = issueCardEntries(input);
    assert.equal(entries.length, 1);
    assert.deepEqual(related, []);
    assert.equal(entries[0].generation_ref, shared.generation_ref);
    assert.equal(entries[0].disposition, "partially_fixed");
    assert.equal(issueDisplayState(entries[0]).state, "science");
    assert.equal(issueUrgency(entries[0]).state, "attention");
    assert.equal(issueCardState({ entries }).state, "science");
    const html = render.issues(input);
    assert.match(html, /data-attention-state="science"/);
    assert.match(html, /Team assessment: Partially fixed/);
    assert.match(html, /Applies across models/);
    assert.doesNotMatch(html, /data-issue-state="response"|<textarea|Save your answer|Save choice|I need your answer/);
    assert.equal(render.issues({ ...input, questionsOnly: true }), "");
  }
  assert.equal(JSON.stringify(shared), before);
  assert.equal(issueDisplayState({ ...shared, disposition: "resolved" }).state, "recorded");
  assert.equal(issueDisplayState({ ...shared, kind: "researcher_decision" }).state, "recorded");
});

test("selected-method issue cards omit other methods' project tasks in local and carried work", () => {
  const source = { branch: "trunk", phase: "P2", family: "attention_items", generation_id: "generation.tasks", sha256: "f".repeat(64), entry_pointer: "/1" };
  const task = { phase: "P2", target_phase: "P4", branch: "trunk", kind: "research_task", disposition: "open", scope: { kind: "project" }, generation_ref: source };
  const own = { ...task, attention_id: "own", question: "Check the selected method.", affected_record_ids: ["method.a"] };
  const other = { ...task, attention_id: "other", question: "Check another method.", affected_record_ids: ["method.b"] };
  const both = { ...task, attention_id: "both", question: "Check both named methods.", affected_record_ids: ["method.a", "method.b"] };
  const shared = { ...task, attention_id: "shared", question: "Check the shared setting.", affected_record_ids: ["setting.record"] };
  const decision = { ...other, attention_id: "decision", kind: "researcher_decision", question: "Choose the common cost unit." };
  const attention = [own, other, both, shared, decision];
  const before = JSON.stringify(attention);
  const input = { ...props, phase: "P4", attention };
  const carried = issueCardEntries(input);
  assert.deepEqual(carried.related.map(item => item.attention_id).sort(), ["both", "decision", "own", "shared"]);
  assert.deepEqual(carried.entries, []);
  const original = issueCardEntries({ ...input, phase: "P2" });
  assert.deepEqual(original.entries.filter(item => item.kind === "researcher_decision").map(item => item.attention_id), ["decision"]);
  assert.equal(carried.related.find(item => item.attention_id === "own").generation_ref, source);
  const html = render.issues(input);
  assert.match(html, /Scientific work carried forward/);
  assert.match(html, /Check the selected method|Check both named methods|Check the shared setting/);
  assert.match(html, /Choose the common cost unit/);
  assert.doesNotMatch(html, /Check another method/);
  const local = issueCardEntries({ ...input, attention: attention.map(item => ({ ...item, phase: "P4" })) });
  assert.deepEqual(local.entries.map(item => item.attention_id).sort(), ["both", "decision", "own", "shared"]);
  assert.equal(JSON.stringify(attention), before);
});

test("partial model tasks remain limited to the exact branch, version and definition", () => {
  const modelRef = { stable_id: "method.a", version: 1, definition_sha256: "b".repeat(64) };
  const scoped = { ...question, kind: "research_task", target_phase: "P3", disposition: "partially_fixed",
    scope: { kind: "model", branch: "method.a", model_ref: modelRef } };
  const input = { ...props, modelRef, attention: [scoped] };
  assert.equal(issueCardEntries(input).entries.length, 1);
  for (const context of [
    { branch: "method.b" },
    { modelRef: { ...modelRef, stable_id: "method.b" } },
    { modelRef: { ...modelRef, version: 2 } },
    { modelRef: { ...modelRef, definition_sha256: "c".repeat(64) } },
    { modelRef: undefined },
  ]) assert.deepEqual(issueCardEntries({ ...input, ...context }).entries, []);
  const carried = { ...input, phase: "P4", attention: [{ ...scoped, target_phase: "P4" }] };
  assert.equal(issueCardEntries(carried).related.length, 1);
  assert.deepEqual(issueCardEntries({ ...carried, branch: "method.b" }).related, []);
  assert.deepEqual(issueCardEntries({ ...carried, modelRef: { ...modelRef, version: 2 } }).related, []);
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
  const carried = { ...question, target_phase: "P4" };
  const other = { ...carried, issue_id: "decision.b", branch: "method.b" };
  const savedOnly = { ...answer, attention_id: "decision.saved", attention: { ...carried, issue_id: "decision.saved" } };
  const result = issueCardEntries({ ...props, phase: "P4", issues: [other], attention: [carried], answers: [savedOnly] });
  assert.deepEqual(result.entries.map((issue) => issue.issue_id), [question.issue_id, "decision.saved"]);
  assert.deepEqual(result.related, []);
  assert.equal(result.entries[1].researcher_answer, savedOnly);
  const html = render.issues({ ...props, phase: "P4", issues: [other], attention: [carried], answers: [savedOnly], onNavigate: () => {} });
  assert.match(html, /data-issue-state="response"/);
  assert.match(html, /data-issue-state="saved"/);
  assert.match(html, /Raised during Phase 3 - Theory/);
  assert.doesNotMatch(html, /No decision is currently requested/);
});

test("project questions raised on a model branch reach their named shared phase with the original source", () => {
  const generation_ref = { branch: "method.a", phase: "P5", family: "attention_items", generation_id: "generation.report",
    sha256: "a".repeat(64), run_id: "run.report", package_id: "package.report", entry_pointer: "/0" };
  const shared = { attention_id: "attention.follow-up", phase: "P5", branch: "method.a", target_phase: "P1",
    kind: "researcher_decision", scope: { kind: "project" }, question: "Which survival horizon matters?", generation_ref };
  const before = JSON.stringify(shared);
  for (const phase of ["P1", "P2"]) {
    const issue = { ...shared, target_phase: phase };
    const input = { projectId: "test", phase, branch: "trunk", attention: [issue] };
    const { entries, related } = issueCardEntries(input);
    assert.equal(entries.length, 1); assert.deepEqual(related, []);
    assert.equal(entries[0].generation_ref, generation_ref);
    assert.equal(entries[0].scope, shared.scope);
    assert.equal(entries[0].phase, "P5"); assert.equal(entries[0].branch, "method.a");
    assert.equal(issueVersionKey(entries[0]), issueVersionKey(issue));
    assert.deepEqual(issueSourceIdentity(entries[0]), issueSourceIdentity(issue));
    assert.equal(issueDisplayState(entries[0]).state, "response");
    const html = render.issues(input);
    assert.match(html, /Which survival horizon matters\?/);
    assert.match(html, /Raised during Phase 5 - Report/);
    assert.match(html, /<textarea/); assert.match(html, /Save answer/);
    assert.deepEqual(issueCardEntries({ ...input, phase: "P3" }).entries, []);
  }
  assert.equal(JSON.stringify(shared), before);
});

test("carried model questions cannot enter a shared phase even when authored on trunk", () => {
  const modelRef = { stable_id: "method.a", version: 2, definition_sha256: "b".repeat(64) };
  for (const branch of ["method.a", "trunk"]) {
    for (const phase of ["P1", "P2", "P5"]) {
      const scoped = { ...question, phase, branch, target_phase: "P1",
        scope: { kind: "model", branch, model_ref: modelRef } };
      assert.deepEqual(issueCardEntries({ phase: "P1", branch: "trunk", methodId: modelRef.stable_id, modelRef, attention: [scoped] }).entries, []);
    }
    const scoped = { ...question, phase: "P5", branch, target_phase: "P1",
      scope: { kind: "model", branch, model_ref: modelRef } };
    assert.deepEqual(issueCardEntries({ phase: "P1", branch: "trunk", attention: [scoped] }).entries, []);
    assert.deepEqual(issueCardEntries({ phase: "P1", branch: "trunk", methodId: modelRef.stable_id, modelRef, attention: [scoped] }).entries, []);
    for (const phase of ["P3", "P4"]) {
      const targeted = { ...scoped, target_phase: phase };
      const context = { phase, branch, methodId: modelRef.stable_id, modelRef, attention: [targeted] };
      assert.equal(issueCardEntries(context).entries.length, 1);
      assert.deepEqual(issueCardEntries({ ...context, modelRef: { ...modelRef, version: 3 } }).entries, []);
      assert.deepEqual(issueCardEntries({ ...context, branch: "method.b" }).entries, []);
    }
  }
});

test("carried project answers remain editable at their destination without reusing another source version", () => {
  const source = { kind: "phase_issue", branch: "method.a", phase: "P5", family: "attention_items",
    generation_id: "generation.report", sha256: "a".repeat(64), object_id: "attention.follow-up", entry_pointer: "/0" };
  const issue = { attention_id: source.object_id, phase: "P5", branch: "method.a", target_phase: "P1",
    kind: "researcher_decision", scope: { kind: "project" }, question: "Which horizon matters?", explanation_target: source };
  const earlier = { attention_id: issue.attention_id, revision: 1, note: "An earlier question's response.",
    attention: { ...issue, explanation_target: { ...source, generation_id: "generation.earlier" } } };
  for (const origin of ["researcher_reported", "unknown"]) {
    const saved = { attention_id: issue.attention_id, revision: 2, note: "The clinical horizon remains unknown.",
      origin, question_ref: source, attention: issue, scope: issue.scope };
    const input = { projectId: "test", phase: "P1", branch: "trunk", attention: [issue], answers: [earlier, saved] };
    const { entries, earlierAnswers } = issueCardEntries(input);
    assert.equal(entries[0].researcher_answer, saved); assert.deepEqual(earlierAnswers, [earlier]);
    assert.equal(issueDisplayState(entries[0]).state, "saved");
    const html = render.issues(input);
    assert.match(html, /Edit your answer/); assert.match(html, /Responses to earlier question versions/);
    if (origin === "unknown") assert.match(html, /Still unknown\. This response does not settle the question/);
    const stale = issueCardEntries({ ...input, answers: [earlier] });
    assert.equal(stale.entries[0].researcher_answer, undefined);
    assert.equal(issueDisplayState(stale.entries[0]).state, "response");
  }
});

test("shared P2 questions and method-specific questions stay with the intended method", () => {
  const shared = { ...question, issue_id: "shared", branch: "trunk", phase: "P2", target_phase: "P2" };
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
