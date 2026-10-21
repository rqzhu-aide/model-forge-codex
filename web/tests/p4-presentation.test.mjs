import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { restoreOpenDisclosures } from "../src/readingPosition.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-presentation-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Workbench from '${src}/components/EmpiricalWorkbench.jsx'; import Question,{EmpiricalDecisionSummary,EmpiricalFullInterpretation} from '${src}/components/EmpiricalQuestion.jsx'; import {SourceRef} from '${src}/components/Shared.jsx'; import {ActionButton} from '${src}/components/Visuals.jsx'; const draw=C=>props=>renderToStaticMarkup(React.createElement(C,props)); export const workbench=draw(Workbench); export const summary=draw(EmpiricalDecisionSummary); export const question=draw(Question); export const summaryTree=props=>EmpiricalDecisionSummary(props); export const interpretationTree=props=>EmpiricalFullInterpretation(props); export const interpretation=draw(EmpiricalFullInterpretation); export const sourceRef=SourceRef; export const actionButton=ActionButton;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const walk = node => Array.isArray(node) ? node.flatMap(walk) : !node || typeof node !== "object" ? [] : [node, ...walk(node.props?.children)];
const ref = { branch: "method.a", phase: "P4", family: "empirical_synthesis", generation_id: "evaluation.one", sha256: "a".repeat(64), run_id: "run.one", package_id: "package.one" };
const decision = { conclusion_markdown: "Main conditional finding.", tradeoff_markdown: "Additional outputs are not improved calibration.", limitations_markdown: "Only synthetic accepted targets were assessed.", intent_markdown: "Conditional survival after a fixed landmark.", implementation_markdown: "Saved implementation details.", method_fidelity_markdown: "Finite checks are not a universal guarantee.", theory_relation: { status: "tested", explanation_markdown: "The formal status is unchanged." } };

// Determine visibility from native disclosure ancestry, including nested details.
function disclosuresAt(html, passage) {
  const offset = html.indexOf(passage); assert.notEqual(offset, -1, passage);
  const stack = [];
  for (const tag of html.slice(0, offset).match(/<\/?details\b[^>]*>/g) || []) {
    if (tag.startsWith("</")) stack.pop(); else stack.push(tag);
  }
  return stack;
}

test("summary leads with method and developed work while preserving the full interpretation and exact sources", () => {
  const record = { generation_ref: ref, decision_summary: decision }, before = structuredClone(record), opened = [];
  const props = { record, onSource: value => opened.push(value) };
  const html = ui.workbench({ branch: "method.a", summaries: [record], onSource: props.onSource });
  for (const field of ["conclusion_markdown", "tradeoff_markdown", "limitations_markdown"]) {
    assert.match(disclosuresAt(html, decision[field])[0], /empirical-full-interpretation/);
    assert.ok(html.indexOf(decision[field]) > html.indexOf(decision.implementation_markdown));
  }
  assert.match(disclosuresAt(html, decision.intent_markdown)[0], /empirical-full-interpretation/);
  assert.ok(html.indexOf(decision.limitations_markdown) < html.indexOf(decision.intent_markdown));
  assert.deepEqual(disclosuresAt(html, decision.implementation_markdown), []);
  assert.doesNotMatch(ui.summary(props), /Finite checks are not a universal guarantee/, "The implementation assessment belongs to the Code card.");
  assert.match(html, /<details class="research-details empirical-full-interpretation" data-reading-anchor="evaluation:evaluation.one:full-interpretation"><summary>/);
  for (const node of [...walk(ui.summaryTree(props)), ...walk(ui.interpretationTree(props))].filter(node => node.type === ui.sourceRef)) ui.sourceRef(node.props).props.onClick();
  assert.deepEqual(opened.map(value => value.entry_pointer), ["/decision_summary/implementation_markdown", "/decision_summary/conclusion_markdown", "/decision_summary/tradeoff_markdown", "/decision_summary/limitations_markdown", "/decision_summary/intent_markdown", "/decision_summary/theory_relation"]);
  assert.ok(opened.every(value => value.generation_id === ref.generation_id && value.sha256 === ref.sha256 && value.package_id === ref.package_id));
  assert.deepEqual(record, before);
  const missing = ui.workbench({ branch: "method.a", summaries: [{ decision_summary: { conclusion_markdown: decision.conclusion_markdown, intent_markdown: decision.intent_markdown } }] });
  assert.deepEqual(disclosuresAt(missing, "no separate authored account"), []);
  assert.match(disclosuresAt(missing, "does not state whether Phase 3")[0], /empirical-full-interpretation/);
});

