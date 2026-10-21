import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { availableDataViews, questionDataLabel, questionDataOrigins } from "../src/empirical.js";
import { normalizeReader, restoreOpenDisclosures } from "../src/readingPosition.js";
import { singleEvaluatedMethod } from "../src/phaseUiState.js";
import { api } from "../src/api.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-workflow-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Workbench,{focusHeadlineExhibit} from '${src}/components/EmpiricalWorkbench.jsx'; import {EmpiricalDecisionSummary,EmpiricalFullInterpretation} from '${src}/components/EmpiricalQuestion.jsx'; import Implementation from '${src}/components/ImplementationReading.jsx'; import Inputs,{fileContentBase64,MAX_INPUT_BYTES} from '${src}/components/EmpiricalInputs.jsx'; const draw=C=>props=>renderToStaticMarkup(React.createElement(C,props)); export const workbench=draw(Workbench); export const implementation=draw(Implementation); export const inputs=draw(Inputs); export {fileContentBase64,MAX_INPUT_BYTES,EmpiricalDecisionSummary,EmpiricalFullInterpretation,focusHeadlineExhibit};`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.a", phase: "P4", family: "protocol", generation_id: "protocol.one", sha256: "a".repeat(64), run_id: "run.one", package_id: "package.one" };
const cases = [{ case_id: "sim", data_source_ids: ["simulation"] }, { case_id: "obs", data_source_ids: ["cohort"] }, { case_id: "bench", data_source_ids: ["public"] }];
const protocol = { branch: "method.a", generation_ref: ref, cases, data_sources: [{ data_source_id: "simulation", label: "Known truth", origin: "synthetic" }, { data_source_id: "cohort", label: "Local cohort", origin: "researcher_observed" }], amendments: [{ added_data_sources: [{ data_source_id: "public", label: "Public comparison", origin: "external_data" }] }] };
const question = { branch: "method.a", question_id: "test.mixed", test_id: "test.mixed", generation_ref: ref, title: "Does the method transfer?", case_ids: ["sim", "obs"], result: { category: "performance", outcome: "inconclusive", answer_markdown: "The synthetic and observed findings have different scopes.", limitations_markdown: "Observed truth is unknown." } };
const summary = { branch: "method.a", generation_ref: { ...ref, family: "empirical_synthesis" }, decision_summary: { conclusion_markdown: "A conditional result.", intent_markdown: "Study transfer of the fixed method.", coverage: [{ dimension: "accuracy", status: "partial", question_ids: [question.question_id] }] }, actual_data_application: { status: "analyzed", summary_markdown: "The local cohort was analyzed without a known truth." } };
const props = { branch: "method.a", protocols: [protocol], questions: [question], summaries: [summary] };

test("origin routing uses exact case/source links, prospective sources and explicit legacy Other", () => {
  assert.deepEqual(questionDataOrigins(question, [], [protocol]), ["synthetic", "researcher_observed"]);
  assert.equal(questionDataLabel(questionDataOrigins(question, [], [protocol])), "Mixed");
  const benchmark = { ...question, case_ids: ["bench"] };
  assert.deepEqual(questionDataOrigins(benchmark, cases, [protocol]), ["external_data"]);
  assert.deepEqual(questionDataOrigins({ ...question, case_ids: ["legacy"] }, [{ case_id: "legacy" }], [protocol]), ["other"]);
  const old = { ...protocol, generation_ref: { ...ref, run_id: "earlier", package_id: "earlier" } };
  assert.deepEqual(questionDataOrigins(question, [], [old]), ["other"], "Matching case/source names do not import an earlier evaluation's origin.");
  assert.deepEqual(availableDataViews([question, benchmark], cases, [protocol]).map(([key]) => key), ["all", "synthetic", "researcher_observed", "external_data"]);
});

test("retired data selections cannot hide a mixed answer or actual-data status", () => {
  const before = structuredClone(props);
  for (const dataView of ["all", "synthetic", "researcher_observed"]) {
    const html = ui.workbench({ ...props, reading: { dataView } });
    for (const text of [question.title, question.result.answer_markdown, question.result.limitations_markdown, "Mixed", "Accuracy: Partial", summary.decision_summary.conclusion_markdown, "Implementation and Code", "The local cohort was analyzed"]) assert.ok(html.includes(text), text);
    assert.doesNotMatch(html, /empirical-data-picker|<select/);
    assert.match(html, /<details class="question-detail empirical-question-row"[^>]*><summary>[\s\S]*Finding[\s\S]*Inconclusive[\s\S]*Mixed[\s\S]*Accuracy: Partial<\/span><\/span><\/summary>/);
    assert.match(html, /role="tab"[^>]*aria-selected="true"[^>]*><span>Performance/);
  }
  assert.deepEqual(props, before);
});

