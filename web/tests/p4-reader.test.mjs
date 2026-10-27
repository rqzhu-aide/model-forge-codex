import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { directionDraftKey, evaluationPlanItems, readDecisionDraft, savedAnswerMatches, decisionAnswerPayload, continuationPayload, latestDecisionAnswer, savedDecisionHistory } from "../src/empiricalProgress.js";
import { modeLabel } from "../src/research.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p4-reader-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Empirical,{EmpiricalEvaluationHistory} from '${src}/components/EmpiricalWorkbench.jsx'; import {EmpiricalExhibit,EmpiricalQuestionTabs} from '${src}/components/EmpiricalQuestion.jsx'; import {EmpiricalProgressCard,EmpiricalPause,EmpiricalSavedDecisions,EmpiricalExecutionHistory,EmpiricalPlan} from '${src}/components/EmpiricalProgress.jsx'; export const render = props => renderToStaticMarkup(React.createElement(Empirical,props)); export const evaluationHistory = props => renderToStaticMarkup(React.createElement(EmpiricalEvaluationHistory,props)); export const exhibit = props => renderToStaticMarkup(React.createElement(EmpiricalExhibit,props)); export const progress = props => renderToStaticMarkup(React.createElement(EmpiricalProgressCard,props)); export const history = props => renderToStaticMarkup(React.createElement(EmpiricalExecutionHistory,props)); export const plan = props => renderToStaticMarkup(React.createElement(EmpiricalPlan,props)); export const pause = props => renderToStaticMarkup(React.createElement(EmpiricalPause,props)); export const savedDecisions = props => renderToStaticMarkup(React.createElement(EmpiricalSavedDecisions,props)); export const tabs = EmpiricalQuestionTabs; export {empiricalSource} from '${src}/components/EmpiricalDocument.jsx';`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const buttonWithText = (html, text) => (html.match(/<button\b[^>]*>[\s\S]*?<\/button>/g) || []).find((button) => button.includes(text)) || "";
const ref = { branch: "method.a", phase: "P4", family: "protocol", generation_id: "protocol.a", sha256: "a".repeat(64), run_id: "run.a", package_id: "package.a" };
const question = { question_id: "q.accuracy", test_ids: ["test.accuracy"], case_ids: ["case.small"], title: "Is the gain worth the extra time?", branch: "method.a", phase: "P4", generation_ref: ref,
  result: { category: "performance", answer_markdown: "Error decreases by 0.2, with higher cost.", relevance_markdown: "The user wants accurate estimates within one second.", comparison_markdown: "Mean error is 0.3 versus 0.5; lower is better.", conditions_markdown: "Only the small Gaussian example was tested.", reliability_markdown: "Matched seeds compare both methods.", uncertainty_markdown: "The difference interval is [-0.3,-0.1].", limitations_markdown: "One numerical failure is retained in the denominator.", decision_implication_markdown: "The accuracy gain needs a larger cost study.", next_steps_markdown: "Which runtime limit matters to your use?", observed_counts: { planned: 11, completed: 10, failed: 1, not_run: 0 }, outcome: "mixed", design_markdown: "Use paired samples and identical data splits.", plan_revision_ids: ["plan.initial"], generation_ref: { ...ref, family: "analyst_synthesis" } },
  review: { review_markdown: "Lead: the intended tradeoff is unresolved.", theorist_findings_markdown: "Theorist: finite sample checks are not a proof.", next_steps_markdown: "Choose a practical computation limit.", generation_ref: { ...ref, family: "empirical_synthesis" } } };
const exhibit = { exhibit_id: "table.comparison", title: "Small example", test_ids: ["test.accuracy"], case_ids: ["case.small"], branch: "method.a", phase: "P4", caption: "Both methods use the same cases; one failure is included.", media_type: "text/csv", artifact_url: "/api/v1/tables/comparison", generation_ref: { ...ref, family: "exhibits" }, table: { columns: [{ key: "method", label: "Method" }, { key: "error", label: "Mean error" }, { key: "cost", label: "Time", unit: "ms" }, { key: "failures", label: "Failures" }], rows: [{ method: "Proposed", error: 0.3, cost: 120, failures: 1 }, { method: "Baseline", error: 0.5, cost: 20, failures: 0 }], total_rows: 2, truncated: false } };
const props = { branch: "method.a", questions: [question], exhibits: [exhibit], onSource: noop, initialTab: "comparisons" };
const progress = { plan: { work_items: [{ work_item_id: "fidelity", title: "Check implementation" }, { work_item_id: "compare", title: "Compare error" }, { work_item_id: "cost", title: "Measure scaling" }], amendments: [{ revision_id: "plan.two", reason_markdown: "The pilot took longer than expected.", changes_markdown: "Defer scaling and add a focused boundary case.", inferential_consequences_markdown: "No scaling conclusion is possible.", deferred_work_item_ids: ["cost"], added_work_items: [{ work_item_id: "boundary", title: "Check boundary case" }], work_item_order: ["fidelity", "boundary", "compare", "cost"] }] }, ledger: [{ work_item_id: "fidelity", batch_id: "b1", status: "failed", elapsed_seconds: 2, plan_revision_id: "plan.initial" }, { work_item_id: "fidelity", batch_id: "b2", status: "completed", elapsed_seconds: 3, plan_revision_id: "plan.initial" }], budget: { used_seconds: 5, remaining_seconds: 55 }, checkpoint: { saved_at: "2026-09-25T12:00:00Z", summary: "A failed pilot was retained; fidelity now matches." } };
const request = { request_id: "direction.one", revision: 1, question: "Which tradeoff should we prioritize?", reason: "The intended runtime limit is unclear.", options: [{ label: "Prioritize accuracy", consequence: "Cost remains an explicit limitation." }] };
const saved = { request_id: request.request_id, request_revision: request.revision, revision: 2, note: "Preserve the estimand and compare both methods.", applied_to: [] };
const pauseProps = { projectId: "p", run: { run_id: "r", state: "awaiting_user", p4_progress: progress }, request };

