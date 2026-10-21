import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { answerEffect, empiricalReaderProps, explanationRun, furtherWorkKey, issuesForPhase, issueSourceTarget, issueVersionKey } from "../src/phaseWorkflow.js";
import { assumptionSource, conversationDraftKey, conversationsForTarget, isConversationTarget, isEarlierConversation } from "../src/assumptionConversations.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-phase-workflow-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {api} from '${src}/api.js'; import {TheoryStatement,ManuscriptReading,ManuscriptReviewStatus,ScientificDocuments,PhaseOverview} from '${src}/components/PhaseReading.jsx'; import Issues from '${src}/components/IssuesCard.jsx'; import Conversations from '${src}/components/AssumptionConversations.jsx'; import Empirical from '${src}/components/EmpiricalWorkbench.jsx'; const calls=[]; for(const key of ['startRun','assessmentMessage','resolveAttention','continueRun']) api[key]=(...args)=>{calls.push([key,args]);throw new Error('Unexpected request from rendering');}; const show=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const statement=props=>show(TheoryStatement,props); export const manuscript=props=>show(ManuscriptReading,props); export const reviewStatus=props=>show(ManuscriptReviewStatus,props); export const documents=props=>show(ScientificDocuments,props); export const overview=props=>show(PhaseOverview,props); export const issues=props=>show(Issues,props); export const conversation=props=>show(Conversations,props); export const empirical=props=>show(Empirical,props); export const requests=calls;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const ref = { branch: "method.a", phase: "P3", family: "theory_record", generation_id: "theory.v1", sha256: "a".repeat(64), run_id: "run.theory", package_id: "package.theory" };
const issueTarget = { ...ref, kind: "phase_issue", object_id: "issue.independence", entry_pointer: "/open_obligations/0" };
const issue = { issue_id: "issue.independence", branch: "method.a", phase: "P3", target_phase: "P4", kind: "researcher_decision", title: "Which dependence regime should be studied?", summary_markdown: "The independent-data result does not settle performance under dependence.", context_markdown: "The coupling argument needs a quantitative dependence condition.", consequence_markdown: "A different regime changes the comparisons worth running.", responsible_role: "theorist", disposition: "open", generation_ref: { ...ref, entry_pointer: issueTarget.entry_pointer }, explanation_target: issueTarget };
const button = (html, text) => (html.match(/<button\b[^>]*>[\s\S]*?<\/button>/g) || []).find((item) => item.includes(text)) || "";

test("P3 and P5 overviews preserve distinct contribution, uncertainty, risk and disagreement accounts", () => {
  const decision = { conclusion: "The frozen analysis establishes an interior result.", fundamental_contribution: "The new argument separates estimation from optimization error.", principal_uncertainty: "The boundary term has not been bounded.", principal_risk: "Reusing the result outside its stated domain could give a wrong decision.", material_disagreement: ["The analyst questions whether the sample condition can be checked."], what_changed: "The domain was narrowed to positive weights.", generation_ref: ref };
  for (const phase of ["P3", "P5"]) {
    const html = render.overview({ phase, decision, onSource: noop });
    for (const text of [decision.conclusion, decision.fundamental_contribution, decision.principal_uncertainty, decision.principal_risk, decision.material_disagreement[0]]) assert.ok(html.includes(text), text);
    assert.equal((html.match(/data-card-role="summary"/g) || []).length, 1);
    if (phase === "P3") assert.match(html, /The domain was narrowed to positive weights/);
    else assert.doesNotMatch(html, /The domain was narrowed to positive weights/);
  }
  const missing = render.overview({ phase: "P5", decision: { conclusion: "Only a conclusion was recorded." } });
  assert.doesNotMatch(missing, /<h3>Contribution|Main uncertainty|Main risk or limitation|Unresolved differences/);
});

