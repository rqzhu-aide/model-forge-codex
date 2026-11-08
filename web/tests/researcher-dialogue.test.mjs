import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { contextApplies } from "../src/researcherDialogue.js";
import { assumptionSource, conversationDraftKey, conversationsForTarget, isConversationTarget, isEarlierConversation, readConversationDraft, saveConversationDraft } from "../src/assumptionConversations.js";
import { activePhaseRun, scientificPhaseRuns } from "../src/phaseUiState.js";
import { readDecisionDraft, saveDecisionDraft, decisionAnswerPayload } from "../src/empiricalProgress.js";
import { adoptWorkflow } from "../src/workflowAdoption.js";
import { GOAL_POINTER } from "../src/phaseOneReader.js";
import { populationChoice } from "./fixtures/researcher-decisions.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-dialogue-render-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Dialogue from '${src}/components/ResearcherDialogue.jsx'; import Issues from '${src}/components/IssuesCard.jsx'; import Pause from '${src}/components/ResearcherPause.jsx'; import Report, {TechnicalReportDocument} from '${src}/components/TechnicalReportReading.jsx'; import {WorkflowAdoptionReview} from '${src}/components/WorkflowAdoption.jsx'; export {React, Dialogue}; export {api} from '${src}/api.js'; export {saveConversationDraft} from '${src}/assumptionConversations.js'; const render=C=>p=>renderToStaticMarkup(React.createElement(C,p)); export const dialogue=render(Dialogue),issues=render(Issues),pause=render(Pause),report=render(Report),document=render(TechnicalReportDocument),workflowReview=WorkflowAdoptionReview;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const target = { kind: "project_context", project_id: "project.dialogue", context_revision: 2, brief_revision: 1, sha256: "a".repeat(64), phase: "P1", branch: "trunk" };
const context = { revision: 2, dialogue_target: target, items: [{ item_id: "context.collection", statement: "Visits occur when the patient feels worse.", origin: "researcher_reported", scope: { kind: "project" }, revision: 1, status: "confirmed" }], proposals: [] };
const ref = { branch: "method.mean", phase: "P5", family: "technical_report", generation_id: "report.1", sha256: "b".repeat(64) };
const offeredWorkflow = { version: "1.15.0", available_version: "1.16.0", upgrade_available: true, can_adopt: true, blocked_runs: [] };
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const nodeText = tree => Array.isArray(tree) ? tree.map(nodeText).join("") : tree?.props ? nodeText(tree.props.children) : String(tree ?? "");
function hookHarness(Component) {
  const slots = []; let cursor = 0;
  const internals = render.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const dispatcher = {
    useState(initial) { const index = cursor++; if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
    useRef(initial) { const index = cursor++; return slots[index] ||= { current: initial }; },
    useId() { return `dialogue-${cursor++}`; }, useEffect() { cursor++; }, useCallback(callback) { cursor++; return callback; },
  };
  return props => { cursor = 0; const previous = internals.ReactCurrentDispatcher.current; internals.ReactCurrentDispatcher.current = dispatcher; try { return Component(props); } finally { internals.ReactCurrentDispatcher.current = previous; } };
}

test("goal correction labels distinguish exact current, replaced, and unavailable published sources on any branch", () => {
  const source = { branch: "trunk", phase: "P1", family: "research_basis", generation_id: "goal.one", sha256: "c".repeat(64), run_id: "run.goal", package_id: "package.goal", kind: "research_goal", entry_pointer: GOAL_POINTER };
  const item = { ...context.items[0], topic: "research_goal", source_refs: [source] };
  const problemContext = { ...context, items: [item] };
  const original = JSON.stringify(problemContext);
  for (const branch of ["trunk", "method.mean"]) {
    const props = { projectId: target.project_id, phase: "P3", branch, problemContext, onDiscuss: noop, onSource: noop };
    const current = render.dialogue({ ...props, goalReference: source });
    assert.match(current, /Research goal correction · current published goal/);
    const earlier = render.dialogue({ ...props, goalReference: { ...source, generation_id: "goal.two", sha256: "d".repeat(64) } });
    assert.match(earlier, /Research goal correction · earlier published goal/);
    const unavailable = render.dialogue(props);
    assert.match(unavailable, /Research goal correction · published goal status unavailable/);
    assert.doesNotMatch(unavailable, /current published goal|earlier published goal/);
    for (const html of [current, earlier, unavailable]) assert.match(html, /title="Research basis · goal\.one"/);
  }
  assert.equal(JSON.stringify(problemContext), original);
});

test("legacy dialogue offers a collapsed workflow review and blocks adoption while work is paused", () => {
  const props = { projectId: "project.legacy", phase: "P1", branch: "trunk", catalogPreview: offeredWorkflow };
  const html = render.dialogue(props);
  assert.match(html, /<details[^>]*data-reading-anchor="workflow-adoption"><summary>Review updated workflow/);
  assert.match(html, /Current workflow: 1\.15\.0\. Offered workflow: 1\.16\.0/);
  assert.match(html, /Adopt updated workflow/); assert.doesNotMatch(html, /data-reading-anchor="workflow-adoption"[^>]*open/);
  const blocked = render.dialogue({ ...props, catalogPreview: { ...offeredWorkflow, can_adopt: false, blocked_runs: [{ run_id: "run.paused", state: "awaiting_user" }] } });
  assert.match(blocked, /Finish or cancel active or paused work/); assert.match(blocked, /run\.paused/); assert.match(blocked, /Awaiting user/);
  assert.match(blocked, /<button(?=[^>]*disabled)(?=[^>]*data-action="continue")/);
  assert.doesNotMatch(render.dialogue({ ...props, catalogPreview: { ...offeredWorkflow, upgrade_available: false } }), /Review updated workflow|Adopt updated workflow/);
});

test("existing dialogue keeps a newer workflow reachable without losing current understanding", () => {
  const catalog = { version: "1.18.0", available_version: "1.19.0", upgrade_available: true, can_adopt: true, blocked_runs: [] };
  const props = { projectId: target.project_id, phase: "P2", branch: "trunk", problemContext: context, catalogPreview: catalog, onDiscuss: noop };
  const adoptionButton = (html) => {
    const matches = [...html.matchAll(/<button\b[^>]*>[\s\S]*?<\/button>/g)].map((match) => match[0]).filter((button) => button.includes("Adopt updated workflow"));
    assert.equal(matches.length, 1, "The offered update has one explicit adoption control.");
    return matches[0];
  };
  const html = render.dialogue(props);
  assert.match(html, /Current workflow: 1\.18\.0\. Offered workflow: 1\.19\.0/);
  assert.match(html, /data-reading-anchor="workflow-adoption"/);
  assert.doesNotMatch(adoptionButton(html), /\bdisabled(?:=|\s|>)/);
  assert.match(html, /Visits occur when the patient feels worse\./);
  assert.match(html, /Save your note/);
  assert.doesNotMatch(html, /Project-context dialogue becomes available when/);

  for (const state of ["running", "awaiting_user"]) {
    // A blocked run must disable the control even if can_adopt is stale.
    const blocked = render.dialogue({ ...props, activeWork: true, catalogPreview: { ...catalog, blocked_runs: [{ run_id: `run.${state}`, state }] } });
    assert.match(adoptionButton(blocked), /\bdisabled(?:=|\s|>)/, state);
    assert.ok(blocked.includes(`run.${state}`), state);
    assert.match(blocked, /Finish or cancel active or paused work/);
    assert.match(blocked, /Visits occur when the patient feels worse\./);
  }

  const unavailable = render.dialogue({ ...props, catalogPreview: { ...catalog, can_adopt: false } });
  assert.match(adoptionButton(unavailable), /\bdisabled(?:=|\s|>)/);
  const current = render.dialogue({ ...props, catalogPreview: { ...catalog, version: "1.19.0", upgrade_available: false } });
  assert.doesNotMatch(current, /data-reading-anchor="workflow-adoption"|Adopt updated workflow/);
  assert.match(current, /Visits occur when the patient feels worse\./);
});

test("workflow review adopts only on explicit click, locks repeated clicks, and refreshes after success", async () => {
  const previousFetch = globalThis.fetch; const requests = []; const busy = []; const errors = []; let saved = 0; let complete;
  globalThis.fetch = (url, options) => { requests.push({ url, options }); return new Promise((resolve) => { complete = resolve; }); };
  try {
    const lock = { current: false }; const props = { projectId: "project.legacy", catalog: offeredWorkflow, lock, onBusy: (value) => busy.push(value), onError: (value) => errors.push(value), onSaved: () => { saved++; } };
    const review = render.workflowReview({ catalog: offeredWorkflow, onAdopt: () => adoptWorkflow(props) });
    const button = review.props.children.find((child) => child?.props?.children === "Adopt updated workflow");
    assert.equal(button.props.disabled, false); assert.equal(requests.length, 0);
    const first = button.props.onClick(); await button.props.onClick();
    assert.equal(requests.length, 1); assert.equal(requests[0].url, "/api/v1/projects/project.legacy/catalog-upgrade"); assert.equal(requests[0].options.method, "POST");
    assert.equal(saved, 0); assert.equal(lock.current, true);
    complete(Response.json({ version: "1.16.0", previous_catalog: "catalog-history/1.15.0" })); await first;
    assert.equal(saved, 1); assert.equal(lock.current, false); assert.deepEqual(busy, [true, false]); assert.deepEqual(errors, [null]);
  } finally { globalThis.fetch = previousFetch; }
});

test("workflow adoption reports rejection, permits explicit retry, and never posts a blocked preview", async () => {
  const previousFetch = globalThis.fetch; let requests = 0; let saved = 0; const errors = [];
  globalThis.fetch = async () => { requests++; return requests === 1 ? Response.json({ detail: "A run became active before adoption." }, { status: 409 }) : Response.json({ version: "1.16.0" }); };
  try {
    const props = { projectId: "project.legacy", catalog: offeredWorkflow, lock: { current: false }, onBusy: noop, onError: (value) => errors.push(value), onSaved: () => { saved++; } };
    await adoptWorkflow({ ...props, catalog: { ...offeredWorkflow, can_adopt: false, blocked_runs: [{ run_id: "run.active", state: "running" }] } });
    assert.equal(requests, 0);
    const review = render.workflowReview({ catalog: offeredWorkflow, onAdopt: () => adoptWorkflow(props) });
    const button = review.props.children.find((child) => child?.props?.children === "Adopt updated workflow");
    await button.props.onClick(); assert.equal(requests, 1); assert.equal(saved, 0); assert.equal(props.lock.current, false); assert.equal(errors.at(-1), "A run became active before adoption.");
    await button.props.onClick(); assert.equal(requests, 2); assert.equal(saved, 1); assert.equal(errors.at(-1), null);
  } finally { globalThis.fetch = previousFetch; }
});

function adoptionFocusFixture(initialFocus = "adoption") {
  const listeners = new Set(); const focuses = []; const button = {}; const editor = {};
  const document = { body: {}, documentElement: {}, activeElement: null, addEventListener: (_, listener) => listeners.add(listener), removeEventListener: (_, listener) => listeners.delete(listener) };
  const section = { isConnected: true, focus: (options) => { focuses.push(options); document.activeElement = section; } };
  const review = { ownerDocument: document, contains: (element) => element === button, closest: (selector) => selector === ".phase-issues" ? section : null };
  document.activeElement = initialFocus === "adoption" ? button : editor;
  const focus = (element) => { document.activeElement = element; for (const listener of listeners) listener({ target: element }); };
  return { document, review, section, editor, listeners, focuses, focus };
}

test("successful workflow adoption hands active review focus to the retained dialogue without scrolling", async () => {
  const previousFetch = globalThis.fetch; let complete; const fixture = adoptionFocusFixture(); let saved = false;
  globalThis.fetch = () => new Promise((resolve) => { complete = resolve; });
  try {
    const props = { projectId: "project.legacy", catalog: offeredWorkflow, lock: { current: false }, review: fixture.review, onBusy: (busy) => { if (busy) fixture.focus(fixture.document.body); }, onError: noop, onSaved: () => { assert.equal(fixture.document.activeElement, fixture.section); saved = true; } };
    const reviewRef = { current: fixture.review };
    const tree = render.workflowReview({ catalog: offeredWorkflow, reviewRef, onAdopt: () => adoptWorkflow(props) });
    assert.equal(tree.ref, reviewRef);
    const action = tree.props.children.find((child) => child?.props?.children === "Adopt updated workflow").props.onClick();
    assert.equal(fixture.document.activeElement, fixture.document.body); assert.equal(fixture.listeners.size, 1);
    complete(Response.json({ version: "1.16.0" })); await action;
    assert.equal(saved, true); assert.deepEqual(fixture.focuses, [{ preventScroll: true }]); assert.equal(fixture.listeners.size, 0);
  } finally { globalThis.fetch = previousFetch; }
});

test("successful workflow adoption preserves focus moved elsewhere or originating outside its review", async () => {
  const previousFetch = globalThis.fetch;
  try {
    for (const scenario of ["moved_to_editor", "moved_then_removed", "started_outside"]) {
      const fixture = adoptionFocusFixture(scenario === "started_outside" ? "editor" : "adoption"); let complete; let saved = false;
      globalThis.fetch = () => new Promise((resolve) => { complete = resolve; });
      const action = adoptWorkflow({ projectId: "project.legacy", catalog: offeredWorkflow, lock: { current: false }, review: fixture.review, onBusy: noop, onError: noop, onSaved: () => { saved = true; } });
      fixture.focus(fixture.editor);
      if (scenario === "moved_then_removed") fixture.focus(fixture.document.body);
      const current = fixture.document.activeElement;
      complete(Response.json({ version: "1.16.0" })); await action;
      assert.equal(saved, true, scenario); assert.equal(fixture.document.activeElement, current, scenario); assert.deepEqual(fixture.focuses, [], scenario); assert.equal(fixture.listeners.size, 0, scenario);
    }
  } finally { globalThis.fetch = previousFetch; }
});

test("dialogue remains available in all phases before outputs and while work is active", () => {
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const html = render.dialogue({ projectId: target.project_id, phase, branch: "trunk", problemContext: { ...context, items: [] }, activeWork: true, onDiscuss: noop, onSaved: noop });
    for (const text of ["Decisions to Discuss", "Data are optional", "Not sure yet", "No data yet", "Save your note", "Work in progress retains its captured context"]) assert.ok(html.includes(text), `${phase}: ${text}`);
    assert.match(html, /What your note describes \(optional\)/); assert.match(html, /value="expectation"/);
    assert.match(html, /data-card-role="attention"/); assert.doesNotMatch(html, /Confirm interpretation|Continue work/);
  }
});

