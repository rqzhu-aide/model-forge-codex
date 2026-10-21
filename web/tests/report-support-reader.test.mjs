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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-report-support-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {TechnicalReportDocument,ReportMaterialLink,ReportMaterialDialog,retainedReportMaterial} from '${src}/components/TechnicalReportReading.jsx'; export {Dialog,ResearchDocument} from '${src}/components/Shared.jsx'; export {ActionButton} from '${src}/components/Visuals.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = (tree) => Array.isArray(tree) ? tree.flatMap(nodes) : tree && typeof tree === "object" && tree.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (tree, predicate) => nodes(tree).find(predicate);
const deferred = () => { let resolve; const promise = new Promise((done) => { resolve = done; }); return { resolve, promise }; };
const ok = (text) => ({ ok: true, text: async () => text });
const noop = () => {};

// Exercise the shipped hooks and callbacks. Existing Dialog tests cover its DOM
// focus trap; these fixtures verify the support reader passes the return target.
function mount(Component, props, attach = noop) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let tree;
  const state = (initial) => { const index = cursor++; if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial }; return [slots[index].value, (update) => { const next = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; } }]; };
  const effect = (run, dependencies) => { const index = cursor++; const old = slots[index]; if (!old || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) { slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run }); } };
  const hooks = { useState: state, useEffect: effect, useRef: (initial) => { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; }, useId: () => { const index = cursor++; return (slots[index] ||= { value: "support:fixture" }).value; } };
  const draw = () => { cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current; try { ui.dispatcher.current = hooks; tree = Component(props); } finally { ui.dispatcher.current = previous; } attach(tree); for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); } };
  return { get tree() { return tree; }, update(changes) { props = { ...props, ...changes }; dirty = true; }, async settle() { for (let i = 0; i < 25; i++) { if (dirty) draw(); await new Promise((resolve) => setImmediate(resolve)); if (!dirty) return tree; } throw new Error("Reader did not settle."); }, unmount() { for (const slot of slots) slot?.cleanup?.(); } };
}

const support = { artifact_id: "artifact.support", authored_path: "notes/supporting-detail.md", path: "working/research_lead/notes/supporting-detail.md", artifact_url: "/api/v1/exact-support?sha256=a", sha256: "a".repeat(64), source_verified: true, media_type: "text/markdown" };
const figure = { artifact_id: "artifact.figure", authored_path: "figures/risk.svg", artifact_url: "/api/v1/exact-figure", source_verified: true, media_type: "image/svg+xml" };
const values = { artifact_id: "artifact.values", authored_path: "data/values.csv", artifact_url: "/api/v1/exact-values", source_verified: true, media_type: "text/csv" };
const materials = [support, figure, values];
const props = { material: support, fragment: "model", path: support.authored_path, materials, onClose: noop };

test("fragment-aware support lookup resolves nested paths and preserves unique authored-alias precedence", () => {
  assert.deepEqual(ui.retainedReportMaterial(materials, "notes/supporting-detail.md#model"), { material: support, fragment: "model", path: support.authored_path });
  assert.equal(ui.retainedReportMaterial(materials, "./notes/supporting-detail.md#model").material, support);
  assert.equal(ui.retainedReportMaterial(materials, "../data/values.csv#row%201", support.authored_path).material, values);
  assert.equal(ui.retainedReportMaterial(materials, "../data/values.csv#row%201", support.authored_path).fragment, "row 1");
  assert.equal(ui.retainedReportMaterial(materials, values.artifact_id, support.authored_path).material, values);
  assert.equal(ui.retainedReportMaterial(materials, "../../outside.md", support.authored_path).material, null);
  const native = { ...values, authored_path: undefined, path: support.authored_path };
  assert.equal(ui.retainedReportMaterial([support, native], `${support.authored_path}#model`).material, support);
  assert.equal(ui.retainedReportMaterial([support, { ...support }, native], `${support.authored_path}#model`).material, null);
  assert.equal(ui.retainedReportMaterial([{ ...support, source_verified: false }, native], `${support.authored_path}#model`).material.source_verified, false);
});

