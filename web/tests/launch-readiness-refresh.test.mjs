import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { normalizeNavigation, restoreReadingPosition } from "../src/readingPosition.js";
import { beginRunReturn, captureRunOrigin } from "../src/runReturnFocus.js";
import { methodStartingPoint, methodStartingPointSource } from "../src/methodSeed.js";
import { furtherWorkKey } from "../src/phaseWorkflow.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-launch-refresh-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {default as App} from '${src}/App.jsx'; export {default as LaunchRun} from '${src}/components/LaunchRun.jsx'; export {default as ProjectView} from '${src}/components/ProjectView.jsx'; export {default as FurtherWorkCard} from '${src}/components/FurtherWorkCard.jsx'; export {default as MethodProposals} from '${src}/components/MethodProposals.jsx'; export {api} from '${src}/api.js'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};

// Exercise the shipped component's hooks, effect dependencies and event handlers.
// Child elements remain React elements: this does not claim browser/DOM coverage.
function mount(Component, initialProps) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let props = initialProps; let tree;
  const state = (initial) => {
    const index = cursor++;
    if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial };
    return [slots[index].value, (update) => {
      const next = typeof update === "function" ? update(slots[index].value) : update;
      if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; }
    }];
  };
  const effect = (run, dependencies) => {
    const index = cursor++; const old = slots[index];
    if (!old || !dependencies || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) {
      slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run });
    }
  };
  const hooks = { useState: state, useEffect: effect, useLayoutEffect: effect,
    useCallback: (callback, dependencies) => {
      const index = cursor++; const old = slots[index];
      if (!old || !dependencies || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) slots[index] = { value: callback, dependencies };
      return slots[index].value;
    },
    useRef: (initial) => { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; },
    useId: () => { const index = cursor++; return (slots[index] ||= { value: `fixture-${index}` }).value; } };
  const draw = () => {
    cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current;
    try { ui.dispatcher.current = hooks; tree = Component(props); }
    finally { ui.dispatcher.current = previous; }
    for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); }
  };
  return { get tree() { return tree; }, update: (changes) => { props = { ...props, ...changes }; dirty = true; },
    async settle() {
      for (let iteration = 0; iteration < 25; iteration++) {
        if (dirty) draw();
        await new Promise((resolve) => setImmediate(resolve));
        if (!dirty) return tree;
      }
      throw new Error("The component did not settle within the bounded fixture.");
    },
    unmount: () => { for (const slot of slots) slot?.cleanup?.(); } };
}

function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return tree && typeof tree === "object" && tree.props ? [tree, ...nodes(tree.props.children)] : [];
}
const find = (tree, predicate) => nodes(tree).find(predicate);
const form = (fixture) => find(fixture.tree, (node) => node.type === "form");
const submit = (fixture) => find(fixture.tree, (node) => node.props.type === "submit");
const refresh = (fixture) => find(fixture.tree, (node) => node.props.children === "Refresh research inputs");
const defer = () => { let resolve; let reject; const promise = new Promise((done, fail) => { resolve = done; reject = fail; }); return { promise, resolve, reject }; };
const readiness = (mode, sha256, progressive = false) => ({ modes: [{ mode, ready: true, progressive_evaluation: progressive, basis: { sha256 }, budget_seconds: 600 }] });
const event = { preventDefault: noop };

test("project refresh cancels abandoned scopes and pauses hidden polling without losing the next visible refresh", async () => {
  const originals = { window: globalThis.window, document: globalThis.document, setInterval: globalThis.setInterval, clearInterval: globalThis.clearInterval };
  const timers = new Set(); const listeners = new Map(); const requests = [];
  const listen = (type, callback) => listeners.set(type, callback);
  const unlisten = (type, callback) => { if (listeners.get(type) === callback) listeners.delete(type); };
  globalThis.window = { addEventListener: listen, removeEventListener: unlisten };
  globalThis.document = { hidden: false, addEventListener: listen, removeEventListener: unlisten };
  globalThis.setInterval = (callback) => { timers.add(callback); return callback; };
  globalThis.clearInterval = (callback) => timers.delete(callback);
  const record = (name, result) => async (...args) => { requests.push({ name, signal: args.at(-1).signal }); return result; };
  let delayed = true;
  try {
    await withApi({
      project: async (...args) => {
        const signal = args.at(-1).signal; requests.push({ name: "project", signal });
        if (!delayed) return { project: {} };
        return new Promise((resolve, reject) => signal.addEventListener("abort", () => reject(new DOMException("Abandoned reader", "AbortError")), { once: true }));
      },
      branches: record("branches", { branches: [] }), listRuns: record("runs", { runs: [] }),
      artifacts: record("artifacts", { research_bases: [{ branch: "trunk", phase: "P1", research_setting: { research_goal_markdown: "Existing study goal." } }] }), decisionsPending: record("questions", {}),
      readiness: record("readiness", {}), records: record("records", { records: [] }),
      assessments: record("assessments", { assessments: [] }), methods: record("methods", { methods: [] }),
    }, async () => {
      const project = mount(ui.ProjectView, { projectId: "project.polling", context: { phase: "P1", branch: "trunk" }, onContextChange: noop });
      try {
        await project.settle();
        assert.equal(requests.length, 9);
        const abandoned = requests[0].signal;
        assert.ok(requests.every(request => request.signal === abandoned));
        for (const poll of timers) poll(); await project.settle();
        assert.equal(requests.length, 9, "An unfinished refresh cannot overlap its own poll.");
        delayed = false;
        project.update({ context: { phase: "P2", branch: "trunk" } }); await project.settle();
        assert.equal(abandoned.aborted, true);
        assert.equal(requests.length, 18);
        assert.equal(requests.at(-1).signal.aborted, false);
        globalThis.document.hidden = true;
        for (const poll of timers) poll(); listeners.get("visibilitychange")(); await project.settle();
        assert.equal(requests.length, 18, "Hidden tabs do not keep rebuilding the research view.");
        globalThis.document.hidden = false;
        listeners.get("visibilitychange")(); await project.settle();
        assert.equal(requests.length, 27, "Returning to the tab refreshes its current scope.");
        assert.ok(!nodes(project.tree).some(node => node.props.role === "alert" && String(node.props.children).includes("Abandoned reader")));
        const lastSignal = requests.at(-1).signal;
        project.unmount();
        assert.equal(lastSignal.aborted, true);
        assert.equal(timers.size, 0);
        assert.equal(listeners.size, 0);
      } finally { project.unmount(); }
    });
  } finally { Object.assign(globalThis, originals); }
});

async function withApi(overrides, run) {
  const previous = Object.fromEntries(Object.keys(overrides).map((key) => [key, ui.api[key]]));
  Object.assign(ui.api, overrides);
  try { await run(); } finally { Object.assign(ui.api, previous); }
}

test("P4 issue preparation reuses the unified editor and keeps the draft, settings and exact source", async () => {
  const previousWindow = globalThis.window; const previousDocument = globalThis.document;
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { addEventListener: noop, removeEventListener: noop };
  const identity = { stable_id: "method.p4-prepare", version: 1, definition_sha256: "a".repeat(64) };
  const source = { branch: identity.stable_id, phase: "P3", family: "attention_items", generation_id: "attention.p4-prepare", sha256: "b".repeat(64), run_id: "run.theory", package_id: "package.theory", kind: "phase_issue", object_id: "task.design", entry_pointer: "/items/2" };
  const issue = { title: "Check the question design", explanation_target: source };
  const issueBefore = JSON.stringify(issue);
  const origin = { fixture: "P4 prepare issue control" }; let starts = 0;
  try {
    await withApi({ project: async () => ({ project: {} }), branches: async () => ({ branches: [] }), listRuns: async () => ({ runs: [] }), artifacts: async () => ({}), decisionsPending: async () => ({}), readiness: async () => ({}), records: async () => ({ records: [] }), assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [{ method_id: identity.stable_id, branch_id: identity.stable_id, identity }] }), phasePreparation: async () => ({ instructions: "Saved directions.", input_ids: ["input.saved"] }), startRun: async () => { starts++; throw new Error("Preparation must not start work."); } }, async () => {
      const project = mount(ui.ProjectView, { projectId: "project.p4-prepare", context: { phase: "P4", branch: identity.stable_id }, onContextChange: noop }); let editor;
      const workspace = () => find(project.tree, node => node.props.furtherWork?.type === ui.FurtherWorkCard);
      const launch = () => find(editor.tree, node => node.type === ui.LaunchRun);
      try {
        await project.settle(); const inner = ui.FurtherWorkCard(workspace().props.furtherWork.props); editor = mount(inner.type, inner.props); await editor.settle();
        launch().props.onInstructionsChange("My existing diagnostic draft."); launch().props.onModeChange("p4.comprehensive"); launch().props.onExperimentBudgetChange("720"); launch().props.onInputIdsChange(["input.draft"]); await editor.settle();
        workspace().props.issues.props.onPrepare(issue, origin); await project.settle();
        assert.equal(find(project.tree, node => node.type === ui.LaunchRun), undefined, "The issue action does not create a launch dialog.");
        editor.update(workspace().props.furtherWork.props); await editor.settle(); await project.settle();
        assert.equal(launch().props.instructions, "My existing diagnostic draft.\n\nInvestigate this recorded issue: Check the question design");
        assert.deepEqual(launch().props.request.context_refs, [source]); assert.equal(launch().props.mode, "p4.comprehensive"); assert.equal(launch().props.experimentBudget, "720"); assert.deepEqual(launch().props.inputIds, ["input.draft"]);
        const summary = find(editor.tree, node => node.type.name === "PhaseInputSummary");
        assert.deepEqual(summary.props.navigationRequest, { origin, returnLabel: "Back to research question" }, "The shared navigation session owns reading position and Back focus.");
        assert.equal(workspace().props.furtherWork.props.preparedIssue, null); assert.equal(starts, 0);
        assert.equal(JSON.stringify(issue), issueBefore);
      } finally { editor?.unmount(); project.unmount(); }
    });
  } finally { globalThis.window = previousWindow; globalThis.document = previousDocument; }
});

