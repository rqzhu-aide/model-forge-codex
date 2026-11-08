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
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {TechnicalReportDocument,ReportMaterialLink,ReportMaterialDialog,retainedReportMaterial} from '${src}/components/TechnicalReportReading.jsx'; export {reportHtmlPreview,bindReportHtmlFrame} from '${src}/reportHtmlSource.js'; export {Dialog,ResearchDocument} from '${src}/components/Shared.jsx'; export {ActionButton} from '${src}/components/Visuals.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const isPortal = tree => tree?.$$typeof === Symbol.for("react.portal");
const nodes = (tree) => Array.isArray(tree) ? tree.flatMap(nodes) : isPortal(tree) ? [tree, ...nodes(tree.children)] : tree && typeof tree === "object" && tree.props ? [tree, ...nodes(tree.props.children)] : [];
const inlineNodes = tree => Array.isArray(tree) ? tree.flatMap(inlineNodes) : isPortal(tree) ? [] : tree && typeof tree === "object" && tree.props ? [tree, ...inlineNodes(tree.props.children)] : [];
const find = (tree, predicate) => nodes(tree).find(predicate);
const deferred = () => { let resolve; const promise = new Promise((done) => { resolve = done; }); return { resolve, promise }; };
const ok = (text) => ({ ok: true, text: async () => text });
const noop = () => {};
async function withPortalBody(run) {
  const previous = globalThis.document;
  globalThis.document = { body: { nodeType: 1 } };
  try { await run(); }
  finally { if (previous === undefined) delete globalThis.document; else globalThis.document = previous; }
}

// Exercise the shipped hooks and callbacks. Existing Dialog tests cover its DOM
// focus trap; these fixtures verify the support reader passes the return target.
function mount(Component, props, attach = noop) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let tree;
  const state = (initial) => { const index = cursor++; if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial }; return [slots[index].value, (update) => { const next = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; } }]; };
  const effect = (run, dependencies) => { const index = cursor++; const old = slots[index]; if (!old || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) { slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run }); } };
  const hooks = { useState: state, useEffect: effect, useLayoutEffect: effect,
    useCallback: (callback, dependencies) => { const index = cursor++; const old = slots[index]; if (!old || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) slots[index] = { value: callback, dependencies }; return slots[index].value; },
    useRef: (initial) => { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; }, useId: () => { const index = cursor++; return (slots[index] ||= { value: "support:fixture" }).value; } };
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

test("main links open verified Markdown in a dialog while other exact files retain direct links and fragments", async () => withPortalBody(async () => {
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
  const portal = find(fixture.tree, isPortal);
  assert.equal(portal.containerInfo, globalThis.document.body);
  assert.equal(inlineNodes({ type: "p", props: { children: fixture.tree } }).some(node => node.type === ui.ReportMaterialDialog), false, "An inline report paragraph must not contain the modal's block content.");
  assert.equal(prevented, true); assert.equal(dialog.props.returnFocus, find(fixture.tree, (node) => node.type === "a").ref);
  fixture.update({ materials: structuredClone(materials) }); await fixture.settle();
  assert.ok(find(fixture.tree, (node) => node.type === ui.ReportMaterialDialog), "Polling retains the open reader.");
  const replacement = { ...support, artifact_url: "/api/v1/new-support?sha256=b", sha256: "b".repeat(64) };
  fixture.update({ material: replacement, materials: [replacement, figure, values] }); await fixture.settle();
  const retained = find(fixture.tree, (node) => node.type === ui.ReportMaterialDialog);
  assert.equal(retained.props.material.artifact_url, support.artifact_url);
  assert.equal(retained.props.material.sha256, support.sha256, "An open material retains the exact version chosen before polling.");
  dialog.props.onClose(); await fixture.settle();
  assert.equal(find(fixture.tree, (node) => node.type === ui.ReportMaterialDialog), undefined);
  const html = ui.render(ui.TechnicalReportDocument, { document });
  assert.match(html, /href="\/api\/v1\/exact-values#row"/);
  assert.match(html, /class="source-link ui-action" data-ui-role="system"[^>]*><svg[^>]*data-icon="source"/);
  assert.doesNotMatch(html, /Supporting model: The exact retained file is unavailable/);
  const invalid = ui.render(ui.TechnicalReportDocument, { document: { ...document, report_materials: [{ ...support, source_verified: false }] } });
  assert.match(invalid, /Supporting model: The exact retained file is unavailable/);
  assert.deepEqual(document, before);
}));

