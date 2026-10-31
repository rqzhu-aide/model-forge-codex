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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-theory-proof-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import {TheoryReading} from '${src}/components/PhaseReading.jsx'; import {TheoryJustification} from '${src}/components/TheoryAssessment.jsx'; export {theoryProofSource,TheoryJustification} from '${src}/components/TheoryAssessment.jsx'; export {SourceRef} from '${src}/components/Shared.jsx'; export const reading=props=>renderToStaticMarkup(<TheoryReading {...props}/>); export const justification=props=>renderToStaticMarkup(<TheoryJustification {...props}/>);`, resolveDir: src, loader: "jsx" }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const candidate = { branch: "method.a", phase: "P3", family: "theory_candidate", generation_id: "generation.original", sha256: "a".repeat(64), run_id: "run.original", stage_id: "p3.theorist", package_id: "package.original" };
const artifact = { uri: "run://run.original/p3.theory_candidate/proof.md", path: "proof.md", sha256: "b".repeat(64), media_type: "text/markdown", source_verified: true, artifact_url: `/api/v1/projects/example/runs/run.original/outputs/p3.theorist/artifact?path=working%2Fproof.md&sha256=${"b".repeat(64)}`, locator: "Appendix C3" };
const source = { ...artifact, generation_ref: candidate, locator: "Appendix F4" };
const justification = { kind: "proof", summary: "The event inclusion proves the stated bound.", artifacts: [artifact] };
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];

test("verified proof opens the original candidate source through the existing accessible source control", () => {
  const before = structuredClone({ artifact, source, justification });
  const opened = [];
  const tree = ui.TheoryJustification({ justification, proofSources: [source], onSource: ref => opened.push(ref) });
  const control = nodes(tree).find(node => node.type === ui.SourceRef);
  assert.equal(control.props.label, "Open support source · Appendix C3");
  const button = ui.SourceRef(control.props);
  assert.equal(button.type, "button"); assert.equal(button.props.type, "button");
  assert.equal(button.props.disabled, false); assert.equal(button.props.href, undefined);
  button.props.onClick();
  assert.deepEqual(opened, [candidate]); assert.notEqual(opened[0], candidate);
  const html = ui.justification({ justification, proofSources: [source], onSource() {} });
  assert.match(html, /<button[^>]*title="Theory candidate · generation.original"[^>]*>[\s\S]*?Open support source · Appendix C3<\/button>/);
  assert.doesNotMatch(html, /href=|target="_blank"|Appendix F4/);
  assert.deepEqual({ artifact, source, justification }, before);
});

test("proof mapping requires exact verified URI, hash, URL and one unambiguous generation", () => {
  assert.deepEqual(ui.theoryProofSource(artifact, [source, structuredClone(source)]), candidate);
  const invalid = [
    [], [{ ...source, uri: "run://run.new/p3.theory_candidate/proof.md" }],
    [{ ...source, sha256: "c".repeat(64) }], [{ ...source, artifact_url: source.artifact_url.replace("run.original", "run.new") }],
    [{ ...source, source_verified: false }], [{ ...source, source_error: "Changed bytes" }],
    [{ ...source, generation_ref: undefined }], [{ ...source, generation_ref: { ...candidate, entry_pointer: "/statements/0" } }],
    [source, { ...source, generation_ref: { ...candidate, generation_id: "generation.other" } }],
    [source, { ...source, generation_ref: { ...candidate, package_id: "package.other" } }],
  ];
  for (const sources of invalid) assert.equal(ui.theoryProofSource(artifact, sources), null);
  for (const changes of [{ source_verified: false }, { source_error: "Unavailable" }, { sha256: "" }, { uri: "" }, { artifact_url: "file:///private/proof.md" }]) {
    assert.equal(ui.theoryProofSource({ ...artifact, ...changes }, [source]), null);
  }
});

test("absent historical mapping and nontext artifacts retain direct exact downloads without a current-source fallback", () => {
  const current = { ...source, uri: "run://run.current/p3.theory_candidate/proof.md", artifact_url: "/api/current/proof.md", generation_ref: { ...candidate, generation_id: "generation.current" } };
  const historical = ui.justification({ justification, proofSources: [current], onSource() {} });
  assert.ok(historical.includes(artifact.artifact_url.replaceAll("&", "&amp;")));
  assert.match(historical, /target="_blank"/); assert.doesNotMatch(historical, /generation.current|<button/);
  const pdf = { ...artifact, media_type: "application/pdf", path: "proof.pdf" };
  assert.equal(ui.theoryProofSource(pdf, [{ ...source, media_type: pdf.media_type }]), null);
  const html = ui.justification({ justification: { ...justification, artifacts: [pdf] }, proofSources: [source], onSource() {} });
  assert.match(html, /<a[^>]*target="_blank"/); assert.doesNotMatch(html, /<button/);
});

test("unsafe or unavailable artifact URLs do not become download or formatted links", () => {
  for (const changes of [{ artifact_url: "javascript:alert(1)" }, { artifact_url: "https://untrusted.test/proof.md" }, { artifact_url: "//untrusted.test/proof.md" }, { artifact_url: "file:///private/proof.md" }, { source_error: "Bytes unavailable" }]) {
    const html = ui.justification({ justification: { ...justification, artifacts: [{ ...artifact, ...changes }] }, proofSources: [source], onSource() {} });
    assert.match(html, /retained proof file is unavailable/); assert.doesNotMatch(html, /href=|<button/);
  }
});

test("P3 claims inspector and arguments pass retained mappings to current and attributed original proof controls", () => {
  const claim = { statement_id: "statement.safety", label: "Safety guarantee", text: "The bound holds under stated premises.", proof_status: "full", status: "established", justification };
  const props = { branch: candidate.branch, selected: claim.statement_id, onSelect() {}, onSource() {},
    claimMaps: [{ branch: candidate.branch, phase: "P3", claims: [claim], assumptions: [], theory_generation_ref: { ...candidate, family: "theory_record", generation_id: "generation.lead" } }],
    documents: [{ kind: "theory_record", inline_sources: [source], body_md: "The conditions remain necessary." }] };
  const before = JSON.stringify(props);
  for (const tab of ["claims", "arguments"]) {
    const html = ui.reading({ ...props, reading: { tab } });
    assert.match(html, /<button[^>]*title="Theory candidate · generation.original"[^>]*>[\s\S]*?Open support source · Appendix C3<\/button>/);
    assert.doesNotMatch(html, /href="\/api\/v1\/projects\/example/);
  }
  const reassessed = { ...claim, original_justification_retained: true, theorist_account: { justification, generation_ref: { ...candidate, entry_pointer: "/statements/0" } }, assessment_context: { reason: "The original support is retained.", generation_ref: { ...candidate, family: "decision" } } };
  const html = ui.reading({ ...props, claimMaps: [{ ...props.claimMaps[0], claims: [reassessed] }], reading: { tab: "claims" } });
  assert.match(html, /Original theorist account/); assert.match(html, /Open support source · Appendix C3<\/button>/); assert.doesNotMatch(html, /href=/);
  assert.equal(JSON.stringify(props), before);
});
