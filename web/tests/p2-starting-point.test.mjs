import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { methodStartingPoint, methodStartingPointSource } from "../src/methodSeed.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p2-starting-point-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Methods from '${src}/components/MethodProposals.jsx'; import Instructions from '${src}/components/PhaseTwoInstructions.jsx'; export const methods=props=>renderToStaticMarkup(React.createElement(Methods,props)); export const instructions=props=>renderToStaticMarkup(React.createElement(Instructions,props));`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

test("a method starting point retains exact catalog and original proposal sources beside editable text", () => {
  const identity = { stable_id: "method.a", version: 3, definition_sha256: "a".repeat(64) };
  const catalog = { branch: "trunk", phase: "P2", family: "method_catalog", generation_id: "catalog.two", sha256: "b".repeat(64), run_id: "run.two" };
  const original = { branch: "trunk", phase: "P2", family: "theory_proposal", generation_id: "proposal.one", sha256: "c".repeat(64), run_id: "run.one", package_id: "package.one" };
  const method = { title: "Repeated method title", identity, mathematical_definition: { canonical_definition: { target_or_estimand: "Original target", algorithm_or_update_rule: [{ operation: "Return the original estimate." }] } } };
  const before = JSON.stringify({ method, catalog, original });
  const seed = methodStartingPoint(method, { proposal_id: "proposal.a", generation_ref: original }, { source_ref: catalog });
  assert.equal(JSON.stringify({ method, catalog, original }), before);
  assert.deepEqual(Object.keys(seed).sort(), ["source_reference", "specification_markdown", "title"]);
  assert.match(seed.specification_markdown, /Original target/);
  assert.deepEqual(methodStartingPointSource(seed), { kind: "p2_method_starting_point", method_identity: identity, catalog_ref: catalog, proposal_ref: original, proposal_id: "proposal.a" });
  seed.title = "An edited title"; seed.specification_markdown = "Researcher's extension request.";
  identity.version = 4; catalog.generation_id = "later.catalog"; original.generation_id = "later.proposal";
  const frozen = methodStartingPointSource(seed);
  assert.equal(frozen.method_identity.version, 3);
  assert.equal(frozen.catalog_ref.generation_id, "catalog.two");
  assert.equal(frozen.proposal_ref.generation_id, "proposal.one");
});

test("legacy source attribution is preserved without inventing a selected model identity", () => {
  assert.equal(methodStartingPointSource({ source_reference: "Researcher's manuscript, equation 4" }), null);
  assert.equal(methodStartingPointSource({ source_reference: JSON.stringify({ title: "A matching title" }) }), null);
  assert.equal(methodStartingPointSource(undefined), null);
});

test("an earlier selected proposal keeps its publication's catalog when the identity is retained again", () => {
  const identity = { stable_id: "method.retained", version: 1, definition_sha256: "a".repeat(64) };
  const catalog = { branch: "trunk", phase: "P2", family: "method_catalog", generation_id: "catalog.earlier", sha256: "b".repeat(64), run_id: "run.earlier", package_id: "package.earlier" };
  const proposalRef = { ...catalog, family: "theory_proposal", generation_id: "proposal.earlier", sha256: "c".repeat(64) };
  const currentCatalog = { ...catalog, generation_id: "catalog.current", sha256: "d".repeat(64), run_id: "run.current", package_id: "package.current" };
  const method = { title: "Earlier method reading", summary: "The selected original account.", identity };
  const seed = methodStartingPoint(method, { proposal_id: "proposal.retained", generation_ref: proposalRef, catalog_ref: catalog }, { source_ref: currentCatalog });
  const source = methodStartingPointSource(seed);
  assert.deepEqual(source.catalog_ref, catalog);
  assert.deepEqual(source.proposal_ref, proposalRef);
  assert.match(seed.specification_markdown, /selected original account/);
  assert.doesNotMatch(seed.source_reference, /catalog.current|run.current/);
});

