import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { coverageForTab, coverageHomeTab, coverageTab, exhibitKey, questionHomeTab, questionTopics, routeEmpiricalExhibits } from "../src/empirical.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-cards-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {default as Workbench,EmpiricalEvaluationHistory as History,ExperimentSetupDocument as Study} from '${src}/components/EmpiricalWorkbench.jsx'; export {default as Question,EmpiricalQuestionTabs as Tabs,EmpiricalDecisionSummary as Summary,EmpiricalQuestionSetup as Setup,EmpiricalFormulation as Formulation,EmpiricalInterpretationDocument as Interpretation} from '${src}/components/EmpiricalQuestion.jsx'; export {default as Implementation,ImplementationDetails,ImplementationFiles} from '${src}/components/ImplementationReading.jsx'; export {ActionButton} from '${src}/components/Visuals.jsx'; export {SourceRef} from '${src}/components/Shared.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.a", phase: "P4", family: "empirical_synthesis", generation_id: "generation.saved", sha256: "a".repeat(64), package_id: "package.saved", run_id: "run.saved" };
const q = (id, category) => ({ id, question_id: id, branch: "method.a", generation_ref: { ...ref, family: "protocol" }, title: `Question ${id}`, test_ids: ["test.shared"], result: { category, outcome: "supported", answer_markdown: `Full answer ${id}.` } });
const e = (id, extra = {}) => ({ exhibit_id: id, branch: "method.a", phase: "P4", generation_ref: { ...ref, family: "exhibits" }, title: `Result ${id}`, source_verified: true, test_ids: ["test.shared"], table: { columns: [{ key: "v", label: "Value" }], rows: [{ v: 0 }, { v: 0.00000019 }] }, ...extra });
const data = { implementation_markdown: "Implemented the saved solver; tested synthetic cohorts and the recorded actual data.", method_fidelity_markdown: "The checked calculation agrees within scope; sparse failures remain.", conclusion_markdown: "Complete original conclusion.", tradeoff_markdown: "Complete original tradeoff.", limitations_markdown: "Complete original limitation.", intent_markdown: "Complete original purpose." };
const nodes = (tree) => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children), ...nodes(tree.props.resources)] : [];
const outsideDetails = (html) => { let depth = 0; return html.split(/(<\/?details\b[^>]*>)/g).filter((part) => { if (/^<details\b/.test(part)) { depth++; return false; } if (/^<\/details/.test(part)) { depth--; return false; } return depth === 0; }).join(""); };

test("Summary shows the frozen math recap and developed work, with full formulation retained and all exhibits in experiments", () => {
  const frozen = { ...ref, phase: "P2", family: "method", generation_id: "frozen.method", sha256: "b".repeat(64) };
  const record = { branch: "method.a", generation_ref: ref, decision_summary: { ...data, headline_exhibit_ids: ["exhibit.saved"], coverage: [{ dimension: "Performance", status: "assessed", question_ids: ["q.performance"], exhibit_ids: ["exhibit.saved"] }] }, evaluated_method: { summary: "A ridge hazard estimates $$\\Psi=E[Y^1-Y^0].$$", objective_markdown: "The full fitting criterion is $$Q(\\beta)=\\ell(\\beta)+\\lambda\\|\\beta\\|^2.$$",
    target_markdown: "The complete target account.", source_ref: frozen }, actual_data_application: { status: "analyzed", summary_markdown: "A real cohort was analyzed within its recorded scope." } };
  const before = structuredClone(record); const opened = [];
  const html = ui.render(ui.Workbench, { branch: "method.a", summaries: [record], exhibits: [e("exhibit.saved")], questions: [q("q.performance", "performance")], onSource: (source) => opened.push(source) });
  const summary = html.slice(0, html.indexOf('class="card empirical-code-card"'));
  const visible = outsideDetails(summary);
  for (const text of ["Summary", "Method evaluated", "Definition recorded at the start of this evaluation", "ridge hazard", "katex-display", data.implementation_markdown, "Actual data", "real cohort"]) assert.ok(visible.includes(text), text);
  assert.doesNotMatch(visible, /full fitting criterion|Complete original conclusion/);
  assert.match(summary, /Full formulation/); assert.doesNotMatch(summary, /full fitting criterion/);
  assert.match(ui.render(ui.Formulation, { record }), /full fitting criterion/);
  assert.doesNotMatch(summary, /<figure|<table/); assert.doesNotMatch(html, /empirical-data-picker|<select/);
  assert.equal((html.match(/<figure\b/g) || []).length, 1); assert.ok(html.indexOf("Result exhibit.saved") > html.indexOf("Experiments and Results"));
  for (const source of nodes(ui.Summary({ record, onSource: (value) => opened.push(value) })).filter((node) => node.type === ui.SourceRef && node.props.reference?.generation_id === frozen.generation_id)) source.props.onOpen(source.props.reference);
  assert.equal(opened.length, 1); assert.ok(opened.every((source) => source.sha256 === frozen.sha256));
  const authored = ui.render(ui.Summary, { record: { ...record, decision_summary: { ...data, method_formulation_markdown: "The implemented method is $$m(x)=x^2.$$" } } });
  assert.match(outsideDetails(authored), /Implemented method|katex-display/); assert.doesNotMatch(authored, /ridge hazard|Definition recorded at the start/);
  assert.deepEqual(record, before);
});