test("a P4 issue awaiting saved instructions does not cross a phase or method scope", async () => {
  const previousWindow = globalThis.window; const previousDocument = globalThis.document;
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { addEventListener: noop, removeEventListener: noop };
  const pending = defer(); const issue = { title: "Only the original P4 scope", explanation_target: { branch: "method.original", phase: "P3", family: "attention_items", generation_id: "attention.late", sha256: "c".repeat(64), run_id: "run.late", package_id: "package.late", kind: "phase_issue", object_id: "task.late", entry_pointer: "/items/1" } };
  try {
    await withApi({ project: async () => ({ project: {} }), branches: async () => ({ branches: [] }), listRuns: async () => ({ runs: [] }), artifacts: async () => ({}), decisionsPending: async () => ({}), readiness: async () => ({}), records: async () => ({ records: [] }), assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [] }), phasePreparation: async () => pending.promise }, async () => {
      const project = mount(ui.ProjectView, { projectId: "project.p4-late-prepare", context: { phase: "P4", branch: "method.original" }, onContextChange: noop }); let editor;
      const workspace = () => find(project.tree, node => node.props.furtherWork?.type === ui.FurtherWorkCard);
      try {
        await project.settle(); workspace().props.issues.props.onPrepare(issue, { fixture: "old origin" }); await project.settle();
        const inner = ui.FurtherWorkCard(workspace().props.furtherWork.props); editor = mount(inner.type, inner.props); await editor.settle();
        assert.equal(find(editor.tree, node => node.type === ui.LaunchRun), undefined);
        editor.unmount(); editor = null; project.update({ context: { phase: "P3", branch: "method.original" } }); await project.settle();
        pending.resolve({ instructions: "Late saved instructions.", input_ids: [] }); await project.settle();
        for (const branch of ["method.other", "method.original"]) {
          project.update({ context: { phase: "P4", branch } }); await project.settle();
          assert.equal(workspace().props.furtherWork.props.preparedIssue, null, branch);
          const next = ui.FurtherWorkCard(workspace().props.furtherWork.props); editor = mount(next.type, next.props); await editor.settle();
          const launch = find(editor.tree, node => node.type === ui.LaunchRun);
          assert.equal(launch.props.instructions, "Late saved instructions."); assert.deepEqual(launch.props.request.context_refs, []);
          assert.equal(find(editor.tree, node => node.type.name === "PhaseInputSummary").props.navigationRequest, null);
          editor.unmount(); editor = null;
        }
      } finally { editor?.unmount(); project.unmount(); }
    });
  } finally { globalThis.window = previousWindow; globalThis.document = previousDocument; }
});

test("adopted workflow refreshes the mounted form while preserving typed instructions, mode and budget", async () => {
  const checks = []; const starts = []; const started = []; const next = defer(); let adopted = false;
  const evaluationReadiness = (basis) => ({ modes: ["p4.preliminary", "p4.comprehensive"].map((mode) => readiness(mode, basis, true).modes[0]) });
  await withApi({ readiness: async (project, branch, phase, mode) => { checks.push({ project, branch, phase, mode }); return adopted ? next.promise : evaluationReadiness("old-basis"); }, startRun: async (_, payload) => { starts.push(payload); return { run_id: "run.new", state: "requested" }; } }, async () => {
    const fixture = mount(ui.LaunchRun, { projectId: "project.refresh", workflowRevision: "1.18.0", embedded: true, request: { phase: "P4", branch: "method.a", mode: "p4.preliminary" }, onStarted: (run) => started.push(run) });
    try {
      await fixture.settle();
      find(fixture.tree, (node) => node.type === "textarea").props.onChange({ target: { value: "Keep the visit-process uncertainty explicit." } });
      find(fixture.tree, (node) => node.type === "input" && node.props.type === "number").props.onChange({ target: { value: "900" } });
      find(fixture.tree, (node) => node.type === "input" && node.props.value === "p4.comprehensive").props.onChange();
      await fixture.settle(); assert.equal(checks.length, 2);
      adopted = true; fixture.update({ workflowRevision: "1.19.0" }); await fixture.settle();
      assert.equal(checks.length, 3); assert.equal(checks[2].mode, "p4.comprehensive");
      assert.equal(find(fixture.tree, (node) => node.type === "input" && node.props.value === "p4.comprehensive").props.checked, true);
      assert.equal(submit(fixture).props.disabled, true);
      assert.equal(find(fixture.tree, (node) => node.type === "textarea").props.value, "Keep the visit-process uncertainty explicit.");
      assert.equal(find(fixture.tree, (node) => node.type === "input" && node.props.type === "number").props.value, "900");
      await form(fixture).props.onSubmit(event); assert.equal(starts.length, 0, "Refreshing inputs must not start work.");
      next.resolve(evaluationReadiness("adopted-basis")); await fixture.settle();
      assert.equal(submit(fixture).props.disabled, false);
      fixture.update({ workflowRevision: "1.19.0" }); await fixture.settle(); assert.equal(checks.length, 3, "Unchanged polling does not refresh or reset the form.");
      await form(fixture).props.onSubmit(event); await fixture.settle();
      assert.equal(starts.length, 1); assert.equal(started.length, 1);
      assert.equal(starts[0].basis_sha256, "adopted-basis"); assert.equal(starts[0].mode, "p4.comprehensive");
      assert.equal(starts[0].instructions, "Keep the visit-process uncertainty explicit."); assert.equal(starts[0].budget_seconds, 900);
    } finally { fixture.unmount(); }
  });
});

test("published theory refreshes the mounted revision form without losing the researcher's draft", async () => {
  let published = false; let checks = 0; const starts = []; const next = defer();
  const theoryReadiness = () => ({ modes: [
    { mode: "p3.theory_establishment", ready: true, basis: { sha256: published ? "published-basis" : "initial-basis" } },
    { mode: "p3.theory_revision", ready: published, reasons: published ? [] : ["A complete current theory package is required for this action"], basis: { sha256: published ? "published-basis" : "initial-basis" } },
  ] });
  await withApi({ readiness: async () => { checks++; return published ? next.promise : theoryReadiness(); }, startRun: async (_, payload) => { starts.push(payload); return { run_id: "run.revision", state: "requested" }; } }, async () => {
    const fixture = mount(ui.LaunchRun, { projectId: "project.theory", workflowRevision: "1.19.0", readinessRevision: "before-publication", embedded: true, request: { phase: "P3", branch: "method.a", mode: "p3.theory_revision" }, onStarted: noop });
    try {
      await fixture.settle();
      find(fixture.tree, (node) => node.type === "textarea").props.onChange({ target: { value: "Keep the visit-process qualification explicit." } });
      await fixture.settle(); assert.equal(submit(fixture).props.disabled, true);
      published = true; fixture.update({ readinessRevision: "after-publication" }); await fixture.settle();
      assert.equal(checks, 2); assert.equal(submit(fixture).props.disabled, true);
      assert.equal(find(fixture.tree, (node) => node.type === "textarea").props.value, "Keep the visit-process qualification explicit.");
      assert.equal(find(fixture.tree, (node) => node.props.value === "p3.theory_revision").props.checked, true);
      await form(fixture).props.onSubmit(event); assert.equal(starts.length, 0, "Refreshing publication inputs cannot start work.");
      next.resolve(theoryReadiness()); await fixture.settle();
      assert.equal(submit(fixture).props.disabled, false);
      assert.ok(!nodes(fixture.tree).some((node) => node.props.children === "Complete theory development for the current model before requesting this work."));
      fixture.update({ readinessRevision: "after-publication" }); await fixture.settle();
      assert.equal(checks, 2, "An unchanged poll must not refresh the mounted form.");
      await form(fixture).props.onSubmit(event); await fixture.settle();
      assert.equal(starts.length, 1); assert.equal(starts[0].basis_sha256, "published-basis");
      assert.equal(starts[0].mode, "p3.theory_revision"); assert.equal(starts[0].instructions, "Keep the visit-process qualification explicit.");
    } finally { fixture.unmount(); }
  });
});

