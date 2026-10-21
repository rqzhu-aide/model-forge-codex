import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { normalizeReader } from "../src/readingPosition.js";
import { mathSegments, validateMathText } from "../src/researchMath.js";

const require = createRequire(import.meta.url);
const katex = require(sharedPackage("katex"));
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-p1-cards-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import PhaseOne from '${src}/components/PhaseOneWorkspace.jsx'; import Literature, {SelectedPaper} from '${src}/components/LiteratureWorkspace.jsx'; import {CitedResearchDocument} from '${src}/components/LiteratureCitation.jsx'; import {MathText,ResearchDocument} from '${src}/components/Shared.jsx'; const render = C => props => renderToStaticMarkup(React.createElement(C,props)); export const phase=render(PhaseOne); export const literature=render(Literature); export const paper=render(SelectedPaper); export const math=render(MathText); export const cited=render(CitedResearchDocument); export const repeatedChildPaths = text => { const calls=[]; const props={text,renderInternalLink:(href,label,occurrence)=>{calls.push({href,label,occurrence}); return label;}}; renderToStaticMarkup(React.createElement(ResearchDocument,props)); const first=calls.splice(0); renderToStaticMarkup(React.createElement(ResearchDocument,props)); return [first,calls]; };`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const reference = { role: "theorist", family: "theory_literature", run_id: "run.first", entry_id: "entry.first", entry_sha256: "a".repeat(64) };
const bibliography = { source_id: "source.first", title: "Original formulation", authors: ["Original Author"], year: 2020, venue: "Original journal", identifiers: [{ kind: "doi", value: "10.1234/original" }] };
const exactCard = { ...reference, source: bibliography, formulation_markdown: "Exact original mathematics.", explanation_markdown: "Original contribution." };
const basis = { generation_ref: { generation_id: "basis.first" }, research_setting: { statement_markdown: "$$Y_i=f(X_i)+\\epsilon_i$$", component_interpretations: [{ symbol_latex: "Y_i", mathematical_role_markdown: "Observed outcome.", problem_meaning_markdown: "The researcher's response measurement." }], research_goal_markdown: "Develop a model and technical report." }, landscape: { summary_markdown: "The literature defines an estimation problem [Author, 2020](#cite:source.first).", overview_item_ids: ["framework.first"], frameworks: [{ framework_id: "framework.first", title: "Moment estimation", formulation_markdown: "$$E[m(W,\\theta)]=0$$", project_relevance: "direct", relevance_reason_markdown: "Closely matches the requested quantity.", support_status: "source_supported", limitations: ["Collection mechanism remains unknown."] }], common_assumptions: [{ assumption_id: "assumption.a", title: "Sampling independence", statement_markdown: "Independent observations are assumed.", project_fit_markdown: "Unknown for the available data.", landscape_item_ids: ["framework.first"], citation_ids: ["source.first"] }] }, citations: [{ source_id: "source.first", canonical_source_id: "canonical.first", entry_ref: reference, status: "available", bibliography, card: exactCard }] };

test("compact setting keeps notation on demand and interpreted goal before cited findings", () => {
  const before = JSON.stringify(basis);
  const html = render.phase({ project: { name: "Project title already shown in the page header", research_instructions: "Research brief" }, basis: { ...basis, catalog_pin: {catalog_version:"1.23.0",catalog_manifest_sha256:"a".repeat(64)} }, artifacts: {}, onGoal: () => {} });
  for (const text of ["Research Setting", "Notation", "Study goal", "Correct or discuss", "Main Findings", "Common assumptions", "Explore Individual Papers"]) assert.ok(html.includes(text), text);
  assert.ok(html.indexOf("Study goal") < html.indexOf("Main Findings"));
  assert.ok(html.indexOf("Main Findings") < html.indexOf("Explore Individual Papers"));
  assert.match(html, /relevance-direct/); assert.match(html, /Closely related/);
  assert.match(html, /Unknown for the available data/); assert.match(html, /class="inline-citation"/);
  assert.doesNotMatch(html, /Project title already shown in the page header|setting-project-title/);
  const settingLabel = html.match(/<section class="card research-setting"[^>]*aria-labelledby="([^"]+)"/)?.[1];
  assert.ok(settingLabel);
  assert.ok(html.includes(`<h2 id="${settingLabel}">Research Setting</h2>`), "The card keeps its accessible heading after removing the repeated project title.");
  assert.doesNotMatch(html, /Meaning in your problem or data|Mathematical role/); assert.doesNotMatch(html, /katex-error|role="tablist"|#cite:source/);
  assert.equal(JSON.stringify(basis), before);
});

// Remove closed disclosures, including nested ones, before checking first-view math.
function outsideClosedDetails(html) {
  const opened = []; let result = "", start = 0;
  for (const tag of html.matchAll(/<\/?details\b[^>]*>/g)) {
    if (opened.every(Boolean)) result += html.slice(start, tag.index);
    if (tag[0].startsWith("</")) opened.pop();
    else opened.push(/\bopen(?:\s|=|>)/.test(tag[0]));
    start = tag.index + tag[0].length;
  }
  assert.equal(opened.length, 0, "balanced rendered disclosures");
  if (opened.every(Boolean)) result += html.slice(start);
  return result;
}

function passageBetween(html, start, end) {
  const from = html.indexOf(start), to = html.indexOf(end, from + start.length);
  assert.ok(from >= 0 && to > from, `visible passage: ${start}`);
  return html.slice(from, to);
}

test("current catalog examples keep authored mathematics visible without changing authored content", () => {
  const load = (name) => JSON.parse(fs.readFileSync(new URL(`../../contracts/${name}`, import.meta.url), "utf8"));
  const examples = { basis: load("examples/research-basis.example.json"), literature: load("examples/literature-findings.example.json"), pin: load("catalog-pin.json") };
  const snapshot = JSON.parse(fs.readFileSync(new URL("./fixtures/p1-visible-math-preview.json", import.meta.url), "utf8"));
  assert.deepEqual(snapshot.research_basis, examples.basis, "browser fixture preserves the current basis example");
  assert.deepEqual(snapshot.literature_findings, examples.literature, "browser fixture preserves the current literature example");
  assert.deepEqual(snapshot.catalog_pin, examples.pin, "browser fixture uses the current catalog pin");
  for (const [source, digest] of Object.entries(snapshot.source_sha256)) assert.equal(createHash("sha256").update(fs.readFileSync(new URL(`../../${source}`, import.meta.url))).digest("hex"), digest, `browser snapshot provenance: ${source}`);
  const before = JSON.stringify(examples);
  const currentBasis = { ...examples.basis, catalog_pin: examples.pin };
  const phaseProps = { project: { name: "Illustrative catalog example", research_instructions: "Local rendering validation." }, basis: currentBasis, artifacts: {} };
  const phaseHtml = render.phase(phaseProps), visible = outsideClosedDetails(phaseHtml);
  const assertAuthoredMath = (text, html, label) => {
    assert.deepEqual(validateMathText(katex, text), [], `${label}: valid authored math`);
    for (const { latex, display } of mathSegments(text)) {
      assert.ok(html.includes(render.math({ latex, display })), `${label}: exact authored ${display ? "display" : "inline"} mathematics visible outside closed details`);
    }
  };
  const goal = 'class="scientific-passage research-goal"', findings = 'data-reading-anchor="main-findings"', papers = 'data-reading-anchor="explore-papers"';
  assertAuthoredMath(currentBasis.research_setting.statement_markdown, passageBetween(visible, 'data-reading-anchor="research-setting"', goal), "study description");
  assertAuthoredMath(currentBasis.research_setting.research_goal_markdown, passageBetween(visible, goal, findings), "study goal");
  const selected = currentBasis.landscape.overview_item_ids;
  assertAuthoredMath(currentBasis.landscape.summary_markdown, passageBetween(visible, findings, selected.length ? "<h3>Relevant approaches</h3>" : papers), "thematic findings");
  const records = ["frameworks", "variants", "relationships", "algorithm_families"].flatMap((key) => currentBasis.landscape[key] || []);
  for (const [index, id] of selected.entries()) {
    const record = records.find((item) => Object.entries(item).some(([key, value]) => key.endsWith("_id") && value === id));
    assert.ok(record, `selected catalog approach ${id}`);
    assertAuthoredMath(record.explanation_markdown, passageBetween(visible, `data-reading-anchor="approach:${id}"`, selected[index + 1] ? `data-reading-anchor="approach:${selected[index + 1]}"` : papers), `selected approach ${id}`);
  }
  for (const paper of examples.literature.papers) {
    const card = { ...paper, catalog_pin: examples.pin };
    const paperHtml = render.paper({ source: { ...paper.source, cards: [card] } });
    assertAuthoredMath(paper.explanation_markdown, outsideClosedDetails(paperHtml), `paper ${paper.entry_id}`);
    assert.doesNotMatch(paperHtml, /katex-error/);
    const earlier = outsideClosedDetails(render.paper({ source: { ...paper.source, cards: [{ ...card, catalog_pin: { ...examples.pin, catalog_version: "1.22.0" } }] } }));
    for (const { latex } of mathSegments(paper.explanation_markdown).filter((segment) => segment.display)) assert.ok(!earlier.includes(render.math({ latex, display: true })), "earlier paper retains its disclosure policy");
  }
  assert.doesNotMatch(phaseHtml, /katex-error/);
  assert.equal(JSON.stringify(examples), before, "rendering leaves the original examples unchanged");
});

test("historical primary paper uses the exact bibliography and assessment", () => {
  const html = render.paper({ source: { source_id: "canonical.first", title: "Changed title", authors: ["Later Author"], year: 2026, cards: [{ ...exactCard, source: { ...bibliography, title: "Changed title" }, formulation_markdown: "Later mathematics" }] }, initialSelection: { exactCard } });
  assert.match(html, /Original formulation/); assert.match(html, /Original Author · 2020 · Original journal/);
  assert.match(html, /Exact original mathematics/); assert.doesNotMatch(html, /Changed title|Later Author|Later mathematics/);
});

test("missing exact targets retain a visible warning without replacing them with a current assessment", () => {
  const html = render.literature({ libraries: [{ branch: "trunk", phase: "P1", sources: [{ source_id: "canonical.first", title: "Selectable current record", cards: [exactCard] }] }], reading: { paperId: "canonical.first", entrySelection: { sourceId: "canonical.first", reference: { ...reference, entry_sha256: "b".repeat(64) } }, origin: { kind: "citation", id: "source.first", title: "Author, 2020" } } });
  assert.match(html, /The exact referenced assessment is unavailable/); assert.match(html, /Back to Author, 2020/); assert.doesNotMatch(html, /Exact original mathematics/);
});

test("nested citation rendering and missing bindings remain readable", () => {
  const html = render.cited({ text: ["One [Author, 2020](#cite:source.first).", "Two [Missing](#cite:missing)."], basis, section: "nested" });
  assert.match(html, /class="inline-citation"/); assert.match(html, /reference unavailable/); assert.doesNotMatch(html, /#cite:/);
});

test("citation occurrences stay distinct and stable when a child document renders again", () => {
  const text = ["First [Author](#cite:source.first). Again [Author](#cite:source.first).\n\n> Quoted [Author](#cite:source.first).\n\n- Listed [Author](#cite:source.first).\n\n| Source | Detail |\n| --- | --- |\n| [Author](#cite:source.first) | row |", "Another [Author](#cite:source.first)."];
  const [first, second] = render.repeatedChildPaths(text);
  assert.equal(first.length, 6);
  assert.deepEqual(second, first);
  assert.ok(first.every(item => typeof item.occurrence === "string"));
  assert.equal(new Set(first.map(item => item.occurrence)).size, first.length);
  const html = render.cited({ text, basis, section: "repeat" });
  const anchors = [...html.matchAll(/data-reading-anchor="([^"]+)"/g)].map(match => match[1]);
  assert.equal(anchors.length, 6);
  assert.equal(new Set(anchors).size, anchors.length);
  assert.deepEqual([...render.cited({ text, basis, section: "repeat" }).matchAll(/data-reading-anchor="([^"]+)"/g)].map(match => match[1]), anchors);
});

test("saved citations follow retained canonical aliases and never fall back when their basis is missing", () => {
  const sources = [{ source_id: "canonical.merged", source_ids: ["canonical.merged", "canonical.first"], title: "Current merged source", cards: [exactCard] }];
  const reading = { paperId: "canonical.first", entrySelection: { sourceId: "canonical.first", reference, citationBasisId: "basis.first" }, origin: { kind: "citation", id: "source.first", title: "Author" } };
  const props = { basis, libraries: [{ branch: "trunk", phase: "P1", sources }], reading };
  assert.match(render.literature(props), /Selected paper: Original formulation/);
  const missing = render.literature({ ...props, reading: { ...reading, entrySelection: { ...reading.entrySelection, citationBasisId: "basis.unavailable" } } });
  assert.match(missing, /The exact referenced assessment is unavailable/); assert.doesNotMatch(missing, /Exact original mathematics/);
  const absentId = render.literature({ ...props, reading: { ...reading, entrySelection: { sourceId: "canonical.first", reference } } });
  assert.match(absentId, /The exact referenced assessment is unavailable/);
});

test("citation return origin and exact basis survive reading-state serialization", () => {
  const saved = normalizeReader({ entrySelection: { sourceId: "canonical.first", reference, citationBasisId: "basis.first" }, origin: { kind: "citation", id: "source.first", title: "Author", anchor: "citation:basis.first:summary:0", position: { y: 512, offset: 40, anchor: { kind: "data-reading-anchor", value: "main-findings" }, disclosures: [] } } }, "P1");
  assert.equal(saved.entrySelection.citationBasisId, "basis.first");
  assert.equal(saved.origin.anchor, "citation:basis.first:summary:0");
  assert.equal(saved.origin.position.y, 512); assert.equal(saved.origin.kind, "citation");
  assert.deepEqual(normalizeReader({ origin: { id: "framework.a", title: "Framework" } }, "P1").origin, { id: "framework.a", title: "Framework" });
});
