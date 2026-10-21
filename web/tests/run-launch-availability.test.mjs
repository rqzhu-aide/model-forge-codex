import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { activePhaseRun, phaseNavigationState } from "../src/phaseUiState.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-launch-availability-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import LaunchRun from '${src}/components/LaunchRun.jsx'; export const launch=props=>renderToStaticMarkup(React.createElement(LaunchRun,props));`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const run = { run_id: "INTERNAL_ACTIVE_RUN", phase: "P3", branch_id: "method.a", state: "running", intent: "run" };
const submit = (html) => (html.match(/<button\b[^>]*type="submit"[^>]*>[\s\S]*?<\/button>/g) || [])[0];

test("active work reserves only its phase and branch through completion or cancellation", () => {
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const branch = ["P1", "P2"].includes(phase) ? "trunk" : "method.a";
    for (const state of ["requested", "running", "correcting", "validating", "awaiting_user", "stopping"]) {
      const current = { ...run, phase, branch_id: branch, state };
      assert.equal(activePhaseRun([current], phase, "method.a"), current, `${phase}:${state}`);
    }
    for (const state of ["published", "assessed", "failed", "cancelled"]) {
      assert.equal(activePhaseRun([{ ...run, phase, branch_id: branch, state }], phase, "method.a"), null);
    }
  }
  assert.equal(activePhaseRun([run], "P4", "method.a"), null);
  assert.equal(activePhaseRun([run], "P3", "method.b"), null);
  assert.equal(activePhaseRun([{ ...run, phase: "P2", branch_id: "method.b" }], "P2", "method.a"), null);
});

test("assessments share the launch slot while independent issue explanations do not", () => {
  for (const purpose of ["assessment", "explanation"]) {
    const assessment = { ...run, intent: "assessment", mode: "p3.assessment", assessment_purpose: purpose };
    assert.equal(activePhaseRun([assessment], "P3", "method.a"), assessment);
    assert.equal(phaseNavigationState({ phase: "P3", branch: "method.a", runs: [assessment] }).state, "idle");
  }
  const issue = { ...run, intent: "assessment", assessment_purpose: "issue_explanation" };
  assert.equal(activePhaseRun([issue], "P3", "method.a"), null);
  assert.equal(activePhaseRun([issue, run], "P3", "method.a"), run);
});

test("all phase launch forms explain active work and preserve editable next-run instructions", () => {
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const activeRun = { ...run, phase, branch_id: ["P1", "P2"].includes(phase) ? "trunk" : "method.a" };
    const html = render.launch({ projectId: "project.a", request: { phase, branch: activeRun.branch_id }, activeRun, embedded: true, instructions: "Draft a different research direction." });
    assert.match(submit(html), /disabled=""/);
    assert.match(submit(html), /Work already in progress/);
    assert.match(html, /role="status">Work already in progress/);
    assert.match(html, /prepare instructions for the next run/);
    assert.match(html, /Draft a different research direction/);
    assert.doesNotMatch(html.match(/<textarea\b[^>]*>/)?.[0] || "", /disabled/);
    assert.doesNotMatch(html, /INTERNAL_ACTIVE_RUN|Start literature study|Start theory development|Start manuscript work/);
  }
});

test("waiting and stopping work retain accurate status and block focused assessment requests", () => {
  for (const [state, label] of [["awaiting_user", "Current work is waiting for your direction"], ["stopping", "Current work is stopping"]]) {
    const html = render.launch({ projectId: "project.a", request: { phase: "P3", branch: "method.a", mode: "p3.assessment" }, activeRun: { ...run, state }, embedded: true });
    assert.match(submit(html), /disabled=""/);
    assert.ok(submit(html).includes(label));
    assert.doesNotMatch(submit(html), /Request assessment/);
  }
  const available = render.launch({ projectId: "project.a", request: { phase: "P1", branch: "trunk" }, embedded: true });
  assert.match(submit(available), /Start literature study/);
  assert.doesNotMatch(available, /Work already in progress|prepare instructions for the next run/);
});
