import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { restoreOpenDisclosures } from "../src/readingPosition.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p5-reader-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Reading,{TechnicalReportDocument,ReportSummary} from '${src}/components/TechnicalReportReading.jsx'; import {ScientificDocuments} from '${src}/components/PhaseReading.jsx'; import {ResearchDocument,SourceRef,MethodStatusNote} from '${src}/components/Shared.jsx'; const draw=C=>props=>renderToStaticMarkup(React.createElement(C,props)); export const document=draw(TechnicalReportDocument); export const summary=draw(ReportSummary); export const scientific=draw(ScientificDocuments); export const reading=draw(Reading); export const research=draw(ResearchDocument); export const documentTree=props=>TechnicalReportDocument(props); export const scientificTree=props=>ScientificDocuments(props); export const reviewTree=props=>Reading(props).props.children.props.tabs.find(tab=>tab.id==='reviews').content; export const changesTree=props=>Reading(props).props.children.props.tabs.find(tab=>tab.id==='changes').content; export const sourceRef=SourceRef; export const statusNote=MethodStatusNote;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const ref = { branch: "method.conditional", phase: "P5", family: "technical_report", generation_id: "report.current", sha256: "a".repeat(64), run_id: "run.report", package_id: "package.report" };
const document = { kind: "technical_report", title: "Conditional technical report", generation_ref: ref, body_md: "## Scientific conclusion\n\nThe synthetic ordering is inconclusive; clinical benefit was not assessed. Use $n=90$.", completion: { status: "interim", missing_work: ["Numerical coverage remains conditional."] }, method_identity: { stable_id: "method.conditional", version: 2 }, problem_context_ref: { revision: 4 }, review_status: "not_independently_reviewed", portable_artifact_url: "/api/v1/report?view=portable" };
const material = { path: "values.csv", authored_path: "authored-values.csv", artifact_path: "retained-values.csv", artifact_id: "artifact.values", uri: "artifact://values", artifact_url: "/api/v1/retained-values", source_verified: true, media_type: "text/csv" };
const walk = node => Array.isArray(node) ? node.flatMap(walk) : !node || typeof node !== "object" ? [] : [node, ...walk(node.props?.children)];
function disclosuresAt(html, passage) {
  const offset = html.indexOf(passage); assert.notEqual(offset, -1, passage);
  const stack = [];
  for (const tag of html.slice(0, offset).match(/<\/?details\b[^>]*>/g) || []) {
    if (tag.startsWith("</")) stack.pop(); else stack.push(tag);
  }
  return stack;
}
const bodyDocument = (body_md, report_materials = [material]) => ({ ...document, body_md, report_materials });

test("corrected delivery is current while complete mixed concerns and independent review stay readable", () => {
  const state = { publication: "published", portable_export_check: "passed", message: "The report passed publication checks and was published.",
    authored_delivery_note: "The earlier portable-rendering check passed after correction. Scientific concerns and independent review requirements remain as recorded.", report_ref: ref };
  const concern = { statement: "The earlier export failed, and its numerical tolerance remains unverified.", consequence: "Repair export and verify the numerical bound." };
  const html = ui.scientific({ documents: [{ kind: "assembly_report", delivery_state: state,
    structured: { unresolved_issues: [concern] }, display_structured: { unresolved_issues: [{ statement: "Population transport remains unverified." }], recorded_checks: ["Independently review the exact report."] },
    delivery_history: [concern] }] });
  assert.match(html, /Export check passed/);
  assert.match(html, /Population transport remains unverified/);
  assert.match(html, /Independently review the exact report/);
  assert.match(html, /Recorded checks and scientific requirements/);
  assert.ok(html.indexOf("Export check passed") < html.indexOf("The earlier export failed"));
  const disclosures = disclosuresAt(html, "The earlier export failed");
  assert.ok(disclosures.length > 0 && disclosures.every(tag => !/\bopen(?:[=\s>])/.test(tag)));
  assert.match(html, /numerical tolerance remains unverified/);
});

test("a numbered report table has one caption, including its authored target and scientific notation", () => {
  const source = [
    'Table 1 gives the comparison.',
    '',
    '<a id="results-table"></a>',
    '**Table 1. Estimated reward.** Mean $R$ among eligible datasets.',
    '',
    '| Method | Mean |', '| --- | ---: |', '| Baseline | 0.5 |',
  ].join('\n');
  const html = ui.document({ document: bodyDocument(source) });
  const caption = html.match(/<caption id="([^"]+)">([\s\S]*?)<\/caption>/);
  assert.ok(caption);
  assert.ok(html.includes('aria-labelledby="' + caption[1] + '"'));
  assert.match(caption[2], /results-table/);
  assert.match(caption[2], /katex/);
  assert.equal(html.split('Estimated reward.').length - 1, 1);
  assert.match(html, /<p>Table 1 gives the comparison\.<\/p>/);
});