test("P5 Changes preserves the lead change account beside the distinct revision record", () => {
  const decision = { what_changed: "The manuscript now restricts its guarantee to independent samples.", generation_ref: { ...ref, phase: "P5", family: "decision" } };
  const html = render.manuscript({ initialTab: "changes", decision, documents: [{ kind: "revision_account", title: "Revision details", body_md: "The proof appendix adds the missing conditioning step." }], onSource: noop });
  assert.match(html, /restricts its guarantee to independent samples/); assert.match(html, /missing conditioning step/); assert.match(html, /Change account source/); assert.doesNotMatch(html, /No revision account has been recorded/);
  const onlyDecision = render.manuscript({ initialTab: "changes", decision, onSource: noop });
  assert.match(onlyDecision, /restricts its guarantee/); assert.doesNotMatch(onlyDecision, /No revision account has been recorded/);
});

test("historical P4 projection never carries the current summary, cases or figures into an older run", () => {
  const current = empiricalReaderProps({ empirical_summaries: [{ decision_summary: { conclusion_markdown: "Current-only conclusion" } }], cases: [{ case_id: "current.case" }], exhibits: [{ exhibit_id: "current.plot" }] });
  const priorRef = { ...ref, phase: "P4", family: "protocol", generation_id: "prior.protocol", run_id: "run.prior", package_id: "package.prior" };
  const old = { empirical_summaries: [{ decision_summary: { conclusion_markdown: "Earlier-only conclusion" } }], case_manifests: [{ branch: "method.a", generation_ref: priorRef, cases: [{ case_id: "prior.case", label: "Earlier setting" }] }], questions: [], protocols: [] };
  const prior = { ...current, ...empiricalReaderProps(old) };
  assert.equal(prior.summaries[0].decision_summary.conclusion_markdown, "Earlier-only conclusion");
  assert.deepEqual(prior.cases.map((item) => item.case_id), ["prior.case"]); assert.equal(prior.cases[0].generation_ref, priorRef); assert.deepEqual(prior.exhibits, []);
  const html = render.empirical({ ...prior, branch: "method.a" }); assert.match(html, /Earlier-only conclusion/); assert.doesNotMatch(html, /Current-only conclusion|current.case|current.plot/);
  const empty = { ...current, ...empiricalReaderProps({}) }; assert.deepEqual(empty.summaries, []); assert.deepEqual(empty.cases, []);
});

test("issues stay in their source phase and exact method while explaining the destination of an answer", () => {
  const items = [issue, { ...issue, issue_id: "other.method", branch: "method.b" }, { ...issue, issue_id: "p4.native", phase: "P4" }];
  assert.deepEqual(issuesForPhase(items, "P3", "method.a").map((item) => item.issue_id), [issue.issue_id]);
  assert.deepEqual(issuesForPhase(items, "P4", "method.a").map((item) => item.issue_id), ["p4.native"]);
  const p2 = ["method.a", "method.b"].map((id) => ({ ...issue, phase: "P2", branch: "trunk", issue_id: id, affected_record_ids: [id] }));
  assert.deepEqual(issuesForPhase(p2, "P2", "branch.a", "method.a").map((item) => item.issue_id), ["method.a"]);
  const shared = { ...p2[0], issue_id: "shared", affected_record_ids: [] };
  assert.deepEqual(issuesForPhase([...p2, shared], "P2", "branch.a", "method.a").map((item) => item.issue_id), ["method.a", "shared"]);
  assert.match(render.issues({ projectId: "p", phase: "P2", branch: "branch.a", methodId: "method.a", issues: [shared] }), /Shared across the proposed models/);
  const html = render.issues({ projectId: "project.a", phase: "P3", branch: "method.a", issues: items, onExplain: noop });
  assert.match(html, /Which dependence regime/); assert.match(html, /intended for numerical evaluation/); assert.doesNotMatch(html, /other.method|p4.native/);
  assert.notEqual(furtherWorkKey("p", "method.a", "P4"), furtherWorkKey("p", "method.b", "P4"));
});

test("saved responses distinguish currently used instructions from an edited revision for future work", () => {
  assert.match(answerEffect({ applied_to: ["run.used"] }), /Used in earlier work/);
  assert.match(answerEffect({ applied_to: [], previously_applied_to: ["run.old"] }), /Earlier work used your previous response/);
  assert.match(answerEffect({}), /Saved for future work/);
  const html = render.issues({ projectId: "project.a", phase: "P3", branch: "method.a", issues: [{ ...issue, researcher_answer: { note: "Study weak dependence first.", applied_to: [], previously_applied_to: ["run.old"] } }] });
  assert.match(html, /Study weak dependence first/); assert.match(html, /Earlier work used your previous response/); assert.match(html, /Edit instruction/); assert.doesNotMatch(html, /<textarea/);
});

