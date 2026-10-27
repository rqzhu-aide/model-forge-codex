import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { clarificationDraftKey } from "../src/contextualRequests.js";
import { assessmentKey, entryIdentity } from "../src/literatureLandscape.js";
import { neuripsSources } from "./fixtures/neurips-paper-aliases.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-ui-render-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Theory from '${src}/components/TheoryWorkbench.jsx'; import Empirical from '${src}/components/EmpiricalWorkbench.jsx'; import Literature, {SelectedPaper, LiteratureTabs, LiteratureHistory} from '${src}/components/LiteratureWorkspace.jsx'; import IssuesCard from '${src}/components/IssuesCard.jsx'; import ResearcherDialogue from '${src}/components/ResearcherDialogue.jsx'; import FurtherWorkCard from '${src}/components/FurtherWorkCard.jsx'; import Methods from '${src}/components/MethodProposals.jsx'; import {ProjectBriefEditor} from '${src}/components/ProjectBrief.jsx'; import PhaseOne from '${src}/components/PhaseOneWorkspace.jsx'; import PhaseTwoPreparation from '${src}/components/PhaseTwoPreparation.jsx'; import {ResearcherDecisions, TeamResearchFollowUp, EarlierOpenQuestions, RunCorrections, RunsAwaitingDirection} from '${src}/components/ContextualRequests.jsx'; import LaunchRun from '${src}/components/LaunchRun.jsx'; import {proposalReviews, MethodPicker, MethodReaderDisclosure, ExploreActions, SupersededNote} from '${src}/components/MethodProposals.jsx'; import {ResearchDocument, MethodStatusNote, MethodStatusPill} from '${src}/components/Shared.jsx'; import Assessments, {assessmentRepairRequest} from '${src}/components/Assessments.jsx'; import TestedTheorySource from '${src}/components/TestedTheorySource.jsx'; export const launchRun = props => renderToStaticMarkup(React.createElement(LaunchRun, props)); export const decisions = props => renderToStaticMarkup(React.createElement(ResearcherDecisions, props)); export const teamFollowUp = props => renderToStaticMarkup(React.createElement(TeamResearchFollowUp, props)); export const earlierQuestions = props => renderToStaticMarkup(React.createElement(EarlierOpenQuestions, props)); export const runCorrections = props => renderToStaticMarkup(React.createElement(RunCorrections, props)); export const waitingDirections = props => renderToStaticMarkup(React.createElement(RunsAwaitingDirection, props)); export const phaseTwoPreparation = props => renderToStaticMarkup(React.createElement(PhaseTwoPreparation, props)); export const briefEditor = props => renderToStaticMarkup(React.createElement(ProjectBriefEditor, props)); export const phaseOne = props => {
    const history = <details className='research-details run-history' data-reading-anchor='research-history'><summary>Phase run history</summary><LiteratureHistory collections={props.artifacts?.literature_collections} coverage={props.artifacts?.literature_coverage} bases={props.artifacts?.research_bases} displayedBasis={props.basis} libraries={props.artifacts?.literature_libraries} cards={props.cards} onSource={props.onSource}/><EarlierOpenQuestions items={props.attentionItems} answers={props.researcherAnswers} branch='trunk' phase='P1' settingQuestions={props.basis?.research_setting?.clarification_questions} settingReference={props.basis?.generation_ref} onSource={props.onSource}/></details>;
    return renderToStaticMarkup(<PhaseOne {...props} issues={<ResearcherDialogue project={props.project} problemContext={props.project.problem_context} projectId={props.project.project_id} phase='P1' branch='trunk' attention={props.attentionItems} answers={props.researcherAnswers} onSource={props.onSource} onSaved={props.onSaved}/>} furtherWork={<FurtherWorkCard projectId={props.project.project_id} phase='P1' branch='trunk' onStarted={props.onLaunch} history={history}/>}/>);
  }; export const literatureTabs = props => LiteratureTabs(props); export const matchingReviews = proposalReviews; export const methodPicker = props => MethodPicker(props); export const methodReaderDisclosure = props => MethodReaderDisclosure(props); export const exploreActions = props => ExploreActions(props); export const supersededNote = props => SupersededNote(props); export const testedTheory = props => renderToStaticMarkup(React.createElement(TestedTheorySource, props)); export const selectedPaper = props => renderToStaticMarkup(React.createElement(SelectedPaper, props)); export const literature = props => renderToStaticMarkup(<><Literature {...props}/><LiteratureHistory {...props} bases={props.bases || (props.basis ? [{branch:"trunk",phase:"P1",...props.basis}] : [])}/></>); export const methods = props => renderToStaticMarkup(<Methods {...props} issues={context => <IssuesCard projectId={props.projectId} phase='P2' branch={context.methodBranch} methodId={context.methodId} methodLabel={context.method?.title} attention={context.catalogMethod ? context.requests : []} answers={context.catalogMethod ? context.answers : []} onSource={props.onSource}/>} furtherWork={context => <section className='card' data-card-role='action'><h2>Further model development</h2>{context.modificationOptions}{context.proposedWork}{context.modelHistory}</section>}/>); export const methodsRaw = props => renderToStaticMarkup(React.createElement(Methods, props)); export const theory = props => renderToStaticMarkup(React.createElement(Theory, props)); export const empirical = props => renderToStaticMarkup(React.createElement(Empirical, props)); export const assessments = props => renderToStaticMarkup(React.createElement(Assessments, props)); export const repairRequest = assessmentRepairRequest; export const document = text => renderToStaticMarkup(React.createElement(ResearchDocument, {text})); export const methodStatusNote = props => renderToStaticMarkup(React.createElement(MethodStatusNote, props)); export const methodStatusPill = props => renderToStaticMarkup(React.createElement(MethodStatusPill, props));`, resolveDir: src, loader: "jsx" },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") },
  logLevel: "silent",
});
const render = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};
const buttonNamed = (html, label) => [...html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].find((match) => match[2].replace(/<[^>]*>/g, "") === label);
const renderedText = html => html.replace(/<[^>]*>/g, "");
const ref = { branch: "method.a", phase: "P3", family: "theory_record", generation_id: "gen.a", sha256: "a".repeat(64), run_id: "run.a" };

test("linked association formulas render as display math with their exact supplied TeX bodies", () => {
  const fixture = JSON.parse(fs.readFileSync(new URL("./fixtures/p3-linked-association-equations.json", import.meta.url), "utf8"));
  const decode = (text) => text.replaceAll("&amp;", "&").replaceAll("&lt;", "<").replaceAll("&gt;", ">").replaceAll("&quot;", '"').replaceAll("&#x27;", "'");
  for (const { token, latex } of fixture.blocks) {
    const html = render.document(`Before.\n${token}\nAfter.`);
    assert.equal((html.match(/class="katex-display"/g) || []).length, 1);
    assert.doesNotMatch(html, /katex-error/);
    const annotation = html.match(/<annotation encoding="application\/x-tex">([\s\S]*?)<\/annotation>/)?.[1];
    assert.equal(decode(annotation), latex, "The reader's KaTeX body is the exact supplied equation interior.");
    assert.match(html, /Before/); assert.match(html, /After/);
  }
});

test("research documents preserve heading hierarchy, step numbering and scientific tables", () => {
  const html = render.document("# Procedure\n## Initialization\n3. Set $x_0=0$.\n   - Record the seed.\n4. Iterate.\n\n### Measurements\n| Statistic | Value |\n| --- | --- |\n| $P(A|B)$ | 0.000001 |\n\n```tex\n<script>literal</script>\n```");
  assert.match(html, /<h3>Procedure<\/h3>/); assert.match(html, /<h4>Initialization<\/h4>/); assert.match(html, /<h5>Measurements<\/h5>/);
  assert.match(html, /<ol start="3"><li value="3">/); assert.match(html, /<li value="4">/);
  assert.match(html, /<ul><li><p>Record the seed/); assert.match(html, /tabindex="0" role="region" aria-label="Research table/);
  assert.match(html, /<th scope="col">Statistic/); assert.match(html, /P\(A\|B\)/);
  assert.match(html, /&lt;script&gt;literal&lt;\/script&gt;/); assert.doesNotMatch(html, /<script>|katex-error/);
  const algorithm = render.document({ canonical_definition: { algorithm_or_update_rule: [{ operation: "Initialize." }, { operation: "Update." }] } });
  assert.match(algorithm, /<ol class="research-algorithm">/);
});

test("P3 inventory keeps readable labels, probe mathematics and exact literature sources", () => {
  const html = render.theory({ branch: "method.a", selected: "statement.a", onSelect: noop, onSource: noop, onRequest: noop,
    claimMaps: [{ phase: "P3", branch: "method.a", generation_ref: ref, claims: [{ statement_id: "statement.a", label: "Central convergence claim", proof_status: "sketch", depends_on: ["assumption.a"], novelty_refs: ["lit.verified", "lit.missing"], novelty_links: [{ identifier: "lit.verified", label: "Earlier convergence theorem", generation_ref: { ...ref, phase: "P1", branch: "trunk", family: "literature_entry" } }, { identifier: "lit.verified", label: "Independent operational account", generation_ref: { ...ref, phase: "P1", branch: "trunk", family: "data_analyst_paper_cards" } }, { identifier: "lit.missing", label: "Missing source", source_error: "The frozen source is unavailable." }] }], assumptions: [{ assumption_id: "assumption.a", label: "Finite second moment" }] }],
    glossaries: [], falsificationLogs: [{ phase: "P3", branch: "method.a", generation_ref: ref, probes: [{ probe_id: "probe.a", target_statement: "statement.a", outcome: "not_tested", method: "Boundary check", detail: "The case $n=1$ was not tested." }] }],
  });
  assert.match(html, /Claims and their support/); assert.match(html, /Finite second moment/); assert.match(html, /Proof sketch/);
  assert.match(html, /Earlier convergence theorem/); assert.match(html, /Independent operational account/); assert.match(html, /Read supporting literature/); assert.match(html, /The frozen source is unavailable/);
  assert.match(html, /Not tested/); assert.match(html, /class="katex"/); assert.doesNotMatch(html, />not_tested</);
});

test("P1 displays retained literature with status, assessments and current search limits", () => {
  const p1 = { branch: "trunk", phase: "P1", generation_ref: { ...ref, branch: "trunk", phase: "P1", family: "literature_library" } };
  const html = render.literature({ onSource: noop, libraries: [{ ...p1, total_sources: 2, changes: { added: 1, updated: 1, rediscovered: 0 }, sources: [
    { source_id: "citation.earlier", title: "Earlier useful reference", authors: ["Ada Example"], year: 2022, source_status: "active", identifiers: [{ kind: "doi", value: "10.12345/paper" }], cards: [{ card_id: "card.old", assessment_predates_source_revision: true, innovation: "Retained convergence guarantee.", definition: "The invariant law is $\\pi$.", evaluation: "Equal cost remains untested.", generation_ref: p1.generation_ref }] },
    { source_id: "citation.retracted", title: "Retracted comparison", source_status: "retracted", status_reason: "The reference was withdrawn by its authors." },
  ] }], coverage: [{ ...p1, scientific_outcome: { conclusion: "The search does not cover non-English literature.", scope: "English-language publications." } }] });
  assert.match(html, /Accepted source records<\/dt><dd class="literature-count-value">2<\/dd>/);
  assert.match(html, /1 new · 1 updated · 0 found again/);
  assert.match(html, /Earlier useful reference/);
  assert.doesNotMatch(html, /Retained convergence guarantee|Equal cost remains untested|selected-paper/);
  assert.match(html, /Choose a paper to read/);
  assert.match(html, /Retracted/);
  assert.doesNotMatch(html, /withdrawn by its authors/); // Only the selected paper is expanded.
  assert.match(html, /does not cover non-English/);
  assert.doesNotMatch(html, /"source_id"/);
});

test("P1 counts one paper for verified URL aliases and restores either original source's exact assessment", () => {
  const before = JSON.stringify(neuripsSources);
  const library = { branch: "trunk", phase: "P1", total_sources: 2, sources: neuripsSources };
  for (const source of neuripsSources) {
    const card = source.cards[0];
    const html = render.literature({ libraries: [library], onSource: noop, reading: {
      paperId: source.source_id, entrySelection: { sourceId: source.source_id, reference: entryIdentity(card) },
    } });
    assert.match(html, /Paper \(1\)/);
    assert.match(html, /Accepted source records<\/dt><dd class="literature-count-value">2<\/dd>/);
    assert.match(html, /Current linked member assessments<\/dt><dd class="literature-count-value">2<\/dd>/);
    assert.equal((html.match(/<option[^>]*>Occam/g) || []).length, 1);
    assert.match(html, /<option[^>]*>Research Lead<\/option>/);
    assert.match(html, /<option[^>]*>Theorist<\/option>/);
    assert.ok(html.includes(card.explanation_markdown));
    assert.ok(html.includes(`data-reading-anchor="paper:${source.source_id}"`), "Saved reading anchors retain the original source identity.");
    assert.ok(html.includes(`href="${source.identifiers[0].value}"`));
    assert.ok(html.includes(`Synthetic ${card.role} search`));
    assert.doesNotMatch(html, /exact referenced assessment is unavailable/);
  }
  const second = neuripsSources[1]; const card = second.cards[0];
  const citationBasis = { generation_ref: { generation_id: "basis.aliases" }, citations: [{
    source_id: second.source_id, canonical_source_id: second.source_id, entry_ref: entryIdentity(card),
    status: "available", bibliography: card.source, card,
  }] };
  const cited = render.literature({ libraries: [library], basis: citationBasis, reading: {
    paperId: second.source_id, entrySelection: { sourceId: second.source_id, reference: entryIdentity(card), citationBasisId: "basis.aliases" },
  } });
  assert.match(cited, /Showing Theorist&#x27;s exact assessment/);
  assert.ok(cited.includes(card.explanation_markdown));
  assert.doesNotMatch(cited, /Synthetic research_lead assessment|exact referenced assessment is unavailable/);
  const filtered = render.literature({ libraries: [library], basis: { landscape: { topics: [{ topic_id: "topic.alias", title: "Synthetic topic", source_ids: [second.source_id] }] } }, reading: { topicId: "topic.alias", query: "Synthetic theorist assessment", paperId: second.source_id } });
  assert.match(filtered, /Paper \(1\)/);
  assert.equal((filtered.match(/<option[^>]*>Occam/g) || []).length, 1);
  assert.equal(JSON.stringify(neuripsSources), before);
});

test("a citation to grouped sources selects its exact member record even when both sources share a role", () => {
  const sources = neuripsSources.map((source) => ({ ...source, cards: source.cards.map((card) => ({ ...card, role: "research_lead", family: "lead_literature" })) }));
  const source = sources[1]; const card = source.cards[0];
  const citationBasis = { generation_ref: { generation_id: "basis.same-role" }, citations: [{
    source_id: source.source_id, canonical_source_id: source.source_id, entry_ref: entryIdentity(card),
    status: "available", bibliography: card.source, card,
  }] };
  const html = render.literature({ libraries: [{ branch: "trunk", phase: "P1", sources }], basis: citationBasis, reading: {
    paperId: source.source_id, entrySelection: { sourceId: source.source_id, reference: entryIdentity(card), citationBasisId: "basis.same-role" },
  } });
  assert.ok(html.includes(`value="${assessmentKey(card)}" selected=""`));
  assert.ok(html.includes(card.explanation_markdown));
});

test("P1 presents the lead summary before distinct retained-record and member-assessment counts", () => {
  const html = render.literature({
    basis: { landscape: { summary_markdown: "The lead's original landscape synthesis." } },
    libraries: [{ branch: "trunk", phase: "P1", total_sources: 2, changes: { added: 1, updated: 0, rediscovered: 1 }, sources: [
      { source_id: "paper.one", source_ids: ["paper.one", "paper.alias"], title: "First paper", cards: [
        { entry_id: "entry.lead", role: "research_lead", assessment_history: [{ entry_id: "entry.lead.earlier" }] },
        { entry_id: "entry.theory", role: "theorist" },
      ] },
      { source_id: "paper.two", title: "Earlier withdrawn record", source_status: "withdrawn", cards: [{ entry_id: "entry.analyst", role: "data_analyst", from_earlier_run: true }] },
    ] }],
    cards: [{ card_id: "card.unlinked", subject_ref: "paper.unresolved", title: "Unlinked earlier assessment" }],
  });
  assert.match(html, /Accepted source records<\/dt><dd class="literature-count-value">2<\/dd>/);
  assert.match(html, /Current linked member assessments<\/dt><dd class="literature-count-value">3<\/dd>/);
  assert.match(html, /paper selector groups verified equivalent publication links/);
  assert.match(html, /latest linked account by each member for each source/);
  assert.match(html, /<details[^>]*data-reading-anchor="earlier-synthesis"><summary>Read the earlier literature synthesis<\/summary>/);
  assert.ok(html.indexOf("The lead&#x27;s original landscape synthesis") < html.indexOf("literature-statistics"));
  assert.ok(html.indexOf("literature-statistics") > html.indexOf("literature-controls"));
  assert.ok(html.indexOf("literature-library-counts") > html.indexOf("Literature accounts, search scopes and review"));
  assert.match(html, /Additional member records \(1\)/);
  assert.match(html, /Latest update: 1 new · 0 updated · 1 found again/);
});

test("P1 counts legacy sources without inventing unavailable totals or conflating an empty library with no library", () => {
  const legacy = render.literature({ libraries: [{ branch: "trunk", phase: "P1", sources: [{ source_id: "paper.old", title: "Older paper", card: { card_id: "card.old" } }] }] });
  assert.match(legacy, /Accepted source record<\/dt><dd class="literature-count-value">1<\/dd>/);
  assert.match(legacy, /Current linked member assessment<\/dt><dd class="literature-count-value">1<\/dd>/);
  const noAssessments = render.literature({ libraries: [{ branch: "trunk", phase: "P1", sources: [{ source_id: "paper.old", title: "Bibliography only" }] }] });
  assert.match(noAssessments, /Accepted source record<\/dt><dd class="literature-count-value">1<\/dd>/);
  assert.doesNotMatch(noAssessments, /Current linked member/);
  const empty = render.literature({ libraries: [{ branch: "trunk", phase: "P1", total_sources: 0, sources: [], changes: {} }] });
  assert.match(empty, /Accepted source records<\/dt><dd class="literature-count-value">0<\/dd>/);
  assert.doesNotMatch(empty, /Latest update:/);
  const unavailable = render.literature({ cards: [{ card_id: "card.legacy", title: "Earlier source assessment" }] });
  assert.match(unavailable, /A record count is not available until a published literature library can be loaded/);
  assert.doesNotMatch(unavailable, /literature-count-value/);
  assert.match(unavailable, /Earlier source assessment/);
});

test("P2 retains catalog entries when the latest run only authored another method card", () => {
  const html = render.methods({ onSource: noop, methods: [{ method_id: "method.old", title: "Earlier method", version: 2, status: "proposed", definition: { summary: "Preserves the target marginal.", limitations: ["Mixing has not been established."] }, source_ref: ref }], cards: [{ card_id: "card.new", subject_ref: "method.new", title: "New method", innovation: "A different coupling." }] });
  assert.match(html, /Earlier method/);
  assert.match(html, /Version 2/);
  assert.match(html, /Preserves the target marginal/);
  assert.match(html, /Mixing has not been established/);
  assert.match(html, /New method/);
});

test("published nested P1 coverage shows search areas, exclusions and gaps without internal bookkeeping", () => {
  const coverage = {
    scientific_outcome: { conclusion: "The focused basis does not establish novelty." },
    coverage: {
      frozen_library: { generation_id: "literature.internal", result: "Private frozen-library bookkeeping" },
      packet_candidates: 18, retained_count: 12,
      duplicate_merges: [{ work: "Merge bookkeeping", result: "Merged internal source aliases" }],
      covered_areas: [{ area: "Expected-cost constrained MDP foundations", sources: ["src.internal"] },
        { area: "Distributional and model-based alternatives", sources: ["src.other"] }],
      focused_exclusions: [{ work: "Earlier CVaR study", reason: "The retained paper covers general losses.", status: "active; excluded for overlap" }],
      open_gaps: ["Finite-sample offline guarantees were not searched systematically."],
      status_audit: "No exhaustive retraction-database search was performed.",
      novelty_statement: "No novelty conclusion follows from this search.",
    },
    content_sha256: "digest.internal",
  };
  const before = JSON.stringify(coverage);
  const html = render.literature({ onSource: noop, coverage: [{ branch: "trunk", phase: "P1", structured: coverage }] });
  for (const text of ["Expected-cost constrained MDP foundations", "Distributional and model-based alternatives",
    "Earlier CVaR study", "The retained paper covers general losses", "excluded for overlap",
    "Finite-sample offline guarantees", "No exhaustive retraction-database search", "No novelty conclusion"]) {
    assert.ok(html.includes(text), text);
  }
  assert.doesNotMatch(html, /no readable research account|literature\.internal|src\.internal|digest\.internal|Merge bookkeeping|frozen-library bookkeeping|packet_candidates/);
  assert.equal(JSON.stringify(coverage), before);
});

test("published nested P1 synthesis renders the formulation, named algorithms and prospective experiment", () => {
  const synthesis = {
    scientific_outcome: { conclusion: "Known-model development can proceed." },
    synthesis: {
      formulation_semantics: { resource_cost_overrun: "Expected overrun combines frequency and severity.",
        cvar_comparison: "The budget threshold is fixed, unlike the optimized CVaR threshold.",
        reward_shortfall: "Reward deficiency differs from resource-cost excess." },
      manuscript_audit: { status: "Page-specific prose was not inspected.", reward_identity: "The signed-reward identity telescopes.",
        cost_identity: "The cost increments telescope.", residual_coordinate: "The residual can be unbounded.",
        convexity_boundary: "Convexity in neural parameters does not follow." },
      policy_class_reconciliation: "Residual-aware policies form a larger class.",
      algorithm_options: [{ family: "Direct trajectory Lagrangian learner", data_regime: "Simulator or online",
        learns: "Learns a policy and nonnegative multiplier.", policy_class: "Declare the differentiable policy class.",
        constraint_handling: "Primal-dual updates use the sampled hinge.", failure_boundary: "Rare events increase variance." }],
      recommended_preliminary_design: { choice: "Three-decision absorbing MDP", reason: "The remaining tail is exactly zero.",
        environment: "Safe and rare-cost actions are available.", calibration_gate: "Check for dominated frontier arms.",
        offline_coverage: "Compare positive and zero action support.", comparators: ["Expected-overrun oracle", "Distributional critic"],
        metrics: ["Expected positive overrun", "Violation probability"], separation: "Use independent final evaluation trajectories.",
        status: "Prospective only; no simulation was executed." },
      coverage_and_provenance: { candidate_works_seen: 18, retained_sources: 12, deduplication: "Internal alias merges",
        focused_exclusions: ["A broader benchmark needs a criterion-specific layer."], status_check: "Retraction checks were limited.",
        novelty_limit: "The search cannot establish novelty." },
    },
    work_summaries: [{ source_id: "src.internal", key_contribution: "An explicit distributional method.", relevance_to_question: "Provides a tail-law comparator." }],
  };
  const before = JSON.stringify(synthesis);
  const html = render.literature({ onSource: noop, syntheses: [{ branch: "trunk", phase: "P1", kind: "full", structured: synthesis }] });
  for (const text of ["Expected overrun combines frequency and severity", "The budget threshold is fixed", "Reward deficiency differs",
    "Page-specific prose was not inspected", "The signed-reward identity telescopes", "The cost increments telescope",
    "The residual can be unbounded", "Convexity in neural parameters", "Residual-aware policies form a larger class",
    "Direct trajectory Lagrangian learner", "Simulator or online", "Learns a policy", "Declare the differentiable policy class",
    "Primal-dual updates", "Rare events increase variance", "Three-decision absorbing MDP", "The remaining tail is exactly zero",
    "Safe and rare-cost actions", "dominated frontier arms", "positive and zero action support", "Expected-overrun oracle",
    "Distributional critic", "Expected positive overrun", "Violation probability", "independent final evaluation trajectories",
    "Prospective only; no simulation was executed", "criterion-specific layer", "Retraction checks were limited",
    "The search cannot establish novelty", "Provides a tail-law comparator"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /no readable research account|Internal alias merges|src\.internal|candidate_works_seen|retained_sources/);
  assert.equal(JSON.stringify(synthesis), before);
});

test("structured reviews expose findings while metadata stays out of the narrative", () => {
  const html = render.document({ report_id: "report.internal", source_run_id: "run.internal", overall_assessment: "The marginal argument is incomplete.", prioritized_issues: [{ issue_id: "issue.internal", issue: "The invariant law is assumed.", scientific_consequence: "Samples may target another law.", requested_resolution: "Derive the stationary marginal.", severity: "major" }] });
  assert.match(html, /The marginal argument is incomplete/);
  assert.match(html, /Samples may target another law/);
  assert.match(html, /Derive the stationary marginal/);
  assert.doesNotMatch(html, /report\.internal|run\.internal|issue\.internal|<pre/);
  const unknown = render.document({ execution_trace: "secret machinery", content_sha256: "a".repeat(64) });
  assert.match(unknown, /no readable research account/);
  assert.doesNotMatch(unknown, /secret machinery|<pre/);
});

test("typed question scope does not create an empty section and genuine empty records keep their fallback", () => {
  const issue = { attention_id: "attention.p2.reference-identification", scope: { kind: "project" },
    context_markdown: "Reference regret depends on the joint law of the informed preference and actual choice $D$.",
    question: "What reference-regret quantities are identified under the declared anchor laws?",
    likely_consequence: "Distinguishes identified decision quality from supplied-model sensitivity." };
  const html = render.document(issue);
  for (const text of ["Mathematical context", issue.question, issue.likely_consequence]) assert.ok(html.includes(text), text);
  assert.match(html, /class="katex/);
  assert.doesNotMatch(html, /Scope<\/h\d>|no readable research account/);
  const authored = render.document({ scope: "Finite supplied-model scope." });
  assert.match(authored, /Scope<\/h\d>/);
  assert.match(authored, /Finite supplied-model scope/);
  assert.doesNotMatch(authored, /no readable research account/);
  assert.match(render.document({ scope: { kind: "project" } }), /no readable research account/);
});

test("historical theory inspection renders the recorded component and its dependencies", () => {
  const html = render.testedTheory({ componentId: "statement.main", onCurrentTheory: noop, document: {
    statements: [{ statement_id: "statement.main", label: "Original bound", text: "This is the tested argument.", latex: "E_n = O(n^{-1/2})", assumption_ids: ["assumption.iid"] }, { statement_id: "statement.other", text: "Unrelated full theory passage" }],
    assumptions: [{ assumption_id: "assumption.iid", label: "Independent samples", text: "Observations are independent." }],
  } });
  assert.match(html, /Original bound/);
  assert.match(html, /class="katex/);
  assert.match(html, /Independent samples/);
  assert.match(html, /current theory may differ/);
  assert.match(html, /Open current theory graph/);
  assert.doesNotMatch(html, /Unrelated full theory passage/);
});

test("rendered theory keeps equations, keyboard controls, exact-source assessment and revision", () => {
  const html = render.theory({ branch: "method.a", selected: "statement.main", onSelect: noop, onRequest: noop, onSource: noop,
    claimMaps: [{ branch: "method.a", phase: "P3", theory_generation_ref: ref, claims: [{ statement_id: "statement.main", label: "Main theorem", latex: "\\theta^2=1", proof_status: "full", depends_on: ["assumption.base"] }], assumptions: [{ assumption_id: "assumption.base", label: "Independent samples", text: "Observations are independent." }] }, { branch: "method.b", phase: "P3", claims: [{ statement_id: "statement.private", label: "Other method theorem", proof_status: "missing" }] }],
    falsificationLogs: [{ branch: "method.a", phase: "P3", probes: [{ probe_id: "probe.limit", target_statement: "statement.main", method: "Boundary case", outcome: "holds", detail: "Checked the limiting example." }] }], glossaries: [],
  });
  assert.match(html, /class="katex/);
  assert.match(html, /role="button" tabindex="0"/);
  assert.match(html, /Request an assessment/);
  assert.match(html, /Prepare theory revision/);
  assert.match(html, /Boundary case/);
  assert.match(html, /Open source/);
  assert.doesNotMatch(html, /Other method theorem/);
});
test("rendered P4 evidence keeps source figures without another method", () => {
  const html = render.empirical({ branch: "method.a", onSource: noop,
    diagnostics: [{ branch: "method.a", phase: "P4", diagnostics_id: "diag.a", generation_ref: { ...ref, phase: "P4" }, headline_numbers: [{ case_id: "case.det", metric: "error", estimate: null, mcse: null, uncertainty_kind: "not_applicable" }], stability: Array.from({ length: 6 }, (_, i) => ({ case_id: `case.${i}`, metric: "error", mean: 1, sd: 0.1, n_seeds: 8, seed_flip: i === 5 })), solver_health: [], runtime: { total_ms: 20, per_case: [] } }],
    exhibits: [{ branch: "method.a", phase: "P4", exhibit_id: "exhibit.a", title: "Applicable conditions", caption: "The result varies by regime.", media_type: "image/svg+xml", artifact_url: "/api/v1/figure.svg" }, { branch: "method.b", phase: "P4", exhibit_id: "exhibit.b", title: "Private other-method result", media_type: "image/svg+xml", artifact_url: "/api/v1/wrong.svg" }],
  });
  assert.match(html, /src="\/api\/v1\/figure.svg"/);
  assert.match(html, /Experiments and Results/);
  assert.match(html, /Complete numerical results and recorded diagnostics/);
  assert.doesNotMatch(html, /Private other-method result|wrong\.svg|NaN|95% CI/);
});
test("research documents render math and keep authored HTML inert", () => {
  const html = render.document("# A mathematical statement\n\nThe bound is $\\theta^2$.\n\n<img src=x onerror=alert(1)>\n\n[Unsafe](javascript:alert)");
  assert.match(html, /class="katex/);
  assert.match(html, /&lt;img/);
  assert.doesNotMatch(html, /<img src=x|href="javascript:/);
});
test("focused assessment preserves limits, proposed next steps, exact sources, and revision context", () => {
  const assessment = { assessment_id: "assessment.saved", target: { ...ref, object_id: "statement.main", kind: "statement" }, summary: "The argument needs another condition.", limitations: ["Dependent observations were not checked."], suggested_actions: ["Explore a mixing condition."], evidence_refs: [{ family: ref.family, generation_id: ref.generation_id }, { family: "diagnostics", generation_id: "gen.evidence", generation_ref: { ...ref, phase: "P4", family: "diagnostics", generation_id: "gen.evidence" } }], messages: [{ role: "researcher", content: "Would mixing suffice?" }] };
  const html = render.assessments({ projectId: "project.test", assessments: [assessment], selectedNode: "statement.main", onStarted: noop, onRepair: noop, onSource: noop });
  assert.match(html, /What was not checked/);
  assert.match(html, /Dependent observations were not checked/);
  assert.match(html, /Possible next steps/);
  assert.match(html, /Explore a mixing condition/);
  assert.match(html, /Would mixing suffice/);
  assert.match(html, /Assessed component and evidence sources/);
  assert.equal((html.match(/Open source/g) || []).length, 3);
  assert.match(html, /Diagnostics/);
  assert.match(html, /Prepare theory revision/);
  const request = render.repairRequest(assessment);
  assert.equal(request.assessment_id, assessment.assessment_id);
  assert.equal(request.assessment, assessment);
  assert.deepEqual(request.target, assessment.target);
  assert.equal(request.mode, "p3.theory_revision");
});


test("P1 retains setting and literature while method preparation moves to P2", () => {
  const p1ref = { ...ref, branch: "trunk", phase: "P1", family: "research_basis" };
  const basis = { generation_ref: p1ref, research_setting: { statement_markdown: "Requested constraint:\n\\[\\mathbb E_\\pi[(C-B)_+]\\leq\\epsilon\\]", clarification_questions: ["Specify the admissible policy class."] }, phase2_preparation: { instructions_markdown: "Develop methods for the declared constrained objective.", supplied_method: { title: "Researcher's operator", specification_markdown: "\\[T_\\pi Q=Q\\]", source_reference: "Manuscript, equation 4" } }, landscape: { summary_markdown: "The literature treats distinct risk criteria.", topics: [] }, coverage_limits: [] };
  const html = render.phaseOne({ project: { project_id: "project.test", research_instructions: "Original instructions", setting_amendments: [{ text: "Allow randomized policies.", created_at: "2026-09-10T20:00:00Z" }] }, basis, artifacts: {}, cards: [], onSource: noop, onSaved: noop, onLaunch: noop });
  for (const text of ["Research Setting", "Main Findings", "Decisions to Discuss", "Explore Individual Papers", "Instructions and run settings", "Specify the admissible policy class"]) assert.ok(html.includes(text), text);
  assert.match(html, /class="katex/);
  assert.equal((html.match(/<(?:section|details)\b[^>]*class="card(?: |")/g) || []).length, 5);
  assert.doesNotMatch(html, /<h2>Issues and decisions<\/h2>/);
  assert.doesNotMatch(html, /Current scientific account|What the literature establishes|The team&#x27;s account|Partly supported/);
  assert.doesNotMatch(html, /Is there anything you want to modify|Save setting changes|setting-amendment/);
  assert.doesNotMatch(html, /Next research step|Develop methods in Phase 2|Prepare Phase 2 run|Additional instructions or ideas for Phase 2|Published sources and member assessments/);
  const p2 = render.phaseTwoPreparation({ basis, instructions: "Compare sample requirements.", onInstructionsChange: noop, onLaunch: noop, onSource: noop });
  for (const text of ["Notes from Phase 1", "Develop methods for the declared constrained objective", "Manuscript, equation 4", "Compare sample requirements", "Additional instructions or ideas for Phase 2", "Prepare Phase 2 run", "Phase 1 notes source"]) assert.ok(p2.includes(text), text);
  assert.match(p2, /These additions go only to the Research Lead/);
  assert.match(p2, /class="katex/);
});

test("legacy P1 keeps the original brief in its editor without inventing a mathematical setting", () => {
  const html = render.phaseOne({ project: { project_id: "legacy", research_instructions: "Original unmodified brief." }, artifacts: {}, onSaved: noop, onLaunch: noop });
  assert.doesNotMatch(html, /Original unmodified brief|Saved project instructions/);
  assert.ok(buttonNamed(html, "Project instructions"));
  const editor = render.briefEditor({ project: { project_id: "legacy", research_instructions: "Original unmodified brief.", setting_amendments: [{ text: "Allow randomized policies.", created_at: "2026-09-10T20:00:00Z" }] }, onClose: noop, onSaved: noop });
  assert.match(editor, /Original unmodified brief/);
  assert.match(editor, /Saved changes to the setting \(1\)/);
  assert.match(editor, /Allow randomized policies\.|2026-09-10 20:00/);
  assert.match(html, /Your project instructions are saved\. The team&#x27;s formulation will appear after the literature study/);
  assert.match(html, /A Lead-interpreted goal is not available yet/);
  assert.equal((html.match(/<(?:section|details)\b[^>]*class="card(?: |")/g) || []).length, 5);
  assert.doesNotMatch(html, /class="katex|Research Lead · published research basis/);
  assert.doesNotMatch(html, /Additional instructions or ideas for Phase 2|These additions go only to the Research Lead/);
  const p2 = render.phaseTwoPreparation({ instructions: "", onInstructionsChange: noop, onLaunch: noop });
  assert.match(p2, /No model development notes have been published in Phase 1 yet/);
  assert.match(p2, /These additions go only to the Research Lead/);
  assert.match(p2, /Each member proposes exactly one model/);
  assert.match(p2, /After submitting their proposals, the Theorist reviews/);
  assert.doesNotMatch(html, /Include a model idea you supplied|Prepare P2 with a supplied method/);
});

test("P2 launch uses one optional lead instruction field and preserves a recorded idea without a separate form", () => {
  for (const supplied_method of [undefined, { title: "Recorded method idea", specification_markdown: "Exact original definition.", source_reference: "Researcher's manuscript" }]) {
    const html = render.launchRun({ projectId: "project.test", request: { phase: "P2", branch: "trunk", mode: "p2.researcher_proposal", instructions: "Please compare sample requirements.", supplied_method }, onClose: noop, onStarted: noop });
    assert.equal((html.match(/<textarea/g) || []).length, 1);
    assert.match(html, /Additional instructions or ideas for Phase 2/);
    assert.match(html, /Please compare sample requirements/);
    assert.match(html, /These additions go only to the Research Lead/);
    assert.match(html, /edit the shared research setting in Phase 1/);
    assert.doesNotMatch(html, /Choose the work|type="radio"|supplied-title|supplied-specification|supplied-source|textarea[^>]*required/);
    if (supplied_method) {
      assert.match(html, /Model supplied to the lead: Recorded method idea/);
      assert.match(html, /Exact original definition/);
      assert.match(html, /Researcher&#x27;s manuscript/);
    }
  }
});

test("non-P2 launch keeps the existing instruction and work mode controls", () => {
  const html = render.launchRun({ projectId: "project.test", request: { phase: "P4", branch: "method.a", instructions: "Check simulation performance." }, onClose: noop, onStarted: noop });
  assert.match(html, /Choose the work/);
  assert.match(html, /Tell me what to do next/);
  assert.match(html, /Check simulation performance/);
  assert.doesNotMatch(html, /These additions go only|Additional instructions or ideas for Phase 2/);
});

test("P2 preparation previews the researcher's equations and explains saved lead-only directions", () => {
  const html = render.phaseTwoPreparation({ instructions: "My constraint:\n\\[U^\\pi=T_\\pi U^\\pi\\]", onSave: noop, updatedAt: "2026-09-12T12:00:00Z", onInstructionsChange: noop, onLaunch: noop });
  assert.match(html, /Saved for future Phase 2 runs/);
  assert.match(html, /Preview your Phase 2 instructions/);
  assert.match(html, /class="katex/);
  assert.doesNotMatch(html, /katex-error/);
  assert.match(html, /mathematical structure, assumptions and guarantees/);
  assert.match(html, /estimation, data requirements and practical computation/);
  assert.match(html, /without adding another model/);
  const blocked = render.phaseTwoPreparation({ instructions: "", ready: false, error: "Could not load instructions", onRetry: noop, onSave: noop, onInstructionsChange: noop, onLaunch: noop });
  assert.match(blocked, /Retry loading instructions/);
  assert.match(buttonNamed(blocked, "Prepare Phase 2 run")[1], /disabled=""/);
});

test("P1 directly renders a selected member's complete mathematics while other papers stay compact", () => {
  const html = render.literature({ onSource: noop, basis: { landscape: { summary_markdown: "Authored landscape account.", topics: [{ topic_id: "topic.risk", title: "Risk constraints", description_markdown: "Exact expected overrun.", source_ids: ["paper.one"] }] } }, libraries: [{ branch: "trunk", phase: "P1", sources: [
    { source_id: "paper.one", title: "Selected paper", cards: [{ entry_id: "entry.theory", role: "theorist", formulation_markdown: "Define \\(J(\\pi)\\) by\n\\[J(\\pi)=\\mathbb E_\\pi\\sum_{t=0}^\\infty\\gamma^t r_t\\]", explanation_markdown: "Original theorist explanation.", relevance_markdown: "Relevant to infinite-horizon reward.", limitations_markdown: "Requires bounded rewards.", evidence_locations: ["Theorem 2, equation 7"], generation_ref: ref }, { entry_id: "entry.analyst", role: "data_analyst", formulation_markdown: "Other assessment is selectable.", explanation_markdown: "Original analyst explanation." }] },
    { source_id: "paper.two", title: "Other paper", cards: [{ formulation_markdown: "Full second paper mathematics.", explanation_markdown: "Full second paper account." }] },
  ] }] });
  for (const text of ["Authored landscape account", "Risk constraints", "Selected paper", "Other paper", "Explore Individual Papers", "Frameworks and relationships", "Literature accounts, search scopes and review"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /Original theorist explanation|Original analyst explanation|Full second paper mathematics|Full second paper account|selected-paper|framework-inspector/);
  const selected = render.selectedPaper({ source: { title: "Selected paper", cards: [{ role: "theorist", formulation_markdown: "Exact equation: $$J=0$$", explanation_markdown: "Original theorist explanation.", relevance_markdown: "Relevant to infinite-horizon reward.", limitations_markdown: "Requires bounded rewards.", evidence_locations: ["Theorem 2, equation 7"], generation_ref: ref }, { role: "data_analyst", explanation_markdown: "Original analyst explanation." }] }, onSource: noop });
  for (const text of ["Original theorist explanation", "Relevant to infinite-horizon reward", "Requires bounded rewards", "Theorem 2, equation 7", "Data Analyst"]) assert.ok(selected.includes(text), text);
  assert.match(selected, /class="katex/);
  assert.doesNotMatch(selected, /Original analyst explanation/);
});

test("P2 audits match both proposal identity and producing run", () => {
  const proposal = { proposal_id: "proposal.shared", role: "theorist", generation_ref: { ...ref, run_id: "run.current" }, method: { title: "Exact proposal", mathematical_definition: { canonical_definition: { objective_or_estimating_equation: "\\[J(\\pi)\\]" } }, assumptions: ["Bounded rewards"] }, data_requirements_markdown: "A generative simulator.", proposed_evaluation_markdown: "Evaluate constraint and reward separately." };
  const reviews = [
    { role: "data_analyst", generation_ref: { ...ref, run_id: "run.current" }, assessments: [{ proposal_id: "proposal.shared", assessment_markdown: "Current targeted audit.", findings: [{ finding_id: "finding.a", statement_reference: "Algorithm, step 2", reasoning_markdown: "The estimate requires independent trajectories.", consequence_markdown: "Reuse would bias the evaluation." }] }, { proposal_id: "proposal.other", assessment_markdown: "Different proposal audit." }] },
    { role: "data_analyst", generation_ref: { ...ref, run_id: "run.old" }, assessments: [{ proposal_id: "proposal.shared", assessment_markdown: "Stale audit must not apply." }] },
  ];
  assert.equal(render.matchingReviews(proposal, reviews).length, 1);
  const html = render.methods({ proposals: [proposal], reviews, onSource: noop });
  for (const text of ["Exact proposal", "Current targeted audit", "Algorithm, step 2", "independent trajectories", "Reuse would bias", "A generative simulator", "Evaluate constraint and reward separately"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /Stale audit must not apply|Different proposal audit/);
  assert.match(html, /class="katex/);
});

test("saved-record citations keep readable labels without inventing clickable destinations", () => {
  const html = render.document("See [final results](artifact://p4.analyst/results.json), [tested theory](generation://generation.one), and [paper](https://example.org/paper). Literal code: `[raw](artifact://example)`.");
  assert.match(html, />final results<\/span>/);
  assert.match(html, />tested theory<\/span>/);
  assert.doesNotMatch(html, /href=\"(?:artifact|generation):/);
  assert.doesNotMatch(html, /p4\.analyst\/results\.json|generation\.one/);
  assert.match(html, /href=\"https:\/\/example\.org\/paper\"/);
  assert.match(html, /<code>\[raw\]\(artifact:\/\/example\)<\/code>/);
});

test("P2 overview keeps internal references as prose and publication citations as links", () => {
  const current = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const proposal = { proposal_id: "proposal.a", method: { title: "Mixture controller" }, generation_ref: { ...current, generation_id: "gen.proposal.exact" } };
  const review = { review_id: "review.a", assessments: [], generation_ref: { ...current, generation_id: "gen.audit.exact" } };
  const comparison = { generation_ref: current, overview_markdown: "See [controller-mixture proposal](#proposal.a), [theorist audit](#review.a), [unavailable alternative](#proposal.missing), and [earlier audit](#review.old). Preserve $J=0$, **the stated limit**, [paper](https://example.test/paper), and `[literal](#proposal.a)`." };
  const html = render.methods({ proposals: [proposal], reviews: [review, { ...review, review_id: "review.old", generation_ref: { ...current, run_id: "run.old", generation_id: "gen.old" } }], comparisons: [comparison], onSource: noop });
  const overview = html.match(/<div class="p2-comparison"[\s\S]*?(?=<div class="field method-branch-selector")/)[0];
  assert.equal(buttonNamed(overview, "controller-mixture proposal"), undefined);
  assert.equal(buttonNamed(overview, "theorist audit"), undefined);
  assert.equal(buttonNamed(overview, "unavailable alternative"), undefined);
  assert.equal(buttonNamed(overview, "earlier audit"), undefined);
  assert.match(overview, /unavailable alternative/); assert.match(overview, /earlier audit/);
  assert.doesNotMatch(overview, /\[controller-mixture proposal\]|#proposal.missing|gen.old|href="#/);
  assert.match(overview, /class="katex/); assert.match(overview, /<strong>the stated limit<\/strong>/);
  assert.match(overview, /href="https:\/\/example.test\/paper"/);
  assert.match(overview, /<code>\[literal\]\(#proposal.a\)<\/code>/);
  const withoutSource = render.methods({ proposals: [proposal], reviews: [review], comparisons: [comparison] });
  assert.equal(buttonNamed(withoutSource, "controller-mixture proposal"), undefined);
  const ambiguous = render.methods({ proposals: [proposal, { ...proposal, method: { title: "Duplicate identity" } }], comparisons: [comparison], onSource: noop });
  assert.equal(buttonNamed(ambiguous.match(/<div class="p2-comparison"[\s\S]*?(?=<div class="field method-branch-selector")/)[0], "controller-mixture proposal"), undefined);
});

test("a lead response to general directions stays separate from selectable model proposals", () => {
  const lead = { schema_version: "1.0.0", no_method_proposed: true, reason_markdown: "Your directions guide the comparison of sample requirements.", generation_ref: { ...ref, phase: "P2", family: "lead_proposal" } };
  const theorist = { proposal_id: "proposal.theory", method: { title: "Specialist method", summary: "Exact submitted proposal." }, generation_ref: { ...ref, phase: "P2" } };
  const html = render.methods({ proposals: [lead, theorist], onSource: noop });
  assert.equal((html.match(/<option/g) || []).length, 1);
  assert.match(html, /Specialist method/);
  assert.match(html, /Research Lead&#x27;s response to your directions/);
  assert.match(html, /Your directions guide the comparison/);
  assert.doesNotMatch(html, /no_method_proposed|reason_markdown|undefined/);
  const onlyLead = render.methods({ proposals: [lead], onSource: noop });
  assert.match(onlyLead, /No additional method proposed/);
  assert.doesNotMatch(onlyLead, /Read a proposal|<select/);
});

test("P2 keeps selected-model questions and proposed work in the following two cards", () => {
  const methodIdentity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const proposal = { proposal_id: "prop.a", role: "research_lead", generation_ref: { ...ref, phase: "P2", branch: "trunk" }, method: { identity: methodIdentity, title: "Method A", summary: "Authored mechanism.\n$$J(\\pi)$$" } };
  const attention = { ...contextualItem, branch: "trunk", phase: "P2", target_phase: "P4", affected_record_ids: ["method.a"], question: "Method A's simulation choice?" };
  const other = { ...attention, attention_id: "other", affected_record_ids: ["method.b"], question: "Method B's question must not leak" };
  const answer = { attention_id: attention.attention_id, attention, note: "The researcher's saved method A answer", resolved_at: "2026-09-13T10:00:00Z" };
  const props = { projectId: "project.test", proposals: [proposal], methods: [{ method_id: "method.a", branch_id: "method.a", identity: methodIdentity, status: "proposed" }], comparisons: [{ generation_ref: proposal.generation_ref, overview_markdown: "Authored overview of the tradeoff.", comparison_markdown: "Complete authored comparison.", method_dispositions: [{ proposal_id: "prop.a", status: "retain", rationale: "Reviewed claim with an unresolved guarantee." }] }], attentionItems: [attention, other], researcherAnswers: [answer], onContinue: noop, onSource: noop };
  const before = JSON.stringify(props);
  const html = render.methods(props);
  assert.ok(html.indexOf("Proposed Methods</h2>") < html.indexOf("Authored overview of the tradeoff"));
  assert.ok(html.indexOf("Proposed Methods</h2>") < html.indexOf("Choose a method</label>"));
  assert.ok(html.indexOf("Reviewed claim with an unresolved guarantee") < html.indexOf("Issues and decisions</h2>"));
  assert.ok(html.indexOf("Run this Method in Phase 3 - Theory</button>") < html.indexOf("Issues and decisions</h2>"));
  assert.equal((html.match(/Run this Method in Phase 3 - Theory/g) || []).length, 1);
  assert.match(html, /Run this Method in Phase 4 - Numerical Eval<\/button>/);
  assert.match(html, /review your instructions before starting the run/);
  assert.match(html, /Method A&#x27;s simulation choice/);
  assert.match(html, /The researcher&#x27;s saved method A answer/);
  assert.match(html, /Edit your answer/);
  assert.match(html, /Issues and decisions/);
  assert.doesNotMatch(html, /Your call: choose a method|Needs your decision|Method landscape|Method B&#x27;s question|Shared project question|Choose a method to develop|Read a proposal/);
  assert.match(html, /class="katex/);
  assert.equal(JSON.stringify(props), before);
});

test("a superseded version stays readable as history with a route to the current version and no launch actions", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const proposal = { proposal_id: "old.a", method: { identity, title: "Earlier definition", summary: "Original mechanism" }, generation_ref: { ...ref, run_id: "old.run" }, is_current_package: false };
  const html = render.methods({ proposals: [proposal], methods: [{ method_id: "method.a", identity: { ...identity, version: 2 }, status: "active" }], attentionItems: [{ ...contextualItem, branch: "trunk", phase: "P2", affected_record_ids: ["method.a"], target_phase: "P3" }], onContinue: noop });
  assert.match(html, /Earlier definition/);
  assert.match(html, /Superseded version/);
  assert.match(html, /kept as history/);
  assert.match(html, /current catalog carries version 2/);
  assert.match(html, /View the current version \(version 2\)/);
  assert.doesNotMatch(html, /<textarea|Save clarification|Run this Method in Phase 3 - Theory|Run this Method in Phase 4 - Numerical Eval/);
  assert.doesNotMatch(html, /No lead comparison has been published yet/);
  // When the current version is among the proposals, the history view routes to it.
  const current = { proposal_id: "new.a", method: { identity: { ...identity, version: 2 }, title: "Current definition", summary: "Revised mechanism" }, generation_ref: { ...ref, run_id: "new.run" } };
  const routed = render.methods({ proposals: [proposal, current], methods: [{ method_id: "method.a", branch_id: "method.a", identity: { ...identity, version: 2 }, status: "active" }], initialPick: "old.run:old.a", onContinue: noop, onSource: noop });
  assert.match(routed, /Earlier definition/);
  assert.match(routed, /View the current version \(version 2\)/);
  assert.match(routed, /Superseded by version 2/);
  assert.doesNotMatch(routed, /Run this Method in Phase 3 - Theory|Run this Method in Phase 4 - Numerical Eval|<textarea|Save clarification/);
});

test("complete method mathematics keeps symbols, ordered updates and tuning definitions", () => {
  const html = render.document({ mathematical_definition: { canonical_definition: {
    target_or_estimand: { symbol: "J(\\pi)", definition: "Expected discounted reward.", domain: "Admissible stationary policies." },
    algorithm_or_update_rule: [{ order: 2, operation: "Update the multiplier." }, { order: 1, operation: "Estimate the policy gradient." }],
    tuning_definition: [{ parameter_id: "parameter.internal", symbol: "\\eta", admissible_values: "$\\eta>0$", selection_rule: "Fix before evaluation." }],
  } } });
  assert.match(html, /class="katex/);
  assert.ok(html.indexOf("Step 1") < html.indexOf("Step 2"));
  for (const text of ["Admissible stationary policies", "Tuning parameters", "Fix before evaluation"]) assert.ok(html.includes(text));
  assert.doesNotMatch(html, /parameter.internal/);
});

test("canonical method information, features and derivatives remain in the readable calculation", () => {
  const canonical = {
    input_information: { object_id: "information.internal", symbol: "\\mathcal H_i(L)", definition: "Use result availability times, never future results.\n$$\\mathcal H_i(L)=\\{Y_i(t):t\\le L\\}.$$" },
    feature_definition: { object_id: "features.internal", symbol: "Z_i", definition: "Fit centering and scaling on training patients only.\n$$Z_i=(B_i-\\mu_{\\rm tr})/s_{\\rm tr}.$$", domain: "A finite marker and positive training scale." },
    derivatives: { object_id: "derivatives.internal", symbol: "J(\\beta)", definition: "The proposed Hessian includes every penalized coefficient.\n$$J(\\beta)=\\operatorname{Cov}(Z)+\\lambda I.$$" },
    execution_metadata: { private_path: "private.runtime.path" },
  };
  const original = JSON.stringify(canonical);
  const html = render.methods({ proposals: [{ proposal_id: "proposal.information", role: "research_lead", generation_ref: ref,
    method: { title: "Landmark calculation", mathematical_definition: { canonical_definition: canonical } } }], onSource: noop });
  for (const text of ["Use result availability times, never future results", "Fit centering and scaling on training patients only", "A finite marker and positive training scale", "The proposed Hessian includes every penalized coefficient"]) assert.ok(html.includes(text), text);
  for (const expression of ["\\mathcal H_i(L)=\\{Y_i(t):t\\le L\\}.", "Z_i=(B_i-\\mu_{\\rm tr})/s_{\\rm tr}.", "J(\\beta)=\\operatorname{Cov}(Z)+\\lambda I."]) assert.ok(html.includes(`<annotation encoding="application/x-tex">${expression}</annotation>`), expression);
  assert.doesNotMatch(html, /information.internal|features.internal|derivatives.internal|private.runtime.path|katex-error/);
  assert.equal(JSON.stringify(canonical), original, "Readable projection must preserve the authored source.");
});

test("known method expression definitions render bare equations while sentence definitions stay prose", () => {
  const source = JSON.parse(fs.readFileSync(path.resolve(src, "../../contracts/examples/method-proposal.example.json"), "utf8"));
  const original = JSON.stringify(source);
  const canonical = source.method.mathematical_definition.canonical_definition;
  const html = render.document({ mathematical_definition: source.method.mathematical_definition });
  for (const expression of [canonical.target_or_estimand.definition, canonical.objective_or_estimating_equation.definition, canonical.constraints_and_normalization[0].definition]) {
    assert.ok(html.includes(`<annotation encoding="application/x-tex">${expression}</annotation>`), expression);
  }
  assert.match(html, /<p>Every nuisance value used for observation i is estimated/);
  assert.doesNotMatch(html, /katex-error/);
  assert.equal(JSON.stringify(source), original);
});

const contextualItem = {
  schema_version: "1.1.0", attention_id: "attention.policy", attention_version_id: "attention.policy.v1",
  kind: "researcher_decision", target_phase: "P1", phase: "P1", branch: "trunk", raised_by: "research_lead", disposition: "open",
  question: "May a policy depend on the remaining budget $b_t$?",
  context_markdown: "Define the discounted cost by\n\\[C=\\sum_{t=0}^{\\infty}\\gamma^t c(S_t,A_t).\\]\nThe proposed setting constrains $\\mathbb E_\\pi[(C-B)_+]$.",
  likely_consequence: "The admissible class changes from $\\pi(a\\mid s)$ to $\\pi(a\\mid s,b)$.",
  generation_ref: { ...ref, branch: "trunk", phase: "P1", family: "research_basis", entry_pointer: "/attention_items/0" },
  related_source_refs: [{ ...ref, branch: "trunk", phase: "P1", family: "theory_literature", entry_pointer: "/papers/2" }],
};

test("P1 clarification follows the two scientific cards before papers with exact context and consequence", () => {
  const html = render.phaseOne({
    project: { project_id: "project.test", research_instructions: "Research instructions" },
    basis: { generation_ref: contextualItem.generation_ref, research_setting: { statement_markdown: "Published problem statement.", clarification_questions: [contextualItem.question, "Earlier unresolved wording."] } },
    artifacts: {}, cards: [], attentionItems: [contextualItem, { ...contextualItem, attention_id: "attention.p2", phase: "P2", target_phase: "P2", question: "A different phase's decision." }],
    onSource: noop, onSaved: noop, onLaunch: noop, onResolved: noop,
  });
  assert.match(html, /Decisions to Discuss/);
  assert.match(html, /Why your answer matters/);
  assert.equal((html.match(/<(?:section|details)\b[^>]*class="card(?: |")/g) || []).length, 5);
  assert.ok(html.indexOf("Decisions to Discuss") > html.indexOf("Main Findings"));
  assert.ok(html.indexOf("Decisions to Discuss") < html.indexOf("Explore Individual Papers"));
  assert.ok(html.indexOf("Explore Individual Papers") < html.indexOf("Instructions and run settings"));
  assert.match(html, /<details[^>]*data-reading-anchor="issue-context:[^"]+"><summary>Context and sources<\/summary>/);
  assert.match(html, /Why your answer matters/);
  assert.match(html, /\\sum_\{t=0\}\^\{\\infty\}\\gamma\^t/);
  assert.match(html, /<details class="phase-issue issue-row"[^>]*><summary class="issue-row-summary"/);
  assert.doesNotMatch(html, /<details class="phase-issue issue-row"[^>]*\sopen(?:=|\s|>)/);
  assert.ok(buttonNamed(html, "Save answer"));
  assert.equal((renderedText(html).match(/May a policy depend/g) || []).length, 1); // The compact row summary names the question once.
  assert.ok(html.indexOf("Earlier open questions") > html.indexOf("Instructions and run settings"));
  assert.match(html, /Earlier unresolved wording/);
  assert.doesNotMatch(html, /different phase&#x27;s decision|Outstanding researcher requests|Mark addressed|Points to clarify|Is there anything you want to modify|Save setting changes/);
});

test("team follow-ups stay collapsed, show authored mathematics and never ask the researcher to resolve them", () => {
  const html = render.teamFollowUp({ items: [{ ...contextualItem, kind: "research_task", target_phase: "P4", question: "Assess sensitivity of $C$ to policy information." }], branch: "method.a", phase: "P4", onSource: noop });
  assert.match(html, /^<details class="research-details team-research-followup"[^>]*><summary>Team research follow-up \(1\)/);
  assert.match(html, /Shared project question/);
  assert.match(html, /class="katex/);
  assert.match(html, /The admissible class changes/);
  assert.match(html, /Original request|Related scientific source 1/);
  assert.doesNotMatch(html, /<form|<textarea|Save clarification|Mark addressed/);
  assert.equal(render.teamFollowUp({ items: [{ ...contextualItem, kind: "research_task", target_phase: "P4", branch: "method.b" }], branch: "method.a", phase: "P4" }), "");
});

test("historical questions remain readable without invented equations, classifications or response controls", () => {
  const legacy = { attention_id: "attention.old", phase: "P1", branch: "trunk", question: "Check the manuscript against its original wording.", likely_consequence: "The formulation may need clarification.", generation_ref: contextualItem.generation_ref };
  const html = render.earlierQuestions({ items: [legacy], branch: "trunk", phase: "P1", onSource: noop });
  assert.match(html, /^<details class="research-details earlier-open-questions"[^>]*><summary>Earlier open questions \(1\)/);
  assert.match(html, /Their context and intended recipient may be incomplete/);
  assert.match(html, /Check the manuscript against its original wording/);
  assert.match(html, /The formulation may need clarification/);
  assert.doesNotMatch(html, /class="katex|<form|<textarea|Save clarification|Mark addressed|researcher-decision/);
});

test("other-phase decisions and execution corrections render only in their declared context", () => {
  const items = [{ ...contextualItem, target_phase: "P3", branch: "method.a" }];
  assert.equal(render.decisions({ items, branch: "method.b", phase: "P3" }), "");
  assert.equal(render.decisions({ items, branch: "method.a", phase: "P4" }), "");
  const html = render.decisions({ items, projectId: "project.test", branch: "method.a", phase: "P3", onSource: noop });
  assert.match(html, /Needs your input/);
  assert.match(html, /class="katex/);
  const p2 = render.decisions({ items: [{ ...contextualItem, target_phase: "P2" }], projectId: "project.test", branch: "trunk", phase: "P2", onSource: noop });
  assert.match(p2, /During Phase 2, new runs give this clarification only to the Research Lead/);
  assert.doesNotMatch(p2, /clarification to all team members/);
  const corrections = render.runCorrections({ runs: [{ run_id: "here", branch_id: "method.a", phase: "P3", state: "failed", mode: "p3.theory_revision" }, { run_id: "elsewhere", branch_id: "method.b", phase: "P3", state: "failed", mode: "PRIVATE OTHER METHOD" }], branch: "method.a", phase: "P3", onOpenRun: noop });
  assert.match(corrections, /Runs needing correction \(1\)/);
  assert.match(corrections, /Execution or output issues/);
  assert.doesNotMatch(corrections, /PRIVATE OTHER METHOD|Save clarification/);
});

test("an exact request source renders the author's mathematical context in the source reader", () => {
  const html = render.document(contextualItem);
  assert.match(html, /Mathematical context/);
  assert.match(html, /Why it matters/);
  assert.match(html, /The admissible class changes/);
  assert.match(html, /class="katex/);
  assert.doesNotMatch(html, /attention.policy|researcher_decision|entry_pointer/);
});

test("saved clarification remains in collapsed Decisions to Discuss after the open request disappears", () => {
  const answer = { attention_id: contextualItem.attention_id, note: "Use the augmented policy class $\\pi(a\\mid s,b)$.", resolved_at: "2026-09-11T14:22:00Z", attention: { ...contextualItem, disposition: "resolved" } };
  const html = render.phaseOne({ project: { project_id: "project.test", research_instructions: "Saved project instructions" }, basis: { research_setting: { statement_markdown: "Original mathematical setting.", clarification_questions: [contextualItem.question] } }, artifacts: {}, cards: [], attentionItems: [], researcherAnswers: [answer, { ...answer, attention_id: "p2.answer", note: "P2-only directions", attention: { ...contextualItem, target_phase: "P2" } }], onSource: noop, onSaved: noop, onLaunch: noop });
  assert.match(html, /data-issue-state="saved"/);
  assert.match(html, /<details class="phase-issue issue-row answered"[^>]*><summary class="issue-row-summary"/);
  assert.doesNotMatch(html, /<details class="phase-issue issue-row answered"[^>]*\sopen(?:=|\s|>)/);
  assert.ok(html.indexOf("Your saved answer</h4>") > html.indexOf("Decisions to Discuss"));
  assert.match(html, /Edit your answer/);
  assert.doesNotMatch(html, /We need your clarifications on:|Needs your input/);
  assert.match(html, /Use the augmented policy class/);
  assert.match(html, /Saved for future work/);
  assert.match(html, /Why your answer matters/);
  assert.match(html, /class="katex/);
  assert.equal((renderedText(html).match(/May a policy depend/g) || []).length, 1); // The compact row summary names the question once.
  assert.doesNotMatch(html, /Earlier open questions|P2-only directions|Save clarification<\/button>|Clarify this setting/);
  const isolated = render.decisions({ items: [], answers: [answer], branch: "trunk", phase: "P1", onSource: noop });
  assert.doesNotMatch(isolated, /<form|<textarea|Save clarification<\/button>/);
  assert.equal(render.decisions({ items: [], answers: [answer], branch: "trunk", phase: "P2" }), "");
});

test("mixed Langevin prose keeps paragraph-position display equations distinct from inline assumptions", () => {
  const first = String.raw`X_{k+1}=X_k-h\nabla U(X_k)+\sqrt{2h}\xi_{k+1}`;
  const second = String.raw`W_2(\mu_k,\pi)\leq(1-mh)^k W_2(\mu_0,\pi)+C\sqrt{hd}`;
  const text = `The baseline is $$${first}$$. Under $m$-strong convexity, the error satisfies $$${second}$$. This is a discretized-chain guarantee.`;
  const html = render.document(text);
  const annotations = [...html.matchAll(/<annotation encoding="application\/x-tex">([\s\S]*?)<\/annotation>/g)].map((match) => match[1]);
  assert.deepEqual(annotations, [first, "m", second]);
  assert.equal((html.match(/class="math-block"/g) || []).length, 2);
  assert.equal((html.match(/class="math-inline"/g) || []).length, 1);
  assert.match(html, /The baseline is /);
  assert.match(html, /\. Under /);
  assert.match(html, /-strong convexity, the error satisfies /);
  assert.match(html, /\. This is a discretized-chain guarantee\./);
  assert.doesNotMatch(html, /\$|katex-error/);
});

test("display math retains multiline bodies and trailing prose while fenced and inline code remain literal", () => {
  const text = ["```text", "$$do not render$$ and $literal$", "```", "", "Keep `$$literal$$ and $code$` unchanged; inline $z$ stays inline.", "", "$$", "a=b", "", "+c", "$$ Trailing words remain prose.", "", String.raw`A bracketed statement \[u=v\] also retains its trailing sentence.`].join("\n");
  const html = render.document(text);
  assert.match(html, /<pre class="record"><code>\$\$do not render\$\$ and \$literal\$<\/code><\/pre>/);
  assert.match(html, /<code>\$\$literal\$\$ and \$code\$<\/code>/);
  const annotations = [...html.matchAll(/<annotation encoding="application\/x-tex">([\s\S]*?)<\/annotation>/g)].map((match) => match[1]);
  assert.deepEqual(annotations.map((entry) => entry.trim()), ["z", "a=b\n\n+c", "u=v"]);
  assert.match(html, /Trailing words remain prose/);
  assert.match(html, /also retains its trailing sentence/);
  assert.equal((html.match(/class="math-block"/g) || []).length, 2);
  assert.doesNotMatch(html, /katex-error/);
});

test("unclosed display delimiters stay literal instead of consuming prose or a later code fence", () => {
  const html = render.document("An incomplete formula $$x plus prose.\n```text\n$$code delimiter$$\n```\nNormal paragraph with $y$.");
  assert.match(html, /An incomplete formula \$\$x plus prose/);
  assert.match(html, /<code>\$\$code delimiter\$\$<\/code>/);
  assert.equal((html.match(/class="katex"/g) || []).length, 1);
  assert.doesNotMatch(html, /class="math-block"|katex-error/);
});

test("P2 explore card keeps retained methods actionable and fires activation with the exact catalog method", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const otherIdentity = { stable_id: "method.b", version: 1, definition_sha256: "b".repeat(64) };
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const proposal = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity, title: "Method A", summary: "Authored mechanism." } };
  const excludedProposal = { proposal_id: "prop.b", role: "data_analyst", generation_ref: run, method: { identity: otherIdentity, title: "Method B", summary: "Other mechanism." } };
  const catalogMethod = { method_id: "method.a", branch_id: "method.a", identity, status: "proposed" };
  const comparison = { generation_ref: run, overview_markdown: "Authored overview.", comparison_markdown: "Complete comparison.", method_dispositions: [
    { proposal_id: "prop.a", status: "retain", rationale: "Strongest guarantee; the tail bound remains open." },
    { proposal_id: "prop.b", status: "exclude", rationale: "Excluded because the estimator is biased." },
  ] };
  const html = render.methods({ projectId: "project.test", proposals: [proposal, excludedProposal], methods: [catalogMethod], comparisons: [comparison], onContinue: noop, onSource: noop });
  assert.doesNotMatch(html, /Your call: choose a method|Needs your decision/);
  assert.match(html, /Strongest guarantee; the tail bound remains open/);
  assert.equal((html.match(/Run this Method in Phase 3 - Theory/g) || []).length, 1);
  assert.equal((html.match(/Run this Method in Phase 4 - Numerical Eval/g) || []).length, 1);
  assert.match(html, /Not retained in this catalog update \(1\)/);
  assert.match(html, /Excluded because the estimator is biased/);
  assert.ok(html.indexOf("Proposed Methods</h2>") < html.indexOf("Choose a method</label>"));
  // The excluded proposal remains selectable for reading but offers no actions.
  const excluded = render.methods({ projectId: "project.test", proposals: [proposal, excludedProposal], methods: [catalogMethod], comparisons: [comparison], initialPick: "run.current:prop.b", onContinue: noop, onSource: noop });
  assert.match(excluded, /Other mechanism/);
  assert.match(excluded, /did not retain this proposal in the catalog/);
  assert.doesNotMatch(excluded, /Run this Method in Phase 3 - Theory|Run this Method in Phase 4 - Numerical Eval|Save clarification/);
  const busy = render.methods({ projectId: "project.test", proposals: [proposal, excludedProposal], methods: [catalogMethod], comparisons: [comparison], onContinue: noop, onSource: noop, busy: true });
  assert.match(buttonNamed(busy, "Run this Method in Phase 3 - Theory")[1], /disabled=""/);
  // The exploration buttons call the existing activation flow with the
  // identity-matched catalog method. Server markup cannot dispatch clicks, so
  // fire the exact handlers from the rendered element tree.
  const calls = [];
  const element = render.exploreActions({ catalogMethod, busy: false, onContinue: (...args) => calls.push(args) });
  const buttons = [];
  const walk = (node) => { if (!node || typeof node !== "object") return; if (Array.isArray(node)) { node.forEach(walk); return; } if (node.type === "button" || node.props?.action) buttons.push(node); walk(node.props?.children); };
  walk(element);
  const theory = buttons.find((button) => button.props.children === "Run this Method in Phase 3 - Theory");
  const experiments = buttons.find((button) => button.props.children === "Run this Method in Phase 4 - Numerical Eval");
  assert.ok(theory && experiments);
  assert.equal(theory.props.disabled, false);
  theory.props.onClick();
  experiments.props.onClick();
  assert.deepEqual(calls, [[catalogMethod, "P3", { prepareRun: true }], [catalogMethod, "P4", { prepareRun: true }]]);
  const archived = render.exploreActions({ catalogMethod: { ...catalogMethod, status: "archived" }, busy: false, onContinue: noop });
  assert.equal(archived.props.children, "This catalog definition is not active for further work.");
  assert.equal(render.exploreActions({ catalogMethod, busy: false }), null);
});

test("P2 history records the exact selected model identity off the decision surface", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const proposal = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity, title: "Method A", summary: "Authored mechanism." } };
  const method = { method_id: "method.a", branch_id: "method.a", title: "Method A", identity, current_identity: identity, selected_identity: identity, registered: true, aligned: true, status: "active" };
  const comparison = { generation_ref: run, overview_markdown: "Authored overview.", method_dispositions: [{ proposal_id: "prop.a", status: "retain", rationale: "Strongest guarantee." }] };
  const props = { projectId: "project.test", proposals: [proposal], methods: [method], comparisons: [comparison], onContinue: noop, onSource: noop };
  const html = render.methods(props);
  assert.match(html, /Model versions and comparisons/);
  assert.match(html, /Recorded model selection/);
  assert.match(html, /Proposed by Theorist · Selected<\/p>/);
  assert.ok(html.includes("method.a"));
  assert.ok(html.includes("a".repeat(64)));
  assert.match(html, /Version 1/);
  assert.match(html, /Run this Method in Phase 3 - Theory<\/button>/);
  // Identifiers and hashes remain in secondary history inside the reader.
  assert.ok(html.indexOf("Proposed Methods</h2>") < html.indexOf("Model versions and comparisons"));
  assert.ok(html.indexOf("Model versions and comparisons") < html.indexOf("a".repeat(64)));
  assert.ok(html.indexOf("<h2>Further model development</h2>") < html.indexOf("Model versions and comparisons"));
  assert.doesNotMatch(html, /<h2>Issues and decisions<\/h2>/);
  const unregistered = render.methods({ ...props, methods: [{ ...method, registered: false, selected_identity: undefined }] });
  assert.doesNotMatch(unregistered, /Your selection is recorded|Recorded model selection|Selected<\/span>/);
  const moved = render.methods({ ...props, methods: [{ ...method, aligned: false, selected_identity: { ...identity, version: 0, definition_sha256: "0".repeat(64) } }] });
  assert.match(moved, /Recorded model selection/);
  assert.ok(moved.includes("0".repeat(64)));
  assert.match(moved, /the catalog now holds a different definition of this model/);
});

test("switching methods shows only the selected model's content, questions, answers and actions", () => {
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const identityA = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const identityB = { stable_id: "method.b", version: 3, definition_sha256: "b".repeat(64) };
  const proposalA = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity: identityA, title: "Method A", summary: "Mechanism A.", mathematical_definition: { canonical_definition: { objective_or_estimating_equation: "\\[J_A\\]" } } } };
  const proposalB = { proposal_id: "prop.b", role: "data_analyst", generation_ref: run, method: { identity: identityB, title: "Method B", summary: "Mechanism B.", mathematical_definition: { canonical_definition: { objective_or_estimating_equation: "\\[J_B\\]" } } } };
  const questionA = { ...contextualItem, attention_id: "q.a", branch: "trunk", phase: "P2", target_phase: "P3", affected_record_ids: ["method.a"], question: "Method A's theory question?" };
  const questionB = { ...contextualItem, attention_id: "q.b", branch: "trunk", phase: "P2", target_phase: "P4", affected_record_ids: ["method.b"], question: "Method B's experiment question?" };
  const answerB = { attention_id: "q.b", attention: questionB, note: "Saved answer for method B", resolved_at: "2026-09-14T09:00:00Z" };
  const methods = [
    { method_id: "method.a", branch_id: "method.a", identity: identityA, status: "proposed" },
    { method_id: "method.b", branch_id: "method.b", identity: identityB, status: "active" },
  ];
  const comparison = { generation_ref: run, overview_markdown: "Overview.", method_dispositions: [{ proposal_id: "prop.a", status: "retain", rationale: "Lead prefers A's guarantee." }, { proposal_id: "prop.b", status: "retain", rationale: "Lead notes B's empirical fit." }] };
  const props = { projectId: "project.test", proposals: [proposalA, proposalB], methods, comparisons: [comparison], attentionItems: [questionA, questionB], researcherAnswers: [answerB], onContinue: noop, onSource: noop };
  const htmlA = render.methods(props);
  const htmlB = render.methods({ ...props, initialPick: "run.current:prop.b" });
  assert.match(htmlA, /Mechanism A\./);
  assert.match(htmlA, /Method A&#x27;s theory question/);
  assert.match(htmlA, /Lead prefers A&#x27;s guarantee/);
  assert.doesNotMatch(htmlA, /Mechanism B\.|Method B&#x27;s experiment question|Saved answer for method B|Lead notes B/);
  assert.match(htmlB, /Mechanism B\./);
  assert.match(htmlB, /Method B&#x27;s experiment question/);
  assert.match(htmlB, /Saved answer for method B/);
  assert.match(htmlB, /Lead notes B&#x27;s empirical fit/);
  assert.match(htmlB, /Version 3/);
  assert.doesNotMatch(htmlB, /Mechanism A\.|Method A&#x27;s theory question|Lead prefers A/);
  for (const html of [htmlA, htmlB]) {
    assert.equal((html.match(/Run this Method in Phase 3 - Theory/g) || []).length, 1);
    assert.equal((html.match(/Run this Method in Phase 4 - Numerical Eval/g) || []).length, 1);
  }
});

test("the model dropdown only changes the view; it never activates a branch or starts a run", () => {
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const proposalA = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity: { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) }, title: "Method A" } };
  const proposalB = { proposal_id: "prop.b", role: "data_analyst", generation_ref: run, method: { identity: { stable_id: "method.b", version: 1, definition_sha256: "b".repeat(64) }, title: "Method B" } };
  const picks = [];
  // MethodPicker receives no activation callback at all: selection is view state.
  const element = render.methodPicker({ id: "pick", describedBy: "note", controls: "explore", proposals: [proposalA, proposalB], methods: [], value: "run.current:prop.a", onSelect: (key) => picks.push(key) });
  let select;
  const walk = (node) => { if (!node || typeof node !== "object") return; if (Array.isArray(node)) { node.forEach(walk); return; } if (node.type === "select") select = node; walk(node.props?.children); };
  walk(element);
  assert.ok(select);
  assert.equal(select.props.value, "run.current:prop.a");
  select.props.onChange({ target: { value: "run.current:prop.b" } });
  assert.deepEqual(picks, ["run.current:prop.b"]);
  select.props.onChange({ target: { value: "run.current:prop.missing" } });
  assert.deepEqual(picks, ["run.current:prop.b", "run.current:prop.missing"]);
});

test("a retained method from an earlier run keeps the same exploration capabilities as a new proposal", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const oldRun = { ...ref, phase: "P2", branch: "trunk", run_id: "run.old" };
  const newRun = { ...ref, phase: "P2", branch: "trunk", run_id: "run.new" };
  const retained = { proposal_id: "prop.old", role: "theorist", generation_ref: oldRun, is_current_package: false, published_at: "2026-09-01T10:00:00Z",
    computational_profile: { per_iteration_markdown: "One pass costs $O(n)$." },
    method: { identity, title: "Retained method", summary: "Earlier authored mechanism.", mathematical_definition: { canonical_definition: { objective_or_estimating_equation: "\\[J\\]" } } } };
  const fresh = { proposal_id: "prop.new", role: "data_analyst", generation_ref: newRun, method: { identity: { stable_id: "method.b", version: 1, definition_sha256: "b".repeat(64) }, title: "Fresh method", summary: "Newly proposed mechanism." } };
  const question = { ...contextualItem, attention_id: "q.retained", branch: "trunk", phase: "P2", target_phase: "P3", affected_record_ids: ["method.a"], question: "Retained method's open question?" };
  const oldComparison = { generation_ref: oldRun, is_current_package: false, overview_markdown: "Earlier overview.", method_dispositions: [{ proposal_id: "prop.old", status: "retain", rationale: "Earlier lead rationale." }] };
  const newComparison = { generation_ref: newRun, overview_markdown: "Latest overview.", method_dispositions: [{ proposal_id: "prop.new", status: "retain", rationale: "Latest lead rationale." }] };
  const methods = [{ method_id: "method.a", branch_id: "method.a", identity, status: "active" }, { method_id: "method.b", branch_id: "method.b", identity: fresh.method.identity, status: "proposed" }];
  const html = render.methods({ projectId: "project.test", proposals: [retained, fresh], methods, comparisons: [oldComparison, newComparison], attentionItems: [question], initialPick: "run.old:prop.old", onContinue: noop, onSource: noop });
  assert.match(html, /Retained from an earlier run/);
  assert.match(html, /Earlier authored mechanism/);
  assert.match(html, /Earlier lead rationale/);
  assert.match(html, /Retained method&#x27;s open question/);
  assert.match(html, /Save answer/);
  assert.match(html, /Run this Method in Phase 3 - Theory<\/button>/);
  assert.match(html, /Run this Method in Phase 4 - Numerical Eval<\/button>/);
  assert.match(html, /One pass costs/);
  assert.match(html, /current catalog definition/);
  assert.doesNotMatch(html, /kept as history|Superseded/);
  // The earlier run's own comparison still heads the page; the latest comparison
  // is retained as history, not borrowed for the retained method.
  assert.match(html, /Latest overview/);
});

test("catalog diagnostics render as labeled, source-linked notes inside history", () => {
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const proposal = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity, title: "Method A", summary: "Authored mechanism." } };
  const diagnostics = [{ code: "method.identity_invalid", message: "Method identity is missing or invalid; applicability cannot be established.", detail: "invalid version", stable_id: "method.broken", source_ref: { branch: "trunk", phase: "P2", family: "method_catalog", generation_id: "gen.catalog", sha256: "c".repeat(64) }, shadowed: true }];
  const html = render.methods({ projectId: "project.test", proposals: [proposal], methods: [{ method_id: "method.a", branch_id: "method.a", identity, status: "proposed" }], diagnostics, onContinue: noop, onSource: noop });
  assert.match(html, /Model versions and comparisons/);
  assert.match(html, /Catalog diagnostic/);
  assert.match(html, /Method identity is missing or invalid; applicability cannot be established/);
  assert.match(html, /invalid version/);
  assert.match(html, /method\.broken/);
  assert.match(html, /shadows an earlier valid record/);
  assert.match(html, /Open the catalog source record/);
  assert.match(html, /cannot be selected or run/);
  assert.ok(html.indexOf("Proposed Methods</h2>") < html.indexOf("Catalog diagnostic"));
  const clean = render.methods({ projectId: "project.test", proposals: [proposal], methods: [{ method_id: "method.a", identity, status: "proposed" }], onContinue: noop, onSource: noop });
  assert.doesNotMatch(clean, /Catalog diagnostic/);
});

test("the explore card surfaces needs-update status for the selected model's existing work", () => {
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const proposal = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity, title: "Method A", summary: "Authored mechanism." } };
  const method = { method_id: "method.a", branch_id: "method.a", identity, status: "active", dependent_outputs: [
    { phase: "P3", status: "needs_update", recorded_version: 1, current_version: 2, change_summary: "The estimator now allows dependent observations.", source_ref: { branch: "trunk", phase: "P2", family: "method_catalog", generation_id: "gen.rev", sha256: "b".repeat(64) } },
    { phase: "P4", status: "current" },
  ] };
  const comparison = { generation_ref: run, overview_markdown: "Authored overview.", method_dispositions: [{ proposal_id: "prop.a", status: "retain", rationale: "Strongest guarantee." }] };
  const html = render.methods({ projectId: "project.test", proposals: [proposal], methods: [method], comparisons: [comparison], onContinue: noop, onSource: noop });
  assert.match(html, /Phase 3 - Theory results for this method/);
  assert.match(html, /Needs update: this work used model version 1\. The current model is version 2\./);
  assert.match(html, /estimator now allows dependent observations/);
  assert.doesNotMatch(html, /Experiments work on this model/);
});

test("legacy scores and earlier lead comparisons live in the collapsed history area", () => {
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const oldRun = { ...ref, phase: "P2", branch: "trunk", run_id: "run.old" };
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const proposal = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity, title: "Method A", summary: "Authored mechanism." } };
  const comparisons = [
    { generation_ref: run, overview_markdown: "Current overview.", method_dispositions: [{ proposal_id: "prop.a", status: "retain", rationale: "Kept." }] },
    { generation_ref: oldRun, is_current_package: false, title: "September comparison", comparison_markdown: "Earlier authored comparison." },
  ];
  const html = render.methods({ projectId: "project.test", proposals: [proposal], methods: [{ method_id: "method.a", branch_id: "method.a", identity, status: "proposed" }], comparisons, legacyScores: [{ method_ref: "method.a", score: 0.42, rationale: "Legacy scoring rationale." }], onContinue: noop, onSource: noop });
  assert.match(html, /Model versions and comparisons/);
  assert.match(html, /Earlier lead comparisons/);
  assert.match(html, /Earlier recorded model scores/);
  assert.match(html, /Legacy scoring rationale/);
  assert.match(html, /Earlier authored comparison/);
  assert.ok(html.indexOf("Proposed Methods</h2>") < html.indexOf("Model versions and comparisons"));
  assert.ok(html.indexOf("Model versions and comparisons") < html.indexOf("Earlier recorded model scores"));
});

test("P2 reader groups computation, assumptions, lead review and proposed work into four panels", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const proposal = { proposal_id: "prop.a", role: "data_analyst", generation_ref: run, data_requirements_markdown: "A generative simulator.", proposed_evaluation_markdown: "Evaluate constraint and reward separately.",
    computational_profile: { per_iteration_markdown: "One update costs $O(nd)$ flops.", memory_markdown: "Stores two sufficient statistics.", scaling_markdown: "Cost grows linearly in $n$." },
    method: { identity, title: "Method A", summary: "Authored mechanism.", assumptions: ["Bounded rewards"], mathematical_definition: { canonical_definition: { objective_or_estimating_equation: "\\[J(\\pi)\\]" } } } };
  const comparison = { generation_ref: run, overview_markdown: "Authored overview.", method_dispositions: [{ proposal_id: "prop.a", status: "retain", rationale: "Strongest guarantee." }],
    modification_options: [
      { option_id: "mod.prop.a.exact", applies_to: "prop.a", title: "Exact-solve variant", what_changes_markdown: "Replace the sampled update with the exact solve $$x^*$$.", when_preferable_markdown: "Prefer when $n$ is small." },
      { option_id: "mod.prop.other", applies_to: "prop.other", title: "PRIVATE OTHER OPTION", what_changes_markdown: "Changes another proposal.", when_preferable_markdown: "Never shown here." },
    ] };
  const html = render.methods({ projectId: "project.test", proposals: [proposal], methods: [{ method_id: "method.a", branch_id: "method.a", identity, status: "proposed" }], comparisons: [comparison], onContinue: noop, onSource: noop });
  for (const text of ["Cost per iteration", "One update costs", "Memory footprint", "Stores two sufficient statistics", "Scaling with problem size", "grows linearly", "Exact-solve variant", "What changes mathematically", "Replace the sampled update", "When it is preferable", "Prefer when"]) assert.ok(html.includes(text), text);
  assert.match(html, /The lead&#x27;s modification options \(1\)/);
  assert.match(html, /Original assumptions and limitations<\/h3><p class="note p2-section-author">Data Analyst/);
  assert.match(html, /Lead assessment source/);
  assert.doesNotMatch(html, /PRIVATE OTHER OPTION|Changes another proposal/);
  assert.match(html, /class="katex/);
  const order = ["Original assumptions and limitations", "Computational profile", "Data requirements", "Rationale and critical assessment", "Specialist reviews", "The lead&#x27;s modification options", "Proposed theory and experiment work"];
  for (let i = 1; i < order.length; i++) assert.ok(html.indexOf(order[i - 1]) < html.indexOf(order[i]), `${order[i - 1]} before ${order[i]}`);
});

test("P2 deep-dive labels missing computational profiles and modification options honestly", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const proposal = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity, title: "Method A", summary: "Authored mechanism." } };
  const catalog = [{ method_id: "method.a", branch_id: "method.a", identity, status: "proposed" }];
  const legacy = { generation_ref: run, overview_markdown: "Authored overview.", method_dispositions: [{ proposal_id: "prop.a", status: "retain", rationale: "Strongest guarantee." }] };
  const html = render.methods({ projectId: "project.test", proposals: [proposal], methods: catalog, comparisons: [legacy], onContinue: noop, onSource: noop });
  assert.match(html, /No computational profile was recorded for this proposal/);
  assert.match(html, /earlier assessment did not record separate modification options/);
  assert.doesNotMatch(html, /Cost per iteration|Memory footprint|Scaling with problem size/);
  const emptyProfile = render.methods({ projectId: "project.test", proposals: [{ ...proposal, computational_profile: {} }], methods: catalog, comparisons: [legacy], onContinue: noop, onSource: noop });
  assert.match(emptyProfile, /The recorded computational profile has no readable entries/);
  const noOptions = render.methods({ projectId: "project.test", proposals: [proposal], methods: catalog, comparisons: [{ ...legacy, modification_options: [] }], onContinue: noop, onSource: noop });
  assert.match(noOptions, /The lead recorded no modification options for this proposal/);
  const unlinked = render.methods({ projectId: "project.test", proposals: [proposal], methods: catalog, onContinue: noop, onSource: noop });
  assert.match(unlinked, /No lead assessment is linked to this exact proposal run/);
  assert.match(unlinked, /No computational profile was recorded for this proposal/);
  assert.doesNotMatch(unlinked, /Your call: choose a method/);
});

test("P2 disclosures preserve authored material while decisions and proposed studies follow in their own cards", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const run = { ...ref, phase: "P2", branch: "trunk", run_id: "run.current" };
  const proposal = { proposal_id: "prop.a", role: "theorist", generation_ref: run, method: { identity, title: "Method A", summary: "Original proposal summary", assumptions: ["Original assumption"], mathematical_definition: { canonical_definition: { algorithm_or_update_rule: [{ order: 1, operation: "Exact algorithm step" }], calculation_defining_assumptions: [{ statement: "The calculation needs a finite score moment.", mathematical_role: "Justifies variance estimation." }] } } }, proposed_evaluation_markdown: "Run the authored experiment plan." };
  const reviews = [{ role: "data_analyst", generation_ref: run, assessments: [{ proposal_id: "prop.a", applicability_markdown: "Applicable only with representative observations.", assessment_markdown: "Auditor's assessment.", findings: [{ title: "An audit finding", statement_reference: "Step 1", reasoning_markdown: "The sample can be biased.", consequence_markdown: "This changes the target." }] }] }, { role: "theorist", generation_ref: { ...run, run_id: "run.other" }, assessments: [{ proposal_id: "prop.a", applicability_markdown: "STALE APPLICABILITY" }] }];
  const question = { ...contextualItem, branch: "trunk", phase: "P2", target_phase: "P3", affected_record_ids: ["method.a"], question: "User choice for A?", context_markdown: "Question mathematical context.", likely_consequence: "Question consequence." };
  const task = { ...question, attention_id: "task.a", kind: "research_task", target_phase: "P4", question: "Team task for A", context_markdown: "Team task mathematical context." };
  const props = { projectId: "project.test", proposals: [proposal], methods: [{ method_id: "method.a", branch_id: "method.a", identity, status: "proposed" }], comparisons: [{ generation_ref: run, method_dispositions: [{ proposal_id: "prop.a", status: "retain", method_summary_markdown: "Lead procedure: compute $x=1$, then update.", rationale: "Lead criticism: innovation remains uncertain." }] }], reviews, attentionItems: [question, task], onSource: noop, onContinue: noop };
  const sourceBefore = JSON.stringify(props);
  const html = render.methods(props);
  const account = html.slice(html.indexOf('Methodological account</h3>'), html.indexOf('data-reading-anchor="p2-model:'));
  const sections = html.split('<details class="research-details p2-reader-disclosure"');
  assert.equal(sections.length, 4);
  const [, assumptions, computation, review] = sections;
  assert.match(account, /Original proposal summary/);
  assert.doesNotMatch(account, /Exact algorithm step|calculation needs a finite score moment|Lead criticism|representative observations|User choice|Lead procedure/);
  for (const section of [assumptions, computation, review]) assert.doesNotMatch(section.split('>', 1)[0], /\bopen=/);
  assert.match(assumptions, /Data Analyst<\/h4>/); assert.match(assumptions, /representative observations/); assert.match(assumptions, /Original assumption/);
  assert.match(assumptions, /Data Analyst applicability source/);
  assert.match(computation, /Exact algorithm step/); assert.match(computation, /calculation needs a finite score moment/);
  assert.match(review, /Full historical Lead procedural account/); assert.match(review, /Lead procedure/); assert.match(review, /class="katex/);
  assert.match(review, /Lead criticism/); assert.match(review, /Auditor&#x27;s assessment/); assert.match(review, /This changes the target/);
  const next = html.slice(html.indexOf('id="phase-issues"'));
  assert.match(next, /User choice for A/); assert.match(next, /Question mathematical context/); assert.match(next, /Question consequence/);
  assert.match(next, /Team task for A/); assert.match(next, /Team task mathematical context/); assert.match(next, /authored experiment plan/);
  assert.equal(JSON.stringify(props), sourceBefore);
  assert.doesNotMatch(html, /STALE APPLICABILITY|role="tablist"|role="tabpanel"/);
  assert.equal((html.match(/<section\b[^>]*class="card(?: |")/g) || []).length, 4);
  const saved = render.methods({ ...props, researcherAnswers: [{ attention_id: question.attention_id, attention: question, note: "Use my saved choice", resolved_at: "2026-09-22T12:00:00Z" }] });
  assert.doesNotMatch(saved, /unanswered question/); assert.match(saved, /Use my saved choice/); assert.match(saved, /Edit your answer/);
});

test("P2 uses native disclosure controls and reports actual open-state changes", () => {
  const toggles = [];
  const tree = render.methodReaderDisclosure({ name: "assumptions", title: "Assumptions and limitations", modelKey: "run.exact:proposal.a", open: false, onToggle: value => toggles.push(value), children: "ORIGINAL_ACCOUNT" });
  assert.equal(tree.type, "details"); assert.equal(tree.props.open, false);
  assert.equal(tree.props["data-reading-anchor"], "p2-model:run.exact:proposal.a:assumptions");
  assert.equal(tree.props.children[0].type, "summary"); assert.equal(tree.props.children[0].props.children, "Assumptions and limitations");
  tree.props.onToggle({ currentTarget: { open: false } });
  tree.props.onToggle({ currentTarget: { open: true } });
  assert.deepEqual(toggles, [true]);
});

test("P1 scientific cards read directly without a primary tab level", () => {
  const html = render.phaseOne({ project: { project_id: "p1", research_instructions: "Brief" }, basis: { research_setting: { statement_markdown: "The authored setting is $X_i$." }, landscape: { summary_markdown: "The authored synthesis." } }, artifacts: {} });
  assert.equal((html.match(/role="tablist"/g) || []).length, 0);
  assert.match(html, /The authored setting/); assert.match(html, /class="katex/);
  const cards = ["Research Setting", "Main Findings", "Decisions to Discuss", "Explore Individual Papers", "Instructions and run settings"];
  assert.equal((html.match(/<(?:section|details)\b[^>]*class="card(?: |")/g) || []).length, cards.length);
  for (let i = 1; i < cards.length; i++) assert.ok(html.indexOf(cards[i - 1]) < html.indexOf(cards[i]));
  assert.ok(html.indexOf("Phase run history") > html.indexOf("Instructions and run settings"));
});

test("P1 legacy disclosures retain whole authored fields and notation stays on demand", () => {
  const longField = label => `${label} first paragraph.\n\n${"Original qualification remains part of this account. ".repeat(30)}${label} final paragraph.`;
  const setting = longField("Setting"); const goal = longField("Goal"); const findings = longField("Findings");
  const explanation = longField("Contribution"); const fit = longField("Fit");
  const basis = { catalog_pin: { catalog_version: "1.22.2", catalog_manifest_sha256: "b".repeat(64) },
    research_setting: { statement_markdown: setting, research_goal_markdown: goal,
      component_interpretations: [{ symbol_latex: "X_i", mathematical_role_markdown: "Observation vector lookup.", problem_meaning_markdown: "Recorded measurement lookup." }] },
    landscape: { summary_markdown: findings, overview_item_ids: [] } };
  const html = render.phaseOne({ project: { project_id: "legacy.whole", name: "Original study", research_instructions: "Brief" }, basis, artifacts: {}, onGoal: noop });
  for (const [anchor, summary] of [["earlier-setting", "Read the earlier study formulation"], ["earlier-goal", "Read the earlier interpreted goal"], ["earlier-synthesis", "Read the earlier literature synthesis"]]) {
    assert.match(html, new RegExp(`<details[^>]*data-reading-anchor="${anchor}"><summary>${summary}</summary>`));
  }
  for (const label of ["Setting", "Goal", "Findings"]) {
    assert.match(html, new RegExp(`${label} first paragraph`));
    assert.match(html, new RegExp(`${label} final paragraph`));
  }
  assert.ok(buttonNamed(html, "Notation"));
  assert.match(buttonNamed(html, "Notation")[1], /aria-haspopup="dialog"/);
  assert.doesNotMatch(html, /Observation vector lookup|Recorded measurement lookup|role="dialog"/);
  assert.equal((html.match(/Original qualification remains part of this account/g) || []).length, 90);

  const paper = render.selectedPaper({ source: { title: "Original paper", cards: [{ role: "theorist", entry_id: "entry.original", explanation_markdown: explanation, relevance_markdown: fit,
    formulation_markdown: "Full formulation:\n$$J(\\pi)=\\mathbb E_\\pi\\sum_{t=0}^{\\infty}\\gamma^t r_t$$", limitations_markdown: "Every stated applicability limit remains inspectable.", reading_extent: "Sections 2 and 3 read; theorem not independently verified.", evidence_locations: ["Theorem 2, equation 7"] }] } });
  assert.match(paper, /<details[^>]*data-reading-anchor="legacy-assessment:[^"]+"><summary>Read the earlier member assessment<\/summary>/);
  assert.match(paper, /<details[^>]*data-reading-anchor="paper-math:[^"]+"><summary>Full mathematics and reading basis<\/summary>/);
  for (const label of ["Contribution", "Fit"]) {
    assert.match(paper, new RegExp(`${label} first paragraph`));
    assert.match(paper, new RegExp(`${label} final paragraph`));
  }
  assert.equal((paper.match(/Original qualification remains part of this account/g) || []).length, 60);
  assert.match(paper, /<annotation encoding="application\/x-tex">J\(\\pi\)=\\mathbb E_\\pi\\sum_\{t=0\}\^\{\\infty\}\\gamma\^t r_t<\/annotation>/);
  for (const retained of ["Every stated applicability limit", "Sections 2 and 3 read", "Theorem 2, equation 7"]) assert.ok(paper.includes(retained), retained);
  assert.equal(basis.research_setting.statement_markdown, setting);
  assert.equal(basis.landscape.summary_markdown, findings);
});

test("P1 keeps every unanswered question discoverable in the third card", () => {
  const neighbor = { ...contextualItem, attention_id: "attention.neighbor", attention_version_id: "attention.neighbor.v1", question: "Which observation units are independent?" };
  const html = render.phaseOne({ project: { project_id: "questions.all", research_instructions: "Brief" }, attentionItems: [contextualItem, neighbor], artifacts: {} });
  assert.equal((html.match(/data-issue-state="response"/g) || []).length, 4); // One row and one contextual state badge per question.
  assert.equal((html.match(/<details class="phase-issue issue-row"/g) || []).length, 2);
  assert.doesNotMatch(html, /<details class="phase-issue issue-row"[^>]*\sopen(?:=|\s|>)/);
  for (const question of ["May a policy depend", "Which observation units are independent"]) {
    assert.ok(html.indexOf(question) > html.indexOf("Decisions to Discuss"));
    assert.ok(html.indexOf(question) < html.indexOf("Explore Individual Papers"));
  }
  assert.doesNotMatch(html, /Other questions and saved responses/);
});

test("P2 hands both following cards the same exact selected proposal without activating it", () => {
  const proposals = ["a", "b"].map((name) => ({ proposal_id: `proposal.${name}`, role: "theorist", generation_ref: { ...ref, run_id: `run.${name}` }, method: { title: `Method ${name}`, identity: { stable_id: `method.${name}`, version: 2, definition_sha256: name.repeat(64) } } }));
  const methods = proposals.map((proposal) => ({ method_id: proposal.method.identity.stable_id, branch_id: `${proposal.method.identity.stable_id}.branch`, identity: proposal.method.identity, status: "active" }));
  const calls = []; let issueContext; let furtherContext;
  const html = render.methodsRaw({ proposals, methods, initialPick: "run.b:proposal.b", onContinue: (...args) => calls.push(args),
    issues: (context) => { issueContext = context; return "ISSUE_SLOT"; }, furtherWork: (context) => { furtherContext = context; return "FURTHER_SLOT"; } });
  assert.equal((html.match(/<section\b[^>]*class="card(?: |")/g) || []).length, 2);
  assert.strictEqual(issueContext, furtherContext);
  assert.strictEqual(issueContext.proposal, proposals[1]);
  assert.strictEqual(issueContext.method, proposals[1].method);
  assert.strictEqual(issueContext.catalogMethod, methods[1]);
  assert.equal(issueContext.methodId, "method.b");
  assert.equal(issueContext.methodBranch, "method.b.branch");
  assert.ok(issueContext.draftStore instanceof Map);
  assert.ok(issueContext.proposedWork); assert.ok(issueContext.modificationOptions); assert.ok(issueContext.modelHistory); assert.equal(issueContext.exploreActions, undefined);
  assert.ok(html.indexOf("ISSUE_SLOT") > html.indexOf("Reviews and scientific sources"));
  assert.ok(html.indexOf("FURTHER_SLOT") > html.indexOf("ISSUE_SLOT"));
  assert.deepEqual(calls, []);
  let empty;
  render.methodsRaw({ issues: (context) => { empty = context; return null; } });
  assert.equal(empty.methodId, null); assert.equal(empty.methodBranch, "trunk"); assert.equal(empty.proposal, null);
});

test("P2 draft text and edit mode survive remounts and stay with the exact question source", () => {
  const question = { ...contextualItem, phase: "P2", target_phase: "P3", affected_record_ids: ["method.a"] };
  const projectId = "project.drafts";
  const draftStore = new Map([[clarificationDraftKey(projectId, question), { note: "Unsaved clarification draft", editing: true }]]);
  const answer = { attention_id: question.attention_id, attention: question, note: "Previously saved choice" };
  const props = { embedded: true, expanded: true, projectId, phase: "P2", phases: ["P3"], branch: "method.a", methodId: "method.a", methodTitle: "Method A", draftStore, items: [question], onSource: noop };
  assert.match(render.decisions(props), /<textarea[^>]*>Unsaved clarification draft<\/textarea>/);
  const editing = render.decisions({ ...props, answers: [answer] });
  assert.match(editing, /<textarea[^>]*>Unsaved clarification draft<\/textarea>/);
  assert.match(editing, />Cancel<\/button>/);
  assert.doesNotMatch(editing, /Edit clarification|Previously saved choice/);
  const changedSource = { ...question, generation_ref: { ...question.generation_ref, generation_id: "generation.changed" } };
  assert.doesNotMatch(render.decisions({ ...props, items: [changedSource] }), /Unsaved clarification draft/);
  assert.doesNotMatch(render.decisions({ ...props, projectId: "project.other" }), /Unsaved clarification draft/);
  assert.doesNotMatch(render.decisions({ ...props, draftStore: undefined }), /Unsaved clarification draft/);
});

test("historical P2 proposals retain their authored work plan without showing current branch tasks", () => {
  const identity = { stable_id: "method.a", version: 1, definition_sha256: "a".repeat(64) };
  const proposal = { proposal_id: "prop.old", role: "theorist", is_current_package: false,
    generation_ref: { ...ref, run_id: "run.old" }, method: { identity, title: "Original procedure" },
    proposed_evaluation_markdown: "Authored historical experiment plan." };
  const task = { ...contextualItem, attention_id: "task.current", kind: "research_task", phase: "P2", target_phase: "P4", affected_record_ids: ["method.a"], question: "CURRENT BRANCH TASK" };
  const props = { proposals: [proposal], attentionItems: [task], onSource: noop };
  const current = render.methods({ ...props, methods: [{ method_id: "method.a", identity, status: "proposed" }] });
  assert.match(current, /CURRENT BRANCH TASK/);
  const superseded = render.methods({ ...props, methods: [{ method_id: "method.a", identity: { ...identity, version: 2 }, status: "proposed" }] });
  assert.match(superseded, /Authored historical experiment plan/);
  assert.doesNotMatch(superseded, /CURRENT BRANCH TASK|Team research follow-up/);
  assert.doesNotMatch(render.methods({ ...props, methods: [] }), /CURRENT BRANCH TASK|Team research follow-up/);
});

test("method status note names both versions, the authored change, and the revision source", () => {
  const status = { status: "needs_update", current_version: 2, recorded_version: 1,
    change_summary: "The estimator now allows dependent observations.",
    source_ref: { branch: "trunk", phase: "P2", family: "method_catalog", generation_id: "gen.rev", sha256: "b".repeat(64) } };
  const html = render.methodStatusNote({ status, onOpen: noop });
  assert.match(html, /note method-status warn/);
  assert.match(html, /role="alert"/);
  assert.match(html, /Needs update: this work used model version 1\. The current model is version 2\./);
  assert.match(html, /estimator now allows dependent observations/);
  assert.match(html, /source-link/);
  assert.match(html, /Open the revision source/);
  const unknown = render.methodStatusNote({ status: { status: "unknown", message: "This model is absent from the current catalog; freshness cannot be established." }, onOpen: noop });
  assert.match(unknown, /absent from the current catalog/);
  assert.match(unknown, /role="status"/);
  assert.doesNotMatch(unknown, /warn|source-link/);
  assert.equal(render.methodStatusNote({ status: { status: "current" }, onOpen: noop }), "");
  assert.equal(render.methodStatusNote({ status: null, onOpen: noop }), "");
});

test("method status pill marks stale and unverifiable runs without hiding their state", () => {
  assert.match(render.methodStatusPill({ status: { status: "needs_update" } }), /pill warn/);
  assert.match(render.methodStatusPill({ status: { status: "needs_update" } }), /Needs update/);
  assert.match(render.methodStatusPill({ status: { status: "unknown" } }), /pill mut/);
  assert.match(render.methodStatusPill({ status: { status: "unknown" } }), /Applicability unknown/);
  assert.equal(render.methodStatusPill({ status: { status: "current" } }), "");
});

test("P2 history shows publication process counts and exact receipt without a quality verdict", () => {
  const html = render.methods({ onOpenRun: noop, proposals: [{
    proposal_id: "proposal.p2", role: "theorist", generation_ref: { ...ref, phase: "P2", run_id: "run.p2" },
    method: { title: "A published method", summary: "The saved procedure.", identity: { stable_id: "method.a", version: 1 } },
  }], publicationHistory: [{
    package_id: "package.p2", run_id: "run.p2", receipt_id: "receipt.p2", is_current_package: true,
    published_at: "2026-09-25T11:12:00Z", mechanical_repair_rounds: 2, researcher_correction_attempts: 1,
  }, {
    package_id: "package.earlier", run_id: "run.earlier", receipt_id: "receipt.earlier", is_current_package: false,
    mechanical_repair_rounds: 0, researcher_correction_attempts: 0,
  }] });
  assert.match(html, /<section class="p2-history"[^>]*><h3>Model versions and comparisons/);
  assert.match(html, /Current publication/);
  assert.match(html, /Earlier publication/);
  assert.match(html, /Mechanical repair rounds: 2 · Researcher-authorized correction attempts: 1/);
  assert.match(html, /Mechanical repair rounds: 0 · Researcher-authorized correction attempts: 0/);
  assert.match(html, /receipt\.p2/);
  assert.match(html, /receipt\.earlier/);
  assert.equal((html.match(/Open producing run/g) || []).length, 2);
  assert.match(html, /not scientific validation/);
  assert.doesNotMatch(html, /published cleanly|scientifically validated|correction succeeded/i);
});

test("P2 legacy publication history keeps unavailable counts distinct from zero", () => {
  const html = render.methods({ publicationHistory: [{
    package_id: null, run_id: null, receipt_id: null, is_current_package: true,
    mechanical_repair_rounds: null, researcher_correction_attempts: null,
  }] });
  assert.match(html, /Mechanical repair rounds: unavailable · Researcher-authorized correction attempts: unavailable/);
  assert.match(html, /Receipt: unavailable/);
  assert.doesNotMatch(html, /rounds: 0|attempts: 0|Open producing run/);
  const empty = render.methods({});
  assert.doesNotMatch(empty, /No lead comparison has been published yet/);
  assert.match(empty, /Published proposals will appear here after the team completes its review/);
  assert.equal((empty.match(/<section\b[^>]*class="card(?: |")/g) || []).length, 2);
  assert.doesNotMatch(empty, /Issues and decisions/);
});

