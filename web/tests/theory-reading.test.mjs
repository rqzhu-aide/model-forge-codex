import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { isTheoryComponentTarget, modesForRequest, targetIsStale, theoryComponentRequest } from "../src/runRequests.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-theory-reading-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Theory from '${src}/components/TheoryWorkbench.jsx'; import {TheoryConditions} from '${src}/components/TheoryConditions.jsx'; import {TheoryStatement,ScientificDocuments} from '${src}/components/PhaseReading.jsx'; import Assessments,{assessmentRepairRequest} from '${src}/components/Assessments.jsx'; import TestedTheory from '${src}/components/TestedTheorySource.jsx'; const render=Component=>props=>renderToStaticMarkup(React.createElement(Component,props)); export const graph=render(Theory); export const conditions=render(TheoryConditions); export const statement=render(TheoryStatement); export const documents=render(ScientificDocuments); export const assessments=render(Assessments); export const tested=render(TestedTheory); export const revisionRequest=assessmentRepairRequest;`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const reference = { branch: "method.conditions", phase: "P3", family: "theory_record", generation_id: "theory.current", sha256: "a".repeat(64), run_id: "run.current" };
const assumption = {
  assumption_id: "assumption.regularization", label: "Vanishing regularization", text: String.raw`The tuning sequence satisfies $\lambda_n\to0$.`, latex: String.raw`\lambda_n\to0`,
  strength: { text: "The rate is required by the recorded bound.", latex: String.raw`\sqrt{n}\lambda_n\to0` },
  sensitivity: String.raw`Without $\sqrt{n}\lambda_n\to0$, the argument for the consistency claim loses its guarantee. This does not demonstrate failure of $\widehat\theta_n$.`,
};
const claim = {
  statement_id: "statement.consistency", label: "Consistency claim", text: String.raw`The error converges to zero in probability.`, latex: String.raw`\widehat\theta_n\xrightarrow{p}\theta_0`,
  regime: String.raw`As $n\to\infty$, require $\lambda_n\to0$ and $\sqrt{n}\lambda_n\to0$.`,
  quantifiers: [String.raw`For every $\varepsilon>0$, the assertion concerns $\Pr(\lvert\widehat\theta_n-\theta_0\rvert>\varepsilon)$.`],
  proof_status: "sketch", status: "conditional", depends_on: [assumption.assumption_id], assumption_ids: [assumption.assumption_id],
  justification: { kind: "proof_sketch", summary: String.raw`Control the remainder by $\sqrt{n}\lambda_n$.`, open_obligation: "A uniform remainder bound remains open.", locator: "Argument, section 2", artifacts: [{ title: "Retained argument", locator: "Lemma 2", sha256: "b".repeat(64), artifact_url: `/api/proof/retained?sha256=${"b".repeat(64)}` }] },
};
const graphProps = (selected, changes = {}) => ({
  branch: reference.branch, selected, onSelect: noop, onRequest: noop, onSource: noop, onAssumptionConversation: noop,
  claimMaps: [{ branch: reference.branch, phase: "P3", theory_generation_ref: reference, claims: [claim], assumptions: [assumption], ...changes }],
});
const inspectedNode = (html, label) => [...html.matchAll(/<g\b[^>]*class="theory-node"[^>]*>[\s\S]*?<\/g>/g)].map(([node]) => node).find((node) => node.includes(`aria-label="${label}.`));

