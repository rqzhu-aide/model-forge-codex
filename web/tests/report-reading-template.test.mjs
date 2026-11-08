import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { reportAssetInput } from "../scripts/report-assets.mjs";
import { renderReport } from "../scripts/report-renderer.mjs";
import { reportReferenceEmphasis } from "../src/reportReferenceEmphasis.js";

const katex = createRequire(import.meta.url)(sharedPackage("katex"));
const descriptor = (name, bytes, media_type) => ({ path: path.resolve(name), authored_path: name,
  artifact_id: `artifact.${name}`, sha256: createHash("sha256").update(bytes).digest("hex"), media_type });

test("reading begins with the authored title and finding and keeps secondary material on demand", () => {
  const proof = Buffer.from('<a id="proof"></a>\n# Proof appendix\n\nThe retained argument is conditional.');
  const values = Buffer.from('{"rows":[{"Case":"Synthetic A","Estimate":0.125}]}');
  const files = { "proof.md": descriptor("proof.md", proof, "text/markdown"), "values.json": descriptor("values.json", values, "application/json") };
  const input = { markdown: '# A synthetic finite account\n\nThe synthetic estimate is 0.125; no population claim is made.\n\n<a id="method"></a>\n## Method\n\n[Proof](proof.md#proof) and [Exact values](values.json).',
    title: "A synthetic finite account", notation_markdown: '# Shared notation\n\n<a id="notation.0"></a>\n$n$ is the synthetic sample size.', asset_files: files };
  const original = JSON.stringify(input);
  const rendered = renderReport(katex, "", reportAssetInput(input, filename => filename === files["proof.md"].path ? proof : values));
  const html = rendered.html;
  assert.ok(html.indexOf("<h1") < html.indexOf("The synthetic estimate"));
  assert.ok(html.indexOf("The synthetic estimate") < html.indexOf('class="report-tools"'));
  assert.match(html, /<nav aria-label="Report contents"><ul><li><a href="#method">Method<\/a>/);
  assert.match(html, /<h2 id="method" tabindex="-1">Method<\/h2>/);
  assert.match(html, /<details class="report-material"><summary>Proof appendix<\/summary><section[^>]*id="report-support-1-document"/);
  assert.match(html, /<h1 id="report-support-1-proof" tabindex="-1">Proof appendix<\/h1>/);
  assert.match(html, /<details class="report-material"><summary>Exact values<\/summary><section[^>]*id="report-evidence-1"/);
  assert.match(html, /<details class="report-notation" id="report-notation"><summary>Notation glossary<\/summary><section[^>]*id="report-notation-content" tabindex="-1"/);
  assert.match(html, /<a id="notation\.0" tabindex="-1"><\/a>/);
  assert.match(html, /id="report-print-main" checked/);
  assert.doesNotMatch(html, /<details[^>]*\bopen\b|<script|onclick|onchange/);
  assert.match(rendered.print_css, /\.report-notation,\.report-material\{display:none!important\}/);
  assert.equal(JSON.stringify(input), original);
});