test("P4 keeps its decisions title with or without problem context and all existing content", () => {
  const common = { phase: "P4", branch: "method.mean", scope: { kind: "project" } };
  const contents = [
    {},
    { attention: [{ ...common, attention_id: "p4.question", kind: "researcher_decision", title: "Choose the next data setting" }] },
    { issues: [{ ...common, issue_id: "p4.finding", kind: "scientific_issue", title: "Recorded fidelity concern" }], attention: [{ ...common, attention_id: "p4.task", kind: "research_task", title: "Investigate the boundary case" }] },
    { pause: "Saved evaluation pause", activePause: true, corrections: "Retained execution correction", correctionCount: 1 },
  ];
  for (const problemContext of [undefined, context]) for (const content of contents) {
    const html = render.dialogue({ projectId: target.project_id, ...common, problemContext, onDiscuss: noop, onPrepare: noop, ...content });
    assert.match(html, /<h2>Decisions to Discuss<\/h2>/);
    assert.doesNotMatch(html, /<h2>Discuss your problem<\/h2>/);
    if (problemContext) {
      assert.match(html, /Visits occur when the patient feels worse\./);
      assert.match(html, /Save your note/);
    } else assert.match(html, /Project-context dialogue becomes available/);
    if (content.issues) {
      assert.match(html, /Recorded fidelity concern/);
      assert.match(html, /Investigate the boundary case/);
      assert.match(html, /Prepare further work/);
    } else if (content.attention) {
      assert.match(html, /Choose the next data setting/);
      assert.match(html, /Save answer/);
    } else if (content.pause) {
      assert.match(html, /Saved evaluation pause/);
      assert.match(html, /Retained execution correction/);
    }
  }
});

