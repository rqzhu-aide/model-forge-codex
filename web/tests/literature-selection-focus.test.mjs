import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { frameworkBasis, frameworkSources } from "./fixtures/framework-landscape.mjs";
import { entryIdentity } from "../src/literatureLandscape.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-literature-focus-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {default as Literature, LiteratureHistory, MainFindings, SelectedPaper} from '${src}/components/LiteratureWorkspace.jsx'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (tree, predicate) => nodes(tree).find(predicate);
const paper = view => find(view.tree, node => node.type === ui.SelectedPaper);
const findings = view => find(view.tree, node => node.type === ui.MainFindings);
const action = (view, label) => find(view.tree, node => [node.props.children].flat().join("") === label);

// Run the component's actual hooks and event handlers, with refs committed before
// effects. Child components remain elements; real browser coverage is separate.
function mount(Component, initialProps, environment) {
  const slots = []; let cursor = 0; let pending; let dirty = true; let props = initialProps; let tree;
  const hooks = {
    useState(initial) {
      const index = cursor++; slots[index] ||= { value: typeof initial === "function" ? initial() : initial };
      return [slots[index].value, update => {
        const next = typeof update === "function" ? update(slots[index].value) : update;
        if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; }
      }];
    },
    useRef(initial) { return (slots[cursor++] ||= { value: { current: initial } }).value; },
    useId() { const index = cursor++; return (slots[index] ||= { value: `fixture-${index}` }).value; },
    useEffect(run, dependencies) {
      const index = cursor++; const old = slots[index];
      if (!old || dependencies.some((value, offset) => !Object.is(value, old.dependencies[offset]))) {
        slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run });
      }
    },
  };
  const view = {
    get tree() { return tree; },
    update(changes) { props = { ...props, ...changes }; dirty = true; },
    settle() {
      for (let count = 0; dirty && count < 20; count++) {
        cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current;
        try { ui.dispatcher.current = hooks; tree = Component(props); }
        finally { ui.dispatcher.current = previous; }
        tree.ref.current = environment.content;
        const selected = paper(view); environment.selected.isConnected = Boolean(selected);
        if (selected) selected.props.focusRef.current = environment.selected;
        for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); }
      }
      assert.equal(dirty, false, "The component settles without additional rendering machinery.");
    },
    unmount() { for (const slot of slots) slot?.cleanup?.(); },
  };
  view.settle(); return view;
}