test("long authored formulations retain complete math in a reader and lead with the current finding", () => {
  const recap = "The supplied objective is\n$$\n\\begin{aligned}\nJ(\\pi)&=E[L],\\\\\n\nL&=Q+\\eta K+\\lambda B.\n\\end{aligned}\n$$";
  const formulation = `${recap}\n\nThe complete fitting account stays available.\n\n[Exact definition](https://example.test/definition)`;
  const record = { generation_ref: ref, scientific_outcome: { conclusion: "The fitted policies coincide.", scope: "Two synthetic fits only." }, decision_summary: { ...data, method_formulation_markdown: formulation }, evaluated_method: { summary: "A stale earlier-stage summary." } };
  const before = structuredClone(record), tree = ui.Summary({ record, onSource() {} });
  const html = ui.render(ui.Summary, { record, onSource() {} }), visible = outsideDetails(html);
  assert.match(visible, /The fitted policies coincide/); assert.match(visible, /Two synthetic fits only/);
  assert.ok(html.indexOf("Current finding and scope") < html.indexOf("Implemented method"));
  assert.match(visible, /supplied objective/); assert.match(visible, /katex-display/); assert.doesNotMatch(html, /katex-error|stale earlier-stage/);
  assert.doesNotMatch(visible, /complete fitting account|Exact definition/);
  const button = nodes(tree).find((node) => node.type?.name === "FormulationButton");
  assert.ok(button); assert.equal(button.props.record, record);
  const document = ui.Formulation({ record });
  assert.ok(nodes(document).some((node) => node.props.text === formulation), "The complete authored string is retained without reconstructing or clipping equations.");
  assert.ok(nodes(tree).some((node) => node.props.text === recap), "The recap ends at the parsed paragraph boundary after the complete display equation.");
  const sources = nodes(tree).find((node) => node.type === "details" && node.props.className === "research-details empirical-summary-sources");
  const source = nodes(sources).find((node) => node.type === ui.SourceRef && node.props.reference.entry_pointer === "/decision_summary/method_formulation_markdown");
  assert.equal(nodes(tree).filter((node) => node.type === ui.SourceRef && node.props.reference.entry_pointer === source.props.reference.entry_pointer).length, 1);
  assert.equal(source.props.reference.entry_pointer, "/decision_summary/method_formulation_markdown");
  assert.equal(source.props.reference.sha256, ref.sha256);
  assert.match(ui.render(ui.Formulation, { record }), /href="https:\/\/example.test\/definition"/);
  assert.deepEqual(record, before);
});

test("experiment settings skip empty conditions and preserve nonempty authored accounts", () => {
  const cases = [
    { case_id: "nominal", conditions: {}, regime: "nominal learning-plus-influence" },
    { case_id: "described", conditions: [], regime: " \n ", description: "Saved description." },
    { case_id: "authored", conditions: "Authored condition.", regime: "Unused regime." },
    { case_id: "structured", conditions: { body_md: "Structured authored condition." }, regime: "Unused structured regime." },
    { case_id: "missing", conditions: {}, regime: " ", description: [] },
  ];
  const before = structuredClone(cases);
  const html = ui.render(ui.Setup, { question: { title: "Recorded setup", case_ids: cases.map((item) => item.case_id) }, cases });
  for (const text of ["nominal learning-plus-influence", "Saved description.", "Authored condition.", "Structured authored condition.", "No separate conditions are recorded."]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /This record has no readable research account|Unused regime|Unused structured regime/);
  assert.deepEqual(cases, before);
});

