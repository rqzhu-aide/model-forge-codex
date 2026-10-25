import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { diagnosticsForQuestion, exhibitsForQuestion, hasEmpiricalFollowup, questionDiagnosticScope, theoryClaimSource } from "../src/empirical.js";

const protocolRef = { branch: "method.a", phase: "P4", family: "protocol", generation_id: "gen.protocol", sha256: "a".repeat(64), package_id: "package.evaluation", run_id: "run.evaluation" };
const testedRef = { ...protocolRef, phase: "P3", family: "theory_record", generation_id: "gen.theory.old", sha256: "b".repeat(64), package_id: "package.theory.old", run_id: "run.theory.old" };
const question = { question_id: "test.error", test_id: "test.error", test_ids: ["test.error"], title: "Does error decrease?", case_ids: ["case.shared"], statement_ids: ["statement.error"], decision_threshold_ids: ["threshold.error"], generation_ref: protocolRef };
const cases = [{ case_id: "case.shared", label: "Shared sample", test_ids: ["test.error", "test.coverage"], metric_ids: ["metric.error", "metric.coverage"], generation_ref: protocolRef }, { case_id: "case.unrelated", label: "Unrelated sample", test_ids: ["test.other"], metric_ids: ["metric.error"], generation_ref: protocolRef }];
const protocols = [{ generation_ref: protocolRef, claim_tests: [{ test_id: "test.error", decision_threshold_ids: ["threshold.error"] }, { test_id: "test.coverage", decision_threshold_ids: ["threshold.coverage"] }], decision_thresholds: [{ threshold_id: "threshold.error", metric_id: "metric.error" }, { threshold_id: "threshold.coverage", metric_id: "metric.coverage" }] }];
const diagnostic = { branch: "method.a", phase: "P4", diagnostics_id: "diag.a", generation_ref: { ...protocolRef, family: "diagnostics", generation_id: "gen.diagnostics", sha256: "c".repeat(64) }, provenance: { protocol_sha256: protocolRef.sha256 },
  headline_numbers: [{ case_id: "case.shared", metric: "metric.error", estimate: 1234, mcse: 0.1 }, { case_id: "case.shared", metric: "metric.coverage", estimate: 9876, mcse: 0.1 }, { case_id: "case.unrelated", metric: "metric.error", estimate: 5432, mcse: 0.1 }],
  stability: [{ case_id: "case.shared", metric: "metric.error", mean: 1234, sd: 0.1, n_seeds: 10, seed_flip: false }, { case_id: "case.shared", metric: "metric.coverage", mean: 9876, sd: 0.1, n_seeds: 10, seed_flip: true }],
  solver_health: [{ regime: "all", n_runs: 900, n_failures: 99 }], runtime: { total_ms: 999999, per_case: [{ case_id: "case.shared", mean_ms: 10, max_ms: 20 }, { case_id: "case.unrelated", mean_ms: 100, max_ms: 200 }] },
};

test("a shared case contributes only the selected test's threshold-linked metric", () => {
  const result = diagnosticsForQuestion(question, [diagnostic], cases, protocols);
  assert.deepEqual(result.pairs, [["case.shared", "metric.error"]]);
  assert.equal(result.diagnostics[0].headline_numbers.length, 1);
  assert.equal(result.diagnostics[0].headline_numbers[0].estimate, 1234);
  assert.equal(result.diagnostics[0].stability.length, 1);
  assert.deepEqual(result.diagnostics[0].solver_health, []);
  assert.equal(result.diagnostics[0].runtime.total_ms, undefined);
  assert.deepEqual(result.diagnostics[0].runtime.per_case.map((row) => row.case_id), ["case.shared"]);
  assert.equal(diagnostic.runtime.total_ms, 999999);
  assert.equal(diagnostic.headline_numbers.length, 3);
});

