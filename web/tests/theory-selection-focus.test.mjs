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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-theory-focus-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {default as Theory} from '${src}/components/TheoryWorkbench.jsx'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const find = (view, predicate) => nodes(view.tree).find(predicate);
const graphNode = (view, label) => find(view, node => node.type === "g" && node.props["aria-label"].startsWith(`${label}.`));
const close = view => find(view, node => node.props.action === "close");
const search = view => find(view, node => node.props.type === "search");
const claimMap = { branch: "method.focus", phase: "P3", assumptions: [{ assumption_id: "assumption.rate", label: "Rate condition" }], claims: [{ statement_id: "claim.bound", label: "Risk bound", proof_status: "missing", depends_on: ["assumption.rate"] }] };

// Exercise the shipped hooks and handlers with refs committed before effects.
// This tests focus ownership, not browser layout or screen reader output.
function mount(changes = {}) {
  const f = { focuses: [], active: "body", selectedGraphNode: null, reading: [] };
  const element = name => ({ name, isConnected: true, getClientRects() { return this.isConnected ? [{}] : []; }, focus(options) { f.focuses.push({ name, options }); f.active = this; } });
  f.search = element("search"); f.inspector = element("inspector"); f.result = element("result");
  f.inspector.contains = item => Boolean(item?.insideInspector);
  f.graph = { scrollLeft: 0, scrollTop: 0, scrollWidth: 480, clientWidth: 480, clientHeight: 260,
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
    querySelector: selector => selector.endsWith(".theory-node-shape") ? f.selectedGraphNode && { getBoundingClientRect: () => ({ left: 10, right: 210, top: 10, bottom: 82 }) } : f.selectedGraphNode,
    scrollTo() { throw new Error("This already visible graph needs no scrolling."); },
  };
  const controls = new Map(); const slots = []; let cursor = 0; let pending; let dirty = true; let tree;
  let props = { branch: claimMap.branch, claimMaps: [claimMap], selected: null, onReadingChange: value => f.reading.push(value), ...changes };
  const update = value => { props = { ...props, ...value }; dirty = true; };
  props.onSelect = selected => update({ selected });
  const hooks = {
    useState(initial) { const index = cursor++; slots[index] ||= { value: initial }; return [slots[index].value, value => { if (!Object.is(slots[index].value, value)) { slots[index].value = value; dirty = true; } }]; },
    useRef(initial) { return (slots[cursor++] ||= { value: { current: initial } }).value; },
    useId() { return `fixture-${cursor++}`; },
    useMemo(factory) { cursor++; return factory(); },
    useEffect(run, dependencies) { const index = cursor++; const old = slots[index]; if (!old || dependencies.some((value, offset) => !Object.is(value, old.dependencies[offset]))) { slots[index] = { dependencies }; pending.push(run); } },
  };
  const view = { get tree() { return tree; }, f, update, element,
    settle() {
      for (let count = 0; dirty && count < 20; count++) {
        cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current;
        try { ui.dispatcher.current = hooks; tree = ui.Theory(props); } finally { ui.dispatcher.current = previous; }
        const rendered = nodes(tree);
        f.inspector.isConnected = Boolean(rendered.find(node => node.props["data-reading-anchor"] === "theory-inspector"));
        f.result.isConnected = Boolean(rendered.find(node => node.props.className === "search-results"));
        for (const node of rendered) {
          if (node.ref && node.type === "input") node.ref.current = f.search;
          if (node.ref && node.props.className === "graph-scroll") node.ref.current = f.graph;
          if (node.ref && node.props["data-reading-anchor"] === "theory-inspector") node.ref.current = f.inspector;
          if (node.type === "g" && node.props.className === "theory-node") {
            const key = node.props["aria-label"];
            if (!controls.has(key)) controls.set(key, element(key));
            if (node.props["aria-pressed"]) f.selectedGraphNode = controls.get(key);
          }
        }
        if (f.active?.isConnected === false) f.active = "body";
        for (const run of pending) run();
      }
      assert.equal(dirty, false);
    },
    chooseSearch() { search(view).props.onChange({ target: { value: "Risk" } }); view.settle(); f.active = f.result; find(view, node => node.props.action === "details").props.onClick(); view.settle(); },
  };
  view.settle(); return view;
}