test("paused evaluation alternatives render inline labels and complete display equations", () => {
  const chance = String.raw`\Pr_{\pi}(G_C>B)\le\delta`;
  const mean = String.raw`\mathbb{E}_{\pi}[G_C]\le B`;
  const value = { ...request, options: [
    { label: "Limit violation probability $\\delta$", consequence: `$$\n${chance}\n$$\n\nControls the frequency of budget overruns.` },
    { label: "Limit average cost $B$", consequence: `$$\n${mean}\n$$\n\nControls mean cost while allowing individual overruns.` },
  ] };
  const before = structuredClone(value);
  const html = render.pause({ ...pauseProps, request: value });
  const options = html.match(/<ul class="direction-options">([\s\S]*?)<\/ul>/)?.[1];
  assert.ok(options);
  assert.equal((options.match(/class="katex-display"/g) || []).length, 2);
  assert.match(options, /<b><span>Limit violation probability <span class="math-inline"/);
  const equations = [...options.matchAll(/<annotation encoding="application\/x-tex">([\s\S]*?)<\/annotation>/g)].map(([, equation]) => equation.replaceAll("&gt;", ">").replaceAll("&lt;", "<").replaceAll("&amp;", "&").trim());
  assert.deepEqual(equations, [String.raw`\delta`, chance, "B", mean]);
  assert.match(options, /Controls the frequency of budget overruns/);
  assert.match(options, /Controls mean cost while allowing individual overruns/);
  assert.doesNotMatch(options, /katex-error|\$\$/);
  assert.deepEqual(value, before);
});

test("question source control names the declared full Analyst account while preserving authored shorthand", () => {
  const value = { ...question, result: { ...question.result, has_full_analyst_account: true, comparison_markdown: "Full Q4." } };
  const before = structuredClone(value);
  const html = render.render({ ...props, questions: [value] });
  assert.match(html, /Open full Analyst account/);
  assert.match(html, /Full Q4\./);
  assert.deepEqual(value, before);
  assert.doesNotMatch(render.render(props), /Open full Analyst account/);
});

