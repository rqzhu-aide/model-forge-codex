import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { exhibitKey, routeEmpiricalExhibits } from "../src/empirical.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-scientific-presentation-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Workbench from '${src}/components/EmpiricalWorkbench.jsx'; import {EmpiricalDecisionSummary,EmpiricalNotation} from '${src}/components/EmpiricalQuestion.jsx'; import {EmpiricalSourceProvider} from '${src}/components/EmpiricalDocument.jsx'; export const render = props => renderToStaticMarkup(React.createElement(Workbench,props)); export const summary = props => renderToStaticMarkup(React.createElement(EmpiricalDecisionSummary,props)); export const notation = (props,sources) => renderToStaticMarkup(React.createElement(EmpiricalSourceProvider,{value:sources},React.createElement(EmpiricalNotation,props))); export const summaryElement = EmpiricalDecisionSummary; export const notationElement = EmpiricalNotation;`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const ref = { branch: "method.a", phase: "P4", family: "empirical_synthesis", generation_id: "summary.current", sha256: "a".repeat(64), run_id: "run.current", package_id: "package.current" };
const record = {
  branch: ref.branch, generation_ref: ref,
  scientific_outcome: { conclusion: "The method reduced error in the tested setting.", scope: "Only synthetic observations were evaluated." },
  decision_summary: {
    method_recap_markdown: "The method estimates a population mean $\\mu$ using independent training and assessment samples.",
    method_formulation_markdown: "The complete formulation defines every fitting quantity.\n\n$$\n\\widehat\\mu=\\frac{1}{n}\\sum_{i=1}^n X_i\n$$",
    implementation_markdown: "The saved implementation evaluates the full procedure.",
    notation_markdown: "| Symbol | Definition | Meaning and units |\n| --- | --- | --- |\n| $\\mu$ | $\\mathbb E[X]$ | Population mean; units have not been supplied. |",
    coverage: [{ dimension: "performance", status: "partial", question_ids: ["question.mean"], summary: "The method reduced error with uncertain generalization.", limitation_markdown: "Only one generating distribution was tested." }],
  },
};

// Inspect component props to check exact source identity, rather than its label.
function elements(node) {
  if (Array.isArray(node)) return node.flatMap(elements);
  if (!node || typeof node !== "object" || !node.props) return [];
  return [node, ...elements(node.props.children)];
}

test("authored recap is visible and the complete formulation retains its exact separate source", () => {
  const before = structuredClone(record);
  const html = render.summary({ record, onSource: noop, onNotation: noop });
  const detail = html.indexOf('<details class="research-details empirical-method-definition"');
  assert.ok(detail > 0);
  assert.match(html.slice(0, detail), /The method estimates a population mean/);
  assert.doesNotMatch(html.slice(0, detail), /The complete formulation defines/);
  assert.match(html.slice(detail), /The complete formulation defines every fitting quantity/);
  assert.match(html.slice(detail), /\\widehat\\mu=\\frac/);
  const sources = elements(render.summaryElement({ record, onSource: noop })).filter((node) => node.props.reference);
  assert.deepEqual(sources.find((node) => node.props.label === "Method recap").props.reference, { ...ref, entry_pointer: "/decision_summary/method_recap_markdown" });
  assert.deepEqual(sources.find((node) => node.props.label === "Implemented method").props.reference, { ...ref, entry_pointer: "/decision_summary/method_formulation_markdown" });
  assert.deepEqual(record, before);
});

test("a deliberately authored recap retains even a one-paragraph full formulation in details", () => {
  const value = { ...record, decision_summary: { ...record.decision_summary, method_formulation_markdown: "Complete single-paragraph criterion with its conditions." } };
  const html = render.summary({ record: value });
  assert.match(html, /<details class="research-details empirical-method-definition"[^>]*><summary>Full mathematical formulation and fitting criterion<\/summary><div class="research-document"><p>Complete single-paragraph criterion/);
  assert.equal((html.match(/Complete single-paragraph criterion/g) || []).length, 1);
});

