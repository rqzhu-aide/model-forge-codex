import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { phaseInputSummary } from "../src/phaseInputSummary.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-pause-navigation-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {renderToStaticMarkup as html} from 'react-dom/server'; export {EmpiricalPause, EmpiricalSavedDecisions} from '${src}/components/EmpiricalProgress.jsx'; export {default as Dialogue} from '${src}/components/ResearcherDialogue.jsx'; export {default as ProjectView} from '${src}/components/ProjectView.jsx'; export {default as Pause} from '${src}/components/ResearcherPause.jsx'; export {api} from '${src}/api.js'; export {saveConversationDraft} from '${src}/assumptionConversations.js'; export const create=React.createElement; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const target = { kind: "p4_pause", phase: "P4", branch: "method.a", run_id: "run.paused",
  request_id: "decision.two", object_id: "decision.two", revision: 2, sha256: "a".repeat(64) };
const request = { request_id: target.request_id, revision: target.revision, question: "Which comparison should continue?", explanation_target: target };
const earlier = { ...request, request_id: "decision.one", revision: 1, explanation_target: { ...target, request_id: "decision.one", object_id: "decision.one", revision: 1 } };
const answer = item => ({ request_id: item.request_id, request_revision: item.revision, revision: 1, note: "Use the recorded comparison.", request: item });
const run = { phase: "P4", run_id: target.run_id, branch_id: target.branch, state: "awaiting_user",
  p4_progress: { pause_request: request, saved_answers: [answer(earlier), answer(request)] } };
const anchor = source => `evaluation-pause:${source.run_id}:${source.request_id}:${source.revision}`;
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];

