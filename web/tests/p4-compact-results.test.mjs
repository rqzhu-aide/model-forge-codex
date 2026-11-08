import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { empiricalExhibitPreview, empiricalExhibitSize, primaryEmpiricalExhibits } from "../src/compactEmpiricalResults.js";
import { exhibitKey, routeEmpiricalExhibits } from "../src/empirical.js";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-compact-results-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server';
 export {default as Workbench} from '${src}/components/EmpiricalWorkbench.jsx';
 export {default as Compact} from '${src}/components/CompactEmpiricalExhibit.jsx';
 export {default as Table,artifactTablePage} from '${src}/components/ArtifactTable.jsx';
 export {tableReadings} from '${src}/tableReading.js';
 export {default as EmpiricalReadingButton,empiricalReadingSnapshot} from '${src}/components/EmpiricalReading.jsx';
 export {ActionButton} from '${src}/components/Visuals.jsx';
 export const render=(Component,props)=>renderToStaticMarkup(React.createElement(Component,props));
 export const renderElement=renderToStaticMarkup; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" }, alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const nodes = tree => Array.isArray(tree) ? tree.flatMap(nodes) : tree?.props ? [tree, ...nodes(tree.props.children)] : [];
const ref = { branch: "method.example", phase: "P4", run_id: "run.example", package_id: "package.example", family: "exhibits", generation_id: "generation.example", sha256: "a".repeat(64) };
const table = (id, columns, rows) => ({ exhibit_id: id, title: `Saved ${id}`, branch: ref.branch, phase: "P4", generation_ref: ref, source_verified: true, artifact_sha256: "b".repeat(64), table: { columns: columns.map(key => ({ key, label: key === "effect_difference" ? "$J_R(\\pi)-J_R(\\pi_0)$" : key })), rows } });
const paired = table("opaque.a", ["condition", "Contrast", "effect_difference", "MCSE", "n_pairs"], Array.from({ length: 36 }, (_, i) => ({ condition: `Condition ${Math.floor(i / 3)}`, Contrast: ["Mixture versus singleton", "Other comparison", "Another comparison"][i % 3], effect_difference: i === 0 ? "undefined: no joint selection" : i / 100, MCSE: i === 0 ? "unavailable: fewer than two pairs" : 0.004, n_pairs: i === 0 ? 0 : 40 })));
const previous = table("opaque.b", ["Condition", "Study", "Selected", "Mean"], Array.from({ length: 12 }, (_, i) => ({ Condition: `Condition ${Math.floor(i / 2)}`, Study: i % 2 ? "Prior published study" : "Fresh rerun", Selected: i < 2 ? "0/40" : "40/40", Mean: i < 2 ? "undefined: no selected dataset" : i / 10 })));
const check = table("opaque.c", ["Check", "Outcome"], Array.from({ length: 48 }, (_, i) => ({ Check: `Check ${i}`, Outcome: "Agrees within recorded tolerance" })));
const ordinary = table("opaque.d", ["Method", "Mean"], [{ Method: "Primary", Mean: 0 }, { Method: "Comparator", Mean: null }]);
const coverage = [{ dimension: "performance", status: "partial", exhibit_ids: [ordinary.exhibit_id, paired.exhibit_id, previous.exhibit_id], summary: "The comparison remains conditional on the recorded datasets." }, { dimension: "implementation", status: "assessed", exhibit_ids: [check.exhibit_id], summary: "The retained implementation checks agree." }];
const summary = { generation_ref: { ...ref, family: "empirical_synthesis" }, decision_summary: { coverage, headline_exhibit_ids: [check.exhibit_id, ordinary.exhibit_id, paired.exhibit_id, previous.exhibit_id] } };

test("primary displays use exact topic associations and column roles, independent of titles and IDs", () => {
  const exhibits = [check, ordinary, paired, previous], before = structuredClone(exhibits);
  const routed = routeEmpiricalExhibits(exhibits, [], coverage, summary);
  assert.deepEqual(primaryEmpiricalExhibits(routed, summary).map(entry => entry.key), [exhibitKey(paired), exhibitKey(previous)]);
  assert.deepEqual(primaryEmpiricalExhibits(routed.map(entry => ({ ...entry, exhibit: { ...entry.exhibit, title: "Finite implementation checks" } })), summary).map(entry => entry.key), [exhibitKey(paired), exhibitKey(previous)]);
  const stale = routed.map(entry => ({ ...entry, exhibit: { ...entry.exhibit, generation_ref: { ...ref, run_id: "another.run" } } }));
  assert.equal(primaryEmpiricalExhibits(stale, summary).length, 0);
  assert.equal(primaryEmpiricalExhibits(routed.map(entry => ({ ...entry, exhibit: { ...entry.exhibit, source_verified: false } })), summary).length, 0);
  assert.deepEqual(exhibits, before);
});