test("phase summaries and research readers keep the same semantic roles across phases", () => {
  const p1 = render.literature({ basis: { landscape: { summary_markdown: "Published literature conclusion." } } });
  const p2 = render.methods({ proposals: [{ proposal_id: "proposal.roles", role: "theorist", generation_ref: { ...ref, phase: "P2", branch: "trunk" }, method: { title: "A candidate", summary: "Its authored mechanism." } }] });
  const p4 = render.empirical({ branch: "method.a", summaries: [{ branch: "method.a", phase: "P4", decision_summary: { conclusion_markdown: "Published evaluation conclusion." } }] });
  for (const [html, className, heading] of [[p1, "literature-overview-card", "Main Findings"], [p4, "empirical-decision", "Summary"]]) {
    assert.match(html, new RegExp(`<section class="card ${className}" data-card-role="summary"[^>]*>[\\s\\S]*?${heading}`));
  }
  for (const [html, className] of [[p1, "literature-library"], [p2, "p2-landscape p2-models-card"], [p4, "empirical-workspace"]]) {
    assert.match(html, new RegExp(`<section class="card ${className}" data-card-role="research"`));
  }
  const preparation = render.phaseTwoPreparation({ instructions: "", onInstructionsChange: noop, onLaunch: noop });
  assert.match(preparation, /data-card-role="action"/);
  assert.match(buttonNamed(preparation, "Prepare Phase 2 run")[1], /data-action="run"/);
});