function environment({ approach = false } = {}) {
  const names = ["window", "getComputedStyle", "MutationObserver", "requestAnimationFrame", "cancelAnimationFrame"];
  const previous = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const scrolls = []; const focuses = []; const frames = new Map(); let sequence = 0;
  class Element {
    constructor(tag, attributes = {}, y = 0) { Object.assign(this, { tagName: tag.toUpperCase(), attributes, y, children: [], parentElement: null, isConnected: true, open: true, textContent: "", height: 100, stickyTop: 0 }); }
    append(child) { this.children.push(child); child.parentElement = this; return child; }
    contains(element) { return element === this || this.children.some(child => child.contains(element)); }
    matches(selector) {
      return selector.split(",").some(part => {
        if (part === ":disabled") return false;
        if (part.startsWith(".")) return this.attributes.class?.split(" ").includes(part.slice(1));
        if (part.startsWith("[")) { const [, name, value] = part.match(/^\[([^=\]]+)(?:=["']?([^\]"']+)["']?)?\]/) || []; return name && this.hasAttribute(name) && (value === undefined || this.getAttribute(name) === value); }
        return this.tagName === part.toUpperCase();
      });
    }
    closest(selector) { for (let item = this; item; item = item.parentElement) if (item.matches(selector)) return item; return null; }
    querySelectorAll(selector) { return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]); }
    querySelector(selector) { return selector === ":scope > summary" ? this.children.find(child => child.tagName === "SUMMARY") : this.querySelectorAll(selector)[0] || null; }
    hasAttribute(name) { return Object.hasOwn(this.attributes, name); }
    getAttribute(name) { return this.attributes[name] ?? null; }
    getClientRects() { return this.isConnected ? [{}] : []; }
    getBoundingClientRect() { const top = this.y - window.scrollY; return { top, bottom: top + this.height, height: this.height }; }
    focus(options) { focuses.push({ element: this, options }); }
  }
  globalThis.window = { scrollY: 800, innerHeight: 700, scrollTo(options) { scrolls.push(options); this.scrollY = options.top; } };
  globalThis.getComputedStyle = element => ({ visibility: "visible", display: "block", top: `${element.stickyTop}px` });
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.requestAnimationFrame = callback => { const id = ++sequence; frames.set(id, callback); return id; };
  globalThis.cancelAnimationFrame = id => frames.delete(id);
  const root = new Element("div", { "data-reader-ready": "true" });
  const toolbar = root.append(new Element("header", { class: "project-toolbar" })); toolbar.height = 195;
  toolbar.getBoundingClientRect = () => ({ top: toolbar.stickyTop, bottom: toolbar.stickyTop + toolbar.height, height: toolbar.height });
  const content = root.append(new Element("div"));
  const disclosures = [];
  let citationContainer = content;
  if (approach) {
    for (const [anchor, title] of [["approach-account:generation.fixture:framework.expected", "Expected discounted cost Closely related"], ["approach-detail:generation.fixture:framework.expected", "Mathematics, assumptions and evidence"]]) {
      const detail = citationContainer.append(new Element("details", { "data-reading-anchor": anchor }, 820));
      const summary = detail.append(new Element("summary", {}, 820)); summary.textContent = title;
      disclosures.push(detail); citationContainer = detail;
    }
  }
  const origin = citationContainer.append(new Element("button", { "data-reading-anchor": "citation:fixture:summary:0" }, 850));
  const selected = content.append(new Element("article", { class: "selected-paper", "data-reading-anchor": "paper:source.fixture" }, 1600));
  selected.isConnected = false;
  return { content, origin, selected, toolbar, scrolls, focuses, disclosures,
    flush() { const callbacks = [...frames.values()]; frames.clear(); for (const callback of callbacks) callback(); },
    cleanup() { for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; } },
  };
}

const libraries = [{ branch: "trunk", phase: "P1", sources: frameworkSources }];
const props = { basis: frameworkBasis, libraries };
const oldCard = frameworkSources[0].cards[0].assessment_history[0];
const citation = { source_id: "source.cited", canonical_source_id: "source.fixture", status: "available", entry_ref: entryIdentity(oldCard), card: oldCard, bibliography: { title: "Exact original paper" } };
const invocation = basis => ({ anchor: "citation:fixture:summary:0", label: "the cited account", basis });

test("only explicit paper selection focuses below the current measured sticky header", () => {
  const f = environment(); const view = mount(ui.Literature, { ...props, reading: { paperId: "source.fixture" } }, f);
  try {
    assert.ok(paper(view), "A saved paper selection is restored on mount.");
    assert.equal(f.focuses.length, 0); assert.equal(f.scrolls.length, 0);
    const choose = () => find(view.tree, node => node.type === "select" && node.props.id.endsWith("-paper")).props.onChange({ target: { value: "source.fixture" } });
    choose(); view.settle();
    assert.deepEqual(f.scrolls, [{ top: 1389, behavior: "instant" }]);
    assert.deepEqual(f.focuses, [{ element: f.selected, options: { preventScroll: true } }]);
    assert.equal(f.selected.getBoundingClientRect().top, 211);
    view.update(structuredClone(props)); view.settle();
    paper(view).props.onSelection({ sourceId: "source.fixture", reference: entryIdentity(frameworkSources[0].cards[1]), memberKey: "analyst" }); view.settle();
    view.update({ reading: { paperId: "different.saved.reader" } }); view.settle();
    assert.equal(f.scrolls.length, 1, "Polling, member choices and saved-navigation updates do not replay paper navigation.");
    f.toolbar.height = 245; f.toolbar.stickyTop = 8;
    choose(); view.settle();
    assert.deepEqual(f.scrolls.at(-1), { top: 1331, behavior: "instant" });
    assert.equal(f.selected.getBoundingClientRect().top, 269);
  } finally { view.unmount(); f.cleanup(); }
});