test("legacy tables fall back to authored priority without interpreting titles or inventing roles", () => {
  const first = { ...ordinary, exhibit_id: "legacy.first", title: "Previous study" }, second = { ...ordinary, exhibit_id: "legacy.second" };
  const routed = [first, second].map(exhibit => ({ exhibit, topic: "comparisons" }));
  assert.deepEqual(primaryEmpiricalExhibits(routed, { decision_summary: { headline_exhibit_ids: [second.exhibit_id] } }).map(entry => entry.exhibit.exhibit_id), [second.exhibit_id, first.exhibit_id]);
  assert.equal(empiricalExhibitSize(first), "2 rows · 2 columns");
  assert.equal(empiricalExhibitSize({ table: { columns: [{ key: "a" }], rows: [{ a: 0 }], truncated: true } }), "Row count unavailable · 1 column");
});

test("available authored headlines outrank semantically recognized non-headline tables", () => {
  const another = { ...ordinary, exhibit_id: "opaque.other-headline" };
  const routed = [paired, previous, ordinary, another].map(exhibit => ({ exhibit, topic: "comparisons" }));
  const choose = ids => primaryEmpiricalExhibits(routed, { generation_ref: ref, decision_summary: { headline_exhibit_ids: ids } }).map(entry => entry.exhibit.exhibit_id);
  assert.deepEqual(choose([another.exhibit_id, ordinary.exhibit_id]), [another.exhibit_id, ordinary.exhibit_id]);
  assert.deepEqual(choose([ordinary.exhibit_id]), [ordinary.exhibit_id, paired.exhibit_id]);
  assert.deepEqual(choose(["unavailable.exhibit", ordinary.exhibit_id]), [ordinary.exhibit_id, paired.exhibit_id]);
});

test("the first recorded contrast is previewed across conditions, retaining undefined results and source cells", () => {
  const before = structuredClone(paired), preview = empiricalExhibitPreview(paired);
  assert.equal(preview.contrast, "Mixture versus singleton"); assert.equal(preview.count, 6);
  assert.deepEqual(preview.exhibit.table.rows, [0, 3, 6, 9, 12, 15].map(i => paired.table.rows[i]));
  assert.ok(preview.exhibit.table.rows.every((row, i) => row === paired.table.rows[i * 3]));
  assert.equal(preview.exhibit.table.rows[0].n_pairs, 0); assert.match(preview.exhibit.table.rows[0].effect_difference, /undefined/);
  assert.deepEqual(preview.exhibit.table.columns.map(column => column.key), ["condition", "effect_difference", "MCSE", "n_pairs"]);
  assert.deepEqual(paired, before);
  const html = ui.render(ui.Compact, { exhibit: paired, primary: true });
  assert.equal((html.match(/<tbody>[\s\S]*?<\/tbody>/)?.[0].match(/<tr>/g) || []).length, 6);
  assert.match(html, /6 rows for the first recorded contrast/); assert.match(html, /36 rows · 5 columns/);
  assert.equal(html.split("Mixture versus singleton").length - 1, 1);
  const caption = html.match(/<figcaption id="([^"]+)">([\s\S]*?)<\/figcaption>/);
  assert.ok(caption && caption[2].includes("Mixture versus singleton"));
  assert.ok(html.includes(`<table aria-describedby="${caption[1]}"`));
  assert.match(html, /application\/x-tex">J_R\(\\pi\)-J_R\(\\pi_0\)/); assert.doesNotMatch(html, /katex-error|Other comparison/);
  assert.match(html, /undefined: no joint selection/); assert.match(html, /unavailable: fewer than two pairs/);
});

test("only identical design labels move to the preview caption", () => {
  const rows = ["A", "B"].map(Condition => ({ Condition, Method: "Baseline", Mean: 0, MCSE: 0, Outcome: "undefined", Study: null }));
  const exhibit = table("example", Object.keys(rows[0]), rows);
  const preview = empiricalExhibitPreview(exhibit);
  assert.deepEqual(preview.sharedColumns.map(c => [c.key, c.value]), [["Method", "Baseline"]]);
  assert.deepEqual(preview.exhibit.table.columns.map(c => c.key), ["Condition", "Mean", "MCSE", "Outcome", "Study"]);
  assert.equal(empiricalExhibitPreview(exhibit, 1).sharedColumns.length, 0);
  assert.deepEqual(empiricalExhibitPreview(table("all-labels", ["Method"], rows)).sharedColumns, []);
  assert.deepEqual(empiricalExhibitPreview(table("changes", ["Method", "Mean"], [rows[0], { ...rows[1], Method: null }])).sharedColumns, []);
  assert.deepEqual(exhibit.table.columns.map(c => c.key), Object.keys(rows[0]));
});