test("older records keep their first-paragraph recap and single-block equations without an invented glossary", () => {
  const decision_summary = { implementation_markdown: "The implementation was evaluated.", method_formulation_markdown: "Legacy definition stays readable.\n\n$$\\theta=\\mathbb E[X]$$" };
  const legacy = { ...record, decision_summary };
  const before = structuredClone(legacy);
  const html = render.summary({ record: legacy, onNotation: noop });
  assert.match(html.slice(0, html.indexOf('<details class="research-details empirical-method-definition"')), /Legacy definition stays readable/);
  assert.equal((html.match(/Legacy definition stays readable/g) || []).length, 2);
  assert.doesNotMatch(html, />Notation<\/button>|Method recap/);
  const single = render.summary({ record: { ...legacy, decision_summary: { ...decision_summary, method_formulation_markdown: "$$\\theta=\\mathbb E[X]$$" } } });
  assert.match(single, /class="katex-display"/);
  assert.doesNotMatch(single, /empirical-method-definition/);
  assert.deepEqual(legacy, before);
});

test("an authored finding is shown once even when its older record omits a separate scope", () => {
  const value = { ...record, scientific_outcome: { conclusion: "The observed comparison remains conditional." } };
  const html = render.render({ branch: ref.branch, summaries: [value] });
  assert.match(html.slice(0, html.indexOf("Implementation and Code")), /The observed comparison remains conditional/);
  const finding = html.slice(html.indexOf('<section class="empirical-overview-section"'), html.indexOf('class="empirical-overview-section empirical-method-formulation"'));
  assert.match(finding, /<h3>Current finding<\/h3>/);
  assert.doesNotMatch(finding, /Current finding and scope|No readable document has been recorded yet/);
  assert.equal((html.match(/The observed comparison remains conditional/g) || []).length, 1);
  assert.doesNotMatch(html, /No actual data supplied|95%|clinical benefit/);
});

test("a recorded scope qualifier remains once beside its finding or in legacy interpretation when the finding is absent", () => {
  const scope = "The bound applies only to the specified observation law and independent assessment sample.";
  for (const conclusion of ["The observed advantage is conditional.", undefined]) {
    const value = { ...record, scientific_outcome: { conclusion, scope } };
    const html = render.render({ branch: ref.branch, summaries: [value] });
    assert.equal((html.match(/The bound applies only to the specified observation law and independent assessment sample\./g) || []).length, 1);
    const primary = html.slice(0, html.indexOf("Implementation and Code"));
    if (conclusion) {
      assert.match(primary, /Current finding and scope/);
      assert.ok(primary.includes(scope));
    } else {
      assert.ok(html.slice(html.indexOf('class="research-details empirical-full-interpretation"')).includes(scope));
      assert.doesNotMatch(primary, /Current finding/);
    }
  }
});

test("historical questions with no exhibits are normalized before the result row is rendered", () => {
  const legacy = { branch: ref.branch, generation_ref: ref, scientific_outcome: { conclusion: "The older finding remains limited to its tested setting." }, decision_summary: { implementation_markdown: "The earlier procedure was evaluated.", method_formulation_markdown: "The original target remains unchanged." } };
  const question = { branch: ref.branch, phase: "P4", question_id: "question.old", title: "What did the older experiment establish?", category: "performance", generation_ref: { ...ref, family: "protocol" }, result: { answer_markdown: "The older account does not identify its numerical rows." } };
  const before = structuredClone({ legacy, question });
  const html = render.render({ branch: ref.branch, summaries: [legacy], questions: [question], initialTab: "comparisons" });
  assert.match(html, /What did the older experiment establish/);
  assert.match(html, /The older account does not identify its numerical rows/);
  assert.doesNotMatch(html, />Notation<\/button>|Current finding and scope/);
  assert.deepEqual({ legacy, question }, before);
});

test("a projected CSV table has one numerical home while a CSV that could not be projected retains the scoped fallback", () => {
  const protocolRef = { ...ref, family: "protocol" };
  const question = { branch: ref.branch, phase: "P4", question_id: "question.csv", test_ids: ["test.csv"], case_ids: ["case.csv"], metric_ids: ["metric.error"], title: "What does the CSV comparison show?", generation_ref: protocolRef, result: { category: "performance", answer_markdown: "The saved comparison is conditional.", exhibit_ids: ["table.csv"] } };
  const exhibit = { branch: ref.branch, phase: "P4", exhibit_id: "table.csv", kind: "table", media_type: "text/csv", artifact_url: "/api/v1/exact.csv", source_verified: true, title: "CSV comparison", generation_ref: { ...ref, family: "exhibits" }, table: { columns: [{ key: "method", label: "Method" }, { key: "error", label: "Reported error" }], rows: [{ method: "Proposed", error: 0.31 }], total_rows: 1 } };
  const diagnostics = [{ branch: ref.branch, phase: "P4", generation_ref: { ...ref, family: "diagnostics" }, headline_numbers: [{ case_id: "case.csv", metric: "metric.error", estimate: 0.31, mcse: 0.02, n_replicates: 24 }] }];
  const props = { branch: ref.branch, questions: [question], exhibits: [exhibit], diagnostics, initialTab: "comparisons" };
  const before = structuredClone(props);
  const html = render.render(props);
  assert.equal((html.match(/<h4>CSV comparison<\/h4>/g) || []).length, 1);
  assert.match(html, /Open original table/);
  assert.doesNotMatch(html, /empirical-recorded-values|Recorded results for this question/);
  assert.deepEqual(props, before);
  const failedProjection = render.render({ ...props, exhibits: [{ ...exhibit, table: undefined, source_error: "The verified CSV table could not be rendered inline." }] });
  assert.match(failedProjection, /The verified CSV table could not be rendered inline/);
  assert.match(failedProjection, /empirical-recorded-values/);
  assert.match(failedProjection, /Recorded results for this question/);
});