test("a rejected launch cannot repeat until explicit input refresh and uses the refreshed basis", async () => {
  for (const message of ["The research basis is stale", "A launch prerequisite changed"]) {
    let checks = 0; const starts = []; const started = [];
    await withApi({ readiness: async () => readiness("p2.full_catalog", ++checks === 1 ? "old-basis" : "refreshed-basis"), startRun: async (_, payload) => { starts.push(payload); if (starts.length === 1) throw new Error(message); return { run_id: "run.refreshed", state: "requested" }; } }, async () => {
      const fixture = mount(ui.LaunchRun, { projectId: "project.rejection", workflowRevision: "1.19.0", embedded: true, request: { phase: "P2", branch: "trunk", instructions: "No patient data are available." }, onStarted: (run) => started.push(run) });
      try {
        await fixture.settle(); await form(fixture).props.onSubmit(event); await fixture.settle();
        assert.equal(starts.length, 1); assert.equal(checks, 1); assert.equal(started.length, 0);
        assert.equal(submit(fixture).props.disabled, true); assert.ok(refresh(fixture));
        const editor = find(fixture.tree, (node) => node.props.value === "No patient data are available." && typeof node.props.onChange === "function");
        assert.ok(editor, "The instructions survive the rejected launch.");
        await form(fixture).props.onSubmit(event); await fixture.settle();
        assert.equal(starts.length, 1, "Submitting again cannot reuse rejected readiness."); assert.equal(checks, 1, "No automatic retry is performed.");
        refresh(fixture).props.onClick(); await fixture.settle(); assert.equal(checks, 2); assert.equal(starts.length, 1);
        assert.equal(submit(fixture).props.disabled, false); assert.equal(refresh(fixture), undefined);
        await form(fixture).props.onSubmit(event); await fixture.settle();
        assert.equal(starts.length, 2); assert.equal(started.length, 1);
        assert.equal(starts[0].basis_sha256, "old-basis"); assert.equal(starts[1].basis_sha256, "refreshed-basis");
        assert.equal(starts[1].instructions, "No patient data are available."); assert.equal(starts[1].mode, "p2.full_catalog");
      } finally { fixture.unmount(); }
    });
  }
});

test("ProjectView sends catalog and changed readiness through both mounted launch paths", async () => {
  const previousWindow = globalThis.window; const previousDocument = globalThis.document;
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { addEventListener: noop, removeEventListener: noop };
  let version = "1.18.0"; let basis = "initial-basis"; let phaseRuns = [];
  await withApi({ project: async () => ({ project: { project_id: "project.wiring", name: "Wiring fixture" }, catalog: { version }, catalog_status: { version: "wrong-field" } }), branches: async () => ({ branches: [] }), listRuns: async () => ({ runs: phaseRuns }), artifacts: async () => ({}), decisionsPending: async () => ({}), readiness: async () => readiness("p2.full_catalog", basis), records: async () => ({ records: [] }), assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [] }), phasePreparation: async () => ({ instructions: "Saved lead instructions" }) }, async () => {
    const project = mount(ui.ProjectView, { projectId: "project.wiring", context: { phase: "P2", branch: "trunk" }, onContextChange: noop, onOpenRun: noop });
    let further;
    try {
      await project.settle(); let methods = find(project.tree, (node) => node.type === ui.MethodProposals);
      const card = methods.props.furtherWork({}); assert.equal(card.props.workflowRevision, "1.18.0");
      assert.equal(card.props.hasRun, false);
      const initialRevision = card.props.readinessRevision; assert.ok(initialRevision);
      const inner = ui.FurtherWorkCard(card.props); further = mount(inner.type, inner.props); await further.settle();
      let embedded = find(further.tree, (node) => node.type === ui.LaunchRun); assert.equal(embedded.props.workflowRevision, "1.18.0");
      assert.equal(embedded.props.readinessRevision, initialRevision);
      embedded.props.onInstructionsChange("Unsaved researcher direction"); await further.settle();
      methods.props.issues({}).props.onPrepare(); await project.settle();
      assert.equal(find(project.tree, (node) => node.type === ui.LaunchRun).props.workflowRevision, "1.18.0");
      assert.equal(find(project.tree, (node) => node.type === ui.LaunchRun).props.readinessRevision, initialRevision);
      version = "1.19.0"; methods.props.issues({}).props.onSaved(); await project.settle();
      methods = find(project.tree, (node) => node.type === ui.MethodProposals);
      const adoptedCard = methods.props.furtherWork({}); assert.equal(adoptedCard.props.workflowRevision, "1.19.0");
      assert.equal(adoptedCard.props.readinessRevision, initialRevision, "Equal fresh readiness objects keep a stable revision.");
      const adoptedInner = ui.FurtherWorkCard(adoptedCard.props); assert.equal(adoptedInner.key, inner.key, "Adoption preserves the preparation component's identity.");
      further.update(adoptedInner.props); await further.settle();
      embedded = find(further.tree, (node) => node.type === ui.LaunchRun);
      assert.equal(embedded.props.workflowRevision, "1.19.0"); assert.equal(embedded.props.instructions, "Unsaved researcher direction");
      assert.equal(find(project.tree, (node) => node.type === ui.LaunchRun).props.workflowRevision, "1.19.0");
      basis = "published-basis"; phaseRuns = [{ run_id: "first.proposal", phase: "P2", branch_id: "trunk", state: "published" }];
      methods.props.issues({}).props.onSaved(); await project.settle();
      methods = find(project.tree, (node) => node.type === ui.MethodProposals);
      const publishedCard = methods.props.furtherWork({}); assert.notEqual(publishedCard.props.readinessRevision, initialRevision);
      assert.equal(publishedCard.props.hasRun, true, "The first scientific run changes the existing card into revision mode.");
      const publishedInner = ui.FurtherWorkCard(publishedCard.props); assert.equal(publishedInner.key, inner.key, "Publication preserves the draft component's identity.");
      further.update(publishedInner.props); await further.settle();
      embedded = find(further.tree, (node) => node.type === ui.LaunchRun);
      assert.equal(embedded.props.readinessRevision, publishedCard.props.readinessRevision);
      assert.equal(embedded.props.instructions, "Unsaved researcher direction");
      assert.equal(find(further.tree, node => node.type.name === "PhaseInputSummary").props.showSummary, true);
      assert.equal(find(further.tree, node => node.type === "details" && node.props["data-reading-anchor"] === "further-work").props.open, true, "The live lifecycle change does not collapse the existing form.");
      assert.equal(find(project.tree, (node) => node.type === ui.LaunchRun).props.readinessRevision, publishedCard.props.readinessRevision);
    } finally { further?.unmount(); project.unmount(); }
  });
  if (previousWindow === undefined) delete globalThis.window; else globalThis.window = previousWindow;
  if (previousDocument === undefined) delete globalThis.document; else globalThis.document = previousDocument;
});

test("cross-phase P2 modals poll their exact target through provider retry completion and restore the view scope", async () => {
  const names = ["window", "document", "setInterval", "clearInterval"];
  const previous = Object.fromEntries(names.map((name) => [name, globalThis[name]]));
  const method = { method_id: "method.target", branch_id: "method.target", title: "Target model", identity: { stable_id: "method.target", version: 1 } };
  try {
    globalThis.window = { addEventListener: noop, removeEventListener: noop };
    globalThis.document = { hidden: false, addEventListener: noop, removeEventListener: noop };
    for (const phase of ["P3", "P4"]) {
      let poll; let published = false; let runState = "failed"; const checks = []; const starts = [];
      globalThis.setInterval = (read) => { poll = read; return 1; }; globalThis.clearInterval = noop;
      const targetReadiness = () => phase === "P3"
        ? { modes: [{ mode: "p3.theory_revision", ready: published, reasons: published ? [] : ["A complete current theory package is required for this action"], basis: { sha256: published ? "target-published" : "target-before" } }] }
        : { modes: ["p4.preliminary", "p4.comprehensive"].map((mode) => readiness(mode, published ? "target-published" : "target-before", true).modes[0]) };
      await withApi({ project: async () => ({ project: { name: "Cross-phase fixture" }, catalog: { version: "1.19.0" } }), branches: async () => ({ branches: [] }), listRuns: async () => ({ runs: [{ run_id: "run.provider-retry", phase, branch_id: method.branch_id, mode: phase === "P3" ? "p3.theory_establishment" : "p4.preliminary", state: runState }] }), artifacts: async () => ({}), decisionsPending: async () => ({}), readiness: async (_, branch, targetPhase, mode) => { checks.push({ branch, phase: targetPhase, mode }); return targetPhase === "P2" ? readiness("p2.full_catalog", "unchanged-p2-basis") : targetReadiness(); }, records: async () => ({ records: [] }), assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [method] }), activateMethod: async () => ({ branch_id: method.branch_id }), startRun: async (_, payload) => { starts.push(payload); return { run_id: "run.next", phase, branch_id: method.branch_id, state: "requested" }; } }, async () => {
        const project = mount(ui.ProjectView, { projectId: "project.cross-phase", context: { phase: "P2", branch: "trunk" }, onContextChange: noop, onOpenRun: noop });
        let launch;
        try {
          await project.settle(); assert.deepEqual(checks.at(-1), { branch: "trunk", phase: "P2", mode: undefined });
          const methods = find(project.tree, (node) => node.type === ui.MethodProposals);
          await methods.props.onContinue(method, phase, { prepareRun: true }); await project.settle();
          assert.deepEqual(checks.at(-1), { branch: method.branch_id, phase, mode: undefined }, "The existing parent poll must follow the modal target before the child mounts.");
          let modal = find(project.tree, (node) => node.type === ui.LaunchRun); const exactRequest = modal.props.request;
          launch = mount(ui.LaunchRun, modal.props); await launch.settle();
          find(launch.tree, (node) => node.type === "textarea").props.onChange({ target: { value: "Keep my cross-phase draft." } });
          if (phase === "P4") {
            find(launch.tree, (node) => node.props.value === "p4.comprehensive").props.onChange();
            await launch.settle();
            find(launch.tree, (node) => node.type === "input" && node.props.type === "number").props.onChange({ target: { value: "900" } });
          }
          await launch.settle(); const beforePublication = modal.props.readinessRevision; const beforeUnchangedPoll = checks.length;
          await poll(); await project.settle(); modal = find(project.tree, (node) => node.type === ui.LaunchRun);
          launch.update(modal.props); await launch.settle();
          assert.equal(checks.length, beforeUnchangedPoll + 1, "An unchanged poll does not trigger another child readiness read.");
          runState = "requested"; await poll(); await project.settle();
          modal = find(project.tree, (node) => node.type === ui.LaunchRun); launch.update(modal.props); await launch.settle();
          assert.equal(submit(launch).props.disabled, true, "The same retried run reserves the target phase.");
          published = true; runState = "published"; await poll(); await project.settle();
          modal = find(project.tree, (node) => node.type === ui.LaunchRun);
          assert.equal(modal.props.request, exactRequest, "Completion keeps the mounted modal's request identity.");
          assert.notEqual(modal.props.readinessRevision, beforePublication, "The target publication refreshes despite an unchanged P2 basis and run id.");
          launch.update(modal.props); await launch.settle();
          assert.equal(find(launch.tree, (node) => node.type === "textarea").props.value, "Keep my cross-phase draft.");
          assert.equal(find(launch.tree, (node) => node.props.value === (phase === "P3" ? "p3.theory_revision" : "p4.comprehensive")).props.checked, true);
          if (phase === "P4") assert.equal(find(launch.tree, (node) => node.type === "input" && node.props.type === "number").props.value, "900");
          assert.equal(submit(launch).props.disabled, false); assert.equal(starts.length, 0);
          await form(launch).props.onSubmit(event); await launch.settle(); await project.settle();
          assert.equal(starts.length, 1); assert.equal(starts[0].basis_sha256, "target-published");
          assert.equal(starts[0].instructions, "Keep my cross-phase draft.");
          if (phase === "P4") assert.equal(starts[0].budget_seconds, 900);
          assert.deepEqual(checks.at(-1), { branch: "trunk", phase: "P2", mode: undefined }, "Closing the completed launch restores the view's existing poll scope.");
        } finally { launch?.unmount(); project.unmount(); }
      });
    }
  } finally { for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; } }
});

