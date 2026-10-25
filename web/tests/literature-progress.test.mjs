import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { literatureCollections, literatureLibrary, literatureBasis } from "./fixtures/literature-updates.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-literature-progress-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Literature, {LiteratureCoverage, literatureCoverageGroups, LiteratureHistory} from '${src}/components/LiteratureWorkspace.jsx'; import Progress from '${src}/components/ResearchProgress.jsx'; const render = Component => props => renderToStaticMarkup(React.createElement(Component,props)); export const literature=props=>renderToStaticMarkup(<><Literature {...props}/><LiteratureHistory {...props} bases={props.bases || (props.basis ? [{branch:"trunk",phase:"P1",...props.basis}] : [])}/></>); export const coverage=render(LiteratureCoverage); export const progress=render(Progress); export const groups=literatureCoverageGroups;`, resolveDir: src, loader: "jsx" },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const render = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);

test("current package scopes stay together while dated history retains exact sources", () => {
  const before = JSON.stringify(literatureCollections);
  const groups = render.groups(literatureCollections);
  assert.deepEqual(groups.current.map((item) => item.role), ["research_lead", "theorist", "data_analyst"]);
  assert.equal(groups.history.length, 1);
  const html = render.coverage({ collections: literatureCollections, onSource: () => {} });
  const current = html.slice(0, html.indexOf('class="research-details literature-search-history"'));
  assert.match(current, /Published 2026-09-30/); assert.match(current, /Current research_lead search/);
  assert.match(current, /Current theorist search/); assert.match(current, /Current data_analyst search/);
  assert.doesNotMatch(current, /Earlier .* search/); assert.match(html, /Earlier literature update · 2026-09-20/);
  assert.equal((html.match(/Member search record/g) || []).length, 6);
  for (const record of literatureCollections) assert.ok(html.includes(record.generation_ref.generation_id));
  assert.equal(JSON.stringify(literatureCollections), before);
});

test("the cumulative library remains available and bookkeeping stays inside Coverage", () => {
  const html = render.literature({ collections: literatureCollections, libraries: [literatureLibrary], basis: literatureBasis });
  const overview = html.slice(0, html.indexOf('class="card literature-library"'));
  assert.match(overview, /Dependence remains unresolved/); assert.doesNotMatch(overview, /Unique records|Current linked member|found again|literature-statistics/);
  assert.match(html, /Earlier estimator remains relevant/); assert.match(html, /Current paper about constraints/);
  assert.ok(html.indexOf("literature-library-counts") > html.indexOf("Literature accounts, search scopes and review"));
  assert.match(html, /Latest update: 1 new · 0 updated · 1 found again/);
});

test("legacy search scope never gains an invented current package or publication date", () => {
  const legacy = { ...literatureCollections[0], published_at: "", is_current_package: undefined, package_id: undefined,
    generation_ref: { ...literatureCollections[0].generation_ref, package_id: undefined } };
  const html = render.coverage({ collections: [legacy] });
  assert.doesNotMatch(html, /data-coverage-update="current"|Published 2026/);
  assert.match(html, /Update association unverified · publication date unavailable/);
  assert.match(html, /do not establish whether this search belongs to the current package/);
});

test("empty literature has no fabricated history or missing source notice", () => {
  const html = render.literature({});
  assert.match(html, /No papers have been published yet/);
  assert.doesNotMatch(html, /Literature history|Earlier literature update|Earlier and unassociated|exact source|generation|Current linked member/);
});

const active = { run_id: "run.current", phase: "P1", branch_id: "trunk", state: "running", created_at: "2026-09-30T15:00:00Z",
  progress: { stages: [{ stage_id: "p1.discovery", label: "Member literature searches", state: "running", parallel: true,
    member_detail_available: true, received_accounts: 1, total_accounts: 3,
    members: [{ role: "research_lead", label: "Research Lead", state: "received" }, { role: "theorist", label: "Theorist", state: "running" }, { role: "data_analyst", label: "Data Analyst", state: "pending" }] }],
    publication: { label: "Literature update published", state: "pending" } } };

