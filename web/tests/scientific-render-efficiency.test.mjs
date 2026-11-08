import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";
import { sharedPackage } from "../scripts/shared-deps.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-scientific-efficiency-"));
const bundle = path.join(directory, "render.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; export {ResearchDocument,MathText} from '${src}/components/Shared.jsx'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") },
  plugins: [{ name: "local-profile-counters", setup(plugin) {
    plugin.onLoad({ filter: /research(Markdown|Math)\.js$/ }, ({ path: filename }) => ({ loader: "js", contents: fs.readFileSync(filename, "utf8")
      .replace(/(export function referenceMarkdown\(text\) \{)/, "$1 globalThis.__scientificProfile.markdown++;")
      .replace(/(export function renderMath\(katex, latex, display\) \{)/, "$1 globalThis.__scientificProfile.math++;") }));
  } }], logLevel: "silent",
});
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

// Reuse mounted component hook slots and React.memo's public comparator contract.
// This measures shipped parser/math calls, not browser reconciliation or paint.
function mountedReader(Component, initialProps) {
  const instances = new Map(); const renders = new Map(); let props = initialProps;
  function visit(element, key = "root") {
    if (Array.isArray(element)) return element.map((child, index) => visit(child, `${key}.${index}`));
    if (!element || typeof element !== "object" || !element.props) return element;
    if (typeof element.type === "string") return { type: element.type, props: { ...element.props, children: visit(element.props.children, `${key}.children`) } };
    if (typeof element.type === "symbol") return visit(element.props.children, `${key}.fragment`);
    const memo = element.type?.$$typeof === Symbol.for("react.memo");
    const type = memo ? element.type.type : element.type;
    let instance = instances.get(key);
    if (!instance || instance.type !== type) { instance = { type, slots: [], props: null, output: null }; instances.set(key, instance); }
    const shallowEqual = (a, b) => a && Object.keys(a).length === Object.keys(b).length && Object.keys(b).every(name => Object.is(a[name], b[name]));
    if (memo && (element.type.compare || shallowEqual)(instance.props, element.props)) return instance.output;
    let cursor = 0;
    const hooks = {
      useId() { return `mounted-${key}-${cursor++}`; },
      useMemo(factory, dependencies) {
        const index = cursor++; const previous = instance.slots[index];
        if (!previous || dependencies.some((value, offset) => !Object.is(value, previous.dependencies[offset]))) instance.slots[index] = { dependencies, value: factory() };
        return instance.slots[index].value;
      },
    };
    const previous = ui.dispatcher.current;
    let child;
    try { ui.dispatcher.current = hooks; renders.set(type.name, (renders.get(type.name) || 0) + 1); child = type(element.props); }
    finally { ui.dispatcher.current = previous; }
    instance.props = element.props; instance.output = visit(child, `${key}.rendered`); return instance.output;
  }
  return { renders, draw(changes = {}) { props = { ...props, ...changes }; return visit({ type: Component, props }); } };
}
const longDocument = Array.from({ length: 40 }, (_, index) => `## Result ${index + 1}\nThe synthetic estimate $\\widehat\\mu_${index}$ targets a donor mean under the stated sampling assumption. [Inspect evidence](#evidence).\n\n$$\\widehat\\mu_${index}=\\frac{1}{n}\\sum_{i=1}^n X_i$$\n\n| Quantity | Value |\n| --- | --- |\n| $n$ | 200 |\n| Assumption | Independent donors |`).join("\n\n");
const counters = () => (globalThis.__scientificProfile = { markdown: 0, math: 0 });
function nodes(element) {
  if (Array.isArray(element)) return element.flatMap(nodes);
  return element && typeof element === "object" && element.props ? [element, ...nodes(element.props.children)] : [];
}

test("unchanged scientific reading avoids parsing on 25 unrelated progress refreshes", (t) => {
  counters(); const view = mountedReader(ui.ResearchDocument, { text: longDocument });
  const first = view.draw(); const initial = { ...globalThis.__scientificProfile };
  const outputs = []; const start = performance.now();
  for (let progress = 1; progress <= 25; progress++) outputs.push(view.draw());
  const updateMilliseconds = Number((performance.now() - start).toFixed(2));
  for (const output of outputs) assert.deepEqual(output, first);
  const update = { markdown: globalThis.__scientificProfile.markdown - initial.markdown, math: globalThis.__scientificProfile.math - initial.math };
  t.diagnostic(JSON.stringify({ fixture: { characters: longDocument.length, sections: 40, updates: 25 }, initial, update, updateMilliseconds, functionRenders: Object.fromEntries(view.renders) }));
  assert.deepEqual(update, { markdown: 0, math: 0 });
  assert.equal(view.renders.get("ResearchDocument"), 26, "The parse saving is separate from parent/component function renders.");
});

test("changed source callbacks update bindings without repeating scientific parsing or math", () => {
  counters(); const older = []; const current = [];
  const link = sink => (target, label) => ({ type: "button", props: { children: label, onClick: () => sink.push(target) } });
  const view = mountedReader(ui.ResearchDocument, { text: "An estimate $x=1$ has [evidence](#evidence).", renderInternalLink: link(older) });
  const first = view.draw(); const afterFirst = { ...globalThis.__scientificProfile };
  nodes(first).find(node => node.type === "button").props.onClick();
  const changed = view.draw({ renderInternalLink: link(current) });
  nodes(changed).find(node => node.type === "button").props.onClick();
  assert.deepEqual(older, ["#evidence"]); assert.deepEqual(current, ["#evidence"]);
  assert.deepEqual(globalThis.__scientificProfile, afterFirst);
  const updated = view.draw({ text: "A corrected estimate $x=2$ has [evidence](#evidence)." });
  assert.ok(nodes(updated).some(node => node.props.dangerouslySetInnerHTML?.__html.includes("x=2")));
  assert.ok(globalThis.__scientificProfile.markdown > afterFirst.markdown);
  assert.ok(globalThis.__scientificProfile.math > afterFirst.math);
  // A retained reader can still render its older exact scientific version.
  view.draw({ text: "An estimate $x=1$ has [evidence](#evidence).", renderInternalLink: link(older) });
  assert.equal(globalThis.__scientificProfile.markdown, afterFirst.markdown + 2);
});

test("identically labelled source links follow the current map while a retained reader keeps its frozen binding", () => {
  counters(); const opened = [];
  const first = { generation_id: "source.one", sha256: "a".repeat(64) };
  const second = { generation_id: "source.two", sha256: "b".repeat(64) };
  const resolver = map => (target, label) => ({ type: "button", props: { children: label, onClick: () => opened.push(map[target]) } });
  const text = "The retained estimate $x=1$ has [evidence](generation://evidence).";
  const frozenMap = { "generation://evidence": first };
  const frozen = mountedReader(ui.ResearchDocument, { text, renderSourceLink: resolver(frozenMap) });
  const live = mountedReader(ui.ResearchDocument, { text, renderSourceLink: resolver(frozenMap) });
  const frozenTree = frozen.draw(); live.draw(); const initial = { ...globalThis.__scientificProfile };
  const currentTree = live.draw({ renderSourceLink: resolver({ "generation://evidence": second }) });
  nodes(currentTree).find(node => node.type === "button").props.onClick();
  nodes(frozenTree).find(node => node.type === "button").props.onClick();
  assert.deepEqual(opened, [second, first]);
  assert.deepEqual(globalThis.__scientificProfile, initial);
});
