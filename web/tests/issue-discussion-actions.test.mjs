import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { records as notationRecords, snapshots as notationSnapshots } from "./fixtures/shared-notation.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-issue-actions-"));
const bundle = path.join(directory, "actions.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `export {default as React} from 'react'; export {api} from '${src}/api.js'; export {IssueEntry} from '${src}/components/IssuesCard.jsx'; export {NotationContent} from '${src}/components/SharedNotation.jsx'; export {default as Conversations} from '${src}/components/AssumptionConversations.jsx'; export * from '${src}/assumptionConversations.js'; export {explanationRun} from '${src}/phaseWorkflow.js'; export {activePhaseRun} from '${src}/phaseUiState.js';`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

const source = { kind: "phase_issue", branch: "trunk", phase: "P2", family: "lead_proposal", generation_id: "proposal.current", sha256: "a".repeat(64), run_id: "run.proposal", package_id: "package.proposal", object_id: "question.collection", entry_pointer: "/attention_items/0" };
const issue = { attention_id: "question.collection", phase: "P2", branch: "trunk", kind: "researcher_decision", title: "How are observations collected?", question: "How are observations collected?", summary_markdown: "Selection changes the population interpretation.", explanation_target: source, generation_ref: source, responsible_role: "research_lead" };
const event = { preventDefault() {} };
const noop = () => {};

function find(tree, predicate) {
  if (Array.isArray(tree)) return tree.map(item => find(item, predicate)).find(Boolean);
  if (!tree || typeof tree !== "object") return null;
  return predicate(tree) ? tree : find(tree.props?.children, predicate);
}
const text = tree => Array.isArray(tree) ? tree.map(text).join("") : tree && typeof tree === "object" ? text(tree.props?.children) : String(tree ?? "");
const button = (tree, label) => find(tree, node => typeof node.props?.onClick === "function" && text(node.props.children) === label);
const form = tree => find(tree, node => node.type === "form");
const textarea = tree => find(tree, node => node.type === "textarea");

// Use the same hook-dispatch pattern as the project integration tests to call
// real action handlers, with state preserved between explicit render calls.
function hookHarness(Component, context = {}) {
  const slots = []; let cursor = 0;
  const internals = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const dispatcher = {
    useState(initial) {
      const index = cursor++;
      if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial;
      return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }];
    },
    useRef(initial) { const index = cursor++; return slots[index] ||= { current: initial }; },
    useContext() { cursor++; return context; },
    useId() { const index = cursor++; return `test-id-${index}`; },
    useEffect() { cursor++; }, useLayoutEffect() { cursor++; },
    useMemo(compute) { cursor++; return compute(); }, useCallback(callback) { cursor++; return callback; },
  };
  return props => {
    cursor = 0; const previous = internals.ReactCurrentDispatcher.current;
    internals.ReactCurrentDispatcher.current = dispatcher;
    try { return Component(props); } finally { internals.ReactCurrentDispatcher.current = previous; }
  };
}

test("a linked question exposes its exact owning route without creating an answer form", () => {
  const carried = { ...issue, target_phase: "P1", researcher_answer: { revision: 1, origin: "unknown", note: "The cost remains unknown." } };
  const routes = [];
  const tree = hookHarness(ui.IssueEntry)({ issue: carried, projectId: "project.linked", phase: "P2", branch: "trunk", readOnly: true, onNavigate: (...args) => routes.push(args) });
  assert.ok(!form(tree)); assert.ok(!textarea(tree));
  assert.ok(!button(tree, "Edit your answer"));
  assert.ok(find(tree, node => node.props?.text === carried.researcher_answer.note));
  const link = button(tree, "Go to Phase 1 - Define and Explore questions");
  assert.ok(link); link.props.onClick();
  assert.deepEqual(routes, [["P1", undefined, carried]]);
});

async function withMocks(action) {
  const originalApi = { ...ui.api }; const previousStorage = globalThis.sessionStorage;
  const values = new Map(); const starts = []; const messages = []; const saves = [];
  globalThis.sessionStorage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) };
  Object.assign(ui.api, {
    startRun: async (...args) => { starts.push(args); return { run_id: "run.suggestion", assessment_id: "conversation.suggestion", assessment_purpose: "issue_suggestions", state: "requested", responsible_role: "research_lead" }; },
    assessmentMessage: async (...args) => { messages.push(args); return { run_id: "run.followup", assessment_id: args[1], assessment_purpose: "issue_suggestions", state: "requested" }; },
    resolveAttention: async (...args) => { saves.push(args); return { answer: { note: args[2], revision: 3 } }; },
  });
  try { await action({ starts, messages, saves }); }
  finally { Object.assign(ui.api, originalApi); if (previousStorage === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = previousStorage; }
}

