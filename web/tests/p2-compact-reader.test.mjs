import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { catalogOnlyMethods, catalogSelectionKey, hasConciseP2Account, proposalKey } from "../src/methodWorkspace.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p2-compact-"));
const bundle = path.join(directory, "render.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `
  import React from 'react';
  import {renderToStaticMarkup} from 'react-dom/server';
  import Methods, {methodReadingDocuments,comparisonReadingDocuments} from '${src}/components/MethodProposals.jsx';
  export {methodReadingKey} from '${src}/components/MethodReadingWindow.jsx';
  import {SourceRef} from '${src}/components/Shared.jsx';
  function sourceReferences(node) {
    if (Array.isArray(node)) return node.flatMap(sourceReferences);
    if (!React.isValidElement(node)) return [];
    if (node.type === SourceRef) return node.props.reference ? [{label: node.props.label, reference: node.props.reference}] : [];
    if (typeof node.type === 'function' && ['MethodAudits', 'CompleteFormulation'].includes(node.type.name)) return sourceReferences(node.type(node.props));
    return sourceReferences(node.props.children);
  }
  export function comparisons(input) {
    return comparisonReadingDocuments(input,()=>{}).map(item=>({...item,html:renderToStaticMarkup(item.body),sources:sourceReferences(item.body)}));
  }
  export function reader(props) {
    let issueContext, furtherContext, historyContext;
    const html=renderToStaticMarkup(<Methods {...props} issues={context=>{
      issueContext=context;return <section className='card' data-card-role='attention'><h2>Decisions to Discuss</h2></section>;
    }} furtherWork={context=>{
      furtherContext=context;return <details className='card' data-card-role='action'><summary><h2>Additional Runs and History</h2></summary></details>;
    }} history={context=>{
      historyContext=context;return <details className='research-details run-history' data-reading-anchor='research-history'><summary>Phase run history</summary>{context.modelHistory}</details>;
    }}/>);
    const documents=issueContext.method ? methodReadingDocuments({selected: issueContext.proposal,
      catalogMethod: issueContext.catalogMethod, method: issueContext.method, reviewed: issueContext.reviewed,
      reviews: props.reviews || [], proposals: props.proposals || [], literatureSources: props.literatureSources || []}, props.onSource)
      .map(item=>({...item,html:renderToStaticMarkup(item.body),sources:sourceReferences(item.body)})) : [];
    return {html,issueContext,furtherContext,historyContext,documents};
  }
`, resolveDir: src, loader: "jsx" }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const reference = (family, name = family, run = "run.exact") => ({ branch: "trunk", phase: "P2", family, generation_id: name, run_id: run, package_id: `package.${run}`, sha256: "a".repeat(64) });
const identity = { stable_id: "method.exact", version: 2, definition_sha256: "b".repeat(64) };
const proposal = { proposal_id: "proposal.exact", role: "theorist", generation_ref: reference("theory_proposal"),
  method: { title: "Constrained estimator", identity, summary: "Original proposer account and equation.\n$$Q(\\beta)=0.$$",
    mathematical_definition: { canonical_definition: { target_or_estimand: "The exact coefficient target.", objective_or_estimating_equation: { definition: "$$Q(\\beta)=0.$$" }, constraints_and_normalization: [{ definition: "$$\\mathbf1^\\top\\beta=0.$$" }], algorithm_or_update_rule: [{ order: 1, operation: "Complete original algorithm." }], tuning_definition: [{ selection_rule: "UNIQUE_ORIGINAL_TUNING_RULE" }], calculation_defining_assumptions: [{ statement: "Finite calculation inputs.", mathematical_role: "Defines the optimization domain." }], custom_mathematical_object: { exact_update: "CUSTOM_SCIENTIFIC_UPDATE" } }, computational_consequences: ["UNIQUE_COMPUTATIONAL_CONSEQUENCE"] },
    assumptions: ["Independent observations."], limitations: ["Uncertainty remains unverified."], literature_provenance: [{ citation_id: "reference.exact", relation: "foundation", contribution: "An independently authored scientific relation." }] },
  computational_profile: { per_iteration_markdown: "UNIQUE_COST_ACCOUNT", memory_markdown: "Retain the design.", scaling_markdown: "Dense scaling." }, data_requirements_markdown: "Observed response and design.", proposed_evaluation_markdown: "A proposed evaluation, not a completed study." };
const concise = "Authored essential inputs and coefficient target.\n$$\\widehat\\beta=\\arg\\min_{\\mathbf1^\\top\\beta=0}Q(\\beta).$$\nReturn the fitted coefficient vector under the stated finite-input condition. No uncertainty guarantee has been checked.";
const assessment = { generation_ref: reference("catalog_assessment"), catalog_pin: { catalog_version: "1.24.0", catalog_manifest_sha256: "c".repeat(64) }, overview_markdown: "Authored comparison of different scientific targets.", comparison_markdown: "The full comparison remains in shared history.", method_dispositions: [{ proposal_id: proposal.proposal_id, status: "retain", method_summary_markdown: concise, rationale: "Independent Lead assessment." }] };
const catalog = { method_id: identity.stable_id, branch_id: "branch.exact", title: proposal.method.title, identity, definition: proposal.method, status: "active", source_ref: reference("method_catalog") };
const props = { proposals: [proposal], comparisons: [assessment], methods: [catalog], onSource: noop, onContinue: noop };
const selectedAccount = html => {
  const start = html.indexOf('Methodological account</h3>');
  return html.slice(start, html.indexOf('<aside class="research-card-resources"', start));
};
const documentNamed = (result, name) => result.documents.find(document => document.name === name);

test("comparison readers show a UTC publication date and retain the exact source timestamp", () => {
  const timestamp = "2026-11-01T18:15:20.123456-06:00";
  const comparison = { ...assessment, title: "Method comparison", published_at: timestamp };
  const [document] = render.comparisons({ comparison, proposals: [proposal] });
  assert.equal(document.subtitle, "Method comparison · Research Lead · Phase 2 · Published Nov 2, 2026 (UTC)");
  assert.doesNotMatch(document.subtitle, /2026-11-01T/);
  assert.match(document.html, /<details class="research-details"><summary>Source details<\/summary><dl><div><dt>Recorded publication timestamp<\/dt>/);
  assert.ok(document.html.includes(timestamp));
  assert.ok(document.sources.some(source => source.reference === comparison.generation_ref));
  for (const published_at of [undefined, "", "invalid", "2026-11-02T00:00:00"]) {
    const [reader] = render.comparisons({ comparison: { ...comparison, published_at }, proposals: [proposal] });
    assert.equal(reader.subtitle, "Method comparison · Research Lead · Phase 2");
    if (published_at) assert.ok(reader.html.includes(published_at), "Unusable metadata remains exact in details.");
    else assert.doesNotMatch(reader.html, /Recorded publication timestamp/);
  }
});

test("a verified producing catalog selects the revised account without inferring provenance from app metadata", () => {
  for (const version of ["1.24.0", "1.24.1", "1.25.0", "2.0.0"]) assert.equal(hasConciseP2Account({ catalog_pin: { catalog_version: version, catalog_manifest_sha256: "f".repeat(64) } }), true);
  for (const record of [null, {}, { catalog_version: "1.24.0" }, { phase_contract_version: "3.10.0" }, { catalog_pin: { catalog_version: "1.24.0" } }, { catalog_pin: { catalog_version: "1.24.0", catalog_manifest_sha256: "bad" } }, { catalog_pin: { catalog_version: "1.23.99", catalog_manifest_sha256: "f".repeat(64) } }, { catalog_pin: { catalog_version: "1.24.0-preview", catalog_manifest_sha256: "f".repeat(64) } }]) assert.equal(hasConciseP2Account(record), false);
});

test("reading position belongs to the exact project, method, document and contributing source revisions", () => {
  const linked = { proposal_id: "proposal.linked", generation_ref: reference("data_proposal", "generation.linked") };
  const review = { generation_ref: reference("theory_review", "generation.review") };
  const input = { selected: proposal, catalogMethod: catalog, method: proposal.method,
    reviewed: { comparison: assessment, disposition: assessment.method_dispositions[0] },
    proposals: [proposal, linked], reviews: [review], literatureSources: [] };
  const selectedKey = proposalKey(proposal);
  const key = (changes = {}, project = "project.exact", selection = selectedKey, name = "review") => render.methodReadingKey(project, selection, name, { ...input, ...changes });
  const original = key();
  assert.equal(key(structuredClone(input)), original, "Unchanged source values retain the same reading position.");
  assert.notEqual(key({}, "project.other"), original);
  assert.notEqual(key({}, "project.exact", "run.exact:proposal.other"), original);
  assert.notEqual(key({}, "project.exact", selectedKey, "computation"), original);
  for (const identityChange of [{ stable_id: "method.other" }, { version: 3 }, { definition_sha256: "d".repeat(64) }]) {
    assert.notEqual(key({ method: { ...proposal.method, identity: { ...identity, ...identityChange } } }), original);
  }
  const revisedRef = ref => ({ ...ref, sha256: "e".repeat(64) });
  assert.notEqual(key({ selected: { ...proposal, generation_ref: revisedRef(proposal.generation_ref) } }), original);
  assert.notEqual(key({ reviewed: { ...input.reviewed, comparison: { ...assessment, generation_ref: revisedRef(assessment.generation_ref) } } }), original);
  assert.notEqual(key({ reviews: [{ ...review, generation_ref: revisedRef(review.generation_ref) }] }), original);
  assert.notEqual(key({ proposals: [proposal, { ...linked, generation_ref: revisedRef(linked.generation_ref) }] }), original,
    "A historical inline link's revised exact proposal source changes the reader context.");
  const updatedCatalog = { ...catalog, source_ref: revisedRef(catalog.source_ref) };
  assert.equal(key({ catalogMethod: updatedCatalog }), original,
    "An unrelated catalog publication does not reset a retained proposal's reading position.");
  const catalogInput = { ...input, selected: null, reviewed: null, proposals: [], reviews: [] };
  const catalogKey = render.methodReadingKey("project.exact", catalogSelectionKey(catalog), "computation", catalogInput);
  assert.notEqual(render.methodReadingKey("project.exact", catalogSelectionKey(catalog), "computation", { ...catalogInput, catalogMethod: updatedCatalog }), catalogKey,
    "A catalog-only reader follows its actual catalog source revision.");
});

test("the proposal summary is separate from the selected model reader in four cards", () => {
  const before = JSON.stringify(props); const { html, issueContext, furtherContext, historyContext, documents } = render.reader(props);
  assert.equal((html.match(/<(?:section|details)\b[^>]*class="card(?: |")/g) || []).length, 4);
  assert.ok(html.indexOf("Proposed Methods") < html.indexOf("Authored comparison"));
  const overview = html.slice(html.indexOf("Proposed Methods"), html.indexOf("</section>"));
  assert.match(overview, /Authored comparison/);
  assert.doesNotMatch(overview, /<select|Methodological account/);
  assert.ok(html.indexOf("</section>") < html.indexOf("Select a Method to Explore"));
  assert.ok(html.indexOf("Select a Method to Explore") < html.indexOf("Choose a method"));
  assert.ok(html.indexOf("Decisions to Discuss") < html.indexOf("Additional Runs and History"));
  const selectedCard = html.slice(html.indexOf('Select a Method to Explore'),html.indexOf('Decisions to Discuss'));
  assert.match(selectedCard, /class="research-card-layout has-rail has-actions"/);
  assert.match(selectedCard, /class="research-card-actions" role="group" aria-label="Method actions"/);
  assert.ok(selectedCard.indexOf("Run this Method in Phase 3 - Theory") < selectedCard.indexOf('class="research-card-account"'));
  assert.ok(selectedCard.indexOf("Methodological account") < selectedCard.indexOf('<aside class="research-card-resources"'));
  assert.match(selectedCard, /aria-label="Method supporting reading"/);
  assert.ok(selectedCard.indexOf('>Notation</h3>') < selectedCard.indexOf('>Supporting reading</h3>'));
  assert.doesNotMatch(selectedCard, /p2-method-layout|p2-method-account|p2-method-resources|p2-resource-group|p2-model-continuation|Read more about this method/);
  const buttons = [...selectedCard.matchAll(/<button\b[^>]*class="[^"]*p2-reading-button[^"]*"[^>]*>([\s\S]*?)<\/button>/g)];
  assert.equal(buttons.length, 3);
  assert.deepEqual(documents.map(item => item.title), ["Assumptions and limitations", "Computation and formulation", "Reviews and sources"]);
  for (const [index, button] of buttons.entries()) {
    assert.match(button[0], /type="button"/); assert.match(button[0], /aria-haspopup="dialog"/);
    assert.ok(button[1].includes(documents[index].title)); assert.match(button[1], /p2-reading-estimate/);
    assert.match(button[1], /About \d[\d,]* words/);
  }
  assert.doesNotMatch(html, /p2-reader-disclosure|role="dialog"|Complete original algorithm|CUSTOM_SCIENTIFIC_UPDATE/);
  assert.doesNotMatch(html, /role="tablist"|role="tabpanel"|Explore a model|What the team found/);
  assert.match(html, /data-reading-anchor="p2-selected-model" tabindex="-1"/);
  assert.strictEqual(issueContext, furtherContext); assert.strictEqual(historyContext, furtherContext); assert.ok(html.indexOf("Additional Runs and History") < html.indexOf("Phase run history")); assert.strictEqual(issueContext.proposal, proposal); assert.strictEqual(issueContext.catalogMethod, catalog);
  assert.equal(issueContext.emptyState, false); assert.equal(issueContext.exploreActions, undefined); assert.ok(issueContext.modelHistory);
  assert.equal(JSON.stringify(props), before);
});

test("the comparison keeps all three candidates and their qualifications beside a selection-independent reading rail", () => {
  const mean = { ...proposal, proposal_id: "proposal.mean", role: "research_lead", generation_ref: reference("lead_proposal", "generation.mean"),
    method: { ...proposal.method, title: "Donor-balanced mean", identity: { ...identity, stable_id: "method.mean" }, summary: "Estimate a mean giving each observed donor equal weight." } };
  const quantile = { ...proposal, proposal_id: "proposal.quantile", role: "data_analyst", generation_ref: reference("data_proposal", "generation.quantile"),
    method: { ...proposal.method, title: "Noisy-audit quantile", identity: { ...identity, stable_id: "method.quantile" }, summary: "Estimate a population quantile using the proposed audit correction." } };
  const candidates = [proposal, mean, quantile];
  const paragraphs = [
    "Constrained estimator is worth developing only if its coefficient constraint matches the scientific question; its uncertainty guarantee is unverified.",
    "Donor-balanced mean instead targets an equally weighted donor population mean, requiring independent observed donors; it does not estimate the constrained coefficients.",
    "Noisy-audit quantile targets a population quantile rather than a mean or coefficient vector; its required audit information is missing, so the Lead excluded it from this update.",
  ];
  const comparison = { ...assessment, title: "Conditional comparison of three targets", _notation_available: true,
    overview_markdown: paragraphs.join("\n\n"),
    comparison_markdown: "FULL_THREE_TARGET_COMPARISON\n\nThe mean target is $\\mu_D=\\mathbb E[\\mu_i]$.\n\nThe audit correction remains unidentified without the required audit information. No target is interchangeable with the other two.",
    method_dispositions: [
      assessment.method_dispositions[0],
      { proposal_id: mean.proposal_id, status: "retain", method_summary_markdown: mean.method.summary, rationale: "Independent donor sampling remains a necessary condition." },
      { proposal_id: quantile.proposal_id, status: "exclude", method_summary_markdown: quantile.method.summary, rationale: "The audit correction remains unidentified without the required audit information." },
    ] };
  const input = { ...props, proposals: candidates, comparisons: [comparison] };
  const before = structuredClone({ candidates, comparison });
  const comparisonCard = html => html.slice(html.indexOf("Proposed Methods</h2>"), html.indexOf("Select a Method to Explore</h2>"));
  const cards = candidates.map(candidate => comparisonCard(render.reader({ ...input, initialPick: proposalKey(candidate) }).html));
  assert.ok(cards.every(card => card === cards[0]), "Changing the selected method does not replace the phase-wide comparison or its reading controls.");
  const card = cards[0], railStart = card.indexOf('<aside class="research-card-resources"');
  assert.ok(railStart > 0);
  const primary = card.slice(0, railStart), rail = card.slice(railStart);
  assert.match(primary, /<div class="research-card-layout has-rail"><div class="research-card-account">/);
  assert.match(primary, /How the methods compare/);
  for (const paragraph of paragraphs) assert.ok(primary.includes(paragraph), paragraph);
  assert.doesNotMatch(primary, /Full comparison|Shared notation|Reasons for excluding alternatives|FULL_THREE_TARGET_COMPARISON/);
  assert.match(rail, /aria-label="Comparison supporting reading"/);
  for (const label of ["Full comparison", "Shared notation", "Reasons for excluding alternatives"]) assert.ok(rail.includes(label), label);
  assert.ok(rail.indexOf('>Notation</h3>') < rail.indexOf('>Supporting reading</h3>'));
  assert.ok(rail.indexOf('Shared notation') < rail.indexOf('Full comparison'));
  assert.equal((rail.match(/aria-haspopup="dialog"/g) || []).length, 3);
  for (const description of ["Detailed reasoning, qualifications and disagreements", "Symbols and definitions used in this comparison", "Why the Lead set these proposals aside"]) assert.ok(rail.includes(description), description);
  const documents = render.comparisons({ comparison, proposals: candidates });
  const full = documents.find(document => document.name === "comparison"), excluded = documents.find(document => document.name === "excluded");
  assert.match(full.html, /FULL_THREE_TARGET_COMPARISON/);
  assert.match(full.html, /No target is interchangeable with the other two/);
  assert.match(full.html, /\\mu_D=\\mathbb E\[\\mu_i\]/);
  assert.ok(full.sources.some(item => item.reference === comparison.generation_ref));
  assert.match(excluded.html, /Noisy-audit quantile/);
  assert.match(excluded.html, /audit correction remains unidentified without the required audit information/);
  assert.ok(excluded.sources.some(item => item.reference === quantile.generation_ref));
  assert.ok(excluded.sources.some(item => item.reference === comparison.generation_ref));
  assert.deepEqual({ candidates, comparison }, before);
});

test("method stale notes, run controls and preparation precede the complete scientific account once", () => {
  const stale = { phase: "P3", status: "needs_update", recorded_version: 1, current_version: 2, change_summary: "The constraint changed.", source_ref: reference("method_catalog", "revision.exact") };
  const result = render.reader({ ...props, initialSharedPreparation: true, methods: [{ ...catalog, dependent_outputs: [stale] }] });
  const card = result.html.slice(result.html.indexOf('Select a Method to Explore'), result.html.indexOf('Decisions to Discuss'));
  const actions = card.slice(card.indexOf('class="research-card-actions"'), card.indexOf('class="research-card-account"'));
  assert.match(actions, /Phase 3 - Theory results for this method/);
  assert.match(actions, /role="alert"/);
  assert.match(actions, /The constraint changed/);
  assert.ok(actions.indexOf('results for this method') < actions.indexOf('Run this Method in Phase 3'));
  assert.ok(actions.indexOf('Run this Method in Phase 4') < actions.indexOf('Prepare work on this method'));
  assert.match(actions, /Shared proposal instructions remain below until you choose a method for this work/);
  for (const text of ['results for this method', 'Run this Method in Phase 3', 'Run this Method in Phase 4', 'Prepare work on this method']) assert.equal(card.split(text).length - 1, 1);
  assert.match(selectedAccount(result.html), /Authored essential inputs|No uncertainty guarantee has been checked/);
  assert.doesNotMatch(selectedAccount(result.html), /results for this method|Prepare work on this method|Run this Method/);
});

test("method actions disappear when absent and preserve an inactive definition's explanation", () => {
  const selectedCard = input => {
    const html = render.reader(input).html;
    return html.slice(html.indexOf('Select a Method to Explore'), html.indexOf('Decisions to Discuss'));
  };
  const noActions = selectedCard({ ...props, onContinue: undefined, initialSharedPreparation: false });
  assert.match(noActions, /class="research-card-layout has-rail"/);
  assert.doesNotMatch(noActions, /research-card-actions|has-actions|Run this Method|Prepare work on this method/);
  const inactive = selectedCard({ ...props, methods: [{ ...catalog, status: "archived" }] });
  assert.match(inactive, /class="research-card-actions"/);
  assert.match(inactive, /This catalog definition is not active for further work/);
  assert.doesNotMatch(inactive, /Run this Method in Phase 3|Run this Method in Phase 4/);
});

test("comparison resources omit empty notation and reading sections", () => {
  const card = comparison => {
    const html = render.reader({ ...props, comparisons: [comparison] }).html;
    return html.slice(html.indexOf('Proposed Methods</h2>'), html.indexOf('Select a Method to Explore</h2>'));
  };
  const notationOnly = card({ ...assessment, overview_markdown: undefined, comparison_markdown: 'Complete legacy comparison.', _notation_available: true });
  assert.match(notationOnly, />Notation<\/h3>/);
  assert.doesNotMatch(notationOnly, />Supporting reading<\/h3>|Full comparison/);
  const readingOnly = card(assessment);
  assert.match(readingOnly, />Supporting reading<\/h3>/);
  assert.doesNotMatch(readingOnly, />Notation<\/h3>|Shared notation/);
  const neither = card({ ...assessment, overview_markdown: undefined, comparison_markdown: 'Complete legacy comparison.' });
  assert.match(neither, /class="research-card-layout"/);
  assert.match(neither, /Complete legacy comparison/);
  assert.doesNotMatch(neither, /research-card-resources|research-card-actions|has-rail|>Supporting reading<\/h3>|>Notation<\/h3>/);
});

test("the revised Lead account stays whole and its exact scientific source records remain on demand", () => {
  const result = render.reader({ ...props, literatureSources: [{ source_id: "reference.exact", title: "Exact scientific reference", identifiers: [{ kind: "doi", value: "10.1234/exact" }] }] });
  const { html } = result;
  const account = selectedAccount(html);
  assert.match(account, /Authored essential inputs/); assert.match(account, /No uncertainty guarantee has been checked/);
  assert.match(account, /<annotation encoding="application\/x-tex">\\widehat\\beta=\\arg\\min_\{\\mathbf1\^\\top\\beta=0\}Q\(\\beta\)\.<\/annotation>/);
  assert.doesNotMatch(account, /Original proposer account|Complete original algorithm|UNIQUE_ORIGINAL_TUNING_RULE/);
  const computation = documentNamed(result, "computation"), reviews = documentNamed(result, "review"), assumptions = documentNamed(result, "assumptions");
  assert.match(reviews.html, /Proposer&#x27;s original summary/); assert.match(reviews.html, /Original proposer account/);
  assert.match(computation.html, /Complete original algorithm/); assert.match(computation.html, /CUSTOM_SCIENTIFIC_UPDATE/); assert.match(computation.html, /Additional original formulation fields/);
  assert.match(reviews.html, /Independent Lead assessment/); assert.match(reviews.html, /Exact scientific reference/); assert.match(reviews.html, /href="https:\/\/doi.org\/10.1234\/exact"/);
  assert.match(assumptions.html, /Independent observations/); assert.match(assumptions.html, /Uncertainty remains unverified/);
  for (const text of ["UNIQUE_ORIGINAL_TUNING_RULE", "UNIQUE_COMPUTATIONAL_CONSEQUENCE", "UNIQUE_COST_ACCOUNT"]) {
    assert.equal((computation.html.match(new RegExp(text, "g")) || []).length, 1, text);
    assert.doesNotMatch(account, new RegExp(text));
  }
  assert.equal(computation.size.equations, 2); assert.ok(computation.size.words > 10);
  assert.ok(reviews.sources.some(({ reference }) => reference.generation_id === assessment.generation_ref.generation_id && reference.entry_pointer === "/method_dispositions/0/method_summary_markdown"));
  assert.ok(reviews.sources.some(({ reference }) => reference.generation_id === assessment.generation_ref.generation_id && reference.entry_pointer === "/method_dispositions/0/rationale"));
  assert.ok(computation.sources.some(({ reference }) => reference === proposal.generation_ref));
  assert.ok(html.indexOf('class="p2-history"') > html.indexOf("Additional Runs and History"));
});

test("historical and unknown writing provenance preserve the full Lead record without making it the default account", () => {
  const historical = "HISTORICAL_FIRST_PARAGRAPH\n\n" + "The full authored condition remains. ".repeat(60) + "\n\nHISTORICAL_FINAL_PARAGRAPH";
  for (const catalog_pin of [undefined, { catalog_version: "1.23.4", catalog_manifest_sha256: "d".repeat(64) }, { catalog_version: "1.24.0", catalog_manifest_sha256: "unknown" }]) {
    const comparison = { ...assessment, catalog_pin, method_dispositions: [{ ...assessment.method_dispositions[0], method_summary_markdown: historical }] };
    const before = structuredClone(comparison); const result = render.reader({ ...props, comparisons: [comparison], appVersion: "1.24.0" }); const { html } = result;
    const account = selectedAccount(html);
    assert.match(account, /Original proposer account/); assert.match(account, /Open Computation and formulation for the complete mathematics/);
    assert.doesNotMatch(account, /Finite calculation inputs|\\mathbf1\^\\top\\beta=0/);
    const computation = documentNamed(result, "computation"), reviews = documentNamed(result, "review");
    assert.match(computation.html, /Finite calculation inputs/); assert.match(computation.html, /\\mathbf1\^\\top\\beta=0/);
    assert.doesNotMatch(account, /HISTORICAL_FIRST_PARAGRAPH|HISTORICAL_FINAL_PARAGRAPH/);
    assert.match(reviews.html, /Full historical Lead procedural account/); assert.match(reviews.html, /HISTORICAL_FIRST_PARAGRAPH/); assert.match(reviews.html, /HISTORICAL_FINAL_PARAGRAPH/);
    assert.equal((reviews.html.match(/The full authored condition remains/g) || []).length, 60);
    assert.ok(reviews.size.words >= 300); assert.doesNotMatch(html, /HISTORICAL_FIRST_PARAGRAPH|HISTORICAL_FINAL_PARAGRAPH/);
    assert.deepEqual(comparison, before);
  }
});

test("selected Lead fragment links resolve only exact unambiguous proposal and audit sources from its producing run", () => {
  const review = { review_id: "review.exact", generation_ref: reference("theory_review", "generation.audit"), assessments: [] };
  const oldReview = { ...review, review_id: "review.old", generation_ref: reference("theory_review", "generation.old", "run.old") };
  const comparison = { ...assessment, method_dispositions: [{ ...assessment.method_dispositions[0], method_summary_markdown: "Read [selected proposal](#proposal.exact), [independent audit](#review.exact), [old audit](#review.old) and [absent account](#proposal.absent)." }] };
  const account = selectedAccount(render.reader({ ...props, reviews: [review, oldReview], comparisons: [comparison] }).html);
  assert.match(account, /title="[^"]* · theory_proposal"[\s\S]*?selected proposal<\/button>/);
  assert.match(account, /title="[^"]* · generation.audit"[\s\S]*?independent audit<\/button>/);
  assert.doesNotMatch(account, /generation.old|href="#|\[selected proposal\]|\[independent audit\]/);
  assert.match(account, /old audit/); assert.match(account, /absent account/);
  const ambiguous = selectedAccount(render.reader({ ...props, proposals: [proposal, { ...proposal, method: { ...proposal.method, title: "Duplicate source identity" } }], comparisons: [comparison] }).html);
  assert.doesNotMatch(ambiguous, />selected proposal<\/button>/);
});

test("catalog-only definitions remain selectable among authored proposals and retain exact eligible continuation", () => {
  const onlyIdentity = { stable_id: "method.only", version: 3, definition_sha256: "e".repeat(64) };
  const only = { method_id: "method.only", title: "Catalog-only model", identity: onlyIdentity, status: "proposed", branch_id: "branch.only", source_ref: reference("method_catalog", "generation.only"), definition: { summary: "Complete catalog-only account.\n$$R=1.$$", limitations: ["Catalog-only original qualification."] } };
  const source = [catalog, only]; const before = structuredClone(source);
  assert.deepEqual(catalogOnlyMethods(source, [proposal]), [only]);
  const result = render.reader({ ...props, methods: source, initialPick: catalogSelectionKey(only) }); const { html, issueContext } = result;
  assert.match(html, /Catalog definitions without a linked proposal/); assert.match(html, /Complete catalog-only account/);
  assert.match(documentNamed(result, "assumptions").html, /Catalog-only original qualification/);
  assert.match(documentNamed(result, "computation").html, /No computational profile was recorded for this catalog definition/);
  assert.ok(documentNamed(result, "assumptions").sources.some(({ reference }) => reference === only.source_ref));
  assert.match(html, /Run this Method in Phase 3 - Theory/); assert.match(html, /Run this Method in Phase 4 - Numerical Eval/); assert.match(html, /generation.only/);
  assert.equal(issueContext.proposal, null); assert.equal(issueContext.method.identity, onlyIdentity); assert.strictEqual(issueContext.catalogMethod, only); assert.equal(issueContext.methodBranch, "branch.only"); assert.equal(issueContext.emptyState, false);
  const legacy = render.reader({ methods: [only], onSource: noop, onContinue: noop }).html;
  assert.match(legacy, /Choose a method/); assert.match(legacy, /Complete catalog-only account/); assert.match(legacy, /Run this Method in Phase 4 - Numerical Eval/);
  assert.deepEqual(source, before);
});

test("excluded and superseded selections preserve readable records without current-version continuation", () => {
  const excluded = { ...assessment, method_dispositions: [{ ...assessment.method_dispositions[0], status: "exclude", rationale: "Required observations remain unavailable." }] };
  const result = render.reader({ ...props, comparisons: [excluded], methods: [] }); const { html } = result;
  assert.match(html, /Excluded from this catalog update/); assert.match(html, /Reasons for excluding alternatives/); assert.doesNotMatch(html, /Run this Method in Phase 3 - Theory|Run this Method in Phase 4 - Numerical Eval/);
  const exclusion = render.comparisons({ comparison: excluded, proposals: [proposal] }).find(item => item.name === "excluded");
  assert.match(exclusion.html, /Required observations remain unavailable/);
  assert.ok(exclusion.sources.some(item => item.reference === excluded.generation_ref));
  assert.match(documentNamed(result, "review").html, /Required observations remain unavailable/);
  const old = { ...proposal, is_current_package: false, method: { ...proposal.method, identity: { ...identity, version: 1, definition_sha256: "f".repeat(64) } } };
  const superseded = render.reader({ ...props, proposals: [old], initialPick: proposalKey(old) });
  assert.match(superseded.html, /Superseded by version 2/); assert.match(superseded.html, /View the current version \(version 2\)/); assert.doesNotMatch(superseded.html, /Run this Method in Phase 3 - Theory|Run this Method in Phase 4 - Numerical Eval/);
  assert.match(documentNamed(superseded, "computation").html, /CUSTOM_SCIENTIFIC_UPDATE/);
  assert.ok(documentNamed(superseded, "computation").sources.some(({ reference }) => reference === old.generation_ref));
});

test("only a genuinely empty catalog marks the additional-work start state", () => {
  const empty = render.reader({}); assert.equal(empty.issueContext.emptyState, true);
  assert.equal((empty.html.match(/Published proposals will appear here/g) || []).length, 1);
  assert.doesNotMatch(empty.html, /No lead comparison has been published/);
  const cards = render.reader({ cards: [{ card_id: "legacy.card", title: "Legacy scientific account", definition: "Preserved original definition.", generation_ref: reference("theory_method_cards") }] });
  assert.equal(cards.issueContext.emptyState, false); assert.match(cards.html, /Preserved original definition/);
});

test("legacy disclosure and tab preferences do not automatically open a reading window", () => {
  const key = proposalKey(proposal);
  const legacy = [
    { modelDisclosures: { [key]: { assumptions: true, computation: false, review: true }, "run.other:proposal.other": { computation: true } } },
    { modelDisclosures: { "run.other:proposal.other": { assumptions: true } } },
    { tab: "computation" },
  ];
  for (const reading of legacy) {
    const result = render.reader({ ...props, reading });
    assert.doesNotMatch(result.html, /role="dialog"|p2-reader-disclosure|Complete original algorithm/);
    assert.equal((result.html.match(/class="[^"]*p2-reading-button[^"]*"/g) || []).length, 4);
    assert.match(selectedAccount(result.html), /Authored essential inputs/);
    assert.match(documentNamed(result, "computation").html, /Complete original algorithm/);
  }
});

test("supporting documents preserve exact run-matched specialist findings, applicability and statement pointers", () => {
  const statement = "/method/mathematical_definition/canonical_definition/objective_or_estimating_equation";
  const review = { review_id: "review.exact", role: "theorist", generation_ref: reference("theory_review", "generation.audit"), assessments: [{
    proposal_id: proposal.proposal_id, headline: "Conditional inference remains unverified.",
    applicability_markdown: "Independent units are needed for the stated analysis.",
    assessment_markdown: "The target and algorithm are distinct claims.", findings: [{ finding_id: "finding.exact", title: "Unproved coverage",
      consequence_markdown: "Use only the stated point estimate until coverage is checked.",
      statement_reference: "The original estimating equation.", reasoning_markdown: "An estimating equation alone does not establish coverage.", statement_refs: [statement] }],
  }] };
  const unrelated = { ...review, generation_ref: reference("theory_review", "generation.other", "run.other"), assessments: [{ proposal_id: proposal.proposal_id, assessment_markdown: "UNRELATED_REVIEW_MUST_NOT_APPEAR" }] };
  const result = render.reader({ ...props, reviews: [unrelated, review] });
  const assumptions = documentNamed(result, "assumptions"), reviews = documentNamed(result, "review");
  assert.match(assumptions.html, /Independent units are needed/);
  assert.ok(assumptions.sources.some(({ reference }) => reference.generation_id === "generation.audit" && reference.entry_pointer === "/assessments/0/applicability_markdown"));
  for (const text of ["Conditional inference remains unverified", "The target and algorithm are distinct claims", "Unproved coverage", "Use only the stated point estimate", "The original estimating equation", "does not establish coverage"]) assert.ok(reviews.html.includes(text), text);
  assert.ok(reviews.sources.some(({ reference }) => reference.generation_id === proposal.generation_ref.generation_id && reference.entry_pointer === statement));
  assert.ok(reviews.sources.some(({ reference }) => reference.generation_id === "generation.audit"));
  assert.doesNotMatch(assumptions.html + reviews.html, /UNRELATED_REVIEW_MUST_NOT_APPEAR|generation.other/);
  assert.doesNotMatch(result.html, /Unproved coverage|Independent units are needed/);
});


test("the proposed-method summary preserves prose without raw audit links or a shared-setting shortcut", () => {
  const review = { review_id: "review.exact", generation_ref: reference("theory_review"), assessments: [] };
  const comparison = { ...assessment, overview_markdown: "The model needs validation. [Theorist audit](#review.exact); [Empirical audit](#review.empirical). See [the publication](https://doi.org/10.1234/exact)." };
  const before = structuredClone(comparison);
  const html = render.reader({ ...props, reviews: [review], comparisons: [comparison], onSharedSetting: noop }).html;
  const overview = html.slice(html.indexOf("Proposed Methods"), html.indexOf("</section>"));
  assert.match(overview, /The model needs validation\. See /);
  assert.match(overview, /href="https:\/\/doi.org\/10.1234\/exact"/);
  assert.doesNotMatch(overview, /Theorist audit|Empirical audit|Lead assessment source|View research goal/);
  assert.match(overview, /Full comparison/);
  assert.deepEqual(comparison, before);
});

test("overview projection removes audit-only references without editing substantive references, code, or math", () => {
  const comparison = { ...assessment, overview_markdown: "The [independent audit](#review.exact) identifies a limit. Preserve [the proposal](#proposal.exact), `[literal audit](#review.literal)`, and $J=0$.\n\n[Theorist audit](#review.exact).\n\nThe next check remains open. [Empirical audit](#review.empirical)." };
  const html = render.reader({ ...props, comparisons: [comparison] }).html;
  const overview = html.slice(html.indexOf("Proposed Methods"), html.indexOf("</section>"));
  assert.match(overview, /The <span>independent audit<\/span> identifies a limit/);
  assert.match(overview, /<span>the proposal<\/span>/);
  assert.match(overview, /<code>\[literal audit\]\(#review.literal\)<\/code>/);
  assert.match(overview, /class="katex/);
  assert.match(overview, /The next check remains open\.<\/p>/);
  assert.doesNotMatch(overview, /Theorist audit|Empirical audit|<p>\s*[.;]\s*<\/p>/);
});
test("full comparisons move into a source-bound reader without duplicating the current history body", () => {
  const comparison = { ...assessment, comparison_markdown: "FULL_COMPARISON_START\n$$V(\\pi)=\\mathbb E_\\pi R.$$\nOnly under the stated observation condition. FULL_COMPARISON_END" };
  const before = structuredClone(comparison);
  const result = render.reader({ ...props, comparisons: [comparison] });
  assert.match(result.html, /Full comparison/);
  assert.doesNotMatch(result.html, /FULL_COMPARISON_START|FULL_COMPARISON_END/);
  const full = render.comparisons({ comparison, proposals: [proposal] }).find(item => item.name === "comparison");
  assert.match(full.html, /FULL_COMPARISON_START/);
  assert.match(full.html, /Only under the stated observation condition/);
  assert.match(full.html, /FULL_COMPARISON_END/);
  assert.equal(full.size.equations, 1);
  assert.ok(full.sources.some(item => item.reference === comparison.generation_ref));
  assert.deepEqual(comparison, before);
});

function assertLegacyComparisonInline(overview_markdown) {
  const comparison = { ...assessment, overview_markdown, comparison_markdown: "LEGACY_FULL_ACCOUNT" };
  assert.equal(render.comparisons({ comparison, proposals: [proposal] }).filter(item => item.name === "comparison").length, 0);
  const html = render.reader({ ...props, comparisons: [comparison] }).html;
  assert.equal((html.match(/LEGACY_FULL_ACCOUNT/g) || []).length, 1);
  assert.doesNotMatch(html, /<span>Full comparison<\/span>/);
}

test("a missing comparison overview keeps the full legacy account inline once without a duplicate reader", () => assertLegacyComparisonInline(undefined));
test("an empty comparison overview keeps the full legacy account inline once without a duplicate reader", () => assertLegacyComparisonInline(""));
test("a whitespace-only comparison overview keeps the full legacy account inline once without a duplicate reader", () => assertLegacyComparisonInline(" \t\r\n "));
test("an identical comparison overview keeps the full legacy account inline once without a duplicate reader", () => assertLegacyComparisonInline("LEGACY_FULL_ACCOUNT"));