test("experiment settings render saved structured conditions including scalar and nested values", () => {
  const cases = [
    { case_id: "c.nominal.dynamic", conditions: { privilege: "M=1 known true package; no test latent-state access", test_users: 2000 } },
    { case_id: "c.primary.dynamic", conditions: { calibration_users: 100, test_users: 2000 } },
    { case_id: "c.primary.nonadaptive", conditions: { calibration_users: 100, schedules: 585, test_users: 2000 } },
    { case_id: "c.early.uniform", conditions: { reused_calibration_datasets: true } },
    { case_id: "c.boundaries", conditions: { zero: 0, enabled: false, absent: null, nested: { outcomes: [0, false, null, "$q=1$", { latex: "x^2" }] } } },
    { case_id: "c.markdown", conditions: "Authored **condition** with $b(m,s)$.", regime: "Unused fallback." },
  ];
  const before = structuredClone(cases);
  const html = ui.render(ui.Setup, { question: { title: "Recorded setup", case_ids: cases.map((item) => item.case_id) }, cases });
  for (const text of ["Privilege:", "M=1 known true package; no test latent-state access", "Test users:", ">2000</span>", "Calibration users:", ">100</span>", "Schedules:", ">585</span>", "Reused calibration datasets:", ">true</span>", "Zero:", ">0</span>", "Enabled:", ">false</span>", "Absent:", ">Not recorded</span>", "Nested:", "Outcomes:", "<strong>condition</strong>"]) assert.ok(html.includes(text), text);
  assert.match(html, /class="katex/);
  assert.doesNotMatch(html, /This record has no readable research account|katex-error|Unused fallback/);
  assert.deepEqual(cases, before);
});

test("Code defaults to one assessment and bundle action while complete verification remains available", () => {
  const record = { generation_ref: ref, producer_role: "data_analyst", bundle_url: "/saved/bundle", reproduction: { status: "available", invocation: "python example.py", dependencies: [{ name: "numpy", version: "2.3.5" }] }, sections: [{ key: "verification", body_md: "The complete retained verification account." }, { key: "choices", body_md: "The complete retained choices account." }], files: [{ path: "model.py", artifact_url: "/saved/model", source_verified: true, download_url: "/saved/model?download=true" }] };
  const props = { records: [record], summary: { generation_ref: ref, decision_summary: data } };
  const html = ui.render(ui.Implementation, props), visible = outsideDetails(html);
  assert.match(visible, /Implementation assessment/); assert.match(visible, /sparse failures remain/); assert.match(visible, /href="\/saved\/bundle"/);
  assert.doesNotMatch(visible, /retained verification|retained choices|numpy|model\.py|python example|Inspect saved|Download model/);
  assert.match(html, /Implementation details|Saved files and checks/);
  const documents = ui.render(ui.ImplementationDetails, { record }) + ui.render(ui.ImplementationFiles, { record });
  for (const text of ["retained verification", "retained choices", "numpy", "model.py", "python example"]) assert.ok(documents.includes(text), text);
  for (const broken of [{ ...record, bundle_error: "Digest mismatch" }, { ...record, bundle_url: undefined }, { ...record, reproduction: { status: "unavailable" } }]) {
    const failed = outsideDetails(ui.render(ui.Implementation, { ...props, records: [broken] }));
    assert.match(failed, /Digest mismatch|No verified code and example bundle|Portable delivery is unavailable/);
    assert.doesNotMatch(failed, /href="\/saved\/bundle"/);
  }
});

test("capitalized legacy coverage routes uncertainty to Performance and shared fidelity checks to Tuning", () => {
  const questions = [q("q.uncertainty", "sensitivity"), q("q.fidelity", "implementation")];
  const coverage = [{ dimension: "Accuracy+Uncertainty", status: "partial", summary: "One full interval demonstration.", question_ids: ["q.uncertainty"] }, { dimension: "Implementation and portability", status: "assessed", question_ids: ["q.fidelity"] }, { dimension: "Tuning", status: "assessed", summary: "The six penalty selections are recorded.", question_ids: ["q.fidelity"] }];
  assert.equal(coverageTab("Uncertainty"), "comparisons"); assert.equal(coverageTab("Cost"), "computation");
  assert.deepEqual(questionTopics(questions[0], coverage), ["comparisons"]); assert.deepEqual(questionTopics(questions[1], coverage), ["setup", "tuning"]);
  assert.equal(questionHomeTab(questions[1], [...coverage].reverse()), "setup", "Shared fidelity checks keep their Synthetic home even when Tuning coverage appears first.");
  const props = { branch: "method.a", questions, summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], protocols: [{ branch: "method.a", generation_ref: { ...ref, family: "protocol" }, tuning_budget: { selection_data: "Training groups only.", search_space: "Six positive penalties.", maximum_trials: 0, fairness_rule: "The saved comparison budget." } }] };
  const tuning = ui.render(ui.Workbench, { ...props, initialTab: "tuning" });
  for (const text of ["six penalty selections", "Read the full answer", "Setup and recorded plans"]) assert.ok(tuning.includes(text), text);
  assert.doesNotMatch(tuning, /Training groups only|Six positive penalties|Maximum trials/);
  assert.doesNotMatch(tuning, /No tuning answer/);
  assert.match(tuning, /<a[^>]*title="Tuning: Assessed"[^>]*><span>Tuning<\/span><span class="empirical-section-coverage">Assessed/);
  assert.equal(coverageForTab(coverage, "tuning", questions).length, 1);
});