test("coverage shortcuts deduplicate exact question IDs and use each available question's readable title", () => {
  const selected = [], questions = [{ id: "test.gate", title: "Does the gate preserve the fitted forecast?" }, { question_id: "test.cost", title: "What computation was actually measured?" }];
  const record = { generation_ref: ref, decision_summary: { ...decision, coverage: [{ dimension: "Fidelity", question_ids: ["test.gate", "test.gate"] }, { dimension: "Fidelity", question_ids: ["test.cost", "test.gate", "test.missing"] }] } };
  const props = { record, questions, onSelect: value => selected.push(value) }, before = structuredClone(record);
  const nodes = walk(ui.summaryTree(props)), actions = nodes.filter(node => node.type === ui.actionButton);
  assert.deepEqual(actions.map(node => node.props.children), questions.map(question => question.title));
  for (const node of actions) node.props.onClick();
  assert.deepEqual(selected, ["test.gate", "test.cost"]);
  const html = ui.summary(props);
  assert.match(html, /<details class="research-details empirical-question-links" data-reading-anchor="evaluation:evaluation.one:questions"><summary>Explore evaluation questions<\/summary>/);
  assert.match(html, /Some linked evaluation questions are unavailable/);
  assert.doesNotMatch(html, /View fidelity evidence|test\.missing<\/button>/);
  assert.deepEqual(record, before);
});

test("compact question rows expose coverage while answers and background retain native disclosures", () => {
  const question = { question_id: "test.fixture", branch: "method.a", title: "Did the boundary check pass?", category: "implementation", result: { category: "implementation", answer_markdown: "Finite boundary check passed.", limitations_markdown: "No universal floating-point result follows." }, review: { review_markdown: "Independent scope qualification." } };
  const protocol = { branch: "method.a", generation_ref: { ...ref, family: "protocol" }, title: "Saved study setup", scope: "One declared generator.", claim_tests: [{ test_id: question.question_id, hypothesis: question.title }], work_items: [{ work_item_id: "boundary", title: "Saved boundary work" }] };
  const implementation = { branch: "method.a", generation_ref: { ...ref, family: "implementation_record" }, body_md: "Exact saved implementation.", theorist_review: { body_md: "Independent implementation assessment." } };
  const props = { branch: "method.a", questions: [question], protocols: [protocol], implementations: [implementation], summaries: [{ branch: "method.a", generation_ref: ref, decision_summary: { ...decision, coverage: [{ dimension: "Fidelity", status: "assessed", summary: "Recorded finite coverage.", question_ids: [question.question_id] }] } }], loadErrors: [{ branch: "method.a", phase: "P4", message: "Retained table digest mismatch" }] };
  const html = ui.workbench(props);
  for (const [passage, className] of [["Exact saved implementation", "empirical-implementation-details"], ["Saved boundary work", "empirical-completed-plan"], ["One declared generator", "empirical-study-background"]]) {
    const ancestors = disclosuresAt(html, passage); assert.ok(ancestors.some(tag => new RegExp(className).test(tag)), passage); assert.ok(ancestors.every(tag => !/\bopen=/.test(tag)));
  }
  assert.deepEqual(disclosuresAt(html, "Retained table digest mismatch"), []);
  assert.deepEqual(disclosuresAt(html, "Recorded finite coverage"), []);
  for (const passage of ["Finite boundary check passed", "No universal floating-point result follows"]) assert.match(disclosuresAt(html, passage)[0], /empirical-question-row/);
  assert.match(disclosuresAt(html, "Independent scope qualification")[0], /empirical-question-row/);
  assert.doesNotMatch(disclosuresAt(html, "Independent scope qualification").at(-1), /\bopen=/);
  assert.match(html, /<details class="question-detail empirical-question-row"[^>]*data-question-id="test.fixture"[^>]*><summary>/);
  assert.deepEqual(disclosuresAt(html, "Fidelity: Assessed"), [], "Coverage is also visible beside the criterion navigation.");
  assert.equal((html.match(/role="tablist"/g) || []).length, 1);
  const progress = { plan: { work_items: [{ work_item_id: "current", title: "Current unfinished work" }] } };
  const active = ui.workbench({ ...props, progressData: progress, progressState: "awaiting_user" });
  assert.deepEqual(disclosuresAt(active, "Current unfinished work"), []);
  const completed = ui.workbench({ ...props, progressData: progress, progressState: "published" });
  assert.ok(disclosuresAt(completed, "Current unfinished work").some(tag => /empirical-completed-plan/.test(tag)));
  const missing = ui.workbench({ branch: "method.a" });
  assert.deepEqual(disclosuresAt(missing, "No separate implementation record"), []);
});

