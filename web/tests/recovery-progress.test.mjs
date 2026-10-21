import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { evaluationRecovery } from "../src/empiricalProgress.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-recovery-reader-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import ResearchProgress from '${src}/components/ResearchProgress.jsx'; import {EmpiricalProgressCard,EmpiricalExecutionHistory,EmpiricalPause,EmpiricalSavedDecisions} from '${src}/components/EmpiricalProgress.jsx'; const draw = C => props => renderToStaticMarkup(React.createElement(C,props)); export const work = draw(ResearchProgress); export const progress = draw(EmpiricalProgressCard); export const history = draw(EmpiricalExecutionHistory); export const pause = draw(EmpiricalPause); export const saved = draw(EmpiricalSavedDecisions);`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

const request = { request_id: "decision.current", revision: 1, question: "How should the evaluation continue?", reason: "Review the saved attempt.", evidence_refs: [{ attempt_id: "attempt.current" }] };
const attempt = { attempt_id: "attempt.current", batch_id: "batch.current", work_item_id: "compare", status: "interrupted", diagnostic: "Interrupted while retaining /outputs/exact.json.", artifacts: [{ path: "/outputs/exact.json", sha256: "a".repeat(64) }] };
const base = { run_id: "run.recovery", state: "awaiting_user", p4_progress: { plan: { work_items: [{ work_item_id: "compare", title: "Compare discounted cost" }] }, budget: { used_seconds: 12, remaining_seconds: 48 }, ledger: [attempt], pause_request: request } };
const feedback = { accepted: false, operation: "run_batch", code: "invalid_arguments", json_pointer: "/timeout_seconds", error: "timeout_seconds is required", hint: "Provide the bounded time limit for the declared work item.", execution_state: "not_accepted" };
const visible = (html) => html.replace(/<details\b[^>]*>[\s\S]*?<\/details>/g, "");

test("artifact repair preserves the saved message and exposes the existing review action", () => {
  for (const state of ["working", "stopped", "accepted"]) {
    const message = state === "working" ? "Correcting an artifact reference, attempt 1 of 2." : state === "stopped" ? "Automatic repair stopped because the same issue remained. Review the findings before requesting correction." : "Saved artifacts were accepted after repair.";
    const run = { run_id: "repair.one", state: state === "stopped" ? "failed" : "running", progress: { stages: [{ stage_id: "p5.lead", label: "Manuscript synthesis", state: state === "stopped" ? "failed" : "correcting", repair: { attempt: 1, state, message } }] } };
    const html = render.work({ run, onOpenRun() {} });
    assert.ok(html.includes(message));
    assert.match(html, new RegExp(`data-repair-state="${state}"`));
    if (state === "stopped") assert.match(html, /Review findings and correction/);
  }
});

test("only the attempt referenced by the current question can explain an interruption", () => {
  const current = evaluationRecovery(base.p4_progress);
  assert.equal(current.kind, "interrupted");
  const later = { ...request, request_id: "decision.later", evidence_refs: [] };
  assert.equal(evaluationRecovery({ ...base.p4_progress, pause_request: later }), null);
  assert.equal(evaluationRecovery({ ...base.p4_progress, pause_request: { ...later, evidence_refs: [{ batch_id: "batch.current" }] } }), null);
  const html = render.progress({ run: { ...base, p4_progress: { ...base.p4_progress, pause_request: later } }, onShowIssues() {} });
  assert.doesNotMatch(html, /Experiment interrupted|Retained results remain provisional/);
  assert.match(html, /Review requested direction/);
});

test("interrupted evidence is provisional, with its exact receipt inside details", () => {
  const html = render.progress({ run: base, onShowIssues() {} });
  assert.match(visible(html), /Experiment interrupted|Retained results remain provisional/);
  assert.match(html, /Review evidence and direction/);
  assert.match(html, /<details[^>]+data-recovery-details="true"[^>]*><summary>Recovery details<\/summary>/);
  assert.ok(html.includes("attempt.current") && !visible(html).includes("attempt.current"));
  assert.ok(html.includes("/outputs/exact.json") && !visible(html).includes("/outputs/exact.json"));
  const editor = render.pause({ run: base, projectId: "p", request });
  assert.match(editor, /Retained results remain provisional/);
  assert.match(editor, /Save response|Finish with available evidence/);
  assert.doesNotMatch(editor, /No experiment started|computation did not run/);
});

test("a rejected request does not erase earlier pending work or reveal raw fields upfront", () => {
  const run = { ...base, p4_progress: { ...base.p4_progress, pause_request: { ...request, evidence_refs: [] }, pending_batch: { batch_id: "earlier" }, control_feedback: feedback } };
  const html = render.progress({ run, onShowIssues() {} });
  assert.match(visible(html), /Experiment request needs correction|earlier saved work remains recorded/);
  assert.ok(html.includes("/timeout_seconds") && !visible(html).includes("/timeout_seconds"));
  assert.doesNotMatch(html, /No experiment started|no new computation/);
});