test("canonical exhibits follow exact declared IDs, bounded legacy references and explicit data links", () => {
  const questions = [q("q.shared", "performance"), q("q.legacy", "cost")];
  questions[0].result.exhibit_ids = ["exhibit.result-specific"];
  const coverage = [{ dimension: "Tuning", question_ids: ["q.shared"], summary: "See exhibit.fresh.tuning and exhibit.paired.extra, not another table." }, { dimension: "Cost", exhibit_ids: ["exhibit.explicit"], summary: "See exhibit.explicit." }, { dimension: "Accuracy", summary: "Shared result (exhibit.paired)." }, { dimension: "Robustness", summary: "Again (exhibit.paired)." }];
  const exhibits = [e("exhibit.fresh.tuning"), e("exhibit.explicit"), e("exhibit.paired"), e("exhibit.paired.extra"), e("exhibit.result-specific"), e("exhibit.figure", { media_type: "image/png", data_exhibit_ids: ["exhibit.paired"] }), e("exhibit.unassigned", { test_ids: [] }), e("exhibit.explicit")];
  const routes = routeEmpiricalExhibits(exhibits, questions, coverage, { generation_ref: ref });
  const topic = (id) => routes.find((entry) => entry.exhibit.exhibit_id === id)?.topic;
  assert.equal(routes.length, exhibits.length - 1); assert.equal(topic("exhibit.fresh.tuning"), "tuning"); assert.equal(topic("exhibit.explicit"), "computation"); assert.equal(topic("exhibit.paired"), "comparisons"); assert.equal(topic("exhibit.paired.extra"), "tuning"); assert.equal(topic("exhibit.figure"), "comparisons"); assert.equal(topic("exhibit.result-specific"), "tuning"); assert.equal(topic("exhibit.unassigned"), "other");
  const exactOnly = routeEmpiricalExhibits([e("exhibit.paired", { test_ids: [] })], [], [{ dimension: "Tuning", summary: "exhibit.paired.extra and prefixexhibit.paired are different IDs." }]);
  assert.equal(exactOnly[0].topic, "other");
  const overridden = routeEmpiricalExhibits([e("exhibit.explicit")], [], [{ dimension: "Tuning", summary: "exhibit.explicit" }, { dimension: "Cost", exhibit_ids: ["exhibit.explicit"] }]);
  assert.equal(overridden[0].topic, "computation");
  const stale = routeEmpiricalExhibits([e("exhibit.explicit", { generation_ref: { ...ref, run_id: "other.run" } })], [], coverage, { generation_ref: ref }); assert.equal(stale[0].topic, "other");
  const shared = [q("q.accuracy", "performance"), q("q.robustness", "sensitivity")].map((question) => ({ ...question, result: { ...question.result, exhibit_ids: ["exhibit.shared-points"] } }));
  const multi = routeEmpiricalExhibits([e("exhibit.shared-points")], shared, [{ dimension: "Accuracy", question_ids: ["q.accuracy"] }, { dimension: "Robustness", question_ids: ["q.robustness"] }]);
  assert.equal(multi[0].topic, "comparisons", "A shared explicit result has one deterministic authored-question home.");
  const broad = routeEmpiricalExhibits([e("exhibit.broad-status")], shared, [{ dimension: "Accuracy", question_ids: ["q.accuracy"] }, { dimension: "Robustness", question_ids: ["q.robustness"] }]);
  assert.equal(broad[0].topic, "other", "A broad multi-topic test association still cannot assign a scientific topic.");
  const before = structuredClone(exhibits);
  const html = ui.render(ui.Workbench, { branch: "method.a", questions, exhibits, summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], initialTab: "comparisons" });
  assert.equal((html.match(/<figure\b/g) || []).length, 2); // Primary comparisons preview inline; every exhibit keeps one canonical reader.
  assert.equal((html.match(/class="empirical-canonical-exhibit"/g) || []).length, 7);
  assert.match(html, /Other recorded results/); assert.match(html, /Result exhibit.unassigned/);
  assert.match(html, /Full answer q\.shared|Question q\.shared/, "Full authored questions remain reachable through topic navigation.");
  assert.deepEqual(exhibits, before);
});

function mount(Component, initialProps) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let props = initialProps; let tree;
  const state = (initial) => { const index = cursor++; if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial }; return [slots[index].value, (update) => { const next = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(next, slots[index].value)) { slots[index].value = next; dirty = true; } }]; };
  const effect = (run, dependencies) => { const index = cursor++; const old = slots[index]; if (!old || !dependencies || dependencies.some((value, offset) => !Object.is(value, old.dependencies?.[offset]))) { slots[index] = { dependencies, cleanup: old?.cleanup }; pending.push({ index, run }); } };
  const hooks = { useState: state, useEffect: effect, useRef: (initial) => { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; }, useId: () => { const index = cursor++; return (slots[index] ||= { value: `cards-${index}` }).value; } };
  const draw = () => { cursor = 0; pending = []; dirty = false; const previous = ui.dispatcher.current; try { ui.dispatcher.current = hooks; tree = Component(props); } finally { ui.dispatcher.current = previous; } for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); } };
  return { get tree() { return tree; }, update(next) { props = next; dirty = true; }, settle() { for (let i = 0; i < 20; i++) { if (!dirty) return tree; draw(); } throw new Error("Component did not settle."); } };
}

test("cross-section links focus the exact canonical result without hiding other sections", () => {
  const exhibit = e("exhibit.shared");
  const coverage = [{ dimension: "Accuracy", status: "assessed", exhibit_ids: [exhibit.exhibit_id] }, { dimension: "Robustness", status: "partial", summary: "See exhibit.shared." }];
  const props = { branch: "method.a", exhibits: [exhibit], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], initialTab: "sensitivity" };
  const app = mount(ui.Workbench, props); app.settle();
  const link = nodes(app.tree).find((node) => node.type === ui.ActionButton && Array.isArray(node.props.children) && node.props.children.includes("Main results"));
  assert.ok(link, "A cross-topic result has an explicit native button action.");
  const oldDocument = globalThis.document; const calls = [];
  const disclosure = { tagName: "DETAILS", open: false, parentElement: null };
  globalThis.document = { getElementById: (id) => { calls.push(["id", id]); return { parentElement: disclosure, focus: () => { assert.equal(disclosure.open, true); calls.push(["focus"]); }, scrollIntoView: () => calls.push(["scroll"]) }; } };
  try { link.props.onClick(); app.settle(); } finally { globalThis.document = oldDocument; }
  const tabs = nodes(app.tree).find((node) => node.type === ui.Tabs); assert.equal(tabs.props.selected, "comparisons");
  assert.ok(calls[0][1].includes(encodeURIComponent(exhibitKey(exhibit)))); assert.deepEqual(calls.slice(1), [["focus"], ["scroll"]]);
  const links = ui.Tabs(tabs.props).props.children;
  assert.ok(links.every((link) => link.type === "a" && !link.props.role && !link.props.onKeyDown));
});