function questionForm(props) {
  const render = hookHarness(ui.Conversations);
  const tree = render({ projectId: "project.suggestions", onClose: noop, ...props });
  return find(tree, node => typeof node.type === "function" && node.type.name === "QuestionForm");
}

test("discussion and suggestions keep distinct histories and unsent drafts for the exact same question", () => {
  const ordinary = { ...source, assessmentPurpose: "model_dialogue" };
  const suggestions = { ...source, assessmentPurpose: "issue_suggestions" };
  const history = [
    { assessment_id: "ordinary", assessment_purpose: "model_dialogue", target: source },
    { assessment_id: "suggestions", assessment_purpose: "issue_suggestions", target: source },
    { assessment_id: "earlier-suggestions", assessment_purpose: "issue_suggestions", target: { ...source, generation_id: "proposal.earlier", sha256: "b".repeat(64) } },
    { assessment_id: "another-question", assessment_purpose: "issue_suggestions", target: { ...source, object_id: "question.other" } },
  ];
  assert.deepEqual(ui.conversationsForTarget(history, ordinary).map(item => item.assessment_id), ["ordinary"]);
  assert.deepEqual(ui.conversationsForTarget(history, suggestions).map(item => item.assessment_id), ["suggestions", "earlier-suggestions"]);
  assert.notEqual(ui.conversationDraftKey("project.modes", ordinary), ui.conversationDraftKey("project.modes", suggestions));
  assert.equal(ui.conversationPurpose(source, history[1]), "issue_suggestions");
  assert.equal(ui.defaultConversationQuestion(ordinary), "");
  assert.match(ui.defaultConversationQuestion(suggestions), /If it asks for a choice.*alternatives, their consequences/);
  assert.match(ui.defaultConversationQuestion(suggestions), /If it asks for a study fact.*what can remain unknown/);
  assert.match(ui.defaultConversationQuestion(suggestions), /Do not infer my preference or a missing study fact/);
  const run = { assessment_purpose: "issue_suggestions", branch_id: "trunk", phase: "P2", mode: "p3.assessment", intent: "assessment", state: "running" };
  assert.equal(ui.explanationRun(run), true);
  assert.equal(ui.activePhaseRun([run], "P2", "trunk"), null);
});

test("item actions retain the exact question, distinguish the unsaved note, and save against its answer revision", async () => withMocks(async ({ starts, saves }) => {
  const targets = []; const saved = { note: "The sample comes from participating clinics.", revision: 2 };
  const props = { issue: { ...issue, researcher_answer: saved }, projectId: "project.item-actions", phase: "P2", branch: "trunk", compact: true, onExplain: target => targets.push(target) };
  const render = hookHarness(ui.IssueEntry);
  button(render(props), "Edit your answer").props.onClick();
  textarea(render(props)).props.onChange({ target: { value: "  Clinics opt in; follow-up may be incomplete.  " } });
  const tree = render(props);
  button(tree, "Discuss").props.onClick(); button(tree, "Get the Lead's advice").props.onClick();
  assert.equal(starts.length, 0); assert.equal(saves.length, 0);
  assert.equal(targets.length, 2);
  for (const target of targets) {
    assert.deepEqual(ui.assumptionSource(target), source);
    assert.equal(target.researcherNote.note, saved.note); assert.equal(target.researcherNote.revision, 2);
    assert.deepEqual(target.researcherResponseDraft, { kind: "custom", note: "Clinics opt in; follow-up may be incomplete." });
  }
  assert.equal(targets[1].assessmentPurpose, "issue_suggestions");
  await form(tree).props.onSubmit(event);
  assert.equal(saves.length, 1); assert.equal(starts.length, 0);
  assert.equal(saves[0][1], issue.attention_id); assert.equal(saves[0][2], "Clinics opt in; follow-up may be incomplete.");
  assert.deepEqual(saves[0][3].expected_source, source); assert.equal(saves[0][3].expected_revision, 2);
  const after = render(props); button(after, "Get the Lead's advice").props.onClick();
  assert.equal(targets.at(-1).researcherNote.note, "Clinics opt in; follow-up may be incomplete.");
  assert.equal(targets.at(-1).researcherNote.revision, 3);
  assert.ok(!targets.at(-1).researcherNoteDraft);
  assert.ok(!targets.at(-1).researcherResponseDraft);
}));

