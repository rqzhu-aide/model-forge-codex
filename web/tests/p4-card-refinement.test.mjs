import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { coverageForTab, coverageTab, exhibitKey, questionHomeTab, questionTopics, routeEmpiricalExhibits } from "../src/empirical.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-cards-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {default as Workbench,EmpiricalEvaluationHistory as History} from '${src}/components/EmpiricalWorkbench.jsx'; export {default as Question,EmpiricalQuestionTabs as Tabs,EmpiricalDecisionSummary as Summary,EmpiricalQuestionSetup as Setup} from '${src}/components/EmpiricalQuestion.jsx'; export {default as Implementation} from '${src}/components/ImplementationReading.jsx'; export {ActionButton} from '${src}/components/Visuals.jsx'; export {SourceRef} from '${src}/components/Shared.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.a", phase: "P4", family: "empirical_synthesis", generation_id: "generation.saved", sha256: "a".repeat(64), package_id: "package.saved", run_id: "run.saved" };
const q = (id, category) => ({ id, question_id: id, branch: "method.a", generation_ref: { ...ref, family: "protocol" }, title: `Question ${id}`, test_ids: ["test.shared"], result: { category, outcome: "supported", answer_markdown: `Full answer ${id}.` } });
const e = (id, extra = {}) => ({ exhibit_id: id, branch: "method.a", phase: "P4", generation_ref: { ...ref, family: "exhibits" }, title: `Result ${id}`, source_verified: true, test_ids: ["test.shared"], table: { columns: [{ key: "v", label: "Value" }], rows: [{ v: 0 }, { v: 0.00000019 }] }, ...extra });
const data = { implementation_markdown: "Implemented the saved solver; tested synthetic cohorts and the recorded actual data.", method_fidelity_markdown: "The checked calculation agrees within scope; sparse failures remain.", conclusion_markdown: "Complete original conclusion.", tradeoff_markdown: "Complete original tradeoff.", limitations_markdown: "Complete original limitation.", intent_markdown: "Complete original purpose." };
const nodes = (tree) => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
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
  assert.match(summary, /Model formulation and fitting criterion/); assert.match(summary, /full fitting criterion/);
  assert.doesNotMatch(summary, /<figure|<table/); assert.doesNotMatch(html, /empirical-data-picker|<select/);
  assert.equal((html.match(/<figure\b/g) || []).length, 1); assert.ok(html.indexOf("Result exhibit.saved") > html.indexOf("Experiments and Results"));
  for (const source of nodes(ui.Summary({ record, onSource: (value) => opened.push(value) })).filter((node) => node.type === ui.SourceRef && node.props.reference?.generation_id === frozen.generation_id)) source.props.onOpen(source.props.reference);
  assert.equal(opened.length, 2); assert.ok(opened.every((source) => source.sha256 === frozen.sha256));
  const authored = ui.render(ui.Summary, { record: { ...record, decision_summary: { ...data, method_formulation_markdown: "The implemented method is $$m(x)=x^2.$$" } } });
  assert.match(outsideDetails(authored), /Implemented method|katex-display/); assert.doesNotMatch(authored, /ridge hazard|Definition recorded at the start/);
  assert.deepEqual(record, before);
});