test("main links open verified Markdown in a dialog while other exact files retain direct links and fragments", async () => {
  const document = { kind: "technical_report", generation_ref: { generation_id: "report.exact" }, body_md: "[Supporting model](notes/supporting-detail.md#model) and [Values](data/values.csv#row).", report_materials: materials };
  const before = structuredClone(document);
  const tree = ui.TechnicalReportDocument({ document });
  const body = find(tree, (node) => node.type === ui.ResearchDocument && node.props.renderFileLink);
  const link = body.props.renderFileLink("notes/supporting-detail.md#model", "Supporting model");
  assert.equal(link.type, ui.ReportMaterialLink); assert.equal(link.props.fragment, "model");
  const fixture = mount(link.type, link.props); await fixture.settle();
  let prevented = false;
  find(fixture.tree, (node) => node.type === "a").props.onClick({ preventDefault() { prevented = true; } });
  await fixture.settle();
  const dialog = find(fixture.tree, (node) => node.type === ui.ReportMaterialDialog);
  assert.equal(prevented, true); assert.equal(dialog.props.returnFocus, find(fixture.tree, (node) => node.type === "a").ref);
  fixture.update({ materials: structuredClone(materials) }); await fixture.settle();
  assert.ok(find(fixture.tree, (node) => node.type === ui.ReportMaterialDialog), "Polling retains the open reader.");
  dialog.props.onClose(); await fixture.settle();
  assert.equal(find(fixture.tree, (node) => node.type === ui.ReportMaterialDialog), undefined);
  const html = ui.render(ui.TechnicalReportDocument, { document });
  assert.match(html, /href="\/api\/v1\/exact-values#row"/);
  assert.match(html, /class="source-link ui-action" data-ui-role="system"[^>]*><svg[^>]*data-icon="source"/);
  assert.doesNotMatch(html, /Supporting model: The exact retained file is unavailable/);
  const invalid = ui.render(ui.TechnicalReportDocument, { document: { ...document, report_materials: [{ ...support, source_verified: false }] } });
  assert.match(invalid, /Supporting model: The exact retained file is unavailable/);
  assert.deepEqual(document, before);
});

test("loaded supporting detail renders LaTeX and nested exact files, focuses its fragment and retains position on polling", async () => {
  const oldFetch = globalThis.fetch; const reads = []; const focused = [];
  const text = '<a id="model"></a>\n## Supporting model\n\n$$x^2=1$$\n\n![Risk](../figures/risk.svg)\n\n[Values](../data/values.csv#row) and [Local model](#model).';
  globalThis.fetch = async (url) => { reads.push(url); return ok(text); };
  const anchor = { dataset: { materialAnchor: "model" }, scrollIntoView: (options) => focused.push(["scroll", options]), focus: (options) => focused.push(["focus", options]) };
  const root = { querySelectorAll: () => [anchor], scrollIntoView: noop, focus: noop };
  const fixture = mount(ui.ReportMaterialDialog, props, (tree) => { const container = find(tree, (node) => node.type === "div" && node.ref); if (container) container.ref.current = root; });
  try {
    await fixture.settle();
    assert.deepEqual(reads, [support.artifact_url]); assert.deepEqual(focused, [["scroll", { block: "start" }], ["focus", { preventScroll: true }]]);
    const body = find(fixture.tree, (node) => node.type === ui.ResearchDocument);
    const html = ui.render(ui.ResearchDocument, body.props);
    assert.match(html, /class="katex-display"/); assert.doesNotMatch(html, /katex-error|report-section-discuss/);
    assert.match(html, /src="\/api\/v1\/exact-figure"/); assert.match(html, /href="\/api\/v1\/exact-values#row"/);
    assert.match(html, /data-material-anchor="model" tabindex="-1"/);
    const encoded = body.props.renderAnchor('a"#[]'); assert.match(encoded.props.id, /^[a-zA-Z0-9_-]+$/);
    body.props.renderInternalLink("#model", "Model").props.onClick({ preventDefault: noop });
    assert.equal(focused.length, 4);
    fixture.update({ material: { ...support }, materials: structuredClone(materials) }); await fixture.settle();
    assert.equal(reads.length, 1); assert.equal(focused.length, 4);
    assert.equal(body.props.renderFileLink("supporting-detail.md#model", "Same file").type, ui.ReportMaterialLink);
  } finally { fixture.unmount(); globalThis.fetch = oldFetch; }
});

test("support reader exposes load errors and retry, and ignores a late response after its source changes", async () => {
  const oldFetch = globalThis.fetch; const stale = deferred(); let calls = 0;
  globalThis.fetch = () => { calls++; return calls === 1 ? stale.promise : calls === 2 ? Promise.resolve({ ok: false, status: 409 }) : Promise.resolve(ok("## Exact replacement\n\n$x=2$.")); };
  const fixture = mount(ui.ReportMaterialDialog, props);
  try {
    await fixture.settle(); assert.ok(find(fixture.tree, (node) => node.props.role === "status"));
    fixture.update({ material: { ...support, artifact_url: "/api/v1/replacement", sha256: "b".repeat(64) } }); await fixture.settle();
    assert.match(find(fixture.tree, (node) => node.props.role === "alert").props.children[0], /409/);
    find(fixture.tree, (node) => node.type === ui.ActionButton).props.onClick(); await fixture.settle();
    stale.resolve(ok("STALE source")); await fixture.settle();
    assert.equal(find(fixture.tree, (node) => node.type === ui.ResearchDocument).props.text, "## Exact replacement\n\n$x=2$.");
    assert.equal(calls, 3);
  } finally { fixture.unmount(); globalThis.fetch = oldFetch; }
});
