import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { researchBlocks } from "../src/researchMarkdown.js";
import { REPORT_SECTION_KEYS, reportReferenceBoundary, reportSectionHeadings } from "../src/reportSections.js";

const cases = JSON.parse(fs.readFileSync(new URL("../../tests/fixtures/report-boundary-cases.json", import.meta.url), "utf8"));

for (const fixture of cases) {
  test(`References boundary shared Python/JavaScript fixture: ${fixture.name}`, () => {
    if (!fixture.valid) {
      assert.throws(() => reportReferenceBoundary(fixture.markdown, fixture.anchors), /report References boundary/i);
      return;
    }
    const parsed = researchBlocks(fixture.markdown);
    const boundary = reportReferenceBoundary(fixture.markdown, fixture.anchors, parsed);
    assert.equal(boundary.anchor, fixture.anchors.references);
    assert.equal(parsed[boundary.headingIndex].kind, "heading");
    assert.equal(boundary.headingPath, `document.block${boundary.headingIndex}`);
    const headings = reportSectionHeadings(fixture.markdown, fixture.anchors, parsed);
    assert.equal(headings.size, 7);
    assert.deepEqual(new Set([...headings.values()].map(({ key }) => key)), new Set(REPORT_SECTION_KEYS));
    assert.ok(!headings.has(boundary.headingPath));
    assert.ok([...headings.keys()].every((key) => Number(key.replace("document.block", "")) < boundary.startIndex));
    assert.deepEqual(reportSectionHeadings(fixture.markdown, fixture.anchors), headings);
  });
}

test("historical References prose has no boundary without explicit metadata", () => {
  const fixture = cases[0]; const { references: _references, ...anchors } = fixture.anchors;
  assert.equal(reportReferenceBoundary(fixture.markdown, anchors), null);
  assert.equal(reportReferenceBoundary(fixture.markdown, null), null);
  assert.equal(reportSectionHeadings(fixture.markdown, anchors).size, 7);
});