test("search selection focuses its named inspector and Close returns to the surviving search field without scrolling", () => {
  const view = mount({ reading: { related: true } }); const { f } = view;
  view.chooseSearch();
  assert.equal(search(view).props.value, ""); assert.equal(f.result.isConnected, false);
  assert.equal(f.active, f.inspector);
  const inspector = find(view, node => node.props["data-reading-anchor"] === "theory-inspector");
  assert.equal(inspector.props["aria-label"], "Inspect Risk bound"); assert.equal(inspector.props.tabIndex, -1);
  assert.equal(graphNode(view, "Risk bound").props["aria-pressed"], true);
  assert.deepEqual(f.reading.at(-1), { search: "", related: true });
  close(view).props.onClick(); view.settle();
  assert.equal(close(view), undefined); assert.equal(f.active, f.search);
  assert.deepEqual(f.focuses, [{ name: "inspector", options: { preventScroll: true } }, { name: "search", options: { preventScroll: true } }]);
});

test("graph keyboard selection keeps graph focus and Close restores its invoking control", () => {
  for (const key of ["Enter", " "]) {
    const view = mount(); const origin = view.element(`graph-${key}`); view.f.active = origin; let prevented = false;
    graphNode(view, "Risk bound").props.onKeyDown({ key, currentTarget: origin, preventDefault() { prevented = true; } }); view.settle();
    assert.ok(prevented); assert.equal(view.f.active, origin); assert.equal(view.f.focuses.length, 0);
    close(view).props.onClick(); view.settle();
    assert.equal(view.f.active, origin); assert.deepEqual(view.f.focuses, [{ name: origin.name, options: { preventScroll: true } }]);
  }
});

test("inspector links retain the original return control when the clicked relationship disappears", () => {
  const view = mount(); view.chooseSearch();
  const relationship = find(view, node => node.type === "button" && node.props.children === "Rate condition" && node.props.className === "chip");
  const origin = view.element("relationship"); origin.insideInspector = true;
  relationship.props.onClick({ currentTarget: origin }); origin.isConnected = false; view.f.active = origin; view.settle();
  assert.equal(view.f.active, view.f.inspector);
  assert.equal(find(view, node => node.props["data-reading-anchor"] === "theory-inspector").props["aria-label"], "Inspect Rate condition");
  close(view).props.onClick(); view.settle(); assert.equal(view.f.active, view.f.search);
});

test("saved selections and equivalent polling do not focus, while selecting the same search result focuses once", () => {
  const view = mount({ selected: "claim.bound" }); assert.equal(view.f.focuses.length, 0);
  view.update({ claimMaps: [structuredClone(claimMap)] }); view.settle(); assert.equal(view.f.focuses.length, 0);
  view.chooseSearch(); assert.equal(view.f.active, view.f.inspector); assert.equal(view.f.focuses.length, 1);
  view.update({ claimMaps: [structuredClone(claimMap)] }); view.settle(); assert.equal(view.f.focuses.length, 1);
});

test("Close falls back to the selected graph control if its origin has disappeared or was restored from saved reading", () => {
  for (const restored of [true, false]) {
    const view = mount(restored ? { selected: "claim.bound" } : {});
    if (!restored) { const origin = view.element("old-graph"); graphNode(view, "Risk bound").props.onClick({ currentTarget: origin }); view.settle(); origin.isConnected = false; }
    const selected = view.f.selectedGraphNode; close(view).props.onClick(); view.settle();
    assert.equal(view.f.active, selected); assert.deepEqual(view.f.focuses.at(-1).options, { preventScroll: true });
  }
});
