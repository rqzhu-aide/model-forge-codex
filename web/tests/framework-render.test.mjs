import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { frameworkBasis, frameworkSources } from "./fixtures/framework-landscape.mjs";
import { selectLandscapeRecord } from "../src/literatureLandscape.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-framework-render-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({
  stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Literature, {SelectedPaper, LiteratureHistory} from '${src}/components/LiteratureWorkspace.jsx'; import Frameworks, {LandscapeRecord} from '${src}/components/FrameworkLandscape.jsx'; const render = Component => props => renderToStaticMarkup(React.createElement(Component, props)); export const literature = props => renderToStaticMarkup(<><Literature {...props}/><LiteratureHistory {...props} bases={props.bases || (props.basis ? [{branch:"trunk",phase:"P1",...props.basis}] : [])}/></>); export const paper = render(SelectedPaper); export const frameworks = render(Frameworks); export const record = render(LandscapeRecord);`, resolveDir: src, loader: "jsx" },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent",
});
const render = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};

test("main findings embeds the detailed map without another primary card", () => {
  const before = JSON.stringify([frameworkBasis, frameworkSources]);
  const html = render.literature({ basis: frameworkBasis, libraries: [{ branch: "trunk", phase: "P1", total_sources: 1, sources: frameworkSources }], onSource: noop });
  assert.match(html, /Unique record identified<\/dt><dd class="literature-count-value">1<\/dd>/);
  assert.match(html, /Current linked member assessments<\/dt><dd class="literature-count-value">2<\/dd>/);
  assert.match(html, /<section class="framework-landscape embedded-science" data-card-role="research" aria-labelledby="[^"]+">/);
  assert.match(html, /<h3 id="[^"]+">Frameworks and relationships<\/h3>/);
  assert.match(html, /Explore a framework or relationship/);
  assert.match(html, /<optgroup label="Frameworks \(2\)">/);
  assert.match(html, /role="button" tabindex="0" aria-label="Framework: Expected discounted cost" aria-pressed="false"/);
  assert.match(html, /role="button" tabindex="0" aria-label="Relationship 1: Overrun gives a shifted expected-cost bound"/);
  assert.match(html, /Variants \(1\)/);
  assert.match(html, /Existing algorithm families \(1\)/);
  assert.doesNotMatch(html, /class="framework-list"|class="framework-inspector"|class="literature-entry selected-paper"/);
  assert.match(html, /Find a paper or research idea/);
  assert.ok(html.indexOf("framework-landscape") < html.indexOf("literature-controls"));
  assert.match(html, /What the Lead checked/);
  assert.match(html, /Other claims were not checked/);
  assert.equal(JSON.stringify([frameworkBasis, frameworkSources]), before);
});

test("controlled selections open only the requested record and never fall back to a different formulation", () => {
  const props = { basis: frameworkBasis, sources: frameworkSources, onEvidence: noop, onSelect: noop, focusRef: { current: null } };
  const selected = render.frameworks({ ...props, selectedId: "relationship.bound" });
  assert.match(selected, /aria-label="Relationship 1: Overrun gives a shifted expected-cost bound" aria-pressed="true"/);
  assert.match(selected, /<option value="relationship.bound" selected="">/);
  assert.match(selected, /class="framework-inspector" tabindex="-1" aria-label="Selected relationship"/);
  assert.match(selected, /Mathematical relationship/);
  assert.match(selected, /class="katex/);
  assert.doesNotMatch(selected, /scientific-review-scope/);
  for (const selectedId of ["", "framework.unavailable"]) {
    const unselected = render.frameworks({ ...props, selectedId });
    assert.doesNotMatch(unselected, /class="framework-inspector"|aria-pressed="true"/);
    assert.match(unselected, /Select a map item or use the dropdown/);
  }
});

test("relationship and variant selection display exact mathematical differences, conditions and consequences", () => {
  const common = { landscape: frameworkBasis.landscape, sources: frameworkSources, review: frameworkBasis.scientific_review, onSelect: noop, onEvidence: noop };
  const html = render.record({ ...common, selection: selectLandscapeRecord(frameworkBasis.landscape, "relationship.bound") });
  assert.match(html, /Mathematical relationship/);
  assert.match(html, /Conditions/);
  assert.match(html, /same admissible policy/);
  assert.match(html, /shifted threshold/);
  assert.match(html, /Supporting paper entries/);
  assert.match(html, /<details class="research-details framework-evidence"><summary>Supporting paper entries/);
  assert.match(html, /Fixture paper on budget criteria/);
  assert.match(html, /Earlier entry version/);
  assert.match(html, /Partial source support/);
  assert.doesNotMatch(html, /Mathematical formulation<\/h4>/);
  const variant = render.record({ ...common, selection: selectLandscapeRecord(frameworkBasis.landscape, "variant.zero") });
  assert.match(variant, /What changes mathematically/);
  assert.match(variant, /Consequences/);
  assert.match(variant, /almost surely/);
  const algorithm = render.record({ ...common, selection: selectLandscapeRecord(frameworkBasis.landscape, "algorithm.trajectory") });
  assert.match(algorithm, /Existing algorithm family/);
  assert.match(algorithm, /Information and computational requirements/);
  assert.match(algorithm, /explicit discounted-tail approximation/);
});

test("algorithm comparison endpoints appear as algorithm families rather than research frameworks", () => {
  const basis = structuredClone(frameworkBasis);
  basis.landscape.relationships[0].from_id = "algorithm.trajectory";
  const html = render.frameworks({ basis, sources: frameworkSources, onEvidence: noop });
  assert.match(html, /aria-label="Existing algorithm family: Trajectory primal-dual family"/);
  assert.match(html, /ALGORITHM FAMILY/);
  assert.doesNotMatch(html, /aria-label="Framework: Trajectory primal-dual family"/);
});

test("current corrected paper text has original author and lead attribution, with original submissions in collapsed history", () => {
  const html = render.paper({ source: frameworkSources[0], review: frameworkBasis.scientific_review, onSource: noop });
  assert.match(html, /Originally authored by Theorist · Revised by Research Lead/);
  assert.match(html, /Current lead-corrected fixture entry/);
  assert.match(html, /Lead correction record/);
  assert.match(html, /<details class="research-details"><summary>Original submissions, revision history and search provenance/);
  assert.match(html, /Original fixture submission, preserved unchanged/);
  assert.match(html, /Correction recorded · Earlier entry version/);
  assert.doesNotMatch(html, /Independent analyst fixture formulation/);
});

test("unavailable evidence versions are explicit and older topic publications gain no invented scientific review", () => {
  const selection = structuredClone(selectLandscapeRecord(frameworkBasis.landscape, "framework.expected"));
  selection.record.entry_refs[0].entry_sha256 = "unavailable.version";
  const html = render.record({ selection, landscape: frameworkBasis.landscape, sources: frameworkSources, onEvidence: noop });
  assert.match(html, /exact supporting entry is unavailable/);
  assert.doesNotMatch(html, /Fixture paper on budget criteria/);
  const legacy = render.literature({ basis: { landscape: { topics: [{ topic_id: "topic.legacy", title: "Earlier research direction" }] } } });
  assert.match(legacy, /Earlier research direction/);
  assert.match(legacy, /No framework map has been published yet/);
  assert.doesNotMatch(legacy, /Lead&#x27;s source assessment|What the lead checked/);
  const empty = render.frameworks({ basis: { landscape: {}, scientific_review: frameworkBasis.scientific_review } });
  assert.match(empty, /<section class="card framework-landscape" data-card-role="research" aria-labelledby="[^"]+">/);
  assert.match(empty, /<h2 id="[^"]+">Frameworks and relationships<\/h2>/);
  assert.match(empty, /No framework map has been published yet/);
  assert.doesNotMatch(empty, /Other claims were not checked|class="framework-inspector"/);
});
