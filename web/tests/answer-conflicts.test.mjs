import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { exactAnswerSnapshot } from "../src/answerDrafts.js";
import { issueVersionKey } from "../src/phaseWorkflow.js";
import { populationChoice, studyFact } from "./fixtures/researcher-decisions.mjs";

// Exercise the real editor handlers. The hook dispatcher retains state between
// polls without adding a browser or another React installation to this test.
const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-answer-conflicts-"));
const bundle = path.join(directory, "handlers.cjs");
const src = fileURLToPath(new URL("../src/", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `export {default as React} from 'react'; export {api} from '${src}/api.js'; export {IssueEntry} from '${src}/components/IssuesCard.jsx'; export {readConversationDraft,saveConversationDraft} from '${src}/assumptionConversations.js';`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const storage = new Map();
globalThis.sessionStorage = { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
const text = tree => Array.isArray(tree) ? tree.map(text).join("") : tree && typeof tree === "object" ? text(tree.props?.children) : String(tree ?? "");
function find(tree, predicate) { if (Array.isArray(tree)) return tree.map(item => find(item, predicate)).find(Boolean); if (!tree || typeof tree !== "object") return null; return predicate(tree) ? tree : find(tree.props?.children, predicate); }
const button = (tree, label) => find(tree, node => (typeof node.props?.onClick === "function" || node.props?.type === "submit") && text(node.props.children) === label);
const field = tree => find(tree, node => node.type === "textarea");
const form = tree => find(tree, node => node.type === "form");
const answer = (item, revision, note, extra = {}) => ({ attention_id: item.attention_id, attention: item, question_ref: item.explanation_target, revision, note, origin: "researcher_reported", ...extra });
const conflictError = message => Object.assign(new Error(message), { status: 409 });
let sequence = 0;
function editor(item, saved, extras = {}) {
  const slots = []; let cursor = 0;
  const projectId = extras.projectId || `project.answer-conflict.${++sequence}`;
  let props = { issue: { ...item, researcher_answer: saved }, projectId, phase: item.phase, branch: item.branch, ...extras };
  const key = `issue-response:${JSON.stringify([projectId, issueVersionKey(item)])}`;
  const internals = ui.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const dispatcher = {
    useState(initial) { const index = cursor++; if (!Object.hasOwn(slots, index)) slots[index] = typeof initial === "function" ? initial() : initial; return [slots[index], value => { slots[index] = typeof value === "function" ? value(slots[index]) : value; }]; },
    useRef(initial) { const index = cursor++; return slots[index] ||= { current: initial }; },
    useId() { return `answer-${cursor++}`; }, useEffect() { cursor++; }, useLayoutEffect() { cursor++; }, useMemo(compute) { cursor++; return compute(); }, useContext() { cursor++; return {}; },
  };
  const render = () => { cursor = 0; const previous = internals.ReactCurrentDispatcher.current; internals.ReactCurrentDispatcher.current = dispatcher; try { return ui.IssueEntry(props); } finally { internals.ReactCurrentDispatcher.current = previous; } };
  return { key, projectId, render, poll: newer => { props = { ...props, issue: { ...item, researcher_answer: newer } }; return render(); }, edit: () => { button(render(), "Edit your answer")?.props.onClick(); return render(); }, write: value => { field(render()).props.onChange({ target: { value } }); return render(); }, submit: () => form(render()).props.onSubmit({ preventDefault() {} }), restore: cached => { slots.length = 0; ui.saveConversationDraft(key, cached); return render(); } };
}

test("polling keeps a free-text draft's exact base until the latest answer is explicitly reviewed", async () => {
  const first = answer(studyFact, 1, "Cells are independent."), newer = answer(studyFact, 2, "Donors are the sampling units.");
  const entry = editor(studyFact, first); entry.edit(); entry.write("Use each donor's counts.");
  let saves = 0; ui.api.resolveAttention = async () => { saves++; };
  const polled = entry.poll(newer);
  assert.equal(field(polled).props.value, "Use each donor's counts.");
  assert.equal(ui.readConversationDraft(entry.key).base.revision, 1);
  assert.match(text(polled), /Another answer was saved while you were editing/);
  assert.equal(button(polled, "Save answer").props.disabled, true);
  await entry.submit(); assert.equal(saves, 0);
  ui.api.decisionsPending = async () => ({ researcher_answers: [newer] });
  await button(polled, "Review latest answer").props.onClick();
  const review = entry.render();
  assert.ok(find(review, node => node.props?.text === newer.note));
  assert.equal(field(review).props.value, "Use each donor's counts.");
  assert.equal(ui.readConversationDraft(entry.key).base.revision, 1);
  button(review, "Keep editing my draft").props.onClick();
  assert.equal(ui.readConversationDraft(entry.key).base.revision, 2);
  ui.api.resolveAttention = async (pid, id, note, options) => { saves++; assert.equal(options.expected_revision, 2); assert.deepEqual(options.expected_source, studyFact.explanation_target); return { answer: answer(studyFact, 7, note) }; };
  await entry.submit();
  assert.equal(saves, 1); assert.equal(ui.readConversationDraft(entry.key), null);
  assert.match(text(entry.render()), /Your answer is saved/);
  entry.edit(); assert.equal(ui.readConversationDraft(entry.key).base.revision, 7);
});

test("concurrent first answers retain multiple-choice selection and note through 409 before polling", async () => {
  const entry = editor(populationChoice); entry.render();
  find(entry.render(), node => node.type === "input" && node.props.value === "option:observed").props.onChange(); entry.write("For the scheduled visit only.");
  const newer = answer(populationChoice, 1, "All surviving patients.");
  ui.api.resolveAttention = async (pid, id, note, options) => { assert.equal(options.expected_revision, 0); throw conflictError("Your saved response changed; reload it before saving"); };
  await entry.submit();
  assert.equal(ui.readConversationDraft(entry.key).choice, "option:observed");
  assert.deepEqual(ui.readConversationDraft(entry.key).base.source, populationChoice.explanation_target);
  assert.doesNotMatch(text(entry.render()), /Your answer is saved/);
  ui.api.decisionsPending = async () => ({ researcher_answers: [newer] });
  await button(entry.render(), "Review latest answer").props.onClick();
  button(entry.render(), "Keep editing my draft").props.onClick();
  const retained = ui.readConversationDraft(entry.key);
  assert.equal(retained.choice, "option:observed"); assert.equal(retained.origin, "researcher_reported"); assert.equal(retained.text, "For the scheduled visit only.");
  ui.api.resolveAttention = async (pid, id, note, options) => { assert.equal(options.expected_revision, 1); assert.equal(options.selection.option_id, "observed"); throw conflictError("Your saved response changed; reload it before saving"); };
  await entry.submit(); // A second update after review still goes through the server guard.
  assert.equal(button(entry.render(), "Save answer").props.disabled, true);
  assert.equal(field(entry.render()).props.value, retained.text);
});

test("known cached bases persist across reload; legacy drafts require review and can use the saved unknown", async () => {
  const first = answer(studyFact, 2, "Original information."), latest = answer(studyFact, 5, "Collection mechanism remains unknown.", { origin: "unknown" });
  const entry = editor(studyFact, latest);
  entry.restore({ text: "My retained information.", origin: "unknown", choice: "unknown", base: { source: studyFact.explanation_target, revision: 2 } });
  assert.equal(ui.readConversationDraft(entry.key).base.revision, 2);
  assert.match(text(entry.render()), /Another answer was saved/);
  entry.restore({ text: "Old cached note.", origin: "unknown", choice: "unknown" });
  assert.match(text(entry.render()), /saved-answer version for this draft is unknown/);
  entry.write("Old cached note, retained.");
  assert.equal(ui.readConversationDraft(entry.key).base.revision, null);
  ui.api.decisionsPending = async () => ({ researcher_answers: [first, latest] });
  await button(entry.render(), "Review latest answer").props.onClick();
  button(entry.render(), "Use latest answer").props.onClick();
  const cached = ui.readConversationDraft(entry.key);
  assert.equal(cached.base.revision, 5); assert.equal(cached.origin, "unknown"); assert.equal(cached.text, latest.note);
  assert.equal(field(entry.render()).props.value, latest.note);
  button(entry.render(), "Cancel edit").props.onClick();
  assert.equal(ui.readConversationDraft(entry.key), null);
});

test("review adopts only the answer actually shown even when another poll arrives before the choice", async () => {
  const original = answer(studyFact, 1, "Original information."), reviewed = answer(studyFact, 2, "Reviewed information."), newest = answer(studyFact, 3, "Later information.");
  const entry = editor(studyFact, original); entry.edit(); entry.write("My retained draft."); entry.poll(reviewed);
  ui.api.decisionsPending = async () => ({ researcher_answers: [reviewed] });
  await button(entry.render(), "Review latest answer").props.onClick();
  entry.poll(newest);
  assert.ok(find(entry.render(), node => node.props?.text === reviewed.note));
  button(entry.render(), "Keep editing my draft").props.onClick();
  assert.equal(ui.readConversationDraft(entry.key).base.revision, 2);
  assert.equal(button(entry.render(), "Save answer").props.disabled, true);
  assert.equal(field(entry.render()).props.value, "My retained draft.");
});

test("a carried answer is not the destination base, including an exact destination in history", async () => {
  const old = { ...studyFact, explanation_target: { ...studyFact.explanation_target, generation_id: "older" } };
  const inherited = answer(old, 6, "Earlier answer.");
  assert.equal(exactAnswerSnapshot(studyFact, [], inherited).revision, 0);
  assert.equal(exactAnswerSnapshot(studyFact, undefined, inherited).revision, null);
  const destination = answer(studyFact, 3, "Destination's earlier answer.");
  assert.equal(exactAnswerSnapshot(studyFact, [inherited, destination], inherited).revision, 3);
  assert.equal(exactAnswerSnapshot(studyFact, [{ ...inherited, history: [destination] }], inherited).revision, 3);
  const projected = { ...studyFact, answer_applicability_refs: [{ attention_id: old.attention_id, answer_revision: inherited.revision, question_ref: old.explanation_target, reason: "The author explicitly retained this answer." }] };
  const withHistory = editor(projected, inherited, { answers: [inherited, destination] });
  assert.ok(find(withHistory.render(), node => node.props?.text === inherited.note));
  withHistory.edit();
  assert.equal(field(withHistory.render()).props.value, inherited.note);
  assert.equal(ui.readConversationDraft(withHistory.key).base.revision, 3);
  const entry = editor(studyFact, inherited, { answers: [inherited] }); entry.edit(); entry.write("Destination draft.");
  assert.equal(ui.readConversationDraft(entry.key).base.revision, 0);
  ui.api.resolveAttention = async (pid, id, note, options) => { assert.equal(options.expected_revision, 0); throw conflictError("Your saved response changed; reload it before saving"); };
  await entry.submit();
  ui.api.decisionsPending = async () => ({ researcher_answers: [inherited, answer(studyFact, 7, "Concurrent destination answer.")] });
  await button(entry.render(), "Review latest answer").props.onClick();
  button(entry.render(), "Keep editing my draft").props.onClick();
  assert.equal(ui.readConversationDraft(entry.key).base.revision, 7);
  assert.equal(field(entry.render()).props.value, "Destination draft.");
});

test("a changed-source 409 preserves the original draft and cannot be rebased onto a successor", async () => {
  const entry = editor(populationChoice); entry.render();
  find(entry.render(), node => node.type === "input" && node.props.value === "unknown").props.onChange(); entry.write("Waiting for the cohort description.");
  ui.api.resolveAttention = async () => { throw conflictError("This question's source version changed; reopen the original question before saving your response."); };
  await entry.submit();
  const oldDraft = ui.readConversationDraft(entry.key);
  assert.equal(oldDraft.origin, "unknown"); assert.equal(oldDraft.choice, "unknown"); assert.deepEqual(oldDraft.base.source, populationChoice.explanation_target);
  assert.match(text(entry.render()), /source changed/);
  assert.equal(button(entry.render(), "Review latest answer"), undefined);
  assert.equal(button(entry.render(), "Save answer").props.disabled, true);
  const successor = { ...populationChoice, explanation_target: { ...populationChoice.explanation_target, generation_id: "successor" }, options: [{ id: "different", label: "Different option", consequence: "Different target." }] };
  const fresh = editor(successor, undefined, { projectId: entry.projectId });
  assert.equal(field(fresh.render()).props.value, "");
  assert.equal(find(fresh.render(), node => node.type === "input" && node.props.value === "option:different").props.checked, false);
  assert.notEqual(entry.key, `issue-response:${JSON.stringify([entry.projectId, issueVersionKey(successor)])}`);
  assert.deepEqual(ui.readConversationDraft(entry.key), oldDraft);
});
