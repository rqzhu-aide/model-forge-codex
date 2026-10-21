import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { executionStatus } from "../src/visualSemantics.js";

test("execution states distinguish work, a request for direction, completion and failure", () => {
  for (const state of ["requested", "running", "validating", "correcting", "promoting", "stopping"]) assert.equal(executionStatus(state).tone, "run", state);
  assert.deepEqual(executionStatus("awaiting_user"), { tone: "warn", label: "Waiting for your direction" });
  assert.deepEqual(executionStatus("stopping"), { tone: "run", label: "Stopping work" });
  for (const state of ["published", "assessed", "completed", "succeeded"]) assert.equal(executionStatus(state).tone, "ok", state);
  for (const state of ["failed", "infrastructure_error", "input_error", "output_error", "timed_out"]) assert.equal(executionStatus(state).tone, "fail", state);
});

test("stopped, unperformed and unfamiliar states never imply successful completion", () => {
  for (const [state, label] of [["cancelled", "Cancelled"], ["interrupted", "Interrupted"], ["not_run", "Not run"], ["pending", "Pending"], ["planned", "Planned"], ["deferred", "Deferred"], ["provider_unavailable", "Provider unavailable"], [null, "Unknown"], ["", "Unknown"]]) {
    assert.deepEqual(executionStatus(state), { tone: "mut", label });
  }
});

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-visual-semantics-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {ActionButton} from '${src}/components/Visuals.jsx'; import {SourceRef, RunState, Dialog} from '${src}/components/Shared.jsx'; export const button = props => renderToStaticMarkup(React.createElement(ActionButton, props)); export const rawButton = ActionButton; export const source = props => renderToStaticMarkup(React.createElement(SourceRef, props)); export const rawSource = SourceRef; export const state = props => renderToStaticMarkup(React.createElement(RunState, props)); export const dialog = props => renderToStaticMarkup(React.createElement(Dialog, props));`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

test("shared actions retain native button behavior and accessible names", () => {
  let opened = false;
  const props = { action: "details", children: "View details", "aria-expanded": false, "aria-controls": "details-panel", onClick: () => { opened = true; } };
  const tree = render.rawButton(props);
  assert.equal(tree.type, "button"); assert.equal(tree.props.type, "button"); tree.props.onClick(); assert.equal(opened, true);
  const html = render.button(props);
  assert.match(html, /aria-expanded="false"/); assert.match(html, /aria-controls="details-panel"/); assert.match(html, /data-action="details"/);
  assert.match(html, /aria-hidden="true"/); assert.match(html, /focusable="false"/); assert.match(html, /View details/);
  const iconOnly = render.button({ action: "ask", "aria-label": "Ask about this assumption", disabled: true });
  assert.match(iconOnly, /aria-label="Ask about this assumption"/); assert.match(iconOnly, /disabled=""/);
  assert.match(render.button({ action: "save", type: "submit", children: "Save" }), /type="submit"/);
});

test("source actions preserve exact reference linkage and remain disabled without a source handler", () => {
  const reference = { family: "protocol", generation_id: "protocol.v2", sha256: "saved-hash" };
  let opened;
  render.rawSource({ reference, onOpen: (value) => { opened = value; } }).props.onClick();
  assert.equal(opened, reference);
  const html = render.source({ reference });
  assert.match(html, /data-action="source"/); assert.match(html, /data-icon="source"/); assert.match(html, /disabled=""/);
  assert.equal(render.source({ reference: null }), "");
  assert.match(render.source({ reference: { family: "theory_record" } }), /exact source is not identified/);
});

test("shared run badges show a waiting request as attention and a cancelled run as neutral", () => {
  assert.equal(render.state({ state: "awaiting_user" }), '<span class="pill warn">Waiting for your direction</span>');
  assert.equal(render.state({ state: "cancelled" }), '<span class="pill mut">Cancelled</span>');
  const busy = render.dialog({ title: "Saving settings", busy: true, onClose() {} });
  assert.match(busy, /aria-busy="true"/); assert.match(busy, /aria-label="Close dialog" disabled=""/);
});