test("active and historical evaluation answers each expose one exact navigation destination", () => {
  const props = { projectId: "project.pause", run };
  const html = ui.html(ui.create("div", null, ui.create(ui.EmpiricalPause, { ...props, request }), ui.create(ui.EmpiricalSavedDecisions, props)));
  const anchors = [...html.matchAll(/data-reading-anchor="(evaluation-pause:[^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(anchors.sort(), [anchor(target), anchor(earlier.explanation_target)].sort());
  assert.equal(new Set(anchors).size, anchors.length);
  assert.match(html, /Saved evaluation decisions \(1\)/);
});

test("a saved-copy link targets the exact active or historical evaluation answer", () => {
  const names = ["window", "getComputedStyle", "requestAnimationFrame", "cancelAnimationFrame"];
  const previous = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const priorDispatcher = ui.dispatcher.current;
  try {
    globalThis.window = { scrollY: 20, innerHeight: 700 };
    globalThis.getComputedStyle = () => ({ display: "block", visibility: "visible" });
    globalThis.requestAnimationFrame = () => 1;
    globalThis.cancelAnimationFrame = () => {};
    for (const source of [target, earlier.explanation_target]) {
      const updates = [];
      ui.dispatcher.current = { useState: value => [typeof value === "function" ? value() : value, next => updates.push(next)], useRef: value => ({ current: value }), useEffect() {} };
      const owner = { kind: "researcher_answer", attention_id: source.request_id, answer_revision: 1, question_ref: source };
      const item = { item_id: "context.answer.navigation", revision: 1, status: "confirmed", scope: { kind: "project" }, statement: "The saved answer.", answer_refs: [owner] };
      const tree = ui.Dialogue({ projectId: "project.pause", phase: "P4", branch: "method.a", problemContext: { items: [item], proposals: [] }, onNavigate: () => assert.fail("A mounted owner should be visited within the current reading scope.") });
      const content = nodes(tree).find(node => node.props.intro)?.props.intro;
      const link = nodes(content).find(node => node.props.onReviewAnswer);
      assert.ok(link, "The saved copy exposes its owner navigation handler.");
      const destination = { tagName: "SECTION", parentElement: null, closest: () => null, getAttribute: key => key === "data-reading-anchor" ? anchor(source) : null, removeAttribute() {} };
      const origin = { closest: selector => selector === "[data-reader-ready]" ? root : null, getAttribute: () => null };
      const root = { querySelectorAll: selector => selector === "[data-reading-anchor]" ? [destination] : [], contains: element => element === origin };
      destination.parentElement = root;
      link.props.onReviewAnswer(owner, origin);
      const visit = updates.find(value => value?.target);
      assert.equal(visit?.target, destination, "The individual pause is used instead of the saved-decision group.");
      visit.dispose();
    }
  } finally {
    ui.dispatcher.current = priorDispatcher;
    for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; }
  }
});

test("unfiltered context owners keep copies, proposals and old drafts out of independent note editors", () => {
  const owner = { kind: "researcher_answer", attention_id: target.request_id, answer_revision: 1, question_ref: target };
  const copy = { item_id: "custom.answer-copy", revision: 1, status: "confirmed", scope: { kind: "project" }, statement: "An answer saved through another proposal or pause." };
  const interpretation = { ...copy, item_id: "context.interpretation", statement: "A separately confirmed interpretation.", answer_refs: [owner] };
  const contextAnswers = [{ attention_id: owner.attention_id, revision: 1, question_ref: target, context_ref: { item_id: copy.item_id, revision: copy.revision } }];
  const pendingCopy = { amendment_id: "proposal.answer-copy", status: "pending", item: { ...copy, revision: 2 } };
  const pendingInterpretation = { amendment_id: "proposal.interpretation", status: "pending", item: { ...interpretation, revision: 2 } };
  const currentTarget = { kind: "project_context", project_id: "project.raw-owners", context_revision: 2, brief_revision: 1, sha256: "b".repeat(64) };
  const problemContext = { revision: 2, dialogue_target: currentTarget, items: [copy, interpretation], proposals: [pendingCopy, pendingInterpretation] };
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const summary = phaseInputSummary({ projectId: currentTarget.project_id, phase, branch: "method.a", answers: [], contextAnswers, problemContext });
    assert.equal(summary.questions.total, 0, "Ownership data does not revive filtered question editors.");
    assert.deepEqual(summary.understanding.items.map(row => row.item.item_id), [interpretation.item_id], phase);
    assert.deepEqual(summary.understanding.proposals.map(row => row.proposal.amendment_id), [pendingInterpretation.amendment_id], phase);
  }
  const draftKey = "problem-response:raw-owners-test";
  ui.saveConversationDraft(draftKey, { projectId: currentTarget.project_id, target: { ...currentTarget, context_revision: 1, sha256: "c".repeat(64), object_id: copy.item_id }, item: copy, text: "A retained unsent answer draft." });
  try {
    const html = ui.html(ui.create(ui.Dialogue, { projectId: currentTarget.project_id, phase: "P2", branch: "trunk", answers: [], contextAnswers, problemContext }));
    assert.equal((html.match(/>Edit your note</g) || []).length, 1, "Only the independent interpretation has a context edit button.");
    assert.equal((html.match(/>Confirm interpretation</g) || []).length, 1, "Only the independent proposal can be confirmed here.");
    assert.match(html, /Your unsent draft is retained below/);
    assert.match(html, /A retained unsent answer draft/);
    assert.doesNotMatch(html, /Edit your saved note/);
    assert.equal((html.match(/>Review your answer</g) || []).length, 3, "Saved, proposed and drafted copies link to the owner without their own editors.");
  } finally { ui.saveConversationDraft(draftKey, null); }
});

