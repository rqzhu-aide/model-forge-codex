import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { reportAssetInput } from "../scripts/report-assets.mjs";
import { renderReport } from "../scripts/report-renderer.mjs";
import { restoreStandaloneHtml } from "../scripts/report-downloads.mjs";

const katex = createRequire(import.meta.url)(sharedPackage("katex"));
const digest = bytes => createHash("sha256").update(bytes).digest("hex");
const descriptor = (name, bytes, media_type) => ({ path: path.resolve(name), sha256: digest(bytes), media_type });
function standaloneEditions(rendered) {
  const bundle = JSON.parse(/<script type="application\/json" id="report-offline-downloads">([\s\S]*?)<\/script>/.exec(rendered.html)[1]);
  const sourceHtml = rendered.html.split('<script type="application/json" id="report-offline-downloads">')[0];
  const sources = [...sourceHtml.matchAll(/<(?:a|img)\b[^>]*>/g)]
    .map(match => /\b(href|src)="([^"]*)"/.exec(match[0])).filter(Boolean);
  const assets = bundle.assets.map(asset => typeof asset === "string" ? asset : sources[asset.element][2].split("#")[0]);
  return bundle.editions.map(edition => ({ ...edition, html: restoreStandaloneHtml(edition.parts, assets, rendered.css) }));
}

test("standalone CSS uses HTML-normalized newlines before computing its exact download hash", () => {
  const markdown = Buffer.from('# Exact proof\n\n$X=1$.');
  const html = Buffer.from('<html>Private original</html>');
  const files = { "appendix.md": { ...descriptor("appendix.md", markdown, "text/markdown"), artifact_id: "artifact.proof.md", authored_path: "appendix.md" },
    "appendix.html": { ...descriptor("appendix.html", html, "text/html"), artifact_id: "artifact.proof.html", authored_path: "appendix.html" } };
  const prepared = reportAssetInput({ markdown: '# Report\n\n[Proof](appendix.html)', shareable_export: true, asset_files: files }, filename => filename === files["appendix.md"].path ? markdown : html);
  const output = renderReport(katex, 'body{color:black}\r\n.katex{color:navy}\r\n', prepared);
  assert.equal(output.css, 'body{color:black}\n.katex{color:navy}\n');
  const edition = standaloneEditions(output)[0];
  assert.equal(digest(Buffer.from(edition.html)), output.derived_materials[0].export_sha256);
  assert.ok(edition.html.includes('<style>' + output.css));
  assert.doesNotMatch(edition.html, /\r/);
});

test("rendered references read exact bytes once per file/media while unreferenced large logs stay unread", () => {
  const code = Buffer.from([0, 255, 65, 10]);
  const svg = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><text>Exact figure</text></svg>');
  const source = descriptor("retained-source.bin", code, "application/octet-stream");
  const image = descriptor("retained-figure.svg", svg, "image/svg+xml");
  // No giant fixture is needed: reading this sentinel fails regardless of its
  // represented size, proving that aliases do not trigger eager file reads.
  const huge = { path: path.resolve("unreferenced-95MB-per-fit-log.json"), media_type: "application/json", sha256: "a".repeat(64) };
  const reads = [];
  const input = {
    markdown: "Inline $x^2$.\n\n[Source](source.bin) [Alias](artifact://source)\n\n![Figure](figure.svg)\n\n"
      + "[Local logs](http://127.0.0.1:8766/api/log?sha256=exact&path=deep) [Web](https://example.org/evidence?q=1&v=2)\n\n"
      + "`[Not a rendered link](deep.json)`\n\n```text\n[Example link](deep.json)\n![Example image](deep.json)\n```",
    asset_files: { "source.bin": source, "artifact://source": source, "figure.svg": image,
      "deep.json": huge, "artifact://deep": huge, "artifact.deep": huge },
  };
  const original = JSON.stringify(input);
  const prepared = reportAssetInput(input, filename => {
    reads.push(filename);
    if (filename === source.path) return code;
    if (filename === image.path) return svg;
    throw new Error("An unreferenced large source was read");
  });
  const html = renderReport(katex, "", prepared).html;
  assert.deepEqual(reads, [source.path, image.path]);
  assert.equal((html.match(/data:application\/octet-stream;base64,AP9BCg==/g) || []).length, 2);
  assert.ok(html.includes(`data:image/svg+xml;base64,${svg.toString("base64")}`));
  assert.match(html, /class="katex"/);
  assert.match(html, /href="http:\/\/127\.0\.0\.1:8766\/api\/log\?sha256=exact&amp;path=deep"/);
  assert.match(html, /href="https:\/\/example\.org\/evidence\?q=1&amp;v=2"/);
  assert.match(html, /<code>\[Not a rendered link\]\(deep\.json\)<\/code>/);
  assert.match(html, /<pre><code>\[Example link\]\(deep\.json\)/);
  assert.equal(JSON.stringify(input), original);
  assert.equal(prepared.assets.toString, undefined);
});