test("Discuss and Lead advice carry the unsaved option through submission without saving the answer", async () => withMocks(async ({ starts, saves }) => {
  const options = [{ id: "donors", label: "Equal donor weights", consequence: "Each donor contributes equally." }, { id: "cells", label: "Equal cell weights", consequence: "Donors with more cells contribute more." }];
  for (const action of ["Discuss", "Get the Lead's advice"]) {
    const targets = [], projectId = `project.choice-${action}`;
    const saved = { note: "The population remains undecided.", origin: "unknown", revision: 2 };
    const props = { issue: { ...issue, response_kind: "choice", options, researcher_answer: saved }, projectId, phase: "P2", branch: "trunk", onExplain: target => targets.push(target) };
    const render = hookHarness(ui.IssueEntry);
    button(render(props), "Edit your answer").props.onClick();
    find(render(props), node => node.type === "input" && node.props.value === "option:cells").props.onChange();
    textarea(render(props)).props.onChange({ target: { value: "" } });
    button(render(props), action).props.onClick();
    const [target] = targets;
    assert.deepEqual(target.researcherResponseDraft, { kind: "choice", option_id: "cells", label: options[1].label, consequence: options[1].consequence, note: "" });
    assert.deepEqual(target.researcherNote, { note: saved.note, revision: 2 });
    assert.equal(saves.length, 0);
    const element = questionForm({ projectId, target }); const renderForm = hookHarness(element.type);
    let tree = renderForm(element.props);
    assert.match(text(tree), /Your unsaved draft/);
    assert.equal(find(tree, node => node.props?.text === "Equal cell weights\n\nDonors with more cells contribute more.")?.type.name, "ResearchDocument");
    if (action === "Discuss") {
      textarea(tree).props.onChange({ target: { value: "How does this change the target?" } });
      tree = renderForm(element.props);
    }
    await form(tree).props.onSubmit(event);
    const body = starts.at(-1)[1];
    assert.deepEqual(body.researcher_response_draft, { kind: "choice", option_id: "cells", note: "" });
    assert.deepEqual(body.target, source);
    assert.equal(body.researcher_note_draft, undefined);
    assert.equal(body.researcher_answer, undefined);
    assert.equal(saves.length, 0);
    assert.deepEqual(saved, { note: "The population remains undecided.", origin: "unknown", revision: 2 });
  }
}));

test("custom and unknown responses use structured unsaved context and preserve the answer editor", async () => withMocks(async ({ starts, saves }) => {
  const options = [{ id: "donors", label: "Equal donor weights", consequence: "Each donor contributes equally." }];
  for (const [value, note, kind] of [["custom", "Use a specified donor subgroup.", "custom"], ["unknown", "", "unknown"]]) {
    const targets = [], props = { issue: { ...issue, response_kind: "choice", options }, projectId: `project.draft-${kind}`, phase: "P2", branch: "trunk", onExplain: target => targets.push(target) };
    const render = hookHarness(ui.IssueEntry);
    find(render(props), node => node.type === "input" && node.props.value === value).props.onChange();
    if (note) textarea(render(props)).props.onChange({ target: { value: note } });
    button(render(props), "Get the Lead's advice").props.onClick();
    const [target] = targets;
    assert.deepEqual(target.researcherResponseDraft, { kind, note });
    const element = questionForm({ projectId: props.projectId, target });
    await form(hookHarness(element.type)(element.props)).props.onSubmit(event);
    assert.deepEqual(starts.at(-1)[1].researcher_response_draft, { kind, note });
    assert.equal(saves.length, 0);
    assert.equal(textarea(render(props)).props.value, note);
    assert.equal(find(render(props), node => node.type === "input" && node.props.value === value).props.checked, true);
  }
}));

test("suggestions show an editable request and submit the note as separate context only after explicit submission", async () => withMocks(async ({ starts }) => {
  const accepted = [];
  const target = { ...source, assessmentPurpose: "issue_suggestions", researcherNoteDraft: "I cannot yet describe the sampling mechanism.", researcherNote: { note: "No data yet.", revision: 2 }, label: issue.title };
  const element = questionForm({ target, onStarted: run => accepted.push(run) });
  assert.ok(element);
  const render = hookHarness(element.type); const tree = render(element.props);
  assert.equal(starts.length, 0);
  assert.equal(textarea(tree).props.value, ui.defaultConversationQuestion(target));
  assert.notEqual(textarea(tree).props.value, target.researcherNoteDraft);
  await form(tree).props.onSubmit(event);
  assert.equal(starts.length, 1); assert.equal(accepted.length, 1);
  const [projectId, body] = starts[0];
  assert.equal(projectId, "project.suggestions"); assert.equal(body.intent, "assessment");
  assert.equal(body.assessment_purpose, "issue_suggestions"); assert.deepEqual(body.target, source);
  assert.equal(body.instructions, ui.defaultConversationQuestion(target));
  assert.equal(body.researcher_note_draft, target.researcherNoteDraft);
  assert.equal(Object.hasOwn(body, "researcherNote"), false);
  assert.ok(body.idempotency_key);
}));

