import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { readDecisionDraft } from "../src/empiricalProgress.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-answer-restore-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; export {EmpiricalPause as Pause} from '${src}/components/EmpiricalProgress.jsx'; export {ActionButton} from '${src}/components/Visuals.jsx'; export {api} from '${src}/api.js'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const button = (tree, label) => nodes(tree).find(node => node.type === ui.ActionButton && node.props.children === label);

// Exercise the editor's actual effects and handlers, including draft persistence.
function mount(props) {
  const editor = ui.Pause(props); const slots = []; let cursor = 0; let effects = []; let dirty = true; let tree;
  const state = initial => {
    const index = cursor++; if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial };
    return [slots[index].value, update => { const next = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; } }];
  };
  const hooks = {
    useState: state,
    useEffect(run, dependencies) {
      const index = cursor++; const previous = slots[index];
      if (!previous || dependencies.some((value, offset) => !Object.is(value, previous.dependencies?.[offset]))) { slots[index] = { dependencies }; effects.push(run); }
    },
    useRef(initial) { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; },
    useId() { const index = cursor++; return (slots[index] ||= { value: `restore-${index}` }).value; },
  };
  return { settle() {
    for (let i = 0; i < 20; i++) {
      if (!dirty) return tree;
      cursor = 0; effects = []; dirty = false; const previous = ui.dispatcher.current;
      try { ui.dispatcher.current = hooks; tree = editor.type(editor.props); } finally { ui.dispatcher.current = previous; }
      for (const run of effects) run();
    }
    throw new Error("The evaluation answer editor did not settle.");
  } };
}

for (const [origin, scope] of [["unknown", { kind: "project" }], ["evidence_supported", { kind: "model" }]]) {
  test(`restoring a scoped ${origin} answer restores its clean state and subsequent save semantics`, async () => {
    const request = { request_id: `restore.${origin}`, revision: 1, question: "What is known?", scope };
    const saved = { request_id: request.request_id, request_revision: 1, revision: 3, note: "No data yet.", origin };
    const props = { projectId: `project.${origin}`, run: { run_id: `run.${origin}`, state: "awaiting_user", p4_progress: { saved_answer: saved } }, request };
    const before = structuredClone(saved); const calls = []; const original = { save: ui.api.saveDecisionAnswer, context: ui.api.problemContext, continue: ui.api.continueRun };
    ui.api.problemContext = async () => ({ revision: 7 });
    ui.api.saveDecisionAnswer = async (projectId, runId, payload) => { calls.push(["save", payload]); return { saved_answer: { ...saved, note: payload.note, revision: 4 } }; };
    ui.api.continueRun = async (projectId, runId, payload) => { calls.push(["continue", payload]); };
    try {
      let app = mount(props); let tree = app.settle();
      assert.equal(button(tree, "Save updated response").props.disabled, true);
      button(tree, "No data yet").props.onClick(); tree = app.settle();
      assert.ok(button(tree, "Use saved response"), "An origin-only change is an unsaved edit.");
      app = mount(props); tree = app.settle();
      assert.ok(button(tree, "Use saved response"), "Reopening retains an origin-only edit even when its words match the saved answer.");
      button(tree, "Use saved response").props.onClick(); tree = app.settle();
      assert.equal(button(tree, "Use saved response"), undefined);
      assert.equal(button(tree, "Save updated response").props.disabled, true);
      assert.equal(button(tree, "Continue with instructions").props.disabled, false);
      const revised = "Keep this saved assessment while refining its wording.";
      nodes(tree).find(node => node.type === "textarea").props.onChange({ target: { value: revised } }); tree = app.settle();
      await button(tree, "Save updated response").props.onClick(); tree = app.settle();
      assert.deepEqual(calls[0], ["save", { request_id: request.request_id, expected_revision: 1, expected_answer_revision: 3, note: revised, origin,
        ...(scope.kind === "project" ? { save_to_context: true, context_expected_revision: 7 } : {}) }]);
      assert.equal(button(tree, "Continue with instructions").props.disabled, false);
      await button(tree, "Continue with instructions").props.onClick(); app.settle();
      assert.equal(calls[1][0], "continue"); assert.equal(calls[1][1].answer_revision, 4);
      assert.deepEqual(saved, before);
    } finally { ui.api.saveDecisionAnswer = original.save; ui.api.problemContext = original.context; ui.api.continueRun = original.continue; }
  });
}

test("matching legacy draft semantics adopt the newest saved revision while differing origins remain edits", () => {
  const saved = { note: "Unchanged words.", revision: 4 };
  const storage = value => ({ getItem: () => JSON.stringify(value) });
  assert.deepEqual(readDecisionDraft("legacy", saved, storage({ note: saved.note, base_revision: 1, origin: "researcher_reported" })), { note: saved.note, base_revision: 4 });
  assert.deepEqual(readDecisionDraft("unknown", saved, storage({ note: saved.note, base_revision: 1, origin: "unknown" })), { note: saved.note, base_revision: 1, origin: "unknown" });
});