test("a table owns its complete authored caption, source anchor and explicit column headers", () => {
  const markdown = '# Synthetic values\n\n<a id="comparison"></a>\n**Table 2. Synthetic values.** Both rows describe finite sets; [the scope](#scope) is unchanged.\n\n'
    + '| Case | Estimate | Monte Carlo SE |\n| --- | --- | --- |\n| A | -0.00358 | 0.00079 |\n| B | 0.05260 | 0.00529 |\n\n<a id="scope"></a>\n## Scope\n\nSynthetic values only.';
  const output = renderReport(katex, "", { markdown, assets: {} });
  assert.match(output.html, /aria-labelledby="report-table-1-caption"><table><caption id="report-table-1-caption"><a id="comparison" tabindex="-1"><\/a>\s*<strong>Table 2\. Synthetic values\.<\/strong>/);
  assert.equal((output.html.match(/Table 2\. Synthetic values\./g) || []).length, 1);
  assert.match(output.html, /<th scope="col" class="report-number">Estimate<\/th>/);
  assert.match(output.html, /<td class="report-number">-0\.00358<\/td><td class="report-number">0\.00079<\/td>/);
  assert.match(output.print_css, /\.report-table caption\{break-inside:avoid;page-break-inside:avoid;break-after:avoid/);
  assert.match(output.print_css, /font-variant-numeric:tabular-nums/);
  assert.match(output.html, /href="#scope"/);
});

test("standalone proof editions omit the shared glossary while retaining linked scientific sources", () => {
  const proof = Buffer.from('# Conditional proof appendix\n\n<a id="proof"></a>\n## Argument\n\n$x+x=2x$.');
  const retainedHtml = Buffer.from('<html>Unretained original display.</html>');
  const files = { "proof.md": descriptor("proof.md", proof, "text/markdown"), "proof.html": descriptor("proof.html", retainedHtml, "text/html") };
  const prepared = reportAssetInput({ markdown: '# Report\n\n[Proof](proof.html#proof)', shareable_export: true,
    notation_markdown: '# Shared notation\n\nGLOSSARY_SENTINEL', asset_files: files }, filename => filename === files["proof.md"].path ? proof : retainedHtml);
  const output = renderReport(katex, "", { ...prepared, standalone_material_id: "artifact.proof.html" });
  assert.equal(output.title, "Conditional proof appendix");
  assert.match(output.html, /<h1[^>]*>Conditional proof appendix<\/h1>/);
  assert.match(output.html, /id="proof" tabindex="-1"/);
  assert.doesNotMatch(output.html, /GLOSSARY_SENTINEL|Notation glossary|Unretained original/);
  assert.match(output.html, /id="report-print-main" checked>This document/);
});

test("journal emphasis renders without interpreting mathematical, code or link asterisks", () => {
  const markdown = 'A. Author. A title. *Journal of Synthetic Examples* **12**, 3. $A^* B$ and `a*b*c`. [Source](https://example.org/a*b*c).';
  const output = renderReport(katex, "", { markdown, assets: {} });
  assert.match(output.html, /<em>Journal of Synthetic Examples<\/em> <strong>12<\/strong>/);
  assert.match(output.html, /<code>a\*b\*c<\/code>/);
  assert.match(output.html, /href="https:\/\/example\.org\/a\*b\*c"/);
  assert.match(output.html, /application\/x-tex">A\^\* B<\/annotation>/);
  assert.deepEqual(reportReferenceEmphasis('An unmatched * stays literal.'), [{ text: 'An unmatched * stays literal.', emphasis: false }]);
});

test("narrow-screen table captions stay semantic and estimate pairs can wrap without changing desktop or print", () => {
  const markdown = '# Synthetic comparison\n\n**Table 1. Paired reward comparison.** The estimates and standard errors are synthetic.\n\n'
    + '| Comparator | 256 episodes | 1,024 episodes |\n| --- | --- | --- |\n'
    + '| Pure policy from the same library | 0.02923 (0.01014) | 0.05260 (0.00529) |';
  const output = renderReport(katex, "", { markdown, assets: {} });
  assert.match(output.html, /<caption id="report-table-1-caption"><strong>Table 1\. Paired reward comparison\.<\/strong>/);
  assert.match(output.html, /<td class="report-number">0\.02923 \(0\.01014\)<\/td>/);
  const mobile = /@media screen and \(max-width:600px\)\{([\s\S]*?)\n/.exec(output.print_css)?.[1];
  assert.ok(mobile, "Responsive rules must exclude desktop and print media");
  assert.match(mobile, /\.report-table\{[^}]*container-type:inline-size/);
  assert.match(mobile, /\.report-table caption\{[^}]*max-width:100cqw/);
  assert.match(mobile, /\.report-table \.report-number\{white-space:normal\}/);
  assert.doesNotMatch(mobile, /caption\{[^}]*(?:display:block|overflow:hidden)/);
  const otherMedia = output.print_css.replace(/@media screen and \(max-width:600px\)\{[^\n]*\n/, "");
  assert.match(otherMedia, /\.report-number\{[^}]*white-space:nowrap/);
  assert.doesNotMatch(otherMedia, /100cqw|container-type:inline-size|\.report-number\{white-space:normal/);
  assert.match(otherMedia, /\.report-table caption\{break-inside:avoid/);
});