test("ProjectView forwards raw copy owners separately and routes a cross-model answer to its recorded scope", () => {
  const priorDispatcher = ui.dispatcher.current;
  const source = { ...target, kind: "researcher_pause", project_id: "project.forward", phase: "P3", branch: "method.original", stage_id: "theory.one" };
  const activeSource = { ...source, branch: "method.current", request_id: "request.current", object_id: "request.current" };
  const question = { ...request, request_id: activeSource.request_id, revision: activeSource.revision, stage_id: activeSource.stage_id, explanation_target: activeSource };
  const activeIssue = { attention_id: question.request_id, phase: "P3", branch: activeSource.branch, kind: "researcher_decision", explanation_target: activeSource };
  const own = { request_id: question.request_id, request_revision: question.revision, revision: 1, note: "The saved answer.", answer_ref: { attention_id: question.request_id, answer_revision: 1, question_ref: activeSource } };
  const shared = { attention_id: question.request_id, revision: 1, note: own.note, question_ref: activeSource, attention: activeIssue, context_ref: { item_id: "custom.current-copy", revision: 1 } };
  const original = { ...shared, attention_id: source.request_id, question_ref: source, attention: { ...activeIssue, attention_id: source.request_id, branch: source.branch, explanation_target: source } };
  const changes = [];
  const snapshot = { scope: "project.forward:method.current:P3", project: { project: { name: "Navigation fixture" } }, branches: [], runs: [], artifacts: {}, pending: { attention: [activeIssue], researcher_answers: [shared, original] }, readiness: {}, records: [], assessments: [], methods: [],
    progressRun: { project_id: "project.forward", run_id: source.run_id, phase: "P3", branch_id: activeSource.branch, state: "awaiting_user", researcher_pause: { pending_request: question, saved_answers: [own] } } };
  let stateIndex = 0;
  try {
    ui.dispatcher.current = { useState: value => [stateIndex++ === 0 ? snapshot : typeof value === "function" ? value() : value, () => {}], useRef: value => ({ current: value }), useEffect() {}, useLayoutEffect() {} };
    const tree = ui.ProjectView({ projectId: "project.forward", context: { phase: "P3", branch: "method.current" }, onContextChange: value => changes.push(value) });
    const dialogue = nodes(tree).find(node => node.type === ui.Dialogue);
    const preparation = nodes(tree).find(node => node.props.summaryContext);
    assert.ok(dialogue && preparation);
    assert.equal(dialogue.props.contextAnswers, snapshot.pending.researcher_answers);
    assert.equal(preparation.props.summaryContext.contextAnswers, snapshot.pending.researcher_answers);
    assert.deepEqual(dialogue.props.answers, [original], "The active pause's response has no duplicate question editor.");
    assert.deepEqual(preparation.props.summaryContext.answers, [original]);
    assert.equal(dialogue.props.onNavigate("P3", source), true);
    assert.deepEqual(changes, [{ phase: "P3", branch: "method.original" }]);
  } finally { ui.dispatcher.current = priorDispatcher; }
});

test("an active pause precedes ordinary questions in the Next line, visible phase cue and accessible name", () => {
  const priorDispatcher = ui.dispatcher.current;
  const ordinary = { attention_id: "ordinary", kind: "researcher_decision", phase: "P3", branch: "method.a", question: "Which future comparison is useful?" };
  const pause = { run_id: "run.pause", phase: "P3", branch_id: "method.a", state: "awaiting_user" };
  const makeTree = (state) => {
    const snapshot = { scope: "project.priority:method.a:P3", project: { project: { name: "Pause priority fixture" } },
      branches: [{ branch_id: "method.a" }], runs: [], artifacts: {}, pending: { attention: [ordinary], researcher_answers: [], runs_awaiting_direction: state === "awaiting_user" ? [pause] : [] },
      readiness: {}, records: [], assessments: [], methods: [{ method_id: "method.a", branch_id: "method.a", title: "Method A" }], progressRun: { ...pause, state } };
    let index = 0;
    ui.dispatcher.current = { useState: value => [index++ === 0 ? snapshot : typeof value === "function" ? value() : value, () => {}], useRef: value => ({ current: value }), useEffect() {}, useLayoutEffect() {} };
    return ui.ProjectView({ projectId: "project.priority", context: { phase: "P3", branch: "method.a" }, onContextChange() {} });
  };
  const text = tree => Array.isArray(tree) ? tree.map(text).join("") : tree?.props ? text(tree.props.children) : typeof tree === "string" || typeof tree === "number" ? String(tree) : "";
  try {
    const paused = nodes(makeTree("awaiting_user"));
    const next = paused.find(node => node.props.className === "project-next");
    assert.match(text(next), /Work is paused in Phase 3/);
    assert.match(text(next), /Unanswered questions: 1 in Phase 3/);
    assert.doesNotMatch(text(next), /Also waiting|needs your response/);
    const step = paused.find(node => node.props["data-phase-state"] === "waiting" && node.props["aria-current"] === "page");
    assert.match(step.props["aria-label"], /Work is paused, 1 unanswered question/);
    assert.match(text(step), /Paused/);
    assert.doesNotMatch(step.props["aria-label"], /question waiting/);
    const resumed = nodes(makeTree("published"));
    const later = resumed.find(node => node.props.className === "project-next");
    assert.match(text(later), /1 unanswered question in this phase/);
    assert.doesNotMatch(text(later), /Work is paused|waiting/);
  } finally { ui.dispatcher.current = priorDispatcher; }
});