test("a deliberately empty topic stays selected through polling, including old saved data selections", () => {
  const changes = [];
  const props = { branch: "method.a", questions: [q("q.performance", "performance")], reading: { tab: "tuning", dataView: "researcher_observed" }, onReadingChange: (value) => changes.push(value) };
  const app = mount(ui.Workbench, props); app.settle();
  app.update({ ...props, questions: [...props.questions, q("q.cost", "cost")] }); app.settle();
  assert.equal(nodes(app.tree).find((node) => node.type === ui.Tabs).props.selected, "tuning");
  assert.ok(changes.every((value) => value.tab === "tuning" && !Object.hasOwn(value, "dataView")));
});

test("cross-topic links focus the exact supporting reader anchor when its exhibit is unavailable inline", () => {
  const exhibit = e("exhibit.shared-unavailable", { source_error: "The retained file could not be verified." });
  const coverage = [{ dimension: "performance", status: "partial", exhibit_ids: [exhibit.exhibit_id] }, { dimension: "robustness", status: "partial", exhibit_ids: [exhibit.exhibit_id] }];
  const props = { branch: ref.branch, exhibits: [exhibit], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], initialTab: "sensitivity" };
  const app = mount(ui.Workbench, props); app.settle();
  const link = nodes(app.tree).find(node => node.type === ui.ActionButton && Array.isArray(node.props.children) && node.props.children.includes("Main results"));
  assert.ok(link);
  const previous = globalThis.document, calls = [], disclosure = { tagName: "DETAILS", open: false, parentElement: null };
  globalThis.document = { getElementById: id => { calls.push(id); return { parentElement: disclosure, focus: options => { assert.equal(disclosure.open, true); calls.push(options); }, scrollIntoView: options => calls.push(options) }; } };
  try { link.props.onClick(); app.settle(); } finally { globalThis.document = previous; }
  assert.ok(calls[0].endsWith(encodeURIComponent(exhibitKey(exhibit))));
  assert.deepEqual(calls.slice(1), [{ preventScroll: true }, { block: "start" }]);
  const html = ui.render(ui.Workbench, props);
  assert.ok(html.includes(`id="${calls[0]}"`) || html.includes(`-exhibit-${encodeURIComponent(exhibitKey(exhibit))}"`));
  assert.match(html, /class="empirical-supporting-exhibit"/);
  assert.match(html, /The retained file could not be verified/);
});

test("actual-data scope retains exact result navigation and source without calling the observed design synthetic", () => {
  const exhibit = e("exhibit.actual", { test_ids: [] });
  const coverage = [{ dimension: "actual_data", status: "assessed", summary: "The supplied cohort was analyzed.", exhibit_ids: [exhibit.exhibit_id], question_ids: [] }];
  const props = { branch: "method.a", initialTab: "setup", exhibits: [exhibit], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], protocols: [{ branch: "method.a", generation_ref: { ...ref, family: "protocol" }, data_sources: [{ data_source_id: "actual", origin: "researcher_observed", label: "Supplied cohort" }], data_or_simulation_unit: { source_type: "observed_data", sampling_or_generation_process: "The recorded observational cohort selection." } }] };
  const html = ui.render(ui.Workbench, props);
  assert.match(html, /No authored experimental setup is recorded/); assert.doesNotMatch(html, /<h3>Synthetic design<\/h3>|recorded observational cohort selection/);
  assert.equal((html.match(/<figure\b/g) || []).length, 1); assert.match(html, /Actual-data coverage source/); assert.match(html, /<h3[^>]*>Actual-data application<\/h3>/);
  const app = mount(ui.Workbench, props); app.settle();
  const source = nodes(app.tree).find((node) => node.type === ui.SourceRef && node.props.label === "Actual-data coverage source");
  assert.deepEqual(source.props.reference, { ...ref, entry_pointer: "/decision_summary/coverage/0" });
  assert.doesNotMatch(html, /Other recorded results/);
});

test("a shared exact Performance, Cost and Robustness result stays canonical and the Cost answer navigates to it", () => {
  const exhibit = e("exhibit.shared-points");
  const questions = [q("q.accuracy", "performance"), q("q.cost", "cost"), q("q.robustness", "sensitivity")].map((question) => ({ ...question, result: { ...question.result, exhibit_ids: [exhibit.exhibit_id] } }));
  const coverage = [{ dimension: "Accuracy", status: "assessed", question_ids: ["q.accuracy"] }, { dimension: "Cost", status: "assessed", question_ids: ["q.cost"] }, { dimension: "Robustness", status: "partial", question_ids: ["q.robustness"] }];
  const props = { branch: "method.a", exhibits: [exhibit], questions, summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], initialTab: "comparisons" };
  const performance = ui.render(ui.Workbench, props);
  assert.equal((performance.match(/<figure\b/g) || []).length, 1); assert.doesNotMatch(performance, /Other recorded results/);
  const cost = ui.render(ui.Workbench, { ...props, initialTab: "computation" });
  assert.equal((cost.match(/<figure\b/g) || []).length, 1); assert.match(cost, /View Result exhibit.shared-points<\/button>/);
  const app = mount(ui.Workbench, { ...props, initialTab: "computation" }); app.settle();
  const detail = nodes(app.tree).find((node) => node.type === ui.Question);
  const link = nodes(ui.Question(detail.props)).find((node) => node.type === ui.ActionButton && node.props.children?.includes(exhibit.title));
  assert.ok(link);
  const oldDocument = globalThis.document; const calls = [];
  globalThis.document = { getElementById: (id) => ({ parentElement: null, focus: () => calls.push(id), scrollIntoView() {} }) };
  try { link.props.onClick(); app.settle(); } finally { globalThis.document = oldDocument; }
  assert.equal(nodes(app.tree).find((node) => node.type === ui.Tabs).props.selected, "comparisons");
  assert.equal(calls.length, 1); assert.ok(calls[0].includes(encodeURIComponent(exhibitKey(exhibit))));
});