test("Markdown material restores its exact loaded position and disclosures, with fragments taking precedence", async () => {
  const oldFetch = globalThis.fetch;
  const text = "## Supporting model\n\nA retained explanation.";
  const material = { ...support, artifact_url: "/api/v1/markdown-position", sha256: "d".repeat(64), label: "Model derivation" };
  const make = (fragment = "", source = material) => {
    const detail = { open: false }, body = { scrollTop: 0, querySelectorAll: () => [detail] };
    const anchor = { dataset: { materialAnchor: "model" }, scrollIntoView: () => { body.scrollTop = 45; }, focus: noop };
    const root = { querySelectorAll: () => [anchor] };
    const fixture = mount(ui.ReportMaterialDialog, { ...props, material: source, fragment }, tree => {
      find(tree, node => node.type === ui.Dialog).props.bodyRef.current = body;
      const content = find(tree, node => node.type === "div" && node.ref); if (content) content.ref.current = root;
    });
    return { fixture, body, detail };
  };
  const opened = [];
  try {
    globalThis.fetch = async () => ok(text);
    const first = make(); opened.push(first.fixture); await first.fixture.settle();
    assert.equal(find(first.fixture.tree, node => node.type === ui.Dialog).props.title, "Model derivation");
    first.body.scrollTop = 370; first.detail.open = true; first.fixture.unmount();
    const pending = deferred(); globalThis.fetch = () => pending.promise;
    const second = make(); opened.push(second.fixture); await second.fixture.settle();
    assert.equal(second.body.scrollTop, 0, "Loading UI must not consume the saved offset.");
    pending.resolve(ok(text)); await second.fixture.settle();
    assert.equal(second.body.scrollTop, 370); assert.equal(second.detail.open, true);
    second.fixture.unmount();
    globalThis.fetch = async () => ok(text);
    const target = make("model"); opened.push(target.fixture); await target.fixture.settle();
    assert.equal(target.body.scrollTop, 45, "A requested section wins over the saved reading position.");
    target.fixture.unmount();
    const revised = make("", { ...material, sha256: "e".repeat(64) }); opened.push(revised.fixture); await revised.fixture.settle();
    assert.equal(revised.body.scrollTop, 0); assert.equal(revised.detail.open, false, "A different hash has its own position.");
  } finally { for (const fixture of opened) fixture.unmount(); globalThis.fetch = oldFetch; }
});

test("HTML material restores frame scroll and disclosures after load without overriding explicit fragments", async () => withPortalBody(async () => {
  const oldFetch = globalThis.fetch;
  globalThis.document.createElement = () => ({ innerHTML: "", content: { querySelectorAll: () => [] } });
  globalThis.fetch = async () => ok("<h1>Exact proof</h1>");
  const material = { ...support, artifact_url: "/api/v1/html-position", sha256: "f".repeat(64), authored_path: "proof.html", media_type: "text/html", title: "Identification proof" };
  const make = (fragment = "", source = material) => {
    const events = new Map(), detail = { open: false };
    const scrolling = { scrollTop: 0, querySelectorAll: () => [detail] };
    const body = { setAttribute: noop, scrollIntoView: () => { scrolling.scrollTop = 0; }, focus: noop };
    const anchor = { id: "proof", setAttribute: noop, scrollIntoView: () => { scrolling.scrollTop = 65; }, focus: noop };
    const sourceDocument = { body, scrollingElement: scrolling, querySelectorAll: () => [anchor], addEventListener: (name, fn) => events.set(name, fn), removeEventListener: name => events.delete(name) };
    const frame = { contentDocument: sourceDocument };
    const fixture = mount(ui.ReportMaterialDialog, { ...props, material: source, fragment }, tree => {
      const node = find(tree, node => node.type === "iframe"); if (node) node.ref.current = frame;
    });
    return { fixture, scrolling, detail, events };
  };
  const opened = [];
  try {
    const first = make(); opened.push(first.fixture); await first.fixture.settle();
    const preview = find(first.fixture.tree, node => node.type === "iframe");
    assert.equal(preview.props.title, "Identification proof retained HTML"); assert.equal(preview.props.sandbox, "allow-same-origin");
    preview.props.onLoad(); first.scrolling.scrollTop = 420; first.detail.open = true;
    first.events.get("scroll")(); first.fixture.unmount();
    const second = make(); opened.push(second.fixture); await second.fixture.settle();
    assert.equal(second.scrolling.scrollTop, 0);
    find(second.fixture.tree, node => node.type === "iframe").props.onLoad();
    assert.equal(second.scrolling.scrollTop, 420); assert.equal(second.detail.open, true);
    second.fixture.unmount();
    const target = make("proof"); opened.push(target.fixture); await target.fixture.settle();
    find(target.fixture.tree, node => node.type === "iframe").props.onLoad();
    assert.equal(target.scrolling.scrollTop, 65); assert.equal(target.detail.open, false);
    target.fixture.unmount();
    const revised = make("", { ...material, sha256: "0".repeat(64) }); opened.push(revised.fixture); await revised.fixture.settle();
    find(revised.fixture.tree, node => node.type === "iframe").props.onLoad();
    assert.equal(revised.scrolling.scrollTop, 0); assert.equal(revised.detail.open, false);
  } finally { for (const fixture of opened) fixture.unmount(); globalThis.fetch = oldFetch; }
}));

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