test("unmapped older questions cannot inherit all evaluation numbers", () => {
  assert.equal(diagnosticsForQuestion({ title: "An old narrative" }, [diagnostic], cases, protocols).hasNumbers, false);
  assert.equal(questionDiagnosticScope({ ...question, decision_threshold_ids: [] }, cases, []).hasMapping, false);
  const exclusive = [{ ...cases[0], test_ids: ["test.error"] }];
  assert.equal(questionDiagnosticScope(question, exclusive, []).pairs.length, 2);
});

test("diagnostic rows must belong to the inspected evaluation's protocol", () => {
  const old = { ...diagnostic, generation_ref: { ...diagnostic.generation_ref, package_id: "package.other" } };
  const wrongHash = { ...diagnostic, provenance: { protocol_sha256: "f".repeat(64) } };
  assert.equal(diagnosticsForQuestion(question, [old, wrongHash], cases, protocols).hasNumbers, false);
});

test("shared cases do not attach a figure explicitly assigned to a different test", () => {
  const figures = [{ exhibit_id: "correct", test_ids: ["test.error"], case_ids: ["case.shared"] }, { exhibit_id: "wrong", test_ids: ["test.coverage"], case_ids: ["case.shared"] }, { exhibit_id: "shared", case_ids: ["case.shared"] }];
  assert.deepEqual(exhibitsForQuestion({ ...question, exhibit_ids: ["wrong"] }, figures).map((item) => item.exhibit_id), ["correct", "shared"]);
  assert.deepEqual(exhibitsForQuestion(question, [{ ...figures[0], generation_ref: { ...protocolRef, run_id: "run.other" } }]), []);
});

test("theory inspection retains the tested generation after a theory repair", () => {
  const context = { tested_ref: testedRef, current_ref: { ...testedRef, generation_id: "gen.theory.new" }, state: "affected", affected_statement_ids: ["statement.error"] };
  const request = theoryClaimSource({ ...question, theory_context: context }, "statement.error");
  assert.equal(request[1], testedRef);
  assert.equal(request[2], context);
  assert.equal(theoryClaimSource(question, "statement.error"), null);
  assert.equal(theoryClaimSource({ ...question, theory_context: context }, "statement.other"), null);
});

