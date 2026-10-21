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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-issue-actions-"));
const bundle = path.join(directory, "actions.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `export {default as React} from 'react'; export {api} from '${src}/api.js'; export {IssueEntry} from '${src}/components/IssuesCard.jsx'; export {default as Conversations} from '${src}/components/AssumptionConversations.jsx'; export * from '${src}/assumptionConversations.js'; export {explanationRun} from '${src}/phaseWorkflow.js'; export {activePhaseRun} from '${src}/phaseUiState.js';`, resolveDir: src },
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
function hookHarness(Component) {
  const slots = []; let cursor = 0;
  const internals = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const dispatcher = {
    useState(initial) {
      const index = cursor++;
      if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial;
      return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }];
    },
    useRef(initial) { const index = cursor++; return slots[index] ||= { current: initial }; },
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
  assert.match(ui.defaultConversationQuestion(suggestions), /alternatives and tradeoffs/);
  const run = { assessment_purpose: "issue_suggestions", branch_id: "trunk", phase: "P2", mode: "p3.assessment", intent: "assessment", state: "running" };
  assert.equal(ui.explanationRun(run), true);
  assert.equal(ui.activePhaseRun([run], "P2", "trunk"), null);
});

test("item actions retain the exact question, distinguish the unsaved note, and save against its answer revision", async () => withMocks(async ({ starts, saves }) => {
  const targets = []; const saved = { note: "The sample comes from participating clinics.", revision: 2 };
  const props = { issue: { ...issue, researcher_answer: saved }, projectId: "project.item-actions", phase: "P2", branch: "trunk", compact: true, onExplain: target => targets.push(target) };
  const render = hookHarness(ui.IssueEntry);
  button(render(props), "Edit instruction").props.onClick();
  textarea(render(props)).props.onChange({ target: { value: "  Clinics opt in; follow-up may be incomplete.  " } });
  const tree = render(props);
  button(tree, "Discuss").props.onClick(); button(tree, "Lead suggestions").props.onClick();
  assert.equal(starts.length, 0); assert.equal(saves.length, 0);
  assert.equal(targets.length, 2);
  for (const target of targets) {
    assert.deepEqual(ui.assumptionSource(target), source);
    assert.equal(target.researcherNote.note, saved.note); assert.equal(target.researcherNote.revision, 2);
    assert.equal(target.researcherNoteDraft.trim(), "Clinics opt in; follow-up may be incomplete.");
  }
  assert.equal(targets[1].assessmentPurpose, "issue_suggestions");
  await form(tree).props.onSubmit(event);
  assert.equal(saves.length, 1); assert.equal(starts.length, 0);
  assert.equal(saves[0][1], issue.attention_id); assert.equal(saves[0][2], "Clinics opt in; follow-up may be incomplete.");
  assert.deepEqual(saves[0][3].expected_source, source); assert.equal(saves[0][3].expected_revision, 2);
  const after = render(props); button(after, "Lead suggestions").props.onClick();
  assert.equal(targets.at(-1).researcherNote.note, "Clinics opt in; follow-up may be incomplete.");
  assert.equal(targets.at(-1).researcherNote.revision, 3);
  assert.ok(!targets.at(-1).researcherNoteDraft);
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