test("an exact declared HTML proof opens its own reader without guessing a Markdown rendition", () => {
  const html = { ...support, artifact_id: "artifact.proof-html", authored_path: "appendix.html", path: "working/research_lead/appendix.html", artifact_url: "/api/v1/exact-proof?sha256=c", sha256: "c".repeat(64), media_type: "text/html" };
  const markdown = { ...support, artifact_id: "artifact.proof-md", authored_path: "appendix.md" };
  const document = { kind: "technical_report", body_md: "[Proof](appendix.html#proof-safety)", report_materials: [html, markdown] };
  const tree = ui.TechnicalReportDocument({ document });
  const body = find(tree, (node) => node.type === ui.ResearchDocument && node.props.renderFileLink);
  const link = body.props.renderFileLink("appendix.html#proof-safety", "Proof");
  assert.equal(link.type, ui.ReportMaterialLink);
  assert.equal(link.props.material, html); assert.equal(link.props.fragment, "proof-safety");
  const missing = ui.TechnicalReportDocument({ document: { ...document, report_materials: [markdown] } });
  assert.match(ui.render(() => find(missing, (node) => node.type === ui.ResearchDocument).props.renderFileLink("appendix.html#proof-safety", "Proof"), {}), /exact retained file is unavailable/);
  const unsafe = ui.TechnicalReportDocument({ document: { ...document, report_materials: [{ ...html, source_verified: false }, markdown] } });
  assert.match(ui.render(() => find(unsafe, (node) => node.type === ui.ResearchDocument).props.renderFileLink("appendix.html#proof-safety", "Proof"), {}), /exact retained file is unavailable/);
  // Fresh P5 projection deliberately uses binary download media for HTML, while
  // preserving the same exact declared path, hash, URL and verified status.
  const projected = { ...html, artifact_id: "artifact.p5.proof-appendix-html", media_type: "application/octet-stream" };
  const projectedTree = ui.TechnicalReportDocument({ document: { ...document, report_materials: [projected, markdown] } });
  const projectedLink = find(projectedTree, (node) => node.type === ui.ResearchDocument).props.renderFileLink("appendix.html#proof-safety", "Proof");
  assert.equal(projectedLink.type, ui.ReportMaterialLink); assert.equal(projectedLink.props.material, projected);
  assert.equal(projectedLink.props.material.sha256, html.sha256); assert.equal(projectedLink.props.material.artifact_url, html.artifact_url);
});

test("the report's standalone download targets its generation attachment and requires one verified Markdown companion", () => {
  const html = { ...support, artifact_id: "artifact.proof-html", authored_path: "appendix.html", media_type: "text/html" };
  const markdown = { ...support, artifact_id: "artifact.proof-md", authored_path: "appendix.md" };
  const document = { kind: "technical_report", body_md: "# Report", report_materials: [html, markdown],
    generation_ref: { branch: "method.example", phase: "P5", family: "technical_report", generation_id: "generation.exact", sha256: "c".repeat(64) },
    portable_artifact_url: "/api/v1/report/generation.exact?view=portable" };
  const tree = ui.TechnicalReportDocument({ document });
  const download = find(tree, node => node.type === "a" && node.props["aria-label"]?.startsWith("Download standalone"));
  assert.ok(download);
  assert.equal(download.props.href, "/api/v1/report/generation.exact?view=attachment&material_id=artifact.proof-html");
  assert.equal(download.props.download, "appendix.shareable.html");
  for (const materials of [[html], [html, markdown, { ...markdown, artifact_id: "other" }], [html, { ...markdown, source_verified: false }]]) {
    assert.equal(find(ui.TechnicalReportDocument({ document: { ...document, report_materials: materials } }), node => node.type === "a" && node.props["aria-label"]?.startsWith("Download standalone")), undefined);
  }
});

