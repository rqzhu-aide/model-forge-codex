import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { sharedPackage } from "../scripts/shared-deps.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-reading-layout-"));
const bundle = path.join(directory, "render.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Literature from '${src}/components/LiteratureWorkspace.jsx'; import Methods from '${src}/components/MethodProposals.jsx'; import Empirical from '${src}/components/EmpiricalWorkbench.jsx'; import {PhaseTabs} from '${src}/components/PhaseReading.jsx'; import Progress from '${src}/components/ResearchProgress.jsx'; import FurtherWork from '${src}/components/FurtherWorkCard.jsx'; const draw = C => props => renderToStaticMarkup(React.createElement(C,props)); export const literature=draw(Literature), methods=draw(Methods), empirical=draw(Empirical), tabs=draw(PhaseTabs), progress=draw(Progress), furtherWork=draw(FurtherWork);`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const order = (html) => {
  assert.ok(html.indexOf('data-card-role="summary"') < html.indexOf("WORK_STATUS_FIXTURE"));
  assert.ok(html.indexOf("WORK_STATUS_FIXTURE") < html.indexOf('data-card-role="research"'));
};
test("composable readers preserve the overview before an optional activity slot", () => {
  const progress = "WORK_STATUS_FIXTURE";
  order(render.literature({ progress }));
  for (const props of [{ progress }, { progress, proposals: [{ proposal_id: "proposal.1", method: { title: "Estimator" }, generation_ref: { run_id: "run.1" } }] }]) {
    const html = render.methods(props);
    assert.equal((html.match(/data-card-role="research"/g) || []).length, props.proposals ? 2 : 1);
    assert.ok(html.indexOf("Proposed Methods</h2>") < html.indexOf("WORK_STATUS_FIXTURE"));
    assert.ok(html.indexOf("WORK_STATUS_FIXTURE") < html.indexOf(props.proposals ? "Choose a method</label>" : "Published proposals will appear here"));
  }
  order(render.empirical({ progress, branch: "method.a" }));
});
test("an explicit controlled Claims destination overrides a remembered Arguments tab", () => {
  const tabs = [{ id: "claims", label: "Claims", content: "CLAIMS_INSPECTOR" }, { id: "arguments", label: "Arguments", content: "ARGUMENT_ACCOUNT" }];
  const html = render.tabs({ tabs, initialTab: "arguments", selectedTab: "claims", label: "Theory" });
  assert.match(html, /CLAIMS_INSPECTOR/); assert.doesNotMatch(html, /ARGUMENT_ACCOUNT/);
});
test("activity distinguishes execution states and retains details in a closed native disclosure", () => {
  const states = { published: "Complete", assessed: "Complete", requested: "Queued", running: "Running", validating: "Running", correcting: "Running", stopping: "Stopping", awaiting_user: "Needs input", failed: "Failed", cancelled: "Stopped" };
  for (const [state, label] of Object.entries(states)) {
    const html = render.progress({ phase: "P3", run: { state, run_id: "exact.run" }, retained: true, onOpenRun: () => {}, onShowIssues: () => {} });
    assert.match(html, /^<details[^>]*data-work-state=/);
    assert.ok(html.includes(`P3 latest update: ${label}. Activity details`));
    assert.doesNotMatch(html.split(">", 1)[0], /\bopen=/);
    assert.match(html, /Activity details[\s\S]*Open run history/);
    if (["failed", "cancelled"].includes(state)) assert.match(html, /did not replace the retained results/);
    if (state === "awaiting_user") assert.match(html, /Review requested input/);
  }
  assert.equal(render.progress({ phase: "P3" }), "");
  const unknown = render.progress({ phase: "P3", run: { state: "unfamiliar", run_id: "unknown" } });
  assert.match(unknown, /Unfamiliar/); assert.doesNotMatch(unknown, /Complete/);
  const olderCorrection = render.progress({ phase: "P3", run: { state: "published", run_id: "latest" }, correctionCount: 1, onShowIssues: () => {} });
  assert.match(olderCorrection, /latest update: Complete/); assert.match(olderCorrection, /Review interrupted work \(1 work correction\)/);
});

test("run history can show activity details immediately without expanding project activity", () => {
  const html = render.progress({ phase: "P4", run: { state: "running", run_id: "history.run" }, expanded: true, children: "RECORDED_EXECUTION_HISTORY" });
  assert.match(html.split(">", 1)[0], /\bopen=/);
  assert.match(html, /RECORDED_EXECUTION_HISTORY/);
});

test("rerun summary and collapsed instructions share one card with mounted recommendations and draft controls", () => {
  const html = render.furtherWork({ projectId: "compact.fixture", phase: "P3", branch: "method.a", hasRun: true, recommendations: "A uniform remainder bound remains open." });
  assert.match(html, /^<section[^>]*data-reading-anchor="rerun-summary"/);
  const settings = html.match(/<details[^>]*data-reading-anchor="further-work"[^>]*>/)?.[0];
  assert.ok(settings); assert.doesNotMatch(settings, /\bopen=/);
  assert.match(html, /<h2>Revise and rerun<\/h2>/);
  assert.match(html, /<summary>Tell me what to do next<\/summary>/);
  assert.equal((html.match(/class="card(?:\s|")/g) || []).length, 1);
  assert.equal((html.match(/<h2>/g) || []).length, 1);
  assert.match(html, /A uniform remainder bound remains open/);
  assert.match(html, /Loading your saved instructions/);
});

test("P5 report revision keeps its native settings disclosure and addressable recovery target", () => {
  const html = render.furtherWork({ projectId: "compact.fixture", phase: "P5", branch: "method.a", hasRun: true });
  assert.match(html, /^<section[^>]*data-reading-anchor="rerun-summary"/);
  const settings = html.match(/<details[^>]*id="p5-additional-work"[^>]*data-reading-anchor="further-work"[^>]*>/)?.[0];
  assert.ok(settings); assert.doesNotMatch(settings, /\bopen=/);
  assert.match(html, /<h2>Revise report<\/h2>/);
  assert.match(html, /<summary>Tell me what to do next<\/summary>/);
  assert.doesNotMatch(html, /Research questions|Study understanding|Discuss your problem/);
});

test("a first run has one instructions card and an immediately available form in every phase", () => {
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const html = render.furtherWork({ projectId: "first.fixture", phase, branch: "method.a", hasRun: false });
    assert.equal((html.match(/class="card(?:\s|")/g) || []).length, 1);
    assert.match(html, /<h2>Instructions and run settings<\/h2>/);
    assert.match(html.match(/<details[^>]*data-reading-anchor="further-work"[^>]*>/)?.[0] || "", /\bopen=/);
    assert.match(html, /<summary hidden="">Tell me what to do next<\/summary>/);
    assert.doesNotMatch(html, /Revise and rerun|Revise report|Research questions|Study understanding/);
  }
});
