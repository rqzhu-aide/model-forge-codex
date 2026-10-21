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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-theory-assessment-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Theory from '${src}/components/TheoryWorkbench.jsx'; import {TheoryReading,TheoryStatement,PhaseOverview} from '${src}/components/PhaseReading.jsx'; import {P3ProofAudit} from '${src}/components/PhaseEvidence.jsx'; import {OriginalTheoristAccount} from '${src}/components/TheoryAssessment.jsx'; const show=Component=>props=>renderToStaticMarkup(React.createElement(Component,props)); export const graph=show(Theory); export const reader=show(TheoryReading); export const statement=show(TheoryStatement); export const inventory=show(P3ProofAudit); export const overview=show(PhaseOverview); export const graphComponent=Theory; export const originalComponent=OriginalTheoristAccount; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const canonical = { branch: "method.assessment", phase: "P3", family: "theory_record", generation_id: "theory.current", sha256: "a".repeat(64), run_id: "run.current", package_id: "package.current" };
const originalRef = { ...canonical, family: "theory_candidate", generation_id: "theory.original", sha256: "b".repeat(64), entry_pointer: "/statements/0", object_id: "statement.rate" };
const decisionRef = { ...canonical, family: "decision", generation_id: "decision.current", sha256: "c".repeat(64), entry_pointer: "/assessment_changes/0", object_id: "statement.rate" };
const issueRef = { ...canonical, family: "analyst_handoff", generation_id: "handoff.analyst", sha256: "d".repeat(64), entry_pointer: "/unresolved_issues/0", object_id: "issue.boundary" };
const originalProof = { kind: "proof", summary: "The submitted proof controls the remainder uniformly.", locator: "Theorem 1", artifacts: [{ title: "Submitted proof", locator: "Section 2", artifact_url: "/api/proof/original-exact" }] };
const claim = { statement_id: "statement.rate", label: "Rate guarantee", text: "The error has the specified rate.", latex: String.raw`\sqrt n(\widehat\theta_n-\theta_0)=O_p(1)`, regime: "As sample size grows.", quantifiers: ["For each fixed positive tolerance."], status: "incomplete", proof_status: "full", depends_on: [], justification: originalProof,
  assessment_context: { origin: "lead_concern", reason: "Uniform control remains unresolved; this is an unreviewed Lead concern.", generation_ref: decisionRef },
  theorist_account: { status: "established", proof_status: "full", justification: originalProof, generation_ref: originalRef }, original_justification_retained: true };
const propsFor = (statement, extra = {}) => ({ branch: canonical.branch, selected: statement.statement_id || statement.assumption_id, onSelect: noop, onRequest: noop, onSource: noop,
  claimMaps: [{ branch: canonical.branch, phase: "P3", theory_generation_ref: canonical, claims: statement.statement_id ? [statement] : [], assumptions: statement.assumption_id ? [statement] : [] }], falsificationLogs: [], ...extra });
const originalDisclosures = (html) => [...html.matchAll(/<details class="research-details theory-original-account">[\s\S]*?<\/details>/g)].map(([block]) => block);
const currentContent = (html) => html.replace(/<details class="research-details theory-original-account">[\s\S]*?<\/details>/g, "");
const nodeMarkup = (html, label) => [...html.matchAll(/<g\b[^>]*class="theory-node"[^>]*>[\s\S]*?<\/g>/g)].map(([node]) => node).find((node) => node.includes(`aria-label="${label}.`));
const surfaces = (statement) => {
  const props = propsFor(statement);
  return { graph: ui.graph(props), arguments: ui.reader({ ...props, reading: { tab: "arguments" } }), inventory: ui.inventory(props) };
};