test("HTML preview keeps scientific markup inert, blocks active/network content and controls every source link", () => {
  const node = (localName, attributes = {}) => ({ localName, values: { ...attributes }, removed: false,
    get attributes() { return Object.keys(this.values).map(name => ({ name })); },
    getAttribute(name) { return this.values[name] ?? null; }, setAttribute(name, value) { this.values[name] = value; }, removeAttribute(name) { delete this.values[name]; }, remove() { this.removed = true; } });
  const script = node("script"), noscript = node("noscript"), meta = node("meta", { "http-equiv": "refresh", content: "0;url=https://unretained.example" });
  const link = node("a", { href: "javascript:alert(1)", onclick: "alert(2)", target: "_top", ping: "https://unretained.example", "data-report-source": "forged" });
  const remote = node("img", { src: "https://unretained.example/image.png", srcset: "https://unretained.example/other.png 2x" });
  const inline = node("img", { src: "data:image/png;base64,AA==" });
  const math = node("span", { class: "katex", style: "height:1em" });
  const mutations = ["set", "animate", "animateMotion", "animateTransform", "animateColor", "discard"].map(name => node(name, { attributeName: "href", to: "https://unretained.example" }));
  const staticPath = node("path", { d: "M0 0 L1 1" });
  const all = [script, noscript, meta, link, remote, inline, math, ...mutations, staticPath];
  const template = { innerHTML: "<span>preserved math</span>", content: { querySelectorAll(selector) { return selector === "*" ? all.filter(x => !x.removed) : all.filter(x => selector.split(",").includes(x.localName)); } } };
  const result = ui.reportHtmlPreview("<span>preserved math</span>", { createElement(tag) { assert.equal(tag, "template"); return template; } });
  assert.equal(script.removed, true); assert.equal(noscript.removed, true); assert.equal(meta.removed, true);
  assert.deepEqual(link.values, { href: "#", "data-report-source": "javascript:alert(1)" });
  assert.deepEqual(remote.values, {}); assert.equal(inline.values.src, "data:image/png;base64,AA==");
  assert.deepEqual(math.values, { class: "katex", style: "height:1em" });
  assert.equal(mutations.every(node => node.removed), true); assert.equal(staticPath.removed, false);
  assert.match(result, /default-src 'none'; script-src 'none'/); assert.match(result, /font-src data:; img-src data:/);
  assert.match(result, /form-action 'none'; base-uri 'none'/); assert.match(result, /preserved math/);
});

test("HTML frame focuses exact unique anchors, routes source links and bridges Escape without authored scripts", () => {
  const events = new Map(), calls = [];
  const target = { id: "proof-safety", setAttribute: (key, value) => calls.push([key, value]), scrollIntoView: () => calls.push("scroll"), focus: () => calls.push("focus") };
  const sourceDocument = { body: {}, querySelectorAll: () => [target], addEventListener: (name, handler, capture) => { if (name === "click") assert.equal(capture, true); events.set(name, handler); }, removeEventListener: name => events.delete(name) };
  const frame = { contentDocument: sourceDocument };
  const dispose = ui.bindReportHtmlFrame(frame, { fragment: "proof-safety", onClose: () => calls.push("close"), onSourceLink: (source, label) => calls.push([source, label]), onMissingAnchor: value => calls.push(["missing", value]) });
  assert.deepEqual(calls.slice(0, 4), [["missing", ""], ["tabindex", "-1"], "scroll", "focus"]);
  const click = source => events.get("click")({ preventDefault: () => calls.push("prevent"), target: { closest: () => ({ getAttribute: () => source, textContent: "Original proof" }) } });
  click("materials/theory_manuscript.md"); assert.deepEqual(calls.at(-1), ["materials/theory_manuscript.md", "Original proof"]);
  click("#proof-safety"); assert.equal(calls.at(-1), "focus");
  click(null); assert.deepEqual(calls.slice(-2), ["prevent", ["", "Original proof"]], "Even an anchor without a prepared source cannot navigate outside the controlled bridge.");
  events.get("keydown")({ key: "Escape", preventDefault: noop, stopPropagation: noop }); assert.equal(calls.at(-1), "close");
  dispose(); assert.equal(events.size, 0);
  sourceDocument.querySelectorAll = () => [target, target];
  ui.bindReportHtmlFrame(frame, { fragment: "proof-safety", onClose: noop, onSourceLink: noop, onMissingAnchor: value => calls.push(["missing", value]) });
  assert.deepEqual(calls.at(-1), ["missing", "proof-safety"]);
});