test("saved empty topics survive while retired data selections are ignored", () => {
  const saved = normalizeReader({ tab: "tuning", dataView: "researcher_observed" }, "P4");
  assert.deepEqual(saved, { tab: "tuning", dataView: "researcher_observed" });
  const html = ui.workbench({ ...props, reading: saved });
  assert.match(html, /role="tab"[^>]*aria-selected="true"[^>]*><span>Tuning/);
  assert.doesNotMatch(html, /<select/);
  assert.doesNotMatch(html, /data-question-id="test.mixed"/);
  assert.match(html, /A conditional result/);
  const fallback = ui.workbench({ ...props, reading: { dataView: "computational_check" } });
  assert.doesNotMatch(fallback, /<select/);
  assert.match(fallback, /Does the method transfer/);
});

test("an absent readable data label does not expose its internal source ID in the summary", () => {
  const source = { data_source_id: "source.internal.synthetic.12488", origin: "synthetic" };
  const sources = { ...protocol, data_sources: [source], amendments: [] };
  const before = structuredClone(sources);
  const html = ui.workbench({ ...props, protocols: [sources] });
  const note = html.match(/<p class="note">Recorded data: ([^<]*)<\/p>/)?.[1];
  assert.equal(note, "Unnamed data source (Synthetic)");
  assert.deepEqual(sources, before, "The exact authored source remains available in its detailed record.");
});

test("a verified headline has one quantitative home inside experiments and question detail links to it", () => {
  const exhibit = { exhibit_id: "table.main", branch: "method.a", phase: "P4", test_ids: [question.test_id], title: "Paired error", source_verified: true, generation_ref: { ...ref, family: "exhibits" }, table: { columns: [{ key: "value", label: "Difference" }], rows: [{ value: -0.00000019 }, { value: 0 }] } };
  const html = ui.workbench({ ...props, exhibits: [exhibit], summaries: [{ ...summary, decision_summary: { ...summary.decision_summary, headline_exhibit_ids: [exhibit.exhibit_id] } }] });
  assert.equal((html.match(/<figure/g) || []).length, 1);
  assert.ok(html.indexOf("Paired error") > html.indexOf("Experiments and Results"));
  assert.match(html, /View Paired error in Experiments and Results/);
  assert.match(html, /<td>0<\/td>/);
  assert.doesNotMatch(html.slice(0, html.indexOf("Experiments and Results")), /<figure|<table/);
  const stale = ui.workbench({ ...props, exhibits: [{ ...exhibit, generation_ref: { ...ref, family: "exhibits", run_id: "old" } }], summaries: [{ ...summary, decision_summary: { ...summary.decision_summary, headline_exhibit_ids: [exhibit.exhibit_id] } }] });
  assert.match(stale, /1 referenced result exhibit could not be verified or loaded/);
  assert.match(stale, /A conditional result/);
});

