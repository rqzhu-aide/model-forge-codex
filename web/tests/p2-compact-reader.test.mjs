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
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Methods from '${src}/components/MethodProposals.jsx'; export function reader(props) { let issueContext, furtherContext; const html=renderToStaticMarkup(<Methods {...props} issues={context=>{issueContext=context;return <section className='card' data-card-role='attention'><h2>Decisions to Discuss</h2></section>;}} furtherWork={context=>{furtherContext=context;return <details className='card' data-card-role='action'><summary><h2>Additional Runs and History</h2></summary><details data-reading-anchor='research-history'><summary>History and original research sources</summary>{context.modelHistory}</details></details>;}}/>); return {html,issueContext,furtherContext}; }`, resolveDir: src, loader: "jsx" }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
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
const selectedAccount = html => html.slice(html.indexOf('Methodological account</h3>'), html.indexOf('<details class="research-details p2-reader-disclosure"'));

test("a verified producing catalog selects the revised account without inferring provenance from app metadata", () => {
  for (const version of ["1.24.0", "1.24.1", "1.25.0", "2.0.0"]) assert.equal(hasConciseP2Account({ catalog_pin: { catalog_version: version, catalog_manifest_sha256: "f".repeat(64) } }), true);
  for (const record of [null, {}, { catalog_version: "1.24.0" }, { phase_contract_version: "3.10.0" }, { catalog_pin: { catalog_version: "1.24.0" } }, { catalog_pin: { catalog_version: "1.24.0", catalog_manifest_sha256: "bad" } }, { catalog_pin: { catalog_version: "1.23.99", catalog_manifest_sha256: "f".repeat(64) } }, { catalog_pin: { catalog_version: "1.24.0-preview", catalog_manifest_sha256: "f".repeat(64) } }]) assert.equal(hasConciseP2Account(record), false);
});

test("the proposal summary is separate from the selected model reader in four cards", () => {
  const before = JSON.stringify(props); const { html, issueContext, furtherContext } = render.reader(props);
  assert.equal((html.match(/<(?:section|details)\b[^>]*class="card(?: |")/g) || []).length, 4);
  assert.ok(html.indexOf("Proposed Methods") < html.indexOf("Authored comparison"));
  const overview = html.slice(html.indexOf("Proposed Methods"), html.indexOf("</section>"));
  assert.match(overview, /Authored comparison/);
  assert.doesNotMatch(overview, /<select|Methodological account/);
  assert.ok(html.indexOf("</section>") < html.indexOf("Select a Method to Explore"));
  assert.ok(html.indexOf("Select a Method to Explore") < html.indexOf("Choose a method"));
  assert.ok(html.indexOf("Run this Method in Phase 3 - Theory") < html.indexOf("Methodological account"));
  assert.ok(html.indexOf("Decisions to Discuss") < html.indexOf("Additional Runs and History"));
  const disclosures = [...html.matchAll(/<details class="research-details p2-reader-disclosure"([^>]*)><summary>([^<]+)<\/summary>/g)];
  assert.deepEqual(disclosures.map(item => item[2]), ["Assumptions and limitations", "Computation and full formulation", "Reviews and scientific sources"]);
  for (const disclosure of disclosures) assert.doesNotMatch(disclosure[1], /\bopen=/);
  assert.doesNotMatch(html, /role="tablist"|role="tabpanel"|Explore a model|What the team found/);
  assert.match(html, /data-reading-anchor="p2-selected-model" tabindex="-1"/);
  assert.strictEqual(issueContext, furtherContext); assert.strictEqual(issueContext.proposal, proposal); assert.strictEqual(issueContext.catalogMethod, catalog);
  assert.equal(issueContext.emptyState, false); assert.equal(issueContext.exploreActions, undefined); assert.ok(issueContext.modelHistory);
  assert.equal(JSON.stringify(props), before);
});

test("the revised Lead account stays whole and its exact scientific source records remain on demand", () => {
  const html = render.reader({ ...props, literatureSources: [{ source_id: "reference.exact", title: "Exact scientific reference", identifiers: [{ kind: "doi", value: "10.1234/exact" }] }] }).html;
  const account = selectedAccount(html);
  assert.match(account, /Authored essential inputs/); assert.match(account, /No uncertainty guarantee has been checked/);
  assert.match(account, /<annotation encoding="application\/x-tex">\\widehat\\beta=\\arg\\min_\{\\mathbf1\^\\top\\beta=0\}Q\(\\beta\)\.<\/annotation>/);
  assert.doesNotMatch(account, /Original proposer account|Complete original algorithm|UNIQUE_ORIGINAL_TUNING_RULE/);
  assert.match(html, /Proposer&#x27;s original summary/); assert.match(html, /Original proposer account/); assert.match(html, /Complete original algorithm/);
  assert.match(html, /CUSTOM_SCIENTIFIC_UPDATE/); assert.match(html, /Additional original formulation fields/);
  assert.match(html, /Independent Lead assessment/); assert.match(html, /Exact scientific reference/); assert.match(html, /href="https:\/\/doi.org\/10.1234\/exact"/);
  for (const text of ["UNIQUE_ORIGINAL_TUNING_RULE", "UNIQUE_COMPUTATIONAL_CONSEQUENCE", "UNIQUE_COST_ACCOUNT"]) assert.equal((html.match(new RegExp(text, "g")) || []).length, 1, text);
  assert.ok(html.indexOf('class="p2-history"') > html.indexOf("Additional Runs and History"));
});

test("historical and unknown writing provenance preserve the full Lead record without making it the default account", () => {
  const historical = "HISTORICAL_FIRST_PARAGRAPH\n\n" + "The full authored condition remains. ".repeat(60) + "\n\nHISTORICAL_FINAL_PARAGRAPH";
  for (const catalog_pin of [undefined, { catalog_version: "1.23.4", catalog_manifest_sha256: "d".repeat(64) }, { catalog_version: "1.24.0", catalog_manifest_sha256: "unknown" }]) {
    const comparison = { ...assessment, catalog_pin, method_dispositions: [{ ...assessment.method_dispositions[0], method_summary_markdown: historical }] };
    const before = structuredClone(comparison); const html = render.reader({ ...props, comparisons: [comparison], appVersion: "1.24.0" }).html;
    const account = selectedAccount(html);
    assert.match(account, /Original proposer account/); assert.match(account, /Read its complete mathematics under Computation and full formulation/);
    assert.doesNotMatch(account, /Finite calculation inputs|\\mathbf1\^\\top\\beta=0/);
    assert.match(html, /Finite calculation inputs/); assert.match(html, /\\mathbf1\^\\top\\beta=0/);
    assert.doesNotMatch(account, /HISTORICAL_FIRST_PARAGRAPH|HISTORICAL_FINAL_PARAGRAPH/);
    assert.match(html, /Full historical Lead procedural account/); assert.match(html, /HISTORICAL_FIRST_PARAGRAPH/); assert.match(html, /HISTORICAL_FINAL_PARAGRAPH/);
    assert.equal((html.match(/The full authored condition remains/g) || []).length, 60);
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
  const { html, issueContext } = render.reader({ ...props, methods: source, initialPick: catalogSelectionKey(only) });
  assert.match(html, /Catalog definitions without a linked proposal/); assert.match(html, /Complete catalog-only account/); assert.match(html, /Catalog-only original qualification/);
  assert.match(html, /Run this Method in Phase 3 - Theory/); assert.match(html, /Run this Method in Phase 4 - Numerical Eval/); assert.match(html, /generation.only/);
  assert.equal(issueContext.proposal, null); assert.equal(issueContext.method.identity, onlyIdentity); assert.strictEqual(issueContext.catalogMethod, only); assert.equal(issueContext.methodBranch, "branch.only"); assert.equal(issueContext.emptyState, false);
  const legacy = render.reader({ methods: [only], onSource: noop, onContinue: noop }).html;
  assert.match(legacy, /Choose a method/); assert.match(legacy, /Complete catalog-only account/); assert.match(legacy, /Run this Method in Phase 4 - Numerical Eval/);
  assert.deepEqual(source, before);
});

test("excluded and superseded selections preserve readable records without current-version continuation", () => {
  const excluded = { ...assessment, method_dispositions: [{ ...assessment.method_dispositions[0], status: "exclude", rationale: "Required observations remain unavailable." }] };
  const html = render.reader({ ...props, comparisons: [excluded], methods: [] }).html;
  assert.match(html, /Excluded from this catalog update/); assert.match(html, /Required observations remain unavailable/); assert.doesNotMatch(html, /Run this Method in Phase 3 - Theory|Run this Method in Phase 4 - Numerical Eval/);
  const old = { ...proposal, is_current_package: false, method: { ...proposal.method, identity: { ...identity, version: 1, definition_sha256: "f".repeat(64) } } };
  const superseded = render.reader({ ...props, proposals: [old], initialPick: proposalKey(old) }).html;
  assert.match(superseded, /Superseded by version 2/); assert.match(superseded, /View the current version \(version 2\)/); assert.doesNotMatch(superseded, /Run this Method in Phase 3 - Theory|Run this Method in Phase 4 - Numerical Eval/);
});

test("only a genuinely empty catalog marks the additional-work start state", () => {
  const empty = render.reader({}); assert.equal(empty.issueContext.emptyState, true);
  assert.equal((empty.html.match(/No method proposal has been published/g) || []).length, 1);
  assert.doesNotMatch(empty.html, /No lead comparison has been published/);
  const cards = render.reader({ cards: [{ card_id: "legacy.card", title: "Legacy scientific account", definition: "Preserved original definition.", generation_ref: reference("theory_method_cards") }] });
  assert.equal(cards.issueContext.emptyState, false); assert.match(cards.html, /Preserved original definition/);
});

test("disclosure restoration follows the exact model key and migrates a prior tab", () => {
  const key = proposalKey(proposal);
  const current = render.reader({ ...props, reading: { modelDisclosures: { [key]: { assumptions: true, computation: false, review: true }, "run.other:proposal.other": { computation: true } } } }).html;
  assert.match(current, /data-reading-anchor="p2-model:run.exact:proposal.exact:assumptions" open=""/);
  assert.match(current, /data-reading-anchor="p2-model:run.exact:proposal.exact:review" open=""/);
  assert.doesNotMatch(current, /data-reading-anchor="p2-model:run.exact:proposal.exact:computation" open/);
  const other = render.reader({ ...props, reading: { modelDisclosures: { "run.other:proposal.other": { assumptions: true } } } }).html;
  assert.doesNotMatch(other, /p2-reader-disclosure"[^>]*\bopen=/);
  const migrated = render.reader({ ...props, reading: { tab: "computation" } }).html;
  assert.match(migrated, /data-reading-anchor="p2-model:run.exact:proposal.exact:computation" open=""/);
});


test("the proposed-method summary preserves prose without raw audit links or a shared-setting shortcut", () => {
  const review = { review_id: "review.exact", generation_ref: reference("theory_review"), assessments: [] };
  const comparison = { ...assessment, overview_markdown: "The model needs validation. [Theorist audit](#review.exact); [Empirical audit](#review.empirical). See [the publication](https://doi.org/10.1234/exact)." };
  const before = structuredClone(comparison);
  const html = render.reader({ ...props, reviews: [review], comparisons: [comparison], onSharedSetting: noop }).html;
  const overview = html.slice(html.indexOf("Proposed Methods"), html.indexOf("</section>"));
  assert.match(overview, /The model needs validation\. See /);
  assert.match(overview, /href="https:\/\/doi.org\/10.1234\/exact"/);
  assert.doesNotMatch(overview, /Theorist audit|Empirical audit|<button|Lead assessment source|View research goal/);
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
