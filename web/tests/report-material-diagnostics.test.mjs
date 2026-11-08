import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { sharedPackage } from "../scripts/shared-deps.mjs";
import { renderReport } from "../scripts/report-renderer.mjs";

const katex = createRequire(import.meta.url)(sharedPackage("katex"));
const diagnostic = callback => {
  let details;
  assert.throws(callback, error => {
    details = JSON.parse(error.message.split(" MF_REPORT_MATERIAL ")[1]);
    return true;
  });
  return details;
};

test("nested relative links identify retained privacy omissions separately from absent dependencies", () => {
  const omitted = { artifact_id: "artifact.implementation", source_sha256: "a".repeat(64),
    privacy_reason: "ambiguous_local_directory", omission_reason: "A shareable material has an ambiguous unquoted local directory" };
  const input = { markdown: "[Evaluation](evidence/evaluation.md)", assets: {},
    documents: { "evidence/evaluation.md": { identity: "evaluation", path: "evidence/evaluation.md",
      markdown: "# Evaluation\n\n[Implementation](../implementation.json)" } },
    withheld_materials: { "implementation.json": omitted }, shareable_export: true };
  const before = JSON.stringify(input);
  const details = diagnostic(() => renderReport(katex, "", input));
  assert.equal(details.reason, "privacy_withheld");
  assert.equal(details.linked_target, "../implementation.json");
  assert.equal(details.from_document, "evidence/evaluation.md");
  assert.deepEqual(details.withheld_material, omitted);
  assert.equal(JSON.stringify(input), before);

  const missing = diagnostic(() => renderReport(katex, "", { ...input, withheld_materials: {} }));
  assert.equal(missing.reason, "undeclared_dependency");
  assert.equal(missing.withheld_material, undefined);
});

test("withheld figures stay unavailable and their metadata never becomes an image source", () => {
  const details = diagnostic(() => renderReport(katex, "", { markdown: "![Retained figure](figure.png)",
    assets: {}, shareable_export: true,
    withheld_materials: { "figure.png": { artifact_id: "artifact.figure", privacy_reason: "uninspected_material" } } }));
  assert.equal(details.reason, "privacy_withheld");
  assert.equal(details.kind, "image");
});

test("an unused omitted material does not enter a successful shared report", () => {
  const rendered = renderReport(katex, "", { markdown: "# Conditional result\n\nFinite evidence remains limited.",
    assets: {}, shareable_export: true,
    withheld_materials: { "private.json": { omission_reason: "private-diagnostic-only-marker" } } });
  assert.doesNotMatch(rendered.html, /private\.json|private-diagnostic-only-marker|MF_REPORT_MATERIAL/);
});

test("an unsupported local target is distinct from an undeclared relative dependency", () => {
  const details = diagnostic(() => renderReport(katex, "", { markdown: "[Source](file:///private/source.json)",
    assets: {}, shareable_export: true }));
  assert.equal(details.reason, "unsupported_location");
});
