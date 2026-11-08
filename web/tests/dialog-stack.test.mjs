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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-dialog-stack-"));
const bundle = path.join(directory, "test.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {Dialog} from '${src}/components/Shared.jsx'; export {Dialog}; export const render=props=>renderToStaticMarkup(React.createElement(Dialog,props)); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.$$typeof === Symbol.for("react.portal") ? [tree, ...nodes(tree.children)] : tree?.props ? [tree, ...nodes(tree.props.children)] : [];

// Exercise the shipped Dialog lifecycle with committed refs. This fixture checks
// stack exposure and focus ownership; browser checks cover layout and native inert.
function environment() {
  const previous = Object.fromEntries(["document", "MutationObserver", "getComputedStyle"].map(key => [key, globalThis[key]]));
  const observers = [], listeners = new Set(), focuses = [];
  const document = { addEventListener: (name, callback) => { if (name === "keydown") listeners.add(callback); }, removeEventListener: (name, callback) => listeners.delete(callback) };
  const element = (name, tagName = "DIV") => ({
    name, tagName, nodeType: 1, ownerDocument: document, children: [], parentElement: null, isConnected: true, tabIndex: -1, style: {}, attributes: new Map(),
    getAttribute(name) { return this.attributes.get(name) ?? null; },
    setAttribute(name, value) { this.attributes.set(name, String(value)); },
    removeAttribute(name) { this.attributes.delete(name); },
    getClientRects() { return this.isConnected ? [{}] : []; },
    contains(other) { for (let value = other; value; value = value.parentElement) if (value === this) return true; return false; },
    closest(selector) { for (let value = this; value; value = value.parentElement) { if (selector === "[hidden],[inert]" && (value.getAttribute("hidden") !== null || value.getAttribute("inert") !== null)) return value; } return null; },
    matches(selector) { return selector === ":disabled" && this.disabled; },
    querySelectorAll() { return this.targets || []; },
    focus(options) { if (!this.closest("[hidden],[inert]")) { document.activeElement = this; focuses.push({ target: this, options }); } },
    append(child) { child.parentElement = this; this.children.push(child); },
    remove() { this.isConnected = false; this.parentElement.children = this.parentElement.children.filter(child => child !== this); this.parentElement = null; },
  });
  document.body = element("body", "BODY"); document.body.style.overflow = "auto"; document.activeElement = document.body;
  const root = element("app"); document.body.append(root);
  const origin = element("origin", "BUTTON"); origin.tabIndex = 0; root.append(origin); document.activeElement = origin;
  globalThis.document = document;
  globalThis.MutationObserver = class {
    constructor(callback) { this.callback = callback; observers.push(this); }
    observe(target, options) { this.target = target; this.options = options; this.connected = true; }
    disconnect() { this.connected = false; }
  };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block", zIndex: "50" });
  const dialogs = [];
  function mount(props = {}, { parent, defer = false } = {}) {
    let cursor = 0; const slots = [], effects = [];
    const hooks = { useContext: () => parent?.ref || null, useRef: value => (slots[cursor++] ||= { current: value }), useId: () => `dialog-${dialogs.length}`, useEffect: callback => effects.push(callback) };
    const old = ui.dispatcher.current; let tree;
    try { ui.dispatcher.current = hooks; tree = ui.Dialog({ title: "Exact document", onClose() {}, ...props }); } finally { ui.dispatcher.current = old; }
    assert.equal(tree.$$typeof, Symbol.for("react.portal")); assert.equal(tree.containerInfo, document.body);
    const section = nodes(tree).find(node => node.type === "section");
    const bodyNode = nodes(tree).find(node => node.props?.className === "modal-body");
    const backdrop = element("backdrop"), box = element("dialog", "SECTION"), close = element("close", "BUTTON"), body = element("reading body");
    document.body.append(backdrop); backdrop.append(box); box.append(close); box.append(body);
    close.tabIndex = 0; body.tabIndex = 0; box.targets = [close, body]; box.setAttribute("aria-modal", "true");
    section.ref.current = box;
    if (bodyNode.ref) typeof bodyNode.ref === "function" ? bodyNode.ref(body) : bodyNode.ref.current = body;
    const view = { tree, ref: section.ref, box, backdrop, close, body, bodyNode, cleanups: [], started: false,
      start() { if (!this.started) { this.started = true; this.cleanups = effects.map(callback => callback()); } },
      unmount() { if (!this.started) return; this.started = false; for (const cleanup of this.cleanups) cleanup?.(); backdrop.remove(); },
    };
    dialogs.push(view); if (!defer) view.start(); return view;
  }
  return { document, root, origin, element, focuses, mount,
    key(key, shiftKey = false) { const event = { key, shiftKey, preventDefault() { this.prevented = true; }, stopPropagation() {} }; for (const listener of [...listeners]) listener(event); return event; },
    bodyChanged() { for (const observer of observers) if (observer.connected && observer.target === document.body) observer.callback(); },
    restore() { for (const view of dialogs.toReversed()) view.unmount(); for (const [key, value] of Object.entries(previous)) if (value === undefined) delete globalThis[key]; else globalThis[key] = value; },
  };
}

test("server rendering retains the labelled document without requiring a DOM", () => {
  const html = ui.render({ title: "Computation", children: "Exact saved formulation", onClose() {} });
  assert.match(html, /role="dialog" aria-modal="true" aria-labelledby=/);
  assert.match(html, /Close dialog/); assert.match(html, /Exact saved formulation/);
  assert.doesNotMatch(html, /aria-describedby|modal-subtitle/);
  const described = ui.render({ title: "Computation", subtitle: "Constrained estimator · Version 2", onClose() {} });
  const subtitleId = described.match(/<p class="modal-subtitle" id="([^"]+)">/)[1];
  assert.ok(described.includes(`aria-describedby="${subtitleId}"`));
  assert.match(described, /class="modal-title"><h2[^>]*>Computation<\/h2><p[^>]*>Constrained estimator · Version 2<\/p>/);
});

