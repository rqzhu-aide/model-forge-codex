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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-source-navigation-"));
const bundle = path.join(directory, "test.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `export {default as React} from 'react'; export {renderToStaticMarkup} from 'react-dom/server'; export {api} from '${src}/api.js'; export {default as ResearchSourceDialog} from '${src}/components/ResearchSourceDialog.jsx'; export {Dialog,ResearchDocument} from '${src}/components/Shared.jsx'; export {ScientificDocuments} from '${src}/components/PhaseReading.jsx'; export {TechnicalReportDocument} from '${src}/components/TechnicalReportReading.jsx'; export {ActionButton} from '${src}/components/Visuals.jsx'; export {readingDocumentKey} from '${src}/components/ReadingHost.jsx'; export {rememberReadingPosition} from '${src}/readingWindowPosition.js';`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.$$typeof === Symbol.for("react.portal") ? nodes(tree.children) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (tree, type) => nodes(tree).find(node => node.type === type);
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const reference = (id, family = "theory_record") => ({ branch: "method.a", phase: "P3", family, generation_id: id, sha256: id.repeat(64).slice(0, 64) });
const record = (ref, text) => ({ kind: ref.family, generation_ref: ref, body_md: text });

function hooks(context = () => null) {
  const slots = [], pending = []; let cursor = 0;
  const dispatcher = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;
  const effect = (callback, dependencies) => {
    const index = cursor++; const old = slots[index];
    if (!old || dependencies.some((value, i) => value !== old.dependencies[i])) pending.push(() => { old?.cleanup?.(); slots[index] = { dependencies, cleanup: callback() }; });
  };
  const implementation = {
    useContext: context,
    useState(initial) { const index = cursor++; if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
    useRef: initial => slots[cursor++] ||= { current: initial },
    useId: () => `source-${cursor++}`,
    useLayoutEffect: effect, useEffect: effect,
  };
  return {
    render(component, props) { cursor = 0; const old = dispatcher.current; dispatcher.current = implementation; try { return component(props); } finally { dispatcher.current = old; } },
    commit() { for (const callback of pending.splice(0)) callback(); },
    close() { for (const slot of slots) slot?.cleanup?.(); },
  };
}

// Run source state and real Dialog Escape/focus lifecycle together. Native layout
// and inert behavior are checked in the browser, not simulated by this fixture.
function environment() {
  const names = ["document", "MutationObserver", "getComputedStyle"];
  const originals = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const listeners = new Set(); const views = [];
  const document = { addEventListener: (name, callback) => { if (name === "keydown") listeners.add(callback); }, removeEventListener: (_, callback) => listeners.delete(callback) };
  const element = (name, tagName = "DIV") => ({
    name, tagName, nodeType: 1, ownerDocument: document, children: [], parentElement: null, isConnected: true, tabIndex: 0, style: {}, attributes: new Map(), scrollTop: 0,
    getAttribute(name) { return this.attributes.get(name) ?? null; }, setAttribute(name, value) { this.attributes.set(name, String(value)); }, removeAttribute(name) { this.attributes.delete(name); },
    getClientRects() { return this.isConnected ? [{}] : []; },
    contains(other) { for (let node = other; node; node = node.parentElement) if (node === this) return true; return false; },
    closest(selector) { for (let node = this; node; node = node.parentElement) if (selector === "[hidden],[inert]" && (node.attributes.has("hidden") || node.attributes.has("inert"))) return node; return null; },
    matches: () => false,
    querySelectorAll() { return this.targets || []; },
    focus() { document.activeElement = this; },
    append(child) { this.children.push(child); child.parentElement = this; return child; },
    remove() { this.isConnected = false; this.parentElement.children = this.parentElement.children.filter(child => child !== this); },
  });
  document.body = element("body", "BODY"); const app = document.body.append(element("app"));
  const origin = app.append(element("Inspect exact source", "BUTTON")); document.activeElement = origin;
  globalThis.document = document;
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block", zIndex: "50" });
  function mountSource(props, parent) {
    const source = hooks(); const dialog = hooks(() => parent?.dialogRef || null);
    const backdrop = document.body.append(element("backdrop")); const box = backdrop.append(element("dialog", "SECTION"));
    const close = box.append(element("close", "BUTTON")); const body = box.append(element("reading body"));
    const details = [{ open: false }]; body.querySelectorAll = () => details; box.targets = [close, body];
    const view = { props, body, details, box, source, dialog, active: true,
      render() {
        this.tree = source.render(ui.ResearchSourceDialog, this.props); this.tree.props.bodyRef.current = body;
        const dialogTree = dialog.render(ui.Dialog, this.tree.props);
        const section = nodes(dialogTree).find(node => node.type === "section"); section.ref.current = box; this.dialogRef = section.ref;
        dialog.commit(); source.commit(); return this.tree;
      },
      async settle() { await new Promise(setImmediate); return this.render(); },
      unmount() { if (!this.active) return; this.active = false; source.close(); dialog.close(); backdrop.remove(); },
    };
    views.push(view); view.render(); return view;
  }
  return { document, origin, element, mountSource,
    escape() { for (const listener of [...listeners]) listener({ key: "Escape", preventDefault() {}, stopPropagation() {} }); },
    cleanup() { for (const view of views.toReversed()) view.unmount(); for (const [name, value] of Object.entries(originals)) if (value === undefined) delete globalThis[name]; else globalThis[name] = value; },
  };
}

test("a child source returns to its exact parent, location and control on Close or Escape", async () => {
  const original = ui.api.recordDocument; const f = environment(); const requests = [];
  const a = reference("a"), b = reference("b", "theory_candidate"); const parentBody = record(a, "Parent retained theory.");
  ui.api.recordDocument = async (projectId, ref) => { requests.push([projectId, ref]); return ref.generation_id === "a" ? parentBody : record(b, "Candidate proof."); };
  let parent;
  try {
    parent = f.mountSource({ projectId: "navigation.fixture", reference: a, onClose: () => parent.unmount() }); await parent.settle();
    parent.body.scrollTop = 920; parent.details[0].open = true;
    const invoker = parent.box.append(f.element("Retained theory, Appendices C1-C3 and E1-E2", "BUTTON")); parent.box.targets.push(invoker);
    for (const closeWith of ["Close", "Escape"]) {
      invoker.focus(); find(parent.tree, ui.ScientificDocuments).props.onSource(b); parent.render();
      const childElement = find(parent.tree, ui.ResearchSourceDialog); let child;
      child = f.mountSource({ ...childElement.props, onClose: () => { childElement.props.onClose(); child.unmount(); parent.render(); } }, parent);
      await child.settle();
      assert.equal(find(child.tree, ui.ScientificDocuments).props.documents[0].generation_ref.generation_id, "b");
      assert.equal(parent.box.getAttribute("aria-modal"), null);
      if (closeWith === "Escape") f.escape(); else child.tree.props.onClose();
      assert.equal(find(parent.tree, ui.ResearchSourceDialog), undefined);
      assert.equal(parent.box.getAttribute("aria-modal"), "true"); assert.equal(f.document.activeElement, invoker);
      assert.equal(parent.body.scrollTop, 920); assert.equal(parent.details[0].open, true);
      assert.equal(find(parent.tree, ui.ScientificDocuments).props.documents[0], parentBody);
    }
    assert.deepEqual(requests, [["navigation.fixture", a], ["navigation.fixture", b], ["navigation.fixture", b]]);
    parent.tree.props.onClose(); assert.equal(f.document.activeElement, f.origin);
  } finally { f.cleanup(); ui.api.recordDocument = original; }
});

test("closing a child during loading cannot revive it when its request finishes", async () => {
  const original = ui.api.recordDocument; const f = environment(); const pending = deferred();
  const a = reference("c"), b = reference("d"); let parent;
  ui.api.recordDocument = (_, ref) => ref.generation_id === a.generation_id ? Promise.resolve(record(a, "Exact parent.")) : pending.promise;
  try {
    parent = f.mountSource({ projectId: "loading.fixture", reference: a, onClose: () => parent.unmount() }); await parent.settle();
    find(parent.tree, ui.ScientificDocuments).props.onSource(b); parent.render();
    const childElement = find(parent.tree, ui.ResearchSourceDialog); let child;
    child = f.mountSource({ ...childElement.props, onClose: () => { childElement.props.onClose(); child.unmount(); parent.render(); } }, parent);
    f.escape(); pending.resolve(record(b, "Late child.")); await parent.settle();
    assert.equal(find(parent.tree, ui.ResearchSourceDialog), undefined); assert.equal(parent.active, true);
    assert.equal(find(parent.tree, ui.ScientificDocuments).props.documents[0].generation_ref.generation_id, "c");
  } finally { f.cleanup(); ui.api.recordDocument = original; }
});

test("source replacement ignores old loading results and entry pointers use the exact raw record", async () => {
  const originals = { recordDocument: ui.api.recordDocument, recordBody: ui.api.recordBody }; const f = environment(); const pending = deferred();
  const first = reference("e"), next = { ...reference("f"), entry_pointer: "/statements/1" }; const raw = [];
  ui.api.recordDocument = () => pending.promise;
  ui.api.recordBody = async (...args) => { raw.push(args); return { statements: [{ statement: "Other statement." }, { statement: "Exact cited statement." }] }; };
  try {
    const view = f.mountSource({ projectId: "replacement.fixture", reference: first, onClose() {} });
    view.props = { ...view.props, reference: next }; view.render(); await view.settle();
    pending.resolve(record(first, "Outdated loading result.")); await view.settle();
    assert.equal(find(view.tree, ui.ScientificDocuments), undefined);
    assert.match(JSON.stringify(find(view.tree, ui.ResearchDocument).props.text), /Exact cited statement/);
    assert.deepEqual(raw, [["replacement.fixture", next.branch, next.phase, next.family, next.generation_id]]);
  } finally { f.cleanup(); Object.assign(ui.api, originals); }
});

test("Retry reloads the same child without adding another dialog or replacing the parent", async () => {
  const original = ui.api.recordDocument; const f = environment(); let attempts = 0;
  const ref = reference("g"); ui.api.recordDocument = async () => { if (++attempts === 1) throw new Error("Retained source unavailable."); return record(ref, "Retried exact source."); };
  try {
    const view = f.mountSource({ projectId: "retry.fixture", reference: ref, onClose() {} }); await view.settle();
    nodes(view.tree).find(node => node.type === ui.ActionButton && node.props.action === "retry").props.onClick(); view.render(); await view.settle();
    assert.equal(find(view.tree, ui.ResearchSourceDialog), undefined); assert.equal(attempts, 2);
    assert.equal(find(view.tree, ui.ScientificDocuments).props.documents[0].generation_ref, ref);
  } finally { f.cleanup(); ui.api.recordDocument = original; }
});

test("an explicit report fragment bypasses an old reading offset and reaches the report renderer", async () => {
  const original = ui.api.recordDocument; const f = environment();
  const ref = { ...reference("h", "technical_report"), report_fragment: "model" };
  const key = ui.readingDocumentKey({ projectId: "fragment.fixture" }, "research-source", [ref, null]);
  ui.rememberReadingPosition(key, { scrollTop: 900, querySelectorAll: () => [] });
  ui.api.recordDocument = async () => record(ref, "Report with an explicit model section.");
  try {
    const view = f.mountSource({ projectId: "fragment.fixture", reference: ref, onClose() {} }); await view.settle();
    assert.equal(view.body.scrollTop, 0); assert.equal(find(view.tree, ui.TechnicalReportDocument).props.fragment, "model");
  } finally { f.cleanup(); ui.api.recordDocument = original; }
});

test("the document request forwards only the exact auxiliary URI and digest", async () => {
  const original = globalThis.fetch; let requested;
  globalThis.fetch = async url => { requested = url; return { ok: true, json: async () => ({ body_md: "Exact proof" }) }; };
  const artifact_ref = { uri: "artifact://p3.theorist/proofs.md", sha256: "b".repeat(64) };
  try {
    await ui.api.recordDocument("project.test", { ...reference("original", "theory_candidate"), artifact_ref, source_locator: "P6" });
    const url = new URL(requested, "http://test");
    assert.equal(url.searchParams.get("view"), "document");
    assert.equal(url.searchParams.get("artifact_uri"), artifact_ref.uri);
    assert.equal(url.searchParams.get("artifact_sha256"), artifact_ref.sha256);
    assert.equal(url.searchParams.has("source_locator"), false);
    assert.equal(url.pathname, "/api/v1/projects/project.test/branches/method.a/phases/P3/records/theory_candidate/original");
  } finally { globalThis.fetch = original; }
});

test("verified P3 text fragments open the exact source reader with its named destination", () => {
  const ref = { ...reference("a", "theory_candidate"), artifact_ref: { uri: "artifact://retained-proof", sha256: "b".repeat(64) } };
  const uri = "/C:/research/retained/proofs.md";
  const source = { uri, source_verified: true, media_type: "text/markdown", artifact_url: "/api/exact-proof", generation_ref: ref };
  const document = { ...record(ref, "The conditions remain necessary."), inline_sources: [source] };
  const opened = [];
  const tree = ui.ScientificDocuments({ documents: [document], onSource: value => opened.push(value) });
  const link = find(tree, ui.ResearchDocument).props.renderSourceLink;
  const control = link(`${uri}#p12`, "Retained construction");
  const expected = { ...ref, source_locator: "#p12" };
  assert.deepEqual(control.props.reference, expected);
  control.type(control.props).props.onClick();
  assert.deepEqual(opened, [expected]);
  assert.deepEqual(ref.artifact_ref, expected.artifact_ref);
  for (const changes of [{ source_verified: false }, { source_error: "Changed bytes" }, { generation_ref: undefined }]) {
    const tree = ui.ScientificDocuments({ documents: [{ ...document, inline_sources: [{ ...source, ...changes }] }], onSource() {} });
    const result = find(tree, ui.ResearchDocument).props.renderSourceLink(`${uri}#p12`, "Retained construction");
    assert.equal(result.props.reference, undefined);
  }
  const json = ui.ScientificDocuments({ documents: [{ ...document, inline_sources: [{ ...source, media_type: "application/json" }] }] });
  assert.equal(find(json, ui.ResearchDocument).props.renderSourceLink(`${uri}#p12`, "Source").type, "a");
});

test("P3 documents render only safe empty source anchors while preserving code and escaping other HTML", () => {
  const text = '<a id="p12"></a>\n\n## P12. Retained counterexample\n\nThe strict boundary remains.\n\n`<a id="example"></a>`\n\n<a id="unsafe" onclick="alert(1)"></a>\n\n<script>alert(1)</script>';
  const document = record(reference("a"), text);
  const before = structuredClone(document);
  const html = ui.renderToStaticMarkup(ui.React.createElement(ui.ScientificDocuments, { documents: [document] }));
  assert.match(html, /<span data-source-anchor="p12"><\/span>/);
  assert.match(html, /<code>&lt;a id=&quot;example&quot;&gt;&lt;\/a&gt;<\/code>/);
  assert.match(html, /&lt;a id=&quot;unsafe&quot; onclick=&quot;alert\(1\)&quot;&gt;/);
  assert.doesNotMatch(html, /<script|data-source-anchor="(?:unsafe|example)"|<a id=/);
  assert.deepEqual(document, before);
});