test("lazy file reads recheck the exact digest and reject conflicting alias metadata", () => {
  const bytes = Buffer.from("retained result\n");
  const source = descriptor("result.txt", bytes, "text/plain");
  const changed = reportAssetInput({ asset_files: { source } }, () => Buffer.from("changed result\n"));
  assert.throws(() => changed.assets.source, /changed after source verification/);

  let reads = 0;
  const prepared = reportAssetInput({ asset_files: { source, conflict: { ...source, sha256: "b".repeat(64) } } }, () => {
    reads += 1;
    return bytes;
  });
  assert.equal(prepared.assets.source, `data:text/plain;base64,${bytes.toString("base64")}`);
  assert.throws(() => prepared.assets.conflict, /conflicting retained digests/);
  assert.equal(reads, 1);
});

test("referenced missing files fail and retained file descriptors require absolute paths", () => {
  const source = descriptor("missing-result.json", Buffer.from("{}"), "application/json");
  const missing = reportAssetInput({ asset_files: { source } }, () => { throw new Error("ENOENT: missing retained source"); });
  assert.throws(() => missing.assets.source, /ENOENT/);
  const relative = reportAssetInput({ asset_files: { source: { ...source, path: "relative.json" } } }, () => {
    throw new Error("An invalid path was read");
  });
  assert.throws(() => relative.assets.source, /invalid retained file metadata/);
});

test("a cached file keeps distinct declared media types and supports existing inline assets", () => {
  const bytes = Buffer.from("same bytes");
  const source = descriptor("source.dat", bytes, "text/plain");
  let reads = 0;
  const prepared = reportAssetInput({ asset_files: { text: source, binary: { ...source, media_type: "application/octet-stream" } },
    assets: { legacy: "data:text/plain;base64,YQ==" } }, () => { reads += 1; return bytes; });
  assert.match(prepared.assets.text, /^data:text\/plain;base64,/);
  assert.match(prepared.assets.binary, /^data:application\/octet-stream;base64,/);
  assert.equal(prepared.assets.legacy, "data:text/plain;base64,YQ==");
  assert.equal(reads, 2);
});

test("Markdown support renders math and exact fragment links offline, including nested files and cycles", () => {
  const support = Buffer.from('<a id="model"></a>\n## Model\n\n$S(t)=\\exp(-t)$. [Back](../report.md#problem) [Theory](theory.md#model) [Again](#model)\n\n![Evidence](figure.svg)');
  const theory = Buffer.from('<a id="model"></a>\n## Theory\n\n[Return](support.md#model)');
  const figure = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><text>Exact</text></svg>');
  const descriptors = {
    'details/support.md': descriptor('support.md', support, 'text/markdown'),
    'details/theory.md': descriptor('theory.md', theory, 'text/markdown'),
    'details/figure.svg': descriptor('figure.svg', figure, 'image/svg+xml'),
  };
  const bytes = new Map([[descriptors['details/support.md'].path, support], [descriptors['details/theory.md'].path, theory], [descriptors['details/figure.svg'].path, figure]]);
  const reads = [];
  const input = reportAssetInput({
    markdown: '<a id="problem"></a>\n# Main\n\n[Definition](details/support.md#model)',
    primary_paths: ['report.md'], asset_files: descriptors,
  }, filename => { reads.push(filename); return bytes.get(filename); });
  const html = renderReport(katex, '', input).html;
  assert.match(html, /href="#report-support-1-model"/);
  assert.match(html, /id="report-support-1-model"/);
  assert.match(html, /href="#report-support-2-model"/);
  assert.match(html, /id="report-support-2-model"/);
  assert.match(html, /href="#problem"/);
  assert.match(html, /class="katex"/);
  assert.match(html, /data:image\/svg\+xml;base64,/);
  assert.equal((html.match(/class="report-supplement"/g) || []).length, 2);
  assert.equal(reads.length, 3);
  assert.doesNotMatch(html, /data:text\/markdown/);
});