test("legacy numerical Markdown tables live in the original interpretation inside Experiments", () => {
  const record = { generation_ref: ref, decision_summary: { ...data, method_formulation_markdown: "The implemented model is $m(x)=x^2$.", conclusion_markdown: "Legacy numerical comparison.\n\n| Method | RMSE |\n| --- | --- |\n| Retained method | 0.0019 |\n\nThe original qualification remains." }, scientific_outcome: { conclusion: "The concise current finding.", scope: "The concise recorded scope." } };
  const before = structuredClone(record);
  const html = ui.render(ui.Workbench, { branch: "method.a", summaries: [record], onSource() {} });
  const codeStart = html.indexOf('class="card empirical-code-card"'), experimentStart = html.indexOf('class="card empirical-workspace"');
  const summary = html.slice(0, codeStart), code = html.slice(codeStart, experimentStart), experiments = html.slice(experimentStart);
  assert.doesNotMatch(summary + code, /<table|Legacy numerical comparison|Full interpretation/);
  assert.match(summary, /The concise current finding/); assert.match(summary, /The concise recorded scope/); assert.match(summary, /class="katex/);
  assert.equal((experiments.match(/<table\b/g) || []).length, 0);
  assert.match(experiments, /Full interpretation/);
  const interpretation = ui.render(ui.Interpretation, { record });
  assert.match(interpretation, /<td>Retained method<\/td><td>0\.0019<\/td>/);
  assert.match(interpretation, /The original qualification remains/);
  assert.deepEqual(record, before);
});

test("the numerical section leads with the main comparison and retains setup and distinct qualifications", () => {
  const exhibit = e("exhibit.paired", { test_ids: [] });
  const coverage = [
    { dimension: "synthetic_example", status: "assessed", summary: "One replication contains a paired dataset and its independent assessment sample.", limitation_markdown: "Only two decisions are simulated.", implication_markdown: "The comparison addresses this finite process.", question_ids: [] },
    { dimension: "performance", status: "partial", summary: "The paired reward gain is positive in the larger assessment sample.", exhibit_ids: [exhibit.exhibit_id], limitation_markdown: "The upper safety confidence limit exceeds the nominal error level.", implication_markdown: "Safety calibration remains unresolved.", question_ids: ["q.performance"] },
    { dimension: "robustness", status: "partial", summary: "Weaker overlap changes the selected subset; see exhibit.paired.", limitation_markdown: "The conditional means use different subsets.", implication_markdown: "The cross-condition comparison is not paired.", question_ids: [] },
    { dimension: "tuning", status: "not_assessed", summary: "Settings were fixed; tuning sensitivity was not evaluated.", limitation_markdown: "No tuning benefit is established.", implication_markdown: "The full settings remain in the protocol.", question_ids: [] },
  ];
  const props = { branch: ref.branch, questions: [{ ...q("q.performance", "performance"), result: { ...q("q.performance", "performance").result, outcome: "partially_supported" }, review: { theorist_findings_markdown: "Theorist: the conditional gain does not establish safety calibration.", generation_ref: ref } }], exhibits: [exhibit], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], protocols: [{ branch: ref.branch, generation_ref: ref, data_or_simulation_unit: { sampling_or_generation_process: "Complete protocol generator retained only in the setup reader." } }] };
  const before = structuredClone(props), html = ui.render(ui.Workbench, props), visible = outsideDetails(html);
  const result = html.indexOf("The paired reward gain"), table = html.indexOf("<figure"), limitation = html.indexOf("The upper safety confidence limit"), implication = html.indexOf("Safety calibration remains unresolved");
  assert.ok(result < table && table < limitation && limitation < implication);
  assert.ok(html.indexOf("One replication contains") > implication);
  assert.equal((html.match(/<figure\b/g) || []).length, 1);
  assert.match(html, /View Result exhibit.paired in Main results/);
  assert.doesNotMatch(visible, /Full answer q.performance|Theorist: the conditional gain|Complete protocol generator/);
  assert.match(html, /Theorist: the conditional gain/);
  assert.ok(html.indexOf("Settings were fixed") > html.indexOf('class="empirical-reading-section empirical-other-scope"'));
  assert.doesNotMatch(html, /<h3[^>]*>Tuning<\/h3>|role="tab(?:list|panel)?"/);
  assert.deepEqual(props, before);
});

