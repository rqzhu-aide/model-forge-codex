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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-reader-position-"));
const bundle = path.join(directory, "test.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: "export * from '" + src + "/readingWindowPosition.js';"
  + "export {readingDocumentKey} from '" + src + "/components/ReadingHost.jsx';"
  + "export {ReadingDocumentButton} from '" + src + "/components/MethodReadingWindow.jsx';"
  + "export {default as React} from 'react'; export {renderToStaticMarkup} from 'react-dom/server';", resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const body = (top = 0, open = false) => {
  const details = [{ open }]; let value = top;
  return { details, querySelectorAll: () => details,
    get scrollTop() { return value; },
    set scrollTop(next) { value = Math.min(next, details[0].open ? 1500 : 100); } };
};

test("expanded content is restored before scroll so a long diagnostic position does not clamp", () => {
  const original = body(950, true);
  ui.rememberReadingPosition("diagnostics:exact-a", original);
  const reopened = body();
  assert.equal(ui.restoreReadingPosition("diagnostics:exact-a", reopened), true);
  assert.equal(reopened.details[0].open, true);
  assert.equal(reopened.scrollTop, 950);
  assert.equal(ui.restoreReadingPosition("diagnostics:exact-b", body()), false);
});

test("reading keys isolate exact source, purpose, project and producing branch", () => {
  const scope = { projectId: "project-a", phase: "P4", branch: "method-a" };
  const source = { generation_id: "old", sha256: "a".repeat(64) };
  const key = ui.readingDocumentKey(scope, "implementation", [source]);
  assert.equal(key, ui.readingDocumentKey({ branch: "method-a", phase: "P4", projectId: "project-a" }, "implementation", [{ sha256: source.sha256, generation_id: "old" }]));
  for (const changed of [
    ui.readingDocumentKey({ ...scope, projectId: "project-b" }, "implementation", [source]),
    ui.readingDocumentKey({ ...scope, branch: "method-b" }, "implementation", [source]),
    ui.readingDocumentKey(scope, "review", [source]),
    ui.readingDocumentKey(scope, "implementation", [{ ...source, generation_id: "new" }]),
  ]) assert.notEqual(key, changed);
});

test("loading content neither restores nor overwrites a completed document's position", () => {
  ui.rememberReadingPosition("async:source", body(800, true));
  const dispatcher = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;
  const previous = dispatcher.current; const effects = [];
  dispatcher.current = { useRef: value => ({ current: value }), useLayoutEffect(effect) { effects.push(effect); } };
  const ref = { current: body() };
  try {
    const loading = ui.useReadingPosition({ key: "async:source", ready: false, bodyRef: ref });
    effects.shift()(); loading.onScroll();
    assert.equal(ref.current.scrollTop, 0);
    ui.useReadingPosition({ key: "async:source", ready: true, bodyRef: ref });
    const cleanup = effects.shift()();
    assert.equal(ref.current.scrollTop, 800);
    assert.equal(ref.current.details[0].open, true);
    cleanup();
  } finally { dispatcher.current = previous; }
});

test("an explicit fragment destination takes precedence over an old remembered position", () => {
  ui.rememberReadingPosition("fragment:source", body(800, true));
  const dispatcher = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;
  const previous = dispatcher.current; let effect;
  dispatcher.current = { useRef: value => ({ current: value }), useLayoutEffect(callback) { effect = callback; } };
  const ref = { current: body(75, true) };
  try {
    ui.useReadingPosition({ key: "fragment:source", ready: true, bodyRef: ref, fragment: "proof-2" });
    effect();
    assert.equal(ref.current.scrollTop, 75);
  } finally { dispatcher.current = previous; }
});

test("a proof locator moves only its source reader to one uniquely matching heading", () => {
  const heading = (textContent, top) => ({ textContent, getBoundingClientRect: () => ({ top }) });
  const exact = heading("P6. Persistent mixtures and exact selection", 680);
  const body = { scrollTop: 20, getBoundingClientRect: () => ({ top: 80 }), querySelectorAll: () => [heading("P60. Other", 900), exact] };
  assert.equal(ui.locateSourceHeading(body, "P6"), true);
  assert.equal(body.scrollTop, 620);
  body.querySelectorAll = () => [exact, heading("P6. Duplicate", 900)];
  assert.equal(ui.locateSourceHeading(body, "P6"), false);
  assert.equal(body.scrollTop, 620);
  assert.equal(ui.locateSourceHeading(body, "Missing"), false);
});

test("a named proof fragment resolves one scoped safe anchor without changing the page scroll", () => {
  const anchor = top => ({ getAttribute: name => name === "data-source-anchor" ? "p12" : null,
    getBoundingClientRect: () => ({ top }) });
  const targets = [anchor(960)];
  const body = { scrollTop: 20, getBoundingClientRect: () => ({ top: 80 }),
    querySelectorAll: selector => selector === "[data-source-anchor]" ? targets : [] };
  assert.equal(ui.locateSourceHeading(body, "#p12"), true);
  assert.equal(body.scrollTop, 900);
  targets.push(anchor(1100));
  assert.equal(ui.locateSourceHeading(body, "#p12"), false);
  assert.equal(body.scrollTop, 900);
  assert.equal(ui.locateSourceHeading(body, "#missing"), false);
});

test("source replacement and retry preserve the completed location before loading markup replaces it", () => {
  const dispatcher = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;
  const previous = dispatcher.current, savedBeforeChange = { current: null };
  let effect;
  dispatcher.current = { useRef: () => savedBeforeChange, useLayoutEffect(callback) { effect = callback; } };
  const ref = { current: body() };
  const render = (key, ready) => {
    const controller = ui.useReadingPosition({ key, ready, bodyRef: ref });
    return { controller, cleanup: effect() };
  };
  try {
    let current = render("replacement:source-a", true);
    ref.current.details[0].open = true; ref.current.scrollTop = 920;
    current.controller.saveBeforeChange();
    // React mutates child content before the parent's layout-effect cleanup.
    // Loading markup removes the expanded document and clamps its scroll.
    ref.current.details[0].open = false; ref.current.scrollTop = 0;
    current.cleanup();
    render("replacement:source-b", false).controller.onScroll();
    current = render("replacement:source-b", true);
    ref.current.details[0].open = true; ref.current.scrollTop = 640;
    current.controller.saveBeforeChange();
    ref.current.details[0].open = false; ref.current.scrollTop = 0; current.cleanup();
    current = render("replacement:source-a", false);
    // A failed load and its Retry button must not replace the completed source
    // position with the short error/loading state, even for this same source.
    current.controller.saveBeforeChange();
    render("replacement:source-a", false).controller.onScroll();
    current = render("replacement:source-a", true);
    assert.equal(ref.current.scrollTop, 920); assert.equal(ref.current.details[0].open, true);
    current.controller.saveBeforeChange();
    ref.current.details[0].open = false; ref.current.scrollTop = 0; current.cleanup();
    render("replacement:source-b", false);
    current = render("replacement:source-b", true);
    assert.equal(ref.current.scrollTop, 640); assert.equal(ref.current.details[0].open, true);
    current.cleanup();
  } finally { dispatcher.current = previous; }
});

test("session position storage is bounded and keeps recently revisited sources", () => {
  for (let i = 0; i < 100; i++) ui.rememberReadingPosition("bounded:" + i, body(i, true));
  ui.rememberReadingPosition("bounded:0", body(50, true));
  ui.rememberReadingPosition("bounded:new", body(60, true));
  assert.equal(ui.restoreReadingPosition("bounded:1", body()), false);
  const recent = body();
  assert.equal(ui.restoreReadingPosition("bounded:0", recent), true);
  assert.equal(recent.scrollTop, 50);
});

test("a source-only or unknown-size reading control remains available without a false empty label", () => {
  const render = props => ui.renderToStaticMarkup(ui.React.createElement(ui.ReadingDocumentButton, props));
  assert.match(render({ title: "Saved files", sizeLabel: "3 files" }), /3 files/);
  const unknown = render({ title: "Proof appendix" });
  assert.match(unknown, /Proof appendix/);
  assert.doesNotMatch(unknown, /No detailed text|0 words|Size available after opening/);
});
