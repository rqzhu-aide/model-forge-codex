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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-layout-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Workbench,{ProtocolSetup} from '${src}/components/EmpiricalWorkbench.jsx'; import Question,{EmpiricalDecisionSummary,EmpiricalQuestionSetup} from '${src}/components/EmpiricalQuestion.jsx'; import {SourceRef} from '${src}/components/Shared.jsx'; import {EmpiricalPlan} from '${src}/components/EmpiricalProgress.jsx'; import LaunchRun from '${src}/components/LaunchRun.jsx'; const draw = C => props => renderToStaticMarkup(React.createElement(C,props)); export const workbench = draw(Workbench); export const question = draw(Question); export const summary = draw(EmpiricalDecisionSummary); export const setup = draw(EmpiricalQuestionSetup); export const protocol = draw(ProtocolSetup); export const protocolTree = props => ProtocolSetup(props); export const sourceRef = SourceRef; export const plan = draw(EmpiricalPlan); export const launch = draw(LaunchRun);`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.a", phase: "P4", family: "protocol", generation_id: "protocol.a", sha256: "a".repeat(64), run_id: "run.a", package_id: "package.a" };

test("Setup retains authored comparison scope and departure consequences with exact source actions", () => {
  const protocol = { title: "Boundary check", generation_ref: ref,
    comparison_applicability: { required: false, reason: "This checks $s_j=0$, without a comparative performance claim." },
    claim_tests: [{ test_id: "test.boundary", hypothesis: "Does the saved zero mapping hold?" }],
    deviations: [
      { deviation_id: "departure.one", description: "An initial reference omitted the zero mapping.", reason: "The invariant check found it.", impact_assessment: "The affected measurements are excluded, not evidence of model failure.", disposition: "exclude_affected_result", affected_test_ids: ["test.boundary"] },
      { deviation_id: "departure.two", description: "The later repetitions were deferred.", reason: "The authorized time was exhausted.", impact_assessment: "No scaling conclusion is possible.", disposition: "retain_with_caveat", affected_test_ids: ["test.scaling"] },
    ] };
  const before = structuredClone(protocol); const opened = [];
  const html = render.protocol({ protocol, onSource: source => opened.push(source) });
  for (const text of ["Comparison is not required", "without a comparative performance claim", "Protocol departures (2)", "The affected measurements are excluded", "Exclude affected result", "No scaling conclusion is possible", "Does the saved zero mapping hold?", "Comparison scope source", "Departure source"]) assert.ok(html.includes(text), text);
  assert.match(html, /class="katex"/);
  assert.match(html, /<details class="research-details empirical-protocol-deviations"><summary>Protocol departures \(2\)<\/summary>/, "Departures remain a native collapsed disclosure.");
  const walk = node => Array.isArray(node) ? node.flatMap(walk) : !node || typeof node !== "object" ? [] : [node, ...walk(node.props?.children)];
  const sources = walk(render.protocolTree({ protocol, onSource: source => opened.push(source) })).filter(node => node.type === render.sourceRef);
  for (const node of sources) render.sourceRef(node.props).props.onClick();
  assert.deepEqual(opened, [{ ...ref, entry_pointer: "/comparison_applicability" }, { ...ref, entry_pointer: "/deviations/0" }, { ...ref, entry_pointer: "/deviations/1" }, ref]);
  assert.deepEqual(protocol, before, "Source targeting and labels do not change retained scientific bytes.");
  const unavailable = render.protocol({ protocol });
  assert.match(unavailable, /<button[^>]*disabled=""[^>]*>[\s\S]*Comparison scope source/);
});

test("required comparison stays explicit while a legacy protocol acquires no invented applicability or departures", () => {
  const current = render.protocol({ protocol: { generation_ref: ref, comparison_applicability: { required: true, reason: "The accuracy claim requires a fair linear benchmark." }, baselines: [{ name: "Nested linear benchmark" }], deviations: [] } });
  assert.match(current, /Comparison is required/); assert.match(current, /fair linear benchmark/); assert.match(current, /Nested linear benchmark/);
  assert.doesNotMatch(current, /Comparison is not required|Protocol departures/);
  const old = render.protocol({ protocol: { title: "Older retained protocol", baselines: [] } });
  assert.match(old, /Older retained protocol/);
  assert.doesNotMatch(old, /Comparison scope|Comparison is (?:not )?required|Protocol departures|scope source/);
});

test("a missing answer stays unassessed in Finding while planned mathematics remains in Setup", () => {
  for (const field of ["caption", "design"]) {
    const question = { question_id: "q.pending", title: "Zero mapping", status: "completed", generation_ref: ref, [field]: "Plan: check $s_j=0$ before interpretation." };
    const finding = render.question({ question }); const setup = render.setup({ question });
    assert.match(finding, /Not assessed/); assert.match(finding, /It remains unassessed/); assert.match(finding, /Execution:/);
    assert.doesNotMatch(finding, /Plan: check|class="katex"/);
    assert.match(setup, /Plan: check/); assert.match(setup, /class="katex"/);
  }
  const legacy = render.question({ question: { conclusion: "The retained answer is inconclusive.", status: "inconclusive", design: "A planned design." } });
  assert.match(legacy, /The retained answer is inconclusive/); assert.doesNotMatch(legacy, /remains unassessed|A planned design/);
  const missingAccount = render.question({ question: { result: { outcome: "supported" }, design: "A planned design." } });
  assert.match(missingAccount, /No separate authored finding/); assert.doesNotMatch(missingAccount, /remains unassessed|A planned design/);
});

test("recorded MCSE is neutral about observed or simulated data and never implies uncertainty in a method difference", () => {
  for (const source_type of ["observed_data", "simulation", undefined]) {
    const html = render.question({ question: { result: { outcome: "inconclusive", answer_markdown: "The recorded answer remains inconclusive." } }, protocol: { data_or_simulation_unit: { source_type } }, diagnostics: [{ generation_ref: ref, headline_numbers: [{ case_id: "case.one", metric: "metric.error", estimate: 0, mcse: 0.02, n_replicates: 12 }] }] });
    assert.match(html, /Monte Carlo standard error \(MCSE\)/); assert.match(html, /not uncertainty in the difference between methods/);
    assert.match(html, /MCSE 0.02/); assert.match(html, /Usable repetitions/); assert.match(html, /12/);
    assert.doesNotMatch(html, /MCSE describes simulation uncertainty|real-patient|clinical benefit/);
  }
});

test("a noncomparative numerical account has a neutral overview without adding cards or claiming comparative performance", () => {
  const html = render.workbench({ branch: "method.a", protocols: [{ branch: "method.a", comparison_applicability: { required: false, reason: "The prescribed update was checked without a performance comparison." }, generation_ref: ref }], summaries: [{ branch: "method.a", generation_ref: { ...ref, family: "empirical_synthesis" }, decision_summary: { implementation_markdown: "Ran only the derivative check.", method_fidelity_markdown: "The derivative matched the frozen objective.", theory_relation: { status: "tested", explanation_markdown: "A numerical check examined the derivative, not a proof." }, conclusion_markdown: "No predictive performance comparison was performed.", limitations_markdown: "Independent accuracy remains unassessed." } }] });
  assert.match(html, /Numerical findings and limitations/); assert.match(html, /No predictive performance comparison was performed/); assert.match(html, /Independent accuracy remains unassessed/); assert.match(html, /Comparison is not required/);
  assert.doesNotMatch(html, /Overall comparative performance/);
  assert.equal((html.match(/class="card /g) || []).length, 3);
  assert.equal((html.match(/role="tablist"/g) || []).length, 1);
});

test("the current run plan stays distinct from published plan sources", () => {
  const published = { protocol_id: "published", branch: "method.a", title: "Published study", generation_ref: ref, work_items: [{ work_item_id: "old", title: "Published comparison" }] };
  const active = { plan: { work_items: [{ work_item_id: "new", title: "Current comparison" }] } };
  const html = render.workbench({ branch: "method.a", protocols: [published], progressData: active, progressState: "awaiting_user", onSource() {} });
  assert.equal((html.match(/class="empirical-current-plan"/g) || []).length, 1);
  const current = html.slice(html.indexOf('class="empirical-current-plan"'), html.indexOf('class="research-details empirical-recorded-plans"'));
  assert.match(current, /Current comparison/);
  assert.doesNotMatch(current, /Published comparison/);
  assert.match(html, /<details class="research-details empirical-recorded-plans"><summary>[^<]+<\/summary>/);
  assert.match(html, /Published comparison/);
  assert.match(html, /Published findings above retain their original evidence/);
  const historical = render.workbench({ branch: "method.a", protocols: [published] });
  assert.equal((historical.match(/class="empirical-current-plan"/g) || []).length, 1);
  assert.match(historical, /Published comparison/);
  assert.doesNotMatch(historical, /empirical-recorded-plans/);
});

test("legacy summary retains its missing formulation and implementation while preserving original interpretation", () => {
  const html = render.workbench({ branch: "method.a", summaries: [{ decision_summary: { conclusion_markdown: "The estimator was faster in one setting." } }] });
  assert.match(html, /data-overview-complete="false"/);
  assert.match(html, /No mathematical formulation is available/);
  assert.match(html, /no separate authored account/);
  assert.match(html, /does not state whether Phase 3 theory was available or tested/);
  assert.match(html, /<details class="research-details empirical-full-interpretation"/);
});

test("experiment settings preserve exact authored values inside a keyboard accessible disclosure", () => {
  const html = render.setup({ question: { title: "Boundary behavior", case_ids: ["zero", "missing"], scope: "Only the boundary is studied.", falsification_rule: "A nonzero error rejects this check." }, cases: [{ case_id: "zero", label: "Zero repetitions", conditions: "Scale = 0.00000019; pairing is false.", replicates: [], baseline_label: "Fixed baseline" }, { case_id: "missing", label: "Unknown repetitions", conditions: "The setting was not recorded." }] });
  assert.match(html, /<details class="research-details empirical-question-cases"><summary>/);
  assert.match(html, /class="table-scroll" tabindex="0" role="region"/);
  assert.match(html, /Scale = 0.00000019; pairing is false/);
  assert.match(html, /<td>0<\/td>/);
  assert.match(html, /<td>Not recorded<\/td>/);
  assert.ok(html.indexOf("Only the boundary is studied") < html.indexOf("<details"));
  assert.ok(html.indexOf("A nonzero error rejects this check") < html.indexOf("<details"));
});

test("plan shortening keeps inferential consequences and reasons for skipped work visible", () => {
  const html = render.plan({ compact: true, progress: { plan: { work_items: [{ work_item_id: "cost", title: "Study scaling", reason: "Measure the practical cost.", reason_not_run: "Insufficient precision remains a limitation." }], amendments: [{ revision_id: "change", reason_markdown: "The first fit exceeded the budget.", changes_markdown: "Defer the scaling cases.", inferential_consequences_markdown: "No conclusion about scaling is possible." }] } } });
  assert.match(html, /<details class="research-details empirical-plan-reasoning"><summary>/);
  assert.match(html, /<details class="research-details empirical-plan-changes"><summary>/);
  assert.match(html, /<\/details>[^]*Insufficient precision remains a limitation/);
  assert.match(html, /<\/details><div class="research-document"><p>No conclusion about scaling is possible/);
});

test("review qualifications retain full text under details and execution cannot become a scientific outcome", () => {
  const review = { review_markdown: "A severe bias remains possible.", theorist_findings_markdown: "The simulation cannot prove consistency." };
  const html = render.question({ question: { status: "completed", result: { answer_markdown: "The code ran." }, review } });
  assert.match(html, /Not assessed/);
  assert.match(html, /Execution:/);
  assert.match(html, /Completed/);
  assert.match(html, /<details class="research-details empirical-review-details"><summary>/);
  assert.match(html, /A severe bias remains possible/);
  assert.doesNotMatch(html, />Supported</);
  const scientific = render.question({ question: { status: "supported" } });
  assert.match(scientific, /Supported/);
  assert.doesNotMatch(scientific, /Execution:/);
  const contradiction = render.question({ question: { status: "published", result: { outcome: "contradicted" } } });
  assert.match(contradiction, /Contradicted/);
  assert.match(contradiction, /Execution:/);
  assert.match(contradiction, /Published/);
});

test("embedded launch controls rely on the containing card for their method context", () => {
  const request = { branch: "method.a", phase: "P4", methodLabel: "Boundary estimator" };
  const embedded = render.launch({ projectId: "p", request, embedded: true });
  assert.doesNotMatch(embedded, /Boundary estimator/);
  const targeted = render.launch({ projectId: "p", request: { ...request, target: { ...ref, object_id: "q.one", kind: "empirical_question" }, targetLabel: "Boundary question" }, embedded: true });
  assert.match(targeted, /Boundary estimator/);
  assert.match(targeted, /Boundary question/);
});