test("a question-only fidelity exhibit follows the complete account that did not declare it", () => {
  const exhibit = e("exhibit.fidelity", { test_ids: [] });
  const question = q("q.fidelity", "implementation");
  question.result.exhibit_ids = [exhibit.exhibit_id];
  const coverage = [{ dimension: "synthetic_example", status: "assessed", summary: "The simulation checks the recorded finite process.", limitation_markdown: "Only the declared process was checked.", implication_markdown: "The qualification applies to this simulation.", question_ids: [question.id], exhibit_ids: [] }];
  const props = { branch: ref.branch, questions: [question], exhibits: [exhibit], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }] }, before = structuredClone(props);
  const html = ui.render(ui.Workbench, props), reader = html.indexOf('class="empirical-supporting-exhibit"');
  assert.ok(html.indexOf(coverage[0].summary) < html.indexOf(coverage[0].limitation_markdown));
  assert.ok(html.indexOf(coverage[0].limitation_markdown) < html.indexOf(coverage[0].implication_markdown));
  assert.ok(html.indexOf(coverage[0].implication_markdown) < reader, "An undeclared exhibit reader must follow the complete coverage account.");
  assert.equal((html.match(/<figure\b/g) || []).length, 0);
  assert.match(html, /Result exhibit.fidelity/);
  const app = mount(ui.Workbench, props); app.settle();
  const account = nodes(app.tree).find(node => node.props.className === "empirical-topic-account");
  assert.ok(account);
  assert.ok(!nodes(account).some(node => node.props.className === "empirical-canonical-exhibit"), "A question association does not make the exhibit part of the coverage account.");
  assert.deepEqual(props, before);
});

test("missing-exhibit warnings agree with the number of unavailable results", () => {
  for (const count of [1, 2]) {
    const record = { generation_ref: ref, decision_summary: { ...data, headline_exhibit_ids: Array.from({ length: count }, (_, index) => `exhibit.missing.${index}`) } };
    const html = ui.render(ui.Workbench, { branch: ref.branch, summaries: [record] });
    assert.ok(html.includes(`${count} referenced result ${count === 1 ? "exhibit" : "exhibits"} could not be verified or loaded. Inspect the retained sources before interpreting ${count === 1 ? "it" : "them"}.`));
  }
});

test("freeform and unassigned coverage retain primary homes and sources without repetition in setup", () => {
  const question = q("q.performance", "performance");
  const coverage = [
    { dimension: "Clinical usefulness", status: "partial", question_ids: [question.id], summary: "The clinical comparison remains conditional.", limitation_markdown: "Only the recorded conditions were tested.", implication_markdown: "Use remains limited to those conditions." },
    { dimension: "External deployment", status: "not_assessed", question_ids: [], summary: "External deployment was not evaluated.", limitation_markdown: "No transfer result is available.", implication_markdown: "Deployment performance remains unknown." },
  ];
  const record = { generation_ref: ref, decision_summary: { ...data, coverage } };
  const props = { branch: ref.branch, questions: [question], summaries: [record] }, before = structuredClone(props);
  const html = ui.render(ui.Workbench, props);
  const app = mount(ui.Workbench, props); app.settle();
  const accounts = nodes(app.tree).filter(node => node.props.className === "empirical-topic-account");
  assert.equal(accounts.length, coverage.length);
  coverage.forEach((entry, index) => {
    for (const passage of [entry.summary, entry.limitation_markdown, entry.implication_markdown]) assert.equal(html.split(passage).length - 1, 1);
    const account = accounts.find(node => node.props["data-reading-anchor"].includes(`:coverage:${entry.dimension}:`));
    assert.deepEqual(nodes(account).find(node => node.type === ui.SourceRef).props.reference, { ...ref, entry_pointer: `/decision_summary/coverage/${index}` });
  });
  assert.ok(html.indexOf(coverage[0].summary) < html.indexOf('class="empirical-reading-section empirical-other-scope"'));
  assert.ok(html.indexOf(coverage[1].summary) > html.indexOf('class="empirical-reading-section empirical-other-scope"'));
  assert.doesNotMatch(ui.render(ui.Study, { coverage, summary: record }), /Additional recorded scope|clinical comparison remains conditional|External deployment was not evaluated/);
  assert.doesNotMatch(html, /Setup and recorded plans/, "Coverage alone no longer opens an empty setup reader.");
  assert.deepEqual(props, before);
});

test("unassessed scope retains adverse findings, no-output states and failed-source notices without inventing results", () => {
  const coverage = [{ dimension: "performance", status: "not_assessed", summary: "No fitted policy was returned.", limitation_markdown: "This does not establish infeasibility.", implication_markdown: "The requested reward comparison remains unknown.", question_ids: ["q.none"] }];
  const question = { ...q("q.none", "performance"), status: "failed", result: { category: "performance", outcome: "inconclusive", answer_markdown: "The assessment rule returned no policy.", uncertainty_markdown: "Conditional reward is undefined.", generation_ref: ref }, review: { theorist_findings_markdown: "Theorist: absence of an output is not evidence that no feasible policy exists.", generation_ref: ref } };
  const exhibit = e("exhibit.failed", { source_verified: false, test_ids: [], table: { columns: [{ key: "v", label: "Unknown quantity" }], rows: [{ v: 99999 }] } });
  const html = ui.render(ui.Workbench, { branch: ref.branch, questions: [question], exhibits: [exhibit], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }] });
  const results = html.slice(html.indexOf('aria-labelledby=":R0:-comparisons-heading"'), html.indexOf('class="empirical-reading-section empirical-other-scope"'));
  assert.match(results, /No fitted policy was returned|This does not establish infeasibility|Conditional reward is undefined|Theorist: absence of an output/);
  assert.doesNotMatch(html, /<td>99999<\/td>/);
  assert.match(html, /The saved exhibit could not be verified/);
  assert.doesNotMatch(outsideDetails(html), /The assessment rule returned no policy/);
});