test("ordinary discussion keeps the note separate and requires the researcher's question", async () => withMocks(async ({ starts }) => {
  const target = { ...source, researcherNoteDraft: "We may recruit from two clinics." };
  const element = questionForm({ projectId: "project.ordinary", target }); const render = hookHarness(element.type);
  let tree = render(element.props);
  assert.equal(textarea(tree).props.value, "");
  await form(tree).props.onSubmit(event); assert.equal(starts.length, 0);
  textarea(tree).props.onChange({ target: { value: "Why does clinic recruitment matter here?" } });
  tree = render(element.props); await form(tree).props.onSubmit(event);
  assert.equal(starts.length, 1); assert.equal(starts[0][1].assessment_purpose, "issue_explanation");
  assert.equal(starts[0][1].instructions, "Why does clinic recruitment matter here?");
  assert.equal(starts[0][1].researcher_note_draft, target.researcherNoteDraft);
}));

test("Notation Explain reaches the actual discussion form and submits its complete exact target", async () => withMocks(async ({ starts, saves }) => {
  let selected;
  const context = { projectId: "project.notation-action", onDiscuss: target => { selected = target; } };
  const content = hookHarness(ui.NotationContent, context)({ record: notationRecords.P4 });
  const rows = find(content, node => node.type?.name === "NotationRows" && node.props.entries.some(entry => entry.entry_id === "bandwidth"));
  assert.ok(rows);
  const row = hookHarness(rows.type, context)(rows.props);
  button(row, "Explain").props.onClick();
  assert.equal(ui.isConversationTarget(selected), true);
  assert.equal(selected.responsible_role, "research_lead");
  assert.match(selected.statement, /evaluation-local bandwidth/);
  const element = questionForm({ projectId: context.projectId, target: selected });
  assert.ok(element, "The real conversation must accept the Notation action's target.");
  const render = hookHarness(element.type);
  let tree = render(element.props);
  assert.equal(starts.length, 0);
  textarea(tree).props.onChange({ target: { value: "What does this bandwidth control?" } });
  tree = render(element.props); await form(tree).props.onSubmit(event);
  assert.equal(starts.length, 1);
  const [projectId, body] = starts[0];
  assert.equal(projectId, context.projectId);
  assert.equal(body.assessment_purpose, "model_dialogue");
  assert.equal(body.intent, "assessment");
  assert.equal(body.phase, "P4");
  assert.deepEqual(body.target, ui.assumptionSource(selected));
  assert.equal(body.target.snapshot_sha256, notationSnapshots.P4.snapshot_sha256);
  assert.equal(body.target.entry_id, "bandwidth");
  assert.equal(body.target.object_id, "bandwidth");
  assert.equal(body.target.generation_id, notationRecords.P4.generation_ref.generation_id);
  assert.equal(body.target.sha256, notationRecords.P4.generation_ref.sha256);
  assert.equal(body.instructions, "What does this bandwidth control?");
  assert.equal(saves.length, 0);
}));

test("a selected saved suggestions conversation preserves its purpose and original context on follow-up", async () => withMocks(async ({ starts, messages }) => {
  const conversation = { assessment_id: "conversation.saved-suggestions", assessment_purpose: "issue_suggestions", target: source, created_at: "2026-10-15T10:00:00Z", turns: [{ run_id: "run.original", state: "assessed", instructions: "Suggest a direction.", assessment_markdown: "Report what remains unknown." }] };
  const target = { ...source, assessmentPurpose: "issue_suggestions", conversationId: conversation.assessment_id, researcherNoteDraft: "This is a later unsaved edit." };
  const element = questionForm({ target, conversations: [conversation] }); assert.equal(element.props.conversation.assessment_id, conversation.assessment_id);
  assert.equal(ui.conversationPurpose(element.props.target, element.props.conversation), "issue_suggestions");
  const render = hookHarness(element.type); let tree = render(element.props);
  assert.equal(textarea(tree).props.value, "");
  textarea(tree).props.onChange({ target: { value: "What would change your recommendation?" } });
  tree = render(element.props); await form(tree).props.onSubmit(event);
  assert.equal(starts.length, 0); assert.equal(messages.length, 1);
  assert.equal(messages[0][1], conversation.assessment_id);
  assert.equal(messages[0][2].instructions, "What would change your recommendation?");
  assert.equal(Object.hasOwn(messages[0][2], "researcher_note_draft"), false);
}));