test("qualified authored conclusion and scope keep the full interpretation and purpose closed but intact", () => {
  const record = { ...summary, scientific_outcome: { state: "partially_supported", conclusion: "Lower conditional paired MAE is limited by scarce nonreturn and unassessed interval coverage.", scope: "One synthetic uncertainty cohort and 300 independent point cohorts; no actual data." }, decision_summary: { ...summary.decision_summary, conclusion_markdown: "The full conclusion retains all measured tradeoffs.", tradeoff_markdown: "Lower conditional error coexists with increased downward bias.", limitations_markdown: "Twelve scarce attempts failed; nominal coverage is unassessed.", intent_markdown: "Evaluate the declared target using the frozen method, comparator and seeds." } };
  const before = structuredClone(record);
  const html = ui.workbench({ ...props, summaries: [record], onSource() {} });
  const full = html.match(/<details class="research-details empirical-full-interpretation"[^>]*>[\s\S]*?<\/details>/)?.[0];
  assert.ok(full);
  assert.doesNotMatch(full.slice(0, full.indexOf(">") + 1), /\sopen(?:[=\s>])/);
  assert.match(full, /data-reading-anchor="evaluation:protocol.one:full-interpretation"/);
  for (const field of ["conclusion_markdown", "tradeoff_markdown", "limitations_markdown", "intent_markdown"]) assert.ok(full.includes(record.decision_summary[field]), field);
  const visible = html.slice(0, html.indexOf('class="card empirical-code-card"')).replace(/<details\b[\s\S]*?<\/details>/g, "");
  assert.ok(visible.includes(record.scientific_outcome.conclusion));
  assert.ok(visible.includes(record.scientific_outcome.scope));
  assert.ok(visible.includes(record.actual_data_application.summary_markdown));
  for (const field of ["conclusion_markdown", "tradeoff_markdown", "limitations_markdown", "intent_markdown"]) assert.ok(!visible.includes(record.decision_summary[field]), field);
  const sourcePointers = [];
  const visit = (node) => { if (Array.isArray(node)) return node.forEach(visit); if (!node?.props) return; if (node.props.reference) sourcePointers.push(node.props.reference); visit(node.props.children); };
  visit(ui.EmpiricalDecisionSummary({ record, onSource() {} }));
  visit(ui.EmpiricalFullInterpretation({ record, onSource() {} }));
  for (const pointer of ["/scientific_outcome/conclusion", "/scientific_outcome/scope", ...["conclusion_markdown", "tradeoff_markdown", "limitations_markdown", "intent_markdown"].map((field) => `/decision_summary/${field}`)]) {
    const source = sourcePointers.find((reference) => reference.entry_pointer === pointer);
    assert.ok(source, pointer); assert.equal(source.run_id, ref.run_id); assert.equal(source.generation_id, ref.generation_id);
  }
  assert.deepEqual(record, before);
});

test("legacy and incomplete concise outcomes preserve the full original interpretation under details", () => {
  const account = { ...summary.decision_summary, tradeoff_markdown: "Retain the complete tradeoff.", limitations_markdown: "Retain the complete limitations.", intent_markdown: "Retain the full purpose." };
  for (const scientific_outcome of [undefined, { conclusion: "Only a conclusion." }, { scope: "Only a scope." }, { conclusion: "A conclusion.", scope: "  " }]) {
    const html = ui.workbench({ ...props, summaries: [{ ...summary, scientific_outcome, decision_summary: account }] });
    assert.match(html, /empirical-full-interpretation/);
    const visible = html.slice(0, html.indexOf('class="card empirical-code-card"')).replace(/<details\b[\s\S]*?<\/details>/g, "");
    for (const field of ["conclusion_markdown", "tradeoff_markdown", "limitations_markdown", "intent_markdown"]) { assert.ok(html.includes(account[field]), field); assert.ok(!visible.includes(account[field]), field); }
  }
});

test("Lead ordering prioritizes all canonical topic exhibits inside experiments without duplicate tables", () => {
  const exhibits = ["cost", "primary", "points", "paired"].map((name) => ({ exhibit_id: `table.${name}`, branch: "method.a", phase: "P4", test_ids: [question.test_id], title: `Headline ${name}`, caption: `Complete ${name} caption with return and uncertainty qualifications.`, source_verified: true, generation_ref: { ...ref, family: "exhibits" }, table: { columns: [{ key: "value", label: "Value" }], rows: Array.from({ length: name === "cost" ? 15 : 3 }, (_, value) => ({ value })) } }));
  const record = { ...summary, decision_summary: { ...summary.decision_summary, headline_exhibit_ids: ["table.paired", "table.points", "table.primary", "table.cost"] } };
  const html = ui.workbench({ ...props, exhibits, summaries: [record] });
  const additional = html.slice(html.indexOf("Experiments and Results"));
  assert.ok(html.indexOf("Headline paired") > html.indexOf("Experiments and Results"));
  assert.equal((html.match(/<figure\b/g) || []).length, 4);
  for (const name of ["points", "primary", "cost"]) {
    assert.ok(additional.includes(`Headline ${name}`));
    assert.ok(additional.includes(`Complete ${name} caption with return and uncertainty qualifications.`));
    assert.ok(html.includes(`View Headline ${name} in Experiments and Results`));
  }
  assert.match(additional, /<td>14<\/td>/, "The fifteen-row cost table is retained without excerpting.");
  assert.ok(additional.indexOf("Headline points") < additional.indexOf("Headline primary"));
  assert.ok(additional.indexOf("Headline primary") < additional.indexOf("Headline cost"));
});

