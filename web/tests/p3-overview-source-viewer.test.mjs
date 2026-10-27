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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p3-source-viewer-"));
const bundle = path.join(directory, "integration.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `export {default as React} from 'react'; export {api} from '${src}/api.js'; export {default as ProjectView} from '${src}/components/ProjectView.jsx'; export {PhaseOverview,ScientificDocuments} from '${src}/components/PhaseReading.jsx'; export {Dialog,ResearchDocument,SourceRef} from '${src}/components/Shared.jsx';`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (tree, type) => nodes(tree).find(node => node.type === type);

// Run the actual component callbacks and state. Browser layout is checked
// separately; these fixtures make navigation and source identity observable.
function hooks() {
  const slots = [], pending = [], cleanup = []; let cursor = 0;
  const dispatcher = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;
  const implementation = {
    useState(initial) { const index = cursor++; if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
    useRef(initial) { return slots[cursor++] ||= { current: initial }; },
    useId() { return `fixture-${cursor++}`; },
    useLayoutEffect() { cursor++; },
    useEffect(effect, dependencies) { const index = cursor++; if (!slots[index] || !dependencies || dependencies.some((value, i) => value !== slots[index][i])) pending.push(effect); slots[index] = dependencies || []; },
  };
  return {
    render(component, props) { cursor = 0; const before = dispatcher.current; dispatcher.current = implementation; try { return component(props); } finally { dispatcher.current = before; } },
    async load() { for (const effect of pending.splice(0)) { const end = effect(); if (typeof end === "function") cleanup.push(end); } await new Promise(setImmediate); },
    close() { cleanup.forEach(end => end()); },
  };
}

test("overview proof opens the exact readable theory in the existing dialog and closes without reader navigation", async () => {
  const originals = { api: { ...ui.api }, window: globalThis.window, document: globalThis.document };
  const harness = hooks(); const requests = [], navigation = [], readingChanges = [];
  const proof = { branch: "method.a", phase: "P3", family: "theory_record", generation_id: "generation.original-proof", sha256: "a".repeat(64), run_id: "run.original", package_id: "package.original" };
  const decision = { phase: "P3", branch: "method.a", conclusion: "The bound holds under the stated assumptions. See [full proof and interpretation](artifact://proof).", generation_ref: { ...proof, family: "decision", generation_id: "generation.original-decision" }, inline_sources: [{ uri: "artifact://proof", source_verified: true, generation_ref: proof }] };
  const body = { phase: "P3", kind: "theory_record", generation_ref: proof, body_md: "# Full proof\n\nThe complete retained argument.", structured: { statements: [] } };
  globalThis.window = { addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: true }) };
  globalThis.document = { hidden: false, addEventListener() {}, removeEventListener() {} };
  Object.assign(ui.api, {
    project: async () => ({ project: { name: "Proof source fixture" } }), branches: async () => ({ branches: [] }), listRuns: async () => ({ runs: [] }),
    artifacts: async () => ({ decisions: [decision] }), decisionsPending: async () => ({}), readiness: async () => ({}), records: async () => ({ records: [] }), assessments: async () => ({ assessments: [] }),
    methods: async () => ({ methods: [{ method_id: "method.a", branch_id: "method.a", title: "Method A" }] }),
    recordDocument: async (projectId, reference) => { requests.push([projectId, reference]); return body; },
    recordBody: async () => { throw new Error("The full proof needs the readable document, not a raw record."); },
  });
  const reading = { selectedNode: "claim.bound", theory: { tab: "arguments" } };
  const props = { projectId: "project.fixture", context: { branch: "method.a", phase: "P3" }, reading, onReadingChange: value => readingChanges.push(value), onContextChange: value => navigation.push(value) };
  const render = () => harness.render(ui.ProjectView, props);
  try {
    render(); await harness.load();
    const initial = render();
    const overview = find(initial, ui.PhaseOverview);
    assert.ok(overview);
    const account = find(ui.PhaseOverview(overview.props), ui.ResearchDocument);
    const link = account.props.renderSourceLink("artifact://proof", "full proof and interpretation");
    await ui.SourceRef(link.props).props.onClick();
    const dialog = find(render(), ui.Dialog);
    assert.equal(dialog.props.title, "Research source");
    const document = find(dialog, ui.ScientificDocuments);
    assert.deepEqual(document.props.documents, [body]);
    assert.equal(document.props.showRecordSource, false);
    assert.deepEqual(requests, [["project.fixture", proof]]);
    dialog.props.onClose();
    assert.equal(find(render(), ui.Dialog), undefined);
    assert.deepEqual(navigation, []); assert.deepEqual(readingChanges, []);
    assert.deepEqual(props.reading, reading);
  } finally {
    harness.close(); Object.assign(ui.api, originals.api);
    for (const key of ["window", "document"]) if (originals[key] === undefined) delete globalThis[key]; else globalThis[key] = originals[key];
  }
});

test("source dialog returns focus to the proof citation with preventScroll", async () => {
  const keys = ["document", "MutationObserver", "getComputedStyle"];
  const originals = Object.fromEntries(keys.map(key => [key, globalThis[key]]));
  const harness = hooks(); const events = []; const focusCalls = [];
  const element = name => ({ name, isConnected: true, tabIndex: 0, parentElement: null, getClientRects: () => [{}], closest: () => null, matches: () => false, focus(options) { focusCalls.push([name, options]); globalThis.document.activeElement = this; } });
  const origin = element("proof citation"), close = element("close");
  const box = { ...element("dialog"), querySelectorAll: () => [close], contains: element => element === close };
  globalThis.document = { activeElement: origin, body: { style: { overflow: "" } }, addEventListener: (name, handler) => events.push([name, handler]), removeEventListener() {} };
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block" });
  try {
    const tree = harness.render(ui.Dialog, { title: "Research source", onClose() {} });
    nodes(tree).find(node => node.props.role === "dialog").ref.current = box;
    await harness.load();
    assert.equal(globalThis.document.activeElement, close);
    harness.close();
    assert.equal(globalThis.document.activeElement, origin);
    assert.deepEqual(focusCalls, [["close", { preventScroll: true }], ["proof citation", { preventScroll: true }]]);
  } finally {
    for (const key of keys) if (originals[key] === undefined) delete globalThis[key]; else globalThis[key] = originals[key];
  }
});
