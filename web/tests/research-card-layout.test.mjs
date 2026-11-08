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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-card-layout-"));
const bundle = path.join(directory, "layout.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `export {default as React} from 'react'; export {renderToStaticMarkup} from 'react-dom/server'; export {default as Layout} from '${src}/components/ResearchCardLayout.jsx';`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom") }, logLevel: "silent" });
const { React, Layout, renderToStaticMarkup } = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const control = React.createElement("button", { type: "button" }, "Prepare theory");
const reading = React.createElement("button", { type: "button" }, "Read assumptions");
const render = props => renderToStaticMarkup(React.createElement(Layout, props, "The claim requires overlap."));

test("cards without supporting content retain one complete account and no empty groups", () => {
  const html = render({});
  assert.match(html, /The claim requires overlap\./);
  assert.doesNotMatch(html, /has-rail|has-actions|<aside|role="group"/);
});

test("actions and reading each occupy one slot, in a logical stacked order", () => {
  const html = render({ actions: control, resources: reading, actionsLabel: "Theory actions", label: "Theory supporting reading", "data-reading-anchor": "theory-account", id: "theory", className: "test-card" });
  assert.ok(html.indexOf("Prepare theory") < html.indexOf("The claim requires overlap."));
  assert.ok(html.indexOf("The claim requires overlap.") < html.indexOf("Read assumptions"));
  assert.equal(html.match(/Prepare theory/g)?.length, 1);
  assert.equal(html.match(/Read assumptions/g)?.length, 1);
  assert.match(html, /role="group" aria-label="Theory actions"/);
  assert.match(html, /<aside class="research-card-resources" aria-label="Theory supporting reading"/);
  assert.match(html, /class="research-card-columns test-card" data-reading-anchor="theory-account" id="theory"/);
});

test("action-only and reading-only cards do not reserve empty semantic regions", () => {
  const actions = render({ actions: control });
  assert.match(actions, /has-rail has-actions/);
  assert.doesNotMatch(actions, /<aside|research-card-resources/);
  const resources = render({ resources: reading });
  assert.match(resources, /has-rail/);
  assert.doesNotMatch(resources, /has-actions|research-card-actions/);
  assert.ok(resources.indexOf("The claim requires overlap.") < resources.indexOf("Read assumptions"));
});

test("question rows use the shared layout without adding complementary landmarks", () => {
  const html = render({ actions: control, resources: reading, resourceElement: "div", label: "Question supporting reading" });
  assert.doesNotMatch(html, /<aside/);
  assert.match(html, /class="research-card-resources" role="group" aria-label="Question supporting reading"/);
});

test("retired split implementations have no remaining application callers or styles", () => {
  const files = fs.readdirSync(src, { recursive: true }).filter(file => /\.(jsx|css)$/.test(file));
  const retired = /\b(?:p2-method-layout|p2-method-account|p2-method-resources|p2-model-continuation|p2-resource-group|p2-preparation-layout|p2-preparation-editor|p2-preparation-resources|issue-team-split|issue-decision-layout|issue-decision-account|issue-decision-rail|has-resources)\b/;
  for (const file of files) assert.doesNotMatch(fs.readFileSync(path.join(src, file), "utf8"), retired, file);
});