test("P4 owns three evidence cards and a single scientific tab layer with complete result blocks", () => {
  const html = render.render(props);
  for (const text of ["Summary", "Experiments and Results", "Error decreases by 0.2", "Mean error", "Proposed", "Baseline", "Matched seeds", "difference interval", "One numerical failure", "Recorded case outcomes: 10 completed, 1 failed and 0 not run, from 11 planned.", "accuracy gain needs a larger cost study", "Open original table", "Lead: the intended tradeoff", "Theorist: finite sample checks"]) assert.ok(html.includes(text), text);
  assert.equal((html.match(/role="tablist"/g) || []).length, 1);
  assert.equal((html.match(/class="card /g) || []).length, 3);
  assert.match(html, /role="tab"[^>]*aria-selected="true"[^>]*><span>Performance/);
  assert.doesNotMatch(html, /question-picker|>Next steps<|>Results<|>Design<|Complete numerical source|Which runtime limit matters|Recorded repetitions/);
  const excluded = render.render({ ...props, questions: [{ ...question, result: { ...question.result, observed_counts: { ...question.result.observed_counts, invalidated: 3 } } }] });
  assert.match(excluded, /Excluded earlier case outcomes: 3\. These are retained in history and do not contribute to the reported results\./);
  assert.doesNotMatch(excluded, /Excluded earlier attempts/);
  const panel = html.slice(html.indexOf('class="empirical-tab-panel"'));
  assert.match(panel, /<details class="research-details empirical-review-details"><summary>/);
  assert.ok(panel.indexOf("Small example") < panel.indexOf("Finding"));
  assert.ok(panel.indexOf("Finding") < panel.indexOf("Conditions and caveats"));
  assert.ok(panel.indexOf("Conditions and caveats") < panel.indexOf("Implication for the model"));
});

test("categories select scientific topics without inferring them from prose", () => {
  const questions = [question, { ...question, question_id: "q.cost", title: "A cost question", result: { ...question.result, category: "cost", answer_markdown: "Only recorded fitting cost." } }, { ...question, question_id: "q.unclassified", title: "Unclassified performance question", result: { ...question.result, category: undefined, answer_markdown: "Older category omitted." } }];
  const computation = render.render({ ...props, questions, initialTab: "computation" });
  assert.match(computation, /Only recorded fitting cost/); assert.doesNotMatch(computation, /Error decreases by 0.2|Older category omitted/);
  const setup = render.render({ ...props, questions, initialTab: "setup", progressData: progress, progressState: "running" });
  assert.match(setup, /Use paired samples and identical data splits/); assert.match(setup, /Older category omitted/); assert.match(setup, /Current evaluation plan/); assert.match(setup, /No scaling conclusion is possible/);
  const tuning = render.render({ ...props, initialTab: "tuning" }); assert.match(tuning, /No tuning answer is recorded/); assert.doesNotMatch(tuning, /Error decreases by 0.2/);
});

test("overview uses explicit implementation and theory accounts with truthful old-run fallbacks", () => {
  const summary = { implementation_markdown: "Reused the saved solver and ran the small example.", method_fidelity_markdown: "The deterministic check matches the Phase 2 update rule.", theory_relation: { status: "not_tested", explanation_markdown: "Consistency was available but was not tested empirically.", statement_ids: [] }, conclusion_markdown: "The small example supports further study.", tradeoff_markdown: "Accuracy costs extra time.", limitations_markdown: "Only one regime is studied.", coverage: [{ dimension: "performance", question_ids: [question.question_id] }] };
  const html = render.render({ ...props, summaries: [{ branch: "method.a", decision_summary: summary, generation_ref: ref }] });
  for (const text of ["What was developed and tested", "Implementation assessment", "Relationship to the theory", "Numerical findings and limitations", "Reused the saved solver", "Available theory was not tested", "Numerical evidence is not a proof", question.title]) assert.ok(html.includes(text), text);
  const old = render.render({ ...props, summaries: [{ decision_summary: { conclusion_markdown: "Old authored conclusion." } }] });
  assert.match(old, /Old authored conclusion/); assert.match(old, /does not state whether Phase 3 theory was available or tested/); assert.doesNotMatch(old, /No Phase 3 theory was available/);
  const empty = render.render({ branch: "method.a", awaitingDirection: true }); assert.match(empty, /waiting for your direction/); assert.match(empty, /Inspect the latest attempt in Activity/); assert.doesNotMatch(empty, /in Issues and decisions|Research Lead · published account/);
});

test("implementation author survives new analyst ownership and historical lead ownership", () => {
  const account = { branch: "method.a", generation_ref: { ...ref, family: "implementation_record" }, sections: [{ key: "rule", body_md: "The saved update uses $\\lambda$ as specified." }, { key: "verification", body_md: "The check could not run." }], theorist_review: { generation_ref: { ...ref, family: "theory_audit" }, body_md: "Fidelity remains unassessed." } };
  const before = structuredClone(account);
  for (const [role, author] of [["data_analyst", "Data Analyst"], ["research_lead", "Research Lead"]]) {
    const html = render.render({ branch: "method.a", implementations: [{ ...account, producer_role: role }], onSource: noop });
    assert.match(html, new RegExp(`<p class="note">Implementation account by ${author}</p>`));
    assert.doesNotMatch(html, /Evaluation run\.a/);
    const source = buttonWithText(html, "Implementation source");
    assert.match(source, /title="Implementation record · protocol\.a"/);
    assert.doesNotMatch(source, /disabled/);
    assert.match(html, /Independent assessment by Theorist · Same evaluation/);
    assert.match(html, /The check could not run/);
    assert.match(html, /Fidelity remains unassessed/);
    assert.match(html, /class="katex/);
  }
  const legacy = render.render({ branch: "method.a", implementations: [account] });
  assert.match(legacy, /Implementation account author is not recorded/);
  assert.doesNotMatch(legacy, /Implementation account by Data Analyst/);
  assert.deepEqual(account, before, "The exact run, package and generation source identity stays intact.");
});

test("figure and table captions use scientific prose and math rendering without changing source values", () => {
  const caption = "With $n=10$, **MCSE** is reported for $\\hat{\\theta}$.";
  const html = render.exhibit({ exhibit: { ...exhibit, caption } });
  assert.match(html, /<figcaption id="([^"]+)"><div class="research-document">/);
  assert.match(html, /<strong>MCSE<\/strong>/);
  assert.match(html, /class="katex/);
  assert.equal((html.match(/<strong>MCSE<\/strong>/g) || []).length, 1);
  assert.doesNotMatch(html, /<caption[^>]*>With \$n=10\$/);
  const captionId = html.match(/<figcaption id="([^"]+)"/)[1];
  assert.ok(html.includes(`<table aria-describedby="${captionId}">`));
  assert.match(html, /<caption class="sr-only">Small example<\/caption>/);
  assert.equal(exhibit.table.rows[0].error, 0.3);
  const figure = render.exhibit({ exhibit: { title: "Observed error", media_type: "image/png", artifact_url: "/api/v1/figure", caption } });
  assert.match(figure, /<figcaption><div class="research-document">/);
  assert.match(figure, /No explicit data-artifact link is recorded/);
});

test("P4 overview and coverage share exact source controls while retaining prose and mathematics", () => {
  const runId = ref.run_id; const digest = "b".repeat(64);
  const uri = `run://${runId}/renamed-answers.json`;
  const original = { ...ref, family: "analyst_synthesis", sha256: digest };
  const text = `With $n=20$, see [test.gain](${uri}#/question_results/1), [code](run://${runId}/solver.R), and [missing](run://${runId}/missing.json).`;
  const summaries = [{ branch: "method.a", generation_ref: { ...ref, family: "empirical_synthesis" }, source_artifacts: [{ uri, sha256: digest }], decision_summary: { implementation_markdown: text, method_fidelity_markdown: text, coverage: [{ dimension: "performance", status: "partial", summary: text, question_ids: [question.question_id] }] } }];
  const implementations = [{ branch: "method.a", generation_ref: { ...ref, family: "implementation_record", sha256: "c".repeat(64) }, files: [{ uri: `run://${runId}/solver.R`, sha256: "d".repeat(64), source_verified: true, artifact_url: "/api/v1/exact-solver?sha256=" + "d".repeat(64) }] }];
  const inputs = { ...props, questions: [{ ...question, result: { ...question.result, generation_ref: original }, review: undefined }], summaries, implementations };
  const before = JSON.stringify(inputs);
  const html = render.render(inputs);
  const implementation = html.slice(html.indexOf("What was developed and tested"), html.indexOf("Implementation and Code"));
  const assessment = html.slice(html.indexOf('class="implementation-assessment"'), html.indexOf('class="scientific-block"'));
  const coverage = html.slice(html.indexOf('class="empirical-topic-account"'), html.indexOf('class="empirical-topic-exhibits"'));
  for (const passage of [implementation, assessment, coverage]) {
    assert.match(buttonWithText(passage, "test.gain"), /class="source-link ui-action"/);
    assert.match(passage, /href="\/api\/v1\/exact-solver\?sha256=d{64}"/);
    assert.match(passage, /missing \(source unavailable\)/);
    assert.match(passage, /class="katex/);
    assert.doesNotMatch(passage, /\[test\.gain\]\(|\[code\]\(|run:\/\//);
  }
  assert.equal(JSON.stringify(inputs), before, "Rendering keeps the authored records and frozen source identities unchanged.");
});

test("P4 narrative sources require a unique declared digest and exact run and branch", () => {
  const uri = `run://${ref.run_id}/answers.json`; const sha256 = "b".repeat(64);
  const reference = { ...ref, family: "analyst_synthesis", sha256 };
  const sources = { branch: ref.branch, artifacts: [{ uri, sha256 }], records: [{ generation_ref: reference }] };
  assert.deepEqual(render.empiricalSource(`${uri}#/question_results/1`, sources), { reference: { ...reference, entry_pointer: "/question_results/1" } });
  assert.equal(render.empiricalSource(uri.replace(ref.run_id, "run.older"), sources), null);
  assert.equal(render.empiricalSource(uri, { ...sources, branch: "method.other" }), null);
  assert.equal(render.empiricalSource(uri, { ...sources, records: [{ generation_ref: { ...reference, run_id: "run.other" } }] }), null);
  assert.equal(render.empiricalSource(uri, { ...sources, records: [{ generation_ref: { ...reference, sha256: "c".repeat(64) } }] }), null);
  assert.equal(render.empiricalSource(uri, { ...sources, artifacts: [...sources.artifacts, { uri, sha256: "c".repeat(64) }] }), null);
  assert.equal(render.empiricalSource(uri, { ...sources, records: [...sources.records, { generation_ref: { ...reference, generation_id: "another.generation" } }] }), null);
  const file = { uri, sha256, branch: ref.branch, source_verified: true, artifact_url: "/api/v1/exact-file" };
  assert.deepEqual(render.empiricalSource(uri, { ...sources, records: [], files: [file] }), { artifact_url: file.artifact_url });
  assert.equal(render.empiricalSource(uri, { ...sources, records: [], files: [{ ...file, source_verified: false }] }), null);
  assert.equal(render.empiricalSource(uri, { ...sources, records: [], files: [{ ...file, source_error: "Digest mismatch" }] }), null);
  const otherFile = { ...file, uri: `run://${ref.run_id}/unrelated.json`, producing_run_id: ref.run_id, artifact_url: "/api/v1/other-file" };
  assert.equal(render.empiricalSource(uri, { ...sources, records: [], files: [otherFile] }), null);
  assert.deepEqual(render.empiricalSource(uri, { ...sources, records: [], files: [file, otherFile] }), { artifact_url: file.artifact_url });
  const relocated = { ...file, uri: undefined, sha256: undefined, artifact_sha256: sha256, producing_run_id: ref.run_id, artifact_url: "/api/v1/relocated-exhibit" };
  assert.deepEqual(render.empiricalSource(uri, { ...sources, records: [], files: [relocated] }), { artifact_url: relocated.artifact_url });
  assert.deepEqual(render.empiricalSource(uri, { ...sources, records: [], files: [file, relocated] }), { artifact_url: file.artifact_url });
  assert.equal(render.empiricalSource(uri, { ...sources, records: [], files: [{ ...relocated, producing_run_id: "run.other" }] }), null);
});

test("P4 narrative run locators consume verified retained-source bindings without source_artifacts", () => {
  const uri = `run://${ref.run_id}/outputs/p4.analyst/working/data_analyst/analyst_text.json`;
  const file = { uri, sha256: "e".repeat(64), branch: ref.branch, producing_run_id: ref.run_id, source_verified: true, artifact_url: "/api/v1/exact-primary?sha256=" + "e".repeat(64) };
  const summary = { branch: ref.branch, generation_ref: { ...ref, family: "empirical_synthesis" }, run_sources: [file], decision_summary: { implementation_markdown: `[Analyst's full account](${uri}) and [unbound](run://${ref.run_id}/outputs/p4.analyst/private.json).` } };
  const input = { ...props, summaries: [summary] }, before = JSON.stringify(input);
  const html = render.render(input);
  assert.match(html, /href="\/api\/v1\/exact-primary\?sha256=e{64}"[^>]*>[\s\S]*?Analyst&#x27;s full account/);
  assert.doesNotMatch(html, /full account \(source unavailable\)/);
  assert.match(html, /unbound \(source unavailable\)/);
  assert.equal(JSON.stringify(input), before);
  assert.equal(render.empiricalSource(uri, { branch: "method.other", files: [file] }), null);
  assert.equal(render.empiricalSource(uri, { branch: ref.branch, files: [{ ...file, source_verified: false }] }), null);
});

test("Setup preserves the scientific protocol, including exact numerical and boolean settings", () => {
  const protocol = JSON.parse(fs.readFileSync(new URL("../../contracts/examples/empirical-protocol.example.json", import.meta.url), "utf8"));
  protocol.tuning_budget.maximum_trials = 0; protocol.repetitions_and_uncertainty.paired_design = false;
  const html = render.render({ branch: "method.a", protocols: [{ ...protocol, branch: "method.a", generation_ref: ref }], onSource: noop });
  for (const text of [protocol.data_or_simulation_unit.sampling_or_generation_process, protocol.baselines[0].rationale, protocol.baselines[0].compute_budget, protocol.metrics[0].definition, protocol.tuning_budget.selection_data, protocol.repetitions_and_uncertainty.interval_or_error_method, protocol.multiplicity.correction_method, protocol.stopping_rules[0].action, protocol.leakage_checks[0].procedure, protocol.decision_thresholds[0].criterion]) assert.ok(html.includes(text), text);
  assert.match(html, /Sample sizes[\s\S]*>200<[^]*>1000</); assert.match(html, /Maximum trials<\/dt><dd>[^]*?<p>0<\/p>/);
  assert.match(html, /Paired comparisons<\/dt><dd>[^]*?<p>false<\/p>/); assert.match(html, /Repetitions<\/dt><dd>[^]*?<p>500<\/p>/);
  assert.doesNotMatch(html, /content_sha256|source_run_id/);
});

test("tables distinguish zero from missing data and preserve boolean values and truncation", () => {
  const html = render.exhibit({ exhibit: { ...exhibit, table: { ...exhibit.table, rows: [{ method: "Zero", error: 0, cost: null, failures: "not run" }], truncated: true, total_rows: 90 } }, onSource: noop });
  assert.match(html, /<td>Zero<\/td><td>0<\/td><td>Not recorded<\/td><td>not run<\/td>/); assert.match(html, /Rows 1 to 1 of 90/);
  const flags = render.exhibit({ exhibit: { ...exhibit, table: { columns: [{ key: "changed", label: "Verdict changed" }], rows: [{ changed: false }, { changed: true }, { changed: null }] } } });
  assert.match(flags, /<td>false<\/td>/); assert.match(flags, /<td>true<\/td>/); assert.match(flags, /<td>Not recorded<\/td>/);
});

test("evidence tab keyboard navigation wraps five topics without starting work", () => {
  let selected; let focused;
  const tabs = render.tabs({ id: "q", selected: "setup", onSelect: (value) => { selected = value; } }).props.children;
  const key = (index, value) => tabs[index].props.onKeyDown({ key: value, preventDefault() {}, currentTarget: { parentElement: { querySelectorAll: () => tabs.map((_, position) => ({ focus() { focused = position; } })) } } });
  key(0, "ArrowLeft"); assert.equal(selected, "sensitivity"); assert.equal(focused, 4);
  key(4, "ArrowRight"); assert.equal(selected, "setup"); key(1, "End"); assert.equal(selected, "sensitivity"); key(2, "Home"); assert.equal(selected, "setup");
});

test("long authored coverage keeps tab support to unique statuses with a complete accessible description", () => {
  const question = { branch: "method.a", question_id: "test.rmst", title: "Population RMST accuracy", category: "performance", generation_ref: ref };
  const coverage = [
    { dimension: "Population RMST point accuracy", status: "partial", question_ids: [question.question_id] },
    { dimension: "Clinical usefulness, awareness pathway and broader model comparisons", status: "not_assessed", question_ids: [question.question_id] },
    { dimension: "Long horizon RMST calibration under changing observation pathways", status: "partial", question_ids: [question.question_id] },
  ];
  const before = structuredClone(coverage);
  const description = coverage.map(item => `${item.dimension}: ${item.status === "partial" ? "Partial" : "Not assessed"}`).join(" · ");
  const tabs = render.tabs({ id: "rmst", selected: "comparisons", onSelect: noop, coverage, questions: [question] }).props.children;
  assert.equal(tabs[1].props.title, description);
  assert.equal(tabs[1].props["aria-description"], description);
  assert.equal(tabs[1].props["aria-controls"], "rmst-panel");
  assert.equal(tabs[1].props["aria-selected"], true);
  assert.equal(tabs[1].props.tabIndex, 0);
  const html = render.render({ branch: "method.a", questions: [question], summaries: [{ branch: "method.a", generation_ref: { ...ref, family: "empirical_synthesis" }, decision_summary: { coverage } }] });
  const performance = html.match(/<button\b[^>]*role="tab"[^>]*><span>Performance<\/span><span class="empirical-tab-coverage">([^<]*)<\/span><\/button>/);
  assert.ok(performance);
  assert.equal(performance[1], "Partial · Not assessed");
  assert.match(html, /<span>Tuning<\/span><span class="empirical-tab-coverage">Coverage not recorded<\/span>/);
  assert.match(html, /Population RMST point accuracy: Partial/);
  assert.match(html, /Clinical usefulness, awareness pathway and broader model comparisons: Not assessed/);
  assert.deepEqual(coverage, before);
});

test("plan amendments preserve attempts and distinguish absent execution detail from unrun work", () => {
  const items = evaluationPlanItems(progress);
  assert.deepEqual(items.map((item) => item.work_item_id), ["fidelity", "boundary", "compare", "cost"]);
  assert.deepEqual(items.map((item) => item.status), ["completed", "planned", "planned", "deferred"]);
  assert.equal(items[0].attempts.length, 2); assert.equal(evaluationPlanItems(progress, true)[2].status, "not_run");
  assert.equal(evaluationPlanItems({ ...progress, pending_batch: { work_item_id: "boundary", status: "running" } })[1].status, "running");
  const old = render.plan({ progress: { plan: progress.plan }, planOnly: true }); assert.match(old, /Execution detail not recorded/); assert.doesNotMatch(old, />Not run</);
});

test("compact progress never duplicates the decision form or full plan", () => {
  const html = render.progress({ ...pauseProps, run: { ...pauseProps.run, p4_progress: { ...progress, pause_request: request } }, onShowIssues: noop });
  for (const text of ["Waiting for your direction", "55 s", "Review requested direction"]) assert.ok(html.includes(text), text);
  assert.match(html, /class="empirical-progress-strip"/); assert.doesNotMatch(html, /<textarea|Which tradeoff|evaluation-plan-list|Continue with instructions|<h2/);
  const history = render.history({ run: pauseProps.run }); assert.match(history, /No scaling conclusion/); assert.match(history, /A failed pilot was retained/); assert.match(history, /class="pill fail">Failed/); assert.match(history, /class="pill ok">Completed/);
});

test("setup failures explain the unrun computation and retain technical logs with explicit controls", () => {
  const setup = { message: "The managed computation could not run. No finding about the model follows.", guidance: "Configure MF_P4_PYTHON for an accessible shared installation.", diagnostic: "Interpreter launch denied.", logs: [{ path: "p4-execution/batches/attempt.one/stderr.log", text: "CreateProcessAsUserW failed: 5 <denied>", sha256: "c".repeat(64) }] };
  const run = { ...pauseProps.run, p4_progress: { ...progress, attention_kind: "setup", setup_attention: setup } };
  const html = render.progress({ projectId: "p", run, onShowIssues: noop });
  for (const text of ["Setup needs attention", "MF_P4_PYTHON", "Technical log for this attempt", "CreateProcessAsUserW", "Review setup and continuation"]) assert.ok(html.includes(text), text);
  assert.match(html, /&lt;denied&gt;/);
  assert.doesNotMatch(html, /Your direction is needed|<textarea/);
  const editor = render.pause({ ...pauseProps, run, request: { ...request, attention_kind: "setup" }, onNavigate: noop, onExplain: noop });
  assert.match(editor, /The computation did not run/);
  assert.match(editor, /not evidence that the model failed/);
  for (const text of ["Save response", "Continue with instructions", "Finish with evidence so far", "End run"]) assert.ok(editor.includes(text), text);
  assert.doesNotMatch(editor, /Open Phase 2 methods|Open Phase 3 theory|Explain more/);
});

test("missing output after successful computation keeps output repair and explicit pause controls", () => {
  const outputRequest = { ...request, question: "Repair the declared experiment outputs before continuing.",
    reason: "The computation finished successfully, but its declared output 'missing.json' could not be retained. Check the script's output path and the saved logs before explicitly continuing." };
  const run = { ...pauseProps.run, p4_progress: { ...progress, pause_request: outputRequest,
    ledger: [{ work_item_id: "fidelity", batch_id: "b1", status: "output_error", exit_code: 0, elapsed_seconds: 2, plan_revision_id: "plan.initial" }] } };
  const html = render.progress({ projectId: "p", run, onShowIssues: noop });
  assert.match(html, /Review requested direction/);
  assert.doesNotMatch(html, /Setup needs attention|MF_P4_PYTHON|computation did not run/);
  const history = render.history({ run });
  assert.match(history, /class="pill fail">Output error/);
  const editor = render.pause({ ...pauseProps, run, request: outputRequest });
  for (const text of ["Repair the declared experiment outputs", "finished successfully", "missing.json", "Save response", "Continue with instructions", "Finish with evidence so far", "End run"]) assert.ok(editor.includes(text), text);
  assert.match(buttonWithText(editor, "Continue with instructions"), /disabled=""/);
  assert.doesNotMatch(editor, /Setup needs attention|MF_P4_PYTHON|computation did not run/);
});

test("pause answers must be saved before continuation and edits do not silently apply", () => {
  const unsaved = render.pause(pauseProps);
  assert.match(unsaved, /Save response/); assert.match(buttonWithText(unsaved, "Continue with instructions"), /disabled=""/);
  assert.match(unsaved, /Saving or discussing an answer does not resume experiments/);
  const ready = render.pause({ ...pauseProps, run: { ...pauseProps.run, p4_progress: { ...progress, saved_answer: saved } } });
  assert.match(ready, /Preserve the estimand/); assert.doesNotMatch(buttonWithText(ready, "Continue with instructions"), /disabled/);
  const applied = render.pause({ ...pauseProps, run: { ...pauseProps.run, state: "running", p4_progress: { ...progress, saved_answer: { ...saved, applied_to: ["r"] } } } });
  assert.match(applied, /This response was used by the evaluation/); assert.doesNotMatch(applied, /Continue with instructions|End run/);
  const blocked = render.pause({ ...pauseProps, run: { ...pauseProps.run, p4_progress: { ...progress, saved_answer: saved, continuation_blocked: "The model changed." } } }); assert.match(buttonWithText(blocked, "Continue with instructions"), /disabled/); assert.match(buttonWithText(blocked, "Finish with evidence so far"), /disabled/);
});

test("saving uses optimistic answer revisions; continuing consumes only an exact saved revision", () => {
  assert.deepEqual(decisionAnswerPayload(request, "  Revised direction  ", 2), { request_id: request.request_id, expected_revision: 1, expected_answer_revision: 2, note: "Revised direction" });
  const payload = continuationPayload({ request, action: "continue", saved, contextChoice: "frozen", extraBudget: "30", idempotencyKey: "once" });
  assert.equal(payload.answer_revision, 2); assert.equal(payload.additional_budget_seconds, 30); assert.equal(payload.context_choice, "frozen"); assert.equal(Object.hasOwn(payload, "answer"), false);
  assert.throws(() => continuationPayload({ request: { ...request, revision: 2 }, action: "continue", saved }), /exact question/);
  assert.equal(savedAnswerMatches(saved, { ...request, request_id: "other" }), false);
  assert.equal(Object.hasOwn(continuationPayload({ request, action: "finish", saved: null, extraBudget: 100 }), "answer_revision"), false);
  assert.equal(Object.hasOwn(continuationPayload({ request, action: "finish", saved, extraBudget: 100 }), "additional_budget_seconds"), false);
});

test("answered evaluation questions stay editable with their original source and no continuation controls", () => {
  const original = { ...request, explanation_target: { kind: "p4_pause", phase: "P4", branch: "method.a", run_id: "r", request_id: request.request_id, object_id: request.request_id, revision: 1, sha256: "a".repeat(64) } };
  const consumed = { ...saved, request: original, applied_to: ["r"] };
  const revised = { ...consumed, revision: 3, note: "For the next evaluation, study tuning cost.", applied_to: [] };
  const nextRequest = { ...request, request_id: "direction.two", question: "Which setting should come next?" };
  const nextAnswer = { ...saved, request: nextRequest, request_id: nextRequest.request_id, note: "Current pause answer." };
  const p4 = { ...progress, pause_request: nextRequest, saved_answer: nextAnswer, saved_answers: [revised, consumed, nextAnswer] };
  assert.equal(latestDecisionAnswer(p4, original), revised);
  assert.deepEqual(savedDecisionHistory(p4, true).map(({ answer }) => answer.revision), [3]);
  const html = render.savedDecisions({ projectId: "p", run: { run_id: "r", state: "awaiting_user", p4_progress: p4 }, onExplain: noop });
  assert.match(html, /^<details class="research-details empirical-saved-decisions"[^>]*><summary>Saved evaluation decisions \(1\)<\/summary>/);
  assert.doesNotMatch(html.match(/^<details[^>]*>/)?.[0] || "", /\bopen(?:=|\s|>)/);
  assert.match(html, /data-reading-anchor="evaluation:r:saved-decisions"/);
  for (const text of [original.question, original.reason, revised.note, "earlier evaluation used your previous answer", "Edit response", "Saving an edit does not change this evaluation", "Explain more"]) assert.ok(html.includes(text), text);
  assert.match(html, /data-card-role="history"/); assert.doesNotMatch(html, /Current pause answer|Which setting should|<textarea|Continue with instructions|End run|Additional experiment/);
  const legacy = { ...consumed, revision: 0, note: "Legacy direction already used." };
  const old = render.savedDecisions({ projectId: "p", run: { run_id: "r", state: "published", p4_progress: { saved_answers: [legacy] } } });
  assert.match(old, /Legacy direction already used/); assert.match(old, /Edit response/); assert.match(old, /This response was used by the evaluation/);
  assert.match(old, /^<details[^>]*><summary>Saved evaluation decisions \(1\)<\/summary>/);
  const active = render.pause({ projectId: "p", run: { run_id: "r", state: "awaiting_user", p4_progress: p4 }, request: nextRequest, onExplain: noop });
  assert.match(active, /^<section class="evaluation-pause"(?=[^>]*data-card-role="attention")[^>]*>/);
  assert.match(active, /data-reading-anchor="evaluation-pause:r:direction\.two:1"/);
  assert.match(active, /Which setting should come next\?/);
  assert.match(active, /<textarea/);
  assert.match(active, /Continue with instructions/);
  assert.doesNotMatch(active, /empirical-saved-decisions|For the next evaluation, study tuning cost/);
  assert.equal(decisionAnswerPayload(original, "Future direction", legacy.revision).expected_answer_revision, 0);
  assert.throws(() => continuationPayload({ request: original, action: "continue", saved: legacy }), /exact question/);
});

test("drafts preserve unsaved text with its original saved revision and exact request scope", () => {
  const key = directionDraftKey("p", "r", request);
  const storage = { getItem: (value) => value === key ? JSON.stringify({ note: "My pending edit", base_revision: 1 }) : null };
  assert.deepEqual(readDecisionDraft(key, saved, storage), { note: "My pending edit", base_revision: 1 });
  assert.deepEqual(readDecisionDraft(directionDraftKey("p", "r", { ...request, revision: 2 }), null, storage), { note: "", base_revision: 0 });
  const previous = globalThis.localStorage; globalThis.localStorage = storage;
  try {
    const html = render.pause({ ...pauseProps, run: { ...pauseProps.run, p4_progress: { ...progress, saved_answer: saved } } });
    assert.match(html, /My pending edit/); assert.match(html, /A newer response was saved elsewhere/); assert.match(buttonWithText(html, "Save updated response"), /disabled/); assert.match(buttonWithText(html, "Continue with instructions"), /disabled/);
  } finally { globalThis.localStorage = previous; }
});

test("history preserves provisional observations and technical feedback without confusing the two", () => {
  const checkpoint = { summary: "Normal-data comparisons completed.", observed_results_markdown: "The paired difference was -0.032002000555099275 with MCSE 0.016853594040025118.", next_action_markdown: "Check contamination next.", observed_results: "Old observation.", next_action: "Old action." };
  const run = { run_id: "r", state: "running", p4_progress: { ...progress, checkpoint } };
  const html = render.history({ run }); assert.match(html, /Provisional observations/); assert.match(html, /MCSE 0.016853594040025118/); assert.match(html, /Check contamination next/); assert.doesNotMatch(html, /Old observation|Old action/);
  const host = render.history({ run: { ...run, p4_progress: { ...progress, checkpoint: { ...checkpoint, host_feedback: true, latest_control_feedback: { error: "batch_id is required" } } } } });
  assert.match(host, /Last planning feedback/); assert.match(host, /outcome is unconfirmed/); assert.match(host, /<details[^>]*data-recovery-details="true"[^>]*>[\s\S]*batch_id is required[\s\S]*<\/details>/); assert.doesNotMatch(host, /No experiment started|MCSE|Check contamination next/);
  const corrupt = render.history({ run: { run_id: "r", state: "failed", terminal_reason: "Saved ledger is invalid", p4_progress: { execution_state_error: "Saved ledger is invalid" } } }); assert.match(corrupt, /saved execution state could not be read/); assert.doesNotMatch(corrupt, /No managed experiment was recorded/);
});

test("legacy numerical diagnostics stay complete inside experiments while history retains only their source", () => {
  const selected = { ...question, metric_ids: ["metric.error"], case_ids: ["case.small", "case.baseline"] };
  const cases = [{ case_id: "case.small", label: "Small Gaussian sample", comparator_id: "selected_method", metric_ids: ["metric.error", "metric.coverage"], test_ids: ["test.accuracy"] }, { case_id: "case.baseline", label: "Matched Gaussian sample", comparator_id: "baseline.median", metric_ids: ["metric.error"], test_ids: ["test.accuracy"] }];
  const diagnostics = [{ branch: "method.a", phase: "P4", generation_ref: { ...ref, family: "diagnostics" }, headline_numbers: [{ case_id: "case.small", metric: "metric.error", estimate: 0.31, mcse: 0.02, n_replicates: 10 }, { case_id: "case.baseline", metric: "metric.error", estimate: 0.53, mcse: 0.03, n_replicates: 10 }, { case_id: "case.small", metric: "metric.coverage", estimate: 9876 }, { case_id: "case.unrelated", metric: "metric.error", estimate: 5432 }] }];
  const protocol = { generation_ref: ref, metrics: [{ metric_id: "metric.error", name: "Mean squared error" }], baselines: [{ baseline_id: "baseline.median", name: "Sample median" }] };
  const html = render.render({ ...props, questions: [selected], exhibits: [], cases, diagnostics, protocols: [protocol] });
  for (const text of ["Complete numerical results and recorded diagnostics", "0.31", "0.53", "MCSE 0.02", "One numerical failure", "9,876", "5,432"]) assert.ok(html.includes(text), text);
  const answer = html.slice(html.indexOf('data-question-id="q.accuracy"'), html.indexOf('class="research-details empirical-complete-numbers"'));
  assert.doesNotMatch(answer, /9,876|5,432|Recorded results for this question/);
  const history = render.evaluationHistory({ branch: "method.a", diagnostics }); assert.doesNotMatch(history, /9876|5432|<table|<pre/); assert.match(history, /Numerical source/);
});

test("frozen source paths remain inspectable and work modes remain distinct", () => {
  const html = render.pause({ ...pauseProps, request: { ...request, evidence_refs: [{ path: "inputs/trunk/p2/catalog/version.json", statement: "The threshold is unspecified." }, "metrics_long.jsonl"] } });
  assert.match(html, /The threshold is unspecified/); assert.match(html, /inputs\/trunk\/p2\/catalog\/version.json/); assert.match(html, /metrics_long.jsonl/); assert.doesNotMatch(html, /<a\b/);
  assert.equal(modeLabel("p4.preliminary"), "Feasibility check"); assert.equal(modeLabel("p4.comprehensive"), "Detailed evaluation");
});
