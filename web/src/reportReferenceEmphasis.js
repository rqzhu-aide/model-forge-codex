import { opaqueInlineRanges } from "./researchMath.js";

// Bibliographic Markdown may italicize journal and proceedings titles. Keep
// stars in mathematics, code and link destinations literal to their owners.
export function reportReferenceEmphasis(text) {
  const source = String(text), opaque = opaqueInlineRanges(source);
  const parts = []; let opened = null, at = 0;
  for (const marker of source.matchAll(/(?<![\\*])\*(?!\*)/g)) {
    if (opaque.some(([start, end]) => marker.index >= start && marker.index < end)) continue;
    if (opened === null) {
      if (/\S/.test(source[marker.index + 1] || "")) opened = marker.index;
    } else if (/\S/.test(source[marker.index - 1] || "")) {
      parts.push({ text: source.slice(at, opened), emphasis: false },
        { text: source.slice(opened + 1, marker.index), emphasis: true });
      at = marker.index + 1; opened = null;
    }
  }
  parts.push({ text: source.slice(at), emphasis: false });
  return parts;
}