test("headline navigation opens its containing disclosures before focus and preserves a stable return path", () => {
  const enclosing = { tagName: "DETAILS", open: false, parentElement: null };
  const additional = { tagName: "DETAILS", open: false, parentElement: { tagName: "SECTION", parentElement: enclosing }, getAttribute: () => "evaluation:protocol.one:additional-headlines", querySelector: () => ({ textContent: "Additional headline exhibits (3)" }) };
  const calls = [];
  const target = { parentElement: additional, focus(options) { assert.ok(additional.open); assert.ok(enclosing.open); calls.push(["focus", options]); }, scrollIntoView(options) { calls.push(["scroll", options]); } };
  ui.focusHeadlineExhibit(target);
  assert.deepEqual(calls, [["focus", { preventScroll: true }], ["scroll", { block: "start" }]]);
  additional.open = false;
  restoreOpenDisclosures({ querySelectorAll: () => [additional] }, [{ index: 99, summary: "Additional headline exhibits (2)", anchor: "evaluation:protocol.one:additional-headlines" }]);
  assert.equal(additional.open, true, "Reading restoration follows the exact disclosure anchor after counts or surrounding details change.");
  assert.doesNotThrow(() => ui.focusHeadlineExhibit(null));
});

test("portable delivery exposes verified source/download controls and preserves unavailable files", () => {
  const artifact = { path: "implementation/model.py", sha256: "b".repeat(64) };
  const record = { producer_role: "data_analyst", generation_ref: ref, reproduction: { status: "available", language: "python", model_entrypoint: { kind: "model", artifact }, invocation: "python model.py --config example.json" }, files: [{ ...artifact, kind: "model", source_verified: true, artifact_url: "/api/exact", download_url: "/api/exact?download=true" }, { path: "helper.py", kind: "helper", source_verified: false, source_error: "The helper digest does not match.", download_url: "/do-not-download" }], bundle_url: "/api/bundle", sections: [{ key: "verification", body_md: "The independent reference check passed within tolerance." }] };
  const html = ui.implementation({ records: [record] });
  for (const text of ["Model entrypoint", artifact.path, "Inspect model entrypoint", "Download model entrypoint", "Download code and example bundle", record.reproduction.invocation, "The helper digest does not match", "The independent reference check passed"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /href="\/do-not-download"/);
  const legacy = ui.implementation({ records: [{ files: [] }] });
  assert.match(legacy, /No verified code/); assert.doesNotMatch(legacy, /Download code and example bundle/);
});

test("only a sole published evaluation receives a viewing default", () => {
  const run = { branch_id: "method.a", phase: "P4", state: "published" };
  assert.equal(singleEvaluatedMethod({ runs: [run] }), "method.a");
  assert.equal(singleEvaluatedMethod({ runs: [{ ...run, state: "failed" }] }), null);
  assert.equal(singleEvaluatedMethod({ runs: [run, { ...run, branch_id: "method.b" }] }), null);
  assert.equal(singleEvaluatedMethod({ runs: [{ ...run, assessment_purpose: "explanation" }] }), null);
});

test("local input bytes use the project import API and selection alone has no run action", async () => {
  const original = globalThis.fetch; const calls = [];
  globalThis.fetch = async (url, options) => { calls.push({ url, ...options }); return { ok: true, status: 200, json: async () => ({ input_id: "input.one" }) }; };
  try {
    await api.inputs("project.one");
    await api.importInput("project.one", { filename: "cohort.csv", role: "dataset", content_base64: "eCx5CjEsMgo=", description: "Local example", mapping: { notes: "x is exposure; y is outcome" } });
    assert.deepEqual(calls.map((item) => item.url), ["/api/v1/projects/project.one/inputs", "/api/v1/projects/project.one/inputs"]);
    assert.equal(calls[1].method, "POST");
    assert.deepEqual(JSON.parse(calls[1].body).mapping, { notes: "x is exposure; y is outcome" });
    assert.ok(calls.every((item) => !item.url.includes("/runs")));
    const html = ui.inputs({ projectId: "project.one", selected: [], onChange() {} });
    assert.match(html, /type="file"/); assert.match(html, /Import and select file/); assert.match(html, /does not start work/);
    assert.doesNotMatch(html, /type="submit"|href=/);
    assert.equal(ui.MAX_INPUT_BYTES, 64 * 1024 * 1024);
  } finally { globalThis.fetch = original; }
});