const pauseFixture = (extra = {}) => {
  const source = { ...target, kind: "researcher_pause", project_id: "project.copy", phase: "P3", stage_id: "stage.copy" };
  const pending = { ...request, stage_id: source.stage_id, explanation_target: source, question: "What is measured per participant?", reason: "The unit determines the target variance.", scope: { kind: "project" } };
  const saved = { request_id: pending.request_id, request_revision: pending.revision, revision: 3, note: "The participant measure remains unknown.", origin: "unknown" };
  return { projectId: "project.copy", run: { ...run, phase: "P3", researcher_pause: { pending_request: pending, saved_answers: [saved], ...extra } } };
};

test("pause copy distinguishes no applicable answer, saved unknown, unsaved edits and blocked continuation", () => {
  const initial = pauseFixture({ saved_answers: [] });
  const waiting = ui.html(ui.create(ui.Pause, initial));
  assert.match(waiting, /Work is paused/); assert.match(waiting, /unit determines the target variance/);
  assert.match(waiting, /haven&#x27;t saved an answer/);
  const saved = ui.html(ui.create(ui.Pause, pauseFixture()));
  assert.match(saved, /Answer saved · still unknown/); assert.match(saved, /Choose Continue work to resume/);
  const wrong = pauseFixture(); wrong.run.researcher_pause.saved_answers[0].request_revision -= 1;
  assert.match(ui.html(ui.create(ui.Pause, wrong)), /haven&#x27;t saved an answer/);
  const fixture = pauseFixture(), pending = fixture.run.researcher_pause.pending_request;
  const key = `researcher-pause:${JSON.stringify([fixture.projectId, fixture.run.run_id, pending.request_id, pending.revision, pending.explanation_target.sha256])}`;
  ui.saveConversationDraft(key, { text: "A changed unsaved measurement.", origin: "researcher_reported" });
  try {
    const dirty = ui.html(ui.create(ui.Pause, fixture));
    assert.match(dirty, /Unsaved changes · work remains paused/);
    assert.doesNotMatch(dirty, /Choose Continue work to resume|haven&#x27;t saved an answer/);
    assert.match(dirty, /disabled=""[^>]*data-action="continue"/);
  } finally { ui.saveConversationDraft(key, null); }
  const blocked = ui.html(ui.create(ui.Pause, pauseFixture({ continuation_blocked: "The scientific target changed. Prepare a new request." })));
  assert.match(blocked, /scientific target changed/);
  assert.doesNotMatch(blocked, /Choose Continue work to resume/);
  assert.match(blocked, /disabled=""[^>]*data-action="continue"/);
});

test("pause continuation retains exact saved answer and the explicit frozen-input choice", async () => {
  const fixture = pauseFixture({ context_changes: [{ kind: "project_brief_changed" }] });
  const before = structuredClone(fixture), priorDispatcher = ui.dispatcher.current, priorContinue = ui.api.continueRun;
  const state = [], refs = [], calls = []; let stateIndex = 0, refIndex = 0;
  const draw = () => {
    stateIndex = 0; refIndex = 0;
    ui.dispatcher.current = { useId: () => "pause-test", useState(initial) { const index = stateIndex++; if (!(index in state)) state[index] = typeof initial === "function" ? initial() : initial; return [state[index], value => { state[index] = typeof value === "function" ? value(state[index]) : value; }]; }, useRef(initial) { const index = refIndex++; return refs[index] ||= { current: initial }; } };
    return ui.Pause(fixture);
  };
  try {
    ui.api.continueRun = async (...args) => calls.push(args);
    let tree = draw();
    let control = nodes(tree).find(node => node.props.children === "Continue work");
    assert.equal(control.props.disabled, true);
    await control.props.onClick(); assert.equal(calls.length, 0);
    // The context checkbox is the final checkbox, after the unknown-origin field.
    const checkboxes = nodes(tree).filter(node => node.type === "input" && node.props.type === "checkbox");
    assert.ok(checkboxes.length);
    checkboxes.at(-1).props.onChange({ target: { checked: true } });
    tree = draw(); control = nodes(tree).find(node => node.props.children === "Continue work");
    assert.equal(control.props.disabled, false);
    await control.props.onClick(); assert.equal(calls.length, 1);
    assert.deepEqual(calls[0].slice(0, 2), [fixture.projectId, fixture.run.run_id]);
    const payload = calls[0][2], pending = fixture.run.researcher_pause.pending_request;
    assert.equal(payload.request_id, pending.request_id); assert.equal(payload.expected_revision, pending.revision);
    assert.equal(payload.answer_revision, 3); assert.equal(payload.context_choice, "frozen");
    assert.equal(payload.action, "continue"); assert.equal(typeof payload.idempotency_key, "string");
    assert.deepEqual(fixture, before, "Rendering and continuing never replace the retained pause context.");
  } finally { ui.dispatcher.current = priorDispatcher; ui.api.continueRun = priorContinue; }
});

test("legacy pause saves display only the origin returned by the backend", async () => {
  const fixture = pauseFixture({ saved_answers: [] }); delete fixture.run.researcher_pause.pending_request.scope;
  const priorDispatcher = ui.dispatcher.current, priorSave = ui.api.saveDecisionAnswer;
  const state = [], refs = [], calls = []; let stateIndex = 0, refIndex = 0;
  const draw = () => {
    stateIndex = 0; refIndex = 0;
    ui.dispatcher.current = { useId: () => "pause-origin-test", useState(initial) { const index = stateIndex++; if (!(index in state)) state[index] = typeof initial === "function" ? initial() : initial; return [state[index], value => { state[index] = typeof value === "function" ? value(state[index]) : value; }]; }, useRef(initial) { const index = refIndex++; return refs[index] ||= { current: initial }; } };
    return ui.Pause(fixture);
  };
  const pending = fixture.run.researcher_pause.pending_request;
  const draftKey = `researcher-pause:${JSON.stringify([fixture.projectId, fixture.run.run_id, pending.request_id, pending.revision, pending.explanation_target.sha256])}`;
  try {
    ui.api.saveDecisionAnswer = async (...args) => { calls.push(args); return { saved_answer: { revision: 1, note: args[2].note, origin: "researcher_reported" } }; };
    nodes(draw()).find(node => node.props.children === "Not sure yet").props.onClick();
    await nodes(draw()).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(calls.length, 1); assert.equal(Object.hasOwn(calls[0][2], "origin"), false, "Legacy save payloads keep their original contract.");
    const after = nodes(draw());
    assert.ok(after.some(node => node.props.children === "Answer saved. Choose Continue work to resume."));
    assert.ok(!after.some(node => node.props.children === "Answer saved · still unknown"), "Draft intent never overrides the saved response's recorded origin.");
  } finally { ui.dispatcher.current = priorDispatcher; ui.api.saveDecisionAnswer = priorSave; ui.saveConversationDraft(draftKey, null); }
});
