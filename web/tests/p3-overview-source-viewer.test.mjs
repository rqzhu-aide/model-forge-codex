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
await build({ stdin: { contents: `export {default as React} from 'react'; export {renderToStaticMarkup as renderElement} from 'react-dom/server'; export {api} from '${src}/api.js'; export {default as ProjectView} from '${src}/components/ProjectView.jsx'; export {default as ResearchSourceDialog} from '${src}/components/ResearchSourceDialog.jsx'; export {PhaseOverview,ScientificDocuments} from '${src}/components/PhaseReading.jsx'; export {Dialog,ResearchDocument,SourceRef} from '${src}/components/Shared.jsx';`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.$$typeof === Symbol.for("react.portal") ? [tree, ...nodes(tree.children)] : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (tree, type) => nodes(tree).find(node => node.type === type);

test("theory summary keeps every qualification in the account and navigates through its actions", () => {
  const decision = {
    conclusion: "The bound holds only under overlap.", fundamental_contribution: "A conditional bound.",
    principal_uncertainty: "Uniformity remains unproved.", principal_risk: "Rare histories may violate overlap.",
    material_disagreement: ["The analyst contests the intended population."], what_changed: "The claim was narrowed.",
    smallest_decisive_result: "Establish a uniform remainder bound.",
  };
  const original = JSON.stringify(decision); const opened = [];
  const overviewHarness = hooks();
  const tree = overviewHarness.render(ui.PhaseOverview, { phase: "P3", decision, onReadTheory: tab => opened.push(tab) });
  const layout = nodes(tree).find(node => node.props?.label === "Theory supporting reading");
  const texts = nodes(layout.props.children).filter(node => node.type === ui.ResearchDocument).map(node => node.props.text);
  for (const field of Object.values(decision)) assert.ok(texts.includes(field), `Inline scientific qualification: ${field}`);
  const controls = nodes(layout.props.actions);
  controls.find(node => node.props.children === "Arguments and proofs").props.onClick();
  assert.deepEqual(opened, ["arguments"]);
  assert.equal(layout.props.actionsLabel, "Theory actions");
  assert.equal(layout.props.resources, null, "Theory navigation alone does not reserve supporting reading.");
  const html = ui.renderElement(tree);
  assert.ok(html.indexOf("research-card-actions") < html.indexOf("research-card-account"));
  assert.doesNotMatch(html, /research-card-resources|<aside/);
  assert.equal(JSON.stringify(decision), original);
  const empty = overviewHarness.render(ui.PhaseOverview, { phase: "P3", onReadTheory() {} });
  const emptyLayout = nodes(empty).find(node => node.props?.label === "Theory supporting reading");
  assert.equal(emptyLayout.props.resources, null);
  assert.equal(emptyLayout.props.actions, null);
  assert.doesNotMatch(ui.renderElement(empty), /has-rail|research-card-actions|research-card-resources/);
});

test("theory overview retains the reading-only layout", () => {
  const reference = { branch: "method.a", phase: "P3", family: "decision", generation_id: "decision.saved", sha256: "a".repeat(64) };
  const tree = hooks().render(ui.PhaseOverview, { phase: "P3", decision: { conclusion: "Only the stated regime is established.", generation_ref: reference } });
  const layout = nodes(tree).find(node => node.props?.label === "Theory supporting reading");
  assert.equal(layout.props.actions, null);
  const html = ui.renderElement(tree);
  assert.match(html, /research-card-layout has-rail/);
  assert.doesNotMatch(html, /has-actions|research-card-actions|Explore the theory/);
  assert.ok(html.indexOf("research-card-account") < html.indexOf("research-card-resources"));
  assert.deepEqual(nodes(layout.props.resources).find(node => node.type === ui.SourceRef).props.reference, reference);
});

// Run the actual component callbacks and state. Browser layout is checked
// separately; these fixtures make navigation and source identity observable.
function hooks() {
  const slots = [], pending = [], cleanup = []; let cursor = 0;
  const dispatcher = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;
  const implementation = {
    useContext(context) { return context._currentValue; },
    useState(initial) { const index = cursor++; if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
    useRef(initial) { return slots[cursor++] ||= { current: initial }; },
    useId() { return `fixture-${cursor++}`; },
    useLayoutEffect() { cursor++; },
    useEffect(effect, dependencies) { const index = cursor++; if (!slots[index] || !dependencies || dependencies.some((value, i) => value !== slots[index][i])) pending.push(effect); slots[index] = dependencies || []; },
  };
  return {
    render(component, props) { cursor = 0; const before = dispatcher.current; dispatcher.current = implementation; try { return component(props); } finally { dispatcher.current = before; } },
    async load() { for (const effect of pending.splice(0)) { const end = effect(); if (typeof end === "function") cleanup.push(end); } await new Promise(setImmediate); },
    close() { cleanup.splice(0).forEach(end => end()); },
  };
}

test("overview proof opens the exact readable theory in the existing dialog and closes without reader navigation", async () => {
  const originals = { api: { ...ui.api }, window: globalThis.window, document: globalThis.document };
  const harness = hooks(); const sourceHarness = hooks(); const requests = [], navigation = [], readingChanges = [];
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
    const account = find(hooks().render(ui.PhaseOverview, overview.props), ui.ResearchDocument);
    const link = account.props.renderSourceLink("artifact://proof", "full proof and interpretation");
    await ui.SourceRef(link.props).props.onClick();
    const source = find(render(), ui.ResearchSourceDialog);
    assert.deepEqual(source.props.reference, proof);
    sourceHarness.render(source.type, source.props); await sourceHarness.load();
    const dialog = sourceHarness.render(source.type, source.props);
    assert.equal(dialog.props.title, "Research source");
    const document = find(dialog, ui.ScientificDocuments);
    assert.deepEqual(document.props.documents, [body]);
    assert.equal(document.props.showRecordSource, false);
    assert.deepEqual(requests, [["project.fixture", proof]]);
    dialog.props.onClose();
    assert.equal(find(render(), ui.ResearchSourceDialog), undefined);
    assert.deepEqual(navigation, []); assert.deepEqual(readingChanges, []);
    assert.deepEqual(props.reading, reading);
    for (const changed of [
      { projectId: "project.other" },
      { context: { ...props.context, phase: "P4" } },
      { context: { ...props.context, branch: "method.other" } },
      { context: { ...props.context, p2ProposalKey: "proposal.other" } },
    ]) {
      overview.props.onSource(proof);
      assert.ok(find(render(), ui.ResearchSourceDialog));
      assert.equal(find(harness.render(ui.ProjectView, { ...props, ...changed }), ui.ResearchSourceDialog), undefined);
      await harness.load();
      render(); await harness.load();
      assert.equal(find(render(), ui.ResearchSourceDialog), undefined, "A scope change discards its old source stack.");
    }
  } finally {
    harness.close(); sourceHarness.close(); Object.assign(ui.api, originals.api);
    for (const key of ["window", "document"]) if (originals[key] === undefined) delete globalThis[key]; else globalThis[key] = originals[key];
  }
});

test("source dialog returns focus to the proof citation with preventScroll", async () => {
  const keys = ["document", "MutationObserver", "getComputedStyle"];
  const originals = Object.fromEntries(keys.map(key => [key, globalThis[key]]));
  const harness = hooks(); const events = []; const focusCalls = [];
  const element = name => ({ name, isConnected: true, tabIndex: 0, parentElement: null, style: {}, attributes: new Map(), getClientRects: () => [{}],
    getAttribute(name) { return this.attributes.get(name) ?? null; }, setAttribute(name, value) { this.attributes.set(name, value); }, removeAttribute(name) { this.attributes.delete(name); },
    closest() { for (let node = this; node; node = node.parentElement) if (node.attributes?.has("inert")) return node; return null; },
    matches: () => false, focus(options) { focusCalls.push([name, options]); globalThis.document.activeElement = this; } });
  const origin = element("proof citation"), close = element("close");
  const box = { ...element("dialog"), querySelectorAll: () => [close], contains: element => element === close };
  const root = element("app"), backdrop = element("backdrop"); origin.parentElement = root; box.parentElement = backdrop; close.parentElement = box;
  globalThis.document = { activeElement: origin, body: { nodeType: 1, children: [root, backdrop], style: { overflow: "" } }, addEventListener: (name, handler) => events.push([name, handler]), removeEventListener() {} };
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block", zIndex: "50" });
  try {
    const tree = harness.render(ui.Dialog, { title: "Research source", onClose() {} });
    assert.equal(tree.$$typeof, Symbol.for("react.portal")); assert.equal(tree.containerInfo, globalThis.document.body);
    nodes(tree).find(node => node.props?.role === "dialog").ref.current = box;
    await harness.load();
    assert.equal(globalThis.document.activeElement, close);
    assert.equal(root.getAttribute("inert"), "");
    harness.close();
    assert.equal(globalThis.document.activeElement, origin);
    assert.equal(root.getAttribute("inert"), null);
    assert.deepEqual(focusCalls, [["close", { preventScroll: true }], ["proof citation", { preventScroll: true }]]);
  } finally {
    harness.close();
    for (const key of keys) if (originals[key] === undefined) delete globalThis[key]; else globalThis[key] = originals[key];
  }
});
