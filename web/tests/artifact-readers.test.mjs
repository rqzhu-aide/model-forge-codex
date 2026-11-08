import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { fmt, fmtMs, fmtBudgetSeconds } from "../src/research.js";
import { readinessMessages } from "../src/readinessContent.js";
import { methodSeedMarkdown } from "../src/methodSeed.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-artifact-readers-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Question,{EmpiricalExhibit} from '${src}/components/EmpiricalQuestion.jsx'; import Implementation from '${src}/components/ImplementationReading.jsx'; import {ScientificDocuments} from '${src}/components/PhaseReading.jsx'; import Reading from '${src}/components/TechnicalReportReading.jsx'; export {default as EmpiricalReadingButton,empiricalReadingSnapshot} from '${src}/components/EmpiricalReading.jsx'; export const implementationElement=Implementation; export const renderElement=renderToStaticMarkup; const show=(C,p)=>renderToStaticMarkup(React.createElement(C,p)); export const question=p=>show(Question,p); export const exhibit=p=>show(EmpiricalExhibit,p); export const implementation=p=>show(Implementation,p); export const report=p=>show(Reading,p); export const documents=p=>show(ScientificDocuments,p);`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.a", phase: "P4", family: "diagnostics", generation_id: "gen.a", sha256: "a".repeat(64), run_id: "run.a" };
const noop = () => {};
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children), ...nodes(tree.props.resources)] : [];
function implementationReaders(props) {
  return new Map(nodes(render.implementationElement(props)).filter(node => node.type === render.EmpiricalReadingButton).map(control => {
    const snapshot = render.empiricalReadingSnapshot({ ...control.props, scope: { projectId: "project.test", phase: "P4", branch: ref.branch } });
    return [control.props.kind, { snapshot, html: render.renderElement(snapshot.body) }];
  }));
}

test("quantitative display preserves meaningful signs, small values, counts and exact inputs", () => {
  assert.equal(fmt(0), "0"); assert.equal(fmt(null), "Not recorded"); assert.equal(fmt(NaN), "Not recorded");
  assert.equal(fmt(0.00296654), "0.00297"); assert.equal(fmt(-0.032002, { uncertainty: 0.01685 }), "-0.032");
  assert.notEqual(fmt(1e-12), "0"); assert.equal(fmt(12345, { kind: "count" }).replaceAll(",", ""), "12345");
  assert.equal(fmtBudgetSeconds(2.4012), "2.4 s"); assert.equal(fmtBudgetSeconds(57.5988), "58 s"); assert.equal(fmtBudgetSeconds(597.96), "9 min 58 s"); assert.equal(fmtBudgetSeconds(0.01), "<0.1 s");
  assert.equal(fmtMs(2.4012), "2.4 ms");
  const saved = { estimate: 0.288819, mcse: 0.0168536 }; const before = JSON.stringify(saved); fmt(saved.estimate, { uncertainty: saved.mcse }); assert.equal(JSON.stringify(saved), before);
});

test("recorded values remain beside figures, table exhibits and broken exhibits with uncertainty and units", () => {
  const diagnostic = { generation_ref: ref, headline_numbers: [{ case_id: "case.one", metric: "error", estimate: 0.288819, mcse: 0.0168536, n_replicates: 24, ci_lo: 0.25, ci_hi: 0.33 }, { case_id: "case.two", metric: "error", estimate: null, n_replicates: null }] };
  for (const exhibit of [{ artifact_url: "/api/figure.png", media_type: "image/png" }, { table: { columns: [{ key: "mean_error", label: "mean_error" }], rows: [{ mean_error: 0.288819 }] } }, { source_error: "Figure digest mismatch" }]) {
    const html = render.question({ question: { result: { answer_markdown: "The observed difference is uncertain." }, exhibits: [exhibit] }, diagnostics: [diagnostic], cases: [{ case_id: "case.one", comparator_id: "selected_method" }], protocol: { metrics: [{ metric_id: "error", name: "Error", unit: "squared units" }] }, onSource: noop });
    for (const text of ["Recorded values, uncertainty and repetitions", "Usable repetitions", "squared units", "0.289", "Monte Carlo standard error 0.0169", "24", "Interval level", "Not recorded", "not uncertainty in the difference"]) assert.ok(html.includes(text), text);
    assert.doesNotMatch(html, /95%/);
  }
});

test("figure data links are declared and missing links stay explicit; enlargement is an in-app action", () => {
  const html = render.exhibit({ exhibit: { title: "Risk comparison", artifact_url: "/api/figure.svg", media_type: "image/svg+xml", data_sources: [{ artifact_url: "/api/data.csv", label: "Observed risk" }, { source_error: "Data digest mismatch" }] } });
  assert.match(html, /<button[^>]*aria-label="Enlarge figure: Risk comparison"/); assert.match(html, /Observed risk/); assert.match(html, /Data digest mismatch/); assert.match(html, /href="\/api\/data.csv"/);
  const absent = render.exhibit({ exhibit: { artifact_url: "/api/figure.png", media_type: "image/png" } }); assert.match(absent, /No explicit data-artifact link/);
});