test("missing review evidence stays distinct from confirmed absence and review of another version", () => {
  for (const review_status of [undefined, "unknown", "unrecognized-historical-status"]) {
    const retained = { ...document, review_status }, before = structuredClone(retained);
    const html = ui.document({ document: retained });
    assert.match(html, /I can&#x27;t confirm an independent review of this draft/);
    assert.doesNotMatch(html, /This version has not been independently reviewed|This version was independently reviewed/);
    assert.deepEqual(retained, before);
  }
  assert.match(ui.document({ document }), /This version has not been independently reviewed/);
  const earlier = ui.document({ document: { ...document, review_status: "independently_reviewed", reviewed_report_ref: { ...ref, generation_id: "earlier", sha256: "b".repeat(64) } } });
  assert.match(earlier, /Review concerns an earlier version/);
  assert.doesNotMatch(earlier, /This version has not been independently reviewed|This version was independently reviewed/);
});

test("Analyst source reader renders complete primary prose and math with an exact original link", () => {
  const account = { title: "Complete Analyst account", conclusion: "Qualified result.", questions: [{ key: "unmatched.key", title: "Authored question title", outcome: "mixed", answer_markdown: "The full answer uses $x=1$.", comparison_markdown: "Complete comparison.", reliability_markdown: "Complete reliability.", uncertainty_markdown: "Complete uncertainty.", limitations_markdown: "Full limits.", decision_implication_markdown: "Full implication.", next_steps_markdown: "Full next step." }], implementation_summary: { verification: "Exact implementation verification." } };
  const source = { kind: "analyst_synthesis", generation_ref: { ...ref, phase: "P4", family: "analyst_synthesis" }, primary_source_verified: true, primary_artifact_kind: "json", primary_content: account, primary_artifact_url: "/api/v1/exact/analyst.json?sha256=retained", structured: { question_results: [{ answer_markdown: "Full Q4." }] } };
  const before = structuredClone(source);
  const html = ui.scientific({ documents: [source], showRecordSource: false });
  for (const text of ["Complete Analyst account", "Qualified result.", "Authored question title", "Complete comparison.", "Complete reliability.", "Complete uncertainty.", "Full limits.", "Full implication.", "Full next step.", "Exact implementation verification.", "Open original document"]) assert.ok(html.includes(text), text);
  assert.match(html, /class="katex"/);
  assert.match(html, /href="\/api\/v1\/exact\/analyst.json\?sha256=retained"/);
  assert.doesNotMatch(html, /Full Q4\.|unmatched.key/);
  const unavailable = ui.scientific({ documents: [{ ...source, primary_content: undefined, primary_source_verified: undefined, primary_artifact_url: undefined, document_error: "The readable Analyst account is missing or its bytes no longer match the published digest." }], showRecordSource: false });
  assert.match(unavailable, /Analyst account is missing/);
  assert.doesNotMatch(unavailable, /Qualified result\.|Complete comparison\.|href=/);
  assert.deepEqual(source, before);
});

test("P5 compact header keeps completion, exact review, gaps and stale notices open while identities are in a native disclosure", () => {
  const value = { ...document, method_status: { status: "needs_update", recorded_version: 2, current_version: 3 }, context_change_notices: [{ status: "reassessment_required", message: "The study context needs reassessment." }], report_materials_error: "One exact report material is unavailable." };
  const before = structuredClone(value), opened = [];
  const html = ui.document({ document: value, onSource: source => opened.push(source) });
  for (const passage of ["Interim report", "has not been independently reviewed", "Work still needed", "Numerical coverage remains conditional", "Needs update", "The study context needs reassessment", "One exact report material is unavailable", "The synthetic ordering is inconclusive"]) assert.deepEqual(disclosuresAt(html, passage), [], passage);
  for (const passage of ["method.conditional", "Report generation", "Problem context"]) assert.match(disclosuresAt(html, passage)[0], /report-source-details/);
  assert.match(html, /<details class="research-details report-source-details" data-reading-anchor="technical-report:report.current:source-details"><summary>Source details<\/summary>/);
  assert.match(html, /<dt>Model version<\/dt><dd>2<\/dd>/);
  assert.equal((html.match(/Download offline HTML/g) || []).length, 1);
  assert.equal((html.match(/Open HTML report/g) || []).length, 1);
  assert.ok(html.indexOf("One exact report material is unavailable") < html.indexOf("Download offline HTML"));
  assert.ok(html.indexOf("Download offline HTML") < html.indexOf("Scientific conclusion"));
  assert.match(html, /view=portable&amp;download=1/);
  assert.match(html, /class="katex"/);
  for (const node of walk(ui.documentTree({ document: value, onSource: source => opened.push(source) })).filter(node => node.type === ui.sourceRef)) ui.sourceRef(node.props).props.onClick();
  assert.deepEqual(opened, [ref]);
  assert.deepEqual(value, before);
});

test("source drawers omit self-source actions while keeping revision sources, retained files and report exports", () => {
  const revision = { ...ref, phase: "P2", family: "method_catalog", generation_id: "model.revision", sha256: "b".repeat(64) };
  const method_status = { status: "needs_update", recorded_version: 2, current_version: 3, source_ref: revision };
  const report = { ...document, method_status, report_materials: [material], primary_artifact_url: "/api/v1/report.md" };
  const manuscript = { kind: "manuscript", generation_ref: { ...ref, family: "manuscript", generation_id: "manuscript.exact" }, body_md: "Original manuscript account.", method_status, primary_artifact_url: "/api/v1/manuscript.md", review_focus: "Frozen reviewer directions.", review_focus_url: "/api/v1/review-focus", supplementary_artifacts: [{ artifact_url: material.artifact_url, label: "Retained values" }] };
  const before = structuredClone({ report, manuscript });
  const cases = [
    { render: ui.document, tree: ui.documentTree, props: { document: report }, selfLabel: "Inspect exact report source", links: ["Download offline HTML", "Open HTML report", "Open retained Markdown source"], paths: ["/api/v1/report?view=portable", "/api/v1/report.md", material.artifact_url] },
    { render: ui.scientific, tree: ui.scientificTree, props: { documents: [manuscript] }, selfLabel: "Open source", links: ["Open original document", "Open frozen review directions", "Retained values"], paths: ["/api/v1/manuscript.md", "/api/v1/review-focus", material.artifact_url] },
  ];
  for (const item of cases) {
    const opened = [], props = { ...item.props, showRecordSource: false, onSource: source => opened.push(source) };
    const html = item.render(props);
    assert.doesNotMatch(html, new RegExp(`>${item.selfLabel}</button>`));
    assert.match(item.render({ ...props, showRecordSource: undefined }), new RegExp(`>${item.selfLabel}</button>`));
    assert.match(html, /Open the revision source/);
    for (const link of item.links) assert.ok(html.includes(link), link);
    for (const path of item.paths) assert.ok(html.includes(`href="${path.replaceAll("&", "&amp;")}`), path);
    const tree = item.tree(props);
    assert.equal(walk(tree).filter(node => node.type === ui.sourceRef).length, 0);
    for (const note of walk(tree).filter(node => node.type === ui.statusNote)) {
      for (const source of walk(ui.statusNote(note.props)).filter(node => node.type === ui.sourceRef)) ui.sourceRef(source.props).props.onClick();
    }
    assert.deepEqual(opened, [revision]);
  }
  assert.deepEqual({ report, manuscript }, before);
});

test("P5 complete conditional reports retain their scientific limits and exact review does not transfer to revised or unidentified bytes", () => {
  const complete = { ...document, completion: { status: "complete", missing_work: [] }, review_status: "independently_reviewed" };
  const current = ui.document({ document: complete });
  assert.match(current, /Complete report/); assert.match(current, /This version was independently reviewed/);
  assert.match(current, /clinical benefit was not assessed/); assert.doesNotMatch(current, /Work still needed/);
  const older = ui.document({ document: { ...complete, reviewed_report_ref: { ...ref, generation_id: "report.old", sha256: "b".repeat(64) } } });
  assert.match(older, /Review concerns an earlier version/); assert.doesNotMatch(older, /This version was independently reviewed/);
  for (const unavailable of [{ ...complete, generation_ref: undefined }, { ...complete, generation_ref: {} }, { ...complete, reviewed_report_ref: {} }]) {
    const html = ui.document({ document: unavailable });
    assert.match(html, /independent review of this version cannot be established/);
    assert.doesNotMatch(html, /This version was independently reviewed/);
  }
});

test("P5 report Reviews distinguish exact current and earlier generations while retaining the original assessed-source action", () => {
  const targets = [ref, { ...ref, object_id: "retained-component" }, { ...ref, generation_id: "report.old" }, { ...ref, sha256: "b".repeat(64) }, { ...ref, family: "technical_report_candidate" }, { ...ref, branch: "method.other" }];
  for (const [index, target] of targets.entries()) {
    const review = { kind: "outside_review", title: "Original independent assessment", body_md: "Retained first-reader concern.", reviewed_report_ref: target }, before = structuredClone(review), opened = [];
    const props = { documents: [document, review], initialTab: "reviews", onSource: source => opened.push(source) };
    const html = ui.reading(props);
    if (index < 2) { assert.match(html, /This assessment concerns the current report version/); assert.doesNotMatch(html, /This assessment concerns an earlier report/); }
    else { assert.match(html, /This assessment concerns an earlier report/); assert.match(html, /does not review the current version/); }
    assert.match(html, /Retained first-reader concern/);
    for (const node of walk(ui.reviewTree(props)).filter(node => node.type === ui.sourceRef)) ui.sourceRef(node.props).props.onClick();
    assert.deepEqual(opened, [target]); assert.deepEqual(review, before);
  }
});

test("P5 missing review targets or unavailable canonical identity stay unknown and candidates cannot establish canonical review", () => {
  const review = { kind: "outside_review", body_md: "Original review text." };
  for (const target of [undefined, {}, { generation_id: ref.generation_id }]) {
    const html = ui.reading({ documents: [document, { ...review, reviewed_report_ref: target }], initialTab: "reviews" });
    assert.match(html, /report version assessed by this review is not identified/);
    assert.doesNotMatch(html, /This assessment concerns the current report version|This assessment concerns an earlier report/);
  }
  const target = { ...review, reviewed_report_ref: ref };
  for (const current of [null, { ...document, generation_ref: undefined }, { ...document, kind: "technical_report_candidate" }]) {
    const html = ui.reading({ documents: [current, target].filter(Boolean), initialTab: "reviews" });
    assert.match(html, /current report is unavailable/); assert.match(html, /Exact report assessed by this review/);
    assert.doesNotMatch(html, /This assessment concerns the current report version|This assessment concerns an earlier report/);
  }
});

test("P5 report-relative links resolve exact unique retained aliases and preserve external links and local anchors", () => {
  const aliases = [material.path, material.authored_path, material.artifact_path, material.artifact_id, material.uri, material.artifact_url];
  const markdown = aliases.map((alias, index) => `[Exact source ${index}](${alias})`).join("\n\n") + '\n\n<a id="analysis"></a>\n\n[Analysis](#analysis) and [Paper](https://example.org/paper).';
  const value = bodyDocument(markdown), before = structuredClone(value);
  const html = ui.document({ document: value });
  for (const index of aliases.keys()) assert.match(html, new RegExp(`href="/api/v1/retained-values"[^>]*>Exact source ${index}</a>`));
  assert.match(html, /id="report-report.current-analysis"/); assert.match(html, /href="#report-report.current-analysis">Analysis/);
  assert.match(html, /href="https:\/\/example.org\/paper"[^>]*>Paper/);
  assert.doesNotMatch(html, /\[Exact source/);
  assert.deepEqual(value, before);
});

test("explicit report-authored file aliases take precedence over upstream native paths with the same spelling", () => {
  const reportFile = { ...material, path: "working/research_lead/srpes.py", authored_path: "srpes.py", artifact_id: "artifact.report.srpes", uri: "artifact://report.srpes", sha256: "c".repeat(64), artifact_url: "/api/v1/report-srpes.py", media_type: "text/plain" };
  const nativeFile = { path: "srpes.py", artifact_id: "artifact.upstream.srpes", sha256: reportFile.sha256, source_verified: true, artifact_url: "/api/v1/frozen-srpes.py", media_type: "text/plain" };
  for (const materials of [[reportFile, nativeFile], [nativeFile, reportFile]]) {
    const value = bodyDocument("[Current implementation](srpes.py) and [Upstream source](artifact.upstream.srpes).", materials), before = structuredClone(value);
    const html = ui.document({ document: value });
    assert.match(html, /href="\/api\/v1\/report-srpes.py"[^>]*>Current implementation<\/a>/);
    assert.match(html, /href="\/api\/v1\/frozen-srpes.py"[^>]*>Upstream source<\/a>/);
    assert.doesNotMatch(html, /Current implementation: The exact retained file is unavailable/);
    assert.deepEqual(value, before);
  }
});

test("an ambiguous or unverified explicit authored alias cannot fall back to a native path", () => {
  const authored = { ...material, path: "working/report/values.csv", authored_path: "values.csv" };
  const native = { ...material, authored_path: undefined, artifact_id: "artifact.upstream", artifact_url: "/api/v1/upstream-values" };
  for (const materials of [[{ ...authored, source_verified: false }, native], [{ ...authored, source_error: "Authored source changed." }, native], [authored, { ...authored, artifact_id: "artifact.competing", artifact_url: "/api/v1/competing-values" }, native], [authored, { ...authored }, native]]) {
    const html = ui.document({ document: bodyDocument("[Declared data](values.csv)", materials) });
    assert.doesNotMatch(html, /href="[^"]+"[^>]*>Declared data<\/a>/);
    assert.match(html, /Declared data:/);
    if (materials.some(item => item.source_error)) assert.match(html, /Authored source changed/);
  }
  const nativeOnly = ui.document({ document: bodyDocument("[Declared data](values.csv)", [native]) });
  assert.match(nativeOnly, /href="\/api\/v1\/upstream-values"[^>]*>Declared data<\/a>/);
});

test("P5 exact file-link hook propagates through headings, quotes, nested lists, table cells and structured recursion without consuming code", () => {
  const markdown = '## [Heading data](values.csv)\n\n> [Quoted data](values.csv)\n\n1. [First data](values.csv)\n   - [Nested data](values.csv)\n\n| [Header data](values.csv) | Value |\n| --- | --- |\n| [Cell data](values.csv) | $x=1$ |\n\n`[Literal data](values.csv)`\n\n```text\n[Fenced data](values.csv)\n```';
  const html = ui.document({ document: bodyDocument(markdown) });
  for (const label of ["Heading data", "Quoted data", "First data", "Nested data", "Header data", "Cell data"]) assert.match(html, new RegExp(`href="/api/v1/retained-values"[^>]*>${label}</a>`));
  assert.match(html, /<code>\[Literal data\]\(values\.csv\)<\/code>/); assert.match(html, /<pre class="record"><code>\[Fenced data\]\(values\.csv\)/);
  assert.match(html, /class="katex"/); assert.match(html, /class="table-scroll" tabindex="0" role="region"/);
  const calls = [];
  const record = { title: "Source fixture", sections: ["[Array data](values.csv)", { algorithm_or_update_rule: [{ order: 1, operation: "[Step data](values.csv)" }], body_md: "[Record data](values.csv)" }] };
  const structured = ui.research({ text: record, renderFileLink: (href, label, readingPath) => { calls.push({ href, label, readingPath }); return label; } });
  assert.match(structured, /Array data/); assert.match(structured, /Step data/); assert.match(structured, /Record data/);
  assert.deepEqual(calls.map(call => call.label).sort(), ["Array data", "Record data", "Step data"]);
  assert.equal(new Set(calls.map(call => call.readingPath)).size, 3);
  assert.ok(calls.every(call => call.href === "values.csv"));
});

test("P5 missing, ambiguous, unverified or unusable report materials stay readable without guessed links", () => {
  const cases = [[], [material, { ...material, artifact_id: "other", artifact_url: "/api/v1/other-values" }], [{ ...material, source_verified: false }], [{ ...material, source_verified: undefined }], [{ ...material, source_error: "Exact data digest mismatch." }], [{ ...material, artifact_url: "https://example.org/values" }], [{ ...material, artifact_url: "javascript:alert(1)" }]];
  for (const materials of cases) {
    const html = ui.document({ document: bodyDocument("[Exact values](values.csv)", materials) });
    assert.match(html, /Exact values:/); assert.doesNotMatch(html, /\[Exact values\]\(values.csv\)/);
    assert.doesNotMatch(html, /href="javascript:|href="https:\/\/example.org\/values"/);
    const bodyLink = /href="[^"]+"[^>]*>Exact values<\/a>/; assert.doesNotMatch(html, bodyLink);
    if (materials.length === 1 && materials[0].source_verified !== true) assert.doesNotMatch(html, /href="\/api\/v1\/retained-values"/);
    if (materials.some(item => item.source_error)) assert.match(html, /Exact data digest mismatch/);
  }
  const unrelated = ui.document({ document: bodyDocument("[Another report's data](other.csv)") });
  assert.match(unrelated, /Another report&#x27;s data: The exact retained file is unavailable/);
});

test("P5 figures use the same unique verified material boundary and keep missing-source notices readable", () => {
  const figure = { ...material, path: "figure.svg", media_type: "image/svg+xml" };
  const current = ui.document({ document: bodyDocument("![Synthetic result](figure.svg)", [figure]) });
  assert.match(current, /<img src="\/api\/v1\/retained-values" alt="Synthetic result"/);
  for (const materials of [[], [figure, { ...figure, artifact_url: "/api/v1/other" }], [{ ...figure, source_verified: false }], [{ ...figure, media_type: "text/csv" }]]) {
    const html = ui.document({ document: bodyDocument("![Synthetic result](figure.svg)", materials) });
    assert.match(html, /Synthetic result: The exact retained figure is unavailable/); assert.doesNotMatch(html, /<img/);
  }
});

test("P5 Source details restore by exact report anchor and the optional hook leaves shared URL rules unchanged elsewhere", () => {
  const html = ui.document({ document });
  const anchor = html.match(/data-reading-anchor="([^"]+:source-details)"/)[1];
  const detail = value => ({ open: false, getAttribute: () => value, querySelector: () => ({ textContent: "Source details" }) });
  const current = detail(anchor), earlier = detail(anchor.replace("report.current", "report.earlier"));
  restoreOpenDisclosures({ querySelectorAll: () => [earlier, current] }, [{ anchor, summary: "Source details" }]);
  assert.equal(current.open, true); assert.equal(earlier.open, false);
  const shared = ui.research({ text: "[Relative data](values.csv) and [Unsafe](javascript:alert) and [Remote](https://example.org/data)." });
  assert.match(shared, /\[Relative data\]\(values.csv\)/); assert.match(shared, /\[Unsafe\]\(javascript:alert\)/);
  assert.match(shared, /href="https:\/\/example.org\/data"/); assert.doesNotMatch(shared, /href="javascript:/);
});

test("P5 Summary states the report conclusion first and owns status, exports and supporting reading", () => {
  const decision = { conclusion: "The report assembles the retained safety theorem and audited synthetic evidence.", headline: "Conditional safety is established; synthetic mixing helped reward.",
    fundamental_contribution: "An exact-real safety theorem with audited numerical evidence.", principal_uncertainty: "The partial-moment search remains mixed.", principal_risk: "Coverage is conditional on the audited regime.",
    material_disagreement: ["The reviewer prefers a wider regime."], smallest_decisive_result: "A complete partial-moment search.", what_changed: "Scientific conclusions are unchanged.",
    generation_ref: { ...ref, family: "decision_record", generation_id: "decision.current", sha256: "b".repeat(64) } };
  const ledger = { kind: "review_issue_ledger", title: "Review issue ledger", body_md: "Two issues remain open.", generation_ref: { ...ref, family: "review_issue_ledger", generation_id: "ledger.current", sha256: "c".repeat(64) } };
  const html = ui.summary({ documents: [document, ledger], decision, methodLabel: "Conditional estimator", onSource() {}, onReadReport() {} });
  assert.match(html, /<section class="card phase-overview report-summary" data-card-role="summary"><div class="card-heading"><h2>Current report conclusion<\/h2>/);
  assert.match(html, /Model: Conditional estimator/);
  assert.match(html, /<dt>Completion<\/dt><dd>Interim report<\/dd>/); assert.match(html, /<dt>Independent review<\/dt><dd>This version has not been independently reviewed/);
  assert.match(html, /Research Lead assessment/);
  assert.match(html, /<div class="phase-overview-headline">[\s\S]*?Conditional safety is established/);
  assert.ok(html.indexOf("Conditional safety is established") < html.indexOf("The report assembles the retained safety theorem"));
  for (const title of ["Contribution", "Main uncertainty", "Main risk or limitation", "Unresolved differences", "What remains to be established"]) assert.match(html, new RegExp(`<h3>${title}</h3>`));
  assert.match(html, /<div class="research-card-actions"[^>]*aria-label="Report actions"><section><h3>Read the report<\/h3><div class="btnrow">/);
  for (const label of ["Report", "Supporting evidence", "Reviews", "Changes"]) assert.match(html, new RegExp(`>${label}<`));
  assert.doesNotMatch(html, />Retained candidates</);
  assert.match(html, /href="\/api\/v1\/report\?view=portable&amp;download=1"[^>]*>[\s\S]*?Download offline HTML/); assert.match(html, /href="\/api\/v1\/report\?view=portable"[^>]*>[\s\S]*?Open HTML report/);
  assert.match(html, /<aside class="research-card-resources"[^>]*aria-label="Report supporting reading">/);
  assert.match(html, /<h3>Supporting reading<\/h3>/); assert.match(html, /Review findings and resolution status/); assert.match(html, /Inspect exact report source/); assert.match(html, /Lead decision source/);
  const reviewsTab = ui.reading({ documents: [document, ledger], initialTab: "reviews", onSource() {} }); assert.match(reviewsTab, /No independent report review has been retained yet/); assert.doesNotMatch(reviewsTab, /Review findings and resolution status|Two issues remain open/);
  assert.match(ui.reading({ documents: [document, ledger], initialTab: "evidence", onSource() {} }), /Review findings and resolution status/);
  assert.match(html, /data-reading-anchor="report-summary:report.current:source-details"/); assert.match(html, /<dt>Model identity<\/dt><dd>method.conditional<\/dd>/); assert.match(html, /<dt>Model version<\/dt><dd>2<\/dd>/);
  assert.doesNotMatch(html, /<h3>Notation<\/h3>|Report tools|report-utility-row/);
});

test("P5 Summary and Changes require matching producing identity and retain their own exact decision source", () => {
  const decision = { conclusion: "Paired conclusion with conditional scope.", what_changed: "The guarantee now requires independent trajectories.",
    generation_ref: { ...ref, family: "decision_record", generation_id: "decision.paired", sha256: "b".repeat(64) } };
  const cases = [
    { name: "matching run and package", report: document, decision, matches: true },
    { name: "matching package without run metadata", report: { ...document, generation_ref: { ...ref, run_id: undefined } }, decision: { ...decision, generation_ref: { ...decision.generation_ref, run_id: undefined } }, matches: true },
    { name: "matching run when account package is unavailable", report: document, decision: { ...decision, generation_ref: { ...decision.generation_ref, package_id: undefined } }, matches: true },
    { name: "different producing run and package", report: document, decision: { ...decision, generation_ref: { ...decision.generation_ref, run_id: "run.other", package_id: "package.other" } } },
    { name: "matching run cannot override conflicting package", report: document, decision: { ...decision, generation_ref: { ...decision.generation_ref, package_id: "package.other" } } },
    { name: "matching package cannot override conflicting run", report: document, decision: { ...decision, generation_ref: { ...decision.generation_ref, run_id: "run.other" } } },
    { name: "conflicting branch", report: document, decision: { ...decision, generation_ref: { ...decision.generation_ref, branch: "method.other" } } },
    { name: "conflicting phase", report: document, decision: { ...decision, generation_ref: { ...decision.generation_ref, phase: "P4" } } },
    { name: "unidentified account", report: document, decision: { ...decision, generation_ref: { ...decision.generation_ref, run_id: undefined, package_id: undefined } } },
    { name: "unidentified report", report: { ...document, generation_ref: { ...ref, run_id: undefined, package_id: undefined } }, decision },
    { name: "missing account", report: document },
  ];
  for (const item of cases) {
    const before = structuredClone(item), opened = [];
    const props = { documents: [item.report], decision: item.decision, onSource: source => opened.push(source) };
    const summary = ui.summary(props), changes = ui.reading({ ...props, initialTab: "changes" });
    if (item.matches) {
      assert.match(summary, /Paired conclusion with conditional scope/, item.name);
      assert.match(changes, /The guarantee now requires independent trajectories/, item.name);
      for (const node of walk(ui.changesTree(props)).filter(node => node.type === ui.sourceRef)) ui.sourceRef(node.props).props.onClick();
      assert.deepEqual(opened, [{ ...item.decision.generation_ref, entry_pointer: "/what_changed" }], item.name);
    } else {
      assert.doesNotMatch(summary, /Paired conclusion|Research Lead assessment|Lead decision source|Lead summary source/, item.name);
      assert.match(summary, /No matching Lead assessment is recorded for this report/, item.name);
      assert.doesNotMatch(changes, /The guarantee now requires|Change account source/, item.name);
      assert.match(changes, /No change account is recorded for this report/, item.name);
    }
    assert.match(summary, /Interim report|Completion not established/, item.name);
    assert.match(summary, /Download offline HTML/, item.name);
    assert.match(summary, /Inspect exact report source/, item.name);
    assert.match(ui.reading(props), /The synthetic ordering is inconclusive; clinical benefit was not assessed/, item.name);
    assert.deepEqual(item, before, item.name);
  }
});

test("P5 Lead-summary fallback follows the same positive report identity rule", () => {
  const lead = { generation_ref: { ...ref, family: "lead_summary", generation_id: "lead.current" }, evaluation_markdown: "The Lead's summary stands in with its qualification." };
  const unrelated = { ...lead, evaluation_markdown: "Unrelated Lead assessment.", generation_ref: { ...lead.generation_ref, package_id: "package.other" } };
  const unidentified = { ...lead, evaluation_markdown: "Unidentified Lead assessment.", generation_ref: undefined };
  const fallback = ui.summary({ documents: [document], summaries: [unrelated, unidentified, lead], onSource() {} });
  assert.match(fallback, /The Lead&#x27;s summary stands in with its qualification/);
  assert.match(fallback, /Lead summary source/);
  assert.doesNotMatch(fallback, /Unrelated Lead assessment|Unidentified Lead assessment|Research Lead assessment/);
  const unmatched = ui.summary({ documents: [document], summaries: [unrelated, unidentified] });
  assert.match(unmatched, /No matching Lead assessment is recorded for this report/);
  assert.doesNotMatch(unmatched, /Unrelated Lead assessment|Unidentified Lead assessment|Lead summary source|Lead decision source/);
});

test("P5 no-report state has one owner and partial supporting documents remain reachable", () => {
  const stale = { conclusion: "A previous report conclusion.", what_changed: "A previous report change.", generation_ref: { ...ref, family: "decision_record", generation_id: "decision.previous" } };
  const limitations = { kind: "limitations_record", title: "Current supporting limitations", body_md: "The available evidence remains conditional.", generation_ref: { ...ref, family: "limitations_record", generation_id: "limitations.current" } };
  for (const documents of [[], [limitations]]) {
    const props = { documents, decision: stale, onSource() {} }, before = structuredClone({ documents, decision: stale });
    assert.equal(ui.summary(props), "");
    const html = ui.summary(props) + ui.reading(props);
    assert.equal((html.match(/No technical report has been assembled for this model yet/g) || []).length, 1);
    assert.doesNotMatch(html, /Current report conclusion|A previous report conclusion|A previous report change/);
    assert.match(html, />Supporting evidence</);
    if (documents.length) assert.match(ui.reading({ ...props, initialTab: "evidence" }), /Current supporting limitations/);
    assert.doesNotMatch(ui.reading({ ...props, initialTab: "changes" }), /A previous report change|Change account source/);
    assert.deepEqual({ documents, decision: stale }, before);
  }
  assert.doesNotMatch(ui.summary({ documents: [{ ...document, portable_artifact_url: undefined }], decision: stale }), /Read the report|Download offline HTML/);
});

test("P5 Report tab keeps the complete report while the Summary owns status and tools once", () => {
  const decision = { conclusion: "The frozen report conclusion.", generation_ref: { ...ref, family: "decision_record", generation_id: "decision.current" } };
  const html = ui.reading({ documents: [document], decision, onSource() {} });
  assert.match(html, /<section class="card technical-report-reader" data-card-role="research" data-reading-anchor="report-reading" tabindex="-1">/);
  assert.match(html, /Technical report and reviews/); assert.match(html, /The synthetic ordering is inconclusive/);
  assert.doesNotMatch(html, /Report tools|Download offline HTML|report-utility-row|Source details|Interim report|Independent review<\/dt>|Historical manuscripts/);
  const candidate = { ...document, kind: "technical_report_candidate", generation_ref: { ...ref, generation_id: "report.candidate", sha256: "d".repeat(64) } };
  const candidates = ui.reading({ documents: [document, candidate], initialTab: "candidates", onSource() {} });
  assert.match(candidates, /Report tools/); assert.match(candidates, /have their own exact sources/);
  const changes = ui.reading({ documents: [document], decision: { ...decision, what_changed: "The appendix adds the conditioning step." }, initialTab: "changes", onSource() {} });
  assert.match(changes, /<h3>What changed<\/h3>/); assert.match(changes, /adds the conditioning step/); assert.match(changes, /Change account source/); assert.doesNotMatch(changes, /<p class="note"><\/p>|No report revision account/);
  assert.match(ui.reading({ documents: [], onSource() {} }), /No technical report has been assembled for this model yet/);
  assert.match(ui.reading({ documents: [document], initialTab: "reviews", onSource() {} }), /No independent report review has been retained yet/);
});
