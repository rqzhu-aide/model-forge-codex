import { researchBlocks } from "./researchMarkdown.js";
import { inlineTokens, mathBody } from "./researchMath.js";

export const REPORT_SECTION_KEYS = ["problem", "model", "existing_approaches", "justification", "numerical_analysis", "limitations", "reproducibility"];
const anchorPattern = /<a id="([A-Za-z0-9_.:-]+)"><\/a>/g;
const codeSpanPattern = /(?<!`)(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)/g;
const anchorsIn = (block) => {
  if (!["paragraph", "heading"].includes(block?.kind)) return [];
  const prose = block.text.replace(codeSpanPattern, (code) => code.replace(/[^\n]/g, " ")).split(inlineTokens).map((part, index) => index % 2 && (mathBody(part) || part.startsWith("`")) ? "" : part).join("");
  return [...prose.matchAll(anchorPattern)].map((match) => match[1]);
};
const onlyAnchors = (block) => block?.kind === "paragraph" && block.text.replace(anchorPattern, "").trim() === "";

function authoredHeadings(blocks, sectionAnchors, keys) {
  const occurrences = new Map();
  blocks.forEach((block, index) => anchorsIn(block).forEach((anchor) => {
    occurrences.set(anchor, [...(occurrences.get(anchor) || []), index]);
  }));
  const found = new Map();
  for (const key of keys) {
    const anchor = sectionAnchors[key]; const positions = occurrences.get(anchor) || [];
    if (typeof anchor !== "string" || !anchor || positions.length !== 1 || keys.filter((name) => sectionAnchors[name] === anchor).length !== 1) continue;
    const at = positions[0]; let headingIndex = blocks[at].kind === "heading" ? at : null;
    if (headingIndex == null && onlyAnchors(blocks[at])) {
      headingIndex = blocks[at + 1]?.kind === "heading" ? at + 1 : blocks[at - 1]?.kind === "heading" ? at - 1 : null;
    }
    if (headingIndex == null) continue;
    found.set(key, { key, anchor, startIndex: Math.min(at, headingIndex), headingIndex,
      headingPath: `document.block${headingIndex}`, label: blocks[headingIndex].text.replace(anchorPattern, "").trim() });
  }
  return found;
}

// Locate authored section headings in the same full-document block structure
// used by ResearchDocument. Never split scientific Markdown into fragments.
export function reportSectionHeadings(text, sectionAnchors = {}, parsedBlocks = null) {
  if (typeof text !== "string" || !sectionAnchors || typeof sectionAnchors !== "object") return new Map();
  const blocks = parsedBlocks || researchBlocks(text);
  const headings = new Map();
  for (const { key, anchor, label, headingPath } of authoredHeadings(blocks, sectionAnchors, REPORT_SECTION_KEYS).values()) {
    if (!headings.has(headingPath)) headings.set(headingPath, { key, anchor, label });
  }
  return headings;
}

// References is a boundary in one parsed document, never an eighth discussion
// section. Historical reports with no declaration keep their existing reading.
export function reportReferenceBoundary(text, sectionAnchors = {}, parsedBlocks = null) {
  if (!sectionAnchors || typeof sectionAnchors !== "object" || !Object.hasOwn(sectionAnchors, "references")) return null;
  if (typeof text !== "string" || typeof sectionAnchors.references !== "string" || !sectionAnchors.references) {
    throw new Error("The report References boundary must name one authored heading anchor");
  }
  const blocks = parsedBlocks || researchBlocks(text);
  const keys = [...REPORT_SECTION_KEYS, "references"];
  const found = authoredHeadings(blocks, sectionAnchors, keys);
  if (found.size !== keys.length || new Set([...found.values()].map((row) => row.headingIndex)).size !== keys.length) {
    throw new Error("The report References boundary and seven section anchors must identify distinct, unique main headings");
  }
  const boundary = found.get("references");
  if (REPORT_SECTION_KEYS.some((key) => found.get(key).startIndex >= boundary.startIndex)) {
    throw new Error("The report References boundary must follow all seven scientific sections");
  }
  const { key: _key, ...result } = boundary;
  return result;
}