// The geometry represents the observed history return: loading content above
// the history expands by 407px. Real component markers drive the wait, while
// this bounded DOM fixture exercises the shipped restoration and focus code.
function readingReturn(further, launch) {
  const names = ["window", "document", "getComputedStyle", "MutationObserver", "requestAnimationFrame", "cancelAnimationFrame"];
  const previous = Object.fromEntries(names.map((name) => [name, globalThis[name]]));
  const listeners = new Set(); const frames = new Map(); const scrolls = []; const focused = [];
  let nextFrame = 0; let observer; let restored = 0;
  const pending = () => [further.tree, launch()?.tree].flatMap(nodes).some((node) => node.props["data-reading-pending"] === "true");
  const documentTop = () => 1084.9 + (launch() ? 362 : 0) + (launch() && form(launch()).props["data-reading-pending"] !== "true" ? 45 : 0);
  globalThis.window = { scrollY: 590, innerHeight: 704, scrollTo: ({ top }) => { scrolls.push(top); globalThis.window.scrollY = top; } };
  globalThis.document = { body: {}, documentElement: {}, addEventListener: (_, callback) => listeners.add(callback), removeEventListener: (_, callback) => listeners.delete(callback) };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block" });
  globalThis.MutationObserver = class {
    constructor(callback) { this.callback = callback; observer = this; }
    observe() { this.active = true; }
    disconnect() { this.active = false; }
  };
  globalThis.requestAnimationFrame = (callback) => { frames.set(++nextFrame, callback); return nextFrame; };
  globalThis.cancelAnimationFrame = (id) => frames.delete(id);
  const history = { tagName: "DETAILS", open: true, isConnected: true, parentElement: null,
    getClientRects: () => [{}], closest: () => null, getAttribute: () => "research-history",
    querySelector: () => ({ textContent: "Research history and sources", contains: () => false }),
    getBoundingClientRect: () => ({ top: documentTop() - window.scrollY, bottom: documentTop() - window.scrollY + 200 }) };
  const button = { tagName: "BUTTON", isConnected: true, parentElement: history,
    getClientRects: () => [{}], closest: () => null, matches: () => false,
    getAttribute: () => "ProjectView:3:run.p2", focus: (options) => focused.push(options),
    getBoundingClientRect: () => ({ top: history.getBoundingClientRect().top + 81.7 }) };
  const root = { querySelector: () => pending() ? {} : null,
    querySelectorAll: (selector) => selector === "details" ? [history] : selector === "[data-run-origin]" ? [button] : selector === "h1,h2" ? [] : [history] };
  history.parentElement = root;
  const scope = "project:P2:trunk";
  const returning = beginRunReturn(captureRunOrigin(root, button, scope));
  history.open = false; returning.prepare(root, scope);
  const cancel = restoreReadingPosition(root, { y: 997, offset: 494.9, anchor: { kind: "data-reading-anchor", value: "research-history" } }, false, (readyRoot) => { restored++; returning.finish(readyRoot, scope); });
  return { history, button, scrolls, focused, get restored() { return restored; }, get queued() { return frames.size; },
    notify: () => { if (observer.active) observer.callback(); },
    flush: () => { for (const [id, callback] of [...frames]) { frames.delete(id); callback(); } },
    moveFocus: () => { for (const listener of listeners) listener({ target: button }); },
    cleanup: () => { cancel(); returning.cancel(); for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; } } };
}

test("history return waits for saved preparation and readiness before restoring its anchor and exact focus", async () => {
  const preparation = defer(); const inputs = defer(); let launch;
  await withApi({ phasePreparation: () => preparation.promise, readiness: () => inputs.promise }, async () => {
    const inner = ui.FurtherWorkCard({ projectId: "project.history", phase: "P2", branch: "trunk", onStarted: noop });
    const further = mount(inner.type, inner.props); let reading;
    try {
      await further.settle(); reading = readingReturn(further, () => launch);
      assert.equal(reading.history.open, true); assert.equal(reading.queued, 0); assert.deepEqual(reading.scrolls, []);
      preparation.resolve({ instructions: "Keep the missing visit process explicit." }); await further.settle();
      const element = find(further.tree, (node) => node.type === ui.LaunchRun);
      launch = mount(element.type, element.props); await launch.settle(); reading.notify(); reading.flush();
      assert.deepEqual(reading.scrolls, [], "The second asynchronous source still changes the layout above history.");
      inputs.resolve({ modes: [{ ...readiness("p2.full_catalog", "basis").modes[0], basis: { sha256: "basis", project: { research_instructions: "Use synthetic data until patient data exist." } } }] });
      await launch.settle(); reading.notify(); reading.flush();
      assert.equal(reading.restored, 1); assert.equal(reading.scrolls.length, 1);
      assert.ok(Math.abs(reading.history.getBoundingClientRect().top - 494.9) < 0.001);
      assert.ok(Math.abs(reading.button.getBoundingClientRect().top - 576.6) < 0.001);
      assert.deepEqual(reading.focused, [{ preventScroll: true }]);
      reading.notify(); reading.flush(); assert.equal(reading.restored, 1, "Later layout notifications cannot jump the reader again.");
    } finally { reading?.cleanup(); launch?.unmount(); further.unmount(); }
  });
});

test("failed preparation or readiness releases history restoration without reclaiming moved focus", async () => {
  for (const stage of ["preparation", "readiness"]) {
    const preparation = defer(); const inputs = defer(); let launch;
    await withApi({ phasePreparation: () => preparation.promise, readiness: () => inputs.promise }, async () => {
      const inner = ui.FurtherWorkCard({ projectId: `project.history-failure-${stage}`, phase: "P2", branch: "trunk", onStarted: noop });
      const further = mount(inner.type, inner.props); let reading;
      try {
        await further.settle(); reading = readingReturn(further, () => launch); reading.moveFocus();
        if (stage === "preparation") {
          preparation.reject(new Error("Saved instructions unavailable")); await further.settle();
          assert.ok(find(further.tree, (node) => node.props.role === "alert"));
          const summary = find(further.tree, (node) => node.type.name === "PhaseInputSummary");
          assert.equal(summary.props.preparation.loaded, false);
          assert.equal(summary.props.preparation.error, true);
          assert.equal(summary.props.preparationStatus, null, "The launch input check has not mounted after preparation loading failed.");
          assert.equal(find(further.tree, (node) => node.type === ui.LaunchRun), undefined);
        } else {
          preparation.resolve({ instructions: "Preserved instructions" }); await further.settle();
          const element = find(further.tree, (node) => node.type === ui.LaunchRun);
          launch = mount(element.type, element.props); await launch.settle(); reading.notify(); assert.equal(reading.queued, 0);
          inputs.reject(new Error("Research inputs unavailable")); await launch.settle();
          assert.ok(refresh(launch)); assert.equal(submit(launch).props.disabled, true);
        }
        reading.notify(); reading.flush(); assert.equal(reading.restored, 1);
        assert.deepEqual(reading.focused, [], "User movement during loading retains priority over origin focus.");
      } finally { reading?.cleanup(); launch?.unmount(); further.unmount(); }
    });
  }
});