test("support math is validated and a missing fragment-bearing file is not invented", () => {
  const bytes = Buffer.from('Invalid $\\notARealCommand{x}$.');
  const source = descriptor('support.md', bytes, 'text/markdown');
  const prepared = reportAssetInput({ markdown: '[Support](support.md#model)', asset_files: { 'support.md': source } }, () => bytes);
  assert.throws(() => renderReport(katex, '', prepared), /report support support.md/);
  assert.throws(() => renderReport(katex, '', { markdown: '[Missing](missing.md#model)', assets: {} }), /no portable target/);
});

test("exact Markdown print scopes exclude other support while all linked documents remain readable offline", () => {
  const appendix = Buffer.from('<a id="proof"></a>\n# Proof appendix\n\n$X=1$. [Main](../report.md#problem) [Other](other.md#notes)');
  const other = Buffer.from('<a id="notes"></a>\n# Supporting notes\n\nRetained notes.');
  const selected = { ...descriptor("appendix.md", appendix, "text/markdown"), artifact_id: "artifact.appendix" };
  const notes = { ...descriptor("other.md", other, "text/markdown"), artifact_id: "artifact.notes" };
  const input = { markdown: '<a id="problem"></a>\n# Main report\n\n[Proof](details/appendix.md#proof)',
    primary_paths: ["report.md"], print_material_id: "artifact.appendix",
    asset_files: { "details/appendix.md": selected, "artifact.appendix": selected, "details/other.md": notes } };
  const original = JSON.stringify(input); const reads = [];
  const rendered = renderReport(katex, "", reportAssetInput(input, filename => {
    reads.push(filename); return filename === selected.path ? appendix : other;
  }));
  assert.equal(reads.length, 2);
  assert.match(rendered.html, /id="report-support-1-print" checked/);
  assert.match(rendered.html, /<label class="report-print-option" for="report-print-main"><input[^>]*id="report-print-main">Report<\/label>/);
  assert.match(rendered.html, /href="#report-support-1-proof"/);
  assert.match(rendered.html, /href="#report-support-2-notes"/);
  assert.match(rendered.html, /href="#problem"/);
  assert.match(rendered.html, /id="report-support-1-document" data-report-material="artifact.appendix"/);
  assert.equal((rendered.html.match(/class="report-supplement"/g) || []).length, 2);
  assert.match(rendered.html, /class="katex"/);
  assert.match(rendered.print_css, /\.report-material\{display:none!important\}/);
  assert.match(rendered.print_css, /:has\(#report-support-1-print:checked\) \.report-primary\{display:none!important\}/);
  assert.match(rendered.print_css, /:has\(#report-support-1-print:checked\) #report-support-1-document\{display:block!important/);
  assert.equal(rendered.print_scopes.find(scope => scope.material_id === "artifact.appendix").region_id, "report-support-1-document");
  assert.equal(JSON.stringify(input), original);
});

test("a selected declared appendix renders even when the primary report has no appendix link", () => {
  const bytes = Buffer.from("# Submitted appendix\n\nExact retained proof.");
  const file = { ...descriptor("appendix.md", bytes, "text/markdown"), artifact_id: "artifact.appendix" };
  const rendered = renderReport(katex, "", reportAssetInput({ markdown: "# Main report", print_material_id: "artifact.appendix", asset_files: { "appendix.md": file } }, () => bytes));
  assert.match(rendered.html, /Submitted appendix/);
  assert.match(rendered.html, /id="report-support-1-print" checked/);
});

test("print material selection requires one exact submitted Markdown artifact identity", () => {
  const bytes = Buffer.from("# Appendix");
  const file = { ...descriptor("appendix.md", bytes, "text/markdown"), artifact_id: "artifact.appendix" };
  const prepare = (changes) => reportAssetInput({ print_material_id: "artifact.appendix", asset_files: { "appendix.md": file }, ...changes }, () => bytes);
  assert.throws(() => prepare({ print_material_id: "appendix.md" }), /not a declared report artifact/);
  assert.throws(() => prepare({ print_material_id: "" }), /exact submitted Markdown artifact/);
  assert.throws(() => prepare({ primary_paths: ["appendix.md"] }), /rather than the primary report/);
  assert.throws(() => prepare({ asset_files: { one: file, two: { ...file, path: path.resolve("other.md") } } }), /ambiguous retained source/);
  assert.throws(() => prepare({ asset_files: { "source.csv": { ...descriptor("source.csv", bytes, "text/csv"), artifact_id: "artifact.appendix" } } }), /not a retained Markdown/);
});

test("artifact-ID appendix links retain the canonical authored base for nested relative assets", () => {
  const appendix = Buffer.from('# Proof\n\n![Nested retained figure](figure.svg) [Notes](notes.md#entry)');
  const notes = Buffer.from('<a id="entry"></a>\n# Notes\n\n[Return](appendix.md)');
  const image = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg"><text>Nested exact image</text></svg>');
  const doc = { ...descriptor("physical-appendix.md", appendix, "text/markdown"), artifact_id: "artifact.appendix", authored_path: "details/proofs/appendix.md" };
  const next = { ...descriptor("physical-notes.md", notes, "text/markdown"), artifact_id: "artifact.notes", authored_path: "details/proofs/notes.md" };
  const figure = descriptor("physical-figure.svg", image, "image/svg+xml");
  const files = { "artifact.appendix": doc, "details/proofs/appendix.md": doc, "details/proofs/notes.md": next, "details/proofs/figure.svg": figure };
  const bytes = new Map([[doc.path, appendix], [next.path, notes], [figure.path, image]]);
  const rendered = renderReport(katex, "", reportAssetInput({ markdown: '[Proof](artifact.appendix)', asset_files: files,
    print_material_id: "artifact.appendix" }, filename => bytes.get(filename)));
  assert.match(rendered.html, /data:image\/svg\+xml;base64,/);
  assert.match(rendered.html, /href="#report-support-2-entry"/);
  assert.match(rendered.html, /href="#report-support-1-document"/);
  assert.match(rendered.html, /<summary>Proof<\/summary><section class="report-supplement"/);
});

test("a historical plain-text Markdown path stays readable without advertising an ineligible print scope", () => {
  const bytes = Buffer.from("# Historical support\n\nRetained readable content.");
  const file = { ...descriptor("support.md", bytes, "text/plain"), artifact_id: "artifact.support" };
  const input = { markdown: "[Support](support.md)", asset_files: { "support.md": file } };
  const rendered = renderReport(katex, "", reportAssetInput(input, () => bytes));
  assert.match(rendered.html, /Historical support/);
  assert.ok(!rendered.print_scopes.some(scope => scope.material_id === "artifact.support"));
  assert.throws(() => reportAssetInput({ ...input, print_material_id: "artifact.support" }, () => bytes), /not a retained Markdown/);
});

test("portable HTML proof links explicitly download the exact retained appendix bytes and original filename", () => {
  const bytes = Buffer.from('<!doctype html><title>Exact proof</title><a id="proof-safety"></a><p>Retained $x=1$.</p>\r\n');
  const file = { ...descriptor("sealed/appendix.html", bytes, "text/html"), artifact_id: "artifact.proof-html", authored_path: "proofs/appendix.html" };
  const input = { markdown: '[Proof](proofs/appendix.html#proof-safety) [Details](artifact.proof-html#proof-safety) [Web](https://example.org/proof.html)',
    asset_files: { "proofs/appendix.html": file, "artifact.proof-html": file } };
  const original = JSON.stringify(input); let reads = 0;
  const rendered = renderReport(katex, "", reportAssetInput(input, () => { reads++; return bytes; }));
  assert.match(rendered.html, /download="appendix\.html">Download proof appendix \(HTML\)<\/a>/);
  assert.match(rendered.html, /download="appendix\.html">Download Details \(HTML\)<\/a>/);
  const links = [...rendered.html.matchAll(/href="(data:text\/html;base64,([^"]+))" download="appendix\.html"/g)];
  assert.equal(links.length, 2); assert.equal(reads, 1);
  for (const [, href] of links) {
    assert.equal(href.endsWith("#proof-safety"), true);
    assert.deepEqual(Buffer.from(href.split(",")[1].split("#")[0], "base64"), bytes);
  }
  assert.match(rendered.html, /<a href="https:\/\/example\.org\/proof\.html">Web<\/a>/);
  assert.equal(rendered.print_scopes.length, 1, "Downloading HTML does not create a guessed Markdown rendition or print scope.");
  assert.equal(JSON.stringify(input), original);
  assert.throws(() => renderReport(katex, "", reportAssetInput(input, () => Buffer.from("changed proof"))), /changed after source verification/);
});

test("hosted HTML proof links use the verified generation attachment while retaining exact offline bytes", () => {
  const bytes = Buffer.from('<!doctype html><title>Exact proof</title><p id="proof">Retained proof.</p>\r\n');
  const file = { ...descriptor("sealed/appendix.html", bytes, "text/html"), artifact_id: "artifact.proof-html",
    authored_path: "proofs/appendix.html",
    download_url: "/api/v1/projects/project.a/branches/method.a/phases/P5/records/technical_report/generation.a?view=attachment&material_id=artifact.proof-html" };
  const source = { markdown: "[Proof](proofs/appendix.html#proof) [Details](artifact.proof-html#proof)",
    asset_files: { "proofs/appendix.html": file, "artifact.proof-html": file } };
  const prepared = reportAssetInput(source, () => bytes);
  const rendered = renderReport(katex, "", prepared);
  assert.equal((rendered.html.match(/href="\/api\/v1\/projects\/project\.a\/branches\/method\.a\/phases\/P5\/records\/technical_report\/generation\.a\?view=attachment&amp;material_id=artifact\.proof-html#proof" download="appendix\.html"/g) || []).length, 2);
  assert.doesNotMatch(rendered.html, /data:text\/html/);
  assert.deepEqual(Buffer.from(prepared.assets["artifact.proof-html"].split(",")[1], "base64"), bytes);
  assert.throws(() => renderReport(katex, "", reportAssetInput(source, () => Buffer.from("changed proof"))), /changed after source verification/);
});

test("shareable source descriptors use only their verified projected bytes for tables and named downloads", () => {
  const projected = Buffer.from(JSON.stringify({ columns: ["Method", "Issued / attempted", "Risk"], rows: [{ Method: "Example", "Issued / attempted": "18/60", Risk: 0.04133735 }] }));
  const file = { ...descriptor("retained-results.json", projected, "application/json"), authored_path: "support/results.json",
    content_base64: projected.toString("base64"), source_sha256: "a".repeat(64), export_filename: "results.shareable.json" };
  const prepared = reportAssetInput({ markdown: "[Result table](support/results.json)", shareable_export: true,
    asset_files: { "support/results.json": file } }, () => { throw new Error("Private source bytes must not be downloaded"); });
  const html = renderReport(katex, "", prepared).html;
  assert.match(html, /href="#report-evidence-1">Result table/);
  assert.match(html, /id="report-evidence-1" tabindex="-1"/);
  assert.match(html, /role="region" aria-labelledby="report-evidence-1-caption"/);
  assert.match(html, /<caption id="report-evidence-1-caption">Result table<\/caption>/);
  assert.match(html, /<th scope="col" class="report-number">Issued \/ attempted<\/th>/);
  assert.match(html, /<td class="report-number">18\/60<\/td><td class="report-number">0\.04133735<\/td>/);
  assert.match(html, /download="results.shareable.json"/);
  assert.deepEqual(Buffer.from(prepared.assets["support/results.json"].split(",")[1], "base64"), projected);
  assert.throws(() => reportAssetInput({ asset_files: { changed: { ...file, content_base64: Buffer.from("private").toString("base64") } } }).assets.changed, /changed after source verification/);
});

test("portable JSON tables retain authored column metadata, notation, captions and undefined states", () => {
  const table = { caption: "No returned output makes quality undefined in this synthetic comparison.", columns: [
    { key: "J_R", label: "J_R" }, { key: "quality", label: "$J_R(\\pi)$", unit: "$\\mathrm{mg}$" }, { key: "count", label: "Returned / attempted" },
  ], rows: [{ J_R: "RL-LPM1", quality: "Undefined (no output)", count: "0 / 60" }, { J_R: "$\\alpha=0.05$", quality: null, count: "<script>unsafe</script>" }] };
  const projected = Buffer.from(JSON.stringify(table));
  const file = { ...descriptor("retained-results.json", projected, "application/json"), authored_path: "support/results.json", content_base64: projected.toString("base64") };
  const input = { markdown: "[Result table](support/results.json)", shareable_export: true, asset_files: { "support/results.json": file } };
  const before = structuredClone(input); const prepared = reportAssetInput(input);
  const html = renderReport(katex, "", prepared).html;
  assert.match(html, /<th scope="col">J_R<\/th>/);
  assert.match(html, /application\/x-tex">J_R\(\\pi\)/);
  assert.match(html, /application\/x-tex">\\mathrm\{mg\}/);
  assert.match(html, /<caption id="report-evidence-1-caption">No returned output makes quality undefined in this synthetic comparison\.<\/caption>/);
  assert.match(html, /<td>RL-LPM1<\/td><td>Undefined \(no output\)<\/td><td>0 \/ 60<\/td>/);
  assert.match(html, /application\/x-tex">\\alpha=0\.05/);
  assert.match(html, /<td>Not recorded<\/td><td>&lt;script&gt;unsafe&lt;\/script&gt;<\/td>/);
  assert.doesNotMatch(html, /J R|RL LPM1|<script>/);
  assert.deepEqual(Buffer.from(prepared.assets["support/results.json"].split(",")[1], "base64"), projected);
  assert.deepEqual(input, before);
});

test("scientific table source links keep relative supporting documents reachable in the offline edition", () => {
  const values = Buffer.from(JSON.stringify({ columns: ["Metric", { key: "definition", label: "$R_{\\alpha}$ definition" }], rows: [{ Metric: "Risk", definition: "[Definition](notes.md#definition)" }], caption: "[Scope](notes.md#definition) remains conditional." }));
  const notes = Buffer.from('<a id="definition"></a>\n# Definition\n\nThe synthetic measure is defined only for returned outputs. [Values](results.json)');
  const table = { ...descriptor("retained-values.json", values, "application/json"), authored_path: "support/results.json", content_base64: values.toString("base64") };
  const note = { ...descriptor("retained-notes.md", notes, "text/markdown"), authored_path: "support/notes.md", content_base64: notes.toString("base64") };
  const html = renderReport(katex, "", reportAssetInput({ markdown: "[Results](support/results.json)", shareable_export: true, asset_files: { "support/results.json": table, "support/notes.md": note } })).html;
  assert.match(html, /href="#report-support-1-definition">Definition<\/a>/);
  assert.match(html, /href="#report-support-1-definition">Scope<\/a>/);
  assert.match(html, /id="report-support-1-definition"/);
  assert.match(html, /The synthetic measure is defined only for returned outputs/);
  assert.equal((html.match(/id="report-evidence-1"/g) || []).length, 1);
  assert.equal((html.match(/<summary>Definition<\/summary>/g) || []).length, 1);
});

test("shareable appendix download includes its rendered proof, report citations and source navigation without sibling files", () => {
  const main = Buffer.from('<a id="justification"></a>\n# Main scientific account\n\nThe theorem is conditional. [Proof](appendix.html#p1) [Results](support/results.json)');
  const appendix = Buffer.from('# Proof appendix\n\n[Return to report](report.html#justification) [Source](support/theory.md#lemma)\n\n<a id="p1"></a>\n## Conditional proof\n\n$X=1$.');
  const theory = Buffer.from('<a id="lemma"></a>\n# Retained lemma\n\n[Proof](../appendix.html#p1)');
  const results = Buffer.from('{"columns":["Attempted"],"rows":[{"Attempted":60}]}');
  const html = Buffer.from('<html><link rel="stylesheet" href="missing.css"><p>unpublished assembly candidate PRIVATE ORIGINAL</p></html>');
  const script = Buffer.from('print("retained implementation")\n');
  const files = Object.fromEntries([
    ["report.md", main, "text/markdown"], ["report.html", html, "text/html"], ["appendix.md", appendix, "text/markdown"],
    ["appendix.html", html, "text/html"], ["support/theory.md", theory, "text/markdown"], ["support/results.json", results, "application/json"],
    ["support/run.py", script, "text/x-python"],
  ].map(([name, bytes, media_type]) => [name, { ...descriptor(name, bytes, media_type), authored_path: name, artifact_id: `artifact.${name}` }]));
  const content = new Map([[files["report.md"].path, main], [files["report.html"].path, html], [files["appendix.md"].path, appendix],
    [files["appendix.html"].path, html], [files["support/theory.md"].path, theory], [files["support/results.json"].path, results], [files["support/run.py"].path, script]]);
  const input = { markdown: main.toString() + '\n\n[Same proof](appendix.html#p1)', primary_path: "report.md", primary_paths: ["report.md"], shareable_export: true, asset_files: files,
    reproduction_archive_base64: Buffer.from("504b0506000000000000000000000000000000000000", "hex").toString("base64") };
  const prepared = reportAssetInput(input, filename => content.get(filename));
  const rendered = renderReport(katex, "embedded-math-css", prepared);
  const editions = standaloneEditions(rendered);
  assert.equal(editions.length, 1, "Repeated proof citations share one standalone download");
  assert.match(rendered.html, /data-report-download="0"/);
  assert.doesNotMatch(rendered.html, /href="data:text\/html;base64,/);
  assert.ok((rendered.html.match(/href="#report-support-1-p1"/g) || []).length >= 2);
  const standalone = editions[0].html;
  assert.equal(rendered.derived_materials.find(material => material.artifact_id === "artifact.appendix.html").export_sha256, digest(Buffer.from(standalone)));
  assert.match(standalone, /embedded-math-css/);
  assert.match(standalone, /class="katex"/);
  assert.match(standalone, /id="p1"/);
  assert.match(standalone, /href="#report-support-1-justification"/);
  assert.match(standalone, /id="report-support-1-justification"/);
  assert.match(standalone, /href="#report-support-2-lemma"/);
  assert.match(standalone, /id="report-support-2-lemma"/);
  assert.match(standalone, /id="report-evidence-1"/);
  assert.doesNotMatch(standalone, /download="run.py"/, "Unlinked reproduction files are not copied into an appendix");
  assert.doesNotMatch(standalone, /PRIVATE ORIGINAL|unpublished assembly candidate|href="(?:report|appendix)\.html|src="(?!data:)|<link|<script/);
  assert.doesNotMatch(standalone, /data:application\/zip/, "The proof retains its scientific sources without duplicating the full reproduction package");
  for (const [, fragment] of standalone.matchAll(/href="#([^"]+)"/g)) assert.ok(standalone.includes(`id="${fragment}"`), fragment);
  const direct = renderReport(katex, "embedded-math-css", { ...prepared, standalone_material_id: "artifact.appendix.html" });
  assert.match(direct.html, /<h1[^>]*>Proof appendix<\/h1>/);
  assert.match(direct.html, /id="report-support-1-justification"/);
  assert.doesNotMatch(direct.html, /PRIVATE ORIGINAL/);
  assert.throws(() => renderReport(katex, "", { ...prepared, documentForHtml: () => undefined, standalone_material_id: "artifact.appendix.html" }), /one declared Markdown companion/);
});

test("shareable links and images cannot smuggle authored data URLs around the retained asset boundary", () => {
  for (const markdown of ['[Source](data:application/json;base64,e30=)', '![Figure](data:image/svg+xml;base64,PHN2Zy8+)']) {
    assert.throws(() => renderReport(katex, "", reportAssetInput({ markdown, shareable_export: true })), /must use declared retained assets/);
  }
});

test("proof and method-detail standalone editions use their own verified headings and distinct named downloads", () => {
  const rawHtml = Buffer.from('<title>Unretained display title</title>');
  const sources = [
    ["report.md", '<a id="question"></a>\n# Scientific report\n\n[Proof](appendix.html#proof) [Details](method-details.html#algorithm) [Proof again](appendix.html#proof)', "text/markdown"],
    ["report.html", rawHtml, "text/html"],
    ["appendix.md", '# Proof appendix: safety argument\n\n<a id="proof"></a>\n$X=1$. [Report](report.html#question) [Algorithm](method-details.html#algorithm)', "text/markdown"],
    ["appendix.html", rawHtml, "text/html"],
    ["method-details.md", '# Method details: policy selection\n\n<a id="algorithm"></a>\nRetained algorithm. [Report](report.html#question) [Argument](appendix.html#proof)', "text/markdown"],
    ["method-details.html", rawHtml, "text/html"],
  ];
  const files = {}; const bytes = new Map();
  for (const [name, content, media] of sources) {
    const value = Buffer.isBuffer(content) ? content : Buffer.from(content);
    files[name] = { ...descriptor(name, value, media), authored_path: name, artifact_id: `artifact.${name}`,
      ...(media === "text/html" ? { export_filename: name.replace(".html", ".shareable.html") } : {}) };
    bytes.set(files[name].path, value);
  }
  const prepared = reportAssetInput({ markdown: sources[0][1], primary_path: "report.md", primary_paths: ["report.md"],
    shareable_export: true, asset_files: files }, filename => bytes.get(filename));
  const output = renderReport(katex, "math-css", prepared);
  const downloads = standaloneEditions(output);
  assert.equal(downloads.length, 2, "Repeated citations do not duplicate either standalone payload");
  const expected = new Map([["appendix.shareable.html", "Proof appendix: safety argument"], ["method-details.shareable.html", "Method details: policy selection"]]);
  for (const { html, filename } of downloads) {
    const title = expected.get(filename); assert.ok(title, filename);
    assert.equal(/<title>([^<]+)<\/title>/.exec(html)[1], title);
    assert.match(html, new RegExp(`<h1[^>]*>${title}</h1>`));
    assert.match(html, /<summary>About this standalone edition<\/summary>/);
    assert.ok(output.html.includes(`Download standalone ${title} (HTML)`));
    assert.doesNotMatch(html, /href="data:text\/html|Unretained display title|href="(?:report|appendix|method-details)\.html/);
    for (const [, fragment] of html.matchAll(/href="#([^"]+)"/g)) assert.ok(html.includes(`id="${fragment}"`), `${filename}: ${fragment}`);
  }
  for (const [filename, title] of expected) {
    const originalName = filename.replace(".shareable.html", ".html");
    assert.equal(renderReport(katex, "math-css", { ...prepared, standalone_material_id: `artifact.${originalName}` }).title, title);
  }
});

test("hosted and offline editions expose one named projected reproduction ZIP without requiring folder-by-folder downloads", () => {
  const archive = Buffer.from("504b0506000000000000000000000000000000000000", "hex");
  const input = { markdown: "# Recorded evaluation", shareable_export: true,
    reproduction_archive_base64: archive.toString("base64"), reproduction_filename: "report-reproduction.shareable.zip" };
  const offline = renderReport(katex, "", reportAssetInput(input)).html;
  const link = /href="data:application\/zip;base64,([^"]+)" download="report-reproduction.shareable.zip"/.exec(offline);
  assert.ok(link); assert.deepEqual(Buffer.from(link[1], "base64"), archive);
  assert.equal((offline.match(/Download shareable reproduction package \(ZIP\)/g) || []).length, 1);
  assert.match(offline, /does not establish a new successful reproduction/);
  assert.match(offline, /manifest lists included files, source and export hashes, and omitted materials/);
  const hosted = renderReport(katex, "", reportAssetInput({ ...input, reproduction_download_url: "/api/v1/exact-shareable-package" })).html;
  assert.match(hosted, /href="\/api\/v1\/exact-shareable-package" download="report-reproduction.shareable.zip"/);
  assert.doesNotMatch(hosted, /data:application\/zip/);
});

test("shareable reports retain literature links and explain local workbench sources without exposing their URLs", () => {
  const markdown = '[Retained logs](http://127.0.0.1:8766/api/private-log?source=run) [Local](http://localhost/api/source) [IPv6](http://[::1]:8766/api/source) [Literature](https://example.org/paper)';
  const html = renderReport(katex, "", reportAssetInput({ markdown, shareable_export: true })).html;
  assert.match(html, /Retained logs \(local source, unavailable in a shared report\)/);
  assert.equal((html.match(/local source, unavailable in a shared report/g) || []).length, 3);
  assert.doesNotMatch(html, /127\.0\.0\.1|localhost|\[::1\]|private-log|source=run/);
  assert.match(html, /href="https:\/\/example\.org\/paper"/);
});