test("issues distinguish scientific work from researcher questions and omit an empty card", () => {
  const scientific = render.issues({ projectId: "p", phase: "P3", branch: "method.a", issues: [{ ...issue, kind: "research_task" }] });
  assert.match(scientific, /Open scientific work/); assert.match(scientific, /further work request below/); assert.doesNotMatch(scientific, /<textarea|Add your direction|Save response/);
  const finding = render.issues({ projectId: "p", phase: "P3", branch: "method.a", issues: [{ ...issue, kind: "scientific_issue" }] });
  assert.match(finding, /Open scientific work/); assert.match(finding, /further work request below/); assert.doesNotMatch(finding, /<textarea|Save instruction/);
  const question = render.issues({ projectId: "p", phase: "P3", branch: "method.a", issues: [issue] }); assert.match(question, /1 question needs your response/); assert.match(question, /Your input needed/); assert.match(question, /<textarea/);
  const empty = render.issues({ projectId: "p", phase: "P3", branch: "method.a" }); assert.equal(empty, "");
  assert.match(render.issues({ projectId: "p", phase: "P3", branch: "method.a", correctionCount: 1 }), /Work needs correction/);
  assert.match(render.issues({ projectId: "p", phase: "P4", branch: "method.a", activePause: true }), /Evaluation waiting for your direction/);
  assert.match(render.issues({ projectId: "p", phase: "P4", branch: "method.a", savedPauseCount: 1 }), /Recorded issues and responses/);
});

test("a revised issue receives a separate editor while answer changes preserve the same question identity", () => {
  assert.notEqual(issueVersionKey(issue), issueVersionKey({ ...issue, explanation_target: { ...issueTarget, sha256: "b".repeat(64) } }));
  assert.notEqual(issueVersionKey({ ...issue, explanation_target: null, generation_ref: null }), issueVersionKey({ ...issue, explanation_target: null, generation_ref: null, question: "A different question" }));
  assert.equal(issueVersionKey(issue), issueVersionKey({ ...issue, researcher_answer: { note: "Updated", revision: 2 } }));
});

test("theory statements preserve mathematics, quantifiers, violation consequences and open proof obligations", () => {
  const statement = { text: "The estimator is consistent under the stated dependence condition.", latex: "\\hat\\theta_n\\xrightarrow{p}\\theta_0", regime: "The sample size tends to infinity with fixed dimension.", quantifiers: ["Uniformly over the compact parameter set."], sensitivity: "Without the dependence bound, the variance estimate need not vanish.", justification: { kind: "proof_sketch", summary: "Apply a maximal inequality and then use identifiability.", open_obligation: "The required maximal inequality is not yet proved.", artifacts: [{ artifact_id: "proof.source", locator: "Appendix B, Lemma 4" }] } };
  const before = JSON.stringify(statement); const html = render.statement({ statement, reference: ref, onSource: noop });
  for (const text of ["class=\"katex", "fixed dimension", "Uniformly over", "variance estimate need not vanish", "use identifiability", "not yet proved", "Appendix B, Lemma 4"]) assert.ok(html.includes(text), text);
  assert.equal(JSON.stringify(statement), before);
});

test("P5 names exactly what was reviewed without treating a subsequent revision as independently reviewed", () => {
  const reviewed = { ...ref, phase: "P5", family: "manuscript", generation_id: "draft.reviewed" };
  const cases = { not_reviewed: /has not received an independent review/, reviewed: /assessed this exact draft/, revised_after_review: /present revision has not itself been independently reviewed/, earlier_draft_review: /available reviews concern an earlier draft/, reviewed_draft_unavailable: /draft it assessed could not be identified/ };
  for (const [status, message] of Object.entries(cases)) {
    const html = render.reviewStatus({ context: { status, reviewed_manuscript_ref: status === "not_reviewed" ? null : reviewed }, onSource: noop }); assert.match(html, message);
    if (status !== "not_reviewed") assert.match(html, /Read the reviewed draft/);
  }
});