test("question-specific excluded observations keep their recorded reason and source", () => {
  const html = render.question({ question: { result: {}, excluded_observations: [{ case_id: "case.one", count: 12, invalidation_reason: "The earlier solver stopped before its declared tolerance.", generation_ref: ref }] }, cases: [{ case_id: "case.one", label: "Small sample" }], onSource: noop });
  assert.match(html, /Why recorded observations were excluded/); assert.match(html, /Small sample/); assert.match(html, /earlier solver stopped/); assert.match(html, /12 excluded observation rows/); assert.match(html, /Excluded observations source/);
});

test("table headers preserve authored labels and offer bounded next-page access", () => {
  const html = render.exhibit({ exhibit: { table: { columns: [{ key: "n_pairs", label: "n_pairs" }, { key: "runtime_ms", label: "Fitting time", unit: "ms" }], rows: [{ n_pairs: 0, runtime_ms: 2 }], total_rows: 401, truncated: true, next_page_url: "/api/table?offset=200" } } });
  assert.match(html, /<th scope="col">n_pairs<\/th>/); assert.match(html, /Fitting time/); assert.match(html, /\(ms\)/); assert.match(html, /Next rows/); assert.doesNotMatch(html, /N pairs/);
});

test("question diagnostic fallback keeps authored metric names and recorded uncertainty states", () => {
  const protocol = { metrics: [], amendments: [{ added_metrics: [{ metric_id: "metric.manual", name: "Risk $R_{\\alpha}$", unit: "$\\mathrm{mg}$" }] }] };
  const diagnostics = [{ generation_ref: ref, headline_numbers: [
    { case_id: "case.one", metric: "metric.manual", estimate: null, n_replicates: 0, uncertainty_kind: "not_assessed", mcse: 0.2 },
    { case_id: "case.one", metric: "metric.workflow_check", estimate: 0, n_replicates: 12, uncertainty_kind: "not_applicable" },
  ] }];
  const props = { question: { result: {} }, diagnostics, protocol, cases: [{ case_id: "case.one", label: "RL-LPM1", comparator_id: "selected_method" }] };
  const before = structuredClone(props); const html = render.question(props);
  assert.match(html, /Risk <span class="math-inline">/);
  assert.match(html, /application\/x-tex">R_\{\\alpha\}/);
  assert.match(html, /<td>RL-LPM1<\/td>/);
  assert.match(html, /<td>metric.workflow_check<\/td>/);
  assert.match(html, /<td>Not recorded<\/td><td>Not assessed<\/td><td>0<\/td>/);
  assert.match(html, /<td>0<\/td><td>Not applicable<\/td><td>12<\/td>/);
  assert.doesNotMatch(html, />Metric manual<|>Metric workflow check<|Monte Carlo standard error 0.2/);
  assert.deepEqual(props, before);
});

test("implementation reader exposes authored correspondence, review and only verified file links", () => {
  const props = { records: [{ generation_ref: ref, sections: [{ key: "correspondence", title: "Method to code", body_md: "The update follows equation $x_{t+1}=x_t+1$." }], files: [{ kind: "code", label: "Solver", path: "solver.py", artifact_url: "/api/solver.py", source_verified: true }, { kind: "configuration", path: "settings.json", source_error: "Digest mismatch" }], theorist_review: { generation_ref: { ...ref, family: "theory_audit" }, sections: [{ key: "mathematical_fidelity", title: "Mathematical fidelity", body_md: "The boundary check remains incomplete." }] } }], onSource: noop };
  const html = render.implementation(props), readers = implementationReaders(props);
  for (const text of ["Method to code", "class=\"katex", "Saved files and checks", "Theorist assessment"]) assert.ok(html.includes(text), text);
  const files = readers.get("p4-implementation-files"), review = readers.get("p4-implementation-review");
  for (const text of ["Solver", "Inspect saved code", "Digest mismatch"]) assert.ok(files.html.includes(text), text);
  assert.match(files.html, /href="\/api\/solver.py"/); assert.doesNotMatch(files.html, /href="settings.json"/);
  for (const text of ["The boundary check remains incomplete", "Theorist assessment source"]) assert.ok(review.html.includes(text), text);
  assert.deepEqual(files.snapshot.body.props.children.props.record.generation_ref, ref);
  assert.deepEqual(review.snapshot.body.props.children.props.record.generation_ref, { ...ref, family: "theory_audit" });
});

test("structured implementation sections retain separate authored qualifications and exact publication warnings", () => {
  const props = { records: [{ body_md: "The executed implementation excludes zero weights.", evaluation_source_error: "This implementation belongs to an earlier evaluation.", sections: [{ key: "correspondence", body_md: "Normalization matches the selected equation." }], theorist_review: { body_md: "The available argument does not cover the excluded boundary.", sections: [{ key: "outcome_conclusion", body_md: "Fidelity is supported only in the interior." }] } }] };
  const html = render.implementation(props), readers = implementationReaders(props);
  for (const text of ["earlier evaluation", "Normalization matches"]) assert.ok(html.includes(text), text);
  assert.match(readers.get("p4-implementation-details").html, /excludes zero weights/);
  for (const text of ["does not cover the excluded boundary", "only in the interior"]) assert.ok(readers.get("p4-implementation-review").html.includes(text), text);
  const repeatedProps = { records: [{ body_md: "Exact repeated authored passage.", sections: [{ key: "correspondence", body_md: "Exact repeated authored passage." }] }] };
  const repeated = render.implementation(repeatedProps) + [...implementationReaders(repeatedProps).values()].map(item => item.html).join("");
  assert.equal((repeated.match(/Exact repeated authored passage/g) || []).length, 1);
  const trace = render.report({ initialTab: "evidence", traceability: [{ manuscript_source_error: "These saved claims belong to a different draft.", claims: [{ text: "An earlier draft claim." }] }] });
  assert.match(trace, /These saved claims belong to a different draft/); assert.match(trace, /An earlier draft claim/);
});

test("historical manuscripts render as plain supporting documents without metadata or source viewers", () => {
  const html = render.documents({ documents: [{ kind: "manuscript", title: "Qualified comparison", structured: { manuscript_kind: "revised_candidate", target_audience: "Statisticians", sections_present: ["abstract", "method", "limitations"], venue_length: "conference" }, body_md: "The saved result has limited support.", primary_artifact_kind: "tex_source", primary_artifact_url: "/api/saved-paper.tex", source_text: "TeX source body", generation_ref: { ...ref, phase: "P5" } }], onSource: noop });
  for (const text of ["Qualified comparison", "saved result has limited support", "Open original document", 'href="/api/saved-paper.tex"']) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /Revised manuscript|Statisticians|Conference paper|Inspect TeX source|Open TeX source|Open manuscript PDF|TeX source body|manuscript-metadata|<iframe/);
});

