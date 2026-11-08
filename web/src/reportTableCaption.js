// Only an explicitly numbered caption immediately before a table is moved.
// Keep its full markup, including source links, math, and authored anchors.
export function reportTableCaption(block) {
  if (block?.kind !== "paragraph") return "";
  return /^(?:\s*<a id="[A-Za-z0-9_.:-]+"><\/a>)*\s*(?:\*\*)?Table\s+\d+[\.:](?=\s|\*\*|$)/i.test(block.text)
    ? block.text : "";
}
