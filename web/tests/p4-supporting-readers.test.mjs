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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-support-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server';
 export {default as Workbench,CompleteNumbers,ExperimentSetupDocument,diagnosticReadingLabel,EmpiricalQuestionDesignDocument} from '${src}/components/EmpiricalWorkbench.jsx';
 export {EmpiricalDecisionSummary as Summary,EmpiricalFormulation as Formulation,EmpiricalFullInterpretation as InterpretationButton,EmpiricalInterpretationDocument as Interpretation} from '${src}/components/EmpiricalQuestion.jsx';
 export {default as Implementation,ImplementationDetails,ImplementationFiles,ImplementationReview} from '${src}/components/ImplementationReading.jsx';
 export {default as EmpiricalReadingButton,empiricalReadingSize,empiricalReadingSnapshot} from '${src}/components/EmpiricalReading.jsx';
 export {empiricalSourceLabel,empiricalSource} from '${src}/components/EmpiricalDocument.jsx';
 export {SourceRef} from '${src}/components/Shared.jsx';
 export {default as ReadingHost} from '${src}/components/ReadingHost.jsx';
 export {rememberReadingPosition,restoreReadingPosition} from '${src}/readingWindowPosition.js';
 export const h=React.createElement; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props));
 export const renderElement=renderToStaticMarkup;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.a", phase: "P4", family: "empirical_synthesis", generation_id: "evaluation.saved", sha256: "a".repeat(64), run_id: "run.saved", package_id: "package.saved" };
const scope = { projectId: "project.one", phase: "P4", branch: "method.a" };
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children), ...nodes(tree.props.actions), ...nodes(tree.props.resources)] : [];
const button = (tree, kind) => nodes(tree).find(node => node.type === ui.EmpiricalReadingButton && node.props.kind === kind);
const snapshot = (control, sources = {}, onSource) => ui.empiricalReadingSnapshot({ ...control.props, scope, sources, onSource });

test("reader snapshots freeze the producing branch and exact records, files and manifests without cloning callbacks", () => {
  const uri = `run://${ref.run_id}/saved-answer.json`;
  const record = { generation_ref: ref, decision_summary: { method_formulation_markdown: `Saved account: ${uri}#/finding\n\n$$Q(\\beta)=0.$$` } };
  const sources = { branch: scope.branch, artifacts: [{ uri, sha256: ref.sha256 }], records: [undefined, { generation_ref: ref, title: "Exact saved answer" }], files: [{ uri, sha256: ref.sha256, branch: scope.branch, source_verified: true, generation_ref: ref }] };
  let current = [], later = [];
  const callback = (...args) => current.push(args);
  const value = ui.empiricalReadingSnapshot({ scope, kind: "formulation", title: "Full formulation", input: { record }, sources, onSource: callback, renderBody: input => ui.h(ui.Formulation, { ...input, onSource: callback }) });
  sources.branch = "method.b"; sources.artifacts[0].sha256 = "b".repeat(64); sources.records[1].title = "New answer"; sources.files[0].source_verified = false;
  record.decision_summary.method_formulation_markdown = "A replacement account.";
  const html = ui.renderElement(value.body);
  assert.match(html, /Exact saved answer/); assert.match(html, /katex-display/);
  assert.doesNotMatch(html, /New answer|replacement account|source unavailable/);
  assert.equal(value.body.props.value.branch, "method.a");
  assert.equal(value.body.props.value.records.length, 1);
  current = later;
  value.body.props.value.onSource(ref);
  assert.deepEqual(later, [[ref]], "The callback remains live application behavior, outside the data clone.");
  const changed = ui.empiricalReadingSnapshot({ scope, kind: "formulation", title: "Full formulation", input: { record }, sources, renderBody: input => ui.h(ui.Formulation, input) });
  assert.notEqual(changed.key, value.key);
});