test("notation uses semantic math tables and exact declared sources without deriving absent definitions", () => {
  const uri = `run://${ref.run_id}/protocol.json`;
  const protocolRef = { ...ref, family: "protocol", generation_id: "protocol.current", sha256: "b".repeat(64) };
  const value = { ...record, decision_summary: { ...record.decision_summary, notation_markdown: `${record.decision_summary.notation_markdown}\n\n[Definition source](${uri}#/estimand) and [unbound](run://${ref.run_id}/missing.json).` } };
  const before = structuredClone(value);
  const props = { record: value, onSource: noop, onClose: noop };
  const html = render.notation(props, { branch: ref.branch, onSource: noop, artifacts: [{ uri, sha256: protocolRef.sha256 }], records: [{ generation_ref: protocolRef }] });
  assert.match(html, /role="dialog" aria-modal="true" aria-labelledby="[^"]+"/);
  assert.match(html, /<h2 id="[^"]+">Notation<\/h2>/);
  assert.match(html, /aria-label="Close dialog"/);
  assert.match(html, /role="region" aria-label="Research table, scroll to inspect all columns"/);
  assert.match(html, /<th scope="col">Symbol<\/th>/);
  assert.match(html, /class="katex/);
  assert.match(html, /units have not been supplied/);
  assert.match(html, /Definition source<\/button>/);
  assert.match(html, /unbound \(source unavailable\)/);
  assert.doesNotMatch(html, /run:\/\/|katex-error|milliseconds|95%|MCSE|Mean error|Whole-procedure time|Notation and measures/);
  const source = elements(render.notationElement(props)).find((node) => node.props.label === "Notation source");
  assert.deepEqual(source.props.reference, { ...ref, entry_pointer: "/decision_summary/notation_markdown" });
  assert.deepEqual(value, before);
  for (const notation_markdown of [undefined, "", "  "]) {
    const emptyRecord = { ...record, decision_summary: { ...record.decision_summary, notation_markdown } };
    assert.equal(render.notationElement({ record: emptyRecord }), null);
    assert.doesNotMatch(render.render({ branch: ref.branch, summaries: [emptyRecord] }), />Notation<\/button>/);
  }
});

test("renaming the notation window preserves historical authored rows and their exact source", () => {
  const notation_markdown = "| Term | Definition |\n| --- | --- |\n| MCSE | Monte Carlo standard error as originally recorded |\n| Whole-procedure time | Historical timing boundary |";
  const legacy = { ...record, decision_summary: { ...record.decision_summary, notation_markdown } };
  const before = structuredClone(legacy);
  const props = { record: legacy, onSource: noop, onClose: noop };
  const html = render.notation(props, { branch: ref.branch, onSource: noop });
  assert.match(html, /<h2 id="[^"]+">Notation<\/h2>/);
  assert.match(html, /<td>MCSE<\/td>/);
  assert.match(html, /Monte Carlo standard error as originally recorded/);
  assert.match(html, /<td>Whole-procedure time<\/td>/);
  assert.match(html, /Historical timing boundary/);
  const source = elements(render.notationElement(props)).find((node) => node.props.label === "Notation source");
  assert.deepEqual(source.props.reference, { ...ref, entry_pointer: "/decision_summary/notation_markdown" });
  assert.deepEqual(legacy, before);
});

test("summary and experimental topics open the same lookup while the Lead account precedes closed detailed sources", () => {
  const question = { question_id: "question.mean", branch: ref.branch, phase: "P4", title: "Reported error comparison", generation_ref: { ...ref, family: "protocol" }, result: { category: "performance", answer_markdown: "Analyst details retain the measured comparison.", conditions_markdown: "The independent dataset is the experimental unit.", generation_ref: { ...ref, family: "analyst_synthesis" } }, review: { theorist_findings_markdown: "Theorist qualification: simulation is not a proof.", generation_ref: ref } };
  const input = { branch: ref.branch, summaries: [record], questions: [question], initialTab: "comparisons" };
  const before = structuredClone(input);
  const html = render.render(input);
  assert.equal((html.match(/aria-haspopup="dialog"/g) || []).length, 2);
  assert.equal((html.match(/>Notation<\/button>/g) || []).length, 2);
  assert.doesNotMatch(html, /role="dialog"|Notation and measures/);
  const lead = html.indexOf('class="empirical-topic-account"');
  const detailed = html.indexOf('<details class="question-detail empirical-question-row"');
  assert.ok(lead > 0 && lead < detailed);
  assert.match(html.slice(lead, detailed), /Research Lead · Partial/);
  assert.match(html.slice(detailed), /Analyst account and scientific review/);
  assert.match(html.slice(detailed), /Theorist qualification: simulation is not a proof/);
  assert.match(html.slice(detailed), /<details class="research-details empirical-review-details"><summary>/);
  assert.deepEqual(input, before);
});

test("a shared exhibit has one primary topic home and retains publication-specific IDs and links", () => {
  const current = { exhibit_id: "table.shared", branch: ref.branch, phase: "P4", title: "Shared observed comparison", source_error: "The original table is not available inline.", generation_ref: { ...ref, family: "exhibits" } };
  const older = { ...current, title: "Earlier observed comparison", generation_ref: { ...current.generation_ref, run_id: "run.older", package_id: "package.older", generation_id: "exhibits.older", sha256: "c".repeat(64) } };
  const questions = [
    { id: "question.performance", question_id: "question.performance", title: "Performance", category: "performance", result: { exhibit_ids: [current.exhibit_id] }, generation_ref: ref },
    { id: "question.robustness", question_id: "question.robustness", title: "Robustness", category: "sensitivity", result: { exhibit_ids: [current.exhibit_id] }, generation_ref: ref },
    { id: "question.older", question_id: "question.older", title: "Older tuning", category: "tuning", result: { exhibit_ids: [older.exhibit_id] }, generation_ref: older.generation_ref },
  ];
  const coverage = [{ dimension: "performance", status: "partial", summary: "Observed comparisons remain conditional.", exhibit_ids: [current.exhibit_id] }, { dimension: "robustness", status: "partial", summary: "The same comparison supports this qualification.", exhibit_ids: [current.exhibit_id] }];
  const summary = { ...record, decision_summary: { ...record.decision_summary, coverage } };
  const before = structuredClone({ current, older, questions, summary });
  const routing = routeEmpiricalExhibits([current, current, older], questions, coverage, summary);
  assert.equal(routing.length, 2);
  assert.equal(routing.find((entry) => entry.key === exhibitKey(current)).topic, "comparisons");
  assert.equal(routing.find((entry) => entry.key === exhibitKey(older)).topic, "tuning");
  const input = { branch: ref.branch, summaries: [summary], exhibits: [current, older], questions };
  const performance = render.render({ ...input, initialTab: "comparisons" });
  const robustness = render.render({ ...input, initialTab: "sensitivity" });
  assert.equal((performance.match(/<h4>Shared observed comparison<\/h4>/g) || []).length, 1);
  assert.doesNotMatch(performance.slice(0, performance.indexOf("Implementation and Code")), /<figure/);
  assert.doesNotMatch(robustness, /<h4>Shared observed comparison<\/h4>/);
  assert.match(robustness, /View Shared observed comparison in Performance/);
  assert.doesNotMatch(robustness, /View Earlier observed comparison/);
  const anchor = performance.match(/<figure id="([^"]+)"/)[1];
  const sameAfterNotationUpdate = render.render({ ...input, summaries: [{ ...summary, decision_summary: { ...summary.decision_summary, notation_markdown: "Updated definitions remain source-owned." } }], initialTab: "comparisons" });
  assert.ok(sameAfterNotationUpdate.includes(`<figure id="${anchor}"`));
  assert.deepEqual({ current, older, questions, summary }, before);
});
