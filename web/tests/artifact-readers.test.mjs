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
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Question,{EmpiricalExhibit} from '${src}/components/EmpiricalQuestion.jsx'; import Implementation from '${src}/components/ImplementationReading.jsx'; import {ManuscriptReading,ScientificDocuments} from '${src}/components/PhaseReading.jsx'; const show=(C,p)=>renderToStaticMarkup(React.createElement(C,p)); export const question=p=>show(Question,p); export const exhibit=p=>show(EmpiricalExhibit,p); export const implementation=p=>show(Implementation,p); export const manuscript=p=>show(ManuscriptReading,p); export const documents=p=>show(ScientificDocuments,p);`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.a", phase: "P4", family: "diagnostics", generation_id: "gen.a", sha256: "a".repeat(64), run_id: "run.a" };
const noop = () => {};

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
    for (const text of ["Recorded values, uncertainty and repetitions", "Usable repetitions", "squared units", "0.289", "MCSE 0.0169", "24", "Interval level", "Not recorded", "not uncertainty in the difference"]) assert.ok(html.includes(text), text);
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

test("table headers humanize only defaults and offer bounded next-page access", () => {
  const html = render.exhibit({ exhibit: { table: { columns: [{ key: "n_pairs", label: "n_pairs" }, { key: "runtime_ms", label: "Fitting time", unit: "ms" }], rows: [{ n_pairs: 0, runtime_ms: 2 }], total_rows: 401, truncated: true, next_page_url: "/api/table?offset=200" } } });
  assert.match(html, /N pairs/); assert.match(html, /Fitting time/); assert.match(html, /\(ms\)/); assert.match(html, /Next rows/); assert.doesNotMatch(html, /<th[^>]*>n_pairs/);
});

test("implementation reader exposes authored correspondence, review and only verified file links", () => {
  const html = render.implementation({ records: [{ generation_ref: ref, sections: [{ key: "correspondence", title: "Method to code", body_md: "The update follows equation $x_{t+1}=x_t+1$." }], files: [{ kind: "code", label: "Solver", path: "solver.py", artifact_url: "/api/solver.py", source_verified: true }, { kind: "configuration", path: "settings.json", source_error: "Digest mismatch" }], theorist_review: { generation_ref: { ...ref, family: "theory_audit" }, sections: [{ key: "mathematical_fidelity", title: "Mathematical fidelity", body_md: "The boundary check remains incomplete." }] } }], onSource: noop });
  for (const text of ["Method to code", "class=\"katex", "Solver", "Inspect saved code", "Digest mismatch", "The boundary check remains incomplete", "Theorist assessment source"]) assert.ok(html.includes(text), text);
  assert.doesNotMatch(html, /href="settings.json"/);
});

test("structured implementation sections retain separate authored qualifications and exact publication warnings", () => {
  const html = render.implementation({ records: [{ body_md: "The executed implementation excludes zero weights.", evaluation_source_error: "This implementation belongs to an earlier evaluation.", sections: [{ key: "correspondence", body_md: "Normalization matches the selected equation." }], theorist_review: { body_md: "The available argument does not cover the excluded boundary.", sections: [{ key: "outcome_conclusion", body_md: "Fidelity is supported only in the interior." }] } }] });
  for (const text of ["excludes zero weights", "earlier evaluation", "Normalization matches", "does not cover the excluded boundary", "only in the interior"]) assert.ok(html.includes(text), text);
  const repeated = render.implementation({ records: [{ body_md: "Exact repeated authored passage.", sections: [{ key: "correspondence", body_md: "Exact repeated authored passage." }] }] });
  assert.equal((repeated.match(/Exact repeated authored passage/g) || []).length, 1);
  const trace = render.manuscript({ initialTab: "evidence", traceability: [{ manuscript_source_error: "These saved claims belong to a different draft.", claims: [{ text: "An earlier draft claim." }] }] });
  assert.match(trace, /These saved claims belong to a different draft/); assert.match(trace, /An earlier draft claim/);
});

test("manuscript metadata and TeX source remain distinct from rendered manuscript text", () => {
  const html = render.documents({ documents: [{ kind: "manuscript", title: "Paper", structured: { manuscript_kind: "revised_candidate", target_audience: "Statisticians", sections_present: ["abstract", "method", "limitations"] }, primary_artifact_kind: "tex_source", source_text: "\\documentclass{article}", primary_artifact_url: "/api/manuscript.tex" }] });
  for (const text of ["Revised manuscript", "Statisticians", "Abstract, Method, Limitations", "Inspect TeX source", "Open TeX source"]) assert.ok(html.includes(text), text);
  assert.match(html, /<pre class="record">\\documentclass/);
});

test("P5 support reader shows actual claims, counterevidence, unresolved links and exact sources", () => {
  const html = render.manuscript({ initialTab: "evidence", traceability: [{ generation_ref: { ...ref, phase: "P5", family: "claim_traceability" }, claims: [{ statement_id: "claim.main", text: "Risk decreases only in the measured regime.", scope: "Gaussian samples", evidence_links: [{ relationship: "support", label: "Small-sample comparison", generation_ref: ref }, { relationship: "counterevidence", label: "Boundary experiment", source_error: "The exact empirical record is unavailable." }] }] }], onSource: noop });
  for (const text of ["Risk decreases only", "Gaussian samples", "Small-sample comparison", "Counterevidence", "Boundary experiment", "The exact empirical record is unavailable", "Inspect exact source"]) assert.ok(html.includes(text), text);
});

test("manuscript scope comes from the saved record and a retained PDF has a readable preview", () => {
  const html = render.documents({ documents: [{ kind: "manuscript", structured: { title: "Qualified comparison", venue_length: "conference" }, primary_artifact_kind: "pdf", primary_artifact_url: "/api/saved-paper.pdf", primary_source_verified: true, generation_ref: { ...ref, phase: "P5" } }], onSource: noop });
  assert.match(html, /Conference paper/);
  assert.match(html, /<iframe[^>]*title="Qualified comparison PDF preview"[^>]*src="\/api\/saved-paper.pdf"/);
  assert.match(html, /Open manuscript PDF/);
  const legacy = render.documents({ documents: [{ kind: "manuscript", structured: { title: "Earlier manuscript" }, body_md: "Earlier scope was not recorded." }], onSource: noop });
  assert.doesNotMatch(legacy, /Journal article|Conference paper/);
});

test("reviews identify their own earlier draft without duplicating the overview status", () => {
  const earlier = { ...ref, phase: "P5", family: "manuscript", generation_id: "draft.old" }; const current = { ...earlier, generation_id: "draft.new" };
  const html = render.manuscript({ initialTab: "reviews", documents: [{ kind: "outside_review", body_md: "Clarify the comparison.", reviewed_manuscript_ref: earlier, generation_ref: { ...ref, phase: "P5", family: "outside_review" } }], reviewContext: { status: "revised_after_review", current_manuscript_ref: current, reviewed_manuscript_ref: earlier }, onSource: noop });
  assert.match(html, /earlier draft linked here/); assert.match(html, /Draft assessed by this review/); assert.doesNotMatch(html, /present revision has not itself been independently reviewed/);
});

test("saved manuscript reader exposes retained source and supplement links with their availability", () => {
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