test("authored question keeps consequence, checkability, uncertainty and answer separate", () => {
  const issue = { attention_id: "question.visits", phase: "P1", branch: "trunk", kind: "researcher_decision", title: "Why does a visit enter the data?", scope: { kind: "project" }, why_it_matters: "Visit selection changes the population interpretation.", checkability: "Collection records may describe the visit rule.", information_limits: "A diagnostic cannot establish an unobserved selection mechanism." };
  const html = render.dialogue({ projectId: target.project_id, phase: "P1", branch: "trunk", problemContext: context, attention: [issue], onDiscuss: noop });
  for (const text of [issue.title, "Why your answer matters", issue.why_it_matters, "How this could be checked", issue.checkability, "What remains unknown", issue.information_limits, "Your saved input", context.items[0].statement]) assert.ok(html.includes(text), text);
  assert.match(html, /Your answer/); assert.doesNotMatch(html, /Your direction for further work/);
});

test("the opening decision line follows current actions and authoritative loading state", () => {
  const props = { projectId: target.project_id, phase: "P4", branch: "method.mean", problemContext: context, onDiscuss: noop };
  const task = { attention_id: "task.current", phase: "P4", branch: "method.mean", kind: "research_task", question: "Check the numerical boundary.", scope: { kind: "project" } };
  const complete = render.dialogue({ ...props, decisionDataState: "ready", attention: [task] });
  assert.match(complete, /No Phase 4 question needs your answer\./);
  assert.match(complete, /Work the team is carrying forward/);
  assert.doesNotMatch(complete, /Open scientific work remains for the team/);
  for (const state of ["unavailable", "partial"]) {
    const html = render.dialogue({ ...props, decisionDataState: state });
    assert.doesNotMatch(html, /No Phase 4 question needs your answer/);
    assert.match(html, state === "partial" ? /Decision information is incomplete/ : /Decision information is unavailable/);
  }
  const invitation = { ...task, attention_id: "question.current", kind: "researcher_decision" };
  const open = render.dialogue({ ...props, decisionDataState: "ready", attention: [invitation] });
  assert.match(open, />1 open question</); assert.doesNotMatch(open, /Work is paused|for your answer/);
  const pause = render.dialogue({ ...props, activePause: true, pause: "Pause editor" });
  assert.match(pause, /Work is paused\./); assert.doesNotMatch(pause, /for your answer/);
  const answeredPause = render.dialogue({ ...props, activePause: true, pause: "Continue work" });
  assert.match(answeredPause, /Work is paused\./); assert.doesNotMatch(answeredPause, /for your answer/);
  const refreshing = render.dialogue({ ...props, decisionDataState: "refreshing" });
  assert.match(refreshing, /Showing the last available decision information/);
  assert.match(refreshing, /The last available update had no open Phase 4 questions/);
  const failed = render.dialogue({ ...props, decisionDataState: "refresh-failed" });
  assert.match(failed, /Updates could not be loaded/); assert.doesNotMatch(failed, /No Phase 4 question needs your answer/);
  const noMethod = render.dialogue({ ...props, decisionScope: "unselected-method" });
  assert.match(noMethod, /Choose a method to see its questions/);
  const sharedOverview = render.dialogue({ ...props, phase: "P2", decisionDataState: "ready", decisionScope: "shared-overview" });
  assert.match(sharedOverview, /No open questions shared across methods\. Select a method to see its questions/);
});