test("long authored formulations retain complete math behind a native disclosure and lead with the current finding", () => {
  const recap = "The supplied objective is\n$$\n\\begin{aligned}\nJ(\\pi)&=E[L],\\\\\n\nL&=Q+\\eta K+\\lambda B.\n\\end{aligned}\n$$";
  const formulation = `${recap}\n\nThe complete fitting account stays available.\n\n[Exact definition](https://example.test/definition)`;
  const record = { generation_ref: ref, scientific_outcome: { conclusion: "The fitted policies coincide.", scope: "Two synthetic fits only." }, decision_summary: { ...data, method_formulation_markdown: formulation }, evaluated_method: { summary: "A stale earlier-stage summary." } };
  const before = structuredClone(record), tree = ui.Summary({ record, onSource() {} });
  const html = ui.render(ui.Summary, { record, onSource() {} }), visible = outsideDetails(html);
  assert.match(visible, /The fitted policies coincide/); assert.match(visible, /Two synthetic fits only/);
  assert.ok(html.indexOf("Current finding and scope") < html.indexOf("Implemented method"));
  assert.match(visible, /supplied objective/); assert.match(visible, /katex-display/); assert.doesNotMatch(html, /katex-error|stale earlier-stage/);
  assert.doesNotMatch(visible, /complete fitting account|Exact definition/);
  const disclosure = nodes(tree).find((node) => node.type === "details" && node.props.className === "research-details empirical-method-definition");
  assert.ok(disclosure); assert.equal(disclosure.props.open, undefined);
  assert.equal(disclosure.props["data-reading-anchor"], "evaluation:generation.saved:method-definition");
  assert.equal(nodes(disclosure).find((node) => node.type === "summary").props.children, "Full mathematical formulation and fitting criterion");
  assert.ok(nodes(disclosure).some((node) => node.props.text === formulation), "The complete authored string is retained without reconstructing or clipping equations.");
  assert.ok(nodes(tree).some((node) => node.props.text === recap), "The recap ends at the parsed paragraph boundary after the complete display equation.");
  const source = nodes(disclosure).find((node) => node.type === ui.SourceRef);
  assert.equal(source.props.reference.entry_pointer, "/decision_summary/method_formulation_markdown");
  assert.equal(source.props.reference.sha256, ref.sha256);
  assert.match(html, /href="https:\/\/example.test\/definition"/);
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
  for (const text of ["retained verification", "retained choices", "numpy", "model.py", "python example"]) assert.ok(html.includes(text), text);
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
  for (const text of ["six penalty selections", "Training groups only", "Six positive penalties", "Maximum trials", ">0<", "Read the full answer"]) assert.ok(tuning.includes(text), text);
  assert.doesNotMatch(tuning, /No tuning answer/);
  assert.match(tuning, /role="tab"[^>]*title="Tuning: Assessed"[^>]*><span>Tuning<\/span><span class="empirical-tab-coverage">Assessed/);
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
  assert.equal((html.match(/<figure\b/g) || []).length, 3); // Performance pair + figure + unassigned retained below.
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

test("cross-topic links switch topics, open result disclosures and focus the exact canonical result", () => {
  const exhibit = e("exhibit.shared");
  const coverage = [{ dimension: "Accuracy", status: "assessed", exhibit_ids: [exhibit.exhibit_id] }, { dimension: "Robustness", status: "partial", summary: "See exhibit.shared." }];
  const props = { branch: "method.a", exhibits: [exhibit], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], initialTab: "sensitivity" };
  const app = mount(ui.Workbench, props); app.settle();
  const link = nodes(app.tree).find((node) => node.type === ui.ActionButton && Array.isArray(node.props.children) && node.props.children.includes("Performance"));
  assert.ok(link, "A cross-topic result has an explicit native button action.");
  const oldDocument = globalThis.document; const calls = [];
  const disclosure = { tagName: "DETAILS", open: false, parentElement: null };
  globalThis.document = { getElementById: (id) => { calls.push(["id", id]); return { parentElement: disclosure, focus: () => { assert.equal(disclosure.open, true); calls.push(["focus"]); }, scrollIntoView: () => calls.push(["scroll"]) }; } };
  try { link.props.onClick(); app.settle(); } finally { globalThis.document = oldDocument; }
  const tabs = nodes(app.tree).find((node) => node.type === ui.Tabs); assert.equal(tabs.props.selected, "comparisons");
  assert.ok(calls[0][1].includes(encodeURIComponent(exhibitKey(exhibit)))); assert.deepEqual(calls.slice(1), [["focus"], ["scroll"]]);
  let keyboardFocus;
  const buttons = ui.Tabs(tabs.props).props.children;
  buttons[1].props.onKeyDown({ key: "End", preventDefault() {}, currentTarget: { parentElement: { querySelectorAll: () => buttons.map((_, index) => ({ focus: () => { keyboardFocus = index; } })) } } });
  app.settle(); assert.equal(keyboardFocus, 4); assert.equal(nodes(app.tree).find((node) => node.type === ui.Tabs).props.selected, "sensitivity");
});

test("a deliberately empty topic stays selected through polling, including old saved data selections", () => {
  const changes = [];
  const props = { branch: "method.a", questions: [q("q.performance", "performance")], reading: { tab: "tuning", dataView: "researcher_observed" }, onReadingChange: (value) => changes.push(value) };
  const app = mount(ui.Workbench, props); app.settle();
  app.update({ ...props, questions: [...props.questions, q("q.cost", "cost")] }); app.settle();
  assert.equal(nodes(app.tree).find((node) => node.type === ui.Tabs).props.selected, "tuning");
  assert.ok(changes.every((value) => value.tab === "tuning" && !Object.hasOwn(value, "dataView")));
});

test("actual-data scope retains exact result navigation and source without calling the observed design synthetic", () => {
  const exhibit = e("exhibit.actual", { test_ids: [] });
  const coverage = [{ dimension: "actual_data", status: "assessed", summary: "The supplied cohort was analyzed.", exhibit_ids: [exhibit.exhibit_id], question_ids: [] }];
  const props = { branch: "method.a", initialTab: "setup", exhibits: [exhibit], summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], protocols: [{ branch: "method.a", generation_ref: { ...ref, family: "protocol" }, data_sources: [{ data_source_id: "actual", origin: "researcher_observed", label: "Supplied cohort" }], data_or_simulation_unit: { source_type: "observed_data", sampling_or_generation_process: "The recorded observational cohort selection." } }] };
  const html = ui.render(ui.Workbench, props);
  assert.match(html, /<h3>Study design<\/h3>/); assert.doesNotMatch(html, /<h3>Synthetic design<\/h3>/);
  assert.equal((html.match(/<figure\b/g) || []).length, 1); assert.match(html, /Actual-data coverage source/); assert.match(html, /View Result exhibit.actual in Other recorded results/);
  const app = mount(ui.Workbench, props); app.settle();
  const source = nodes(app.tree).find((node) => node.type === ui.SourceRef && node.props.label === "Actual-data coverage source");
  assert.deepEqual(source.props.reference, { ...ref, entry_pointer: "/decision_summary/coverage/0" });
  const link = nodes(app.tree).find((node) => node.type === ui.ActionButton && node.props.children?.includes("Other recorded results"));
  assert.ok(link);
});