test("nested windows expose only the top dialog and restore exact background attributes and focus", () => {
  const f = environment();
  try {
    const hidden = f.element("already hidden"); hidden.setAttribute("inert", "retained"); hidden.setAttribute("aria-hidden", "false"); f.document.body.append(hidden);
    const bodyRef = { current: null }; let scrollTarget;
    const parent = f.mount({ bodyRef, onBodyScroll: event => { scrollTarget = event.currentTarget; } });
    assert.equal(bodyRef.current, parent.body); parent.bodyNode.props.onScroll({ currentTarget: parent.body }); assert.equal(scrollTarget, parent.body);
    assert.equal(f.root.getAttribute("inert"), ""); assert.equal(f.root.getAttribute("aria-hidden"), "true");
    assert.equal(parent.box.getAttribute("aria-modal"), "true"); assert.equal(parent.backdrop.getAttribute("inert"), null);
    parent.body.scrollTop = 430; parent.body.focus(); let closed = 0;
    const child = f.mount({ onClose: () => closed++ }, { parent });
    assert.equal(child.box.getAttribute("aria-modal"), "true"); assert.equal(child.backdrop.getAttribute("inert"), null);
    assert.equal(parent.backdrop.style.zIndex, "50"); assert.equal(child.backdrop.style.zIndex, "51");
    assert.equal(parent.box.getAttribute("aria-modal"), null); assert.equal(parent.backdrop.getAttribute("aria-hidden"), "true"); assert.equal(parent.backdrop.getAttribute("inert"), "");
    assert.equal(child.box.closest("[hidden],[inert]"), null, "A nested portal cannot inherit its parent's inert backdrop.");
    assert.equal(f.key("Escape").prevented, true); assert.equal(closed, 1);
    child.body.focus(); assert.equal(f.key("Tab").prevented, true); assert.equal(f.document.activeElement, child.close);
    const added = f.element("new background"); f.document.body.append(added); f.bodyChanged(); assert.equal(added.getAttribute("inert"), "");
    child.unmount(); assert.equal(f.document.activeElement, parent.body); assert.equal(parent.body.scrollTop, 430);
    assert.equal(parent.box.getAttribute("aria-modal"), "true"); assert.equal(parent.backdrop.getAttribute("inert"), null); assert.equal(f.document.body.style.overflow, "hidden");
    parent.unmount(); assert.equal(f.document.activeElement, f.origin); assert.equal(f.document.body.style.overflow, "auto");
    assert.equal(f.root.getAttribute("inert"), null); assert.equal(f.root.getAttribute("aria-hidden"), null); assert.equal(added.getAttribute("inert"), null);
    assert.equal(hidden.getAttribute("inert"), "retained"); assert.equal(hidden.getAttribute("aria-hidden"), "false");
    assert.equal(f.focuses[0].options.preventScroll, true); assert.equal(f.focuses.at(-1).options.preventScroll, true);
  } finally { f.restore(); }
});

test("covered-window cleanup keeps the surviving reader focused and the page locked", () => {
  const f = environment();
  try {
    const parent = f.mount(), child = f.mount({}, { parent });
    const active = f.document.activeElement; parent.unmount();
    assert.equal(f.document.activeElement, active); assert.equal(f.document.body.style.overflow, "hidden"); assert.equal(f.root.getAttribute("inert"), "");
    assert.equal(child.box.getAttribute("aria-modal"), "true");
    child.unmount(); assert.equal(f.document.body.style.overflow, "auto"); assert.equal(f.root.getAttribute("inert"), null);
  } finally { f.restore(); }
});

test("a child mounted in the same commit stays above its parent despite child-first effects", () => {
  const f = environment();
  try {
    const parent = f.mount({}, { defer: true }), child = f.mount({}, { parent }); parent.start();
    assert.equal(child.box.getAttribute("aria-modal"), "true"); assert.equal(parent.box.getAttribute("aria-modal"), null);
    assert.equal(parent.backdrop.style.zIndex, "50"); assert.equal(child.backdrop.style.zIndex, "51", "Paint order follows nesting even when portal DOM insertion order differs.");
    assert.equal(f.document.activeElement, child.close); assert.equal(child.box.closest("[hidden],[inert]"), null);
    child.unmount(); assert.equal(parent.box.getAttribute("aria-modal"), "true");
  } finally { f.restore(); }
});
