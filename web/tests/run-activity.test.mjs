import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { activitySummary } from "../src/runActivity.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-run-activity-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {RunActivity} from '${src}/components/RunDetail.jsx'; export const activity=props=>renderToStaticMarkup(React.createElement(RunActivity,props));`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const heartbeat = (message) => ({ type: "heartbeat", role: "research_lead", message });
const run = { state: "running", phase: "P1" };
const publicActivity = (html) => html.split('<details class="research-details" data-technical-activity="true">')[0];

test("preparation and lifecycle summaries do not expose internal filenames or settings records", () => {
  const events = [
    { type: "brief.assembled", role: "data_analyst", message: "Brief for data_analyst: 14,359 B." },
    { type: "turn.configured", role: "research_lead", message: "Applied research_lead settings for this turn." },
    heartbeat("turn start: p1.discovery.research_lead.md"),
    { type: "stage.running", message: "Stage p1.discovery running." },
  ];
  const html = render.activity({ run, events, connection: "live" });
  assert.match(publicActivity(html), /Prepared the task instructions|Applied the member&#x27;s model|Started work on the requested task/);
  assert.match(publicActivity(html), /Data Analyst|Research Lead|Research team/);
  assert.doesNotMatch(publicActivity(html), /data_analyst|research_lead|p1\.discovery|14,359/);
  assert.match(html, /p1\.discovery\.research_lead\.md/);
  assert.match(html, /<details class="research-details" data-technical-activity="true"><summary>Technical activity log/);
});

test("tool status stays about the tool and never declares a scientific or phase outcome", () => {
  for (const [raw, expected] of [
    ["running: powershell.exe -Command Get-Content C:/internal/schema.json", "Running a tool action."],
    ["completed: $schemaRoot='C:/internal'; Get-Content schema.json", "Tool action completed."],
    ["failed (exit 1): Get-Content schema.json; rg --files -g AGENTS.md", "Tool action returned exit code 1."],
    ["failed: python computation.py", "Tool action failed."],
    ["declined: git command", "Tool action was declined."],
  ]) {
    const summary = activitySummary(heartbeat(raw));
    assert.equal(summary.message, expected);
    assert.doesNotMatch(summary.message, /research.*(succeed|failed)|phase.*failed|scientific|schema|powershell|computation/i);
  }
  assert.equal(activitySummary(heartbeat("failed (exit 1): rg no matches")).tone, "warn");
  assert.equal(activitySummary(heartbeat("completed: rg matches")).tone, null);
});

test("literature queries, source URLs and retrieval errors remain visible", () => {
  const query = '"quantile" "constrained" reinforcement learning 2026';
  const url = "https://proceedings.mlr.press/v267/mcmahan25b.html";
  const events = [heartbeat(`searching: ${query}`), heartbeat(`searched: ${query}`), heartbeat(`opened page: ${url}`), heartbeat(`find in page completed: Theorem 6 in ${url}`), heartbeat(`page retrieval failed: ${url}`)];
  const visible = publicActivity(render.activity({ run, events, connection: "live" }));
  assert.ok(visible.includes(url));
  assert.match(visible, /quantile.*constrained.*reinforcement learning 2026/);
  assert.match(visible, /Searching literature|Literature search completed|Source text search completed|Source retrieval failed/);
  assert.equal(activitySummary(events.at(-1)).tone, "warn");
});

test("checks and repair stay visible without turning acceptance into publication", () => {
  assert.match(activitySummary({ type: "stage.mechanical_repair", attempt: 2 }).message, /correcting the saved work \(attempt 2\)/);
  const stopped = activitySummary({ type: "stage.mechanical_repair_stopped", reason: "unchanged_failure" });
  assert.match(stopped.message, /same issue remained.*Review the findings/);
  assert.equal(stopped.tone, "warn");
  assert.match(activitySummary({ type: "stage.validation", findings: [{ severity: "error" }] }).message, /reported 1 issue/);
  assert.match(activitySummary({ type: "run.failed", message: "Run failed: C:/internal/output.json" }).message, /stopped with a problem.*correction options/);
  const accepted = activitySummary({ type: "p4.control_accepted", operation: "run_batch" }).message;
  assert.equal(accepted, "Experiment request accepted.");
  assert.doesNotMatch(accepted, /completed|published|supported/);
  assert.match(activitySummary({ type: "p4.control_unknown" }).message, /outcome is unconfirmed/);
  assert.match(activitySummary({ type: "member.crashed", message: "research_lead turn raised: INTERNAL_FILE.json" }).message, /member's work stopped with a problem/);
  assert.equal(activitySummary({ type: "new.operation.failed", message: "INTERNAL_FILE.json" }).tone, "warn");
  assert.match(activitySummary({ type: "thread.resumed", message: "thread.INTERNAL" }).message, /Resumed the saved research conversation/);
});

test("raw records remain unchanged and collapsed even for unrecognized activity", () => {
  const events = [heartbeat("running: powershell.exe -Command PRIVATE_COMMAND"), { type: "new.internal_event", message: "PRIVATE_FILE.json", payload: { exact: "PRIVATE_VALUE" } }];
  const before = JSON.stringify(events);
  const html = render.activity({ run, events, connection: "live" });
  assert.equal(JSON.stringify(events), before);
  assert.doesNotMatch(publicActivity(html), /PRIVATE_COMMAND|PRIVATE_FILE|PRIVATE_VALUE|new\.internal_event/);
  assert.match(html, /PRIVATE_COMMAND|PRIVATE_FILE\.json|PRIVATE_VALUE/);
  assert.doesNotMatch(html, /data-technical-activity="true"[^>]*\bopen/);
});

test("recent activity limits do not discard earlier technical records", () => {
  const events = Array.from({ length: 65 }, (_, index) => heartbeat(`completed: command ${index}`));
  const html = render.activity({ run, events, connection: "live" });
  assert.equal((publicActivity(html).match(/class="row"/g) || []).length, 60);
  assert.match(html, /Show all 65 events/);
  assert.match(html, /completed: command 0/);
});
