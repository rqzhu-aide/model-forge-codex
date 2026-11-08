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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-report-labels-"));
const bundle = path.join(directory, "test.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {ReportSummary} from '${src}/components/TechnicalReportReading.jsx'; export {SourceRef} from '${src}/components/Shared.jsx'; const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher; export function summary(props,host) { const previous=dispatcher.current; dispatcher.current={useContext:()=>host}; try { return ReportSummary(props); } finally { dispatcher.current=previous; } }`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const walk = node => Array.isArray(node) ? node.flatMap(walk) : !node || typeof node !== "object" ? [] : [node, ...walk(node.props?.children), ...walk(node.props?.resources), ...walk(node.props?.actions)];
const reference = family => ({ branch: "method.exact", phase: "P5", family, generation_id: `${family}.exact`, sha256: "a".repeat(64), run_id: "run.report", package_id: "package.report" });
const report = { kind: "technical_report", body_md: "The report retains its conditional scientific account.", generation_ref: reference("technical_report") };
const lead = { evaluation_markdown: "The summary retains its uncertainty.", generation_ref: reference("lead_summary") };
const decision = { conclusion: "The decision retains the decisive condition.", generation_ref: reference("decision_record") };

test("report source labels identify the account actually bound to each action", () => {
  for (const paired of [decision, { ...decision, conclusion: undefined }, undefined]) {
    const opened = [];
    const tree = ui.summary({ documents: [report], decision: paired, summaries: [lead], onSource: source => opened.push(source) }, { scope: {} });
    const sources = walk(tree).filter(node => node.type === ui.SourceRef);
    const account = sources.find(node => node.props.label.startsWith("Lead "));
    assert.equal(account.props.label, paired?.conclusion ? "Lead decision source" : "Lead summary source");
    ui.SourceRef(account.props).props.onClick();
    assert.deepEqual(opened, [paired?.conclusion ? decision.generation_ref : lead.generation_ref]);
    assert.ok(sources.some(node => node.props.label === "Inspect exact report source" && node.props.reference === report.generation_ref));
  }
});

test("the separately opened Lead summary keeps its selected source version and callback", () => {
  const opened = [], later = []; let snapshot;
  const trigger = { isConnected: true };
  const host = { scope: { projectId: "project.exact", phase: "P5", branch: "method.exact" }, open(value, invoker) { snapshot = value; assert.equal(invoker, trigger); } };
  const props = { documents: [report], decision, summaries: [lead], onSource: source => opened.push(source) };
  const tree = ui.summary(props, host);
  const button = walk(tree).find(node => node.props?.title === "Lead summary" && node.props.onClick);
  assert.ok(button); button.props.onClick({ currentTarget: trigger });
  const chosen = snapshot;
  ui.summary({ ...props, summaries: [{ ...lead, generation_ref: { ...lead.generation_ref, generation_id: "lead_summary.new", sha256: "b".repeat(64) } }], onSource: source => later.push(source) }, host);
  const source = walk(chosen.body).find(node => node.type === ui.SourceRef);
  assert.equal(chosen.title, "Lead summary");
  assert.equal(source.props.label, "Lead summary source");
  ui.SourceRef(source.props).props.onClick();
  assert.deepEqual(opened, [lead.generation_ref]); assert.deepEqual(later, []);
});