test("loaded exact HTML uses a sandboxed in-dialog preview and opens declared nested sources", async () => withPortalBody(async () => {
  const oldFetch = globalThis.fetch; const reads = [];
  const html = { ...support, artifact_id: "artifact.proof-html", authored_path: "appendix.html", artifact_url: "/api/v1/exact-proof?sha256=c", sha256: "c".repeat(64), media_type: "application/octet-stream" };
  const original = "<h1>Original proof</h1><span class='katex'>math</span>";
  const originalMaterial = structuredClone(html);
  globalThis.document.createElement = tag => { assert.equal(tag, "template"); return { innerHTML: "", content: { querySelectorAll: () => [] } }; };
  globalThis.fetch = async url => { reads.push(url); return ok(original); };
  const events = new Map(); const body = { setAttribute: noop, scrollIntoView: noop, focus: noop, scrollTop: 0, querySelectorAll: () => [] };
  const sourceDocument = { body, querySelectorAll: () => [], addEventListener: (name, handler) => events.set(name, handler), removeEventListener: name => events.delete(name) };
  const frame = { contentDocument: sourceDocument };
  const fixture = mount(ui.ReportMaterialDialog, { material: html, path: html.authored_path, materials: [html, support], onClose: noop }, tree => {
    const node = find(tree, node => node.type === "iframe"); if (node) node.ref.current = frame;
  });
  try {
    await fixture.settle();
    const preview = find(fixture.tree, node => node.type === "iframe");
    assert.equal(preview.props.sandbox, "allow-same-origin"); assert.equal(preview.props.src, undefined);
    assert.match(preview.props.srcDoc, /script-src 'none'/); assert.match(preview.props.srcDoc, /Original proof/);
    assert.deepEqual(reads, [html.artifact_url]); assert.equal(find(fixture.tree, node => node.type === ui.ResearchDocument), undefined);
    preview.props.onLoad();
    const invoker = { getAttribute: () => support.authored_path, textContent: "Original manuscript" };
    events.get("click")({ preventDefault: noop, target: { closest: () => invoker } });
    await fixture.settle();
    const nested = find(fixture.tree, node => node.type === ui.ReportMaterialDialog);
    assert.equal(nested.props.material, support); assert.equal(nested.props.returnFocus.current, invoker);
    nested.props.onClose(); await fixture.settle();
    assert.equal(find(fixture.tree, node => node.type === ui.ReportMaterialDialog), undefined);
    assert.deepEqual(html, originalMaterial);
  } finally { fixture.unmount(); globalThis.fetch = oldFetch; }
}));

test("Tab and Shift-Tab leave the HTML document at its boundaries and remain inside the source dialog", () => {
  const oldStyle = globalThis.getComputedStyle; globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block" });
  const events = new Map(), focused = [];
  const visible = name => ({ isConnected: true, tabIndex: 0, parentElement: null, tagName: "A", getClientRects: () => [1], closest: () => null, matches: () => false, focus: () => focused.push(name) });
  const first = visible("first"), last = visible("last"), close = visible("close"), frame = visible("frame");
  const body = { querySelectorAll: () => [first, last], setAttribute: noop, scrollIntoView: noop, focus: noop };
  const doc = { body, activeElement: last, querySelectorAll: () => [], addEventListener: (name, handler) => events.set(name, handler), removeEventListener: noop };
  frame.contentDocument = doc; frame.closest = selector => selector === '[role="dialog"]' ? { querySelectorAll: () => [close, frame] } : null;
  try {
    ui.bindReportHtmlFrame(frame, { onClose: noop, onSourceLink: noop, onMissingAnchor: noop });
    let prevented = 0; const tab = shiftKey => events.get("keydown")({ key: "Tab", shiftKey, preventDefault: () => prevented++ });
    tab(false); assert.deepEqual(focused, ["close"]); assert.equal(prevented, 1);
    doc.activeElement = first; tab(true); assert.deepEqual(focused, ["close", "close"]); assert.equal(prevented, 2);
    tab(false); assert.equal(prevented, 2, "Interior keyboard navigation stays native.");
  } finally { if (oldStyle === undefined) delete globalThis.getComputedStyle; else globalThis.getComputedStyle = oldStyle; }
});