test("the manuscript remains readable and retained reviews keep their own finding and stale-method notice", () => {
  const manuscript = { kind: "manuscript", title: "Full research draft", body_md: "# Main result\nThe complete argument is preserved.\n\n$$x^2=1.$$", generation_ref: { ...ref, phase: "P5", family: "manuscript" }, primary_artifact_url: "/api/v1/original-paper" };
  const html = render.manuscript({ documents: [manuscript], onSource: noop }); assert.match(html, /The complete argument is preserved/); assert.match(html, /class="katex/); assert.match(html, /Open original document/);
  const ledger = render.documents({ documents: [{ kind: "review_issue_ledger", structured: { issues: [{ issue: "Unresolved reviewer criticism.", requested_resolution: "Report the tuning rule." }] }, generation_ref: ref, method_status: { status: "needs_update", current_version: 2, recorded_version: 1 } }], onSource: noop });
  assert.match(ledger, /Unresolved reviewer criticism/); assert.match(ledger, /Report the tuning rule/); assert.match(ledger, /earlier manuscript version/); assert.match(ledger, /Needs update/);
});

test("issue and pause explanation targets retain the exact source fields through submission projection", () => {
  const target = issueSourceTarget(issue); const before = JSON.stringify(issue);
  assert.equal(target.responsible_role, "theorist"); assert.equal(target.label, issue.title);
  assert.deepEqual(assumptionSource(target), issueTarget); assert.equal(assumptionSource(target).package_id, "package.theory");
  assert.equal(isConversationTarget(target), true); assert.equal(isConversationTarget({ ...target, entry_pointer: undefined }), false);
  const pause = { kind: "p4_pause", phase: "P4", branch: "method.a", run_id: "run.waiting", request_id: "request.one", object_id: "request.one", revision: 3, sha256: "d".repeat(64), label: "Latency choice", statement: "Which limit matters?" };
  const frozen = assumptionSource(pause); assert.equal(frozen.request_id, "request.one"); assert.equal(frozen.revision, 3); assert.equal(frozen.sha256, pause.sha256); assert.equal(frozen.run_id, "run.waiting"); assert.equal(isConversationTarget(frozen), true);
  assert.notEqual(conversationDraftKey("p", pause), conversationDraftKey("p", { ...pause, revision: 4 })); assert.equal(JSON.stringify(issue), before);
});

test("saved explanation history stays with the issue, method and source version", () => {
  const current = { assessment_id: "current", assessment_purpose: "issue_explanation", target: issueTarget, created_at: "2026-09-26" };
  const older = { ...current, assessment_id: "old", target: { ...issueTarget, generation_id: "theory.v0", sha256: "b".repeat(64) }, created_at: "2026-09-25" };
  const other = { ...current, assessment_id: "other", target: { ...issueTarget, branch: "method.b" } };
  assert.deepEqual(conversationsForTarget([older, other, current], issueTarget).map((item) => item.assessment_id), ["current", "old"]);
  assert.equal(isEarlierConversation(current, issueTarget), false); assert.equal(isEarlierConversation(older, issueTarget), true);
  assert.equal(explanationRun({ assessment_purpose: "issue_explanation" }), true); assert.equal(explanationRun({ assessment_purpose: "scientific_assessment" }), false);
});

test("opening explanation UI does not submit work and requires an explicit question", () => {
  render.requests.length = 0;
  const html = render.issues({ projectId: "p", phase: "P3", branch: "method.a", issues: [issue], onExplain: noop });
  assert.match(button(html, "Discuss"), /type="button"/); assert.match(button(html, "Discuss"), /aria-haspopup="dialog"/);
  const conversation = render.conversation({ projectId: "p", target: issueSourceTarget(issue), onClose: noop, onStarted: noop });
  assert.match(conversation, /About this issue/); assert.match(conversation, /Your question/); assert.match(button(conversation, ">Discuss<"), /disabled=""/); assert.deepEqual(render.requests, []);
  assert.match(conversation, /Saving a response is a separate action/);
});