test("independent P3 audit retains its manuscript, findings and separate disagreement without metadata", () => {
  const audit = {
    kind: "analyst_audit", title: "Independent audit by Data Analyst", producer_role: "data_analyst",
    generation_ref: { ...reference, family: "analyst_audit", stage_id: "p3.analyst" },
    body_md: "The full analyst account identifies an overlap boundary.",
    structured: { record_id: "INTERNAL_RECORD_IDENTIFIER", content_sha256: "INTERNAL_CONTENT_DIGEST", worker_manual: "INTERNAL_WORKER_MANUAL",
      scientific_outcome: { state: "partially_supported", conclusion: "Identification requires positive overlap.", material_disagreement: ["The analyst contests the operational scope of the uniform claim."] },
      issues: [{ title: "Overlap boundary", issue: "Zero weights leave the target unidentified.", scientific_consequence: "The guarantee does not cover the boundary.", status: "open" }] },
  };
  const before = JSON.stringify(audit);
  const html = render.documents({ documents: [audit], onSource: noop });
  for (const text of ["Independent audit by Data Analyst", "full analyst account", "requires positive overlap", "contests the operational scope", "Zero weights leave", "does not cover the boundary", "Open source"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /INTERNAL_RECORD_IDENTIFIER|INTERNAL_CONTENT_DIGEST|INTERNAL_WORKER_MANUAL/);
  assert.equal(JSON.stringify(audit), before);
});

test("graph and complete reader keep identical authored condition mathematics", () => {
  const before = JSON.stringify({ assumption, claim });
  for (const statement of [assumption, claim]) {
    const id = statement.assumption_id || statement.statement_id;
    const conditions = render.conditions({ statement });
    const graph = render.graph(graphProps(id));
    const reader = render.statement({ statement, reference, onSource: noop });
    assert.ok(graph.includes(conditions)); assert.ok(reader.includes(conditions));
    if (statement.status) assert.match(reader, /Statement status: Conditional/);
    for (const html of [conditions, graph, reader]) { assert.match(html, /class="katex/); assert.doesNotMatch(html, /katex-error/); }
  }
  const graph = render.graph(graphProps(claim.statement_id));
  assert.match(inspectedNode(graph, claim.label), /Conditional/);
  assert.match(graph, /Uniform remainder bound remains open\.|uniform remainder bound remains open\./);
  assert.ok(graph.includes(claim.justification.artifacts[0].artifact_url));
  assert.match(graph, /Retained argument · Lemma 2/); assert.match(graph, /Argument, section 2/);
  assert.equal(JSON.stringify({ assumption, claim }), before);
});

test("loss of a guarantee, unknown consequences and unperformed probes do not imply failure or proof", () => {
  const graph = render.graph(graphProps(assumption.assumption_id));
  assert.match(graph, /loses its guarantee/); assert.match(graph, /does not demonstrate failure/);
  assert.doesNotMatch(inspectedNode(graph, assumption.label), /data-tone="fail"|Probe failed/);
  const unknown = { ...assumption, sensitivity: "The consequence is unknown; a boundary argument is still needed." };
  const unknownGraph = render.graph(graphProps(unknown.assumption_id, { assumptions: [unknown] }));
  assert.match(unknownGraph, /consequence is unknown/); assert.doesNotMatch(inspectedNode(unknownGraph, unknown.label), /data-tone="fail"/);
  const unperformed = render.graph({ ...graphProps(claim.statement_id, { claims: [{ ...claim, proof_status: "missing" }] }), falsificationLogs: [{ branch: reference.branch, phase: "P3", probes: [{ probe_id: "probe.boundary", target_statement: claim.statement_id, outcome: "not_tested", method: "Boundary case", detail: "This case has not been performed." }] }] });
  assert.match(unperformed, /Proof missing/); assert.match(unperformed, /Not tested/); assert.doesNotMatch(inspectedNode(unperformed, claim.label), /Probe failed|Full proof/);
});

test("missing sensitivity and proof files are reported without inventing scientific conclusions", () => {
  const { sensitivity, ...older } = assumption;
  const graph = render.graph(graphProps(older.assumption_id, { assumptions: [older] }));
  const reader = render.statement({ statement: older, reference, onSource: noop });
  for (const html of [graph, reader]) { assert.match(html, /consequence of removing this condition was not recorded/); assert.doesNotMatch(html, /demonstrated failure|proven to fail/); }
  const unavailable = { ...claim, justification: { ...claim.justification, artifacts: [{ title: "Earlier proof", path: "working/theorist/proof.md", locator: "Lemma 2" }] } };
  const missingProof = render.graph(graphProps(claim.statement_id, { claims: [unavailable] }));
  assert.match(missingProof, /retained proof file is unavailable: Earlier proof · Lemma 2/);
  assert.doesNotMatch(missingProof, /href="[^"]*proof\.md/);
});

test("component actions state explanation, nonpublishing assessment and publishing revision separately", () => {
  const graph = render.graph(graphProps(assumption.assumption_id));
  assert.match(graph, /aria-label="Explain this assumption"/);
  assert.match(graph, /Request an assessment/); assert.match(graph, /Request a theory revision/);
  assert.match(graph, /separate check without changing the published theory/);
  assert.doesNotMatch(graph, /Challenge this assumption|Request repair of this step|legacy graph/);
  const unlinked = render.graph(graphProps(claim.statement_id, { theory_generation_ref: null }));
  assert.match(unlinked, /exact theory source is unavailable/);
  for (const action of ["check", "repair"]) assert.match(unlinked, new RegExp(`<button(?=[^>]*data-action="${action}")(?=[^>]*disabled="")[^>]*>`));
});

test("assessment and revision requests retain exact targets and distinct modes", () => {
  const target = { ...reference, kind: "assumption", object_id: assumption.assumption_id };
  const assessment = theoryComponentRequest("assessment", target, assumption.label);
  const revision = theoryComponentRequest("repair", target, assumption.label);
  assert.equal(assessment.mode, "p3.assessment"); assert.equal(assessment.title, "Request an assessment");
  assert.match(assessment.instructions, /without changing the published theory/);
  assert.equal(revision.mode, "p3.theory_revision"); assert.equal(revision.title, "Request a theory revision");
  assert.match(revision.instructions, /Preserve stable statement identities and unrelated statements/);
  assert.deepEqual(assessment.target, target); assert.deepEqual(revision.target, target);
  assert.notEqual(assessment.target, target);
  const modes = [{ mode: "p3.assessment" }, { mode: "p3.theory_revision" }, { mode: "p3.theory_establishment" }];
  assert.deepEqual(modesForRequest(assessment, modes), [modes[0]]); assert.deepEqual(modesForRequest(revision, modes), [modes[1]]);
  for (const broken of [{ ...target, sha256: null }, { ...target, object_id: null }, { ...target, kind: "unresolved" }, { ...target, family: "claim_map" }]) {
    assert.equal(isTheoryComponentTarget(broken), false); assert.equal(theoryComponentRequest("assessment", broken), null);
  }
});

test("historical assessments and experiment sources stay on their recorded mathematics", () => {
  const earlier = { ...reference, generation_id: "theory.earlier", sha256: "c".repeat(64), run_id: "run.earlier", kind: "assumption", object_id: assumption.assumption_id };
  const saved = { assessment_id: "assessment.earlier", state: "assessed", target: earlier, summary: "This check concerned the earlier condition.", messages: [{ role: "researcher", content: "Explain the earlier argument." }] };
  const before = JSON.stringify(saved);
  const html = render.assessments({ projectId: "project.conditions", assessments: [saved], onStarted: noop, onRepair: noop, onSource: noop });
  assert.match(html, /theory\.earlier/); assert.match(html, /earlier condition/); assert.match(html, /earlier argument/); assert.match(html, /does not change the published theory/);
  const request = render.revisionRequest(saved);
  assert.deepEqual(request.target, earlier); assert.equal(request.assessment_id, saved.assessment_id);
  assert.equal(targetIsStale(request, reference), true);
  assert.equal(JSON.stringify(saved), before);
  const oldCondition = { ...assumption, sensitivity: "Earlier guarantee loss remains the recorded account." };
  const tested = render.tested({ document: { statements: [claim], assumptions: [oldCondition] }, componentId: claim.statement_id, onCurrentTheory: noop });
  assert.match(tested, /current theory may differ/); assert.match(tested, /Earlier guarantee loss remains the recorded account/); assert.match(tested, /Conditions under which it applies/);
  assert.ok(tested.includes(render.conditions({ statement: claim })));
});