test("full Analyst reader separates exact Lead reporting notes and retains the original account", () => {
  const noteRef = { ...ref, family: "empirical_evidence_index", package_id: "package.original", entry_pointer: "/reporting_corrections/0" };
  const original = { kind: "analyst_synthesis", phase: "P4", generation_ref: { ...ref, family: "analyst_synthesis" }, primary_source_verified: true, primary_artifact_kind: "json", primary_content: { summary_markdown: "The original endpoint is 0.835254." } };
  const notes = { producer_role: "research_lead", notes: [{ text: "The saved endpoint rounds to 0.835253.", generation_ref: noteRef }, { text: "Singleton timing is recorded in diagnostics.", generation_ref: { ...noteRef, entry_pointer: "/reporting_corrections/1" } }] };
  const html = render.documents({ documents: [{ ...original, lead_reporting_notes: notes }], onSource: noop });
  for (const text of ["Research Lead reporting notes for this evaluation", "recorded these notes separately", "0.835253", "Singleton timing", "The original endpoint is 0.835254."]) assert.ok(html.includes(text), text);
  assert.equal((html.match(/Reporting note source/g) || []).length, 2);
  assert.ok(html.indexOf("0.835253") < html.indexOf("0.835254"));
  assert.doesNotMatch(render.documents({ documents: [original], onSource: noop }), /Research Lead reporting notes|Reporting note source/);
  assert.doesNotMatch(render.documents({ documents: [{ ...original, kind: "theory_record", lead_reporting_notes: notes }], onSource: noop }), /Research Lead reporting notes/);
  assert.doesNotMatch(render.documents({ documents: [{ ...original, lead_reporting_notes: { ...notes, producer_role: "theorist" } }], onSource: noop }), /Research Lead reporting notes/);
});

test("P5 support reader shows actual claims, counterevidence, unresolved links and exact sources", () => {
  const html = render.report({ initialTab: "evidence", traceability: [{ generation_ref: { ...ref, phase: "P5", family: "claim_traceability" }, claims: [{ statement_id: "claim.main", text: "Risk decreases only in the measured regime.", scope: "Gaussian samples", evidence_links: [{ relationship: "support", label: "Small-sample comparison", generation_ref: ref }, { relationship: "counterevidence", label: "Boundary experiment", source_error: "The exact empirical record is unavailable." }] }] }], onSource: noop });
  for (const text of ["Risk decreases only", "Gaussian samples", "Small-sample comparison", "Counterevidence", "Boundary experiment", "The exact empirical record is unavailable", "Inspect exact source"]) assert.ok(html.includes(text), text);
});