test("selected P2 model passes its exact source and scoped edit to the ordinary proposal launch", async () => {
  const identity = { stable_id: "method.seed-support", version: 1, definition_sha256: "a".repeat(64) };
  const catalog = { branch: "trunk", phase: "P2", family: "method_catalog", generation_id: "catalog.original", sha256: "b".repeat(64), run_id: "run.original", package_id: "package.original" };
  const proposal = { proposal_id: "proposal.original", catalog_ref: catalog, generation_ref: { ...catalog, family: "lead_proposal", generation_id: "proposal.original", sha256: "c".repeat(64) } };
  const method = { identity, title: "Selected nonlinear calculation", mathematical_definition: { canonical_definition: { feature_definition: { definition: "Construct the quadratic feature using training-only transforms." }, algorithm_or_update_rule: [{ order: 1, operation: "Keep the exact estimator except the requested support check." }] } } };
  const seed = methodStartingPoint(method, proposal, { identity, source_ref: catalog });
  const issues = ["theory_review", "empirical_review"].map((family, index) => ({ issue_id: `issue.support-${index}`, kind: "scientific_issue", title: `Support gate concern ${index + 1}`, phase: "P2", branch: "trunk", affected_record_ids: [identity.stable_id],
    explanation_target: { ...catalog, family, generation_id: `review.${index}`, sha256: String(index + 1).repeat(64), kind: "phase_issue", entry_pointer: "/assessments/0/findings/0", object_id: `finding.support-${index}` } }));
  const original = JSON.stringify(seed); const starts = [];
  await withApi({ phasePreparation: async () => ({ instructions: "" }), readiness: async () => readiness("p2.full_catalog", "current-basis"), startRun: async (_, payload) => { starts.push(payload); return { run_id: "run.seeded", state: "requested" }; } }, async () => {
    const inner = ui.FurtherWorkCard({ projectId: "project.seed-support", phase: "P2", branch: identity.stable_id, methodId: identity.stable_id, modelRef: identity, methodLabel: method.title, suppliedMethod: seed, issues, onStarted: noop });
    const further = mount(inner.type, inner.props); let launch;
    try {
      await further.settle(); let element = find(further.tree, (node) => node.type === ui.LaunchRun);
      assert.equal(find(further.tree, (node) => node.type === "input" && node.props.type === "radio").props.checked, true);
      const issueChoices = nodes(further.tree).filter((node) => node.type === "input" && node.props.type === "checkbox");
      const sourceLabels = nodes(further.tree).filter((node) => node.type === "label" && Array.isArray(node.props.children) && node.props.children.includes("Scientific finding: "));
      assert.equal(sourceLabels.length, 2, "The two review findings are not described as researcher questions.");
      assert.equal(issueChoices.length, 2); issueChoices[0].props.onChange({ target: { checked: true } }); await further.settle();
      nodes(further.tree).filter((node) => node.type === "input" && node.props.type === "checkbox")[1].props.onChange({ target: { checked: true } }); await further.settle();
      element = find(further.tree, (node) => node.type === ui.LaunchRun);
      element.props.onInstructionsChange("Replace only the derived-square range gate with a check on primitive inputs; retain the other calculation rules.");
      await further.settle(); element = find(further.tree, (node) => node.type === ui.LaunchRun);
      launch = mount(element.type, element.props); await launch.settle(); await form(launch).props.onSubmit(event); await launch.settle();
      assert.equal(starts.length, 1); assert.equal(starts[0].phase, "P2"); assert.equal(starts[0].branch_id, "trunk");
      assert.equal(starts[0].mode, "p2.full_catalog", "The ordinary UI choice is routed to the supplied-proposal mode by the backend.");
      assert.equal(starts[0].basis_sha256, "current-basis"); assert.deepEqual(starts[0].supplied_method, seed);
      assert.deepEqual(starts[0].context_refs, issues.map((issue) => issue.explanation_target), "Both authored review findings retain exact source-entry references.");
      assert.deepEqual(methodStartingPointSource(starts[0].supplied_method), { kind: "p2_method_starting_point", method_identity: identity, catalog_ref: catalog, proposal_ref: proposal.generation_ref, proposal_id: proposal.proposal_id });
      assert.match(starts[0].supplied_method.specification_markdown, /training-only transforms|exact estimator/);
      assert.match(starts[0].instructions, /Replace only the derived-square range gate/);
      assert.equal(JSON.stringify(seed), original);
      const alternatives = nodes(further.tree).filter((node) => node.type === "input" && node.props.type === "radio")[1];
      alternatives.props.onChange(); await further.settle(); element = find(further.tree, (node) => node.type === ui.LaunchRun);
      assert.equal(element.props.request.supplied_method, undefined, "Choosing new alternatives removes only the selected starting point.");
      assert.equal(element.props.instructions, starts[0].instructions); assert.equal(starts.length, 1, "Changing the choice never launches another turn.");
    } finally { launch?.unmount(); further.unmount(); }
  });
});

test("FurtherWork carries typed questions and tasks from the exact published trunk candidate", async () => {
  const identity = { stable_id: "method.trunk-work", version: 1, definition_sha256: "a".repeat(64) };
  const source = { branch: "trunk", phase: "P2", family: "attention_items", generation_id: "attention.trunk-work", sha256: "b".repeat(64), run_id: "run.trunk-work", package_id: "package.trunk-work" };
  const record = (kind, index, title) => ({ issue_id: `issue.trunk-work.${index}`, kind, title, phase: "P2", branch: "trunk", generation_ref: { ...source, entry_pointer: `/${index}` }, scope: { kind: "model", branch: "trunk", model_ref: identity }, explanation_target: { ...source, kind: "phase_issue", object_id: `attention.trunk-work.${index}`, entry_pointer: `/${index}` } });
  const question = record("researcher_decision", 0, "Is this clinical history recorded?");
  const task = record("research_task", 1, "Investigate the support check.");
  const wrongModel = { ...record("researcher_decision", 2, "Another model must remain hidden"), scope: { ...question.scope, model_ref: { ...identity, stable_id: "method.other" } } };
  const oldVersion = { ...record("researcher_decision", 3, "An earlier version must remain hidden"), scope: { ...question.scope, model_ref: { ...identity, version: 0 } } };
  await withApi({ phasePreparation: async () => ({ instructions: "" }) }, async () => {
    const inner = ui.FurtherWorkCard({ projectId: "project.trunk-work", phase: "P2", branch: identity.stable_id, methodId: identity.stable_id, modelRef: identity, issues: [question, task, wrongModel, oldVersion], onStarted: noop });
    const further = mount(inner.type, inner.props);
    try {
      await further.settle();
      const choices = nodes(further.tree).filter((node) => node.type === "label" && Array.isArray(node.props.children) && node.props.children[0]?.props?.type === "checkbox");
      assert.equal(choices.length, 2);
      assert.ok(choices[0].props.children.includes("Researcher question: ")); assert.ok(choices[1].props.children.includes("Team task: "));
      assert.ok(choices[0].props.children.includes(question.title)); assert.ok(choices[1].props.children.includes(task.title));
      const before = JSON.stringify(task); choices[1].props.children[0].props.onChange({ target: { checked: true } }); await further.settle();
      const launch = find(further.tree, (node) => node.type === ui.LaunchRun);
      assert.deepEqual(launch.props.request.context_refs, [task.explanation_target]); assert.equal(launch.props.request.branch, "trunk");
      assert.equal(JSON.stringify(task), before, "Selected source retains its authored scope and exact entry.");
    } finally { further.unmount(); }
  });
});

function methodExplorer(props) {
  const direct = ui.MethodProposals(props);
  const tree = direct.type(direct.props);
  return { tree, element: find(tree, (node) => node.type.name === "ExploreMethod") };
}

