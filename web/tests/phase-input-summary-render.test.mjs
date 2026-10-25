import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { phaseInputSummary, phaseQuestionAnchor } from "../src/phaseInputSummary.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-input-summary-render-"));
const bundle = path.join(directory, "render.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Summary from '${src}/components/PhaseInputSummary.jsx'; import Dialogue from '${src}/components/ResearcherDialogue.jsx'; export {Summary}; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher; export const summary = props => renderToStaticMarkup(<Summary {...props}/>); export const dialogue = props => renderToStaticMarkup(<Dialogue {...props}/>);`, resolveDir: src, loader: "jsx" },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  define: { "process.env.NODE_ENV": '"production"' },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const modelRef = { stable_id: "method.a", version: 2, definition_sha256: "d".repeat(64) };
const escape = value => value.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("'", "&#x27;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
const source = (id, phase = "P4", branch = "method.a") => ({ kind: "phase_issue", branch, phase, family: "attention_items", generation_id: "generation.current", sha256: "a".repeat(64), run_id: "run.current", package_id: "package.current", entry_pointer: `/items/${id}`, object_id: id });
const question = (id, phase = "P4", branch = "method.a", extra = {}) => ({ attention_id: id, kind: "researcher_decision", phase, branch, question: `Question ${id}?`, disposition: "open", scope: { kind: "project" }, generation_ref: source(id, phase, branch), explanation_target: source(id, phase, branch), ...extra });
const answer = (item, extra = {}) => ({ attention_id: item.attention_id, question_ref: item.explanation_target, attention: item, scope: item.scope, revision: 1, note: "A saved account.", origin: "researcher_reported", ...extra });
const preparation = { loaded: true, hasInstructions: true, instructionsChanged: false, inputCount: 0, inputsChanged: false };
const readyInputs = { loading: false, selected: true, inputsReady: true };
const summary = (context, extra = {}) => render.summary({ context, phase: context.phase, scope: "exact-view-scope", preparation, preparationStatus: readyInputs, ...extra });

test("the compact summary has navigable labels and honest counts without response or launch controls", () => {
  const open = question("open"), saved = question("saved"), unknown = question("unknown");
  const html = summary({ projectId: "project.render", phase: "P4", branch: "method.a", modelRef, issues: [open, saved, unknown], answers: [answer(saved), answer(unknown, { origin: "unknown" })] });
  for (const label of ["Research questions", "Study understanding", "Run preparation"]) assert.match(html, new RegExp(`<button[^>]*>${label}`));
  for (const label of ["answered", "unanswered", "unknown"]) assert.match(html, new RegExp(`<b>1</b> ${label}</button>`));
  for (const text of ["Instructions saved", "Inputs available", "Counts reflect saved responses, not scientific readiness"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /<form\b|<textarea\b|<input\b|type="submit"|Start research|Save instruction/);
  const zero = summary({ projectId: "empty", phase: "P1", branch: "trunk" });
  assert.match(zero, /<b>0<\/b> unanswered<\/span>/);
  assert.doesNotMatch(zero, /<b>0<\/b> unanswered<\/button>/);
});

test("every counted current question has one exact destination in the existing editors across P1 to P4", () => {
  for (const phase of ["P1", "P2", "P3", "P4"]) {
    const branch = phase === "P1" ? "trunk" : "method.a";
    const authoredBranch = phase === "P2" ? "trunk" : branch;
    const open = question("open", phase, authoredBranch), saved = question("saved", phase, authoredBranch), unknown = question("unknown", phase, authoredBranch);
    const scoped = question("scoped", phase, authoredBranch, { scope: { kind: "model", branch: authoredBranch, model_ref: modelRef } });
    const context = { projectId: "project.render", phase, branch, methodId: phase === "P2" ? "method.a" : undefined, modelRef, issues: [open, saved, unknown, scoped, question("task", phase, authoredBranch, { kind: "research_task" })], answers: [answer(saved), answer(unknown, { origin: "unknown" })] };
    const projected = phaseInputSummary(context);
    const html = render.dialogue(context);
    assert.equal(projected.questions.total, phase === "P1" ? 3 : 4, phase);
    if (phase === "P1") {
      assert.ok(projected.questions.items.every(({ issue }) => issue.attention_id !== scoped.attention_id));
      assert.ok(!html.includes(`data-reading-anchor="${escape(phaseQuestionAnchor(scoped))}"`));
      assert.ok(!html.includes("Question scoped?"));
    }
    for (const { anchor } of projected.questions.items) assert.equal(html.split(`data-reading-anchor="${escape(anchor)}"`).length - 1, 1, `${phase}: ${anchor}`);
    assert.equal(html.split('data-reading-anchor="phase-decisions"').length - 1, 1);
    assert.equal(html.split('data-reading-anchor="researcher-dialogue"').length - 1, 1);
  }
});

test("study understanding links share the original saved-context and pending-interpretation destinations", () => {
  const problemContext = { revision: 3, items: [1, 2, 3].map(number => ({ item_id: `context.${number}`, revision: 2, status: "confirmed", statement: `Account ${number}.`, scope: { kind: "project" } })), proposals: [{ amendment_id: "proposal.current", status: "pending", reason: "Confirm the collection account.", item: { statement: "A prospective collection.", scope: { kind: "project" } } }] };
  const context = { projectId: "project.render", phase: "P1", branch: "trunk", problemContext };
  const projected = phaseInputSummary(context);
  const html = render.dialogue(context);
  assert.equal(projected.understanding.saved, 3); assert.equal(projected.understanding.pending, 1);
  for (const { anchor } of [...projected.understanding.items, ...projected.understanding.proposals]) assert.equal(html.split(`data-reading-anchor="${escape(anchor)}"`).length - 1, 1);
  const card = summary(context);
  assert.match(card, /<b>3<\/b> saved<\/button>/); assert.match(card, /<b>1<\/b> to confirm<\/button>/);
});

test("input errors, unknown instructions and active work stay separate from saved response counts", () => {
  const item = question("saved");
  const context = { projectId: "project.render", phase: "P4", branch: "method.a", issues: [item], answers: [answer(item)] };
  const unavailable = summary(context, { preparation: { loaded: false, error: true }, preparationStatus: { error: true } });
  assert.match(unavailable, /Instructions unavailable/); assert.match(unavailable, /Input check unavailable/);
  assert.match(unavailable, /<b>1<\/b> answered<\/button>/); assert.doesNotMatch(unavailable, /Inputs available|Instructions saved/);
  const preparationFailure = summary(context, { preparation: { loaded: false, error: true }, preparationStatus: null });
  assert.match(preparationFailure, /Instructions unavailable/); assert.match(preparationFailure, /Input check unavailable/);
  assert.doesNotMatch(preparationFailure, /Checking inputs/);
  assert.match(summary(context, { preparationStatus: { ...readyInputs, invalidBudget: true } }), /Check settings/);
  assert.match(summary(context, { activeRun: { state: "awaiting_user" } }), /Work waiting for input/);
});

test("P5 keeps report revision preparation without a generic researcher discussion summary", () => {
  const html = summary({ projectId: "report.render", phase: "P5", branch: "method.a", issues: [question("editorial", "P5")] });
  assert.match(html, /Revise report|Next report revision/);
  assert.match(html, /aria-label="Revise report"/);
  assert.match(summary({ projectId: "evaluation.render", phase: "P4", branch: "method.a" }), /aria-label="Revise and rerun"/);
  assert.match(html, /Run preparation/); assert.match(html, /Section discussions stay with the report/);
  assert.doesNotMatch(html, /Research questions|Study understanding|Discuss your problem|<form\b|<textarea\b/);
});

test("P5 pause review opens its existing revision settings instead of a nonexistent generic discussion", () => {
  const names = ["window", "getComputedStyle", "requestAnimationFrame", "cancelAnimationFrame"];
  const previous = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const oldDispatcher = render.dispatcher.current; const refs = [];
  const settings = { tagName: "DETAILS", open: false, parentElement: null, closest: () => null, removeAttribute: () => {}, getAttribute: name => name === "data-reading-anchor" ? "further-work" : null };
  const root = { contains: () => true, querySelectorAll: selector => selector === "[data-reading-anchor]" ? [settings] : [] };
  settings.parentElement = root;
  const origin = { closest: selector => selector === "[data-reader-ready]" ? root : null, getAttribute: () => null };
  const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
  try {
    globalThis.window = { scrollY: 0, innerHeight: 700 };
    globalThis.getComputedStyle = () => ({ display: "block", visibility: "visible" });
    globalThis.requestAnimationFrame = () => 1; globalThis.cancelAnimationFrame = () => {};
    // Inspect the shipped event handler without claiming DOM layout coverage.
    render.dispatcher.current = {
      useState: initial => [typeof initial === "function" ? initial() : initial, () => {}],
      useRef: initial => { const ref = { current: initial }; refs.push(ref); return ref; },
      useEffect: () => {}, useLayoutEffect: () => {},
    };
    const tree = render.Summary({ context: { projectId: "report.pause", phase: "P5", branch: "method.a", activePause: true }, phase: "P5", scope: "report.scope", preparation, preparationStatus: readyInputs });
    const review = nodes(tree).find(node => node.props.children === "Review the current pause");
    assert.ok(review); review.props.onClick({ currentTarget: origin });
    assert.equal(settings.open, true, "The existing P5 settings contain the retained pause response and recovery.");
  } finally {
    for (const ref of refs) ref.current?.dispose?.();
    render.dispatcher.current = oldDispatcher;
    for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; }
  }
});
