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
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-artifact-table-"));
const bundle = path.join(directory, "render.cjs");
const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src").replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; import {renderToStaticMarkup} from 'react-dom/server'; import Table, {artifactTablePage} from '${src}/components/ArtifactTable.jsx'; export {artifactTablePage}; export const render = table => renderToStaticMarkup(React.createElement(Table, {table}));`, resolveDir: src }, outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const { artifactTablePage, render } = require(bundle);
fs.unlinkSync(bundle); fs.rmdirSync(directory);

const columns = [{ key: "id", label: "Case" }, { key: "estimate", label: "Estimate" }];
const tableWithRows = (count) => ({ columns, rows: Array.from({ length: count }, (_, index) => ({ id: `case-${index}`, estimate: index === 0 ? 0 : index === 1 ? null : index / 10 })) });

test("complete inline tables show 25 rows and retain zero and missing values", () => {
  const table = tableWithRows(156); const html = render(table);
  assert.equal((html.match(/<tbody>[\s\S]*?<\/tbody>/)?.[0].match(/<tr>/g) || []).length, 25);
  assert.match(html, /Rows 1 to 25 of 156/);
  assert.match(html, /<td>case-0<\/td><td>0<\/td>/);
  assert.match(html, /<td>case-1<\/td><td>Not recorded<\/td>/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>[\s\S]*?Previous rows/);
  assert.match(html, /Next rows/);
  assert.doesNotMatch(html, /case-25<\/td>|original table contains/);
});

test("all inline rows are reachable in their saved order without changing their data", () => {
  const table = tableWithRows(156); const before = JSON.stringify(table);
  table.rows.forEach(Object.freeze); Object.freeze(table.rows); Object.freeze(table);
  const visited = []; let offset = 0;
  while (offset < table.rows.length) {
    const page = artifactTablePage(table, offset);
    assert.equal(page.inline, true); assert.equal(page.offset, offset);
    assert.equal(page.total, 156); assert.ok(page.rows.length <= 25);
    visited.push(...page.rows); offset += page.rows.length;
  }
  assert.deepEqual(visited, table.rows);
  assert.ok(visited.every((row, index) => row === table.rows[index]));
  assert.equal(JSON.stringify(table), before);
  const last = artifactTablePage(table, 150);
  assert.equal(last.rows.length, 6); assert.equal(last.offset + last.rows.length, last.total);
  assert.deepEqual(artifactTablePage(table, 125).rows, table.rows.slice(125, 150));
});

test("small inline tables retain their complete rendering without pagination", () => {
  for (const count of [0, 1, 25]) {
    const table = tableWithRows(count); const page = artifactTablePage(table);
    assert.equal(page.inline, false); assert.equal(page.rows, table.rows);
    assert.doesNotMatch(render(table), /table-pagination|Previous rows|Next rows/);
  }
});

test("server pages preserve their full rows, offsets and existing URL controls", () => {
  const table = { ...tableWithRows(200), row_offset: 200, total_rows: 401, truncated: true, previous_page_url: "/api/table?offset=0", next_page_url: "/api/table?offset=400" };
  const before = JSON.stringify(table); const page = artifactTablePage(table, 25); const html = render(table);
  assert.equal(page.inline, false); assert.equal(page.rows, table.rows);
  assert.equal(page.offset, 200); assert.equal(page.total, 401);
  assert.equal((html.match(/<tbody>[\s\S]*?<\/tbody>/)?.[0].match(/<tr>/g) || []).length, 200);
  assert.match(html, /Rows 201 to 400 of 401/);
  assert.match(html, /Previous rows/); assert.match(html, /Next rows/);
  assert.equal(JSON.stringify(table), before);
  for (const metadata of [{ next_page_url: "/api/table?offset=200" }, { previous_page_url: "/api/table?offset=0" }, { truncated: true }, { total_rows: 401 }, { row_offset: 200 }]) {
    const server = { ...tableWithRows(200), ...metadata };
    assert.equal(artifactTablePage(server).inline, false);
    assert.equal(artifactTablePage(server).rows, server.rows);
  }
});
