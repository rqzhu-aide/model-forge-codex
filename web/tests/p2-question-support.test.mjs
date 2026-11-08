import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { populationChoice } from "./fixtures/researcher-decisions.mjs";
import { researchReadingSize } from "../src/readingSize.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p2-question-support-"));
const bundle = path.join(directory, "support.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {React}; export {default as Issues, IssueEntry} from '${src}/components/IssuesCard.jsx'; export {default as ResearchCardLayout} from '${src}/components/ResearchCardLayout.jsx'; export * from '${src}/components/QuestionSupport.jsx'; export {MethodReadingWindow, ReadingDocumentButton} from '${src}/components/MethodReadingWindow.jsx'; export {SourceRef} from '${src}/components/Shared.jsx'; export {default as Editorial} from '${src}/components/ReportEditorialQuestions.jsx'; export {default as ReadingHost} from '${src}/components/ReadingHost.jsx'; export {CitedRequestDocument} from '${src}/components/LiteratureCitation.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props));`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const input = { projectId: "project.question-support", phase: "P2", branch: "trunk", questionsOnly: true };
const question = { ...populationChoice, summary_markdown: "Earlier scientific context.\n\n$$a=b.$$", checkability: "Inspect the collection records.", related_source_refs: [{ ...populationChoice.generation_ref, generation_id: "generation.related", entry_pointer: "/checks/0" }] };
const text = tree => Array.isArray(tree) ? tree.map(text).join("") : tree && typeof tree === "object" ? text(tree.props?.children) : String(tree ?? "");
function all(tree, predicate) {
  if (Array.isArray(tree)) return tree.flatMap(item => all(item, predicate));
  if (!tree || typeof tree !== "object") return [];
  return [...(predicate(tree) ? [tree] : []), ...all(tree.props?.children, predicate), ...all(tree.props?.actions, predicate), ...all(tree.props?.resources, predicate)];
}
const find = (tree, predicate) => all(tree, predicate)[0];
const rows = tree => all(tree, node => node.type === ui.IssueEntry);
function hookHarness(Component, context) {
  const slots = []; let cursor = 0, pending = [];
  const internals = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const dispatcher = {
    useState(initial) { const index = cursor++; if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
    useRef(initial) { const index = cursor++; return slots[index] ||= { current: initial }; },
    useId() { return `question-support-${cursor++}`; },
    useEffect(callback, dependencies) { const index = cursor++; if (!slots[index] || dependencies.some((value, i) => value !== slots[index][i])) { slots[index] = dependencies; pending.push(callback); } },
    useContext(value) { return context ?? value._currentValue; },
    useLayoutEffect() { cursor++; }, useMemo(compute) { cursor++; return compute(); }, useCallback(callback) { cursor++; return callback; },
  };
  return value => {
    cursor = 0; const previous = internals.ReactCurrentDispatcher.current; internals.ReactCurrentDispatcher.current = dispatcher;
    let result; try { result = Component(value); } finally { internals.ReactCurrentDispatcher.current = previous; }
    const effects = pending; pending = []; effects.forEach(effect => effect()); return result;
  };
}

test("current typed P2 question owners keep full brief, exact scope, limits and one editor inline", () => {
  const card = hookHarness(ui.Issues)({ ...input, issues: [question] });
  const row = rows(card)[0];
  assert.equal(typeof row.props.onReadSupport, "function");
  const html = ui.render(ui.IssueEntry, row.props);
  for (const value of ["Why this matters", "Lead recommendation", "Applies across models.", "Your response", "Save answer"]) assert.ok(html.includes(value), value);
  assert.doesNotMatch(html, /What this choice changes|Why your answer matters|What remains unknown/);
  assert.equal((html.match(/Applies across models\./g) || []).length, 1);
  assert.doesNotMatch(html, /Shared across the proposed models/);
  assert.match(html, /Read background and sources/);
  assert.doesNotMatch(html, /<summary>Context and sources</);
  assert.doesNotMatch(html.replace(/<[^>]+>/g, ""), /Earlier scientific context|Inspect the collection records/);
  assert.equal((html.match(/<form\b/g) || []).length, 1);
  assert.equal((html.match(/<textarea\b/g) || []).length, 1);
  assert.equal((html.match(/The cohort&#x27;s observation/g) || []).length, 1);
  assert.equal((html.match(/data-reading-anchor="issue-context:/g) || []).length, 1);
  const scoped = { ...question, branch: "method.exact", scope: { kind: "model", model_ref: { stable_id: "method.exact", version: 3, definition_sha256: "b".repeat(64) } } };
  assert.match(ui.render(ui.IssueEntry, { ...row.props, issue: scoped }), /Applies only to this exact model version \(Version 3\)/);
  const trunkScoped = ui.render(ui.IssueEntry, { ...row.props, issue: { ...scoped, branch: "trunk", affected_record_ids: undefined } });
  assert.match(trunkScoped, /Applies only to this exact model version \(Version 3\)/);
  assert.doesNotMatch(trunkScoped, /Shared across the proposed models/);
});

test("limitations stay whole inline once even when exactly duplicated by another authored field", () => {
  for (const duplicate of ["summary_markdown", "checkability"]) {
    const item = { ...question, [duplicate]: question.information_limits };
    const support = ui.questionSupport(item, item.question);
    assert.equal(support.inlineLimits, null, "The full limitation belongs to the unified rationale.");
    assert.ok(support.sections.every(section => section.text !== item.information_limits));
    const html = ui.render(ui.IssueEntry, { ...input, issue: item });
    assert.equal((html.replace(/<[^>]+>/g, "").match(/The cohort&#x27;s observation/g) || []).length, 1);
  }
  const item = { ...question, context_markdown: question.information_limits };
  const support = ui.questionSupport(item, item.question);
  assert.equal(support.inlineLimits, null, "An exact limitation already shown in the full brief is not repeated.");
  assert.ok(support.sections.every(section => section.text !== item.information_limits));
  const markdown = { ...question, information_limits: undefined, information_limits_markdown: "Keep this complete limitation.\n\n$$u\\ne v.$$" };
  assert.equal(ui.questionSupport(markdown, markdown.question).inlineLimits, null);
  assert.match(ui.render(ui.IssueEntry, { ...input, issue: markdown }), /Keep this complete limitation[\s\S]*katex-display/);
});

test("support sizes count only the selected document and source-only controls show a source count", () => {
  const support = ui.questionSupport(question, question.question);
  assert.deepEqual(support.size, researchReadingSize([question.summary_markdown, question.checkability]));
  assert.equal(support.size.equations, 1);
  const onlySources = ui.questionSupport(populationChoice, populationChoice.question);
  assert.equal(onlySources.title, "View scientific sources");
  assert.equal(onlySources.sizeLabel, "1 scientific source");
  assert.deepEqual(onlySources.size, { words: 0, equations: 0 });
  const absent = ui.questionSupport({ ...populationChoice, generation_ref: undefined }, populationChoice.question);
  assert.equal(absent.available, false);
});

test("current typed questions in P1, P3 and P4 get the same reader and split row; P2-only wording stays in P2", () => {
  for (const phase of ["P1", "P3", "P4"]) {
    const card = hookHarness(ui.Issues)({ ...input, phase, questionsOnly: phase === "P1", progressive: true, issues: [{ ...question, phase, target_phase: phase, scope: undefined }] });
    const row = rows(card)[0];
    assert.equal(typeof row.props.onReadSupport, "function", phase);
    const html = ui.render(ui.IssueEntry, row.props);
    assert.match(html, /class="issue-team-content"/, phase);
    assert.match(html, /class="research-card-layout has-rail"/, phase);
    assert.match(html, /Read background and sources/, phase);
    assert.doesNotMatch(html, /<summary>Context and sources</, phase);
    assert.doesNotMatch(html, /Shared across the proposed models/, phase);
    assert.doesNotMatch(html, /the Lead can use it for the next model development work|across models in their next work/, phase);
    assert.match(html, /After you save, it is available to the next work you start\./, phase);
  }
  const p2 = ui.render(ui.IssueEntry, rows(hookHarness(ui.Issues)({ ...input, issues: [{ ...question, scope: undefined }] }))[0].props);
  assert.equal((p2.match(/Shared across the proposed models\./g) || []).length, 1);
  const raised = ui.render(ui.IssueEntry, rows(hookHarness(ui.Issues)({ ...input, phase: "P4", progressive: true, issues: [{ ...question, phase: "P3", target_phase: "P4" }] }))[0].props);
  assert.match(raised, /Raised during [^<]+; applicable here\./);
});

test("legacy, related and historical questions retain their existing owners", () => {
  const legacy = { ...question, response_kind: undefined };
  const p2 = hookHarness(ui.Issues)({ ...input, issues: [legacy] });
  assert.match(ui.render(ui.IssueEntry, rows(p2)[0].props), /<summary>Context and sources<\/summary>/);
  const p3Legacy = hookHarness(ui.Issues)({ ...input, phase: "P3", progressive: true, issues: [{ ...legacy, phase: "P3", target_phase: "P3" }] });
  const p3LegacyHtml = ui.render(ui.IssueEntry, rows(p3Legacy)[0].props);
  assert.match(p3LegacyHtml, /<summary>Context and sources<\/summary>/);
  assert.doesNotMatch(p3LegacyHtml, /research-card-layout/);
  const related = { ...question, phase: "P2", target_phase: "P4" };
  const relatedCard = hookHarness(ui.Issues)({ ...input, phase: "P4", attention: [related] });
  assert.equal(rows(relatedCard)[0].props.readOnly, true);
  assert.equal(rows(relatedCard)[0].props.onReadSupport, undefined);
  const relatedHtml = ui.render(ui.IssueEntry, { ...rows(relatedCard)[0].props, onReadSupport() {} });
  assert.doesNotMatch(relatedHtml, /research-card-layout/);
  assert.match(relatedHtml, /<summary>Context and sources<\/summary>/);
  const old = { ...question, explanation_target: { ...question.explanation_target, generation_id: "generation.old", sha256: "c".repeat(64) } };
  const answer = { attention_id: old.attention_id, attention: old, question_ref: old.explanation_target, note: "Original response.", revision: 1 };
  const historical = rows(hookHarness(ui.Issues)({ ...input, issues: [question], answers: [answer] })).find(row => row.props.issue.researcher_answer);
  assert.equal(historical.props.onReadSupport, undefined);
  assert.match(ui.render(ui.IssueEntry, historical.props), /<summary>Context and sources<\/summary>/);
});

test("opening support preserves the selected option, unsaved note and original question anchors", () => {
  const renderCard = hookHarness(ui.Issues), renderRow = hookHarness(ui.IssueEntry);
  let card = renderCard({ ...input, issues: [question] }), row = rows(card)[0];
  let tree = renderRow(row.props);
  find(tree, node => node.type === "input" && node.props.value === "option:observed").props.onChange();
  find(tree, node => node.type === "textarea").props.onChange({ target: { value: "Keep my unsaved qualification." } });
  tree = renderRow(row.props);
  const anchor = tree.props["data-reading-anchor"];
  find(tree, node => node.type === ui.ReadingDocumentButton).props.onClick({ currentTarget: { isConnected: true } });
  card = renderCard({ ...input, issues: [question] }); row = rows(card)[0]; tree = renderRow(row.props);
  assert.equal(find(tree, node => node.type === "input" && node.props.value === "option:observed").props.checked, true);
  assert.equal(find(tree, node => node.type === "textarea").props.value, "Keep my unsaved qualification.");
  assert.equal(tree.props["data-reading-anchor"], anchor);
  assert.equal(all(tree, node => node.type === "form").length, 1);
  assert.ok(find(card, node => node.type === ui.MethodReadingWindow));
});

test("open scientific support and citation mappings stay frozen through polling and question replacement", () => {
  const citationSource = { ...question.generation_ref, family: "literature_review", generation_id: "generation.cited", entry_pointer: "/papers/0" };
  const item = { ...structuredClone(question), citations: [{ source_id: "paper.original", entry_ref: { entry_sha256: "c".repeat(64) }, card: { generation_ref: citationSource, entry_pointer: "/papers/0" } }] };
  const opened = [], render = hookHarness(ui.Issues), props = { ...input, issues: [item], onSource: source => opened.push(source) };
  let tree = render(props); rows(tree)[0].props.onReadSupport(item, item.question, [], { isConnected: false });
  tree = render(props); const initial = find(tree, node => node.type === ui.MethodReadingWindow).props.snapshot;
  item.summary_markdown = "Polling must not replace this open document.";
  item.citations[0].card.generation_ref.generation_id = "generation.replaced";
  const replacement = { ...item, explanation_target: { ...item.explanation_target, generation_id: "generation.new" } };
  for (const issues of [[item], [replacement], []]) {
    tree = render({ ...props, issues });
    const current = find(tree, node => node.type === ui.MethodReadingWindow).props.snapshot;
    assert.equal(current, initial);
    assert.equal(current.body.props.issue.summary_markdown, question.summary_markdown);
    assert.equal(current.body.props.issue.citations[0].card.generation_ref.generation_id, "generation.cited");
  }
  const body = ui.QuestionSupportDocument(initial.body.props);
  const sources = all(body, node => node.type === ui.SourceRef);
  sources[0].props.onOpen(sources[0].props.reference);
  assert.deepEqual(opened, [question.generation_ref]);
  const cited = find(body, node => node.type === ui.CitedRequestDocument);
  const document = ui.CitedRequestDocument(cited.props);
  document.props.onOpenCitation(initial.body.props.issue.citations[0]);
  assert.equal(opened[1].generation_id, "generation.cited");
  assert.equal(opened[1].entry_pointer, "/papers/0");
  tree = render({ ...props, phase: "P1" });
  assert.equal(find(tree, node => node.type === ui.MethodReadingWindow), undefined);
  tree = render(props);
  assert.equal(find(tree, node => node.type === ui.MethodReadingWindow), undefined, "Returning to P2 does not revive a retained old window.");
});

test("a reader closes when the selected branch, method or model changes and does not return with it", () => {
  const render = hookHarness(ui.Issues);
  const modelRef = { stable_id: "method.a", version: 2 };
  const props = { ...input, phase: "P3", progressive: true, methodId: "method.a", modelRef, issues: [{ ...question, phase: "P3", target_phase: "P3" }] };
  const window = tree => find(tree, node => node.type === ui.MethodReadingWindow);
  for (const change of [{ branch: "method.b" }, { methodId: "method.b" }, { modelRef: { ...modelRef, version: 3 } }]) {
    let tree = render(props); rows(tree)[0].props.onReadSupport(props.issues[0], question.question, [], { isConnected: false });
    tree = render({ ...props, modelRef: { ...modelRef } });
    assert.ok(window(tree), "An equal model reference keeps the reader open.");
    tree = render({ ...props, ...change });
    assert.equal(window(tree), undefined, JSON.stringify(change));
    tree = render(props);
    assert.equal(window(tree), undefined, `Returning after ${JSON.stringify(change)} does not revive the reader.`);
  }
});

test("question-support position keys follow scientific sources and exclude answer revisions", () => {
  const context = { projectId: input.projectId, phase: "P2", branch: "trunk" };
  const key = (item, overrides = {}) => ui.questionSupportReadingKey({ ...context, ...overrides }, item);
  assert.equal(key(question), key(structuredClone(question)));
  assert.equal(key(question), key({ ...question, researcher_answer: { note: "Changed response.", revision: 8 } }));
  assert.notEqual(key(question), key(question, { projectId: "project.other" }));
  for (const overrides of [{ phase: "P3" }, { branch: "method.b" }, { methodId: "method.a" }, { modelRef: { stable_id: "method.a", version: 2 } }]) assert.notEqual(key(question), key(question, overrides), JSON.stringify(overrides));
  assert.equal(key(question, { modelRef: { stable_id: "method.a", version: 2 } }), key(question, { modelRef: { version: 2, stable_id: "method.a" } }));
  for (const field of ["generation_id", "sha256", "entry_pointer"]) assert.notEqual(key(question), key({ ...question, explanation_target: { ...question.explanation_target, [field]: "different" } }));
  assert.notEqual(key(question), key({ ...question, related_source_refs: [{ ...question.related_source_refs[0], generation_id: "generation.changed-related" }] }));
  assert.notEqual(key(question), key({ ...question, citations: [{ source_id: "paper.extra", card: { generation_ref: question.generation_ref } }] }));
});

test("questions use the shared action, account and reading order with a full-width answer below", () => {
  const props = rows(hookHarness(ui.Issues)({ ...input, issues: [question], onExplain: () => {} }))[0].props;
  const html = ui.render(ui.IssueEntry, props);
  const at = value => { const index = html.indexOf(value); assert.ok(index >= 0, value); return index; };
  assert.match(html, /class="issue-team-content"/);
  assert.equal((html.match(/class="research-card-layout has-rail has-actions"/g) || []).length, 1);
  assert.doesNotMatch(html, /<aside\b/, "Each open row must not add a complementary landmark.");
  assert.match(html, /class="research-card-actions" role="group" aria-label="Question actions"/);
  assert.match(html, /class="research-card-resources" role="group" aria-label="Question supporting reading"/);
  const order = ["research-card-actions", "Discuss</button>", "Get the Lead&#x27;s advice", "research-card-account", "Why this matters", "The cohort&#x27;s observation", "research-card-resources", "From Research lead", "Applies across models.", "Read background and sources", "<form"].map(at);
  assert.deepEqual(order, [...order].sort((a, b) => a - b));
  assert.doesNotMatch(html.slice(at("research-card-actions"), at("research-card-account")), /From Research lead|Applies across models|Read background and sources/);
  assert.equal((html.match(/>Discuss<\/button>/g) || []).length, 1);
  assert.equal((html.match(/Get the Lead&#x27;s advice/g) || []).length, 1);
  const tree = hookHarness(ui.IssueEntry)(props);
  const layout = find(tree, node => node.type === ui.ResearchCardLayout);
  assert.match(layout.props["data-reading-anchor"], /^issue-context:/);
  assert.equal(layout.props.resourceElement, "div");
  assert.equal(all(layout, node => node.type === "form").length, 0, "The answer stays full width below the split.");
  assert.equal(all(tree, node => node.type === "form").length, 1);
  const plain = ui.render(ui.IssueEntry, { ...props, issue: { ...populationChoice, generation_ref: undefined } });
  assert.doesNotMatch(plain, /research-card-layout|Read background and sources|View scientific sources/);
  assert.ok(plain.indexOf("From Research lead") < plain.indexOf("Why this matters"));
  const legacy = ui.render(ui.IssueEntry, { ...props, issue: { ...question, response_kind: undefined } });
  assert.doesNotMatch(legacy, /research-card-layout/);
  assert.match(legacy, /<summary>Context and sources<\/summary>/);
});

test("P5 editorial choices split the same way and open their background in the project reader", () => {
  const modelRef = { stable_id: "method.a", version: 2, definition_sha256: "d".repeat(64) };
  const scope = { projectId: input.projectId, phase: "P5", branch: "method.a" };
  const source = { ...question.generation_ref, phase: "P5", branch: "method.a" };
  const editorial = { ...question, phase: "P5", target_phase: "P5", branch: "method.a", scope: { kind: "model", branch: "method.a", model_ref: modelRef }, explanation_target: source, generation_ref: source };
  const context = { ...scope, methodId: "method.a", modelRef, issues: [editorial] };
  const renderHost = hookHarness(ui.ReadingHost);
  let host = renderHost({ scope });
  const row = rows(hookHarness(ui.Editorial, host.props.value)({ context, onSource: () => {}, onExplain: () => {} }))[0];
  assert.equal(typeof row.props.onReadSupport, "function");
  const html = ui.render(ui.IssueEntry, row.props);
  const at = value => { const index = html.indexOf(value); assert.ok(index >= 0, value); return index; };
  assert.match(html, /class="issue-team-content"/);
  assert.match(html, /class="research-card-layout has-rail has-actions"/);
  assert.match(html, /class="research-card-resources" role="group" aria-label="Question supporting reading"/);
  assert.doesNotMatch(html, /<aside\b/);
  assert.doesNotMatch(html, /<summary>Context and sources</);
  const order = ["research-card-actions", "Discuss</button>", "research-card-account", "Why this matters", "The cohort&#x27;s observation", "research-card-resources", "Applies only to this exact model version (Version 2).", "Read background and sources", "<form"].map(at);
  assert.deepEqual(order, [...order].sort((a, b) => a - b));
  assert.doesNotMatch(html.replace(/<[^>]+>/g, ""), /Earlier scientific context|Inspect the collection records/);
  row.props.onReadSupport(editorial, editorial.question, [], { isConnected: true });
  host = renderHost({ scope });
  const snapshot = find(host, node => node.type === ui.MethodReadingWindow).props.snapshot;
  assert.equal(snapshot.key, ui.questionSupportReadingKey({ ...scope, methodId: "method.a", modelRef }, editorial));
  assert.equal(snapshot.title, "Background and sources");
  assert.equal(snapshot.phase, "P5");
  assert.match(ui.render(ui.QuestionSupportDocument, snapshot.body.props), /Earlier scientific context[\s\S]*Inspect the collection records/);
  assert.equal(find(renderHost({ scope: { ...scope, branch: "method.b" } }), node => node.type === ui.MethodReadingWindow), undefined, "Changing the report's method closes the reader.");
  const alone = rows(hookHarness(ui.Editorial)({ context }))[0];
  assert.equal(alone.props.onReadSupport, undefined, "Without the project reader the row keeps its disclosure.");
  assert.match(ui.render(ui.IssueEntry, alone.props), /<summary>Context and sources<\/summary>/);
});

test("team work splits beside its brief, opens a reader without response wording, and keeps further work below", () => {
  const object_id = "issue.analyst.capped-minimizer";
  const reference = { ...question.generation_ref, phase: "P3", family: "analyst_audit", object_id, entry_pointer: "/issues/1" };
  const task = { issue_id: object_id, object_id, title: object_id, kind: "research_task", phase: "P3", target_phase: "P4", branch: "trunk", disposition: "partially_fixed", severity: "major", original_role: "data_analyst",
    statement: "Check whether the capped implementation reaches the theorem's minimizer.",
    likely_consequence: "The coverage claim depends on the capped implementation reaching the minimizer.",
    expected_consequence: "Phase 4 cannot yet separate optimisation error from coverage loss.",
    recommendation: "Run the capped and uncapped fits on the same seeds.",
    context_markdown: "The theorem assumes an exact minimizer of the penalized objective.",
    information_limits: "Only two seeds were compared.", generation_ref: reference, explanation_target: reference };
  const prepared = [], props = { ...input, phase: "P3", progressive: true, questionsOnly: false, issues: [task], onExplain: () => {}, onPrepare: issue => prepared.push(issue) };
  const render = hookHarness(ui.Issues);
  let card = render(props); const row = rows(card)[0];
  assert.equal(typeof row.props.onReadSupport, "function");
  const html = ui.render(ui.IssueEntry, row.props);
  const at = value => { const index = html.indexOf(value); assert.ok(index >= 0, value); return index; };
  assert.match(html, /class="research-card-layout has-rail has-actions"/);
  assert.match(html, /class="research-card-actions" role="group" aria-label="Team work actions"/);
  assert.match(html, /class="research-card-resources" role="group" aria-label="Team work supporting reading"/);
  assert.doesNotMatch(html, /<aside\b|aria-label="Question actions"|aria-label="Question supporting reading"/);
  const order = ["research-card-actions", "Discuss</button>", "Get the Lead&#x27;s advice", "research-card-account", "Why it matters<", "The coverage claim depends", "What this changes<", "Phase 4 cannot yet separate", "Analyst recommendation", "What remains unknown", "research-card-resources", "From Data analyst",
    "This work is intended for numerical evaluation.", "Team assessment: Partially fixed.", "Read background and sources", "Use the further work request below", "Prepare further work"].map(at);
  assert.deepEqual(order, [...order].sort((a, b) => a - b));
  assert.doesNotMatch(html, /<form|<textarea|<summary>Context and sources<|Your response|your answer|Researcher choice|Original title/i);
  assert.equal((html.match(/Team assessment:/g) || []).length, 1);
  assert.equal((html.match(/>Prepare further work<\/button>/g) || []).length, 1);
  const tree = hookHarness(ui.IssueEntry)(row.props);
  const layout = find(tree, node => node.type === ui.ResearchCardLayout);
  assert.equal(all(layout, node => text(node.props?.children) === "Prepare further work").length, 0, "The further-work request stays full width below the split.");
  const noActions = ui.render(ui.IssueEntry, { ...row.props, onExplain: undefined });
  assert.match(noActions, /class="research-card-layout has-rail"/);
  assert.doesNotMatch(noActions, /has-actions|research-card-actions|<form|<textarea|<aside\b/);
  assert.match(noActions, /aria-label="Team work supporting reading"/);
  assert.equal((noActions.match(/>Prepare further work<\/button>/g) || []).length, 1);

  row.props.onReadSupport(task, row.props.issue.statement, [], { isConnected: false });
  card = render(props);
  const snapshot = find(card, node => node.type === ui.MethodReadingWindow).props.snapshot;
  assert.equal(snapshot.title, "Background and sources");
  const reader = ui.render(ui.QuestionSupportDocument, snapshot.body.props);
  assert.match(reader, /Scientific importance: Major\./);
  assert.match(reader, /The theorem assumes an exact minimizer/);
  assert.match(reader, /Team assessment: Partially fixed\.<\/p>/);
  assert.match(reader, /Read the scientific context/);
  assert.doesNotMatch(reader, /Researcher choice|Researcher question|kept separately|Original title|issue\.analyst\.capped-minimizer/);

  const bare = { ...task, likely_consequence: undefined, expected_consequence: undefined, recommendation: undefined, information_limits: undefined, context_markdown: undefined, disposition: "open" };
  const bareHtml = ui.render(ui.IssueEntry, rows(hookHarness(ui.Issues)({ ...props, issues: [bare] }))[0].props);
  assert.doesNotMatch(bareHtml, /research-card-layout|<summary>Context and sources</, "Team work without a brief stays in one column.");
  assert.match(bareHtml, /View scientific sources/);
  assert.match(bareHtml, /1 scientific source/);

  const carried = hookHarness(ui.Issues)({ ...props, phase: "P4" });
  const carriedRow = rows(carried)[0];
  assert.equal(typeof carriedRow.props.onReadSupport, "function", "Scientific work carried forward gets the same reader.");
  const carriedHtml = ui.render(ui.IssueEntry, carriedRow.props);
  assert.match(carriedHtml, /Raised during [^<]+; applicable here\.<\/p>/);
  assert.doesNotMatch(carriedHtml, /Your response stays with the original question|This work is intended for/);

  const workCard = hookHarness(ui.Issues)({ ...input, questionsOnly: false, workOnly: true, embedded: true, issues: [{ ...question, kind: "research_task" }] });
  assert.equal(typeof rows(workCard)[0].props.onReadSupport, "function", "The P1 and P2 Team work card gets the reader.");
});
