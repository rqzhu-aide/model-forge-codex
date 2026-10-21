import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { empiricalDialogueItems } from "../src/empiricalProgress.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-retry-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {default as RunDetail} from '${src}/components/RunDetail.jsx'; export {default as ProjectView} from '${src}/components/ProjectView.jsx'; export {default as Workbench} from '${src}/components/EmpiricalWorkbench.jsx'; export {default as Dialogue} from '${src}/components/ResearcherDialogue.jsx'; export {EmpiricalSavedDecisions} from '${src}/components/EmpiricalProgress.jsx'; export {api} from '${src}/api.js'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher; export const html=renderToStaticMarkup;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const target = { kind: "p4_pause", phase: "P4", branch: "method.a", run_id: "run.paused", request_id: "decision.one", object_id: "decision.one", revision: 1, sha256: "a".repeat(64) };
const request = { request_id: "decision.one", revision: 1, question: "How should this evaluation continue?", explanation_target: target };
const attentionId = "pause.run.paused.decision.one";
const attention = { attention_id: attentionId, kind: "researcher_decision", phase: "P4", branch: "method.a", question: request.question, explanation_target: target };
const shared = { attention_id: attentionId, revision: 2, note: "Continue the retained operational check.", question_ref: target, attention };
const saved = { request_id: request.request_id, request_revision: 1, revision: 1, request, note: shared.note, applied_to: ["run.paused"], answer_ref: { attention_id: attentionId, answer_revision: 2, question_ref: target } };
const failed = { run_id: "run.paused", phase: "P4", branch_id: "method.a", mode: "p4.preliminary", state: "failed", terminal_reason: "Selected model is at capacity. Please try a different model.", provider_retry: { eligible: true, reason: null }, p4_progress: { saved_answers: [saved], ledger: [], budget: { used_seconds: 3, remaining_seconds: 597 } } };

test("only the exact pause answer owned by the evaluation editor leaves general dialogue", () => {
  const clinical = { attention_id: "clinical.one", phase: "P3", target_phase: "P4", branch: "method.a", kind: "researcher_decision", question: "Is result availability known?" };
  const inputs = { run: structuredClone(failed), attention: [attention, clinical], answers: [shared] };
  const before = structuredClone(inputs);
  assert.deepEqual(empiricalDialogueItems(inputs.run, inputs.attention, inputs.answers), { attention: [clinical], answers: [] });
  assert.deepEqual(inputs, before, "Recorded responses and question sources stay unchanged.");
  for (const change of [
    { question_ref: { ...target, run_id: "another.run" } },
    { question_ref: { ...target, branch: "method.b" } },
    { question_ref: { ...target, request_id: "another.request" } },
    { question_ref: { ...target, object_id: "another.object" } },
    { question_ref: { ...target, revision: 2 } },
    { question_ref: { ...target, sha256: "b".repeat(64) } },
    { revision: 3 }, { note: "A different retained response." }, { question_ref: null },
  ]) {
    const other = { ...shared, ...change };
    assert.deepEqual(empiricalDialogueItems(failed, [attention, clinical], [other]), { attention: [attention, clinical], answers: [other] });
  }
  const incomplete = structuredClone(failed); delete incomplete.p4_progress.saved_answers[0].answer_ref;
  assert.deepEqual(empiricalDialogueItems(incomplete, [attention], [shared]), { attention: [attention], answers: [shared] });
  const missingSource = structuredClone(failed); delete missingSource.p4_progress.saved_answers[0].request.explanation_target.sha256;
  assert.equal(empiricalDialogueItems(missingSource, [], [shared]).answers.length, 1);
  for (const other of [null, { ...failed, phase: "P3" }, { ...failed, p4_progress: null }]) assert.deepEqual(empiricalDialogueItems(other, [attention], [shared]), { attention: [attention], answers: [shared] });
});

test("an active exact pause owns its editor without hiding unanswered scientific questions", () => {
  const clinical = { ...attention, attention_id: "clinical.two", explanation_target: { ...target, kind: "phase_issue", request_id: undefined } };
  const waiting = { ...failed, state: "awaiting_user", p4_progress: { pause_request: request, saved_answers: [] } };
  assert.deepEqual(empiricalDialogueItems(waiting, [attention, clinical], []), { attention: [clinical], answers: [] });
  assert.deepEqual(empiricalDialogueItems({ ...waiting, state: "running" }, [attention, clinical], []), { attention: [attention, clinical], answers: [] });
});

