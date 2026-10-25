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

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-dialogue-render-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Dialogue from '${src}/components/ResearcherDialogue.jsx'; import Issues from '${src}/components/IssuesCard.jsx'; import Pause from '${src}/components/ResearcherPause.jsx'; import Report, {TechnicalReportDocument} from '${src}/components/TechnicalReportReading.jsx'; import {WorkflowAdoptionReview} from '${src}/components/WorkflowAdoption.jsx'; const render=C=>p=>renderToStaticMarkup(React.createElement(C,p)); export const dialogue=render(Dialogue),issues=render(Issues),pause=render(Pause),report=render(Report),document=render(TechnicalReportDocument),workflowReview=WorkflowAdoptionReview;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const target = { kind: "project_context", project_id: "project.dialogue", context_revision: 2, brief_revision: 1, sha256: "a".repeat(64), phase: "P1", branch: "trunk" };
const context = { revision: 2, dialogue_target: target, items: [{ item_id: "context.collection", statement: "Visits occur when the patient feels worse.", origin: "researcher_reported", scope: { kind: "project" }, revision: 1, status: "confirmed" }], proposals: [] };
const ref = { branch: "method.mean", phase: "P5", family: "technical_report", generation_id: "report.1", sha256: "b".repeat(64) };
const offeredWorkflow = { version: "1.15.0", available_version: "1.16.0", upgrade_available: true, can_adopt: true, blocked_runs: [] };

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
  assert.match(html, /Save response/);
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
    for (const text of [["P1", "P2", "P4"].includes(phase) ? "Decisions to Discuss" : "Discuss your problem", "Data are optional", "I am not sure", "No data yet", "Save response", "Work in progress retains its captured context"]) assert.ok(html.includes(text), `${phase}: ${text}`);
    assert.match(html, /Type of understanding \(optional\)/); assert.match(html, /value="expectation"/);
    assert.match(html, /data-card-role="attention"/); assert.doesNotMatch(html, /Confirm understanding|Continue work/);
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
      assert.match(html, /Save response/);
    } else assert.match(html, /Project-context dialogue becomes available/);
    if (content.issues) {
      assert.match(html, /Recorded fidelity concern/);
      assert.match(html, /Investigate the boundary case/);
      assert.match(html, /Prepare further work/);
    } else if (content.attention) {
      assert.match(html, /Choose the next data setting/);
      assert.match(html, /Save instruction/);
    } else if (content.pause) {
      assert.match(html, /Saved evaluation pause/);
      assert.match(html, /Retained execution correction/);
    }
  }
});

test("authored question keeps consequence, checkability, uncertainty and answer separate", () => {
  const issue = { attention_id: "question.visits", phase: "P1", branch: "trunk", kind: "researcher_decision", title: "Why does a visit enter the data?", scope: { kind: "project" }, why_it_matters: "Visit selection changes the population interpretation.", checkability: "Collection records may describe the visit rule.", information_limits: "A diagnostic cannot establish an unobserved selection mechanism." };
  const html = render.dialogue({ projectId: target.project_id, phase: "P1", branch: "trunk", problemContext: context, attention: [issue], onDiscuss: noop });
  for (const text of [issue.title, "Practical consequence", issue.why_it_matters, "How this could be checked", issue.checkability, "What remains unknown", issue.information_limits, "Saved understanding", context.items[0].statement]) assert.ok(html.includes(text), text);
  assert.match(html, /Your instruction/); assert.doesNotMatch(html, /Your direction for further work/);
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
  assert.match(html, /2 questions need your response/);
  assert.match(html, /Is monthly clinical history available/);
  assert.match(html, /Which report target is useful/);
  assert.match(html, /Applies only to this exact model version.*Version 1/); assert.match(html, /Applies across models/);
  assert.match(html, /<summary>Your problem, data and saved understanding<\/summary>/);
  assert.equal((html.match(/<summary>Context and sources<\/summary>/g) || []).length, 2);
  assert.doesNotMatch(html, /Other questions and saved responses|Theorist&#x27;s exact support concern|Investigate this exact support rule/);
  const work = render.issues({ ...input, embedded: true, workOnly: true, title: "Team work" });
  assert.match(work, /Theorist&#x27;s exact support concern/); assert.match(work, /Read the scientific context/);
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
  for (const text of ["Work waiting for your response", "Which population matters?", "Why it matters", "Save response", "Continue work"]) assert.ok(html.includes(text), text);
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
  for (const text of ["Proposed understanding", "Research team", proposal.reason, "conflict with saved context"]) assert.ok(team.includes(text), text);
  assert.doesNotMatch(team, /<textarea|Reviewable interpretation/);
  assert.ok(html.indexOf(proposal.item.statement, responseStart) > responseStart);
  assert.match(html, /Review or edit the team&#x27;s interpretation/);
  assert.match(html, /Confirm understanding/);
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
  assert.match(report, /No technical report has been assembled/); assert.match(report, /Historical manuscripts/); assert.doesNotMatch(report, /Saved article prose/);
  const history = render.report({ documents: [document], initialTab: "manuscripts", onSource: noop });
  assert.match(history, /Conference paper/); assert.match(history, /Saved article prose/); assert.match(history, /not the current technical report/);
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
