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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p1-p3-readers-"));
const bundle = path.join(directory, "test.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; export {MainFindings,PaperAssessment,SelectedPaper,LiteratureSupportingDocument} from '${src}/components/LiteratureWorkspace.jsx'; export {TheoryArguments,exactArgumentsDocument,PhaseOverview} from '${src}/components/PhaseReading.jsx'; export {default as ReadingHost} from '${src}/components/ReadingHost.jsx'; export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props)); export const withHost=(Component,props)=>renderToStaticMarkup(React.createElement(require('${src}/components/ReadingHost.jsx').default,{scope:{projectId:'fixture.project',phase:'P1',branch:'trunk'}},React.createElement(Component,props))); export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

const pin = { catalog_version: "1.23.0", catalog_manifest_sha256: "f".repeat(64) };
const reference = { branch: "trunk", phase: "P1", family: "research_basis", generation_id: "fixture.basis", sha256: "a".repeat(64) };
const card = { catalog_pin: pin, role: "theorist", family: "theory_literature", entry_id: "fixture.entry", entry_sha256: "b".repeat(64), run_id: "fixture.run", generation_ref: { ...reference, family: "theory_literature" }, entry_pointer: "/papers/0", source: { title: "Exact earlier paper", authors: ["Fixture Author"], year: 2025 }, explanation_markdown: "A conditional result identifies the target.", relevance_markdown: "It applies when overlap holds.", limitations_markdown: "The boundary case is unresolved.", formulation_markdown: "$$x>0$$", evidence_locations: ["Equation 2."] };
const citation = { status: "available", source_id: "source.original", canonical_source_id: "source.canonical", bibliography: card.source, card, entry_ref: { role: card.role, family: card.family, run_id: card.run_id, entry_id: card.entry_id, entry_sha256: card.entry_sha256 } };
const basis = { catalog_pin: pin, generation_ref: reference, citations: [citation], landscape: { summary_markdown: "The result remains conditional.", overview_item_ids: ["framework.fixture"], frameworks: [{ framework_id: "framework.fixture", title: "Fixture approach", explanation_markdown: "The approach estimates a conditional target.", relevance_reason_markdown: "The setting needs positive overlap.", formulation_markdown: "$$x>0$$", assumptions_markdown: "Positive overlap is required [Fixture](#cite:source.original).", limitations: ["The boundary case is unresolved."], entry_refs: [citation.entry_ref], support_status: "partially_supported" }] } };
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children), ...nodes(tree.props.resources)] : [];
function hooks(Component, props, host) {
  const previous = ui.dispatcher.current;
  try {
    ui.dispatcher.current = { useContext: () => host, useId: () => "fixture-id", useState: initial => [typeof initial === "function" ? initial() : initial, () => {}], useRef: initial => ({ current: initial }), useEffect() {} };
    return Component(props);
  } finally { ui.dispatcher.current = previous; }
}