test("attention clears for saved clarifications while an unanswered neighboring question stays visible", () => {
  const answered = { ...contextualItem, attention_id: "attention.answered", question: "Which model is intended?" };
  const answer = { attention_id: answered.attention_id, attention: answered, note: "Use the stated Gaussian model." };
  const props = { projectId: "project.test", branch: "trunk", phase: "P1", onSource: noop };
  const mixed = render.decisions({ ...props, items: [contextualItem, answered], answers: [answer] });
  assert.match(mixed, /class="card researcher-decisions" data-card-role="attention"/);
  assert.equal((mixed.match(/class="researcher-decision" data-card-role="attention"/g) || []).length, 1);
  assert.equal((mixed.match(/class="researcher-decision" data-card-role="history"/g) || []).length, 1);
  const resolved = render.decisions({ ...props, answers: [answer] });
  assert.match(resolved, /class="card researcher-decisions" data-card-role="history"/);
  assert.match(resolved, /Your saved clarifications/);
  assert.doesNotMatch(resolved, /Needs your input|data-card-role="attention"/);
  assert.match(buttonNamed(resolved, "Edit clarification")[1], /data-action="edit"/);
});

test("a waiting evaluation is a visible attention card with one action and no hidden response requirement", () => {
  const props = { branch: "method.a", phase: "P4", onOpenRun: noop };
  const html = render.waitingDirections({ ...props, runs: [{ run_id: "run.waiting", branch_id: "method.a", phase: "P4", state: "awaiting_user", mode: "p4.comprehensive" }, { run_id: "run.other", branch_id: "method.b", phase: "P4", state: "awaiting_user", mode: "p4.preliminary" }] });
  assert.match(html, /^<section class="card runs-awaiting-direction" data-card-role="attention">/);
  assert.match(html, /Evaluations waiting for your direction \(1\)/);
  assert.doesNotMatch(html, /<details|p4\.comprehensive|Feasibility check/);
  assert.match(buttonNamed(html, "Review waiting evaluation")[1], /data-action="details"/);
  assert.equal(render.waitingDirections({ ...props, runs: [{ branch_id: "method.a", phase: "P4", state: "published" }] }), "");
});