test("a bare exact source tolerates absent optional records rather than crashing", () => {
  const uri = `run://${ref.run_id}/answer.json`;
  const sources = { branch: ref.branch, artifacts: [{ uri, sha256: ref.sha256 }], records: [undefined, null, { generation_ref: ref, title: "Retained numerical answer" }] };
  const target = ui.empiricalSource(uri, sources);
  assert.equal(ui.empiricalSourceLabel(uri, sources, target), "Retained numerical answer");
});

test("Implementation readers retain complete independent accounts, verified delivery and protocol fallback provenance", () => {
  const protocol = { generation_ref: { ...ref, family: "protocol" }, implementation_strategy: { route: "custom_implementation", route_rationale: "A shared package does not implement the frozen criterion." } };
  const record = { generation_ref: { ...ref, family: "implementation_record" }, producer_role: "data_analyst", body_md: "Unique implementation qualification.", sections: [{ key: "correspondence", body_md: "Finite correspondence only." }, { key: "limitations", body_md: "Small-denominator cases remain unassessed." }, { key: "verification", body_md: "The retained check could not run." }], reproduction: { invocation: "python example.py", model_entrypoint: { artifact: { path: "model.py", sha256: "b".repeat(64) } } }, files: [{ path: "model.py", sha256: "b".repeat(64), source_verified: true, artifact_url: "/api/model", download_url: "/api/model?download=true" }, { path: "bad.py", source_verified: false, source_error: "Digest mismatch", download_url: "/never" }], theorist_review: { generation_ref: { ...ref, family: "theory_audit" }, body_md: "An independent review leaves fidelity unassessed." } };
  const tree = ui.Implementation({ records: [record], protocols: [protocol], onSource() {} });
  const page = ui.render(ui.Implementation, { records: [record], protocols: [protocol] });
  for (const text of ["Finite correspondence only", "Small-denominator cases remain unassessed"]) assert.ok(page.includes(text));
  assert.doesNotMatch(page, /Unique implementation qualification|retained check could not run|independent review leaves/);
  const details = snapshot(button(tree, "p4-implementation-details"));
  const detailsBody = ui.renderElement(details.body);
  assert.match(detailsBody, /Unique implementation qualification|retained check could not run|python example.py|Inspect model entrypoint/);
  const strategySource = button(tree, "p4-implementation-details").props.input.strategySource;
  assert.deepEqual(strategySource, { ...protocol.generation_ref, entry_pointer: "/implementation_strategy" });
  const files = ui.renderElement(snapshot(button(tree, "p4-implementation-files")).body);
  assert.match(files, /Digest mismatch/); assert.doesNotMatch(files, /href="\/never"/);
  assert.match(files, /Saved file manifest source/);
  assert.match(ui.renderElement(snapshot(button(tree, "p4-implementation-review")).body), /independent review leaves fidelity unassessed/);
});

test("zero prose never hides a manifest or equation, while absent support stays an honest notice", () => {
  const manifest = ui.render(ui.Implementation, { records: [{ files: [{ path: "model.py", sha256: "c".repeat(64) }] }] });
  assert.match(manifest, /Saved files and checks|1 saved file/);
  assert.doesNotMatch(manifest, /No detailed text recorded/);
  const empty = ui.render(ui.Implementation, { records: [{ files: [], theorist_review: {} }] });
  assert.doesNotMatch(empty, /aria-haspopup="dialog"/);
  assert.match(empty, /No readable theorist assessment|No separate implementation/);
  assert.equal(ui.empiricalReadingSize("$$x=0.$$"), "1 displayed equation");
  const theoryOnly = ui.render(ui.InterpretationButton, { record: { decision_summary: { theory_relation: { status: "not_tested" } } } });
  assert.match(theoryOnly, /Full interpretation/); assert.doesNotMatch(theoryOnly, /No detailed text recorded/);
});

