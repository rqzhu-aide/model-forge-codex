import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { restoreReadingPosition } from "../src/readingPosition.js";
import { beginRunReturn, captureRunOrigin } from "../src/runReturnFocus.js";
import { methodStartingPoint, methodStartingPointSource } from "../src/methodSeed.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-launch-refresh-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {default as LaunchRun} from '${src}/components/LaunchRun.jsx'; export {default as ProjectView} from '${src}/components/ProjectView.jsx'; export {default as FurtherWorkCard} from '${src}/components/FurtherWorkCard.jsx'; export {default as MethodProposals} from '${src}/components/MethodProposals.jsx'; export {api} from '${src}/api.js'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
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

async function withApi(overrides, run) {
  const previous = Object.fromEntries(Object.keys(overrides).map((key) => [key, ui.api[key]]));
  Object.assign(ui.api, overrides);
  try { await run(); } finally { Object.assign(ui.api, previous); }
}

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
  let version = "1.18.0"; let basis = "initial-basis";
  await withApi({ project: async () => ({ project: { project_id: "project.wiring", name: "Wiring fixture" }, catalog: { version }, catalog_status: { version: "wrong-field" } }), branches: async () => ({ branches: [] }), listRuns: async () => ({ runs: [] }), artifacts: async () => ({}), decisionsPending: async () => ({}), readiness: async () => readiness("p2.full_catalog", basis), records: async () => ({ records: [] }), assessments: async () => ({ assessments: [] }), methods: async () => ({ methods: [] }), phasePreparation: async () => ({ instructions: "Saved lead instructions" }) }, async () => {
    const project = mount(ui.ProjectView, { projectId: "project.wiring", context: { phase: "P2", branch: "trunk" }, onContextChange: noop, onOpenRun: noop });
    let further;
    try {
      await project.settle(); let methods = find(project.tree, (node) => node.type === ui.MethodProposals);
      const card = methods.props.furtherWork({}); assert.equal(card.props.workflowRevision, "1.18.0");
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
      basis = "published-basis"; methods.props.issues({}).props.onSaved(); await project.settle();
      methods = find(project.tree, (node) => node.type === ui.MethodProposals);
      const publishedCard = methods.props.furtherWork({}); assert.notEqual(publishedCard.props.readinessRevision, initialRevision);
      const publishedInner = ui.FurtherWorkCard(publishedCard.props); assert.equal(publishedInner.key, inner.key, "Publication preserves the draft component's identity.");
      further.update(publishedInner.props); await further.settle();
      embedded = find(further.tree, (node) => node.type === ui.LaunchRun);
      assert.equal(embedded.props.readinessRevision, publishedCard.props.readinessRevision);
      assert.equal(embedded.props.instructions, "Unsaved researcher direction");
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
    assert.equal(reader.tree, null); assert.deepEqual(picks, ["run.old:old"]);
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
