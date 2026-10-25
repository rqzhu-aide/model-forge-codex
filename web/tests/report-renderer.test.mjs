import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
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

test("declared References partitions one parsed report and retains citation and return anchors", () => {
  const fixture = JSON.parse(fs.readFileSync(new URL("../../tests/fixtures/report-boundary-cases.json", import.meta.url), "utf8"))[0];
  const markdown = fixture.markdown.replace("Main problem.", "Main problem. [Citation](#reference-one)")
    .replace("[1] Retained source.", '<a id="reference-one"></a>\n\nRetained source. [Return](#problem)');
  const original = JSON.stringify({ markdown, section_anchors: fixture.anchors, assets: {} });
  const input = JSON.parse(original);
  const rendered = renderReport(katex, "math-css", input);
  assert.match(rendered.html, /class="report-body"[^>]*>[\s\S]*Main reproducibility\.[\s\S]*<\/section>\n<section class="report-references"/);
  assert.match(rendered.html, /class="report-references"[^>]*><p><a id="report-references"><\/a><\/p>\n<h2>Sources<\/h2>/);
  assert.match(rendered.html, /href="#reference-one"/);
  assert.match(rendered.html, /id="reference-one"/);
  assert.match(rendered.html, /href="#problem"/);
  assert.match(rendered.html, /id="report-print-main" checked/);
  assert.match(rendered.print_css, /@page\{size:letter;margin:1in\}/);
  assert.match(rendered.print_css, /font-size:11pt;line-height:1\.4/);
  assert.match(rendered.print_css, /report-references\{break-before:page;page-break-before:always\}/);
  assert.equal(rendered.css, "math-css");
  assert.ok(Object.isFrozen(rendered.print_scopes));
  assert.equal(JSON.stringify(input), original);
  assert.doesNotMatch(rendered.html, /<script|onclick|onchange/);
});

test("a historical report keeps its unpartitioned account even when it has a References heading", () => {
  const rendered = renderReport(katex, "", { markdown: "# Main\n\n## References\n\nHistorical bibliography.", assets: {} });
  assert.equal(rendered.html, "<h1>Main</h1>\n<h2>References</h2>\n<p>Historical bibliography.</p>");
  assert.equal(rendered.print_css, "");
});

test("inline code examples cannot create citation anchors or offline asset reads", () => {
  const markdown = '`<a id="references"></a> [Example](missing.md)` and `` an inner ` plus <a id="references"></a> ``.';
  const html = draw(markdown);
  assert.equal((html.match(/<code>/g) || []).length, 2);
  assert.doesNotMatch(html, /<a |href=/);
  assert.match(html, /&lt;a id=&quot;references&quot;&gt;/);
});

test("indented code examples remain literal in the portable account", () => {
  const html = draw('    <a id="example"></a>\n    [Example](missing.md)\n\nAfter the example.');
  assert.match(html, /<pre><code>&lt;a id=&quot;example&quot;&gt;&lt;\/a&gt;\n\[Example\]\(missing\.md\)<\/code><\/pre>/);
  assert.doesNotMatch(html, /<a |href=/);
});

test("nested examples cannot shadow reserved report anchors but ordinary bibliography anchors remain usable", () => {
  const fixture = JSON.parse(fs.readFileSync(new URL("../../tests/fixtures/report-boundary-cases.json", import.meta.url), "utf8"))[0];
  const examples = '> <a id="report-references"></a>\n> Quoted anchor example.\n\n- <a id="problem"></a> Listed example.\n\n| Example | Value |\n| --- | --- |\n| <a id="report-references"></a> | Reserved anchor |\n\n';
  const rendered = renderReport(katex, "", { markdown: examples + fixture.markdown + '\n\n1. <a id="entry-in-list"></a> Bibliography entry.\n\n[Entry](#entry-in-list)', section_anchors: fixture.anchors, assets: {} });
  assert.equal((rendered.html.match(/id="report-references"/g) || []).length, 1);
  assert.equal((rendered.html.match(/id="problem"/g) || []).length, 1);
  assert.match(rendered.html, /id="entry-in-list"/);
  assert.match(rendered.html, /href="#entry-in-list"/);
});