// Exercise shipped effects and handlers without running child effects or a browser.
function mount(Component, initialProps) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let props = initialProps; let tree;
  const state = initial => { const index = cursor++; if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial }; return [slots[index].value, update => { const next = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; } }]; };
  const effect = (run, dependencies) => { const index = cursor++; const old = slots[index]; if (!old || !dependencies || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) { slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run }); } };
  const hooks = { useState: state, useEffect: effect, useLayoutEffect: effect, useRef: initial => { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; }, useId: () => { const index = cursor++; return (slots[index] ||= { value: `retry-${index}` }).value; } };
  const draw = () => { cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current; try { ui.dispatcher.current = hooks; tree = Component(props); } finally { ui.dispatcher.current = previous; } for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); } };
  return { get tree() { return tree; }, async settle() { for (let i = 0; i < 25; i++) { if (dirty) draw(); await new Promise(resolve => setImmediate(resolve)); if (!dirty) return tree; } throw new Error("Component did not settle."); }, unmount: () => { for (const slot of slots) slot?.cleanup?.(); } };
}
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree && typeof tree === "object" && tree.props ? [tree, ...nodes(tree.props.children)] : [];
const button = (tree, text) => nodes(tree).find(node => node.props.children === text && typeof node.props.onClick === "function");
const defer = () => { let resolve; let reject; const promise = new Promise((done, fail) => { resolve = done; reject = fail; }); return { promise, resolve, reject }; };
async function withHost(overrides, body) {
  const oldApi = Object.fromEntries(Object.keys(overrides).map(key => [key, ui.api[key]]));
  const oldGlobals = { window: globalThis.window, document: globalThis.document, EventSource: globalThis.EventSource };
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { addEventListener: noop, removeEventListener: noop };
  globalThis.EventSource = class { close() {} };
  Object.assign(ui.api, overrides);
  try { await body(); } finally { Object.assign(ui.api, oldApi); for (const [key, value] of Object.entries(oldGlobals)) if (value === undefined) delete globalThis[key]; else globalThis[key] = value; }
}

test("ProjectView retains one owned response and the carried study question", async () => {
  const clinical = { attention_id: "clinical.one", phase: "P3", target_phase: "P4", branch: "method.a", kind: "researcher_decision", question: "Is result availability known?" };
  await withHost({ project: async () => ({ project: {}, problem_context: { revision: 1, items: [] } }), branches: async () => ({ branches: [] }), listRuns: async () => ({ runs: [failed] }), run: async () => failed, artifacts: async () => ({}), decisionsPending: async () => ({ attention: [clinical], researcher_answers: [shared] }), readiness: async () => ({}), records: async () => ({ records: [] }), assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [] }) }, async () => {
    const fixture = mount(ui.ProjectView, { projectId: "p", context: { phase: "P4", branch: "method.a" }, onContextChange: noop });
    try {
      await fixture.settle();
      const workbench = nodes(fixture.tree).find(node => node.type === ui.Workbench);
      const dialogue = workbench.props.issues;
      assert.equal(dialogue.type, ui.Dialogue); assert.deepEqual(dialogue.props.answers, []); assert.deepEqual(dialogue.props.attention, [clinical]);
      assert.equal(dialogue.props.savedPauseCount, 1);
      assert.ok(nodes(dialogue.props.pause).some(node => node.type === ui.EmpiricalSavedDecisions));
      const html = ui.html(dialogue); assert.equal((html.match(/Continue the retained operational check/g) || []).length, 1);
      assert.match(html, /Is result availability known/); assert.match(html, /This response was used by the evaluation/);
      assert.doesNotMatch(html, /Saved for future work\. Work already underway/);
    } finally { fixture.unmount(); }
  });
});

test("eligible provider interruption stays visible and retries only an explicit locked click", async () => {
  let value = structuredClone(failed); let reads = 0; const calls = []; const next = defer();
  await withHost({ run: async () => { reads++; return value; }, correctionPreview: async () => ({ eligible: false, reason: "Correction is not eligible.", attempts_remaining: 0 }), retryProvider: async (...args) => { calls.push(args); await next.promise; value = { ...value, state: "running", provider_retry: { eligible: false, reason: null } }; return { run_id: value.run_id, state: value.state }; }, startRun: () => { throw new Error("Unexpected new run"); }, continueRun: () => { throw new Error("Unexpected continuation"); } }, async () => {
    const fixture = mount(ui.RunDetail, { projectId: "p", runId: failed.run_id, onBack: noop });
    try {
      await fixture.settle(); const html = ui.html(fixture.tree).split('<details class="drawer"')[0];
      assert.match(html, /Selected model is at capacity/); assert.match(html, /Saved work and your evaluation direction are retained/);
      assert.doesNotMatch(html, /Correction is not eligible|correction budget.*spent|Authorize correction/);
      assert.equal(calls.length, 0, "Loading and rendering do not retry work.");
      const retry = button(fixture.tree, "Retry interrupted step"); assert.ok(retry); assert.equal(retry.props.disabled, false);
      const first = retry.props.onClick(); const repeated = retry.props.onClick(); await fixture.settle();
      assert.equal(calls.length, 1); assert.equal(button(fixture.tree, "Requesting retry…").props.disabled, true);
      next.resolve(); await Promise.all([first, repeated]); await fixture.settle();
      assert.deepEqual(calls, [["p", failed.run_id]]); assert.ok(reads >= 2, "Successful retry refreshes host state.");
      assert.equal(button(fixture.tree, "Retry interrupted step"), undefined);
    } finally { fixture.unmount(); }
  });
});