test("interrupted evaluations do not claim active work and retain earlier published summaries", () => {
  for (const progressState of ["failed", "cancelled"]) {
    const props = { branch: "method.a", progressData: { plan: { work_items: [] } }, progressState };
    const html = ui.workbench(props);
    assert.match(html, /evaluation stopped before publication/);
    assert.doesNotMatch(html, /evaluation is in progress/);
    const retained = ui.workbench({ ...props, summaries: [{ branch: "method.a", generation_ref: ref, decision_summary: decision }] });
    assert.match(retained, /Saved implementation details/);
    assert.doesNotMatch(retained, /evaluation stopped before publication/);
  }
});

test("background disclosures restore by exact evaluation anchors after navigation without sharing prior publication state", () => {
  const html = ui.interpretation({ record: { generation_ref: ref, decision_summary: decision } });
  const anchor = html.match(/data-reading-anchor="([^"]+:full-interpretation)"/)[1];
  const detail = value => ({ open: false, getAttribute: () => value, querySelector: () => ({ textContent: "Full interpretation and evaluation purpose" }) });
  const current = detail(anchor), earlier = detail(anchor.replace("evaluation.one", "evaluation.earlier"));
  restoreOpenDisclosures({ querySelectorAll: () => [earlier, current] }, [{ anchor, summary: "Full interpretation and evaluation purpose" }]);
  assert.equal(current.open, true); assert.equal(earlier.open, false);
});

test("verified linked exhibits cannot be mislabeled as missing numerical evidence while unavailable sources retain the warning", () => {
  const question = { question_id: "test.performance", result: { outcome: "inconclusive", answer_markdown: "The paired comparison is inconclusive.", uncertainty_markdown: "Nineteen usable pairs retain the paired MCSE." } };
  const exhibit = { exhibit_id: "table.paired", title: "Paired comparison", source_verified: true, artifact_url: "/api/v1/exact-table", table: { columns: [{ key: "difference", label: "Paired difference" }], rows: [{ difference: -0.0006028427364321294 }] } };
  const before = structuredClone(question);
  const html = ui.question({ question: { ...question, exhibits: [exhibit] } });
  assert.match(html, /No additional aggregate numerical summary/);
  assert.match(html, /Nineteen usable pairs retain the paired MCSE/);
  assert.match(html, /Inconclusive/);
  assert.doesNotMatch(html, /No completed numerical values|Its evidence gap remains open/);
  assert.deepEqual(question, before);
  for (const unavailable of [null, { ...exhibit, source_verified: false }, { ...exhibit, source_verified: undefined }, { ...exhibit, source_error: "Digest mismatch" }, { ...exhibit, artifact_url: undefined }]) {
    const missing = ui.question({ question: { ...question, exhibits: unavailable ? [unavailable] : [] } });
    assert.match(missing, /No completed numerical values are linked/);
    assert.doesNotMatch(missing, /No additional aggregate numerical summary/);
  }
});
