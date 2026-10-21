import { researchBlocks } from "./researchMarkdown.js";
import { inlineTokens, mathBody } from "./researchMath.js";

export const REPORT_SECTION_KEYS = ["problem", "model", "existing_approaches", "justification", "numerical_analysis", "limitations", "reproducibility"];
const anchorPattern = /<a id="([A-Za-z0-9_.:-]+)"><\/a>/g;
const anchorsIn = (block) => {
  if (!["paragraph", "heading"].includes(block?.kind)) return [];
  const prose = block.text.split(inlineTokens).map((part, index) => index % 2 && (mathBody(part) || part.startsWith("`")) ? "" : part).join("");
  return [...prose.matchAll(anchorPattern)].map((match) => match[1]);
};
const onlyAnchors = (block) => block?.kind === "paragraph" && block.text.replace(anchorPattern, "").trim() === "";

// Locate authored section headings in the same full-document block structure
// used by ResearchDocument. Never split scientific Markdown into fragments.
export function reportSectionHeadings(text, sectionAnchors = {}) {
  if (typeof text !== "string" || !sectionAnchors || typeof sectionAnchors !== "object") return new Map();
  const blocks = researchBlocks(text); const occurrences = new Map();
  blocks.forEach((block, index) => anchorsIn(block).forEach((anchor) => {
    occurrences.set(anchor, [...(occurrences.get(anchor) || []), index]);
  }));
  const headings = new Map();
  for (const key of REPORT_SECTION_KEYS) {
    const anchor = sectionAnchors[key]; const positions = occurrences.get(anchor) || [];
    if (!anchor || positions.length !== 1 || REPORT_SECTION_KEYS.filter((name) => sectionAnchors[name] === anchor).length !== 1) continue;
    const at = positions[0]; let headingIndex = blocks[at].kind === "heading" ? at : null;
    if (headingIndex == null && onlyAnchors(blocks[at])) {
      headingIndex = blocks[at + 1]?.kind === "heading" ? at + 1 : blocks[at - 1]?.kind === "heading" ? at - 1 : null;
    }
    if (headingIndex == null || headings.has(`document.block${headingIndex}`)) continue;
    headings.set(`document.block${headingIndex}`, { key, anchor, label: blocks[headingIndex].text.replace(anchorPattern, "").trim() });
  }
  return headings;
}