test("a shared exact Performance, Cost and Robustness result stays canonical and the Cost answer navigates to it", () => {
  const exhibit = e("exhibit.shared-points");
  const questions = [q("q.accuracy", "performance"), q("q.cost", "cost"), q("q.robustness", "sensitivity")].map((question) => ({ ...question, result: { ...question.result, exhibit_ids: [exhibit.exhibit_id] } }));
  const coverage = [{ dimension: "Accuracy", status: "assessed", question_ids: ["q.accuracy"] }, { dimension: "Cost", status: "assessed", question_ids: ["q.cost"] }, { dimension: "Robustness", status: "partial", question_ids: ["q.robustness"] }];
  const props = { branch: "method.a", exhibits: [exhibit], questions, summaries: [{ generation_ref: ref, decision_summary: { ...data, coverage } }], initialTab: "comparisons" };
  const performance = ui.render(ui.Workbench, props);
  assert.equal((performance.match(/<figure\b/g) || []).length, 1); assert.doesNotMatch(performance, /Other recorded results/);
  const cost = ui.render(ui.Workbench, { ...props, initialTab: "computation" });
  assert.equal((cost.match(/<figure\b/g) || []).length, 0); assert.match(cost, /View Result exhibit.shared-points in Experiments and Results/);
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
  assert.doesNotMatch(summary + code, /<table|Legacy numerical comparison|Full interpretation and evaluation purpose/);
  assert.match(summary, /The concise current finding/); assert.match(summary, /The concise recorded scope/); assert.match(summary, /class="katex/);
  assert.equal((experiments.match(/<table\b/g) || []).length, 1);
  assert.match(experiments, /<td>Retained method<\/td><td>0\.0019<\/td>/);
  assert.match(experiments, /The original qualification remains/);
  assert.match(experiments, /<details class="research-details empirical-full-interpretation" data-reading-anchor="evaluation:generation.saved:full-interpretation"><summary>Full interpretation and evaluation purpose/);
  assert.deepEqual(record, before);
});
