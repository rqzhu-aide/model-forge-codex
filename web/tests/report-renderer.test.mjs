import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { renderReport } from "../scripts/report-renderer.mjs";

const katex = createRequire(import.meta.url)(sharedPackage("katex"));
const draw = markdown => renderReport(katex, "", { markdown, assets: {} }).html;

test("wide portable tables have named keyboard-scroll regions without changing their cell values", () => {
  const html = draw("| Target | Estimate | Source |\n| --- | --- | --- |\n| 180 days | -0.0006028432811984 | `generation.long_retained_identity` |\n\nAfter the table.");
  assert.match(html, /<div class="report-table" tabindex="0" role="region" aria-label="Report table"><table>/);
  assert.match(html, /<td>180 days<\/td><td>-0\.0006028432811984<\/td><td><code>generation\.long_retained_identity<\/code><\/td>/);
  assert.match(html, /<\/table><\/div>\n<p>After the table\.<\/p>/);
  assert.equal((html.match(/<table>/g) || []).length, 1);
});

test("display equations get a keyboard-scroll region while inline math keeps its exact form", () => {
  const latex = String.raw`\begin{aligned}X&=a+b+c+d+e+f+g+h+i+j\\Y&=2\end{aligned}`;
  const html = draw(`Inline $x$.\n\n$$${latex}$$`);
  assert.match(html, /<span class="report-equation" tabindex="0" role="region" aria-label="Mathematical equation"><span class="katex-display">/);
  assert.equal((html.match(/class="report-equation"/g) || []).length, 1);
  assert.ok(html.includes(katex.renderToString(latex, { displayMode: true, throwOnError: true })));
  assert.ok(html.includes(katex.renderToString("x", { displayMode: false, throwOnError: true })));
  assert.doesNotMatch(html, /katex-error/);
});

test("nested report tables remain native tables and ordinary prose gains no scroll region", () => {
  const html = draw("> | Quantity | Value |\n> | --- | --- |\n> | Accepted | 19 |\n\n1. Retained account\n   | Quantity | Value |\n   | --- | --- |\n   | Planned | 20 |");
  assert.equal((html.match(/class="report-table"/g) || []).length, 2);
  assert.equal((html.match(/<thead>/g) || []).length, 2);
  assert.match(html, /<blockquote><div class="report-table"/);
  assert.match(html, /<li value="1"><p>Retained account<\/p>\n<div class="report-table"/);
  assert.equal(draw("Plain conclusion with **retained emphasis**."), "<p>Plain conclusion with <strong>retained emphasis</strong>.</p>");
});

test("a primary document link without a fragment has an existing target even without supplements", () => {
  const html = renderReport(katex, '', {markdown:'[Top](report.md)',primary_paths:['report.md'],assets:{}}).html;
  assert.match(html, /id="report-main"/);
  assert.match(html, /href="#report-main"/);
});
