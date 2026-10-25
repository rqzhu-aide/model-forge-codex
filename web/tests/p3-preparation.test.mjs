import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p3-preparation-"));
const bundle = path.join(directory, "test.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {default as LaunchRun} from '${src}/components/LaunchRun.jsx'; export {default as FurtherWorkCard} from '${src}/components/FurtherWorkCard.jsx'; export {assessmentRepairRequest} from '${src}/components/Assessments.jsx'; export {api} from '${src}/api.js'; export {theoryComponentRequest, targetIsStale} from '${src}/runRequests.js'; export {readConversationDraft} from '${src}/assumptionConversations.js'; export {furtherWorkKey} from '${src}/phaseWorkflow.js'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};

// Execute the shipped hooks and handlers. Browser layout/focus is covered by
// the ProjectView fixture, rather than inferred from this bounded hook harness.
function mount(Component, initialProps) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let props = initialProps; let tree;
  const effect = (run, dependencies) => {
    const index = cursor++; const old = slots[index];
    if (!old || !dependencies || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) {
      slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run });
    }
  };
  const hooks = {
    useState(initial) {
      const index = cursor++; slots[index] ||= { value: typeof initial === "function" ? initial() : initial };
      return [slots[index].value, update => { const next = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; } }];
    },
    useEffect: effect, useLayoutEffect: effect,
    useCallback(callback, dependencies) {
      const index = cursor++; const old = slots[index];
      if (!old || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) slots[index] = { value: callback, dependencies };
      return slots[index].value;
    },
    useRef(initial) { return (slots[cursor++] ||= { value: { current: initial } }).value; },
    useId() { const index = cursor++; return (slots[index] ||= { value: `p3-${index}` }).value; },
  };
  return {
    get tree() { return tree; }, update(changes) { props = { ...props, ...changes }; dirty = true; },
    async settle() {
      for (let iteration = 0; iteration < 30; iteration++) {
        if (dirty) {
          cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current;
          try { ui.dispatcher.current = hooks; tree = Component(props); } finally { ui.dispatcher.current = previous; }
          for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); }
        }
        await new Promise(resolve => setImmediate(resolve));
        if (!dirty) return tree;
      }
      throw new Error("P3 hooks did not settle.");
    },
    unmount() { for (const slot of slots) slot?.cleanup?.(); },
  };
}
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (fixture, predicate) => nodes(fixture.tree).find(predicate);
const launchElement = fixture => find(fixture, node => node.type === ui.LaunchRun);
const submit = fixture => find(fixture, node => node.props.type === "submit");
const submitForm = fixture => find(fixture, node => node.type === "form").props.onSubmit({ preventDefault: noop });
const defer = () => { let resolve; let reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const methodRef = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
const theory = { branch: "method.a", phase: "P3", family: "theory_record", generation_id: "theory.current", sha256: "b".repeat(64), run_id: "run.theory", package_id: "package.theory" };
const target = { ...theory, object_id: "claim.boundary", kind: "statement" };
const request = ui.theoryComponentRequest("repair", target, "Boundary guarantee");
const readiness = (revisionReady = true) => ({ modes: [
  { mode: "p3.theory_establishment", ready: true, basis: { sha256: "current-basis" } },
  { mode: "p3.theory_revision", ready: revisionReady, reasons: revisionReady ? [] : ["A complete current theory package is required for this action"], basis: { sha256: "current-basis" } },
  { mode: "p3.assessment", ready: true, basis: { sha256: "current-basis" } },
] });
const cardProps = projectId => ({ projectId, phase: "P3", branch: "method.a", methodId: "method.a", modelRef: methodRef, currentTheoryRef: theory, currentTheoryAligned: true, onStarted: noop });
function card(props) { const element = ui.FurtherWorkCard(props); return mount(element.type, element.props); }
async function withApi(overrides, run) {
  const previous = Object.fromEntries(Object.keys(overrides).map(key => [key, ui.api[key]])); Object.assign(ui.api, overrides);
  try { await run(); } finally { Object.assign(ui.api, previous); }
}

test("untouched P3 uses revision eligibility once and preserves a subsequent choice across publication refresh", async () => {
  for (const eligible of [true, false]) {
    let revisionReady = eligible; const starts = [];
    await withApi({ readiness: async () => readiness(revisionReady), startRun: async (_, payload) => starts.push(payload) }, async () => {
      const form = mount(ui.LaunchRun, { projectId: `default.${eligible}`, embedded: true, request: { phase: "P3", branch: "method.a" }, onStarted: noop });
      try {
        await form.settle();
        const chosen = eligible ? "p3.theory_revision" : "p3.theory_establishment";
        assert.equal(find(form, node => node.props.value === chosen).props.checked, true);
        assert.equal(submit(form).props.children, eligible ? "Start theory revision" : "Start theory development");
        find(form, node => node.props.value === "p3.theory_establishment").props.onChange(); await form.settle();
        revisionReady = true; form.update({ readinessRevision: "new-publication" }); await form.settle();
        assert.equal(find(form, node => node.props.value === "p3.theory_establishment").props.checked, true);
        assert.deepEqual(starts, [], "Choosing and refreshing preparation cannot launch work.");
      } finally { form.unmount(); }
    });
  }
});

test("component preparation keeps prose separate, replaces generated directions, and survives save and remount", async () => {
  const saved = []; const props = cardProps("scope.persistence");
  await withApi({ phasePreparation: async () => ({ instructions: "Saved instructions" }), savePhasePreparation: async (_, __, ___, value) => { saved.push(value); return value; } }, async () => {
    let editor = card(props);
    try {
      await editor.settle(); launchElement(editor).props.onInstructionsChange("My boundary priorities."); await editor.settle();
      const origin = { fixture: "invoking button" }; editor.update({ preparedTheory: { request, modelRef: methodRef, origin }, onPrepared: () => editor.update({ preparedTheory: null }) }); await editor.settle();
      let launch = launchElement(editor);
      assert.equal(launch.props.instructions, "My boundary priorities."); assert.deepEqual(launch.props.request.target, target);
      assert.deepEqual(launch.props.request.methodRef, methodRef); assert.equal(launch.props.mode, "p3.theory_revision");
      assert.equal(find(editor, node => node.type.name === "PhaseInputSummary").props.navigationRequest.origin, origin);
      const other = ui.theoryComponentRequest("repair", { ...target, object_id: "assumption.overlap", kind: "assumption" }, "Overlap condition");
      editor.update({ preparedTheory: { request: other, modelRef: methodRef } }); await editor.settle();
      launch = launchElement(editor); assert.equal(launch.props.instructions, "My boundary priorities.");
      assert.match(launch.props.request.preparedDirections, /Overlap condition/); assert.doesNotMatch(launch.props.request.preparedDirections, /Boundary guarantee/);
      await launch.props.beforeActions.props.children[0].props.onClick(); await editor.settle();
      assert.deepEqual(saved, [{ instructions: "My boundary priorities." }], "Server prose save does not absorb generated directions or target metadata.");
      editor.unmount(); editor = card(props); await editor.settle(); launch = launchElement(editor);
      assert.deepEqual(launch.props.request.target, other.target); assert.deepEqual(launch.props.request.methodRef, methodRef);
      assert.equal(launch.props.mode, "p3.theory_revision");
      find(editor, node => node.props.children === "Clear theory focus").props.onClick(); await editor.settle();
      assert.equal(launchElement(editor).props.request.target, undefined);
      assert.equal(ui.readConversationDraft(ui.furtherWorkKey(props.projectId, props.methodId, "P3")).theoryPreparation, null);
    } finally { editor.unmount(); }
  });
});

test("issue preparation carries supporting context without changing focused component or researcher prose", async () => {
  const issueSource = { ...theory, family: "attention_items", kind: "phase_issue", entry_pointer: "/items/0", object_id: "issue.boundary" };
  const issue = { title: "Check the boundary", explanation_target: issueSource };
  await withApi({ phasePreparation: async () => ({ instructions: "Keep my notes." }) }, async () => {
    const editor = card({ ...cardProps("issue.context"), preparedTheory: { request, modelRef: methodRef } });
    try {
      await editor.settle(); editor.update({ preparedTheory: { issue } }); await editor.settle();
      const launch = launchElement(editor);
      assert.deepEqual(launch.props.request.target, target); assert.deepEqual(launch.props.request.context_refs, [issueSource]);
      assert.match(launch.props.instructions, /^Keep my notes\.\n\nInvestigate this recorded issue: Check the boundary$/);
      editor.update({ preparedTheory: { issue } }); await editor.settle();
      assert.equal(launchElement(editor).props.instructions.split("Investigate this recorded issue:").length, 2);
      assert.equal(launchElement(editor).props.request.context_refs.length, 1);
    } finally { editor.unmount(); }
  });
});

test("a P4-authored task carried into P3 keeps its exact source with neutral selected-source copy", async () => {
  const issueSource = { ...theory, phase: "P4", family: "attention_items", kind: "phase_issue", generation_id: "attention.current-p4", sha256: "c".repeat(64), run_id: "run.evaluation", package_id: "package.evaluation", entry_pointer: "/items/0", object_id: "issue.ledger" };
  const issue = { issue_id: "issue.ledger", kind: "research_task", title: "Clarify the retained theory", branch: "method.a", phase: "P4", target_phase: "P3", explanation_target: issueSource };
  const text = tree => Array.isArray(tree) ? tree.map(text).join("") : tree?.props ? text(tree.props.children) : typeof tree === "string" || typeof tree === "number" ? String(tree) : "";
  const props = { ...cardProps("issue.cross-phase"), issues: [issue] };
  await withApi({ phasePreparation: async () => ({ instructions: "Keep my notes." }) }, async () => {
    let editor = card({ ...props, preparedTheory: { issue } });
    try {
      await editor.settle();
      const group = find(editor, node => node.type === "section" && text(node).includes("Additional selected issue sources"));
      assert.ok(group);
      assert.match(text(group), /These selected sources remain attached to your request\./);
      assert.match(text(group), /Selected source 1/);
      assert.doesNotMatch(text(group), /earlier|replaced/i);
      assert.equal(find(editor, node => node.props.type === "checkbox"), undefined, "Carrying the source does not widen the current-phase issue list.");
      assert.deepEqual(launchElement(editor).props.request.context_refs, [issueSource]);
      const key = ui.furtherWorkKey(props.projectId, props.methodId, "P3");
      assert.deepEqual(ui.readConversationDraft(key).selectedRefs, [issueSource]);
      editor.unmount(); editor = card(props); await editor.settle();
      assert.deepEqual(launchElement(editor).props.request.context_refs, [issueSource], "The exact cross-phase reference survives a return to preparation.");
      find(editor, node => text(node) === "Remove selected source 1" && node.props.onClick).props.onClick(); await editor.settle();
      assert.deepEqual(launchElement(editor).props.request.context_refs, []);
      assert.deepEqual(ui.readConversationDraft(key).selectedRefs, []);
      assert.equal(find(editor, node => node.type === "h3" && text(node) === "Additional selected issue sources"), undefined);
    } finally { editor.unmount(); }
  });
});

test("targeted launch retains assessment and context payloads until explicit submit, then consumes only its scope", async () => {
  const starts = []; const started = []; const assessment = { assessment_id: "assessment.exact", target, summary: "The boundary needs qualification." };
  const assessmentRequest = ui.assessmentRepairRequest(assessment);
  await withApi({ phasePreparation: async () => ({ instructions: "My actual instruction." }), readiness: async () => readiness(), startRun: async (_, value) => { starts.push(value); return { run_id: "run.new", state: "requested" }; } }, async () => {
    const editor = card({ ...cardProps("assessment.payload"), preparedTheory: { request: assessmentRequest, modelRef: methodRef }, onStarted: run => started.push(run) }); let form;
    try {
      await editor.settle(); const element = launchElement(editor); form = mount(element.type, element.props); await form.settle();
      assert.deepEqual(starts, []); assert.equal(submit(form).props.disabled, false); assert.equal(submit(form).props.children, "Start theory revision");
      assert.equal(find(form, node => node.type === "p" && node.props.className === "context-note"), undefined, "The embedded focus line already explains scope and consequences.");
      await submitForm(form); await form.settle(); await editor.settle();
      assert.equal(starts.length, 1); assert.equal(started.length, 1);
      const payload = starts[0]; assert.equal(payload.phase, "P3"); assert.equal(payload.branch_id, "method.a");
      assert.equal(payload.mode, "p3.theory_revision"); assert.equal(payload.intent, "run"); assert.deepEqual(payload.target, target);
      assert.equal(payload.assessment_id, assessment.assessment_id); assert.equal(payload.basis_sha256, "current-basis");
      assert.equal(payload.instructions, `${assessmentRequest.instructions}\n\nMy actual instruction.`);
      assert.equal(launchElement(editor).props.request.target, undefined); assert.equal(launchElement(editor).props.instructions, "My actual instruction.");
    } finally { form?.unmount(); editor.unmount(); }
  });
});

test("changed or missing exact source and method block launch while the retained scope remains inspectable", async () => {
  const scoped = { ...request, methodRef };
  assert.equal(ui.targetIsStale(scoped, theory, methodRef, true), false);
  for (const [currentTheory, currentMethod, aligned] of [
    [null, methodRef, true], [{ ...theory, generation_id: "theory.new" }, methodRef, true],
    [theory, { ...methodRef, version: 2 }, true], [theory, { ...methodRef, definition_sha256: "c".repeat(64) }, true],
    [theory, null, true], [theory, { stable_id: methodRef.stable_id }, true], [theory, methodRef, false],
    [{ ...theory, branch: "method.other" }, methodRef, true],
  ]) assert.equal(ui.targetIsStale(scoped, currentTheory, currentMethod, aligned), true);
  assert.equal(ui.targetIsStale({ ...scoped, branch: "method.other" }, theory, methodRef, true), true);
  const starts = []; const statuses = [];
  await withApi({ readiness: async () => readiness(), startRun: async (_, value) => starts.push(value) }, async () => {
    const form = mount(ui.LaunchRun, { projectId: "stale.scope", request: scoped, currentTargetRef: null, currentMethodRef: methodRef, currentTheoryAligned: true, embedded: true, mode: "p3.theory_revision", instructions: "Kept prose", onPreparationStatus: status => statuses.push(status), onStarted: noop });
    try {
      await form.settle(); assert.equal(submit(form).props.disabled, true); assert.equal(statuses.at(-1).inputsReady, false);
      assert.ok(find(form, node => node.props.role === "alert")); await submitForm(form); assert.deepEqual(starts, []);
      assert.equal(find(form, node => node.type === "textarea").props.value, "Kept prose");
      form.update({ currentTargetRef: theory }); await form.settle(); assert.equal(submit(form).props.disabled, false);
      form.update({ mode: "p3.theory_establishment" }); await form.settle(); assert.equal(submit(form).props.disabled, true);
      await submitForm(form); assert.deepEqual(starts, [], "A cached incompatible mode cannot bypass the focused request's allowed mode.");
    } finally { form.unmount(); }
  });
});

test("launch failure preserves preparation and successful pending launch cannot clear a newer prepared target", async () => {
  const pending = defer(); let rejectFirst = true;
  await withApi({ phasePreparation: async () => ({ instructions: "Preserve these notes." }), readiness: async () => readiness(), startRun: async () => { if (rejectFirst) throw new Error("Research basis is stale"); return pending.promise; } }, async () => {
    const props = cardProps("scope.pending"); const editor = card({ ...props, preparedTheory: { request, modelRef: methodRef } }); let form;
    try {
      await editor.settle(); let element = launchElement(editor); form = mount(element.type, element.props); await form.settle();
      await submitForm(form); await form.settle(); await editor.settle(); assert.deepEqual(launchElement(editor).props.request.target, target);
      form.unmount(); rejectFirst = false; element = launchElement(editor); form = mount(element.type, element.props); await form.settle();
      const launchPending = submitForm(form);
      const next = ui.theoryComponentRequest("repair", { ...target, object_id: "claim.new" }, "New selected claim");
      editor.update({ preparedTheory: { request: next, modelRef: methodRef } }); await editor.settle();
      pending.resolve({ run_id: "run.submitted", state: "requested" }); await launchPending; await form.settle(); await editor.settle();
      assert.deepEqual(launchElement(editor).props.request.target, next.target);
      assert.equal(launchElement(editor).props.instructions, "Preserve these notes.");
    } finally { form?.unmount(); editor.unmount(); }
  });
});

test("a submitted editor's completion cannot overwrite preparation made after navigating away and back", async () => {
  const pending = defer(); const props = cardProps("scope.remounted");
  await withApi({ phasePreparation: async () => ({ instructions: "Original prose." }), readiness: async () => readiness(), startRun: async () => pending.promise }, async () => {
    let editor = card({ ...props, preparedTheory: { request, modelRef: methodRef } }); let form;
    try {
      await editor.settle(); const element = launchElement(editor); form = mount(element.type, element.props); await form.settle();
      const launching = submitForm(form); editor.unmount();
      const next = ui.theoryComponentRequest("repair", { ...target, object_id: "claim.remounted" }, "Remounted claim");
      editor = card({ ...props, preparedTheory: { request: next, modelRef: methodRef } }); await editor.settle();
      launchElement(editor).props.onInstructionsChange("Newer prose after returning."); await editor.settle();
      const key = ui.furtherWorkKey(props.projectId, props.methodId, "P3"); const before = structuredClone(ui.readConversationDraft(key));
      pending.resolve({ run_id: "run.old-instance", state: "requested" }); await launching; await form.settle();
      assert.deepEqual(ui.readConversationDraft(key), before);
      assert.deepEqual(launchElement(editor).props.request.target, next.target);
      assert.equal(launchElement(editor).props.instructions, "Newer prose after returning.");
    } finally { form?.unmount(); editor.unmount(); }
  });
});

test("completion after a phase return clears the same consumed focus in the newly mounted editor", async () => {
  const pending = defer(); const props = cardProps("scope.remounted-same");
  await withApi({ phasePreparation: async () => ({ instructions: "Saved prose." }), readiness: async () => readiness(), startRun: async () => pending.promise }, async () => {
    let editor = card({ ...props, preparedTheory: { request, modelRef: methodRef } }); let form;
    try {
      await editor.settle(); const element = launchElement(editor); form = mount(element.type, element.props); await form.settle();
      const launching = submitForm(form); editor.unmount(); editor = card(props); await editor.settle();
      assert.deepEqual(launchElement(editor).props.request.target, target);
      launchElement(editor).props.onInstructionsChange("New notes after returning."); await editor.settle();
      pending.resolve({ run_id: "run.same-scope", state: "requested" }); await launching; await form.settle(); await editor.settle();
      assert.equal(launchElement(editor).props.request.target, undefined);
      assert.equal(launchElement(editor).props.instructions, "New notes after returning.");
      assert.equal(ui.readConversationDraft(ui.furtherWorkKey(props.projectId, props.methodId, "P3")).text, "New notes after returning.");
    } finally { form?.unmount(); editor.unmount(); }
  });
});

test("a pending prose save cannot overwrite target, sources or newer text after a phase return", async () => {
  for (const returningText of ["New returning prose.", "Submitted prose."]) {
    const pending = defer(); const props = cardProps(`save.remounted.${returningText}`);
    await withApi({ phasePreparation: async () => ({ instructions: "Original saved prose." }), savePhasePreparation: async () => pending.promise }, async () => {
      let editor = card({ ...props, preparedTheory: { request, modelRef: methodRef } });
      try {
        await editor.settle(); launchElement(editor).props.onInstructionsChange("Submitted prose."); await editor.settle();
        const saving = launchElement(editor).props.beforeActions.props.children[0].props.onClick(); editor.unmount();
        const next = ui.theoryComponentRequest("repair", { ...target, object_id: "claim.during-save" }, "During-save selection");
        editor = card({ ...props, preparedTheory: { request: next, modelRef: methodRef } }); await editor.settle();
        const source = { ...theory, family: "attention_items", kind: "phase_issue", object_id: "issue.during-save", entry_pointer: "/items/1" };
        editor.update({ preparedTheory: { issue: { title: "Check a new regime", explanation_target: source } } }); await editor.settle();
        launchElement(editor).props.onInstructionsChange(returningText); await editor.settle();
        const key = ui.furtherWorkKey(props.projectId, props.methodId, "P3"); const before = structuredClone(ui.readConversationDraft(key));
        pending.resolve({ instructions: "Submitted prose." }); await saving; await editor.settle();
        const after = ui.readConversationDraft(key);
        assert.deepEqual(after.theoryPreparation, before.theoryPreparation); assert.deepEqual(after.selectedRefs, [source]);
        assert.equal(after.text, returningText === "Submitted prose." ? undefined : returningText);
        assert.equal(launchElement(editor).props.instructions, returningText); assert.deepEqual(launchElement(editor).props.request.target, next.target);
      } finally { editor.unmount(); }
    });
  }
});
