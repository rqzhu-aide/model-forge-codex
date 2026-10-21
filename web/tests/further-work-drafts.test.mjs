import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { furtherWorkKey } from "../src/phaseWorkflow.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-further-work-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import FurtherWork,{rememberFurtherWorkDraft} from '${src}/components/FurtherWorkCard.jsx'; import {readConversationDraft} from '${src}/assumptionConversations.js'; export const render=props=>renderToStaticMarkup(React.createElement(FurtherWork,props)); export const remember=rememberFurtherWorkDraft; export const read=readConversationDraft;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const exact = { kind: "phase_issue", branch: "trunk", phase: "P2", family: "theory_review", generation_id: "review.one", sha256: "a".repeat(64), run_id: "run.one", package_id: "package.one", object_id: "finding.one", entry_pointer: "/assessments/0/findings/0" };
const issue = { issue_id: "issue.one", title: "An unresolved calibration argument", branch: "trunk", phase: "P2", affected_record_ids: ["method.a"], explanation_target: exact };
const props = { projectId: "p", phase: "P2", branch: "method.a", methodId: "method.a", issues: [issue] };
const radio = (html, label) => [...html.matchAll(/<label class="check-label"><input([^>]*)\/>\s*([^<]+)/g)].find((match) => match[2].replaceAll("&#x27;", "'") === label)?.[1];
function withStorage(run) {
  const previous = globalThis.sessionStorage; const values = new Map();
  globalThis.sessionStorage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
  try { run(); } finally { if (previous === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = previous; }
}

test("returning to a method restores alternatives and its exact selected issues without borrowing another method's intent", () => withStorage(() => {
  const keyA = furtherWorkKey("p", "method.a", "P2"), keyB = furtherWorkKey("p", "method.b", "P2");
  let draft = ui.remember(keyA, null, { text: "Explore a different estimating equation.", focus: "alternatives" });
  draft = ui.remember(keyA, draft, { selectedRefs: [exact] });
  ui.remember(keyB, null, { text: "Refine method B.", focus: "selected", selectedRefs: [] });
  const a = ui.render(props), b = ui.render({ ...props, branch: "method.b", methodId: "method.b" });
  assert.match(radio(a, "Explore new alternatives"), /checked=""/);
  assert.doesNotMatch(radio(a, "Explore alternatives from this model"), /checked/);
  assert.match(a, /type="checkbox" checked=""/);
  assert.match(radio(b, "Explore alternatives from this model"), /checked=""/);
  assert.match(b, /proposal and comparison run/);
  assert.match(b, /does not guarantee a revision of the selected model/);
  assert.doesNotMatch(b, /An unresolved calibration argument/);
  assert.deepEqual(ui.read(keyA).selectedRefs, [exact]);
  assert.equal(ui.read(keyA).text, "Explore a different estimating equation.");
  assert.equal(ui.read(keyB).text, "Refine method B.");
}));

test("saving instructions leaves choices intact but allows fresh server instructions on the next visit", () => withStorage(() => {
  const key = furtherWorkKey("p", "method.a", "P2");
  const draft = ui.remember(key, null, { text: "Now saved on the server.", focus: "alternatives", selectedRefs: [exact] });
  ui.remember(key, draft, { text: undefined });
  const restored = ui.read(key);
  assert.equal(Object.hasOwn(restored, "text"), false);
  assert.equal(restored.focus, "alternatives");
  assert.deepEqual(restored.selectedRefs, [exact]);
  assert.match(radio(ui.render(props), "Explore new alternatives"), /checked=""/);
}));

test("evaluation mode and a typed budget survive phase switches and saving prose", () => withStorage(() => {
  const evaluation = furtherWorkKey("p", "method.a", "P4"), theory = furtherWorkKey("p", "method.a", "P3");
  let draft = ui.remember(evaluation, null, { mode: "p4.comprehensive", experimentBudget: "900" });
  draft = ui.remember(evaluation, draft, { text: "Compare contamination regimes." });
  ui.remember(theory, null, { text: "Complete the calibration proof.", mode: "p3.theory_revision" });
  ui.remember(evaluation, draft, { text: undefined });
  assert.deepEqual(ui.read(evaluation), { mode: "p4.comprehensive", experimentBudget: "900" });
  assert.equal(ui.read(theory).mode, "p3.theory_revision");
  assert.equal(ui.read(furtherWorkKey("p", "method.b", "P4")), null);
}));

test("an earlier selected source does not silently select a revised issue with the same object id", () => withStorage(() => {
  const key = furtherWorkKey("p", "method.a", "P2");
  ui.remember(key, null, { selectedRefs: [exact] });
  const updated = { ...issue, explanation_target: { ...exact, generation_id: "review.two", sha256: "b".repeat(64), run_id: "run.two", package_id: "package.two" } };
  const html = ui.render({ ...props, issues: [updated] });
  assert.doesNotMatch(html, /type="checkbox" checked=""/);
  assert.deepEqual(ui.read(key).selectedRefs, [exact]);
}));