test("a rejected retry reports the error and refreshes eligibility without another provider call", async () => {
  let value = structuredClone(failed); let calls = 0; let reads = 0;
  await withHost({ run: async () => { reads++; return value; }, correctionPreview: async () => ({ eligible: false, reason: "A scientific correction is unavailable.", attempts_remaining: 1 }), retryProvider: async () => { calls++; value = { ...value, provider_retry: { eligible: false, reason: "Captured inputs changed." } }; throw new Error("Captured inputs changed."); } }, async () => {
    const fixture = mount(ui.RunDetail, { projectId: "p", runId: failed.run_id, onBack: noop });
    try { await fixture.settle(); await button(fixture.tree, "Retry interrupted step").props.onClick(); await fixture.settle(); assert.equal(calls, 1); assert.ok(reads >= 2); assert.match(ui.html(fixture.tree), /role="alert"[^]*Captured inputs changed/); assert.equal(button(fixture.tree, "Retry interrupted step"), undefined); }
    finally { fixture.unmount(); }
  });
});

test("capacity wording alone never enables retry, and ordinary correction stays available", async () => {
  for (const provider_retry of [undefined, { eligible: false, reason: "Not a resumable P4 step.", failure_code: null }, { eligible: false, reason: "A different failure.", failure_code: "scientific.validation" }]) {
    await withHost({ run: async () => ({ ...failed, provider_retry }), correctionPreview: async () => ({ eligible: true, attempts_remaining: 2 }) }, async () => {
      const fixture = mount(ui.RunDetail, { projectId: "p", runId: failed.run_id, onBack: noop });
      try { await fixture.settle(); assert.equal(button(fixture.tree, "Retry interrupted step"), undefined); const html = ui.html(fixture.tree).split('<details class="drawer"')[0]; assert.match(html, /Selected model is at capacity/); assert.match(html, /Authorize correction/); }
      finally { fixture.unmount(); }
    });
  }
});

test("an identified capacity interruption shows its exact retry blocker rather than scientific correction advice", async () => {
  for (const reason of ["Captured research context changed. Prepare a new linked run.", "Member settings changed. Restore the captured settings before retrying.", "Another step is pending. Inspect its recorded outcome first."]) {
    await withHost({ run: async () => ({ ...failed, provider_retry: { eligible: false, reason, failure_code: "provider.capacity" } }), correctionPreview: async () => ({ eligible: false, reason: "This failure is not eligible for scientific correction.", attempts_remaining: 0 }) }, async () => {
      const fixture = mount(ui.RunDetail, { projectId: "p", runId: failed.run_id, onBack: noop });
      try {
        await fixture.settle(); const html = ui.html(fixture.tree).split('<details class="drawer"')[0];
        assert.ok(html.includes(reason)); assert.match(html, /Selected model is at capacity/);
        assert.equal(button(fixture.tree, "Retry interrupted step"), undefined);
        assert.doesNotMatch(html, /scientific correction|correction budget.*spent|Authorize correction/);
      } finally { fixture.unmount(); }
    });
  }
});

test("provider retry sends the exact existing run a POST without a body", async () => {
  const previous = globalThis.fetch; const requests = [];
  globalThis.fetch = async (url, options) => { requests.push({ url, options }); return { ok: true, status: 200, json: async () => ({ run_id: "run.exact", state: "requested" }) }; };
  try { assert.deepEqual(await ui.api.retryProvider("project.exact", "run.exact"), { run_id: "run.exact", state: "requested" }); assert.equal(requests.length, 1); assert.equal(requests[0].url, "/api/v1/projects/project.exact/runs/run.exact/retry-provider"); assert.equal(requests[0].options.method, "POST"); assert.equal(requests[0].options.body, undefined); }
  finally { globalThis.fetch = previous; }
});
