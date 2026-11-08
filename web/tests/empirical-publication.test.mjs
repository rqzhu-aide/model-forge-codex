import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { empiricalPublicationPresentation } from "../src/empiricalPublication.js";

const record = { branch: "method.a", phase: "P4", published_at: "2026-11-07T10:00:00Z",
  generation_ref: { branch: "method.a", phase: "P4", family: "empirical_synthesis", generation_id: "generation.saved", sha256: "a".repeat(64), run_id: "run.saved", package_id: "package.saved" },
  scientific_outcome: { conclusion: "The checked calculation agrees within the studied conditions.", scope: "Only the saved synthetic cases were examined." },
  decision_summary: { implementation_markdown: "The saved implementation was checked.", method_recap_markdown: "The evaluated objective is $Q(\\beta)$." } };
const run = { branch_id: "method.a", phase: "P4", run_id: "run.new", state: "running", created_at: "2026-11-07T11:00:00Z" };
const present = (publication = record, attempt = run, branch = "method.a") => empiricalPublicationPresentation(publication, attempt, branch);
const current = { heading: "Summary", status: null, earlier: false };

test("an earlier exact publication names the last completed evaluation throughout a later P4 run", () => {
  for (const state of ["requested", "running", "validating", "correcting", "promoting", "stopping", "awaiting_user", "failed", "cancelled"]) {
    const shown = present(record, { ...run, state });
    assert.equal(shown.heading, "Last completed evaluation", state);
    assert.equal(shown.earlier, true, state);
    assert.match(shown.status, /findings below are from the last completed evaluation/, state);
  }
  assert.match(present(record, { ...run, state: "awaiting_user" }).status, /waiting for your direction/);
  assert.match(present(record, { ...run, state: "failed" }).status, /failed before publication/);
  assert.match(present(record, { ...run, state: "cancelled" }).status, /cancelled before publication/);
  for (const stage of ["p4.analyst", "p4.theorist", "p4.lead"]) {
    assert.deepEqual(present(record, { ...run, stage_states: { [stage]: "running" } }), present(), stage);
  }
  assert.equal(present(record, { ...run, intent: "run", assessment_purpose: "assessment" }).heading, "Last completed evaluation", "Ordinary scientific runs can carry the default assessment purpose.");
});

test("publication catch-up distinguishes the old account and clears when the new account arrives", () => {
  const finished = { ...run, state: "published" };
  assert.equal(present(record, finished).heading, "Previous completed evaluation");
  assert.match(present(record, finished).status, /newer evaluation has been published/);
  const replacement = { ...record, published_at: "2026-11-07T12:00:00Z", generation_ref: { ...record.generation_ref, run_id: run.run_id, package_id: "package.new" } };
  assert.deepEqual(present(replacement, finished), current);
  assert.deepEqual(present(record, { ...run, run_id: record.generation_ref.run_id, state: "published" }), current);
});

test("first run and unsupported method, phase, chronology or publication scope receive no earlier label", () => {
  const before = structuredClone({ record, run });
  for (const publication of [null, {}, { ...record, decision_summary: null }, { ...record, generation_ref: undefined },
    { ...record, generation_ref: { ...record.generation_ref, run_id: undefined } },
    { ...record, generation_ref: { ...record.generation_ref, package_id: undefined } },
    { ...record, branch: "method.b" }, { ...record, phase: "P3" },
    { ...record, generation_ref: { ...record.generation_ref, branch: "method.b" } },
    { ...record, generation_ref: { ...record.generation_ref, phase: "P3" } },
    { ...record, published_at: undefined }, { ...record, published_at: "invalid" }]) assert.deepEqual(present(publication), current);
  for (const attempt of [null, {}, { ...run, branch_id: "method.b" }, { ...run, phase: "P3" },
    { ...run, run_id: undefined }, { ...run, state: "unknown" }, { ...run, intent: "assessment" },
    { ...run, assessment_purpose: "explanation" }, { ...run, created_at: undefined },
    { ...run, created_at: "2026-11-07T09:00:00Z" }, { ...run, created_at: record.published_at }]) assert.deepEqual(present(record, attempt), current);
  assert.deepEqual(present(record, run, "method.b"), current);
  assert.deepEqual({ record, run }, before);
});

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-publication-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Workbench from '${src}/components/EmpiricalWorkbench.jsx'; export const render = props => renderToStaticMarkup(React.createElement(Workbench,props));`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

test("the workbench labels only earlier content, exposes a compact live status and preserves content anchors", () => {
  const props = { branch: "method.a", summaries: [record] };
  const oldHtml = ui.render(props);
  const activeHtml = ui.render({ ...props, progressRun: run, progressState: run.state });
  assert.match(activeHtml, /<h2>Last completed evaluation<\/h2>/);
  assert.match(activeHtml, /<div role="status" aria-atomic="true"><p class="note">A new evaluation is running/);
  assert.match(activeHtml, /<h3>Finding and scope<\/h3>/);
  assert.doesNotMatch(activeHtml, />Current finding(?: and scope)?</);
  assert.match(activeHtml, /Published finding/);
  for (const text of [record.scientific_outcome.conclusion, record.scientific_outcome.scope, record.decision_summary.implementation_markdown]) assert.ok(activeHtml.includes(text));
  const anchors = html => [...html.matchAll(/data-reading-anchor="([^"]+)"/g)].map(match => match[1]);
  assert.deepEqual(anchors(activeHtml), anchors(oldHtml));
  assert.match(ui.render({ ...props, progressState: "running", progressData: {} }), /<h2>Summary<\/h2>/, "Progress alone cannot identify an earlier publication.");
  const first = ui.render({ branch: "method.a", progressRun: run, progressData: {}, progressState: "running" });
  assert.match(first, /<h2>Summary<\/h2>/); assert.match(first, /evaluation is in progress/); assert.doesNotMatch(first, /Last completed evaluation/);
});