test("first P2 publication preserves shared preparation until an explicit method choice, including phase return", async () => {
  const previousWindow = globalThis.window; const previousDocument = globalThis.document;
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { addEventListener: noop, removeEventListener: noop };
  const identity = { stable_id: "method.first-publication", version: 1, definition_sha256: "a".repeat(64) };
  const source = { branch: "trunk", phase: "P2", family: "method_catalog", generation_id: "catalog.first", sha256: "b".repeat(64), run_id: "run.first", package_id: "package.first" };
  const proposal = { proposal_id: "proposal.first", role: "research_lead", branch: "trunk", phase: "P2", generation_ref: { ...source, family: "lead_proposal", generation_id: "proposal.first" }, method: { title: "First method", identity, mathematical_definition: { canonical_definition: { target_or_estimand: "The first estimand" } } } };
  const catalog = { method_id: identity.stable_id, branch_id: identity.stable_id, title: proposal.method.title, identity, registered: true, status: "active", source_ref: source };
  const literatureSeed = { title: "The researcher's original idea", specification_markdown: "Preserve the original shared seed." };
  const loads = []; let published = false; let starts = 0;
  try {
    await withApi({ project: async () => ({ project: { name: "First publication fixture" } }), branches: async () => ({ branches: [] }),
      listRuns: async () => ({ runs: published ? [{ run_id: "run.first", phase: "P2", branch_id: "trunk", state: "published" }] : [] }),
      artifacts: async () => ({ method_proposals: published ? [proposal] : [], research_bases: [{ branch: "trunk", phase: "P1", phase2_preparation: { supplied_method: literatureSeed } }] }), decisionsPending: async () => ({}),
      readiness: async () => readiness("p2.full_catalog", published ? "published" : "initial"), records: async () => ({ records: [] }),
      assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: published ? [catalog] : [] }),
      phasePreparation: async (_project, branch, phase) => { loads.push([branch, phase]); return { instructions: branch === "trunk" ? "" : "This method's saved instructions" }; },
      startRun: async () => { starts++; throw new Error("Publication and selection must not launch research."); },
    }, async () => {
      let context = { phase: "P2", branch: "trunk" };
      let project;
      const props = { projectId: "project.first-publication", onContextChange: patch => { context = { ...context, ...patch }; project.update({ context }); }, onOpenRun: noop };
      project = mount(ui.ProjectView, { ...props, context });
      let reader; let further;
      const cardFromReader = () => find(reader.tree, node => node.type === ui.FurtherWorkCard);
      const embedded = () => find(further.tree, node => node.type === ui.LaunchRun);
      try {
        await project.settle(); let methods = find(project.tree, node => node.type === ui.MethodProposals);
        const emptyRoot = ui.MethodProposals(methods.props);
        let explorer = methodExplorer(methods.props).element; reader = mount(explorer.type, explorer.props); await reader.settle();
        const firstSlot = reader.tree.props.children[3];
        const first = ui.FurtherWorkCard(cardFromReader().props); further = mount(first.type, first.props); await further.settle();
        const draft = "Keep the shared directions I am preparing for the next proposal run.";
        embedded().props.onInstructionsChange(draft); await further.settle();
        assert.deepEqual(embedded().props.request.supplied_method, literatureSeed);
        assert.equal(context.p2SharedPreparation, true, "The empty preparation scope is persisted before publication.");
        published = true; methods.props.onResolved(); await project.settle();
        methods = find(project.tree, node => node.type === ui.MethodProposals);
        assert.equal(ui.MethodProposals(methods.props).type, emptyRoot.type, "Publication retains the complete reader ancestor tree.");
        explorer = methodExplorer(methods.props).element; reader.update(explorer.props); await reader.settle(); await project.settle();
        assert.equal(find(reader.tree, node => node.type.name === "MethodPicker").props.value, "run.first:proposal.first");
        const publishedSlot = reader.tree.props.children[3];
        assert.equal(publishedSlot.type, firstSlot.type, "Preparation stays at the same sibling slot beside the newly populated reader.");
        const publishedCard = ui.FurtherWorkCard(publishedSlot.props);
        assert.equal(publishedCard.key, first.key); assert.equal(publishedCard.props.branch, "trunk");
        assert.equal(publishedCard.props.summaryContext.methodId, identity.stable_id, "Counts follow the displayed model while instructions stay shared.");
        further.update(publishedCard.props); await further.settle();
        assert.equal(embedded().props.instructions, draft); assert.deepEqual(embedded().props.request.supplied_method, literatureSeed, "Automatic display keeps the original shared seed.");
        assert.equal(embedded().props.request.methodLabel, "New model proposals");
        assert.equal(find(further.tree, node => node.type.name === "PhaseInputSummary").props.showSummary, true);
        assert.equal(find(further.tree, node => node.props["data-reading-anchor"] === "further-work").props.open, true);
        assert.deepEqual(loads, [["trunk", "P2"]]);
        reader.unmount(); further.unmount(); reader = null; further = null;
        context = { ...context, phase: "P3", branch: identity.stable_id }; project.update({ context }); await project.settle();
        context = { ...context, phase: "P2" }; project.update({ context }); await project.settle();
        methods = find(project.tree, node => node.type === ui.MethodProposals);
        explorer = methodExplorer(methods.props).element; reader = mount(explorer.type, explorer.props); await reader.settle();
        const returning = ui.FurtherWorkCard(cardFromReader().props); assert.equal(returning.key, first.key);
        further = mount(returning.type, returning.props); await further.settle();
        assert.equal(embedded().props.instructions, draft, "Phase return restores the same shared draft after first publication.");
        reader.unmount(); further.unmount(); project.unmount(); reader = null; further = null;
        context = normalizeNavigation({ projectId: props.projectId, contexts: { [props.projectId]: context } }).contexts[props.projectId];
        project = mount(ui.ProjectView, { ...props, context }); await project.settle();
        methods = find(project.tree, node => node.type === ui.MethodProposals);
        explorer = methodExplorer(methods.props).element; reader = mount(explorer.type, explorer.props); await reader.settle();
        const remounted = ui.FurtherWorkCard(cardFromReader().props); assert.equal(remounted.key, first.key);
        further = mount(remounted.type, remounted.props); await further.settle();
        assert.equal(embedded().props.instructions, draft, "Run-detail return and restored navigation retain the shared preparation.");
        const explicit = find(reader.tree, node => node.props.children === "Prepare work on this method");
        assert.ok(explicit, "The sole automatically displayed method has an explicit preparation action.");
        const focusEffects = [];
        const settings = { open: false, querySelector: () => ({ getBoundingClientRect: () => ({ top: 500 }), focus: options => focusEffects.push(["focus", options]) }) };
        globalThis.document.getElementById = () => ({ closest: () => ({ querySelector: selector => selector === ".project-toolbar" ? null : settings }) });
        globalThis.window.scrollY = 80; globalThis.window.scrollTo = options => focusEffects.push(["scroll", options]);
        explicit.props.onClick(); await reader.settle(); await project.settle();
        assert.equal(context.p2SharedPreparation, false);
        assert.equal(settings.open, true);
        assert.deepEqual(focusEffects, [["scroll", { top: 564, behavior: "instant" }], ["focus", { preventScroll: true }]], "The removed action leaves focus on the new method's opened settings below the toolbar offset.");
        const methodCard = ui.FurtherWorkCard(cardFromReader().props); assert.notEqual(methodCard.key, first.key);
        further.unmount(); further = mount(methodCard.type, methodCard.props); await further.settle();
        assert.equal(embedded().props.instructions, "This method's saved instructions", "The shared draft is not copied into method instructions.");
        assert.deepEqual(methodStartingPointSource(embedded().props.request.supplied_method).method_identity, identity);
        assert.equal(starts, 0);
      } finally { further?.unmount(); reader?.unmount(); project.unmount(); }
    });
  } finally {
    if (previousWindow === undefined) delete globalThis.window; else globalThis.window = previousWindow;
    if (previousDocument === undefined) delete globalThis.document; else globalThis.document = previousDocument;
  }
});

test("P2 persists shared preparation before first publication can arrive while the reader is away", async () => {
  let context = { phase: "P2", branch: "trunk" }; let preparation;
  const onPreparationScopeChange = p2SharedPreparation => { context = { ...context, p2SharedPreparation }; };
  const empty = methodExplorer({ onPreparationScopeChange, furtherWork: selection => { preparation = selection; return null; } });
  let reader = mount(empty.element.type, empty.element.props);
  try {
    await reader.settle(); assert.equal(context.p2SharedPreparation, true);
    reader.unmount(); reader = null;
    const proposal = { proposal_id: "first", role: "research_lead", generation_ref: { run_id: "run.away" }, method: { title: "Published while away", identity: { stable_id: "method.away", version: 1, definition_sha256: "a".repeat(64) } } };
    const restored = normalizeNavigation({ contexts: { project: context } }).contexts.project;
    const returning = methodExplorer({ proposals: [proposal], methods: [{ method_id: "method.away", identity: proposal.method.identity, registered: true }], initialSharedPreparation: restored.p2SharedPreparation,
      onPreparationScopeChange, furtherWork: selection => { preparation = selection; return null; } });
    reader = mount(returning.element.type, returning.element.props); await reader.settle();
    assert.equal(preparation.proposal, proposal);
    assert.equal(preparation.sharedPreparation, true, "The first automatically displayed method cannot replace the shared preparation while away.");
  } finally { reader?.unmount(); }
});