test("reviews identify the earlier report version they assessed without duplicating the Summary status", () => {
  const earlier = { ...ref, phase: "P5", family: "technical_report", generation_id: "report.old" }; const current = { ...earlier, generation_id: "report.new", sha256: "b".repeat(64) };
  const report = { kind: "technical_report", title: "Current report", generation_ref: current, body_md: "The current report body.", completion: { status: "complete" }, review_status: "not_independently_reviewed" };
  const review = { kind: "outside_review", body_md: "Clarify the comparison.", reviewed_report_ref: earlier, generation_ref: { ...ref, phase: "P5", family: "outside_review" } };
  const html = render.report({ initialTab: "reviews", documents: [report, review], onSource: noop });
  assert.match(html, /concerns an earlier report version/); assert.match(html, /Exact report assessed by this review/); assert.match(html, /Clarify the comparison/);
  assert.doesNotMatch(html, /concerns the current report version|Complete report|Report tools|Download offline HTML/);
  const exact = render.report({ initialTab: "reviews", documents: [report, { ...review, reviewed_report_ref: current }], onSource: noop });
  assert.match(exact, /concerns the current report version/); assert.doesNotMatch(exact, /concerns an earlier report version/);
  const unknown = render.report({ initialTab: "reviews", documents: [report, { ...review, reviewed_report_ref: undefined }], onSource: noop });
  assert.match(unknown, /not identified in the available record/);
  const orphan = render.report({ initialTab: "reviews", documents: [review], onSource: noop });
  assert.match(orphan, /The current report is unavailable, so this review cannot be compared with it/);
});

test("retained supporting documents expose source and supplement links with their availability", () => {
  const html = render.documents({ documents: [{ kind: "manuscript", generation_ref: { ...ref, phase: "P5", family: "manuscript", generation_id: "draft.old" }, body_md: "# Original reviewed paper\n\nThe saved result has limited support.", primary_artifact_kind: "markdown", primary_artifact_url: "/api/old-paper.md?sha256=old", supplementary_artifacts: [{ label: "Original TeX source", artifact_url: "/api/old-paper.tex?sha256=source", source_verified: true }, { path: "original-references.bib", source_error: "The exact retained file is missing." }] }], onSource: noop });
  for (const text of ["Original reviewed paper", "saved result has limited support", "Sources and supplements", "Original TeX source", "original-references.bib", "The exact retained file is missing."]) assert.ok(html.includes(text), text);
  assert.match(html, /href="\/api\/old-paper.md\?sha256=old"/);
  assert.match(html, /href="\/api\/old-paper.tex\?sha256=source"/);
  assert.doesNotMatch(html, /href="original-references.bib"/);
});

test("readiness explains research work while preserving unknown reasons without guessing", () => {
  assert.deepEqual(readinessMessages(["P4 needs a complete current empirical_evidence_index aligned to the selected model version 1"]), ["Complete an evaluation for the selected model so the experimental evidence is available for the current model."]);
  assert.deepEqual(readinessMessages([{ code: "missing_manuscript" }, "Unknown gate diagnostic"]), ["Create a manuscript draft before requesting review.", "Unknown gate diagnostic"]);
});

test("method seeds are readable scientific copies and preserve the exact original definition", () => {
  const method = { title: "Weighted mean", identity: { stable_id: "method.a", definition_sha256: "opaque" }, summary: "Estimate a weighted mean.", canonical_definition: { target_or_estimand: { latex: "\\mu=E[X]" }, algorithm_or_update_rule: [{ order: 1, operation: "Compute the supplied weights." }, { order: 2, operation: "Return $\\sum_i w_i X_i$." }] }, limitations: ["Positive weights are required."] };
  const before = JSON.stringify(method); const seed = methodSeedMarkdown(method);
  assert.match(seed, /# Weighted mean/); assert.match(seed, /\$\$\n\\mu=E\[X\]\n\$\$/); assert.match(seed, /Compute the supplied weights/); assert.match(seed, /Positive weights/); assert.doesNotMatch(seed, /definition_sha256|opaque|"canonical_definition"/); assert.equal(JSON.stringify(method), before);
  const nested = methodSeedMarkdown({ title: "Stored method", mathematical_definition: { canonical_artifact: { path: "internal.json", sha256: "opaque" }, canonical_definition: { target_or_estimand: "Exact authored target" } } });
  assert.match(nested, /Exact authored target/); assert.doesNotMatch(nested, /internal.json|opaque|Canonical artifact/);
});
