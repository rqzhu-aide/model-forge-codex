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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-citation-escape-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {LiteratureCitation} from '${src}/components/LiteratureCitation.jsx'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];

test("Escape dismisses an open citation tooltip once, then reaches the enclosing reader", () => {
  let open = false;
  const previous = ui.dispatcher.current;
  const render = () => {
    try {
      ui.dispatcher.current = { useId: () => "fixture-citation", useState: () => [open, value => { open = value; }] };
      return ui.LiteratureCitation({ label: "Fixture paper", citation: { status: "available", card: {}, entry_ref: { entry_sha256: "a".repeat(64) }, bibliography: { title: "Fixture paper" } } });
    } finally { ui.dispatcher.current = previous; }
  };
  const button = () => nodes(render()).find(node => node.type === "button");
  const tooltip = () => nodes(render()).find(node => node.props.role === "tooltip");
  const keyDown = key => {
    let stopped = false;
    button().props.onKeyDown({ key, stopPropagation() { stopped = true; } });
    return stopped;
  };

  assert.equal(keyDown("Escape"), false, "A closed tooltip leaves Escape for the enclosing dialog.");
  button().props.onFocus();
  assert.ok(tooltip());
  assert.equal(keyDown("Enter"), false);
  assert.ok(tooltip(), "An unrelated key leaves the preview open.");
  assert.equal(keyDown("Escape"), true, "The first Escape dismisses the visible preview.");
  assert.equal(tooltip(), undefined);
  assert.equal(keyDown("Escape"), false, "The next Escape can close the reader without moving focus.");

  button().props.onFocus();
  button().props.onClick({ currentTarget: {} });
  assert.equal(tooltip(), undefined);
  assert.equal(keyDown("Escape"), false, "Opening a paper clears the preview and leaves later Escape available.");
});
