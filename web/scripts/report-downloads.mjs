// A saved report already contains the shared fonts and scientific sources.
// Keep standalone editions as small recipes, then assemble an independent HTML
// file only when it is downloaded. The resulting bytes retain their own digest.
const dataUri = /data:[A-Za-z0-9.+/-]+;base64,[A-Za-z0-9+/=]+/g;

export function restoreStandaloneHtml(parts, assets, mathCss) {
  return parts.map(part => part === null ? mathCss : typeof part === "number" ? assets[part] : part).join("");
}

function bindStandaloneDownloads(restore) {
  const bundleElement = document.currentScript.previousElementSibling;
  const root = bundleElement.previousElementSibling;
  const bundle = JSON.parse(bundleElement.textContent);
  const sources = root.querySelectorAll("a[href],img[src]");
  const assets = bundle.assets.map(asset => typeof asset === "string" ? asset
    : sources[asset.element].getAttribute(asset.attribute).split("#")[0]);
  const mathCss = document.getElementById("report-styles").textContent.slice(0, bundle.math_css_length);
  const urls = new Map();
  const prepare = event => {
    const anchor = event.target.closest?.("a[data-report-download]");
    if (!anchor || !root.contains(anchor)) return;
    const index = Number(anchor.getAttribute("data-report-download"));
    const edition = bundle.editions[index];
    if (!edition) return;
    if (!urls.has(index)) urls.set(index, URL.createObjectURL(new Blob([
      restore(edition.parts, assets, mathCss),
    ], { type: "text/html;charset=utf-8" })));
    anchor.href = urls.get(index);
    anchor.download = edition.filename;
  };
  for (const event of ["click", "contextmenu", "auxclick"]) root.addEventListener(event, prepare);
}

export function bundleStandaloneDownloads(html, css, downloads) {
  const editions = downloads.filter(download => typeof download.body === "string");
  if (!editions.length) return html;
  const assets = [], identities = new Map();
  // Refer to source URLs already present in the readable main document rather
  // than storing another copy. DOM order is unchanged by wrapping this content.
  const sources = [...html.matchAll(/<(?:a|img)\b[^>]*>/g)]
    .map(match => /\b(href|src)="([^"]*)"/.exec(match[0])).filter(Boolean);
  sources.forEach((match, element) => {
    const uri = match[2].split("#")[0];
    if (!/^data:[A-Za-z0-9.+/-]+;base64,[A-Za-z0-9+/=]+$/.test(uri) || identities.has(uri)) return;
    identities.set(uri, assets.length);
    assets.push({ element, attribute: match[1] });
  });
  const tokenize = text => {
    const parts = []; let at = 0;
    for (const match of text.matchAll(dataUri)) {
      parts.push(text.slice(at, match.index));
      if (!identities.has(match[0])) {
        identities.set(match[0], assets.length);
        assets.push(match[0]);
      }
      parts.push(identities.get(match[0]));
      at = match.index + match[0].length;
    }
    parts.push(text.slice(at));
    return parts;
  };
  const bundle = { math_css_length: css.length, assets, editions: editions.map(download => {
    const at = css ? download.body.indexOf(css) : -1;
    const parts = at < 0 ? tokenize(download.body)
      : [...tokenize(download.body.slice(0, at)), null, ...tokenize(download.body.slice(at + css.length))];
    return { filename: download.filename, parts };
  }) };
  const json = JSON.stringify(bundle).replaceAll("<", "\\u003c");
  let suffix = "", sequence = 0;
  while (["report-offline-content", "report-offline-downloads"].some(id => html.includes(`id="${id}${suffix}"`))) suffix = `-${++sequence}`;
  return `<div id="report-offline-content${suffix}">` + html
    + '<noscript><p>Enable JavaScript to download standalone supporting HTML. The supporting documents can also be read in this report.</p></noscript></div>'
    + `<script type="application/json" id="report-offline-downloads${suffix}">` + json + '</script>'
    + '<script>(' + bindStandaloneDownloads.toString() + ')(' + restoreStandaloneHtml.toString() + ');</script>';
}
