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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-issue-citations-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Issues from '${src}/components/IssuesCard.jsx'; import Empirical from '${src}/components/EmpiricalWorkbench.jsx'; import {ResearcherDecisions} from '${src}/components/ContextualRequests.jsx'; import {CitedRequestDocument} from '${src}/components/LiteratureCitation.jsx'; export const issues = props => renderToStaticMarkup(<Issues {...props}/>); export const decisions = props => renderToStaticMarkup(<ResearcherDecisions {...props}/>); export const p4 = ({issueProps, ...props}) => renderToStaticMarkup(<Empirical {...props} issues={<Issues {...issueProps}/>}/>); export const openCitation = (props, citation) => CitedRequestDocument(props).props.onOpenCitation(citation);`, resolveDir: src, loader: "jsx" }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

const exact = { branch: "trunk", phase: "P1", family: "literature_library", generation_id: "gen.old", sha256: "a".repeat(64), run_id: "run.old", package_id: "package.old", entry_pointer: "/sources/0/assessments/0/entry" };
const citation = { source_id: "source.shared", status: "available", entry_ref: { role: "research_lead", family: "lead_literature", run_id: "run.old", entry_id: "entry.old", entry_sha256: "b".repeat(64) }, bibliography: { title: "Original cited paper" }, card: { generation_ref: exact, entry_pointer: exact.entry_pointer } };
const question = { issue_id: "attention.observation", attention_id: "attention.observation", attention_version_id: "attention.observation.v3", branch: "method.a", phase: "P3", target_phase: "P1", kind: "researcher_decision", disposition: "open", question: "Which observations are available?", context_markdown: "Use $x_t$ as described by [Original author](#cite:source.shared) and [Missing author](#cite:source.missing).", likely_consequence: "See [Original author](#cite:source.shared).", citations: [citation] };
const props = { projectId: "project.current", phase: "P3", branch: "method.a" };
const visibleText = html => html.replace(/<[^>]*>/g, "");

test("carried question context uses existing blue citation controls and explicit unavailable references", () => {
  const before = JSON.stringify(question);
  const html = render.issues({ ...props, issues: [question] });
  assert.equal((html.match(/class="inline-citation"/g) || []).length, 2);
  assert.match(html, /Original author\. Read the exact cited paper assessment/);
  assert.match(html, /class="citation-unavailable"[^>]*>Missing author/);
  assert.match(html, /reference unavailable/);
  assert.doesNotMatch(visibleText(html), /#cite:|\[Original author\]/);
  assert.doesNotMatch(html, /katex-error/);
  assert.match(html, /class="katex"/);
  assert.equal(JSON.stringify(question), before);
});

test("citation opens its original retained generation and entry without current-source lookup", () => {
  let opened;
  render.openCitation({ item: question, onSource: target => { opened = target; } }, citation);
  assert.deepEqual(opened, exact);
});

test("question-only citations stay actionable in details while the full question appears once in its summary", () => {
  const item = { ...question, title: "Observation design and retained source identity", context_markdown: "The original observation context.", likely_consequence: undefined, question: "Can [Original author](#cite:source.shared) or [Missing author](#cite:source.missing) establish the observation design?" };
  const before = structuredClone(item), html = render.issues({ ...props, issues: [item] });
  const summary = html.match(/class="issue-row-summary"[^>]*>([\s\S]*?)<\/summary>/)[1];
  assert.match(summary, /Can Original author or Missing author establish the observation design\?/);
  assert.doesNotMatch(summary, /<a\b|<button\b|<p\b|#cite:/);
  assert.equal((visibleText(html).match(/establish the observation design\?/g) || []).length, 1);
  assert.equal((html.match(/class="inline-citation"/g) || []).length, 1);
  assert.match(html, /Question sources/);
  assert.match(html, /class="citation-unavailable"[^>]*>Missing author/);
  assert.ok(html.indexOf('class="inline-citation"') > html.indexOf("Context and sources"));
  assert.ok(html.includes('citation:unpublished:request:attention.observation.v3:question-sources:'));
  assert.deepEqual(item, before);
});

test("external question sources remain links outside the summary, while math and code stay opaque", () => {
  const item = { ...question, context_markdown: undefined, likely_consequence: undefined, question: "Does [the schedule](https://example.test/schedule) match `$x$ [an example](#cite:code)` and $[x](#cite:math)$?" };
  const html = render.issues({ ...props, issues: [item] });
  const summary = html.match(/class="issue-row-summary"[^>]*>([\s\S]*?)<\/summary>/)[1];
  assert.doesNotMatch(summary, /<a\b|<button\b/);
  assert.match(html, /href="https:\/\/example.test\/schedule"/);
  assert.doesNotMatch(html, /inline-citation|citation-unavailable/);
});

test("unprojected references remain visibly unavailable instead of literal Markdown", () => {
  const html = render.issues({ ...props, issues: [{ ...question, citations: undefined }] });
  assert.doesNotMatch(html, /inline-citation/);
  assert.doesNotMatch(visibleText(html), /#cite:/);
  assert.equal((html.match(/reference unavailable/g) || []).length, 3);
});

test("legacy contextual request uses the same exact citation renderer", () => {
  const html = render.decisions({ ...props, items: [{ ...question, target_phase: "P3" }], answers: [] });
  assert.equal((html.match(/class="inline-citation"/g) || []).length, 2);
  assert.match(html, /reference unavailable/);
  assert.doesNotMatch(visibleText(html), /#cite:/);
  assert.doesNotMatch(html, /katex-error/);
});

test("question scope keeps other model citations out of this branch", () => {
  const html = render.issues({ ...props, issues: [{ ...question, branch: "method.other" }] });
  assert.doesNotMatch(html, /inline-citation|Original author|Missing author/);
});

test("P4 question context resolves current run sources beside unchanged blue P1 citations", () => {
  const runId = "run.p4.current"; const digest = "c".repeat(64);
  const analyst = { branch: "method.a", phase: "P4", family: "analyst_synthesis", generation_id: "analysis.current", sha256: digest, run_id: runId, package_id: "package.p4" };
  const uri = `run://${runId}/analyst_synthesis.json`;
  const issue = { ...question, phase: "P4", likely_consequence: `${question.likely_consequence} P4 synthetic consequence: [test.censoring](${uri}#/question_results/6). See [missing current source](run://${runId}/missing.json).` };
  const reader = { branch: "method.a", summaries: [{ branch: "method.a", generation_ref: { ...analyst, family: "empirical_synthesis", generation_id: "lead.current", sha256: "d".repeat(64) }, source_artifacts: [{ uri, sha256: digest }], decision_summary: { implementation_markdown: "Reviewed synthetic evidence." } }], questions: [{ branch: "method.a", question_id: "test.censoring", title: "Censoring test", category: "sensitivity", generation_ref: analyst, result: { generation_ref: analyst, category: "sensitivity" } }], issueProps: { ...props, phase: "P4", issues: [issue], onSource() {} } };
  const before = JSON.stringify(reader);
  const html = render.p4(reader);
  assert.equal((html.match(/class="inline-citation"/g) || []).length, 2);
  assert.match(html, /Original author\. Read the exact cited paper assessment/);
  assert.match(html, /title="Analyst synthesis · analysis\.current"[^>]*>[\s\S]*?test\.censoring<\/button>/);
  assert.match(html, /missing current source \(source unavailable\)/);
  assert.doesNotMatch(visibleText(html), /#cite:|\[test\.censoring\]\(|\[Original author\]|run:\/\//);
  assert.doesNotMatch(html, /katex-error/);
  assert.equal(JSON.stringify(reader), before);
});