test("superseding the selected exact P2 version changes preparation scope while preserving both drafts", async () => {
  const names = ["window", "document", "sessionStorage"];
  const previous = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const storage = new Map(); const projectId = "project.superseded-preparation";
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { addEventListener: noop, removeEventListener: noop };
  globalThis.sessionStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
  const identity = { stable_id: "method.superseded", version: 1, definition_sha256: "a".repeat(64) };
  const proposal = version => ({ proposal_id: `proposal.v${version}`, role: "research_lead", branch: "trunk", phase: "P2",
    generation_ref: { run_id: `run.v${version}`, generation_id: `proposal.v${version}` },
    method: { title: `Selected model version ${version}`, identity: { ...identity, version, definition_sha256: (version === 1 ? "a" : "b").repeat(64) } } });
  const original = proposal(1), successor = proposal(2);
  const catalog = item => ({ method_id: identity.stable_id, branch_id: identity.stable_id, title: item.method.title, identity: item.method.identity, registered: true, status: "active" });
  const sharedDraft = "Keep these separate shared proposal directions.";
  const methodDraft = "Keep this unsaved direction for the exact earlier model.";
  storage.set(furtherWorkKey(projectId, "trunk", "P2"), JSON.stringify({ text: sharedDraft }));
  let published = false; let starts = 0;
  try {
    await withApi({ project: async () => ({ project: { name: "Supersession fixture" } }), branches: async () => ({ branches: [] }),
      listRuns: async () => ({ runs: [{ run_id: published ? "run.v2" : "run.v1", phase: "P2", branch_id: "trunk", state: "published" }] }),
      artifacts: async () => ({ method_proposals: published ? [successor, { ...original, is_current_package: false }] : [original] }),
      decisionsPending: async () => ({}), readiness: async () => readiness("p2.full_catalog", published ? "v2" : "v1"),
      records: async () => ({ records: [] }), assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [catalog(published ? successor : original)] }),
      phasePreparation: async () => ({ instructions: "Saved instructions" }),
      startRun: async () => { starts++; throw new Error("Publication must not launch research."); },
    }, async () => {
      let context = { phase: "P2", branch: "trunk", p2ProposalKey: "run.v1:proposal.v1", p2SharedPreparation: false };
      let project;
      project = mount(ui.ProjectView, { projectId, context, onOpenRun: noop, onContextChange: patch => { context = { ...context, ...patch }; project.update({ context }); } });
      let reader; let further; let returned;
      const preparation = () => ui.FurtherWorkCard(find(reader.tree, node => node.type === ui.FurtherWorkCard).props);
      const instructions = fixture => find(fixture.tree, node => node.type === ui.LaunchRun).props.instructions;
      try {
        await project.settle(); let methods = find(project.tree, node => node.type === ui.MethodProposals);
        let explorer = methodExplorer(methods.props).element; reader = mount(explorer.type, explorer.props); await reader.settle();
        const before = preparation(); assert.equal(before.props.methodId, identity.stable_id);
        further = mount(before.type, before.props); await further.settle();
        find(further.tree, node => node.type === ui.LaunchRun).props.onInstructionsChange(methodDraft); await further.settle();
        published = true; methods.props.onResolved(); await project.settle();
        methods = find(project.tree, node => node.type === ui.MethodProposals);
        explorer = methodExplorer(methods.props).element; reader.update(explorer.props); await reader.settle(); await project.settle();
        assert.equal(find(reader.tree, node => node.type.name === "MethodPicker").props.value, "run.v1:proposal.v1");
        assert.equal(context.p2ProposalKey, "run.v1:proposal.v1", "Publication keeps the exact historical selection.");
        const after = preparation(); assert.notEqual(after.key, before.key, "Supersession replaces the keyed preparation subtree.");
        assert.equal(after.props.branch, "trunk"); assert.equal(after.props.methodId, undefined);
        assert.deepEqual(after.props.summaryContext.modelRef, identity, "The reading summary still follows the exact earlier version.");
        further.unmount(); further = mount(after.type, after.props); await further.settle();
        assert.equal(instructions(further), sharedDraft, "Shared preparation retains its own draft.");
        returned = mount(before.type, before.props); await returned.settle();
        assert.equal(instructions(returned), methodDraft, "The previous model's draft is retained separately without migration.");
        assert.equal(starts, 0);
      } finally { returned?.unmount(); further?.unmount(); reader?.unmount(); project.unmount(); }
    });
  } finally {
    for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; }
  }
});

test("P2 proposal navigation scope changes independently of its shared preparation draft", async () => {
  const context = name => ({ projectId: "project.proposal-summary-scope", phase: "P2", branch: `method.${name}`, methodId: `method.${name}`, modelRef: { stable_id: `method.${name}`, version: 1, definition_sha256: name.repeat(64) } });
  let loads = 0;
  await withApi({ phasePreparation: async () => { loads++; return { instructions: "" }; } }, async () => {
    const props = { projectId: "project.proposal-summary-scope", phase: "P2", branch: "trunk", summaryContext: context("a"), onStarted: noop };
    const first = ui.FurtherWorkCard(props); const further = mount(first.type, first.props);
    const summary = () => find(further.tree, node => node.type.name === "PhaseInputSummary");
    try {
      await further.settle(); const initialScope = summary().props.scope;
      find(further.tree, node => node.type === ui.LaunchRun).props.onInstructionsChange("Keep this shared proposal instruction."); await further.settle();
      const unchanged = { ...context("a"), modelRef: Object.fromEntries(Object.entries(context("a").modelRef).reverse()) };
      further.update({ summaryContext: unchanged }); await further.settle();
      assert.equal(summary().props.scope, initialScope, "Equal polling data with reordered properties retains the return session.");
      const next = ui.FurtherWorkCard({ ...props, summaryContext: context("b") });
      assert.equal(next.key, first.key, "Noncatalog proposals use the existing shared trunk preparation draft.");
      further.update(next.props); await further.settle();
      assert.notEqual(summary().props.scope, initialScope, "Switching the viewed proposal invalidates the previous question navigation session.");
      assert.equal(summary().props.context.methodId, "method.b");
      assert.equal(find(further.tree, node => node.type === ui.LaunchRun).props.instructions, "Keep this shared proposal instruction.");
      assert.equal(loads, 1, "Changing the viewed proposal does not reload or replace shared instructions.");
    } finally { further.unmount(); }
  });
});

test("a published model update preserves the initially resolved selection and its mounted draft until an explicit choice", async () => {
  const proposal = (run, id, title) => ({ proposal_id: `proposal.${id}`, role: "research_lead", generation_ref: { run_id: run, generation_id: `generation.${id}` }, method: { title, identity: { stable_id: `method.${id}`, version: 1, definition_sha256: id === "original" ? "a".repeat(64) : "b".repeat(64) }, mathematical_definition: { canonical_definition: { target_or_estimand: `${title} target` } } } });
  const original = proposal("run.original", "original", "Original QLC");
  const correction = proposal("run.correction", "correction", "Corrected QLC-PS");
  const catalog = (item) => ({ method_id: item.method.identity.stable_id, identity: item.method.identity, registered: true, status: "active" });
  const oldComparison = { generation_ref: { run_id: "run.original" }, overview_markdown: "Original team comparison" };
  const latestComparison = { generation_ref: { run_id: "run.correction" }, overview_markdown: "New team comparison" };
  const picks = []; let remembered; let selection;
  const props = { projectId: "project.selection-publication", methods: [catalog(original)], proposals: [original], comparisons: [oldComparison], onPick: (key) => { picks.push(key); remembered = key; }, furtherWork: (context) => {
    selection = context;
    return ui.FurtherWorkCard({ projectId: "project.selection-publication", phase: "P2", branch: context.methodBranch, methodId: context.methodId, modelRef: context.method.identity, onStarted: noop });
  } };
  await withApi({ phasePreparation: async () => ({ instructions: "" }) }, async () => {
    const first = methodExplorer(props); const reader = mount(first.element.type, first.element.props); let further; let returned;
    try {
      await reader.settle();
      assert.deepEqual(picks, ["run.original:proposal.original"], "The default also reaches the existing navigation persistence callback.");
      const firstCard = find(reader.tree, (node) => node.type.name === "FurtherWork");
      further = mount(firstCard.type, firstCard.props); await further.settle();
      const draft = "Keep the primitive-input support correction exact. ".repeat(50);
      find(further.tree, (node) => node.type === ui.LaunchRun).props.onInstructionsChange(draft); await further.settle();
      find(reader.tree, (node) => node.type.name === "MethodReaderDisclosure" && node.props.name === "assumptions").props.onToggle(true); await reader.settle();
      const published = { ...props, methods: [catalog(correction), catalog(original)], proposals: [correction, { ...original, is_current_package: false }], comparisons: [latestComparison, { ...oldComparison, is_current_package: false }] };
      const next = methodExplorer(published);
      assert.equal(next.element.props.comparison, latestComparison, "The latest comparison still updates independently.");
      reader.update(next.element.props); await reader.settle();
      assert.equal(selection.proposal.proposal_id, original.proposal_id);
      assert.equal(find(reader.tree, (node) => node.type.name === "MethodPicker").props.value, remembered);
      assert.equal(find(reader.tree, (node) => node.type.name === "MethodReaderDisclosure" && node.props.name === "assumptions").props.open, true);
      const retainedCard = find(reader.tree, (node) => node.type.name === "FurtherWork");
      assert.equal(retainedCard.key, firstCard.key, "Publication retains the mounted native disclosure rather than remounting Further work.");
      further.update(retainedCard.props); await further.settle();
      assert.equal(find(further.tree, (node) => node.type === ui.LaunchRun).props.instructions, draft);
      assert.equal(picks.length, 1, "Polling does not manufacture another model choice.");
      const defaultReturn = methodExplorer({ ...published, initialPick: remembered });
      returned = mount(defaultReturn.element.type, defaultReturn.element.props); await returned.settle();
      assert.equal(find(returned.tree, (node) => node.type.name === "MethodPicker").props.value, "run.original:proposal.original", "History return retains the default the researcher was reading before publication.");
      returned.unmount(); returned = null;
      find(reader.tree, (node) => node.type.name === "MethodPicker").props.onSelect("run.correction:proposal.correction"); await reader.settle();
      assert.equal(selection.proposal.proposal_id, correction.proposal_id);
      assert.equal(remembered, "run.correction:proposal.correction");
      assert.notEqual(find(reader.tree, (node) => node.type.name === "FurtherWork").key, firstCard.key, "An explicit choice still selects the other model's own form.");
      const remount = methodExplorer({ ...published, initialPick: remembered }); returned = mount(remount.element.type, remount.element.props); await returned.settle();
      assert.equal(find(returned.tree, (node) => node.type.name === "MethodPicker").props.value, remembered, "Returning to the reader uses the persisted actual selection.");
      assert.equal(picks.length, 2);
    } finally { returned?.unmount(); further?.unmount(); reader.unmount(); }
  });
});