test("concise P1 reader clicks freeze the exact basis and citation while retaining the main qualifications", () => {
  const input = structuredClone(basis); let snapshot;
  const host = { scope: { projectId: "fixture.project", phase: "P1", branch: "trunk" }, open: value => { snapshot = value; }, close() {} };
  const tree = hooks(ui.MainFindings, { basis: input }, host);
  const button = nodes(tree).find(node => node.props.title === "Mathematics, assumptions and evidence");
  assert.ok(button);
  button.props.onClick({ currentTarget: { isConnected: true } });
  input.landscape.frameworks[0].formulation_markdown = "Changed by publication";
  input.citations[0].card.formulation_markdown = "Today's assessment";
  assert.equal(snapshot.body.props.document.record.formulation_markdown, "$$x>0$$");
  assert.equal(snapshot.body.props.document.basis.citations[0].card.formulation_markdown, "$$x>0$$");
  assert.match(snapshot.key, /fixture\.basis/);
  assert.equal(snapshot.size.equations, 1);
  const html = ui.withHost(ui.MainFindings, { basis });
  for (const text of ["The result remains conditional", "estimates a conditional target", "needs positive overlap", "Source support: Partially supported"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /The boundary case is unresolved/);
});

test("exact paper dialogs suppress nested support controls", () => {
  const paper = { source_id: "source.canonical", ...card.source, cards: [card] };
  const concise = ui.withHost(ui.SelectedPaper, { source: paper, onSource() {} });
  assert.match(concise, /aria-haspopup="dialog"/);
  for (const text of [card.explanation_markdown, card.relevance_markdown, card.limitations_markdown]) assert.ok(concise.includes(text));
  const dialogPaper = ui.withHost(ui.SelectedPaper, { source: paper, allowReaders: false, initialSelection: { exactCard: card }, onSource() {} });
  assert.doesNotMatch(dialogPaper, /aria-haspopup="dialog"/);
  assert.match(dialogPaper, /Full mathematics and reading basis/);
  assert.match(dialogPaper, /Exact earlier paper/);
});

test("P1 split keeps complete findings and paper assessments together while moving each resource once", () => {
  const input = structuredClone(basis);
  input.coverage_limits = ["The search did not cover the boundary regime."];
  input.landscape.common_assumptions = [{ assumption_id: "assumption.overlap", title: "Overlap", statement_markdown: "Positive overlap is required." }];
  const html = ui.withHost(ui.MainFindings, { basis: input, onSource() {} });
  const [account, rail] = html.split('<aside ');
  assert.match(account, /The result remains conditional/);
  assert.match(account, /needs positive overlap/);
  assert.match(account, /Source support: Partially supported/);
  for (const title of ["Mathematics, assumptions and evidence", "Common assumptions and project fit", "Review scope and limits", "Research basis source"]) {
    assert.equal(html.split(title).length - 1, 1, `${title} has one owner`);
    assert.ok(rail.includes(title), `${title} is supporting reading`);
  }
  assert.doesNotMatch(account, /ReadingDocumentButton|The search did not cover/);
  const paper = { source_id: "source.canonical", ...card.source, cards: [card], search_provenance: [{ search_source: "Fixture index", query: "overlap", searched_at: "2026-10-31" }] };
  const selected = ui.withHost(ui.SelectedPaper, { source: paper, onSource() {} });
  const [paperAccount, paperRail] = selected.split('<aside ');
  for (const text of [card.explanation_markdown, card.relevance_markdown, card.limitations_markdown]) assert.ok(paperAccount.includes(text), text);
  for (const title of ["Full mathematics and reading basis", "Evidence locations", "Original member record", "Original submissions, revision history and search provenance"]) {
    assert.equal(selected.split(title).length - 1, 1, `${title} has one owner`);
    assert.ok(paperRail.includes(title), `${title} is beside the complete account`);
  }
  assert.doesNotMatch(ui.withHost(ui.SelectedPaper, { source: paper, allowReaders: false }), /<aside /);
  assert.doesNotMatch(ui.withHost(ui.MainFindings, {}), /<aside /);
  const noSupportingFields = { ...input, generation_ref: undefined, coverage_limits: [], landscape: { summary_markdown: "An account without extra records.", overview_item_ids: ["framework.empty"], frameworks: [{ framework_id: "framework.empty", title: "No supporting fields", explanation_markdown: "An authored explanation." }] } };
  assert.doesNotMatch(ui.withHost(ui.MainFindings, { basis: noSupportingFields }), /<aside /);
});

test("P1 supporting citations use their frozen card and retain an explicit full-explorer route", () => {
  let selection; let rerender;
  const document = { kind: "approach", basis: structuredClone(basis), record: structuredClone(basis.landscape.frameworks[0]), itemId: "framework.fixture", sources: [] };
  const previous = ui.dispatcher.current;
  try {
    ui.dispatcher.current = { useState: () => [selection, value => { selection = value; }], useContext: () => ({ scope: {} }) };
    let tree = ui.LiteratureSupportingDocument({ document, onNavigate() {} });
    const support = nodes(tree).find(node => node.props.itemId === "framework.fixture");
    support.props.onOpenCitation(document.basis.citations[0], { basis: document.basis, anchor: "fixture.citation", element: { isConnected: true } });
    tree = ui.LiteratureSupportingDocument({ document, onNavigate() {} }); rerender = nodes(tree).find(node => node.props.citation);
  } finally { ui.dispatcher.current = previous; }
  assert.equal(rerender.props.citation.card.entry_sha256, card.entry_sha256);
  assert.equal(rerender.props.citation.basis.generation_ref.sha256, reference.sha256);
  assert.equal(typeof rerender.props.onNavigate, "function");
  assert.equal(rerender.props.citation.origin.anchor, "fixture.citation");
});

const theoryRef = { branch: "method.fixture", phase: "P3", family: "theory_record", generation_id: "fixture.theory", sha256: "c".repeat(64), run_id: "fixture.theory.run", package_id: "fixture.package" };
const assumption = { assumption_id: "assumption.overlap", text: "Positive overlap is required.", strength: "Uniform positivity.", sensitivity: "Without overlap the guarantee is lost; failure is not demonstrated.", status: "conditional" };
const claim = { statement_id: "statement.target", label: "Target guarantee", text: "The target is identified under overlap.", proof_status: "full", status: "incomplete", assumption_ids: [assumption.assumption_id], regime: "Inside the overlap region.", quantifiers: ["For every admissible policy."], proof: "Legacy proof text stays accessible.", assessment_context: { origin: "lead_concern", reason: "The uniform argument remains open.", generation_ref: theoryRef }, theorist_account: { status: "established", proof_status: "full", generation_ref: { ...theoryRef, family: "theory_candidate" }, justification: { summary: "The submitted proof uses compactness." } } };
const otherClaim = { statement_id: "statement.bound", label: "Risk bound", text: "The error is bounded in the interior.", proof_status: "missing", assumption_ids: [assumption.assumption_id] };
const theory = { theory_scope: "Only the interior regime is addressed.", scientific_outcome: { conclusion: "The proof remains conditional.", material_disagreement: ["The Analyst disputes uniformity."] }, limitations: ["No boundary guarantee is established."], empirical_implications: [{ text: "Probe the boundary separately.", conditions: ["Keep the target and policy fixed."], observable_or_metric: "Record target error.", expected_pattern: "Interior error decreases with sample size.", falsifying_result: "A nonvanishing interior error contradicts the pattern." }], statements: [claim, otherClaim], assumptions: [assumption] };
const map = { authoritative: true, branch: theoryRef.branch, phase: "P3", theory_generation_ref: theoryRef, claims: [claim, otherClaim], assumptions: [assumption] };
const document = { kind: "theory_record", title: "Complete fixture theory", generation_ref: theoryRef, structured: theory, body_md: "The full narrative remains in its exact source dialog." };
const argumentsProps = (changes = {}) => ({ map, branch: theoryRef.branch, documents: [document], selected: claim.statement_id, onSelect() {}, onSource() {}, ...changes });

test("compact P3 Arguments retain exact scope, qualifications, current support and registered assumptions", () => {
  const before = JSON.stringify({ map, document });
  const html = ui.render(ui.TheoryArguments, argumentsProps());
  for (const text of [theory.theory_scope, theory.limitations[0], theory.scientific_outcome.conclusion, theory.scientific_outcome.material_disagreement[0], claim.regime, claim.quantifiers[0], claim.proof, assumption.text, assumption.strength, assumption.sensitivity, "Registered assumptions used", "Original theorist account", "Theorist submitted proof assessment: Full proof", "Incomplete", "Proof missing", "Complete fixture theory"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /The full narrative remains|The error is bounded in the interior/);
  assert.equal((html.match(/class="research-details theory-argument"/g) || []).length, 2);
  assert.equal((html.match(/class="research-details theory-argument" open=""/g) || []).length, 1);
  assert.equal(JSON.stringify({ map, document }), before);
  for (const text of [theory.empirical_implications[0].conditions[0], theory.empirical_implications[0].observable_or_metric, theory.empirical_implications[0].expected_pattern, theory.empirical_implications[0].falsifying_result]) assert.ok(html.includes(text), text);
  const unselected = ui.render(ui.TheoryArguments, argumentsProps({ selected: assumption.assumption_id }));
  assert.doesNotMatch(unselected, /class="research-details theory-argument" open=""/);
  assert.ok(unselected.includes(theory.limitations[0]));
});

test("canonical rows need no display decorations and unresolved assumption IDs stay unresolved", () => {
  const canonical = { statement_id: "statement.canonical", text: "The registered claim has no display label.", depends_on_assumption_ids: ["assumption.absent"], justification: { kind: "open_obligation", summary: "A boundary argument remains open." } };
  const canonicalMap = { ...map, claims: [canonical], assumptions: [] };
  const canonicalDocument = { ...document, structured: { ...theory, statements: [canonical], assumptions: [] } };
  const html = ui.render(ui.TheoryArguments, argumentsProps({ map: canonicalMap, documents: [canonicalDocument], selected: canonical.statement_id }));
  assert.match(html, /Canonical/);
  assert.match(html, /The registered claim has no display label/);
  assert.match(html, /A boundary argument remains open/);
  assert.match(html, /Absent: the registered assumption is unavailable in this theory source/);
  assert.doesNotMatch(html, /Positive overlap is required/);
});

test("Arguments selection uses the graph's selectedNode and exact source controls", () => {
  const selected = []; const opened = [];
  const tree = ui.TheoryArguments(argumentsProps({ selected: otherClaim.statement_id, onSelect: value => selected.push(value), onSource: value => opened.push(value) }));
  const rows = nodes(tree).filter(node => node.props.className === "research-details theory-argument");
  rows[0].props.onToggle({ currentTarget: { open: true } });
  rows[1].props.onToggle({ currentTarget: { open: false } });
  assert.deepEqual(selected, [claim.statement_id, null]);
  const source = nodes(tree).find(node => node.props.label === "Complete fixture theory");
  source.props.onOpen(source.props.reference);
  assert.deepEqual(opened, [theoryRef]);
});

test("legacy, ambiguous or mismatched theory sources keep the complete inline account", () => {
  for (const changes of [{ map: { ...map, authoritative: false, source_warning: "This legacy map is not authoritative." } }, { map: { ...map, authoritative: undefined } }, { documents: [{ ...document, generation_ref: { ...theoryRef, sha256: "d".repeat(64) } }] }, { documents: [{ ...document, generation_ref: { ...theoryRef, package_id: "another.package" } }] }, { documents: [document, { ...document }] }, { documents: [{ ...document, structured: undefined }] }]) {
    const props = argumentsProps(changes);
    assert.equal(ui.exactArgumentsDocument(props.map, props.documents), null);
    const html = ui.render(ui.TheoryArguments, props);
    assert.match(html, /The full narrative remains in its exact source dialog/);
    assert.match(html, /The error is bounded in the interior/);
    assert.doesNotMatch(html, /class="research-details theory-argument"/);
  }
});

test("P1 Main Findings offers Explore the literature actions beside the complete findings", () => {
  const clicks = [];
  const host = { scope: { projectId: "fixture.project", phase: "P1", branch: "trunk" }, open() {}, close() {} };
  const props = { basis, onExplorePapers: () => clicks.push("papers"), onExploreFrameworks: () => clicks.push("frameworks") };
  const tree = hooks(ui.MainFindings, props, host);
  const layout = nodes(tree).find(node => node.props?.actionsLabel === "Literature findings actions");
  assert.ok(layout, "the findings card uses the shared layout with named actions");
  assert.equal(layout.props.label, "Literature findings supporting reading");
  const buttons = nodes(layout.props.actions).filter(node => typeof node.props?.onClick === "function");
  assert.deepEqual(buttons.map(node => node.props.children), ["Individual papers", "Framework map"]);
  buttons[1].props.onClick(); buttons[0].props.onClick();
  assert.deepEqual(clicks, ["frameworks", "papers"]);
  const html = ui.withHost(ui.MainFindings, props);
  assert.match(html, /<div class="research-card-actions" role="group" aria-label="Literature findings actions"><section><h3>Explore the literature<\/h3><div class="btnrow">/);
  assert.ok(html.indexOf("research-card-actions") < html.indexOf("research-card-account"));
  assert.ok(html.includes("The result remains conditional."));
  assert.doesNotMatch(html, /earlier-synthesis|Read the earlier|This earlier account has no authored overview/);
  assert.doesNotMatch(ui.withHost(ui.MainFindings, { basis }), /Explore the literature|research-card-actions/);
  assert.doesNotMatch(ui.withHost(ui.MainFindings, { ...props, embedded: true }), /Explore the literature|research-card-actions/);
  const withoutBasis = ui.withHost(ui.MainFindings, { onExplorePapers() {}, onExploreFrameworks() {} });
  assert.match(withoutBasis, /Individual papers/);
  assert.doesNotMatch(withoutBasis, /Framework map/);
  const unpinned = ui.withHost(ui.MainFindings, { basis: { ...basis, catalog_pin: undefined } });
  assert.ok(unpinned.includes("The result remains conditional."));
  assert.doesNotMatch(unpinned, /earlier-synthesis|Read the earlier literature synthesis/);
});

test("P3 What changed opens as a sized reader with the Lead's exact source", () => {
  let snapshot;
  const host = { scope: { projectId: "fixture.project", phase: "P3", branch: "method.a" }, open: value => { snapshot = value; }, close() {} };
  const decision = { conclusion: "Only the stated regime is established.", what_changed: "The claim was narrowed to $$\\beta>0$$.",
    generation_ref: { ...reference, phase: "P3", branch: "method.a", family: "decision", generation_id: "fixture.decision" } };
  const props = { phase: "P3", decision, methodLabel: "Method A", onSource() {} };
  const tree = hooks(ui.PhaseOverview, props, host);
  const layout = nodes(tree).find(node => node.props?.label === "Theory supporting reading");
  const button = nodes(layout.props.resources).find(node => node.props?.title === "What changed");
  assert.ok(button, "What changed is offered as a reading document");
  assert.equal(button.props.size.equations, 1);
  button.props.onClick({ currentTarget: "trigger" });
  assert.equal(snapshot.title, "What changed");
  assert.equal(snapshot.subtitle, "Method A · Research Lead");
  assert.match(snapshot.key, /fixture\.decision/);
  assert.equal(snapshot.size.equations, 1);
  const body = ui.render(() => snapshot.body);
  assert.match(body, /The claim was narrowed/);
  assert.match(body, /Lead assessment source/);
  assert.doesNotMatch(ui.render(() => layout.props.children), /What changed/);
  const html = ui.withHost(ui.PhaseOverview, props);
  assert.match(html, /<aside class="research-card-resources" aria-label="Theory supporting reading">[\s\S]*?<h3>Supporting reading<\/h3><div class="p2-reading-links">[\s\S]*?What changed/);
  assert.doesNotMatch(html, /<h3>What changed<\/h3>/);
  const hostless = ui.render(ui.PhaseOverview, props);
  assert.match(hostless, /<h3>What changed<\/h3>/);
  assert.doesNotMatch(hostless, /p2-reading-links/);
});