test("common progress distinguishes received accounts, accepted stages and retained research", () => {
  const html = render.progress({ runs: [active], phase: "P1", retained: true, onOpenRun: () => {} });
  assert.match(html, /1 of 3 member reports received/); assert.match(html, /Delivery checks must pass/);
  assert.match(html, /Research Lead: Report received/); assert.match(html, /Theorist: Working/);
  assert.match(html, /Retained results remain available\./); assert.match(html, /Literature update published/);
  assert.doesNotMatch(html, /percent|progressbar|Delivery accepted|Exhaustive|verified/);
  assert.equal((html.match(/role="status"/g) || []).length, 1);
});

test("an explanation cannot replace a failed scientific update in common progress", () => {
  const failed = { ...active, state: "failed", progress: undefined };
  const explanation = { ...active, run_id: "run.explanation", created_at: "2026-10-01T10:00:00Z", intent: "assessment", assessment_purpose: "explanation" };
  const html = render.progress({ runs: [failed, explanation], phase: "P1", retained: true });
  assert.match(html, /The latest update failed/); assert.match(html, /did not replace the retained results/);
  assert.doesNotMatch(html, /Theorist: Working|1 of 3/);
});

test("P3 startup failure reports failed work without inventing a rejected delivery", () => {
  // Rendering fields from the retained DRBP startup failure on 2026-10-22.
  const run = { run_id: "run.p3.p3.theory_revision.37d64c2a0327a9b480c1994e375e9023", phase: "P3", mode: "p3.theory_revision",
    branch_id: "method.dual-reference-belief-planning", state: "failed", thread_ids: {},
    terminal_reason: "Codex could not apply this member's execution settings or resume its thread.",
    progress: { stages: [
      { stage_id: "p3.theorist", label: "Theory development", state: "failed", parallel: false, member_detail_available: false, members: [], received_accounts: null, total_accounts: 1 },
      { stage_id: "p3.analyst", label: "Analyst audit", state: "pending", parallel: false, member_detail_available: false, members: [], received_accounts: null, total_accounts: 1 },
      { stage_id: "p3.lead", label: "Lead synthesis", state: "pending", parallel: false, member_detail_available: false, members: [], received_accounts: null, total_accounts: 1 },
    ], publication: { label: "Theory account published", state: "pending" } } };
  const html = render.progress({ run, phase: "P3", retained: true });
  assert.match(html, /<strong>Theory development<\/strong><span class="note">Work failed<\/span>/);
  assert.match(html, /<strong>Analyst audit<\/strong><span class="note">Not started<\/span>/);
  assert.match(html, /This attempt did not replace the retained results\./);
  assert.doesNotMatch(html, /Delivery not accepted|Delivery accepted|Report received|member reports received/);
});

test("accepted historical stages retain acceptance without implying missing member deliveries", () => {
  const run = { ...active, state: "published", progress: { stages: [{
    stage_id: "p1.discovery", label: "Member literature searches", state: "succeeded", parallel: true,
    member_detail_available: false, received_accounts: null, total_accounts: 3, members: [],
  }], publication: { label: "Literature update published", state: "completed" } } };
  const html = render.progress({ run, phase: "P1", retained: true });
  assert.match(html, /Delivery accepted/);
  assert.match(html, /Complete member report details are unavailable for this stage/);
  assert.match(html, /Literature update published/);
  assert.doesNotMatch(html, /of 3 member reports received|Delivery checks must pass|Theorist:|Data Analyst:/);
});

test("setup failures ask for configuration correction in the shared progress view", () => {
  const run = { ...active, phase: "P4", state: "awaiting_user", p4_progress: { attention_kind: "setup" },
    progress: { stages: [{ stage_id: "p4.analyst", label: "Protocol and empirical work", state: "awaiting_user",
      member_detail_available: true, members: [{ role: "data_analyst", label: "Data Analyst", state: "awaiting_user" }] }] } };
  const html = render.progress({ run, phase: "P4", retained: true });
  assert.match(html, /Experiment setup needs attention/);
  assert.match(html, /Data Analyst: Waiting for setup correction/);
  assert.doesNotMatch(html, /Waiting for your direction/);
});