test("selection persistence ignores transient empty data but resolves a genuinely missing proposal", async () => {
  const old = { proposal_id: "old", generation_ref: { run_id: "run.old" }, method: { title: "Old", identity: { stable_id: "method.old", version: 1, definition_sha256: "a".repeat(64) } } };
  const replacement = { ...old, proposal_id: "replacement", generation_ref: { run_id: "run.replacement" } };
  const picks = []; const first = methodExplorer({ proposals: [old], onPick: (key) => picks.push(key) });
  const reader = mount(first.element.type, first.element.props);
  try {
    await reader.settle(); reader.update({ proposals: [] }); await reader.settle();
    assert.equal(find(reader.tree, node => node.type.name === "MethodPicker"), undefined); assert.deepEqual(picks, ["run.old:old"]);
    reader.update({ proposals: [old] }); await reader.settle(); assert.deepEqual(picks, ["run.old:old"]);
    reader.update({ proposals: [replacement] }); await reader.settle();
    assert.deepEqual(picks, ["run.old:old", "run.replacement:replacement"]);
    assert.equal(find(reader.tree, (node) => node.type.name === "MethodPicker").props.value, "run.replacement:replacement");
  } finally { reader.unmount(); }
});

test("P2 native disclosure state and drafts remain independent across explicit exact-model selections", async () => {
  const proposals = ["a", "b"].map((name) => ({ proposal_id: `proposal.${name}`, role: "theorist", generation_ref: { run_id: `run.${name}` }, method: { title: `Method ${name}`, identity: { stable_id: `method.${name}`, version: 1, definition_sha256: name.repeat(64) }, summary: `Original ${name} account.` } }));
  const readings = []; const contexts = []; const element = methodExplorer({ proposals, onReadingChange: patch => readings.push(patch), furtherWork: context => { contexts.push(context); return null; } }).element;
  const reader = mount(element.type, element.props);
  const disclosure = name => find(reader.tree, node => node.type.name === "MethodReaderDisclosure" && node.props.name === name);
  const picker = () => find(reader.tree, node => node.type.name === "MethodPicker");
  try {
    await reader.settle();
    const draftStore = contexts.at(-1).draftStore; draftStore.set("exact-question-a", "An unsent scientific response.");
    disclosure("assumptions").props.onToggle(true); await reader.settle();
    picker().props.onSelect("run.b:proposal.b"); await reader.settle();
    assert.equal(disclosure("assumptions").props.open, false);
    disclosure("review").props.onToggle(true); await reader.settle();
    picker().props.onSelect("run.a:proposal.a"); await reader.settle();
    assert.equal(disclosure("assumptions").props.open, true); assert.equal(disclosure("review").props.open, false);
    assert.strictEqual(contexts.at(-1).draftStore, draftStore); assert.equal(draftStore.get("exact-question-a"), "An unsent scientific response.");
    const saved = readings.at(-1).modelDisclosures;
    assert.deepEqual(saved["run.a:proposal.a"], { assumptions: true }); assert.deepEqual(saved["run.b:proposal.b"], { review: true });
    const returned = mount(element.type, { ...element.props, initialPick: "run.b:proposal.b", reading: { modelDisclosures: saved } });
    try { await returned.settle(); assert.equal(find(returned.tree, node => node.type.name === "MethodReaderDisclosure" && node.props.name === "review").props.open, true); }
    finally { returned.unmount(); }
  } finally { reader.unmount(); }
});

test("credential guidance stays advisory and does not probe or start work when settings are opened", async () => {
  let starts = 0; let probes = 0; let accountReads = 0; let settings = 0; let accounts = 0;
  await withApi({
    readiness: async () => readiness("p1.literature_update", "a".repeat(64)),
    startRun: async () => { starts++; return { run_id: "run.explicit" }; },
    probeProvider: async () => { probes++; throw new Error("Unexpected paid probe"); },
    account: async () => { accountReads++; throw new Error("Unexpected global account check"); },
  }, async () => {
    const launch = mount(ui.LaunchRun, {
      projectId: "project.setup", request: { phase: "P1", branch: "trunk", mode: "p1.literature_update" },
      setupProject: { members: { research_lead: { provider: "openai", credential_source: "account", credential_configured: false } } },
      onTeamSettings: () => settings++, onOpenAIAccount: () => accounts++, onStarted: noop,
    });
    try {
      await launch.settle();
      assert.equal(submit(launch).props.disabled, false, "Configuration hints do not add a launch gate.");
      const guidance = find(launch.tree, node => node.type.name === "RunSetupGuidance");
      const guidanceTree = guidance.type(guidance.props);
      const settingControl = find(guidanceTree, node => node.props.children === "Team Settings");
      const accountControl = find(guidanceTree, node => node.props.children === "OpenAI Account");
      settingControl.props.onClick(); accountControl.props.onClick();
      assert.equal(settings, 1); assert.equal(accounts, 1);
      assert.deepEqual([starts, probes, accountReads], [0, 0, 0]);
      await form(launch).props.onSubmit(event); await launch.settle();
      assert.equal(starts, 1, "Research starts only after the existing submit action.");
      assert.deepEqual([probes, accountReads], [0, 0]);
    } finally { launch.unmount(); }
  });
});

test("settings shortcuts keep the project editor mounted and request a refresh on return", async () => {
  const originals = { window: globalThis.window, document: globalThis.document, history: globalThis.history, localStorage: globalThis.localStorage, sessionStorage: globalThis.sessionStorage };
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { documentElement: { dataset: {} } };
  globalThis.history = { scrollRestoration: "auto" };
  globalThis.localStorage = { getItem: () => null, setItem: noop };
  globalThis.sessionStorage = { getItem: () => null, setItem: noop };
  try {
    await withApi({ projects: async () => ({ projects: [{ project_id: "project.setup", name: "Existing research" }] }) }, async () => {
      const app = mount(ui.App, {});
      const project = () => find(app.tree, node => node.type === ui.ProjectView);
      try {
        await app.settle();
        const original = project();
        original.props.onTeamSettings(); await app.settle();
        assert.equal(project().key, original.key);
        assert.strictEqual(project().type, original.type);
        assert.deepEqual(project().props.context, original.props.context);
        const team = find(app.tree, node => node.props.title === "Team Settings");
        assert.ok(team, "The settings shortcut opens the actual team editor.");
        assert.equal(team.props.children.props.embedded, true);
        team.props.onClose(); await app.settle();
        assert.equal(project().props.settingsRevision, 1);
        project().props.onOpenAIAccount(); await app.settle();
        assert.equal(project().key, original.key);
        find(app.tree, node => node.type.name === "AccountDialog").props.onClose(); await app.settle();
        assert.equal(project().props.settingsRevision, 2);
      } finally { app.unmount(); }
    });
  } finally { Object.assign(globalThis, originals); }
});

test("returning from settings refreshes effective team credentials in the existing project scope", async () => {
  const originals = { window: globalThis.window, document: globalThis.document, setInterval: globalThis.setInterval, clearInterval: globalThis.clearInterval };
  globalThis.window = { addEventListener: noop, removeEventListener: noop };
  globalThis.document = { hidden: false, addEventListener: noop, removeEventListener: noop };
  globalThis.setInterval = () => 1; globalThis.clearInterval = noop;
  let configured = false; let reads = 0;
  const snapshot = () => ({ project: {}, members: { research_lead: { provider: "custom", credential_source: "environment", credential_configured: configured } }, provider_config: {} });
  try {
    await withApi({
      project: async () => { reads++; return snapshot(); }, branches: async () => ({ branches: [] }),
      listRuns: async () => ({ runs: [] }), artifacts: async () => ({ research_bases: [{ branch: "trunk", phase: "P1", research_setting: { research_goal_markdown: "Existing study goal." } }] }),
      decisionsPending: async () => ({}), readiness: async () => ({}), records: async () => ({ records: [] }),
      assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [] }),
    }, async () => {
      const context = { phase: "P1", branch: "trunk" };
      const project = mount(ui.ProjectView, { projectId: "project.setup", context, onContextChange: noop, onTeamSettings: noop, onOpenAIAccount: noop });
      const editor = () => find(project.tree, node => node.type.name === "PhaseOneWorkspace").props.furtherWork;
      try {
        await project.settle();
        assert.equal(editor().props.setupProject.members.research_lead.credential_configured, false);
        assert.equal(typeof editor().props.onTeamSettings, "function");
        const key = editor().key;
        configured = true; project.update({ settingsRevision: 1 }); await project.settle();
        assert.equal(reads, 2);
        assert.equal(editor().key, key);
        assert.equal(editor().props.setupProject.members.research_lead.credential_configured, true);
      } finally { project.unmount(); }
    });
  } finally { Object.assign(globalThis, originals); }
});