test("explicit evidence selection preserves the exact historical assessment and returns to the invoking reading position", () => {
  const f = environment(); const view = mount(ui.Literature, props, f); const before = JSON.stringify(props);
  try {
    findings(view).props.onOpenEvidence({ source: frameworkSources[0], card: oldCard }, { id: "framework.expected", record: { title: "Expected cost" }, anchor: "citation:fixture:summary:0" }); view.settle();
    assert.equal(paper(view).props.initialSelection.historyIndex, 0);
    assert.equal(paper(view).props.source.cards[0].assessment_history[0], oldCard);
    assert.deepEqual(f.focuses.at(-1), { element: f.selected, options: { preventScroll: true } });
    assert.equal(f.selected.getBoundingClientRect().top, 211);
    action(view, "Back to Expected cost").props.onClick(); view.settle(); f.flush();
    assert.equal(window.scrollY, 800);
    assert.deepEqual(f.focuses.at(-1), { element: f.origin, options: { preventScroll: true } });
    const count = f.scrolls.length; view.update(structuredClone(props)); view.settle(); f.flush();
    assert.equal(f.scrolls.length, count); assert.equal(JSON.stringify(props), before);
  } finally { view.unmount(); f.cleanup(); }
});

test("explicit citations keep the exact cited card while Back retains citation focus and reading offset", () => {
  const f = environment(); const basis = { ...frameworkBasis, citations: [citation] };
  const view = mount(ui.Literature, { ...props, basis }, f);
  try {
    findings(view).props.onOpenCitation(citation, invocation(basis)); view.settle();
    assert.equal(paper(view).props.initialSelection.exactCard, oldCard);
    assert.equal(f.selected.getBoundingClientRect().top, 211);
    action(view, "Back to the cited account").props.onClick(); view.settle(); f.flush();
    assert.equal(window.scrollY, 800);
    assert.deepEqual(f.focuses.at(-1), { element: f.origin, options: { preventScroll: true } });
    const count = f.focuses.length; view.update({ basis: structuredClone(basis) }); view.settle(); f.flush();
    assert.equal(f.focuses.length, count);
  } finally { view.unmount(); f.cleanup(); }
});

test("a citation inside a compact approach restores both disclosures before returning focus", () => {
  const f = environment({ approach: true }); const basis = { ...frameworkBasis, citations: [citation] };
  const view = mount(ui.Literature, { ...props, basis }, f);
  try {
    findings(view).props.onOpenCitation(citation, invocation(basis)); view.settle();
    assert.equal(paper(view).props.initialSelection.exactCard, oldCard);
    for (const detail of f.disclosures) detail.open = false;
    view.update({ basis: structuredClone(basis) }); view.settle();
    action(view, "Back to the cited account").props.onClick(); view.settle(); f.flush();
    assert.ok(f.disclosures.every(detail => detail.open));
    assert.equal(window.scrollY, 800);
    assert.deepEqual(f.focuses.at(-1), { element: f.origin, options: { preventScroll: true } });
    const count = f.focuses.length;
    view.update({ basis: structuredClone(basis) }); view.settle(); f.flush();
    assert.ok(f.disclosures.every(detail => detail.open));
    assert.equal(f.focuses.length, count, "Polling does not replay citation navigation.");
  } finally { view.unmount(); f.cleanup(); }
});

test("history citations use the same measured arrival without replaying on polling or Back", () => {
  const f = environment(); const basis = { ...frameworkBasis, citations: [citation] };
  const historyProps = { bases: [basis], libraries }; const view = mount(ui.LiteratureHistory, historyProps, f);
  try {
    assert.equal(f.scrolls.length, 0);
    findings(view).props.onOpenCitation(citation, invocation(basis)); view.settle();
    assert.equal(paper(view).props.initialSelection.exactCard, oldCard);
    assert.deepEqual(f.scrolls, [{ top: 1389, behavior: "instant" }]);
    assert.deepEqual(f.focuses, [{ element: f.selected, options: { preventScroll: true } }]);
    view.update(structuredClone(historyProps)); view.settle();
    assert.equal(f.scrolls.length, 1);
    action(view, "Back to literature account").props.onClick(); view.settle(); f.flush();
    assert.equal(paper(view), undefined); assert.equal(window.scrollY, 800);
    assert.deepEqual(f.focuses.at(-1), { element: f.origin, options: { preventScroll: true } });
    const count = f.scrolls.length; view.update(structuredClone(historyProps)); view.settle(); f.flush();
    assert.equal(f.scrolls.length, count);
  } finally { view.unmount(); f.cleanup(); }
});
