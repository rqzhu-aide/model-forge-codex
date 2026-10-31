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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p3-sources-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {ScientificDocuments,PhaseOverview} from '${src}/components/PhaseReading.jsx'; export {ScientificDocuments,PhaseOverview}; export {ResearchDocument,SourceRef} from '${src}/components/Shared.jsx'; export const render=props=>renderToStaticMarkup(<ScientificDocuments {...props}/>); export const overview=props=>renderToStaticMarkup(<PhaseOverview {...props}/>);`, resolveDir: src, loader: "jsx" }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const reference = { branch: "method.a", phase: "P4", family: "decision", generation_id: "generation.earlier", sha256: "a".repeat(64), run_id: "run.earlier", package_id: "package.earlier" };
const candidate = "run://run.revision/outputs/p3.theorist/theory_candidate.json";
const audit = "run://run.revision/outputs/p3.analyst/analyst_audit.json";
const artifact = "artifact://artifact.original-proof";
const revision = "artifact://artifact.revision";
const generation = "generation://generation.earlier";
const file = (uri, name) => ({ uri, source_verified: true, sha256: "b".repeat(64), artifact_url: `/api/v1/exact/${name}?sha256=${"b".repeat(64)}` });
const document = { phase: "P3", kind: "theory_record", generation_ref: { ...reference, phase: "P3", family: "theory_record", generation_id: "generation.revision" }, body_md: `The bound is $\\alpha \\leq 1$. [Revised theory](${candidate}) and [Independent audit](${audit}). [Original proof](${artifact}#proof) [Revision](${revision}) [Earlier P4](${generation}#/conclusion) [Declared relative](./revision.md) [Missing](run://run.revision/outputs/p3.theorist/private.json) [Undeclared](../private.md).`, inline_sources: [file(candidate, "candidate.json"), file(audit, "audit.json"), file(artifact, "original.md"), file(revision, "revision.md"), file("./revision.md", "revision.md"), { uri: generation, source_verified: true, generation_ref: reference }] };
const find = (node, predicate) => {
  if (!node || typeof node !== "object") return null;
  if (Array.isArray(node)) return node.map((item) => find(item, predicate)).find(Boolean);
  return predicate(node) ? node : find(node.props?.children, predicate);
};
const documentLink = (doc, onSource = () => {}) => find(ui.ScientificDocuments({ documents: [doc], onSource }), (node) => node.type === ui.ResearchDocument && node.props.renderSourceLink).props.renderSourceLink;

test("P3 account renders verified run, artifact, generation and relative citations with readable labels", () => {
  const before = structuredClone(document);
  const html = ui.render({ documents: [document], onSource() {} });
  for (const name of ["candidate.json", "audit.json", "original.md", "revision.md"]) assert.ok(html.includes(`/api/v1/exact/${name}?sha256=`));
  assert.match(html, /original\.md\?sha256=b{64}#proof/);
  assert.match(html, /<button[^>]*title="Decision · generation\.earlier"[^>]*>[\s\S]*?Earlier P4<\/button>/);
  assert.match(html, /class="source-link ui-action" data-action="source" data-ui-role="system"/);
  assert.match(html, /Missing \(source unavailable\)/);
  assert.match(html, /Undeclared \(source unavailable\)/);
  assert.match(html, /class="katex"/);
  assert.doesNotMatch(html, /katex-error|run:\/\/|artifact:\/\/|generation:\/\/|\[Revised theory\]\(/);
  assert.deepEqual(document, before);
});

test("generation citation opens its exact frozen source and JSON pointer", () => {
  let opened;
  const link = documentLink(document, (ref) => { opened = ref; })(`${generation}#/conclusion`, "Earlier P4");
  assert.equal(link.type, ui.SourceRef);
  ui.SourceRef(link.props).props.onClick();
  assert.deepEqual(opened, { ...reference, entry_pointer: "/conclusion" });
  assert.equal(reference.entry_pointer, undefined);
});

test("unverified and ambiguous bindings cannot become links or fall back to current sources", () => {
  for (const sources of [[], [{ ...file(candidate, "candidate.json"), source_verified: false }], [file(candidate, "one.json"), file(candidate, "two.json")], [{ ...file(candidate, "candidate.json"), source_error: "Changed bytes" }], [{ ...file(candidate, "candidate.json"), artifact_url: "file:///private.json" }]]) {
    const doc = { ...document, body_md: `[Revised theory](${candidate})`, inline_sources: sources };
    const html = ui.render({ documents: [doc], onSource() {} });
    assert.match(html, /Revised theory \(source unavailable\)/);
    assert.doesNotMatch(html, /href=|run:\/\//);
  }
  assert.equal(documentLink(document)("https://example.org/paper", "Paper"), null);
});

test("overview proof citation uses the decision's exact published document and original label", () => {
  const proof = { ...document.generation_ref, family: "theory_record" };
  const decision = { phase: "P3", conclusion: `The bound requires the stated assumptions. See [full proof and interpretation](${artifact}).`,
    generation_ref: { ...proof, family: "decision", generation_id: "generation.decision" },
    inline_sources: [{ ...file(artifact, "original.md"), generation_ref: proof }] };
  let opened;
  const tree = ui.PhaseOverview({ phase: "P3", decision, onSource: ref => { opened = ref; } });
  const account = find(tree, node => node.type === ui.ResearchDocument);
  const link = account.props.renderSourceLink(artifact, "full proof and interpretation");
  assert.equal(link.type, ui.SourceRef);
  ui.SourceRef(link.props).props.onClick();
  assert.deepEqual(opened, proof);
  const html = ui.overview({ phase: "P3", decision, onSource() {} });
  assert.match(html, /<button[^>]*data-action="source"[^>]*>[\s\S]*?full proof and interpretation<\/button>/);
  assert.doesNotMatch(html, /artifact:\/\/|source unavailable|href=/);
});

test("overview summary fallback owns its citations and source reference even if an empty decision exists", () => {
  const proof = document.generation_ref;
  const summary = { phase: "P3", summary_markdown: `[Published summary proof](${artifact})`,
    generation_ref: { ...proof, family: "phase_summary", generation_id: "generation.summary" },
    inline_sources: [{ ...file(artifact, "original.md"), generation_ref: proof }] };
  const emptyDecision = { phase: "P3", generation_ref: { ...proof, family: "decision", generation_id: "generation.empty" } };
  const html = ui.overview({ phase: "P3", decision: emptyDecision, summaries: [summary], onSource() {} });
  assert.match(html, /Published summary proof<\/button>/);
  assert.match(html, /Phase summary · generation.summary/);
  assert.doesNotMatch(html, /generation.empty|source unavailable/);
  const missing = { ...emptyDecision, conclusion: `[Missing decision proof](${artifact})`, inline_sources: [] };
  assert.match(ui.overview({ phase: "P3", decision: missing, summaries: [summary], onSource() {} }), /Missing decision proof \(source unavailable\)/);
});

test("overview leads with a distinct authored headline and keeps the complete qualified conclusion", () => {
  const headline = "Safety is conditional; useful returns remain unmeasured.";
  const conclusion = `The retained theorem permits no recommendation and requires the stated sampling premises. See [full proof](${artifact}).`;
  const decision = { phase: "P3", headline, conclusion, principal_uncertainty: "Actual-study applicability remains unknown.", generation_ref: { ...document.generation_ref, family: "decision" }, inline_sources: [{ ...file(artifact, "original.md"), generation_ref: document.generation_ref }] };
  const before = structuredClone(decision);
  for (const phase of ["P3", "P5"]) {
    const html = ui.overview({ phase, decision, onSource() {} });
    assert.match(html, /class="phase-overview-headline"/);
    assert.ok(html.indexOf(headline) < html.indexOf("The retained theorem permits no recommendation"));
    assert.match(html, /requires the stated sampling premises/);
    assert.match(html, /full proof<\/button>/);
    assert.match(html, /Actual-study applicability remains unknown/);
    assert.equal((html.match(/Safety is conditional; useful returns remain unmeasured\./g) || []).length, 1);
  }
  assert.deepEqual(decision, before);
});

test("overview does not repeat an identical headline or change the single-field fallback", () => {
  const statement = "The result remains conditional on the recorded premises.";
  for (const decision of [{ headline: statement, conclusion: statement }, { headline: ` ${statement} `, conclusion: statement }, { headline: statement }, { conclusion: statement }, { headline: "", conclusion: statement }]) {
    const html = ui.overview({ phase: "P3", decision });
    assert.equal((html.match(/The result remains conditional on the recorded premises\./g) || []).length, 1);
    assert.doesNotMatch(html, /phase-overview-headline/);
  }
});

test("canonical record JSON opens its verified original bytes while the full proof uses the readable viewer", () => {
  const proof = document.generation_ref;
  const canonical = file("complete_theory.json", "canonical-record.json");
  const doc = { ...document, body_md: "[Full proof](artifact://proof) [Canonical JSON](complete_theory.json)", inline_sources: [
    { ...file("artifact://proof", "proof.md"), generation_ref: proof }, canonical,
  ] };
  const resolve = documentLink(doc);
  const proofLink = resolve("artifact://proof", "Full proof");
  const recordLink = resolve("complete_theory.json", "Canonical JSON");
  assert.equal(proofLink.type, ui.SourceRef);
  assert.deepEqual(proofLink.props.reference, proof);
  assert.equal(recordLink.type, "a");
  assert.equal(recordLink.props.href, canonical.artifact_url);
  assert.equal(recordLink.props.target, "_blank");
  const html = ui.render({ documents: [doc], onSource() {} });
  assert.match(html, /<a[^>]*href="\/api\/v1\/exact\/canonical-record.json\?sha256=b{64}"[^>]*>[\s\S]*?Canonical JSON<\/a>/);
});