test("an accepted suggestion immediately retains its note, Lead identity and pending state", async () => withMocks(async ({ starts, messages }) => {
  const target = { ...source, assessmentPurpose: "issue_suggestions", researcherNote: { note: "Recruitment varies by clinic.", revision: 2 }, researcherNoteDraft: "The collection process is not settled." };
  const props = { projectId: "project.pending-suggestions", target, onClose: noop };
  const renderDialog = hookHarness(ui.Conversations);
  const first = find(renderDialog(props), node => typeof node.type === "function" && node.type.name === "QuestionForm");
  await form(hookHarness(first.type)(first.props)).props.onSubmit(event);
  assert.equal(starts.length, 1);
  const pending = find(renderDialog(props), node => typeof node.type === "function" && node.type.name === "QuestionForm");
  assert.equal(pending.props.pending, true);
  assert.equal(pending.props.conversation.assessment_purpose, "issue_suggestions");
  assert.equal(pending.props.conversation.responsible_role, "research_lead");
  assert.deepEqual(pending.props.conversation.researcher_answer, target.researcherNote);
  assert.equal(pending.props.conversation.researcher_note_draft, target.researcherNoteDraft);
  const renderPending = hookHarness(pending.type); let tree = renderPending(pending.props);
  textarea(tree).props.onChange({ target: { value: "Please also consider incomplete follow-up." } });
  tree = renderPending(pending.props); await form(tree).props.onSubmit(event);
  assert.equal(messages.length, 0); assert.equal(starts.length, 1);
  assert.equal(textarea(tree).props.value, "Please also consider incomplete follow-up.");
}));

test("a structured draft stays separate from the saved answer in pending and retained conversation context", async () => withMocks(async ({ starts, messages, saves }) => {
  const response = { kind: "choice", option_id: "cells", label: "Equal cell weights", consequence: "Donors with more cells contribute more.", note: "Consider unequal sampling." };
  const target = { ...source, assessmentPurpose: "issue_suggestions", researcherNote: { note: "Saved donor weighting.", revision: 2 }, researcherResponseDraft: response };
  const props = { projectId: "project.pending-choice", target, onClose: noop };
  const renderDialog = hookHarness(ui.Conversations);
  const first = find(renderDialog(props), node => typeof node.type === "function" && node.type.name === "QuestionForm");
  await form(hookHarness(first.type)(first.props)).props.onSubmit(event);
  const pending = find(renderDialog(props), node => typeof node.type === "function" && node.type.name === "QuestionForm");
  assert.equal(pending.props.pending, true);
  assert.deepEqual(pending.props.conversation.researcher_response_draft, response);
  assert.deepEqual(pending.props.conversation.researcher_answer, target.researcherNote);
  const retained = { ...pending.props.conversation, turns: [{ run_id: "run.suggestion", state: "assessed", instructions: "Compare the choices." }] };
  const reopened = questionForm({ ...props, target: { ...target, conversationId: retained.assessment_id, researcherResponseDraft: { kind: "unknown", note: "A later edit." } }, conversations: [retained] });
  const renderFollowup = hookHarness(reopened.type); let tree = renderFollowup(reopened.props);
  const context = find(tree, node => node.type === "details" && node.props.className.includes("conversation-note-context"));
  assert.match(text(context), /unsaved draft/);
  assert.equal(find(context, node => node.props?.text === "Equal cell weights\n\nDonors with more cells contribute more.\n\nConsider unequal sampling.")?.type.name, "ResearchDocument");
  assert.ok(!find(context, node => node.props?.text === "A later edit."));
  textarea(tree).props.onChange({ target: { value: "Which sampling assumption changes that comparison?" } });
  tree = renderFollowup(reopened.props); await form(tree).props.onSubmit(event);
  assert.equal(starts.length, 1); assert.equal(messages.length, 1); assert.equal(saves.length, 0);
  assert.equal(messages[0][2].researcher_response_draft, undefined);
}));

