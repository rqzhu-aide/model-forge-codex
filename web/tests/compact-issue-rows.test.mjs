import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { issueCardEntries, issueDisplayKind, issueDisplayState, issueUrgency } from "../src/phaseUiState.js";
import { issueLabel, issueSourceTarget, issueVersionKey } from "../src/phaseWorkflow.js";
import { populationChoice, studyFact } from "./fixtures/researcher-decisions.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-compact-issues-"));
const bundle = path.join(directory, "rows.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Issues, {IssueEntry} from '${src}/components/IssuesCard.jsx'; export {React, Issues, IssueEntry}; export {ResearcherDecision} from '${src}/components/ContextualRequests.jsx'; export {api} from '${src}/api.js'; export {saveConversationDraft} from '${src}/assumptionConversations.js'; export const entry = props => renderToStaticMarkup(<IssueEntry {...props}/>); export const issues = props => renderToStaticMarkup(<Issues {...props}/>);`, resolveDir: src, loader: "jsx" },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

const source = { kind: "phase_issue", branch: "trunk", phase: "P2", family: "attention_items", generation_id: "generation.current", sha256: "a".repeat(64), run_id: "run.current", package_id: "package.current", object_id: "question.collection", entry_pointer: "/attention_items/0" };
const question = { attention_id: source.object_id, phase: "P2", branch: "trunk", kind: "researcher_decision", disposition: "open", severity: "major", title: "How were observation times chosen?", question: "How were observation times chosen?", context_markdown: "The observation schedule determines which trajectories are available.", scope: { kind: "project" }, explanation_target: source, generation_ref: source };
const props = { projectId: "project.compact-rows", phase: "P2", branch: "trunk", compact: true, onExplain() {} };
const answerFor = (issue, note, revision) => ({ attention_id: issue.attention_id, attention: issue, question_ref: issue.explanation_target, scope: issue.scope, note, revision });
const rewardObjective = String.raw`\max_{\pi\in\Pi} J_R(\pi),\qquad J_R(\pi)=\mathbb{E}_{\pi}\!\left[\sum_{t=0}^{H-1}\gamma^t R_t\right]`;
const costReturn = String.raw`G_C=\sum_{t=0}^{H-1}\gamma^t C_t`;
const chanceConstraint = String.raw`\Pr_{\pi}(G_C>B)\le\delta`;
const meanConstraint = String.raw`\mathbb{E}_{\pi}[G_C]\le B`;
const mathematicalChoice = {
  ...populationChoice, question: "Which budget requirement matches the intended application?",
  context_markdown: `Both alternatives maximize the same expected discounted reward over the policy class.\n\n$$\n${rewardObjective}\n$$\n\nThe random discounted cost is\n\n$$\n${costReturn}\n$$\n\nHere $\\pi$ is the policy, $\\Pi$ is the admissible policy class, $H$ is the finite number of decision times, $\\gamma$ is the discount factor, and $R_t$ and $C_t$ are the reward and cost at time $t$. The expectation and probability use the trajectory distribution induced by the policy. The budget $B$ is measured in discounted cost units, and $\\delta$ is the permitted probability of exceeding it. The alternatives below change the budget requirement while preserving this reward objective.`,
  likely_consequence: "The choice determines whether the budget controls violation frequency or average discounted cost.",
  options: [
    { id: "chance", label: "Limit budget violation probability", consequence: `$$\n${chanceConstraint}\n$$\n\nControls how often discounted cost exceeds the budget; the size of an overrun is not bounded by this constraint.` },
    { id: "mean", label: "Limit average discounted cost", consequence: `$$\n${meanConstraint}\n$$\n\nControls average discounted cost; an individual trajectory may still exceed the budget.` },
  ],
};
const texAnnotations = html => [...html.matchAll(/<annotation encoding="application\/x-tex">([\s\S]*?)<\/annotation>/g)].map(([, value]) => value.replaceAll("&amp;", "&").replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&quot;", '"').replaceAll("&#x27;", "'").trim());
test("disclosure accessible name retains authored notation and citation labels without link targets", () => {
  const html = ui.entry({ ...props, issue: { ...question, question: "Should **$C_t$** use [cost units](paper:cost-units)?" } });
  assert.match(html, /aria-label="Should C_t use cost units\? Open question"/);
  assert.match(html, /<math[\s>]/, "Heading still exposes structured mathematics.");
  assert.doesNotMatch(html.match(/<summary\b[^>]*>/)[0], /paper:cost-units/);
});
const text = tree => Array.isArray(tree) ? tree.map(text).join("") : tree && typeof tree === "object" ? text(tree.props?.children) : String(tree ?? "");
function all(tree, predicate) {
  if (Array.isArray(tree)) return tree.flatMap(item => all(item, predicate));
  if (!tree || typeof tree !== "object") return [];
  return [...(predicate(tree) ? [tree] : []), ...all(tree.props?.children, predicate)];
}
const find = (tree, predicate) => all(tree, predicate)[0];
const button = (tree, label) => find(tree, node => (typeof node.props?.onClick === "function" || node.props?.type === "submit") && text(node.props.children) === label);
function hookHarness(Component) {
  const slots = []; let cursor = 0;
  const internals = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const dispatcher = {
    useState(initial) { const index = cursor++; if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
    useRef(initial) { const index = cursor++; return slots[index] ||= { current: initial }; },
    useId() { return `compact-row-${cursor++}`; },
    useEffect() { cursor++; }, useLayoutEffect() { cursor++; },
    useMemo(compute) { cursor++; return compute(); }, useCallback(callback) { cursor++; return callback; },
  };
  return value => { cursor = 0; const previous = internals.ReactCurrentDispatcher.current; internals.ReactCurrentDispatcher.current = dispatcher; try { return Component(value); } finally { internals.ReactCurrentDispatcher.current = previous; } };
}
async function withStorage(action) {
  const previous = globalThis.sessionStorage; const values = new Map();
  globalThis.sessionStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  try { await action(); } finally { if (previous === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = previous; }
}

test("researcher row urgency follows response state while team findings retain scientific severity", () => {
  for (const [severity, expected] of [["blocking", { state: "blocking", label: "Blocking" }], ["reassessment_required", { state: "reassess", label: "Reassess" }], ["major", { state: "attention", label: "Discuss" }], ["monitor", { state: "attention", label: "Discuss" }]]) {
    assert.deepEqual(issueUrgency({ ...question, severity }), { state: "attention", label: "Open question" });
    assert.deepEqual(issueUrgency({ ...question, kind: "scientific_issue", severity }), expected);
  }
  assert.deepEqual(issueUrgency({ ...question, severity: undefined, question: "URGENT: this is blocking" }), { state: "attention", label: "Open question" });
  assert.deepEqual(issueUrgency({ ...question, severity: "blocking", disposition: "resolved" }), { state: "recorded", label: "Closed question" });
  assert.deepEqual(issueUrgency({ ...question, severity: "blocking", researcher_answer: answerFor(question, "Keep the schedule unknown.", 1) }), { state: "saved", label: "Answer saved" });
  assert.equal(issueDisplayState({ ...question, kind: "scientific_issue", researcher_answer: answerFor(question, "Investigate this next.", 1) }).state, "science");
});

test("a row uses a closed native disclosure with title and textual status in its summary", () => {
  const html = ui.entry({ ...props, issue: { ...question, severity: "blocking" } });
  const opening = html.match(/^<details\b[^>]*>/)?.[0];
  assert.ok(opening, "The row itself must be a native disclosure.");
  assert.match(opening, /class="[^"]*phase-issue[^"]*issue-row/);
  assert.doesNotMatch(opening, /\bopen(?:=|\s|>)/);
  const summary = html.match(/<summary\b[^>]*>([\s\S]*?)<\/summary>/)?.[1];
  assert.ok(summary);
  assert.match(summary, /How were observation times chosen\?/);
  assert.match(summary, /Open question/);
  assert.match(summary, /<h3 class="issue-row-title">/);
  assert.doesNotMatch(summary, /data-urgency="blocking"|data-urgency="reassess"/);
  assert.doesNotMatch(summary, /<button|Discuss<\/button>|Lead suggestions/);
  assert.match(html.slice(html.indexOf("</summary>")), /Discuss|Lead suggestions/);
  assert.match(html, /The observation schedule determines which trajectories are available/);
  const render = hookHarness(ui.IssueEntry); const tree = render({ ...props, issue: question });
  assert.equal(tree.props["data-reading-anchor"], `issue:${issueVersionKey(question)}`);
  assert.ok(find(tree, node => node.props?.["data-reading-anchor"] === `issue-context:${issueVersionKey(question)}`));
});

test("a mathematical row label remains inline and its cited text does not become a nested link", () => {
  const title = "Does $N_i(t)$ depend on the [observation schedule](https://example.com/source)?";
  const html = ui.entry({ ...props, issue: { ...question, title, question: title } });
  const summary = html.match(/<summary\b[^>]*>([\s\S]*?)<\/summary>/)?.[1];
  assert.match(summary, /class="katex"/);
  assert.match(summary, /observation schedule/);
  assert.doesNotMatch(summary, /<a\b|<p\b|class="math-block"|katex-display|katex-error/);
});

test("researcher rows show one stable full question heading and retain a distinct authored title in details", () => {
  const item = { ...populationChoice, title: "Donor and cell weighting change the population target", question: "Should every donor receive the same weight when donors contribute different numbers of observed cells, conditional on the supplied sampling design?" };
  const before = structuredClone(item);
  for (const compact of [false, true]) {
    const html = ui.entry({ ...props, issue: item, compact });
    const summary = html.match(/<summary\b[^>]*>([\s\S]*?)<\/summary>/)[1];
    assert.match(summary, /<h3 class="issue-row-title">/);
    assert.ok(summary.includes(item.question));
    const visibleText = html.replace(/<[^>]+>/g, "");
    assert.equal(visibleText.split(item.question).length - 1, 1);
    assert.ok(visibleText.indexOf(item.title) > visibleText.indexOf("Context and sources"));
    assert.equal((html.match(/Researcher choice · Interpretation/g) || []).length, 1);
    assert.doesNotMatch(html, /role="heading"|title="Should every donor/);
  }
  const render = hookHarness(ui.IssueEntry);
  let tree = render({ ...props, issue: item });
  const label = find(tree, node => node.props?.text === item.question);
  tree.props.onToggle({ currentTarget: { open: true } }); tree = render({ ...props, issue: item });
  assert.equal(find(tree, node => node.props?.text === item.question).props.text, label.props.text);
  assert.equal(tree.props["data-reading-anchor"], `issue:${issueVersionKey(item)}`);
  assert.deepEqual(item, before);
});

test("standalone and embedded cards keep question and section headings below their card heading", () => {
  for (const compact of [false, true]) {
    for (const embedded of [false, true]) {
      const html = ui.issues({ ...props, issues: [populationChoice], questionsOnly: compact, embedded });
      assert.match(html, new RegExp(`<h${embedded ? 3 : 2}>Issues and decisions<`));
      assert.match(html, new RegExp(`<h${embedded ? 4 : 3} class="issue-row-title">`));
      assert.match(html, new RegExp(`<h${embedded ? 5 : 4}>What this choice changes<`));
    }
  }
});

test("all questions remain individual rows in authored order after a current instruction is saved", () => {
  const first = { ...question, attention_id: "question.first", title: "First question", question: "First question", explanation_target: { ...source, object_id: "question.first" } };
  const legacy = { ...question, attention_id: "question.legacy", title: "Legacy question", question: "Legacy question", kind: undefined, explanation_target: { ...source, object_id: "question.legacy" } };
  const last = { ...question, attention_id: "question.last", title: "Last question", question: "Last question", explanation_target: { ...source, object_id: "question.last" } };
  const render = hookHarness(ui.Issues); const input = { ...props, issues: [first, legacy, last], questionsOnly: true };
  const entries = tree => all(tree, node => node.type === ui.IssueEntry);
  let tree = render(input);
  assert.deepEqual(entries(tree).map(node => node.props.issue.attention_id), [first.attention_id, legacy.attention_id, last.attention_id]);
  entries(tree)[0].props.onAnswerSaved(answerFor(first, "Use the scheduled visits.", 1));
  tree = render(input);
  assert.deepEqual(entries(tree).map(node => node.props.issue.attention_id), [first.attention_id, legacy.attention_id, last.attention_id]);
  assert.equal(entries(tree)[0].props.issue.researcher_answer.note, "Use the scheduled visits.");
  const html = ui.issues({ ...input, answers: [answerFor(first, "Use the scheduled visits.", 1)] });
  assert.equal((html.match(/<details\b[^>]*class="[^"]*\bissue-row(?:\s|")/g) || []).length, 3);
  assert.doesNotMatch(html, /Saved responses and earlier decisions|data-reading-anchor="saved-decisions"/);
});

test("an authored scientific kind remains a source-linked finding rather than a researcher question", () => {
  const object_id = "issue.analyst.srpes.application-conditions";
  const statement = "Original enrollment offers, allocation, population, sufficient complete pre-offer inputs and reliable death follow-up remain unestablished. Current researcher answers explicitly retain scheduling and assay facts as unknown.";
  const findingSource = { ...source, phase: "P3", branch: "method.srpes", family: "analyst_audit", object_id, entry_pointer: "/issues/0" };
  const finding = { issue_id: "issue.projection", object_id, title: object_id, statement, kind: "nonblocking_application_conditions", severity: "major", phase: "P3", branch: "method.srpes", intended_audience: ["research_lead"], generation_ref: findingSource, explanation_target: findingSource };
  const explanations = [];
  const input = { ...props, phase: "P3", branch: "method.srpes", issues: [finding], progressive: true, onExplain: target => explanations.push(target) };
  const before = JSON.stringify(finding);
  assert.equal(issueDisplayKind(finding), "scientific_issue");
  assert.equal(issueDisplayState(finding).state, "science");
  const html = ui.issues(input);
  assert.match(html, /Scientific findings \(1\)/);
  assert.ok(html.indexOf(statement) > html.indexOf("Scientific findings (1)"));
  assert.match(html, /Read the scientific context/);
  assert.doesNotMatch(html, /<textarea|Your answer<\/label>|Save your answer|Edit your answer|I need your answer|Your information or preference is needed|data-issue-state="response"/);
  const summary = html.match(/class="issue-row-summary"[^>]*>([\s\S]*?)<\/summary>/)?.[1];
  assert.ok(summary?.includes("Original enrollment offers"));
  assert.ok(!summary?.includes(object_id));
  assert.equal(ui.issues({ ...input, questionsOnly: true }), "");
  assert.match(ui.issues({ ...input, workOnly: true }), /Original enrollment offers/);
  const target = issueSourceTarget(finding);
  assert.equal(target.label, statement);
  assert.equal(target.statement, statement);
  assert.equal(target.object_id, object_id);
  assert.equal(target.entry_pointer, "/issues/0");
  const tree = hookHarness(ui.IssueEntry)({ ...input, issue: finding });
  button(tree, "Discuss").props.onClick();
  assert.deepEqual(explanations, [target]);
  assert.equal(JSON.stringify(finding), before);
});

test("scientific findings retain saved instructions read-only and ignore cached answer drafts", async () => withStorage(async () => {
  const object_id = "issue.analyst.srpes.application-conditions";
  const findingSource = { ...source, phase: "P3", branch: "method.standardized-ridge-piecewise-exponential", family: "analyst_audit", object_id, entry_pointer: "/issues/0" };
  const finding = { issue_id: "issue.projection", object_id, title: object_id, statement: "Original enrollment offers, allocation, population, sufficient complete pre-offer inputs and reliable death follow-up remain unestablished. Current researcher answers explicitly retain scheduling and assay facts as unknown.", kind: "nonblocking_application_conditions", severity: "major", phase: "P3", branch: findingSource.branch, intended_audience: ["research_lead"], generation_ref: findingSource, explanation_target: findingSource };
  const answer = answerFor(finding, "Keep the actual allocation unknown.", 2);
  const key = `issue-response:${JSON.stringify([props.projectId, issueVersionKey(finding)])}`;
  ui.saveConversationDraft(key, { text: "An older unfinished answer draft.", origin: "researcher_reported" });
  const explanations = []; const preparations = [];
  const input = { ...props, phase: "P3", branch: findingSource.branch, issue: { ...finding, researcher_answer: answer }, onExplain: target => explanations.push(target), onPrepare: (issue, origin) => preparations.push([issue, origin]) };
  const html = ui.entry(input);
  assert.match(html, /Your saved answer/);
  assert.match(html, /Keep the actual allocation unknown\./);
  for (const label of ["Discuss", "Read the scientific context", "Prepare further work"]) assert.ok(html.includes(label));
  assert.doesNotMatch(html, /<textarea|<form|Your answer<\/label>|Edit your answer|Save your answer|An older unfinished answer draft/);
  const tree = hookHarness(ui.IssueEntry)(input);
  button(tree, "Discuss").props.onClick();
  assert.deepEqual(explanations[0].researcherNote, { note: answer.note, revision: 2 });
  assert.equal(explanations[0].researcherNoteDraft, undefined);
  const origin = {};
  button(tree, "Prepare further work").props.onClick({ currentTarget: origin });
  assert.equal(preparations[0][0], input.issue);
  assert.equal(preparations[0][1], origin);
  assert.equal(answer.note, "Keep the actual allocation unknown.");
}));

test("four P3 research tasks remain readable P4 team work with their exact sources and no response editor", () => {
  const statements = [
    "The identified causal RMST and the fixed-positive-penalty population contrast can differ.",
    "Full-estimator coverage and repeated all-success interval return remain unassessed.",
    "The conditional argmin theorem does not prove success for the capped implementation.",
    "The revised implications supply a future agenda, not a sealed 600-second protocol.",
  ];
  const tasks = statements.map((statement, index) => {
    const object_id = `issue.analyst.srpes.task-${index}`;
    const reference = { ...source, phase: "P3", branch: "method.srpes", family: "analyst_audit", object_id, entry_pointer: `/issues/${index + 1}` };
    return { issue_id: object_id, object_id, title: object_id, statement, phase: "P3", branch: "method.srpes", target_phase: "P4", kind: "research_task", generation_ref: reference, explanation_target: reference };
  });
  const input = { ...props, phase: "P4", branch: "method.srpes", issues: tasks, progressive: true };
  const before = JSON.stringify(tasks);
  const html = ui.issues(input);
  assert.match(html, /Related scientific work is linked below/);
  assert.match(html, /Scientific work carried forward/);
  assert.equal((html.match(/class="issue-row-summary"/g) || []).length, 4);
  assert.equal((html.match(/Read the scientific context/g) || []).length, 4);
  for (const statement of statements) assert.ok(html.includes(statement));
  assert.doesNotMatch(html, /<textarea|Your answer<\/label>|I need your answer|Your information or preference is needed|Their responses stay|Questions carried/);
  assert.equal(ui.issues({ ...input, questionsOnly: true }), "");
  const projected = issueCardEntries(input);
  assert.deepEqual(projected.related.map(issue => issue.explanation_target), tasks.map(issue => issue.explanation_target));
  assert.equal(JSON.stringify(tasks), before);
});

test("readable labels preserve authored precedence, mathematical prose and legacy questions", () => {
  assert.equal(issueLabel({ title: "Authored title", question: "Authored question", statement: "A statement" }), "Authored title");
  assert.equal(issueLabel({ title: "Authored title", question: "Authored question" }, true), "Authored question");
  const statement = "Does $N_i(t)$ determine [the observation process](https://example.com/source)?";
  const legacy = { ...question, kind: undefined, title: source.object_id, question: undefined, statement };
  assert.equal(issueDisplayKind(legacy), undefined);
  const html = ui.issues({ ...props, issues: [legacy], questionsOnly: true });
  assert.match(html, /class="katex"/);
  assert.match(html, /the observation process/);
  assert.doesNotMatch(html, /Scientific findings|I need your answer|katex-error/);
  assert.match(ui.issues({ ...props, issues: [question], questionsOnly: true }), /Open question/);
  assert.equal(issueLabel({ title: source.object_id, object_id: source.object_id }), "Research issue");
});

test("only the newest instruction for the exact question becomes current", () => {
  const previous = { ...question, explanation_target: { ...source, generation_id: "generation.earlier", sha256: "b".repeat(64) } };
  const oldQuestion = answerFor(previous, "Instruction for the earlier question.", 9);
  const first = answerFor(question, "Earlier edit for the current question.", 1);
  const current = answerFor(question, "Current instruction only.", 2);
  const projected = issueCardEntries({ ...props, issues: [question], answers: [oldQuestion, first, current] });
  assert.equal(projected.entries.length, 1);
  assert.equal(projected.entries[0].researcher_answer, current);
  assert.deepEqual(projected.earlierAnswers, [oldQuestion]);
  const html = ui.entry({ ...props, issue: projected.entries[0] });
  assert.match(html, /Current instruction only\./);
  assert.doesNotMatch(html, /Instruction for the earlier question|Earlier edit for the current question/);
  assert.equal((html.match(/Edit your answer/g) || []).length, 1);
});

test("earlier question history keeps one editable instruction and saves to its original source", async () => withStorage(async () => {
  const earlierSource = { ...source, generation_id: "generation.earlier", sha256: "b".repeat(64) };
  const earlier = { ...question, title: "Earlier collection question", question: "Earlier collection question", explanation_target: earlierSource, generation_ref: earlierSource };
  const first = answerFor({ ...earlier, explanation_target: Object.fromEntries(Object.entries(earlierSource).reverse()) }, "First historical instruction.", 1);
  const latest = answerFor(earlier, "Latest historical instruction.", 2);
  const previousApi = { ...ui.api }; const saves = []; const targets = [];
  ui.api.resolveAttention = async (...args) => { saves.push(args); return { answer: answerFor(earlier, args[2], 3) }; };
  try {
    const render = hookHarness(ui.Issues); const input = { ...props, issues: [question], answers: [first, latest], questionsOnly: true, onExplain: target => targets.push(target) };
    let tree = render(input);
    const history = find(tree, node => node.type === "details" && text(node.props.children).includes("Responses to earlier question versions"));
    assert.ok(history); assert.notEqual(history.props.open, true);
    assert.match(text(history), /Responses to earlier question versions \(1\)/);
    const rows = all(tree, node => node.type === ui.IssueEntry);
    assert.equal(rows.length, 2); assert.equal(rows[0].props.issue.researcher_answer, undefined);
    const historical = rows[1];
    assert.deepEqual(historical.props.issue.explanation_target, earlierSource);
    assert.deepEqual(historical.props.issue.generation_ref, earlierSource);
    assert.equal(historical.props.issue.researcher_answer, latest);
    const renderRow = hookHarness(ui.IssueEntry); let row = renderRow(historical.props);
    button(row, "Discuss").props.onClick(); assert.equal(targets[0].generation_id, earlierSource.generation_id);
    button(row, "Edit your answer").props.onClick(); row = renderRow(historical.props);
    find(row, node => node.type === "textarea").props.onChange({ target: { value: "Revised historical instruction." } }); row = renderRow(historical.props);
    await find(row, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(saves.length, 1); assert.deepEqual(saves[0][3].expected_source, earlierSource); assert.equal(saves[0][3].expected_revision, 2);
    tree = render(input);
    const updated = all(tree, node => node.type === ui.IssueEntry);
    assert.equal(updated[0].props.issue.researcher_answer, undefined);
    assert.equal(updated[1].props.issue.researcher_answer.note, "Revised historical instruction.");
    const html = ui.issues(input);
    assert.equal((html.match(/Edit your answer/g) || []).length, 1);
    assert.doesNotMatch(html, /First historical instruction/);
  } finally { Object.assign(ui.api, previousApi); }
}));

test("a historical answer's question reference supplies its missing original source", () => {
  const earlierSource = { ...source, generation_id: "generation.retained", sha256: "e".repeat(64) };
  const original = { ...question, explanation_target: undefined, generation_ref: undefined };
  const retained = { ...answerFor(original, "Retained original instruction.", 2), question_ref: earlierSource };
  const tree = hookHarness(ui.Issues)({ ...props, issues: [question], answers: [retained], questionsOnly: true });
  const rows = all(tree, node => node.type === ui.IssueEntry);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows[1].props.issue.explanation_target, earlierSource);
  assert.deepEqual(rows[1].props.issue.generation_ref, earlierSource);
  assert.equal(rows[1].props.issue.researcher_answer.note, retained.note);
});

test("editing an authored carried instruction starts a current-source answer before using its own revision", async () => withStorage(async () => {
  const successorSource = { ...source, generation_id: "generation.successor", sha256: "f".repeat(64) };
  const predecessor = answerFor(question, "Instruction carried from the predecessor.", 4);
  const successor = { ...question, explanation_target: successorSource, generation_ref: successorSource,
    answer_applicability_refs: [{ attention_id: question.attention_id, answer_revision: 4, question_ref: source, reason: "The study setting is unchanged." }] };
  const projected = issueCardEntries({ ...props, issues: [successor], answers: [predecessor] }).entries[0];
  assert.equal(projected.researcher_answer, predecessor);
  const previousApi = { ...ui.api }; const saves = [];
  ui.api.resolveAttention = async (...args) => { saves.push(args); return { answer: answerFor(successor, args[2], 4 + saves.length) }; };
  try {
    const render = hookHarness(ui.IssueEntry); const input = { ...props, issue: projected };
    for (const [expectedRevision, note] of [[0, "Instruction for this successor."], [5, "Updated successor instruction."]]) {
      let tree = render(input); button(tree, "Edit your answer").props.onClick(); tree = render(input);
      find(tree, node => node.type === "textarea").props.onChange({ target: { value: note } }); tree = render(input);
      await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
      assert.equal(saves.at(-1)[3].expected_revision, expectedRevision);
      assert.deepEqual(saves.at(-1)[3].expected_source, successorSource);
    }
    assert.equal(predecessor.note, "Instruction carried from the predecessor.");
    assert.equal(saves.length, 2);
  } finally { Object.assign(ui.api, previousApi); }
}));

test("model questions remain scoped to the exact selected model version", () => {
  const identity = { stable_id: "method.a", version: 2, definition_sha256: "c".repeat(64) };
  const scoped = { ...question, phase: "P3", branch: "method.a", scope: { kind: "model", branch: "method.a", model_ref: identity } };
  const other = { ...scoped, attention_id: "question.other", scope: { ...scoped.scope, model_ref: { ...identity, version: 1 } } };
  const input = { phase: "P3", branch: "method.a", modelRef: identity, issues: [scoped, other] };
  assert.deepEqual(issueCardEntries(input).entries.map(issue => issue.attention_id), [scoped.attention_id]);
  assert.equal(issueCardEntries({ ...input, modelRef: { ...identity, version: 3 } }).entries.length, 0);
  assert.equal(issueCardEntries({ ...input, branch: "method.b" }).entries.length, 0);
});

test("a cached instruction draft opens only its exact row and keeps one editor", async () => withStorage(async () => {
  const key = `issue-response:${JSON.stringify([props.projectId, issueVersionKey(question)])}`;
  ui.saveConversationDraft(key, { text: "Check who selected the visit times.", origin: "researcher_reported" });
  const render = hookHarness(ui.IssueEntry); const tree = render({ ...props, issue: question });
  assert.equal(tree.type, "details"); assert.equal(tree.props.open, true);
  const editors = all(tree, node => node.type === "textarea");
  assert.equal(editors.length, 1); assert.equal(editors[0].props.value, "Check who selected the visit times.");
  assert.match(text(tree), /You haven't saved an answer to this question yet\./);
  assert.doesNotMatch(text(tree), /Your latest saved answer|Save to use this update/);
  const revised = { ...question, explanation_target: { ...source, generation_id: "generation.revised", sha256: "d".repeat(64) } };
  assert.notEqual(hookHarness(ui.IssueEntry)({ ...props, issue: revised }).props.open, true);
}));

test("a restored edit draft acknowledges the applicable saved answer without claiming the draft is saved", async () => withStorage(async () => {
  const saved = answerFor(question, "The saved sampling account.", 3);
  const key = `issue-response:${JSON.stringify([props.projectId, issueVersionKey(question)])}`;
  ui.saveConversationDraft(key, { text: "A retained unsaved correction.", origin: "researcher_reported" });
  const tree = hookHarness(ui.IssueEntry)({ ...props, issue: { ...question, researcher_answer: saved } });
  assert.equal(tree.props.open, true);
  assert.equal(all(tree, node => node.type === "textarea").length, 1);
  assert.equal(find(tree, node => node.type === "textarea").props.value, "A retained unsaved correction.");
  assert.match(text(tree), /Save to use this update in future work\. Work already started keeps its original answer\./);
  assert.doesNotMatch(text(tree), /You haven't saved an answer/);
  assert.ok(button(tree, "Save answer"));
  assert.ok(button(tree, "Cancel edit"));
  assert.equal(saved.note, "The saved sampling account.");
}));

test("general and distinct answer consequences retain their final qualifiers before the response controls", () => {
  const general = "This changes the interpretation of the supplied comparison, only under the stated observational conditions.";
  const expected = "Equal donor weights target the donor population, provided that donor selection supports that population.";
  const answerSpecific = "Cell weights target the observed cell distribution, without identifying unobserved cells or a donor-level effect.";
  const item = { ...populationChoice, likely_consequence: undefined, why_it_matters: general, expected_consequence: expected, answer_consequences_markdown: answerSpecific };
  const before = structuredClone(item);
  const html = ui.entry({ ...props, issue: item });
  const sourcesAt = html.indexOf("Context and sources"), controlsAt = html.indexOf('<fieldset class="decision-options"');
  for (const value of [general, expected, answerSpecific]) {
    assert.equal(html.split(value).length - 1, 1);
    assert.ok(html.indexOf(value) < sourcesAt && html.indexOf(value) < controlsAt);
  }
  const repeated = ui.entry({ ...props, issue: { ...item, expected_consequence: general, answer_consequences_markdown: general } });
  assert.equal(repeated.split(general).length - 1, 1);
  assert.deepEqual(item, before);
});

test("editing an instruction replaces the current text against its saved revision without starting work", async () => withStorage(async () => {
  const previousApi = { ...ui.api }; const saves = []; const runs = []; const saved = answerFor(question, "Use only scheduled observations.", 3);
  Object.assign(ui.api, { resolveAttention: async (...args) => { saves.push(args); return { answer: answerFor(question, args[2], 4) }; }, startRun: async (...args) => { runs.push(args); throw new Error("Saving an instruction must not start work."); } });
  try {
    const render = hookHarness(ui.IssueEntry); const input = { ...props, issue: { ...question, researcher_answer: saved } };
    let tree = render(input); assert.equal(all(tree, node => node.type === "textarea").length, 0);
    button(tree, "Edit your answer").props.onClick(); tree = render(input);
    const editors = all(tree, node => node.type === "textarea");
    assert.equal(editors.length, 1); assert.equal(editors[0].props.value, saved.note);
    assert.ok(find(tree, node => node.type === "label" && text(node.props.children) === "Your answer"));
    editors[0].props.onChange({ target: { value: "  Keep event-triggered observations separate.  " } }); tree = render(input);
    assert.ok(button(tree, "Save answer"));
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(saves.length, 1); assert.equal(runs.length, 0);
    assert.equal(saves[0][2], "Keep event-triggered observations separate.");
    assert.equal(saves[0][3].expected_revision, 3); assert.deepEqual(saves[0][3].expected_source, source);
    tree = render(input); assert.equal(all(tree, node => node.type === "textarea").length, 0);
    assert.equal(all(tree, node => node.type === "section" && node.props.className?.split(" ").includes("issue-answer")).length, 1);
    assert.ok(button(tree, "Edit your answer"));
    button(tree, "Edit your answer").props.onClick(); tree = render(input);
    assert.equal(find(tree, node => node.type === "textarea").props.value, "Keep event-triggered observations separate.");
  } finally { Object.assign(ui.api, previousApi); }
}));

test("Edit focuses the instruction field and Cancel returns to its saved instruction button", async () => withStorage(async () => {
  const previousFrame = globalThis.requestAnimationFrame; const frames = []; const focused = [];
  globalThis.requestAnimationFrame = callback => { frames.push(callback); return frames.length; };
  try {
    const saved = answerFor(question, "Keep the collection mechanism unknown.", 2);
    const render = hookHarness(ui.IssueEntry); const input = { ...props, issue: { ...question, researcher_answer: saved } };
    let tree = render(input); tree.props.onToggle({ currentTarget: { open: true } }); tree = render(input);
    const savedSection = find(tree, node => node.type === "section" && node.props.className?.split(" ").includes("issue-answer"));
    button(tree, "Edit your answer").props.onClick();
    assert.equal(focused.length, 0, "Focus must wait until the editor has mounted.");
    savedSection.ref.current = null; tree = render(input);
    const editor = find(tree, node => node.type === "textarea");
    assert.ok(editor.ref, "The focus target must be the native textarea.");
    editor.ref.current = { focus: options => focused.push(["editor", options]) };
    assert.equal(frames.length, 1); frames.shift()();
    assert.deepEqual(focused, [["editor", { preventScroll: true }]]);
    editor.props.onChange({ target: { value: "An unsaved alternative." } }); tree = render(input);
    button(tree, "Cancel edit").props.onClick(); editor.ref.current = null; tree = render(input);
    const restored = find(tree, node => node.type === "section" && node.props.className?.split(" ").includes("issue-answer"));
    restored.ref.current = { querySelector: selector => { assert.equal(selector, "button"); return { focus: options => focused.push(["edit", options]) }; } };
    assert.equal(frames.length, 1); frames.shift()();
    assert.deepEqual(focused, [["editor", { preventScroll: true }], ["edit", { preventScroll: true }]]);
    assert.equal(tree.props.open, true);
    assert.ok(button(tree, "Edit your answer")); assert.equal(all(tree, node => node.type === "textarea").length, 0);
    button(tree, "Edit your answer").props.onClick(); tree = render(input);
    assert.equal(find(tree, node => node.type === "textarea").props.value, saved.note);
  } finally { if (previousFrame === undefined) delete globalThis.requestAnimationFrame; else globalThis.requestAnimationFrame = previousFrame; }
}));

test("authored choice briefs lead with the affected point, consequence and advice before supporting sources", () => {
  const html = ui.entry({ ...props, issue: populationChoice });
  assert.match(html, /Researcher choice · Interpretation/);
  assert.match(html, /class="katex"/);
  assert.ok(html.indexOf("What this choice changes") < html.indexOf("Why your answer matters"));
  assert.ok(html.indexOf("Lead recommendation") < html.indexOf("Context and sources"));
  assert.equal((html.match(/Neither choice establishes/g) || []).length, 1);
  assert.match(html, /<fieldset class="decision-options"/);
  assert.equal((html.match(/type="radio"/g) || []).length, 4);
  assert.doesNotMatch(html, /checked=""/);
  assert.match(html, /Not sure yet|Give a different response|Add a note \(optional\)|Save answer/);
});

test("a complete shared objective stays visible with distinct chance and mean budget alternatives", () => {
  assert.ok(mathematicalChoice.context_markdown.trim().split(/\s+/).length > 60);
  const before = structuredClone(mathematicalChoice);
  const html = ui.entry({ ...props, issue: mathematicalChoice });
  assert.match(html, /<section[^>]*><h4>What this choice changes<\/h4>/);
  assert.doesNotMatch(html, /<details[^>]*decision-rationale|katex-error/);
  const equations = texAnnotations(html);
  for (const equation of [rewardObjective, costReturn, chanceConstraint, meanConstraint]) assert.ok(equations.includes(equation), equation);
  assert.equal(equations.filter(equation => equation === rewardObjective).length, 1);
  assert.equal((html.match(/class="katex-display"/g) || []).length, 4);
  assert.match(html, /Controls how often discounted cost exceeds the budget/);
  assert.match(html, /Controls average discounted cost/);
  assert.doesNotMatch(html, /checked=""/);
  assert.deepEqual(mathematicalChoice, before);
});

test("raw published attention uses its exact generation reference for discussion and choice saves", async () => withStorage(async () => {
  const originalApi = { ...ui.api }; const saves = []; const discussions = [];
  ui.api.resolveAttention = async (...args) => { saves.push(args); return { answer: answerFor(populationChoice, "Canonical response.", 1) }; };
  try {
    const raw = { ...populationChoice, explanation_target: undefined };
    const render = hookHarness(ui.IssueEntry); const input = { ...props, projectId: "project.raw-published-choice", issue: raw, onExplain: target => discussions.push(target) };
    let tree = render(input); button(tree, "Discuss").props.onClick(); button(tree, "Get the Lead's advice").props.onClick();
    assert.deepEqual(discussions.map(target => target.entry_pointer), [populationChoice.generation_ref.entry_pointer, populationChoice.generation_ref.entry_pointer]);
    assert.equal(discussions[0].generation_id, populationChoice.generation_ref.generation_id);
    assert.equal(discussions[0].responsible_role, "research_lead"); assert.equal(discussions[1].assessmentPurpose, "issue_suggestions");
    find(tree, node => node.type === "input" && node.props.value === "option:survivors").props.onChange(); tree = render(input);
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(saves[0][3].expected_source.generation_id, populationChoice.generation_ref.generation_id);
    assert.equal(saves[0][3].expected_source.entry_pointer, populationChoice.generation_ref.entry_pointer);
    assert.equal(saves[0][3].expected_source.object_id, populationChoice.attention_id);
  } finally { Object.assign(ui.api, originalApi); }
}));

test("historical prose stays display-only and study facts never turn into options", () => {
  const historical = { ...question, options: ["Keep the existing target.", "Use a narrower population."], recommendation: "The original advice remains readable." };
  const html = ui.entry({ ...props, issue: historical });
  assert.match(html, /Keep the existing target|Use a narrower population|original advice/);
  assert.doesNotMatch(html, /type="radio"/);
  const factual = ui.entry({ ...props, issue: { ...studyFact, options: populationChoice.options, recommendation: "Do not make a preference out of a study fact." } });
  assert.match(factual, /Study information · Data applicability|Your answer|This remains unknown/);
  assert.doesNotMatch(factual, /type="radio"|Do not make a preference/);
});

test("legacy context remains whole inside supporting disclosure and retains recommendation attribution", () => {
  const context = `Original opening. ${"The full historical scientific context is retained. ".repeat(80)}Original ending.`;
  const html = ui.entry({ ...props, issue: { ...question, context_markdown: context, likely_consequence: "The concise effect remains visible.", recommendation: "The original reviewer advice.", original_role: "outside_reviewer" } });
  const body = html.slice(html.indexOf("issue-team-content")).replace(/<[^>]+>/g, "");
  assert.ok(body.indexOf("The concise effect remains visible.") < body.indexOf("Context and sources"));
  assert.ok(body.indexOf(context) > body.indexOf("Context and sources"));
  assert.equal((body.match(/Original opening/g) || []).length, 1);
  assert.match(html, /Reviewer recommendation/); assert.doesNotMatch(html, /Lead recommendation|Affected point/);
});

test("a choice and optional note save once for the exact question and restore as an editable selection", async () => withStorage(async () => {
  const originalApi = { ...ui.api }; const saves = []; const starts = [];
  ui.api.startRun = (...args) => starts.push(args);
  ui.api.resolveAttention = async (...args) => {
    saves.push(args); const selected = populationChoice.options.find(option => option.id === args[3].selection.option_id);
    return { answer: { ...answerFor(populationChoice, `Selected option: ${selected.label}\n\n${selected.consequence}`, saves.length), selection: { option_id: selected.id, label: selected.label, consequence: selected.consequence, note: args[3].selection.note || "" } } };
  };
  try {
    const input = { ...props, projectId: "project.choice-save", issue: populationChoice }; const render = hookHarness(ui.IssueEntry);
    let tree = render(input); assert.equal(button(tree, "Save answer").props.disabled, true);
    find(tree, node => node.type === "input" && node.props.value === "option:survivors").props.onChange(); tree = render(input);
    assert.equal(button(tree, "Save answer").props.disabled, false);
    find(tree, node => node.type === "textarea").props.onChange({ target: { value: "  Match the cohort-wide use case.  " } }); tree = render(input);
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(saves.length, 1); assert.equal(starts.length, 0);
    assert.equal(saves[0][2], "Match the cohort-wide use case.");
    assert.deepEqual(saves[0][3].selection, { option_id: "survivors", note: "Match the cohort-wide use case." });
    assert.deepEqual(saves[0][3].expected_source, populationChoice.explanation_target); assert.equal(saves[0][3].expected_revision, 0);
    tree = render(input); assert.equal(all(tree, node => node.type === "textarea").length, 0);
    button(tree, "Edit your answer").props.onClick(); tree = render(input);
    assert.equal(find(tree, node => node.type === "input" && node.props.value === "option:survivors").props.checked, true);
    assert.equal(find(tree, node => node.type === "textarea").props.value, "Match the cohort-wide use case.");
    find(tree, node => node.type === "input" && node.props.value === "option:observed").props.onChange(); tree = render(input);
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(saves[1][3].expected_revision, 1); assert.equal(saves[1][3].selection.option_id, "observed");
    assert.equal(starts.length, 0);
  } finally { Object.assign(ui.api, originalApi); }
}));

test("mathematical choices retain the saved formulation while editing only the optional researcher note", async () => withStorage(async () => {
  const originalApi = { ...ui.api }; const saves = []; const answers = [];
  ui.api.startRun = () => assert.fail("Saving or editing a choice must not start research.");
  ui.api.resolveAttention = async (...args) => {
    saves.push(args);
    const option = mathematicalChoice.options.find(item => item.id === args[3].selection.option_id);
    const note = args[3].selection.note || "";
    const answer = { ...answerFor(mathematicalChoice, `Selected option: ${option.label}\n\n${option.consequence}${note ? `\n\nYour note: ${note}` : ""}`, saves.length), selection: { option_id: option.id, label: option.label, consequence: option.consequence, note } };
    answers.push(answer); return { answer };
  };
  try {
    const input = { ...props, projectId: "project.mathematical-choice-save", issue: mathematicalChoice };
    const render = hookHarness(ui.IssueEntry);
    let tree = render(input);
    find(tree, node => node.type === "input" && node.props.value === "option:chance").props.onChange(); tree = render(input);
    find(tree, node => node.type === "textarea").props.onChange({ target: { value: "  Keep the declared budget and tolerance.  " } }); tree = render(input);
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.deepEqual(saves[0][3].selection, { option_id: "chance", note: "Keep the declared budget and tolerance." });
    assert.equal(answers[0].selection.consequence, mathematicalChoice.options[0].consequence);
    const savedHtml = ui.entry({ ...input, issue: { ...mathematicalChoice, researcher_answer: answers[0] } });
    assert.ok(texAnnotations(savedHtml).includes(chanceConstraint)); assert.doesNotMatch(savedHtml, /katex-error/);
    tree = render(input); button(tree, "Edit your answer").props.onClick(); tree = render(input);
    assert.equal(find(tree, node => node.type === "textarea").props.value, "Keep the declared budget and tolerance.");
    assert.equal(find(tree, node => node.type === "input" && node.props.value === "option:chance").props.checked, true);
    find(tree, node => node.type === "input" && node.props.value === "option:mean").props.onChange(); tree = render(input);
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.deepEqual(saves[1][3].selection, { option_id: "mean", note: "Keep the declared budget and tolerance." });
    assert.equal(saves[1][3].expected_revision, 1);
    assert.ok(answers[1].note.includes(meanConstraint)); assert.ok(!answers[1].note.includes(chanceConstraint));
    assert.equal(answers[1].note.split(meanConstraint).length - 1, 1);
    tree = render(input); button(tree, "Edit your answer").props.onClick(); tree = render(input);
    assert.equal(find(tree, node => node.type === "textarea").props.value, "Keep the declared budget and tolerance.");
  } finally { Object.assign(ui.api, originalApi); }
}));

test("unsaved choices survive remounts without saving, and uncertainty remains an unknown ordinary response", async () => withStorage(async () => {
  const originalApi = { ...ui.api }; const saves = [];
  ui.api.resolveAttention = async (...args) => { saves.push(args); return { answer: { ...answerFor(populationChoice, args[2], 1), origin: args[3].origin } }; };
  try {
    const input = { ...props, projectId: "project.choice-draft", issue: populationChoice };
    let render = hookHarness(ui.IssueEntry); let tree = render(input);
    find(tree, node => node.type === "input" && node.props.value === "option:observed").props.onChange();
    render = hookHarness(ui.IssueEntry); tree = render(input);
    assert.equal(tree.props.open, true); assert.equal(saves.length, 0);
    assert.equal(find(tree, node => node.type === "input" && node.props.value === "option:observed").props.checked, true);
    find(tree, node => node.type === "input" && node.props.value === "unknown").props.onChange(); tree = render(input);
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(saves[0][3].origin, "unknown"); assert.equal(saves[0][3].selection, undefined);
    assert.equal(saves[0][2], "This choice remains unresolved."); tree = render(input);
    assert.match(text(tree), /Still unknown/);
  } finally { Object.assign(ui.api, originalApi); }
}));

test("a custom response requires text and does not claim an authored selection", async () => withStorage(async () => {
  const originalApi = { ...ui.api }; const saves = [];
  ui.api.resolveAttention = async (...args) => { saves.push(args); return { answer: answerFor(populationChoice, args[2], 1) }; };
  try {
    const input = { ...props, projectId: "project.choice-custom", issue: populationChoice }; const render = hookHarness(ui.IssueEntry);
    let tree = render(input); find(tree, node => node.type === "input" && node.props.value === "custom").props.onChange(); tree = render(input);
    assert.equal(button(tree, "Save answer").props.disabled, true);
    find(tree, node => node.type === "textarea").props.onChange({ target: { value: "Predict only for the prespecified clinic population." } }); tree = render(input);
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(saves[0][3].selection, undefined); assert.equal(saves[0][3].origin, "researcher_reported");
  } finally { Object.assign(ui.api, originalApi); }
}));

test("the contextual response uses the same explicit choice and exact-source save", async () => withStorage(async () => {
  const originalApi = { ...ui.api }; const saves = []; const saved = [];
  ui.api.resolveAttention = async (...args) => { saves.push(args); return { answer: answerFor(populationChoice, "A canonical saved choice.", 1) }; };
  try {
    const render = hookHarness(ui.ResearcherDecision); const input = { item: populationChoice, projectId: "project.contextual-choice", branch: "trunk", number: 1, onSaved: answer => saved.push(answer) };
    let tree = render(input); assert.equal(all(tree, node => node.type === "input" && node.props.checked).length, 0);
    find(tree, node => node.type === "input" && node.props.value === "option:survivors").props.onChange(); tree = render(input);
    await find(tree, node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(saves.length, 1); assert.equal(saves[0][2], ""); assert.deepEqual(saves[0][3].selection, { option_id: "survivors" });
    assert.deepEqual(saves[0][3].expected_source, populationChoice.explanation_target); assert.equal(saved.length, 1);
  } finally { Object.assign(ui.api, originalApi); }
}));