const target = { ...protocolRef, kind: "empirical_question", question_id: question.question_id, object_id: question.question_id, test_ids: question.test_ids, case_ids: question.case_ids, statement_ids: question.statement_ids };
test("follow-up requires canonical exact publication metadata and retains verified legacy sources", () => {
  assert.equal(hasEmpiricalFollowup({ ...question, followup_target: target }), true);
  assert.equal(hasEmpiricalFollowup(question), false);
  assert.equal(hasEmpiricalFollowup({ ...question, followup_target: { ...target, package_id: null } }), true);
  const missingPackage = { ...target }; delete missingPackage.package_id;
  assert.equal(hasEmpiricalFollowup({ ...question, followup_target: missingPackage }), false);
  assert.equal(hasEmpiricalFollowup({ ...question, followup_target: { ...target, object_id: "test.other" } }), false);
  assert.equal(hasEmpiricalFollowup({ ...question, question_id: "test.other", followup_target: target }), false);
});

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-empirical-render-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Empirical,{EmpiricalEvaluationHistory} from '${src}/components/EmpiricalWorkbench.jsx'; export const render = props => renderToStaticMarkup(React.createElement(React.Fragment,null,React.createElement(Empirical, props),React.createElement(EmpiricalEvaluationHistory,props)));`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const { render } = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};

test("complete diagnostics preserve rare failures and missing uncertainty context", () => {
  const source = { ...diagnostic, headline_numbers: [{ case_id: "case.shared", metric: "metric.error", estimate: 0, mcse: 0, n_replicates: 100000, ci_lo: 0, ci_hi: 0.00001 }], solver_health: [{ regime: "rare failures", n_runs: 100000, n_failures: 1, failure_rate: 0.00001 }] };
  const html = render({ branch: "method.a", diagnostics: [source], onSource: noop });
  assert.match(html, /0\.001%/); assert.doesNotMatch(html, />0\.0%<|95%/);
  assert.match(html, /100,000/); assert.match(html, /Usable repetitions/); assert.match(html, /Interval level/);
  assert.match(html, /aria-label="Diagnostic table, scroll to inspect all columns"/);
  assert.equal(source.solver_health[0].failure_rate, 0.00001);
});

test("recorded noncompletion is not presented as solver failure", () => {
  // Older records expose only the aggregate fields, not separate status counts.
  const source = { ...diagnostic, solver_health: [{ regime: "all", n_runs: 335, n_failures: 19, failure_rate: 19 / 335 }] };
  const before = JSON.stringify(source);
  const html = render({ branch: "method.a", diagnostics: [source], onSource: noop });
  assert.match(html, /19 incomplete or nonconverged \/ 335 recorded checks/);
  assert.match(html, /<h3>Completion and convergence<\/h3>/);
  assert.match(html, /<th>Recorded checks<\/th><th>Incomplete or nonconverged<\/th><th>Share<\/th>/);
  assert.match(html, /Includes unrun cases, failed attempts and reported nonconvergence; this is not a count of solver failures\./);
  assert.match(html, /Sum of recorded case times:/);
  assert.match(html, /<b>Sum of case times<\/b>/);
  assert.doesNotMatch(html, /19 failures|<h3>Solver health<\/h3>|<th>Failures<\/th>|class="danger"/);
  assert.doesNotMatch(html, /Recorded experiment time|<b>Total<\/b>/);
  assert.equal(JSON.stringify(source), before);
});

test("missing legacy completion totals remain unrecorded", () => {
  const html = render({ branch: "method.a", diagnostics: [{ ...diagnostic, solver_health: [] }], onSource: noop });
  assert.match(html, /Completion totals not recorded/);
  assert.doesNotMatch(html, /<h3>Completion and convergence<\/h3>|0 incomplete or nonconverged/);
});

test("question view retains interpretation while numerical results have their own experiment disclosure", () => {
  const html = render({ branch: "method.a", questions: [{ ...question, branch: "method.a", phase: "P4", followup_target: target, theory_context: { state: "affected", tested_ref: testedRef, affected_statement_ids: ["statement.error"], message: "A dependency changed after these experiments." } }], cases, protocols, diagnostics: [diagnostic], onSource: noop, onRequest: noop, onTheory: noop });
  const start = html.indexOf('<details class="question-detail empirical-question-row"');
  const selected = html.slice(start, html.indexOf('class="research-details empirical-complete-numbers"', start));
  assert.doesNotMatch(selected, /1,234/);
  assert.doesNotMatch(selected, /9,?876|5,?432|999999|Solver health|<b>total<\/b>/);
  assert.match(html, /<details class="research-details complete-evaluation" data-card-role="history"><summary>/);
  assert.match(html, /9,876|5,432/);
  assert.match(html, /Reassessment needed after a theory change/);
  assert.match(html, /Theory used for this evaluation/);
  assert.match(html, /Request another check/);
  assert.match(html, /Inspect tested claim: Error/);
  assert.match(html, /role="tab"[^>]*aria-selected="true"[^>]*><span>Synthetic example/);
  assert.doesNotMatch(html, /class="question-picker"/);
});

test("older question remains readable without inventing a follow-up target or current theory link", () => {
  const html = render({ branch: "method.a", questions: [{ question_id: "old", title: "An older research question", statement_ids: ["statement.error"], branch: "method.a", phase: "P4" }], diagnostics: [diagnostic], onRequest: noop, onTheory: noop });
  assert.match(html, /does not identify which numerical rows answer this question/);
  assert.doesNotMatch(html, /Request another check/);
  assert.match(html, /aria-label="Inspect tested claim: Error" disabled=""/);
  assert.match(html, /Complete numerical results and recorded diagnostics/);
});

test("preliminary exploration is displayed without suggesting completed theory", () => {
  const html = render({ branch: "method.a", questions: [{ ...question, statement_ids: [], theory_context: { state: "early_exploration", message: "This proof of concept began before theory was established." } }] });
  assert.match(html, /Early exploration/);
  assert.match(html, /before theory was established/);
  assert.doesNotMatch(html, /Uses the current theory|Claims in the theory/);
});