test("missing acceptance remains unknown and successful feedback clears old rejection", () => {
  for (const current of [{ ...feedback, accepted: undefined, execution_state: "unknown" }, { error: "A historical tool response was lost." }]) {
    const progress = { ...base.p4_progress, pause_request: { ...request, evidence_refs: [] }, control_feedback: current };
    assert.equal(evaluationRecovery(progress).kind, "unknown");
    const html = render.progress({ run: { ...base, p4_progress: progress }, onShowIssues() {} });
    assert.match(visible(html), /outcome is unconfirmed|Inspect saved work/);
    assert.match(html, /Review saved work/);
    assert.doesNotMatch(html, /This request was not accepted|No experiment started/);
  }
  const accepted = { ...base.p4_progress, pause_request: { ...request, evidence_refs: [] }, control_feedback: { accepted: true }, checkpoint: { host_feedback: true, latest_control_feedback: feedback } };
  assert.equal(evaluationRecovery(accepted), null);
  assert.doesNotMatch(render.progress({ run: { ...base, p4_progress: accepted } }), /request needs correction|timeout_seconds/);
  const historical = { ...request, request_id: "decision.previous", evidence_refs: [] };
  assert.equal(evaluationRecovery({ ...base.p4_progress, execution_state_error: "Current state unreadable", control_feedback: feedback }, historical), null);
});

test("validation outages request setup repair without a scientific rewrite", () => {
  const run = { ...base, p4_progress: { ...base.p4_progress, pause_request: { ...request, evidence_refs: [] }, control_feedback: { ...feedback, code: "validation_unavailable" } } };
  const html = render.progress({ run, onShowIssues() {} });
  assert.match(visible(html), /Validation setup needs attention|Restore the validation setup/);
  assert.doesNotMatch(visible(html), /scientific artifacts.*failed|rewrite/);
});

test("a current setup pause keeps repair guidance and the attempt log beside the response", () => {
  const setupRequest = { ...request, attention_kind: "setup", evidence_refs: [] };
  const run = { ...base, state: "awaiting_user", p4_progress: { ...base.p4_progress, attention_kind: "setup", pause_request: setupRequest, setup_attention: { guidance: "Use the shared runtime and restore workspace access.", logs: [{ path: "attempt.log", text: "Permission denied for the workspace." }] } } };
  const html = render.pause({ projectId: "p", run, request: setupRequest });
  assert.match(html, /Use the shared runtime and restore workspace access/);
  assert.match(html, /Technical log for this attempt[\s\S]*Permission denied for the workspace/);
  assert.match(html, /Your instruction or answer/);
  assert.doesNotMatch(html, /method failed[.]<\/p>/);
});

test("historical checkpoint feedback cannot establish that nothing executed", () => {
  const run = { ...base, p4_progress: { ...base.p4_progress, checkpoint: { host_feedback: true, summary: "Review the last response.", latest_control_feedback: { error: "The result could not be delivered." } } } };
  const html = render.history({ run });
  assert.match(html, /Last planning feedback|outcome is unconfirmed/);
  assert.doesNotMatch(html, /No experiment started|no new computation/);
});

test("historical inspection stays collapsed and exposes only its original receipt when opened", () => {
  const receipt = { operation: "run_batch", code: "execution_outcome_unknown", execution_state: "unknown",
    json_pointer: "/timeout_seconds", error: "Response failed after saving C:/saved/previous-request.json." };
  const previous = { ...request, request_id: "decision.previous", reason: receipt.error,
    evidence_refs: [{ attempt_id: "attempt.previous", description: "The original tool result needs inspection.", control_feedback: receipt }] };
  const progress = { ...base.p4_progress, pause_request: { ...request, evidence_refs: [] },
    control_feedback: { accepted: true },
    saved_answers: [{ request_id: previous.request_id, request_revision: 1, revision: 1, request: previous,
      note: "I inspected the saved attempt before continuing.", applied_to: ["run.recovery"] }] };
  assert.deepEqual(evaluationRecovery(progress, previous)?.feedback, receipt);
  assert.equal(evaluationRecovery(progress), null);
  assert.equal(evaluationRecovery({ ...progress, control_feedback: feedback }, { ...previous, evidence_refs: [] }), null);
  const html = render.saved({ projectId: "p", run: { ...base, p4_progress: progress } });
  assert.match(html, /^<details class="research-details empirical-saved-decisions"[^>]*><summary>Saved evaluation decisions \(1\)<\/summary>/);
  assert.doesNotMatch(html.match(/^<details[^>]*>/)?.[0] || "", /\bopen(?:=|\s|>)/);
  const openedHistory = html.slice(html.indexOf("</summary>") + "</summary>".length, -"</details>".length);
  assert.match(visible(openedHistory), /outcome was unconfirmed when this question was saved/);
  assert.ok(html.includes("/timeout_seconds") && !visible(openedHistory).includes("/timeout_seconds"));
  assert.ok(html.includes("C:/saved/previous-request.json") && !visible(openedHistory).includes("C:/saved/previous-request.json"));
  assert.doesNotMatch(html, /attempt.current|Experiment interrupted|Continue with instructions|Finish with evidence/);
});