test("projection generation updates preserve section and question identities and never trigger navigation", () => {
  const props = { branch: ref.branch, questions: [q("q.performance", "performance")], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage: [{ dimension: "performance", status: "partial", summary: "The comparison remains conditional.", question_ids: ["q.performance"] }] } }] };
  const app = mount(ui.Workbench, props); app.settle();
  const anchors = tree => nodes(tree).map(node => node.props["data-reading-anchor"]).filter(Boolean);
  const before = anchors(app.tree), oldDocument = globalThis.document;
  globalThis.document = { getElementById() { throw new Error("Polling must not navigate or take focus."); } };
  try { app.update({ ...props, summaries: [{ ...props.summaries[0], generation_ref: { ...ref, generation_id: "projection.new", sha256: "b".repeat(64) } }] }); app.settle(); } finally { globalThis.document = oldDocument; }
  assert.deepEqual(anchors(app.tree), before);
  const question = nodes(app.tree).find(node => node.props["data-question-id"] === "q.performance");
  assert.equal(question.props.open, undefined, "The native disclosure keeps the researcher's own expanded state through unchanged polling.");
  const changed = ui.render(ui.Workbench, { ...props, summaries: [{ ...props.summaries[0], generation_ref: { ...ref, run_id: "run.next" } }] });
  assert.match(changed, /evaluation:method.a:run.next:package.saved:topic:comparisons/);
});

test("a freeform account has one authored-order home, exact source and secondary-topic navigation", () => {
  const questions = [q("q.accuracy", "performance"), q("q.robustness", "sensitivity")];
  const entry = { dimension: "Clinical usefulness and transfer", status: "partial", question_ids: ["q.robustness", "q.accuracy"], summary: "The broad clinical comparison remains unresolved.", limitation_markdown: "Only the specified conditions were tested.", implication_markdown: "Use remains limited to those conditions.", exhibit_ids: ["exhibit.freeform"] };
  const actual = { dimension: "actual_data", status: "assessed", question_ids: [], summary: "The supplied cohort was analyzed within its recorded scope.", exhibit_ids: ["exhibit.actual"] };
  const record = { generation_ref: ref, decision_summary: { ...data, coverage: [entry, actual] } };
  const exhibits = [e("exhibit.freeform", { test_ids: [] }), e("exhibit.actual", { test_ids: [] })];
  const props = { branch: ref.branch, questions, exhibits, summaries: [record] }, before = structuredClone(props);
  assert.equal(coverageHomeTab(entry, questions, record), "sensitivity", "The authored linked-question order sets the primary home independently of the question-array order.");
  assert.deepEqual(coverageForTab([entry], "comparisons", questions, record), [entry]);
  const routed = routeEmpiricalExhibits(exhibits, questions, record.decision_summary.coverage, record);
  assert.deepEqual(routed.map(item => item.topic), ["sensitivity", "actual_data"]);
  const foreign = { ...questions[1], generation_ref: { ...ref, run_id: "run.foreign" } };
  assert.equal(coverageHomeTab({ ...entry, question_ids: [foreign.id] }, [foreign], record), null);
  assert.deepEqual(coverageForTab([{ ...entry, question_ids: [foreign.id] }], "sensitivity", [foreign], record), []);
  assert.equal(routeEmpiricalExhibits([{ ...exhibits[0], generation_ref: { ...ref, run_id: "run.foreign" } }], questions, [entry], record)[0].topic, "other");

  const html = ui.render(ui.Workbench, props);
  assert.equal(html.split(entry.summary).length - 1, 1);
  const coverageAnchors = [...html.matchAll(/data-reading-anchor="([^"]+:coverage:[^"]+)"/g)].map(match => match[1]);
  assert.equal(coverageAnchors.length, 2); assert.equal(new Set(coverageAnchors).size, 2);
  assert.equal((html.match(/<figure\b/g) || []).length, 1);
  assert.equal((html.match(/class="empirical-canonical-exhibit"/g) || []).length, 2);
  assert.ok(html.indexOf(entry.summary) > html.indexOf('id=":R0:-sensitivity-heading"'));
  assert.match(html, /Read Clinical usefulness and transfer in Sensitivity and robustness/);
  assert.deepEqual(props, before);

  const app = mount(ui.Workbench, props); app.settle();
  const account = nodes(app.tree).find(node => node.props["data-reading-anchor"]?.includes(`:coverage:${entry.dimension}:`));
  const source = nodes(account).find(node => node.type === ui.SourceRef);
  assert.deepEqual(source.props.reference, { ...ref, entry_pointer: "/decision_summary/coverage/0" });
  const link = nodes(app.tree).find(node => node.type === ui.ActionButton && node.props.children?.includes(entry.dimension));
  const oldDocument = globalThis.document, calls = [];
  globalThis.document = { getElementById: id => { calls.push(["target", id]); return { parentElement: null, focus: options => calls.push(["focus", options]), scrollIntoView: options => calls.push(["scroll", options]) }; } };
  try { link.props.onClick(); app.settle(); } finally { globalThis.document = oldDocument; }
  assert.deepEqual(calls, [["target", account.props.id], ["focus", { preventScroll: true }], ["scroll", { block: "start" }]]);
});