test("an uncertain structured submission keeps its original draft and identity when the editor changes later", async () => withMocks(async ({ starts }) => {
  ui.api.startRun = async (...args) => { starts.push(args); throw new Error("Connection lost."); };
  const response = { kind: "unknown", note: "The intended population is undecided." };
  const target = { ...source, assessmentPurpose: "issue_suggestions", researcherResponseDraft: response };
  const element = questionForm({ projectId: "project.uncertain-choice", target });
  await form(hookHarness(element.type)(element.props)).props.onSubmit(event);
  const reopened = questionForm({ projectId: "project.uncertain-choice", target: { ...target, researcherResponseDraft: { kind: "custom", note: "A later response." } } });
  await form(hookHarness(reopened.type)(reopened.props)).props.onSubmit(event);
  assert.equal(starts.length, 2); assert.deepEqual(starts[1], starts[0]);
  assert.deepEqual(starts[1][1].researcher_response_draft, response);
}));

test("reopening an unsent question keeps its wording while using the current structured response and saved answer", async () => withMocks(async ({ starts, saves }) => {
  const initial = { kind: "choice", option_id: "donors", label: "Equal donor weights", consequence: "Donors contribute equally.", note: "Earlier note." };
  const current = { kind: "choice", option_id: "cells", label: "Equal cell weights", consequence: "Donors with more cells contribute more.", note: "Updated note." };
  const target = { ...source, researcherResponseDraft: initial, researcherNote: { note: "Saved earlier answer.", revision: 1 } };
  const first = questionForm({ projectId: "project.unsent-current-choice", target });
  const renderFirst = hookHarness(first.type); let tree = renderFirst(first.props);
  textarea(tree).props.onChange({ target: { value: "How does this population change the interpretation?" } });
  const reopened = questionForm({ projectId: "project.unsent-current-choice", target: { ...target, researcherResponseDraft: current, researcherNote: { note: "Saved latest answer.", revision: 2 } } });
  const renderReopened = hookHarness(reopened.type); tree = renderReopened(reopened.props);
  assert.equal(textarea(tree).props.value, "How does this population change the interpretation?");
  assert.ok(find(tree, node => node.props?.text === "Equal cell weights\n\nDonors with more cells contribute more.\n\nUpdated note."));
  assert.ok(find(tree, node => node.props?.text === "Saved latest answer."));
  assert.ok(!find(tree, node => node.props?.text?.includes?.("Earlier note.")));
  await form(tree).props.onSubmit(event);
  assert.equal(starts.length, 1); assert.equal(saves.length, 0);
  assert.deepEqual(starts[0][1].researcher_response_draft, { kind: "choice", option_id: "cells", note: "Updated note." });
}));

test("reopening an unsent legacy note uses the current note rather than an old cached response", async () => withMocks(async ({ starts }) => {
  const target = { ...source, researcherNoteDraft: "Earlier unsaved note." };
  const first = questionForm({ projectId: "project.unsent-current-note", target });
  textarea(hookHarness(first.type)(first.props)).props.onChange({ target: { value: "Explain this assumption." } });
  const reopened = questionForm({ projectId: "project.unsent-current-note", target: { ...target, researcherNoteDraft: "Current unsaved note." } });
  await form(hookHarness(reopened.type)(reopened.props)).props.onSubmit(event);
  assert.equal(starts[0][1].researcher_note_draft, "Current unsaved note.");
}));

test("an uncertain suggestions submission retains its question, draft note and idempotency key for retry", async () => withMocks(async ({ starts }) => {
  ui.api.startRun = async (...args) => { starts.push(args); throw new Error("Connection lost."); };
  const target = { ...source, assessmentPurpose: "issue_suggestions", researcherNoteDraft: "We do not know whether follow-up is selective." };
  const element = questionForm({ projectId: "project.uncertain-suggestions", target });
  const render = hookHarness(element.type);
  await form(render(element.props)).props.onSubmit(event);
  const reopened = questionForm({ projectId: "project.uncertain-suggestions", target: { ...target, researcherNoteDraft: "A later unsaved clinic note." } });
  const renderReopened = hookHarness(reopened.type);
  await form(renderReopened(reopened.props)).props.onSubmit(event);
  assert.equal(starts.length, 2); assert.deepEqual(starts[1], starts[0]);
  assert.equal(starts[1][1].researcher_note_draft, target.researcherNoteDraft);
  assert.equal(textarea(renderReopened(reopened.props)).props.value, ui.defaultConversationQuestion(target));
}));