test("seeded lead proposals retain original-source authorship and launch previews state the supplied version", () => {
  const identity = { stable_id: "method.original", version: 3, definition_sha256: "a".repeat(64) };
  const original = { title: "Original theorist definition", identity, mathematical_definition: { canonical_definition: { target_or_estimand: "Original mean target" } } };
  const proposalRef = { branch: "trunk", phase: "P2", family: "theory_proposal", generation_id: "theory.original", sha256: "b".repeat(64), run_id: "run.original" };
  const catalogRef = { ...proposalRef, family: "method_catalog", generation_id: "catalog.selected" };
  const supplied = methodStartingPoint(original, { proposal_id: "proposal.original", generation_ref: proposalRef }, { source_ref: catalogRef });
  const candidate = { title: "Lead candidate", identity: { ...identity, stable_id: "method.lead", version: 1 }, mathematical_definition: { canonical_definition: { target_or_estimand: "Corrected primitive-input target" } } };
  const html = ui.methods({ proposals: [{ proposal_id: "proposal.lead", role: "research_lead", method: candidate, researcher_origin: supplied, generation_ref: { ...proposalRef, family: "lead_proposal", generation_id: "lead.candidate", run_id: "run.seeded" } }] });
  assert.match(html, /Proposed by Research Lead/);
  assert.match(html, /From a selected model starting point/);
  assert.doesNotMatch(html, /From your idea/);
  assert.match(html, /Version 3 supplied the lead/);
  assert.match(html, /Starting original proposal source/);
  assert.doesNotMatch(html, /p2-reader-section contribution-surface/, "A selected team-authored model does not become researcher-authored when used as a starting point.");
  const originalDisclosure = html.match(/<details class="research-details"><summary>Original starting formulation<\/summary>([\s\S]*?)<\/details>/);
  assert.ok(originalDisclosure, "The supplied parent formulation is retained in a native collapsed disclosure.");
  assert.match(originalDisclosure[1], /Original mean target/);
  assert.doesNotMatch(originalDisclosure[0], /<details[^>]*\bopen(?:=|\s|>)/);
  const outsideOriginal = html.replace(originalDisclosure[0], "");
  assert.match(outsideOriginal, /Corrected primitive-input target/, "The current candidate's own formulation remains readable.");
  assert.doesNotMatch(outsideOriginal, /Original mean target/, "The parent's scientific prose is not duplicated beside the corrected candidate.");
  assert.match(outsideOriginal, /Starting catalog definition source|Starting original proposal source/);
  const preview = ui.instructions({ id: "p2-input", value: "Lead direction", onChange: () => {}, suppliedMethod: supplied, onSource: () => {} });
  assert.match(preview, /Starting point: Version 3/);
  assert.match(preview, /original proposal are frozen/);
  assert.match(preview, /Selected catalog definition source/);
  assert.match(preview, /These additions go only to the Research Lead/);
});

test("an unseeded researcher idea remains readable without being relabeled as a parent model", () => {
  const html = ui.methods({ proposals: [{ proposal_id: "proposal.idea", role: "research_lead", method: { title: "Idea candidate", summary: "The team's reformulated mechanism.", identity: { stable_id: "method.idea", version: 1, definition_sha256: "a".repeat(64) } }, researcher_origin: { specification_markdown: "The researcher's original proposed mechanism.", source_reference: "Research manuscript, section 2" }, generation_ref: { run_id: "run.idea", generation_id: "lead.idea" } }] });
  assert.match(html, /From your idea|Your supplied method and source/);
  assert.match(html, /The researcher&#x27;s original proposed mechanism/);
  assert.match(html, /Research manuscript, section 2/);
  const original = html.match(/<section class="p2-reader-section contribution-surface">([\s\S]*?)<\/section>/)?.[1];
  assert.ok(original, "The researcher's original words retain the contribution treatment.");
  assert.match(original, /The researcher&#x27;s original proposed mechanism/);
  assert.match(original, /Research manuscript, section 2/);
  assert.doesNotMatch(original, /The team&#x27;s reformulated mechanism/);
  assert.match(html, /The team&#x27;s reformulated mechanism/);
  assert.doesNotMatch(html, /Original starting formulation|Selected model starting point and source/);
});

test("the comparison omits internal source controls and keeps the excluded method reason", () => {
  const generation_ref = { branch: "trunk", phase: "P2", family: "catalog_assessment", generation_id: "assessment.exact", sha256: "a".repeat(64), run_id: "run.exact" };
  const proposal = { proposal_id: "proposal.excluded", role: "theorist", generation_ref: { ...generation_ref, family: "theory_proposal", generation_id: "proposal.exact" }, method: { title: "Excluded original model", identity: { stable_id: "method.excluded", version: 1, definition_sha256: "b".repeat(64) } } };
  const comparison = { generation_ref, overview_markdown: "The alternatives have different conditions.", method_dispositions: [{ proposal_id: proposal.proposal_id, status: "exclude", rationale_markdown: "Its required observations are unavailable." }] };
  const before = structuredClone({ proposal, comparison });
  const html = ui.methods({ proposals: [proposal], comparisons: [comparison], onSource: () => {} });
  const card = html.match(/<div class="p2-comparison"[\s\S]*?(?=<div class="field method-branch-selector")/)?.[0];
  assert.ok(card);
  assert.equal((card.match(/>Lead assessment source<\/button>/g) || []).length, 0);
  assert.doesNotMatch(card, /assessment.exact/);
  assert.match(card, /Not retained in this catalog update \(1\)/);
  assert.match(card, /Excluded original model/);
  assert.match(card, /Its required observations are unavailable/);
  assert.deepEqual({ proposal, comparison }, before);
});