test("default results bound the two previews and retain every full table behind named readers", () => {
  const html = ui.render(ui.Workbench, { branch: ref.branch, exhibits: [check, ordinary, paired, previous], summaries: [summary] });
  assert.equal((html.match(/<table\b/g) || []).length, 2);
  assert.equal((html.match(/<tbody>[\s\S]*?<\/tbody>/g) || []).reduce((n, body) => n + (body.match(/<tr>/g) || []).length, 0), 12);
  assert.ok(html.indexOf("Main results</h3>") < html.indexOf("Experimental setup</h3>"));
  assert.match(html, /48 rows · 2 columns/); assert.doesNotMatch(html, /Check 47|Agrees within recorded tolerance/);
  for (const exhibit of [check, ordinary, paired, previous]) {
    const tree = ui.Compact({ exhibit, primary: exhibit === paired || exhibit === previous });
    const button = nodes(tree).find(node => node.type === ui.EmpiricalReadingButton);
    assert.ok(button); assert.equal(button.props.input.exhibit, exhibit);
    const snapshot = ui.empiricalReadingSnapshot({ ...button.props, scope: { projectId: "project.fixture", phase: "P4", branch: ref.branch } });
    const frozen = snapshot.body.props.children.props.exhibit;
    assert.deepEqual(frozen, exhibit); assert.notEqual(frozen, exhibit);
    const complete = ui.renderElement(snapshot.body);
    assert.match(complete, /<table/);
    const visited = [];
    for (let offset = 0; offset < frozen.table.rows.length; offset += 25) visited.push(...ui.artifactTablePage(frozen.table, offset).rows);
    assert.deepEqual(visited, exhibit.table.rows);
  }
});

test("a preview of a paged source retains original paging and exact size in the full reader", () => {
  const page = { ...paired, table: { ...paired.table, total_rows: 401, row_offset: 0, truncated: true, next_page_url: "/api/saved-table?offset=200" } };
  const before = structuredClone(page), preview = empiricalExhibitPreview(page);
  assert.equal(preview.exhibit.table.rows.length, 6);
  assert.equal(preview.exhibit.table.next_page_url, undefined);
  assert.equal(empiricalExhibitSize(page), "401 rows · 5 columns");
  const control = nodes(ui.Compact({ exhibit: page, primary: true })).find(node => node.type === ui.EmpiricalReadingButton);
  assert.deepEqual(control.props.input.exhibit.table, page.table);
  const snapshot = ui.empiricalReadingSnapshot({ ...control.props, scope: { projectId: "project.fixture", phase: "P4", branch: ref.branch } });
  assert.match(ui.renderElement(snapshot.body), /Next rows|401/);
  assert.deepEqual(page, before);
});

function mount(Component, props) {
  const slots = []; let cursor = 0, dirty = true, tree, effects = [];
  const state = initial => { const i = cursor++; slots[i] ||= { value: typeof initial === "function" ? initial() : initial }; return [slots[i].value, value => { const next = typeof value === "function" ? value(slots[i].value) : value; if (!Object.is(next, slots[i].value)) { slots[i].value = next; dirty = true; } }]; };
  const effect = (run, deps) => { const i = cursor++, old = slots[i]; if (!old || deps.some((dep, j) => dep !== old.deps[j])) { slots[i] = { deps, cleanup: old?.cleanup }; effects.push(() => { slots[i].cleanup?.(); slots[i].cleanup = run(); }); } };
  const hooks = { useState: state, useLayoutEffect: effect, useRef: initial => { const i = cursor++; return (slots[i] ||= { value: { current: initial } }).value; } };
  return { get tree() { return tree; }, settle() { for (let n = 0; dirty && n < 20; n++) { cursor = 0; dirty = false; effects = []; const previous = ui.dispatcher.current; try { ui.dispatcher.current = hooks; tree = Component(props); } finally { ui.dispatcher.current = previous; } effects.forEach(run => run()); } return tree; } };
}

test("complete inline table readers reopen at the saved page and keyboard paging focuses the table", () => {
  const key = "verified-exhibit:fixture"; ui.tableReadings.delete(key);
  const props = { table: paired.table, readingKey: key }, app = mount(ui.Table, props); app.settle();
  const calls = [], region = { focus: options => calls.push(options), scrollTop: 0, scrollLeft: 27 };
  nodes(app.tree).find(node => node.props.className === "table-scroll").ref.current = region;
  const next = nodes(app.tree).find(node => node.type === ui.ActionButton && node.props.children === "Next rows");
  next.props.onClick(); app.settle();
  assert.equal(ui.tableReadings.get(key).offset, 25); assert.deepEqual(calls, [{ preventScroll: true }]);
  const reopened = mount(ui.Table, props); reopened.settle();
  const rows = nodes(reopened.tree).filter(node => node.type === "tr");
  assert.equal(rows.length, 12); // header and the remaining eleven rows
  assert.ok(nodes(reopened.tree).some(node => node.type === "ResearchInline" || node.props.text === paired.table.rows[25].condition));
  ui.tableReadings.delete(key);
});