test("an unprojected theorist account retains its exact source without an empty reader", () => {
  const reviewRef = { ...ref, family: "theory_audit" };
  const record = { generation_ref: ref, theorist_review: { generation_ref: reviewRef } };
  const opened = [];
  const tree = ui.Implementation({ records: [record], onSource: source => opened.push(source) });
  assert.equal(button(tree, "p4-implementation-review"), undefined);
  const source = nodes(tree).find(node => node.type === ui.SourceRef && node.props.label === "Theorist assessment source");
  assert.deepEqual(source.props.reference, reviewRef);
  source.props.onOpen(source.props.reference);
  assert.deepEqual(opened, [reviewRef]);
  const html = ui.render(ui.Implementation, { records: [record], onSource() {} });
  assert.match(html, /No readable theorist assessment is retained/);
  assert.match(html, /Theorist assessment source/);
  assert.doesNotMatch(html, /aria-haspopup="dialog"/);
});

test("a newly published theory cannot redirect a frozen experiment-design reader to the current graph", () => {
  const tested = { ...ref, phase: "P3", family: "complete_theory", generation_id: "theory.T1", sha256: "1".repeat(64) };
  const current = { ...tested, generation_id: "theory.T2", sha256: "2".repeat(64) };
  const question = { title: "Tested finite claim", statement_ids: ["statement.one"], theory_context: { tested_ref: tested, state: "current" } };
  const opened = [];
  const value = ui.empiricalReadingSnapshot({ scope, kind: "p4-question-design", title: "Experiment design and sources", input: { question, cases: [] }, onSource: (...args) => opened.push(args), renderBody: (input, onSource) => ui.h(ui.EmpiricalQuestionDesignDocument, { ...input, onSource }) });
  question.theory_context.tested_ref = current; question.theory_context.state = "affected";
  const document = value.body.props.children;
  const setup = ui.EmpiricalQuestionDesignDocument(document.props);
  assert.deepEqual(setup.props.question.theory_context.tested_ref, tested);
  setup.props.onTheory("statement.one", setup.props.question.theory_context.tested_ref);
  assert.deepEqual(opened, [[tested, "statement.one"]], "The exact frozen claim opens as a source, independently of today's graph.");
});

test("full interpretation preserves every field and a legacy numerical table under Experiments ownership", () => {
  const record = { generation_ref: ref, decision_summary: { method_recap_markdown: "The saved method is fixed.", method_formulation_markdown: "Full mathematical definition.\n\n$$Q=0.$$", conclusion_markdown: "The full conclusion.\n\n| Quantity | Value |\n| --- | --- |\n| Error | 0.00000019 |", tradeoff_markdown: "A complete tradeoff.", limitations_markdown: "One failed fit remains in the denominator.", intent_markdown: "Assess the fixed method in the declared scope.", theory_relation: { status: "tested", explanation_markdown: "Only the named finite check was tested." } } };
  const before = structuredClone(record);
  const page = ui.render(ui.Workbench, { branch: ref.branch, summaries: [record] });
  assert.ok(page.indexOf("Full interpretation") > page.indexOf("Experiments and Results"));
  assert.doesNotMatch(page.slice(0, page.indexOf("Experiments and Results")), /Full interpretation|<table/);
  const body = ui.render(ui.Interpretation, { record });
  for (const text of ["full conclusion", "0.00000019", "complete tradeoff", "failed fit remains in the denominator", "Assess the fixed method", "named finite check", "Numerical evidence is not a proof"]) assert.ok(body.includes(text), text);
  const refs = nodes(ui.Interpretation({ record })).filter(node => node.type === ui.SourceRef).map(node => node.props.reference);
  assert.deepEqual(refs.map(item => item.entry_pointer), ["conclusion_markdown", "tradeoff_markdown", "limitations_markdown", "intent_markdown", "theory_relation"].map(field => `/decision_summary/${field}`));
  assert.deepEqual(record, before);
});

