import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { createHash } from "node:crypto";
import { bundleStandaloneDownloads, restoreStandaloneHtml } from "../scripts/report-downloads.mjs";

const digest = text => createHash("sha256").update(text).digest("hex");

test("offline standalone downloads reuse existing scientific sources and fonts and restore exact independent bytes", async () => {
  const source = `data:text/plain;base64,${Buffer.from("retained evidence\n".repeat(20_000)).toString("base64")}`;
  const image = 'data:image/svg+xml;base64,PHN2Zy8+';
  const extra = 'data:text/csv;base64,eCx5CjEsMgo=';
  const css = '@font-face{src:url(data:font/woff2;base64,ZXhhY3QtZm9udA==)}';
  const main = '<p><a href="#proof" data-report-download="0">Download standalone proof (HTML)</a></p>'
    + `<a href="${source}#row" download="evidence.txt">Evidence</a><img src="${image}" alt="Evidence">`
    + '<p><a href="#details" data-report-download="1">Download standalone details (HTML)</a></p>';
  const body = title => '<!doctype html><html><meta charset="utf-8"><title>' + title + '</title><style>' + css
    + '</style><body><a id="proof"></a><p>Conditionally valid λ.</p><a href="#proof">Proof</a>'
    + `<a href="${source}" download="evidence.txt">Evidence</a><img src="${image}" alt="Evidence">`
    + `<a href="${extra}" download="extra.csv">Extra evidence</a></body></html>`;
  const downloads = [{ filename: "appendix.shareable.html", body: body("Proof") }, { filename: "details.shareable.html", body: body("Details") }];
  const output = bundleStandaloneDownloads(main, css, downloads);
  assert.equal(output.split(source).length - 1, 1, "The large source is already in the readable main report");
  assert.equal(output.split(extra).length - 1, 1, "A source unique to the standalone editions is stored once");
  assert.equal(output.includes(css), false, "Shared math fonts are read from the main style element");
  assert.ok(output.length < main.length + 10_000, "Adding standalone editions must not multiply the large source payload");
  const bundle = JSON.parse(/id="report-offline-downloads">([\s\S]*?)<\/script>/.exec(output)[1]);
  const sources = [{ getAttribute: () => "#proof" }, { getAttribute: () => source + "#row" }, { getAttribute: () => image }, { getAttribute: () => "#details" }];
  const assets = bundle.assets.map(asset => typeof asset === "string" ? asset : sources[asset.element].getAttribute(asset.attribute).split("#")[0]);
  bundle.editions.forEach((edition, index) => {
    const restored = restoreStandaloneHtml(edition.parts, assets, css);
    assert.equal(restored, downloads[index].body);
    assert.equal(digest(restored), digest(downloads[index].body));
    assert.doesNotMatch(restored, /<script|report-offline|blob:|src="(?!data:)/);
  });

  const events = new Map(), blobs = [];
  const root = { querySelectorAll: () => sources, contains: () => true, addEventListener: (name, fn) => events.set(name, fn) };
  const document = { currentScript: { previousElementSibling: { textContent: JSON.stringify(bundle), previousElementSibling: root } },
    getElementById: () => ({ textContent: css + "body{color:black}" }) };
  const script = /<script>([\s\S]*?)<\/script>/.exec(output)[1];
  vm.runInNewContext(script, { document, Blob, URL: { createObjectURL: blob => { blobs.push(blob); return `blob:offline-${blobs.length}`; } } });
  const anchor = { getAttribute: () => "0" };
  events.get("contextmenu")({ target: { closest: selector => { assert.equal(selector, "a[data-report-download]"); return anchor; } } });
  assert.equal(anchor.href, "blob:offline-1");
  assert.equal(anchor.download, "appendix.shareable.html");
  assert.equal(await blobs[0].text(), downloads[0].body);
  events.get("click")({ target: { closest: () => anchor } });
  events.get("auxclick")({ target: { closest: () => anchor } });
  assert.equal(blobs.length, 1, "Repeated native clicks reuse the same download URL");
});

test("standalone recipes keep authored content inert and leave hosted attachment links unchanged", () => {
  const hosted = '<a href="/api/exact?view=attachment&amp;material_id=proof" download="proof.html">Proof</a>';
  assert.equal(bundleStandaloneDownloads(hosted, "css", [{ href: "/api/exact", filename: "proof.html" }]), hosted);
  const attack = '<!doctype html><p>&lt;script&gt;untrusted()&lt;/script&gt;</p>';
  const output = bundleStandaloneDownloads('<a href="#proof" data-report-download="0">Proof</a>', "", [{ body: attack, filename: "proof.html" }]);
  const json = /id="report-offline-downloads">([\s\S]*?)<\/script>/.exec(output)[1];
  assert.doesNotMatch(json, /</);
  assert.equal(restoreStandaloneHtml(JSON.parse(json).editions[0].parts, [], ""), attack);
});

test("authored anchors cannot shadow the generated download bundle or content wrapper", () => {
  const authored = '<a id="report-offline-content"></a><a id="report-offline-downloads"></a><a href="#proof" data-report-download="0">Proof</a>';
  const output = bundleStandaloneDownloads(authored, "", [{ body: "<!doctype html><p>Exact proof</p>", filename: "proof.html" }]);
  assert.match(output, /<div id="report-offline-content-1">/);
  assert.match(output, /type="application\/json" id="report-offline-downloads-1"/);
  assert.equal((output.match(/id="report-offline-downloads"/g) || []).length, 1);
  assert.equal((output.match(/id="report-offline-content"/g) || []).length, 1);
  assert.match(output, /document.currentScript.previousElementSibling/);
});