test("Lead-own incomplete is current across graph, accessibility, Arguments and inventory; submitted proof stays collapsed", () => {
  for (const proof_status of ["full", "cited", undefined]) {
    const statement = { ...claim, proof_status }; const before = JSON.stringify(statement);
    const rendered = surfaces(statement);
    const node = nodeMarkup(rendered.graph, statement.label);
    assert.match(node, /aria-label="Rate guarantee\. Claim\. Incomplete"/);
    assert.match(node, /data-tone="warn"/); assert.match(node, /role="button" tabindex="0"/);
    assert.doesNotMatch(node, /Full proof|Cited proof|Proof not recorded|Needs proof support|stroke-dasharray/);
    for (const [surface, html] of Object.entries(rendered)) {
      const open = currentContent(html); assert.match(open, /Incomplete/, surface);
      assert.doesNotMatch(open, /Full proof|Needs proof support|Proof not recorded|submitted proof controls|api\/proof\/original-exact/);
      const originals = originalDisclosures(html); assert.ok(originals.length, surface);
      for (const original of originals) { assert.match(original, /^<details[^>]*><summary>Original theorist account/); assert.doesNotMatch(original, / open=/); assert.match(original, /Theorist submitted status: Established/); assert.match(original, /Theorist submitted proof assessment: Full proof/); assert.match(original, /Original theorist source/); }
      if (surface !== "inventory") { assert.match(open, /Research Lead assessment/); assert.match(open, /has not received independent Analyst review/); assert.match(open, /Uniform control remains unresolved/); assert.match(open, /Lead assessment source/); assert.doesNotMatch(open, /Original Analyst concern|review consensus/); assert.equal(html.split(originalProof.summary).length - 1, 1); assert.match(html, /api\/proof\/original-exact/); assert.match(html, /class="katex/); assert.doesNotMatch(html, /katex-error/); }
    }
    assert.equal(JSON.stringify(statement), before);
  }
});

test("Analyst contradiction presents canonical negative support before the attributed original proof without a new proof verdict", () => {
  const counterexample = { kind: "counterexample", summary: "The retained boundary example violates the stated rate.", artifacts: [{ title: "Analyst boundary example", artifact_url: "/api/support/analyst-exact" }] };
  for (const proof_status of ["full", undefined]) {
    const statement = { ...claim, status: "contradicted", proof_status, justification: counterexample, assessment_context: { origin: "analyst_issue", reason: "The exact Analyst example defeats this guarantee.", generation_ref: decisionRef, issue_ref: issueRef }, original_justification_retained: false };
    const rendered = surfaces(statement); const node = nodeMarkup(rendered.graph, statement.label);
    assert.match(node, /aria-label="Rate guarantee\. Claim\. Contradicted"/); assert.match(node, /data-tone="fail"/); assert.doesNotMatch(node, /Full proof|Needs proof support|Proof not recorded/);
    for (const [surface, html] of Object.entries(rendered)) {
      const open = currentContent(html); assert.match(open, /Contradicted/); assert.doesNotMatch(open, /Full proof|Needs proof support|Proof not recorded|submitted proof controls/);
      if (surface !== "inventory") { assert.match(open, /Current support from the Analyst/); assert.match(open, /retained boundary example violates/); assert.match(open, /api\/support\/analyst-exact/); assert.match(open, /Original Analyst concern/); assert.doesNotMatch(open, /has not received independent Analyst review/); assert.ok(html.indexOf(counterexample.summary) < html.indexOf("Original theorist account")); }
      assert.match(originalDisclosures(html)[0], /Theorist submitted proof assessment: Full proof/);
    }
  }
});

test("retained-argument display follows the backend comparison and never compares enriched proof URLs", () => {
  const currentProof = { ...originalProof, artifacts: [{ ...originalProof.artifacts[0], artifact_url: "/api/proof/canonical-exact" }] };
  const retained = ui.statement({ statement: { ...claim, justification: currentProof }, reference: canonical, onSource: noop });
  assert.doesNotMatch(currentContent(retained), /submitted proof controls|api\/proof\/canonical-exact/);
  assert.match(originalDisclosures(retained)[0], /api\/proof\/original-exact/);
  const unresolvedComparison = ui.statement({ statement: { ...claim, original_justification_retained: undefined }, reference: canonical, onSource: noop });
  assert.match(currentContent(unresolvedComparison), /submitted proof controls/);
  assert.match(originalDisclosures(unresolvedComparison)[0], /submitted proof controls/);
  assert.doesNotMatch(currentContent(unresolvedComparison), /Full proof/);
});

test("unchanged and legacy claims retain proof warnings and labels without fabricated role accounts", () => {
  const { assessment_context, theorist_account, original_justification_retained, ...unchanged } = claim;
  for (const status of ["established", "conditional", "incomplete"]) {
    for (const proof_status of ["full", "missing", undefined]) {
      const rendered = surfaces({ ...unchanged, status, proof_status });
      const node = nodeMarkup(rendered.graph, unchanged.label);
      assert.match(node, proof_status === "full" ? /Claim · Full proof/ : /Needs proof support/);
      for (const [surface, html] of Object.entries(rendered)) { assert.doesNotMatch(html, /Original theorist account|Research Lead assessment|Lead assessment source/); if (surface !== "inventory") assert.match(html, /submitted proof controls/); }
    }
  }
});

test("changed legacy and missing-source cases preserve current status without inventing an attribution or source", () => {
  const { assessment_context, ...legacyChanged } = claim;
  const missingAttribution = { ...legacyChanged, assessment_source_error: "No exact attributed change account is retained." };
  const missingOriginal = { ...claim, theorist_account: undefined, original_justification_retained: undefined, assessment_source_error: "The exact original candidate bytes are unavailable." };
  const originalSourceUnavailable = { ...claim, theorist_account: { ...claim.theorist_account, generation_ref: { generation_id: "wrong-guessed-generation" }, source_error: "The original source cannot be resolved." } };
  for (const statement of [missingAttribution, missingOriginal, originalSourceUnavailable]) {
    const rendered = surfaces(statement); assert.doesNotMatch(nodeMarkup(rendered.graph, claim.label), /Full proof|Needs proof support|Proof not recorded/);
    for (const html of Object.values(rendered)) { assert.match(currentContent(html), /Incomplete/); assert.ok(originalDisclosures(html).length); assert.doesNotMatch(html, /title="[^"]*wrong-guessed-generation/); }
    if (statement === missingAttribution) { for (const html of [rendered.graph, rendered.arguments]) { assert.match(html, /No exact attributed change account is retained/); assert.doesNotMatch(html, /Research Lead assessment|has not received independent Analyst review/); assert.doesNotMatch(currentContent(html), /submitted proof controls/); } }
    if (statement === missingOriginal) assert.match(rendered.arguments, /original theorist account is unavailable/);
    if (statement === originalSourceUnavailable) assert.match(rendered.arguments, /original source cannot be resolved/);
  }
});

test("assumption reassessment retains exact conditions, current status and original attribution without claim proof labels", () => {
  const assumption = { assumption_id: "assumption.overlap", label: "Positive overlap", status: "unverified", text: "Each probability is positive.", latex: String.raw`p(x)>0`, strength: String.raw`p(x)\geq\varepsilon`, sensitivity: "Without overlap the guarantee does not apply.", assessment_context: { ...claim.assessment_context, generation_ref: { ...decisionRef, object_id: "assumption.overlap", entry_pointer: "/assessment_changes/1" } }, theorist_account: { status: "active", generation_ref: { ...originalRef, object_id: "assumption.overlap", entry_pointer: "/assumptions/0" } } };
  const before = JSON.stringify(assumption); const props = propsFor(assumption);
  props.claimMaps[0].claims = [{ statement_id: "statement.uses_overlap", label: "Claim using overlap", proof_status: "sketch", status: "conditional", depends_on: [assumption.assumption_id] }];
  const graph = ui.graph(props); const reader = ui.reader({ ...props, reading: { tab: "assumptions" } });
  assert.match(nodeMarkup(graph, assumption.label), /Assumption\. Unverified/); assert.match(nodeMarkup(graph, assumption.label), /data-tone="warn"/);
  for (const html of [graph, reader]) { assert.match(currentContent(html), /Unverified/); assert.match(html, /Theorist submitted status: Active/); assert.match(html, /Without overlap the guarantee/); assert.match(html, /class="katex/); assert.doesNotMatch(html, /katex-error|Theorist submitted proof assessment|Full proof|Needs proof support/); }
  assert.equal(JSON.stringify(assumption), before);
});

test("same-run original account stays distinct from prior-publication established versus current incomplete", () => {
  const props = propsFor(claim); props.claimMaps[0].revision_changes = [{ label: claim.label, before: { text: "Earlier publication used a stronger regime.", status: "established" }, after: { text: claim.text, status: "incomplete" }, reason: "The current publication narrows the assessment." }];
  const html = ui.graph(props); assert.match(html, /Previously/); assert.match(html, /Earlier publication used a stronger regime/); assert.match(html, /Status: Established/); assert.match(html, /Now/); assert.match(html, /Status: Incomplete/);
  assert.match(originalDisclosures(html)[0], /Theorist submitted status: Established/); assert.doesNotMatch(originalDisclosures(html)[0], /Earlier publication used/);
});

test("resolved Lead response retains independent open concern and sources, with overview attribution", () => {
  const issue = { issue_id: "issue.boundary", title: "Boundary concern", issue: "The Analyst contests the boundary guarantee.", status: "open" };
  const props = propsFor(claim); props.claimMaps[0].issue_dispositions = [{ issue_id: issue.issue_id, status: "resolved", reason: "The Lead limits reliance on that guarantee.", generation_ref: { ...decisionRef, entry_pointer: "/issue_dispositions/0" }, issue, issue_ref: issueRef }];
  const documents = [{ kind: "analyst_audit", title: "Independent Analyst audit", body_md: "The independent boundary concern remains recorded.", structured: { issues: [issue] }, generation_ref: issueRef }];
  const before = JSON.stringify({ documents, responses: props.claimMaps[0].issue_dispositions });
  const html = ui.reader({ ...props, documents, reading: { tab: "review" } });
  assert.match(html, /Independent Analyst audit/); assert.match(html, /independent boundary concern remains recorded/); assert.match(html, /Open/); assert.match(html, /Lead response: Resolved/); assert.match(html, /Original Analyst concern/); assert.match(html, /Lead response source/); assert.doesNotMatch(html, /consensus|Analyst agrees/);
  assert.ok(html.indexOf("Independent Analyst audit") < html.indexOf("Research Lead responses"));
  assert.equal(JSON.stringify({ documents, responses: props.claimMaps[0].issue_dispositions }), before);
  const overview = ui.overview({ phase: "P3", decision: { conclusion: "The current rate guarantee remains incomplete.", generation_ref: decisionRef }, onSource: noop }); assert.match(overview, /Research Lead assessment/); assert.match(overview, /current rate guarantee remains incomplete/);
});

// Invoke the shipped graph controls with deterministic hook state, without a
// browser or model request. Exact target routing is separate from SSR checks.
function componentTree(Component, props) {
  const previous = ui.dispatcher.current;
  ui.dispatcher.current = { useState: (value) => [value, noop], useEffect: noop, useRef: (value) => ({ current: value }), useMemo: (factory) => factory(), useId: () => "assessment-fixture" };
  try { return Component(props); } finally { ui.dispatcher.current = previous; }
}
function nodes(tree) { return Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : []; }
function renderedNodes(tree) { return Array.isArray(tree) ? tree.flatMap(renderedNodes) : tree?.props ? typeof tree.type === "function" ? renderedNodes(componentTree(tree.type, tree.props)) : [tree, ...renderedNodes(tree.props.children)] : []; }

test("requests retain exact canonical target while the original disclosure opens only its exact candidate source", () => {
  const requests = []; const sources = []; const props = propsFor(claim, { onRequest: (...args) => requests.push(args), onSource: (ref) => sources.push(ref) });
  const tree = componentTree(ui.graphComponent, props);
  for (const action of ["check", "repair"]) nodes(tree).find((node) => node.props.action === action).props.onClick();
  for (const [mode, target] of requests) { assert.ok(["assessment", "repair"].includes(mode)); assert.deepEqual(target, { ...canonical, object_id: claim.statement_id, kind: "statement" }); assert.notEqual(target.generation_id, originalRef.generation_id); }
  const originalTree = ui.originalComponent({ statement: claim, onSource: props.onSource });
  renderedNodes(originalTree).find((node) => node.type === "button" && node.props.className === "source-link ui-action").props.onClick();
  assert.deepEqual(sources, [originalRef]);
  const assumption = { assumption_id: "assumption.rate", label: "Rate condition", status: "unverified", text: "This rate is assumed.", assessment_context: claim.assessment_context, theorist_account: { status: "active", generation_ref: { ...originalRef, object_id: "assumption.rate", entry_pointer: "/assumptions/0" } } };
  const assumptionProps = propsFor(assumption, { onAssumptionConversation: (ref) => sources.push(ref), onRequest: (...args) => requests.push(args) });
  assumptionProps.claimMaps[0].claims = [{ statement_id: "statement.uses_rate", proof_status: "sketch", depends_on: [assumption.assumption_id] }];
  const assumptionTree = componentTree(ui.graphComponent, assumptionProps);
  nodes(assumptionTree).find((node) => node.props.action === "ask").props.onClick();
  nodes(assumptionTree).find((node) => node.props.action === "repair").props.onClick();
  assert.deepEqual(requests.at(-1)[1], { ...canonical, object_id: assumption.assumption_id, kind: "assumption" });
  assert.equal(sources.at(-1).family, "theory_record"); assert.equal(sources.at(-1).generation_id, canonical.generation_id); assert.equal(sources.at(-1).object_id, assumption.assumption_id);
});