test("diagnostic counts describe diagnostic arrays and preserve zero, missing totals and expanded rows on reopen", () => {
  const diagnostics = [{ generation_ref: ref, headline_numbers: Array.from({ length: 7 }, (_, i) => ({ case_id: `case.${i}`, metric: "error", estimate: i === 0 ? 0 : i === 1 ? null : i, mcse: i === 0 ? 0 : null, n_replicates: i === 1 ? 0 : 11 })), stability: Array.from({ length: 6 }, (_, i) => ({ case_id: `seed.${i}`, metric: "error", mean: 0, sd: 0, n_seeds: 1, seed_flip: false })), solver_health: [{ regime: "Zero checks", n_runs: 0, n_failures: 0 }], runtime: { per_case: [{ case_id: "case.0", mean_ms: 0, max_ms: 0 }] } }];
  assert.equal(ui.diagnosticReadingLabel(diagnostics), "1 record · 4 tables · 16 rows");
  const html = ui.render(ui.CompleteNumbers, { diagnostics, cases: [] });
  assert.match(html, /Completion totals not recorded|Case times not recorded/);
  assert.match(html, /Show all 7 rows|Show all 6 rows/);
  assert.match(html, /MCSE 0/); assert.match(html, /Not recorded/);
  assert.match(html, /class="research-details diagnostic-row-expansion"/);
  const first = { open: true }, second = { open: true }, raw = { open: false };
  const body = { scrollTop: 485, querySelectorAll: () => [first, second, raw] };
  ui.rememberReadingPosition("p4.exact.diagnostics", body);
  const reopened = [{ open: false }, { open: false }, { open: false }];
  const target = { scrollTop: 0, querySelectorAll: () => reopened };
  assert.equal(ui.restoreReadingPosition("p4.exact.diagnostics", target), true);
  assert.equal(target.scrollTop, 485); assert.deepEqual(reopened.map(item => item.open), [true, true, false]);
  assert.equal(ui.restoreReadingPosition("p4.new.diagnostics", target), false);
});

