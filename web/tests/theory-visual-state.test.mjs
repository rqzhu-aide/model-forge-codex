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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-theory-visual-state-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Theory from '${src}/components/TheoryWorkbench.jsx'; import {Outcome, RunState} from '${src}/components/Shared.jsx'; const render = Component => props => renderToStaticMarkup(React.createElement(Component, props)); export const theory = render(Theory); export const outcome = render(Outcome); export const run = render(RunState);`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};

test("scientific findings and completed execution remain distinguishable", () => {
  const published = render.run({ state: "published" });
  const contradicted = render.outcome({ state: "contradicted" });
  assert.match(published, /class="pill ok"/);
  assert.match(published, /Published/);
  assert.match(contradicted, /class="outcome-badge fail"/);
  assert.match(contradicted, /Finding:/);
  assert.match(contradicted, /Contradicted/);
  assert.match(contradicted, /data-icon="close"/);
  for (const state of [undefined, "completed", "published", "unfamiliar_result"]) {
    const html = render.outcome({ state });
    assert.match(html, /Not assessed/);
    assert.doesNotMatch(html, /Supported|class="pill/);
  }
  assert.match(render.outcome({ state: "no_observed_advantage" }), /No observed advantage/);
  assert.match(render.outcome({ state: "partially_supported" }), /Partly supported/);
  assert.match(render.outcome({ state: "inconclusive" }), /Inconclusive/);
});

const branch = "method.example";
const fixture = {
  branch, onSelect: noop, onRequest: noop, onSource: noop,
  claimMaps: [{ branch, phase: "P3", assumptions: [{ assumption_id: "assumption.independent", label: "Independent observations" }], claims: [
    { statement_id: "statement.cited", label: "Cited statement", proof_status: "cited", depends_on: ["assumption.independent"] },
    { statement_id: "statement.missing", label: "Missing proof", proof_status: "missing" },
    { statement_id: "statement.unrecorded", label: "Unrecorded proof" },
    { statement_id: "statement.adverse", label: "Contradicted statement", proof_status: "sketch" },
    { statement_id: "statement.probed", label: "Failed probe statement", proof_status: "full", latex: "x^2 \\geq 0" },
  ] }],
  glossaries: [{ branch, phase: "P3", glossary: { "statement.adverse": { status: "contradicted" } } }],
  falsificationLogs: [{ branch, phase: "P3", probes: [{ probe_id: "probe.one", target_statement: "statement.probed", method: "Boundary example", outcome: "fails_as_stated", detail: "The boundary example fails." }] }],
};
const nodeMarkup = (html, label) => [...html.matchAll(/<g\b[^>]*class="theory-node"[^>]*>[\s\S]*?<\/g>/g)].map(([node]) => node).find((node) => node.includes(`aria-label="${label}.`));

test("theory graph separates assumption shape, proof source and unresolved support", () => {
  const before = JSON.stringify(fixture);
  const html = render.theory(fixture);
  const assumption = nodeMarkup(html, "Independent observations");
  assert.match(assumption, /data-kind="assumption" data-tone="mut"/);
  assert.match(assumption, /class="theory-node-shape"[^>]*rx="23"[^>]*fill="var\(--panel\)"/);
  assert.doesNotMatch(assumption, /stroke-dasharray|assumption-soft|ok-soft/);
  const cited = nodeMarkup(html, "Cited statement");
  assert.match(cited, /data-kind="claim"/);
  assert.match(cited, /Claim · Cited proof/);
  assert.match(cited, /class="theory-node-shape"[^>]*stroke-dasharray="5 3"/);
  for (const label of ["Missing proof", "Unrecorded proof"]) {
    const node = nodeMarkup(html, label);
    assert.match(node, /data-tone="warn"/);
    assert.match(node, /Needs proof support/);
    assert.doesNotMatch(node, /var\(--danger\)|data-tone="fail"/);
  }
  assert.match(html, /role="list" aria-label="Theory graph key"/);
  assert.match(html, /class="graph-legend-item" role="listitem"><svg/);
  assert.equal(JSON.stringify(fixture), before);
});

test("a selected adverse probe asks for scope review without labeling its claim contradicted", () => {
  const html = render.theory({ ...fixture, selected: "statement.probed" });
  const node = nodeMarkup(html, "Failed probe statement");
  assert.match(node, /aria-pressed="true"/);
  assert.match(node, /role="button" tabindex="0"/);
  assert.match(node, /data-tone="warn"/);
  assert.match(node, /Claim · Full proof/);
  assert.match(node, /Review probe scope/);
  assert.match(node, /Inspect its tested scope and assumptions/);
  assert.doesNotMatch(node, /Contradicted/);
  assert.match(node, /class="theory-node-selection"[^>]*stroke="var\(--accent\)"/);
  assert.match(node, /class="theory-node-shape"[^>]*fill="var\(--panel-selected\)"[^>]*stroke="var\(--warn\)"/);
  assert.match(nodeMarkup(html, "Contradicted statement"), /data-tone="fail"/);
  assert.match(html, /class="katex/);
  assert.match(html, /Boundary example/);
  assert.match(html, /aria-label="Inspect Failed probe statement"/);
});

test("relaxed-assumption counterexamples retain the authored result and established statement status", () => {
  const detail = "The relaxed product-recursion claim fails; no failure of the specified independent synthetic law is asserted.";
  const props = { ...fixture, selected: "statement.probed", glossaries: [{ branch, phase: "P3", glossary: { "statement.probed": { status: "established" }, "statement.adverse": { status: "contradicted" } } }], falsificationLogs: [{ branch, phase: "P3", probes: [{ probe_id: "probe.relaxed", target_statement: "statement.probed", method: "Relax conditional independence while preserving marginals.", outcome: "fails_as_stated", detail }] }] };
  const before = JSON.stringify(props);
  const html = render.theory(props);
  assert.match(nodeMarkup(html, "Failed probe statement"), /Claim · Full proof/);
  assert.match(nodeMarkup(html, "Failed probe statement"), /data-tone="warn"/);
  assert.match(html, /Statement assessment: <span class="pill ok">Established/);
  assert.match(html, /<span class="pill fail">Fails as stated<\/span>/);
  assert.ok(html.includes(detail));
  assert.match(html, /Relax conditional independence while preserving marginals/);
  assert.doesNotMatch(html, /Probe failed|A falsification probe failed for this statement/);
  assert.match(nodeMarkup(html, "Contradicted statement"), /data-tone="fail"/);
  assert.equal(JSON.stringify(props), before);
});