test("the footer keeps saved input collapsed, preserves original sources and follows current controls", () => {
  const source = { kind: "phase_issue", branch: "trunk", phase: "P2", family: "attention_items", generation_id: "generation.recorded", run_id: "run.recorded", package_id: "package.recorded", sha256: "d".repeat(64), object_id: "question.goal", entry_pointer: "/items/0" };
  const issue = { attention_id: "question.goal", kind: "researcher_decision", phase: "P2", target_phase: "P1", branch: "trunk", scope: { kind: "project" }, question: "Which population should the result cover?", explanation_target: source };
  const answer = { attention_id: issue.attention_id, attention: issue, question_ref: source, note: "The prospective population is still unknown.", revision: 2, origin: "unknown", scope: issue.scope, context_ref: { item_id: "context.answer.goal", revision: 1 } };
  const copy = { ...context.items[0], item_id: "context.answer.goal", statement: answer.note, answer_refs: [{ kind: "researcher_answer", attention_id: issue.attention_id, question_ref: source, answer_revision: 2 }] };
  const goal = { ...context.items[0], item_id: "context.goal", statement: "Preserve $J(\\pi)=\\mathbb E[R]$.", topic: "research_goal", source_refs: [{ ...source, phase: "P1", kind: "research_goal" }] };
  const html = render.dialogue({ projectId: target.project_id, phase: "P4", branch: "method.mean", decisionDataState: "ready", answers: [answer], problemContext: { ...context, items: [copy, goal] }, onDiscuss: noop, onSource: noop, corrections: "Current correction controls" });
  assert.match(html, /<summary>Phase 1 · 1 answer, 1 goal correction<\/summary>/);
  assert.equal((html.match(/The prospective population is still unknown\./g) || []).length, 1);
  assert.match(html, /Saved · still unknown/);
  assert.match(html, /data-phase-input-origin="saved-input-review:/);
  assert.match(html, /Review at original question/);
  assert.match(html, /title="Attention items · generation\.recorded"/);
  assert.match(html, /class="katex/);
  assert.doesNotMatch(html, /class="saved-input-(?:group|item)"[^>]*\bopen=/);
  assert.ok(html.indexOf("Current correction controls") < html.indexOf("Your saved input"));
  assert.ok(html.indexOf("Your saved answer") < html.indexOf("Original question and sources"));
  assert.doesNotMatch(html, /Edit your answer|View the saved copy|What you told me/);
});

test("a retained answer interpretation is not counted as an actionable confirmation", () => {
  const issue = { attention_id: "question.saved", phase: "P1", branch: "trunk", kind: "researcher_decision", scope: { kind: "project" }, question: "Which target is useful?" };
  const answer = { attention_id: issue.attention_id, attention: issue, revision: 1, note: "A population mean.", scope: issue.scope, context_ref: { item_id: "context.mirror", revision: 1 } };
  const proposal = { amendment_id: "proposal.mirror", status: "pending", item: { item_id: "context.mirror", statement: answer.note, scope: issue.scope } };
  const html = render.dialogue({ projectId: target.project_id, phase: "P4", branch: "method.mean", decisionDataState: "ready", contextAnswers: [answer], problemContext: { ...context, items: [], proposals: [proposal] }, onDiscuss: noop });
  assert.match(html, /No Phase 4 question needs your answer\./);
  assert.match(html, /This earlier interpretation concerns a saved answer/);
  assert.doesNotMatch(html, /interpretation awaiting your review|Confirm interpretation/);
});

test("historical generic drafts retain separate anchors and never replace the current composer target", () => {
  const targets = [1, 2].map(value => ({ ...target, context_revision: 1, brief_revision: value }));
  const keys = targets.map(original => `problem-response:${conversationDraftKey(target.project_id, original)}`);
  try {
    keys.forEach((key, index) => render.saveConversationDraft(key, { text: `Earlier draft ${index + 1}.`, projectId: target.project_id, target: targets[index] }));
    const html = render.dialogue({ projectId: target.project_id, phase: "P4", branch: "method.mean", problemContext: context, onDiscuss: noop });
    assert.equal((html.match(/data-reading-anchor="researcher-dialogue"/g) || []).length, 1);
    assert.match(html, /Unsent responses to earlier context \(2\)/);
    assert.match(html, /Earlier draft 1\./); assert.match(html, /Earlier draft 2\./);
    const anchors = [...html.matchAll(/data-reading-anchor="(problem-draft:[^"]+)"/g)].map(match => match[1]);
    assert.equal(anchors.length, 2); assert.equal(new Set(anchors).size, 2);
    assert.ok(html.indexOf("Unsent responses") < html.indexOf("Your saved input"));
  } finally { keys.forEach(key => render.saveConversationDraft(key, null)); }
});

test("polling a changed saved note keeps its draft and original save revision", async () => {
  const projectId = "project.note-polling";
  const note = context.items[0];
  const props = { projectId, phase: "P4", branch: "method.mean", problemContext: context, onDiscuss: noop };
  const renderDialogue = hookHarness(render.Dialogue);
  const dialogue = renderDialogue(props);
  const footer = nodes(dialogue).find(node => node.props.footer).props.footer;
  const noteElement = nodes(footer.type(footer.props)).find(node => node.props.item === note);
  const renderNote = hookHarness(noteElement.type);
  const initial = renderNote(noteElement.props);
  nodes(initial).find(node => node.props.onClick && nodeText(node) === "Edit your note").props.onClick();
  const opened = renderNote(noteElement.props);
  const originalForm = nodes(opened).find(node => node.props.item === note);
  const renderForm = hookHarness(originalForm.type);
  let formTree = renderForm(originalForm.props);
  nodes(formTree).find(node => node.type === "textarea").props.onChange({ target: { value: "My unsaved correction." } });
  const polledDialogue = renderDialogue({ ...props, problemContext: { ...context, revision: 3, dialogue_target: { ...target, context_revision: 3 } } });
  assert.doesNotMatch(nodeText(nodes(polledDialogue).find(node => node.props.intro).props.intro), /Unsent responses to earlier context/, "The active note draft has one editor after polling.");
  const latest = renderNote({ ...noteElement.props, item: { ...note, revision: 2, statement: "A separately saved account." }, context: { ...context, revision: 3 }, target: { ...target, context_revision: 3 } });
  const retainedForm = nodes(latest).find(node => node.props.item === note);
  assert.equal(retainedForm.type, originalForm.type); assert.equal(retainedForm.key, originalForm.key);
  assert.equal(retainedForm.props.context.revision, 2); assert.equal(retainedForm.props.target.context_revision, 2);
  assert.match(nodeText(latest), /Your saved note changed while you were editing/);
  formTree = renderForm(retainedForm.props);
  assert.equal(nodes(formTree).find(node => node.type === "textarea").props.value, "My unsaved correction.");
  const originalSave = render.api.saveProblemContext;
  let payload;
  render.api.saveProblemContext = async (_, next) => { payload = next; throw new Error("The saved context changed."); };
  try {
    await nodes(formTree).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(payload.expected_revision, 2); assert.equal(payload.statement, "My unsaved correction.");
    formTree = renderForm(retainedForm.props);
    assert.equal(nodes(formTree).find(node => node.type === "textarea").props.value, "My unsaved correction.");
    assert.match(nodeText(formTree), /Your draft is retained/);
  } finally {
    render.api.saveProblemContext = originalSave;
    render.saveConversationDraft(`problem-response:${conversationDraftKey(projectId, retainedForm.props.target)}`, null);
  }
});

test("team context stays separate from researcher input across phases and retains source access", () => {
  const modelRef = { stable_id: "method.mean", version: 1, definition_sha256: "d".repeat(64) };
  const source = { branch: "method.mean", phase: "P3", family: "theory_record", generation_id: "generation.team", sha256: "c".repeat(64) };
  const teamItem = { ...context.items[0], item_id: "team.evidence", origin: "evidence_supported", statement: "The bound requires an independent sample.",
    scope: { kind: "model", branch: "method.mean", model_ref: modelRef }, source_refs: [source] };
  const accepted = { ...context.items[0], item_id: "team.accepted", statement: "The team interprets the target as a donor average." };
  const problemContext = { ...context, items: [context.items[0], teamItem, accepted], proposals: [
    { status: "confirmed", item: { ...accepted, status: "proposed" }, confirmed_item_revision: accepted.revision },
  ] };
  for (const phase of ["P1", "P2", "P3", "P4", "P5"]) {
    const html = render.dialogue({ projectId: target.project_id, phase, branch: "method.mean", modelRef, problemContext, onSource: noop, onDiscuss: noop });
    const team = html.slice(html.indexOf('class="recorded-context-footer"'), html.indexOf('class="saved-input-footer"'));
    const researcher = html.slice(html.indexOf('class="saved-input-footer"'));
    assert.match(team, /Research team context/);
    assert.match(team, /Research team account/);
    assert.match(team, /Evidence supported · This model only/);
    assert.match(team, /Team interpretation · confirmed by you · Across models/);
    assert.match(team, /title="Theory record · generation\.team"/);
    assert.match(team, /data-reading-anchor="problem-context:team\.evidence:1"/);
    assert.equal((team.match(/>Correct this account</g) || []).length, 2);
    assert.doesNotMatch(team, /Edit your note|contribution-surface|Saved · still unknown/);
    assert.match(researcher, /Visits occur when the patient feels worse/);
    assert.match(researcher, /Project notes · 1 note/);
    assert.doesNotMatch(researcher, /The bound requires|The team interprets/);
  }
});

test("a team account correction keeps its original scope, sources and draft while polling", async () => {
  const projectId = "project.team-correction";
  const source = { branch: "trunk", phase: "P1", family: "research_basis", generation_id: "generation.context", sha256: "d".repeat(64) };
  const item = { ...context.items[0], item_id: "team.correction", origin: "evidence_supported", source_refs: [source] };
  const renderDialogue = hookHarness(render.Dialogue);
  const dialogue = renderDialogue({ projectId, phase: "P4", branch: "method.mean", problemContext: { ...context, items: [item] }, onDiscuss: noop });
  const footer = nodes(dialogue).find(node => node.props.footer).props.footer;
  const noteElement = nodes(footer.type(footer.props)).find(node => node.props.item === item);
  const renderNote = hookHarness(noteElement.type);
  let noteTree = renderNote(noteElement.props);
  nodes(noteTree).find(node => node.props.onClick && nodeText(node) === "Correct this account").props.onClick();
  noteTree = renderNote(noteElement.props);
  const editor = nodes(noteTree).find(node => node.props.item === item);
  assert.equal(editor.props.correction, true);
  const renderForm = hookHarness(editor.type);
  let formTree = renderForm(editor.props);
  assert.match(nodeText(formTree), /Your correction to this account/);
  assert.match(nodeText(formTree), /Save records your correction as researcher input, with the original sources retained/);
  assert.ok(nodes(formTree).find(node => node.type === "label" && nodeText(node) === "Your correction"));
  assert.equal(nodes(formTree).find(node => nodeText(node) === "Save your correction").props.disabled, true, "Untouched team prose cannot be adopted as researcher input by saving the correction editor.");
  const save = render.api.saveProblemContext;
  render.api.saveProblemContext = async () => assert.fail("The unchanged team account must not be saved as researcher input.");
  try { await nodes(formTree).find(node => node.type === "form").props.onSubmit({ preventDefault() {} }); }
  finally { render.api.saveProblemContext = save; }
  nodes(formTree).find(node => node.type === "input" && node.props.type === "checkbox").props.onChange({ target: { checked: true } });
  formTree = renderForm(editor.props);
  assert.equal(nodes(formTree).find(node => nodeText(node) === "Save your correction").props.disabled, false, "An explicit unknown response is a researcher correction even when its words are unchanged.");
  nodes(formTree).find(node => node.type === "input" && node.props.type === "checkbox").props.onChange({ target: { checked: false } });
  formTree = renderForm(editor.props);
  assert.equal(nodes(formTree).find(node => nodeText(node) === "Save your correction").props.disabled, true, "Returning to the untouched baseline restores its team attribution.");
  nodes(formTree).find(node => node.type === "textarea").props.onChange({ target: { value: "My correction preserves the study's uncertainty." } });
  const polled = renderNote({ ...noteElement.props, item: { ...item, revision: 2, statement: "An updated team account." }, context: { ...context, revision: 3 } });
  assert.match(nodeText(polled), /This account changed while you were editing/);
  const retained = nodes(polled).find(node => node.props.item === item);
  formTree = renderForm(retained.props);
  assert.equal(nodes(formTree).find(node => node.type === "textarea").props.value, "My correction preserves the study's uncertainty.");
  assert.equal(nodes(formTree).find(node => nodeText(node) === "Save your correction").props.disabled, false);
  let payload;
  render.api.saveProblemContext = async (_, next) => { payload = next; };
  try {
    await nodes(formTree).find(node => node.type === "form").props.onSubmit({ preventDefault() {} });
    assert.equal(payload.origin, "researcher_reported");
    assert.equal(payload.expected_revision, context.revision);
    assert.deepEqual(payload.scope, item.scope);
    assert.deepEqual(payload.source_refs, item.source_refs);
  } finally {
    render.api.saveProblemContext = save;
    render.saveConversationDraft(`problem-response:${conversationDraftKey(projectId, retained.props.target)}`, null);
  }
});

test("dialogue presents typed decisions through the shared layout without mixing the answer into its rail", () => {
  for (const phase of ["P1", "P2", "P3", "P4"]) {
    const source = { ...populationChoice.generation_ref, phase };
    const issue = { ...populationChoice, phase, target_phase: phase, generation_ref: source, explanation_target: source };
    const before = JSON.stringify(issue);
    const html = render.dialogue({ projectId: target.project_id, phase, branch: "trunk", attention: [issue], onExplain: noop, onSource: noop });
    const split = html.indexOf('class="research-card-layout has-rail has-actions"');
    assert.ok(split >= 0, phase);
    const row = html.slice(split, html.indexOf('<div class="researcher-dialogue"', split) < 0 ? undefined : html.indexOf('<div class="researcher-dialogue"', split));
    const sourceTitle = phase === "P4" ? "View original request" : "View scientific sources";
    const order = ['class="research-card-actions"', '>Discuss</button>', 'class="research-card-account"', "Why this matters", 'class="research-card-resources"', "From Research lead", "Applies across models.", sourceTitle, '<form class="issue-instruction-editor'].map(value => {
      const index = row.indexOf(value); assert.ok(index >= 0, `${phase}: ${value}`); return index;
    });
    assert.deepEqual(order, [...order].sort((a, b) => a - b), phase);
    assert.equal((row.match(/<form\b/g) || []).length, 1, phase);
    assert.equal((row.match(/<textarea\b/g) || []).length, 1, phase);
    assert.match(row, /aria-label="Question supporting reading"/);
    assert.doesNotMatch(row, /<aside\b|issue-decision-layout|issue-team-split/);
    assert.equal(JSON.stringify(issue), before, phase);
  }
});

test("context scope cannot follow a stable branch into a different model version", () => {
  const identity = { stable_id: "method.mean", version: 1, definition_sha256: "c".repeat(64) };
  const scope = { kind: "model", branch: "method.mean", model_ref: identity };
  assert.equal(contextApplies(scope, "method.mean", identity), true);
  assert.equal(contextApplies(scope, "method.mean", { ...identity, version: 2 }), false);
  assert.equal(contextApplies(scope, "method.other", identity), false);
  assert.equal(contextApplies(scope, "method.mean", null), false);
  assert.equal(contextApplies({ kind: "project" }, "method.other", null), true);
});

test("actual dialogue wiring displays only questions for its exact model identity", () => {
  const identity = { stable_id: "method.mean", version: 1, definition_sha256: "c".repeat(64) };
  const question = { attention_id: "model.question", kind: "researcher_decision", title: "Does this exact candidate fit the visit process?", phase: "P2", branch: "trunk", scope: { kind: "model", branch: "method.mean", model_ref: identity } };
  const props = { projectId: target.project_id, phase: "P2", branch: "method.mean", methodId: identity.stable_id, problemContext: context, attention: [question], onDiscuss: noop };
  assert.match(render.dialogue({ ...props, modelRef: identity }), /Does this exact candidate fit the visit process/);
  assert.doesNotMatch(render.dialogue({ ...props, modelRef: { ...identity, version: 2 } }), /Does this exact candidate fit the visit process/);
});

test("published P2 dialogue separates independent findings and includes exact trunk-authored model work", () => {
  const identity = { stable_id: "method.trunk-reader", version: 1, definition_sha256: "e".repeat(64) };
  const source = { branch: "trunk", phase: "P2", family: "attention_items", generation_id: "attention.current", sha256: "f".repeat(64), run_id: "run.current", package_id: "package.current" };
  const scoped = { phase: "P2", branch: "trunk", scope: { kind: "model", branch: "trunk", model_ref: identity }, generation_ref: source };
  const own = { ...scoped, attention_id: "question.own", kind: "researcher_decision", question: "Is monthly clinical history available?" };
  const shared = { ...scoped, scope: { kind: "project" }, attention_id: "question.shared", kind: "researcher_decision", question: "Which report target is useful?" };
  const finding = { ...scoped, scope: undefined, affected_record_ids: [identity.stable_id], issue_id: "finding.own", kind: "scientific_issue", title: "Theorist's exact support concern", original_role: "theorist", generation_ref: { ...source, family: "theory_review" } };
  const task = { ...scoped, attention_id: "task.own", kind: "research_task", question: "Investigate this exact support rule." };
  const other = { ...own, attention_id: "question.other", question: "Other model question must stay hidden", scope: { ...own.scope, model_ref: { ...identity, stable_id: "method.other" } } };
  const previous = { ...own, attention_id: "question.old-version", question: "Old version question must stay hidden", scope: { ...own.scope, model_ref: { ...identity, version: 0 } } };
  const input = { projectId: target.project_id, phase: "P2", branch: identity.stable_id, methodId: identity.stable_id, modelRef: identity, problemContext: context, issues: [finding], attention: [own, shared, task, other, previous], onDiscuss: noop, onSource: noop };
  const before = JSON.stringify(input); const html = render.dialogue(input);
  assert.match(html, /2 open questions/);
  assert.match(html, /Is monthly clinical history available/);
  assert.match(html, /Which report target is useful/);
  assert.match(html, /Applies only to this exact model version.*Version 1/); assert.match(html, /Applies across models/);
  assert.match(html, /<summary>Add a note or ask a question<\/summary>/);
  assert.match(html, /<summary>Project notes · 1 note<\/summary>/);
  assert.doesNotMatch(html, /What you told me/);
  assert.equal((html.match(/<summary>Context and sources<\/summary>/g) || []).length, 2);
  assert.doesNotMatch(html, /Other questions and saved responses|Theorist&#x27;s exact support concern|Investigate this exact support rule/);
  const work = render.issues({ ...input, embedded: true, workOnly: true, title: "Team work" });
  assert.match(work, /Theorist&#x27;s exact support concern/);
  assert.equal((work.match(/View scientific sources/g) || []).length, 2, "Each team-work row opens its source in the reader.");
  assert.doesNotMatch(work, /<summary>Context and sources<\/summary>/);
  assert.match(work, /Investigate this exact support rule/);
  assert.doesNotMatch(work, /Is monthly clinical history available|Which report target is useful|Other model question must stay hidden|Old version question must stay hidden/);
  assert.doesNotMatch(html, /Other model question must stay hidden|Old version question must stay hidden/);
  assert.equal(JSON.stringify(input), before);
});

test("context discussions preserve earlier exact revisions across branches and have no invented generation", () => {
  const earlier = { assessment_id: "earlier", assessment_purpose: "project_context", target: { ...target, context_revision: 1, sha256: "d".repeat(64), branch: "method.other" } };
  assert.equal(isConversationTarget(target), true);
  assert.equal(isEarlierConversation(earlier, target), true);
  assert.deepEqual(conversationsForTarget([earlier], target), [earlier]);
  const source = assumptionSource(target); assert.equal(source.generation_id, undefined); assert.equal(source.run_id, undefined); assert.equal(source.context_revision, 2);
  assert.notEqual(conversationDraftKey(target.project_id, target), conversationDraftKey(target.project_id, earlier.target));
});

test("browser storage failure keeps conversation and paused-work drafts for their exact original target", () => {
  const previous = Object.getOwnPropertyDescriptor(globalThis, "sessionStorage");
  const local = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  Object.defineProperty(globalThis, "sessionStorage", { configurable: true, get() { throw new Error("blocked"); } });
  Object.defineProperty(globalThis, "localStorage", { configurable: true, get() { throw new Error("blocked"); } });
  try {
    const key = conversationDraftKey("storage.failure", target); const draft = { text: "Keep the uncertainty explicit.", idempotencyKey: "same-turn" };
    saveConversationDraft(key, draft); assert.deepEqual(readConversationDraft(key), draft);
    assert.equal(readConversationDraft(conversationDraftKey("storage.failure", { ...target, context_revision: 3 })), null);
    saveDecisionDraft("pause.exact.failure", { note: "No data yet.", base_revision: 0 });
    assert.deepEqual(readDecisionDraft("pause.exact.failure", null), { note: "No data yet.", base_revision: 0 });
    saveDecisionDraft("pause.exact.failure", null); saveConversationDraft(key, null);
  } finally { if (previous) Object.defineProperty(globalThis, "sessionStorage", previous); else delete globalThis.sessionStorage; if (local) Object.defineProperty(globalThis, "localStorage", local); else delete globalThis.localStorage; }
});

test("context dialogue does not claim the scientific phase lock", () => {
  const run = { run_id: "context.active", branch_id: "trunk", phase: "P1", mode: "p3.assessment", intent: "assessment", assessment_purpose: "project_context", state: "running" };
  assert.equal(activePhaseRun([run], "P1", "trunk"), null); assert.deepEqual(scientificPhaseRuns([run], "P1", "trunk"), []);
});

test("paused work separates saving from explicit continuation", () => {
  const html = render.pause({ projectId: target.project_id, run: { run_id: "run.waiting", state: "awaiting_user", researcher_pause: { pending_request: { request_id: "request.target", revision: 1, question: "Which population matters?", reason: "A changed target changes the authorized interpretation.", options: ["All patients", "Symptom-triggered visits"], scope: { kind: "project" } }, saved_answers: [] } }, onSaved: noop });
  for (const text of ["Work is paused", "Which population matters?", "Why it matters", "Save answer", "Continue work"]) assert.ok(html.includes(text), text);
  const teamStart = html.indexOf('<div class="team-context-band">');
  const responseStart = html.indexOf('<form class="contribution-surface"', teamStart);
  assert.ok(teamStart >= 0 && responseStart > teamStart, "Team context precedes the researcher's separate response area.");
  const team = html.slice(teamStart, responseStart);
  for (const text of ["Research team", "Research lead", "Which population matters?", "A changed target changes the authorized interpretation.", "All patients", "Symptom-triggered visits"]) assert.ok(team.includes(text), text);
  assert.doesNotMatch(team, /<textarea|Your response/);
  assert.match(html, /data-reading-anchor="researcher-pause:run.waiting:request.target:1"/);
  assert.match(html, /<button(?=[^>]*disabled)(?=[^>]*data-action="continue")/);
});

test("proposed understanding distinguishes the team's reason from the editable response", () => {
  const proposal = { amendment_id: "amendment.collection", status: "pending", reason: "The team interprets this as symptom-triggered collection.", conflicts_with: ["context.collection"], item: { statement: "Reviewable interpretation of the visit process.", scope: { kind: "project" } } };
  const problemContext = { ...context, proposals: [proposal] };
  const before = JSON.stringify(problemContext);
  const html = render.dialogue({ projectId: target.project_id, phase: "P1", branch: "trunk", problemContext, onDiscuss: noop, onSaved: noop });
  const teamStart = html.indexOf('<div class="team-context-band">');
  const responseStart = html.indexOf('<div class="field contribution-surface">', teamStart);
  assert.ok(teamStart >= 0 && responseStart > teamStart);
  const team = html.slice(teamStart, responseStart);
  for (const text of ["Please check my interpretation", "Research team", proposal.reason, "conflict with saved context"]) assert.ok(team.includes(text), text);
  assert.doesNotMatch(team, /<textarea|Reviewable interpretation/);
  assert.ok(html.indexOf(proposal.item.statement, responseStart) > responseStart);
  assert.match(html, /How I interpreted your input: review or correct it/);
  assert.match(html, /Confirm interpretation/);
  assert.equal(JSON.stringify(problemContext), before);
});

test("paused answers preserve uncertainty without widening their authored scope", () => {
  const request = { request_id: "request.collection", revision: 3, scope: { kind: "model" } };
  const candidate = decisionAnswerPayload(request, "I am not sure.", 1, { origin: "unknown" });
  assert.equal(candidate.origin, "unknown"); assert.equal(candidate.save_to_context, undefined);
  const shared = decisionAnswerPayload({ ...request, scope: { kind: "project" } }, "I am not sure.", 1, { origin: "unknown", contextRevision: 5 });
  assert.equal(shared.origin, "unknown"); assert.equal(shared.save_to_context, true); assert.equal(shared.context_expected_revision, 5);
});

test("paused questions expose authored sources without inventing record linkage", () => {
  const request = { request_id: "request.sources", revision: 1, question: "Which collection mechanism is plausible?", evidence_refs: [{ generation_ref: ref }], source_refs: [
    { generation_ref: { ...ref, phase: "P1", family: "problem", generation_id: "problem.collection" }, label: "Read the exact collection account" },
    { url: "https://example.org/collection-protocol", title: "Collection protocol" },
    "The researcher described symptom-triggered visits.",
    { kind: "problem_context", item_id: "context.collection", revision: 2 },
    { generation_id: "incomplete.source", description: "An incomplete retained reference." },
    { url: "javascript:alert(1)", title: "Unusable source address" },
  ] };
  const html = render.pause({ projectId: target.project_id, run: { run_id: "run.sources", researcher_pause: { pending_request: request, saved_answers: [] } }, onSource: noop });
  assert.match(html, /title="Technical report · report\.1"/);
  assert.match(html, /title="Problem · problem\.collection"/); assert.match(html, /Read the exact collection account/);
  assert.match(html, /href="https:\/\/example\.org\/collection-protocol"/); assert.match(html, /Collection protocol/);
  assert.match(html, /The researcher described symptom-triggered visits/); assert.match(html, /context\.collection/); assert.match(html, /Revision: 2/);
  assert.match(html, /An incomplete retained reference/); assert.match(html, /Unusable source address/);
  assert.doesNotMatch(html, /title="[^\"]*incomplete\.source"|href="javascript:/);
});

test("report reader renders mathematics and real offline exports with completion separate from review", () => {
  const document = { kind: "technical_report", title: "Repeated observation model", generation_ref: ref, body_md: "## Model\n\nUse $Y_{it}=\\mu+b_i+\\epsilon_{it}$.", completion: { status: "interim", missing_work: ["No retained numerical analysis exists for this exact model."] }, method_identity: { stable_id: "method.mean", version: 1 }, review_status: "not_independently_reviewed", portable_artifact_url: "/api/v1/report.1?view=portable" };
  const html = render.document({ document, onSource: noop });
  for (const text of ["Interim report", "Work still needed", document.completion.missing_work[0], "has not been independently reviewed", "report.1", "Download offline HTML", "Open HTML report", "class=\"katex"]) assert.ok(html.includes(text), text);
  assert.match(html, /view=portable&amp;download=1/); assert.doesNotMatch(html, /Complete report/);
  const changed = render.document({ document: { ...document, completion: { status: "complete", missing_work: [] }, review_status: "independently_reviewed", reviewed_report_ref: { ...ref, generation_id: "report.earlier" } } });
  assert.match(changed, /Complete report/); assert.match(changed, /Review concerns an earlier version/); assert.doesNotMatch(changed, /This version was independently reviewed/);
});

test("historical manuscripts never occupy the current technical-report slot", () => {
  const document = { kind: "manuscript", title: "Historical article", structured: { venue_length: "conference" }, generation_ref: { ...ref, family: "manuscript" }, body_md: "Saved article prose." };
  const report = render.report({ documents: [document], onSource: noop });
  assert.match(report, /No technical report has been assembled/); assert.doesNotMatch(report, /Saved article prose|Historical manuscripts|Manuscripts</);
  const evidence = render.report({ documents: [document], initialTab: "evidence", onSource: noop });
  assert.match(evidence, /<h3>Supporting documents<\/h3>/); assert.match(evidence, /class="p2-reading-label"><span>Historical article<\/span>/); assert.doesNotMatch(evidence, /Saved article prose/);
});

test("report figures and reading anchors resolve only through exact declared materials", () => {
  const document = { kind: "technical_report", generation_ref: ref, body_md: '<a id="numerical"></a>\n\n## Numerical analysis\n\n![Error in a synthetic mechanism](risk.svg)\n\n[Return to analysis](#numerical)', report_materials: [{ path: "risk.svg", artifact_url: "/api/retained-risk.svg", media_type: "image/svg+xml", source_verified: true }], context_change_notices: [{ item_id: "context.target", previous_revision: 1, current_revision: 2, status: "context_changed" }] };
  const html = render.document({ document });
  assert.match(html, /<img src="\/api\/retained-risk.svg" alt="Error in a synthetic mechanism"/);
  assert.match(html, /id="report-report.1-numerical"/); assert.match(html, /href="#report-report.1-numerical"/);
  assert.match(html, /applicability has not been reassessed/); assert.doesNotMatch(html, /<p class="note warn">The saved context changed/);
  const missing = render.document({ document: { ...document, report_materials: [] } });
  assert.match(missing, /exact retained figure is unavailable/); assert.doesNotMatch(missing, /<img/);
});