test("complete diagnostics use matching protocol names without humanizing authored science or borrowing another run", () => {
  const exact = { ...ref, family: "protocol" };
  const old = { ...exact, run_id: "run.older", package_id: "package.older" };
  const name = "Risk $R_{\\alpha}$ for RL-LPM1";
  const diagnostics = [{ generation_ref: ref, headline_numbers: [
    { case_id: "case.one", metric: "metric.manual", estimate: null, uncertainty_kind: "not_assessed", mcse: 0.1, n_replicates: 0 },
    { case_id: "case.one", metric: "metric.unlabeled_key", estimate: 0, uncertainty_kind: "not_applicable", n_replicates: 1 },
    { case_id: "case.one", metric: "legacy", estimate: 1, uncertainty_kind: "not_assessed" },
  ], metric_labels: { legacy: "J_R-A", "metric.manual": "Earlier label" }, stability: [{ case_id: "case.one", metric: "metric.manual", mean: 0, sd: 0, n_seeds: 1, seed_flip: false }] }];
  const props = { diagnostics, cases: [{ generation_ref: exact, case_id: "case.one", label: "RL-LPM1" }, { generation_ref: old, case_id: "case.one", label: "Unrelated old case" }], protocols: [
    { generation_ref: old, metrics: [{ metric_id: "metric.manual", name: "Unrelated old metric" }] },
    { generation_ref: exact, metrics: [], amendments: [{ added_metrics: [{ metric_id: "metric.manual", name, unit: "$\\mathrm{mg}$" }] }] },
  ] };
  const before = structuredClone(props); const html = ui.render(ui.CompleteNumbers, props);
  const readable = html.slice(0, html.indexOf("Complete numerical source"));
  assert.equal((readable.match(/application\/x-tex">R_\{\\alpha\}/g) || []).length, 2);
  assert.match(readable, /application\/x-tex">\\mathrm\{mg\}/);
  assert.match(readable, /<td>J_R-A<\/td>/);
  assert.match(readable, /<td>metric.unlabeled_key<\/td>/);
  assert.match(readable, /<td class="rid">RL-LPM1<\/td>/);
  assert.match(readable, /<b>Not recorded<\/b><\/td><td class="note">Not assessed<\/td>/);
  assert.doesNotMatch(readable, /Unrelated old|Earlier label|MCSE 0.1|J R A|Metric unlabeled key/);
  assert.deepEqual(props, before);
});

test("current plans remain live and inline in unfinished terminal and waiting states; completed plans remain inspectable", () => {
  const progressData = { plan: { work_items: [{ work_item_id: "scaling", title: "Current scaling work", reason_not_run: "Scaling remains unassessed." }] } };
  const protocols = [{ generation_ref: { ...ref, family: "protocol" }, title: "Earlier retained plan", work_items: [{ work_item_id: "old", title: "Old completed work" }] }];
  for (const progressState of ["running", "awaiting_user", "assessed", "failed", "cancelled"]) {
    const html = ui.render(ui.Workbench, { branch: ref.branch, progressData, progressState, protocols });
    assert.match(html, /Current evaluation plan|Current scaling work|Scaling remains unassessed/);
    assert.doesNotMatch(html, /Old completed work/);
  }
  const completed = ui.render(ui.Workbench, { branch: ref.branch, progressData, progressState: "published", protocols });
  assert.doesNotMatch(completed, /Current scaling work/); assert.match(completed, /Completed evaluation plan/);
  const document = ui.render(ui.ExperimentSetupDocument, { protocols, progressData });
  assert.match(document, /Current scaling work|Old completed work/);
});

test("standalone SSR keeps reader controls, including when rendered under the shared host", () => {
  const props = { branch: ref.branch, diagnostics: [{ branch: ref.branch, phase: "P4", generation_ref: ref, headline_numbers: [{ estimate: 0 }] }] };
  assert.match(ui.render(ui.Workbench, props), /Numerical results and diagnostics/);
  assert.match(ui.renderElement(ui.h(ui.ReadingHost, { scope }, ui.h(ui.Workbench, props))), /Numerical results and diagnostics/);
});

test("Summary separates the complete scientific account from its existing exact-source controls", () => {
  const selected = [], notation = [];
  const record = { generation_ref: ref, scientific_outcome: { conclusion: "The paired result is inconclusive.", scope: "Only the retained synthetic settings were tested." }, decision_summary: { method_recap_markdown: "The fixed estimator uses the recorded objective.", method_formulation_markdown: "The complete objective is $$Q(\\beta)=0.$$.\n\nThe boundary qualification remains.", implementation_markdown: "The saved implementation was checked on the synthetic settings.", notation_markdown: "The coefficient is $\\beta$.", coverage: [{ dimension: "Performance", question_ids: ["q.saved"] }] }, actual_data_application: { status: "supplied_not_analyzed", summary_markdown: "The supplied cohort was not analyzed." } };
  const question = { id: "q.saved", title: "What did the paired comparison establish?" };
  const before = structuredClone(record);
  const tree = ui.Summary({ record, questions: [question], onSelect: value => selected.push(value), onNotation: () => notation.push("opened"), onSource() {} });
  const layout = nodes(tree).find(node => node.type?.name === "ResearchCardLayout");
  const account = ui.renderElement(layout.props.children), resources = ui.renderElement(layout.props.resources);
  for (const text of ["paired result is inconclusive", "retained synthetic settings", "fixed estimator", "saved implementation", "supplied cohort was not analyzed"]) assert.ok(account.includes(text), text);
  assert.doesNotMatch(account, /Full formulation|Explore evaluation questions|Summary sources|aria-haspopup/);
  for (const text of ["Full formulation", "Notation", "Summary sources", question.title]) assert.ok(resources.includes(text), text);
  assert.doesNotMatch(resources, /paired result is inconclusive|supplied cohort was not analyzed|boundary qualification/);
  const controls = nodes(layout.props.resources);
  controls.find(node => node.props.children === "Notation" && typeof node.props.onClick === "function").props.onClick();
  controls.find(node => node.props.children === question.title).props.onClick();
  assert.deepEqual(notation, ["opened"]); assert.deepEqual(selected, [question.id]);
  assert.equal(nodes(tree).filter(node => node.props["data-reading-anchor"] === `evaluation:${ref.generation_id}:method-definition`).length, 1);
  assert.deepEqual(record, before);
  for (const props of [{}, { awaitingDirection: true }, { progressState: "failed" }, { progressState: "cancelled" }, { hasProgress: true }]) assert.doesNotMatch(ui.render(ui.Summary, props), /research-card-resources|has-rail/);
});

test("Implementation keeps fidelity and limitations beside verified delivery and frozen supporting readers", () => {
  const record = { generation_ref: { ...ref, family: "implementation_record" }, producer_role: "data_analyst", bundle_url: "/api/saved-bundle", reproduction: { status: "available" }, sections: [{ key: "correspondence", body_md: "Only the retained finite check agrees." }, { key: "limitations", body_md: "The sparse boundary remains unassessed." }, { key: "verification", body_md: "The complete saved check account." }], files: [{ path: "model.py", source_verified: true, artifact_url: "/api/saved-model" }], theorist_review: { generation_ref: { ...ref, family: "theory_audit" }, body_md: "The independent assessment retains its qualification." } };
  const before = structuredClone(record), tree = ui.Implementation({ records: [record], onSource() {} });
  const layout = nodes(tree).find(node => node.type?.name === "ResearchCardLayout");
  const account = ui.renderElement(layout.props.children), actions = ui.renderElement(layout.props.actions), resources = ui.renderElement(layout.props.resources);
  for (const text of ["retained finite check", "sparse boundary remains unassessed"]) assert.ok(account.includes(text), text);
  assert.doesNotMatch(account, /Download code|Implementation details|Saved files and checks|Theorist assessment/);
  assert.match(actions, /Download code and example bundle/);
  assert.doesNotMatch(actions, /Implementation details|Saved files and checks|Theorist assessment/);
  for (const text of ["Implementation details", "Saved files and checks", "Theorist assessment"]) assert.ok(resources.includes(text), text);
  assert.doesNotMatch(resources, /Download code and example bundle/);
  assert.doesNotMatch(resources, /retained finite check|sparse boundary remains unassessed|complete saved check account|independent assessment retains/);
  assert.match(ui.renderElement(snapshot(button(tree, "p4-implementation-details")).body), /complete saved check account/);
  assert.match(ui.renderElement(snapshot(button(tree, "p4-implementation-review")).body), /independent assessment retains its qualification/);
  const filesOnly = ui.render(ui.Implementation, { records: [{ files: record.files }] });
  assert.match(filesOnly, /Saved files and checks/); assert.doesNotMatch(filesOnly, /Download code and example bundle/);
  const empty = ui.render(ui.Implementation, { records: [{}] });
  assert.doesNotMatch(empty, /research-card-actions|research-card-resources|has-rail/); assert.match(empty, /No verified code and example bundle/);
  const fidelity = "The checked implementation agrees only in the recorded scope.";
  const reviewed = ui.Implementation({ records: [record], summary: { generation_ref: ref, decision_summary: { method_fidelity_markdown: fidelity } } });
  const reviewedLayout = nodes(reviewed).find(node => node.type?.name === "ResearchCardLayout");
  assert.ok(ui.renderElement(reviewedLayout.props.children).includes(fidelity)); assert.ok(!ui.renderElement(reviewedLayout.props.resources).includes(fidelity));
  assert.doesNotMatch(ui.renderElement(reviewedLayout.props.children), /Assessment source/);
  assert.match(ui.renderElement(reviewedLayout.props.resources), /Assessment source/);
  const assessedSource = nodes(reviewedLayout.props.resources).find(node => node.type === ui.SourceRef && node.props.label === "Assessment source");
  assert.deepEqual(assessedSource.props.reference, { ...ref, entry_pointer: "/decision_summary/method_fidelity_markdown" });
  const noRecord = ui.render(ui.Implementation, { records: [], summary: { generation_ref: ref, decision_summary: { method_fidelity_markdown: fidelity } } });
  assert.match(noRecord, /Assessment source/); assert.doesNotMatch(noRecord, /research-card-resources|has-rail/);
  assert.deepEqual(record, before);
});

test("delivery-only implementation records keep their fallback notes once without an empty reading area", () => {
  for (const [record, delivery] of [
    [{ bundle_url: "/api/verified-bundle", reproduction: { status: "available" } }, "Download code and example bundle"],
    [{ reproduction: { status: "unavailable" } }, "Portable delivery is unavailable."],
    [{ bundle_error: "The retained digest does not match." }, "The source bundle is unavailable: The retained digest does not match."],
  ]) {
    const tree = ui.Implementation({ records: [record] });
    const layout = nodes(tree).find(node => node.type?.name === "ResearchCardLayout");
    assert.equal(layout.props.resources, null);
    assert.equal(layout.props.actionsLabel, "Implementation actions");
    assert.match(ui.renderElement(layout.props.actions), new RegExp(delivery.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
    const html = ui.render(ui.Implementation, { records: [record] });
    assert.match(html, /research-card-layout has-rail has-actions/);
    assert.doesNotMatch(html, /research-card-resources|<aside/);
    assert.ok(html.indexOf("research-card-actions") < html.indexOf("research-card-account"));
    for (const text of [delivery, "No separate implementation, verification or dependency details are recorded.", "No code, configuration, environment or check files are linked in this record.", "No theorist assessment is linked to this exact evaluation."]) assert.equal(html.split(text).length - 1, 1, text);
  }
});

test("Summary topic actions select the evaluation tab and stay absent without a handler", () => {
  const explored = [];
  const record = { generation_ref: ref, scientific_outcome: { conclusion: "The paired result is inconclusive." }, decision_summary: { method_recap_markdown: "The fixed estimator uses the recorded objective.", implementation_markdown: "The saved implementation was checked." } };
  const before = structuredClone(record);
  const tree = ui.Summary({ record, onExplore: value => explored.push(value), onSource() {} });
  const layout = nodes(tree).find(node => node.type?.name === "ResearchCardLayout");
  assert.equal(layout.props.actionsLabel, "Evaluation actions");
  assert.equal(layout.props.label, "Summary supporting reading");
  const actions = ui.renderElement(layout.props.actions);
  assert.match(actions, /<h3>Explore the evaluation<\/h3>/);
  for (const label of ["Experimental setup", "Main results", "Computational cost", "Tuning", "Sensitivity and robustness"]) assert.equal(actions.split(`>${label}<`).length - 1, 1, label);
  nodes(layout.props.actions).find(node => node.props.children === "Sensitivity and robustness").props.onClick();
  nodes(layout.props.actions).find(node => node.props.children === "Experimental setup").props.onClick();
  assert.deepEqual(explored, ["sensitivity", "setup"]);
  assert.doesNotMatch(ui.renderElement(layout.props.children), /Explore the evaluation|Robustness/);
  const html = ui.render(ui.Summary, { record, onExplore() {}, onSource() {} });
  assert.match(html, /<div class="card-heading"><h2>Summary<\/h2><\/div>/);
  assert.match(html, /research-card-layout has-rail has-actions/);
  assert.match(html, /<div class="research-card-actions" role="group" aria-label="Evaluation actions">/);
  assert.ok(html.indexOf("research-card-actions") < html.indexOf("research-card-account"));
  assert.equal(nodes(ui.Summary({ record, onSource() {} })).find(node => node.type?.name === "ResearchCardLayout").props.actions, null);
  assert.doesNotMatch(ui.render(ui.Summary, { onExplore() {} }), /Explore the evaluation|research-card-actions/);
  assert.deepEqual(record, before);
});

test("Experiments keeps one compact supporting reading row under the topic strip and drops the bottom toolbar", () => {
  const summary = { generation_ref: ref, scientific_outcome: { conclusion: "The paired result is inconclusive." }, decision_summary: { conclusion_markdown: "The complete interpretation.", notation_markdown: "The coefficient is $\\beta$." } };
  const diagnostics = [{ branch: ref.branch, phase: "P4", generation_ref: ref, headline_numbers: [{ estimate: 0 }] }];
  const protocols = [{ generation_ref: ref, branch: ref.branch, phase: "P4", questions: [{ id: "q.saved", title: "What did the paired comparison establish?" }] }];
  const html = ui.render(ui.Workbench, { branch: ref.branch, summaries: [summary], diagnostics, protocols });
  const experiments = html.slice(html.indexOf('<section class="card empirical-workspace"'));
  assert.match(experiments, /^<section class="card empirical-workspace" data-card-role="research"><div class="card-heading"><h2>Experiments and Results<\/h2><\/div>/);
  assert.equal(experiments.split('aria-label="Experiment supporting documents"').length - 1, 1);
  const strip = experiments.indexOf('class="empirical-section-nav"'), row = experiments.indexOf('class="reading-toolbar empirical-support-toolbar empirical-support-row"'), panel = experiments.indexOf('class="empirical-numerical-section"');
  assert.ok(strip > -1 && strip < row && row < panel, "the row sits between the topic strip and the panel");
  const rowHtml = experiments.slice(row, panel);
  for (const label of ["Notation", "Numerical results and diagnostics", "Full interpretation", "Setup and recorded plans"]) assert.ok(rowHtml.includes(label), label);
  assert.doesNotMatch(experiments.slice(panel), /<span>Numerical results and diagnostics<|<span>Setup and recorded plans<|>Notation</);
  assert.doesNotMatch(experiments, /class="btnrow empirical-support-links"/);
  assert.match(html, /<div class="card-heading"><h2>Implementation and Code<\/h2><\/div>/);
  const bare = ui.render(ui.Workbench, { branch: ref.branch });
  assert.doesNotMatch(bare, /Experiment supporting documents|empirical-support-row/);
  const partial = ui.render(ui.Workbench, { branch: ref.branch, diagnostics });
  assert.equal(partial.split('aria-label="Experiment supporting documents"').length - 1, 1);
  assert.match(partial, /Numerical results and diagnostics/); assert.doesNotMatch(partial, />Notation<|Setup and recorded plans/);
});

test("Implementation names the code files column and offers Notation in the first record's rail only", () => {
  const opened = [];
  const record = { generation_ref: { ...ref, family: "implementation_record" }, bundle_url: "/api/saved-bundle", reproduction: { status: "available" }, files: [{ path: "model.py", source_verified: true, artifact_url: "/api/saved-model" }] };
  const tree = ui.Implementation({ records: [record, { ...record, generation_ref: { ...record.generation_ref, generation_id: "implementation.second" } }], hasNotation: true, onNotation: () => opened.push("opened"), onSource() {} });
  const layouts = nodes(tree).filter(node => node.type?.name === "ResearchCardLayout");
  assert.equal(layouts.length, 2);
  const [first, second] = layouts.map(layout => ({ actions: ui.renderElement(layout.props.actions), resources: ui.renderElement(layout.props.resources) }));
  assert.match(first.actions, /^<section class="implementation-delivery"><h3>Code files<\/h3>[\s\S]*Download code and example bundle/);
  assert.match(first.resources, /<h3>Notation<\/h3>/);
  assert.ok(first.resources.indexOf("<h3>Notation</h3>") < first.resources.indexOf("<h3>Supporting reading</h3>"));
  assert.doesNotMatch(second.resources, /Notation/); assert.match(second.actions, /Code files/);
  nodes(layouts[0].props.resources).find(node => node.props.children === "Notation" && typeof node.props.onClick === "function").props.onClick();
  assert.deepEqual(opened, ["opened"]);
  const withoutHandler = ui.render(ui.Implementation, { records: [record], hasNotation: true });
  assert.doesNotMatch(withoutHandler, /Notation/);
  const notationOnly = ui.render(ui.Implementation, { records: [{}], hasNotation: true, onNotation() {} });
  assert.match(notationOnly, /research-card-layout has-rail"|research-card-layout has-rail /);
  assert.match(notationOnly, /<h3>Notation<\/h3>/); assert.doesNotMatch(notationOnly, /Code files|research-card-actions/);
  assert.match(notationOnly, /<div class="implementation-delivery"><p class="note">No verified code and example bundle/);
});
