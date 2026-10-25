import test from "node:test";
import assert from "node:assert/strict";
import { assessmentKey, buildFrameworkGraph, entryIdentity, entryMatches, groupPaperSources, landscapeRecords, paperReviewFindings, resolveLandscapeEntry, selectLandscapeRecord } from "../src/literatureLandscape.js";
import { frameworkBasis, frameworkSources } from "./fixtures/framework-landscape.mjs";
import { neuripsSources } from "./fixtures/neurips-paper-aliases.mjs";

test("official NeurIPS URL aliases share a paper view while exact assessments and provenance remain intact", () => {
  const before = JSON.stringify(neuripsSources);
  const [paper] = groupPaperSources(neuripsSources);
  assert.equal(groupPaperSources(neuripsSources).length, 1);
  assert.equal(paper.source_id, neuripsSources[0].source_id);
  assert.deepEqual(paper.source_aliases, neuripsSources.map((source) => source.source_id));
  for (const [index, source] of neuripsSources.entries()) {
    const card = source.cards[0];
    assert.equal(paper.cards[index], card);
    assert.equal(paper.identifiers[index], source.identifiers[0]);
    assert.equal(paper.search_provenance[index], source.search_provenance[0]);
    assert.equal(resolveLandscapeEntry([paper], entryIdentity(card)).card, card);
    assert.equal(card.canonical_source_id, source.source_id);
    assert.equal(resolveLandscapeEntry([paper], { ...entryIdentity(card), entry_sha256: "unknown" }), null);
  }
  assert.equal(JSON.stringify(neuripsSources), before);
  assert.deepEqual(groupPaperSources([]), []);
});

test("paper views do not merge titles, unverified URL forms, ambiguous hashes, or conflicting dispositions", () => {
  const [first, second] = neuripsSources;
  const url = second.identifiers[0].value;
  const cases = [
    { identifiers: [{ kind: "url", value: url.replace("d89a66c7", "a89a66c7") }] },
    { identifiers: [{ kind: "url", value: url.replace("proceedings.neurips.cc", "example.org") }] },
    { identifiers: [{ kind: "url", value: `${url}?version=other` }] },
    { identifiers: [{ kind: "url", value: url.replace("https:", "http:") }] },
    { identifiers: [{ kind: "url", value: url.replace("-Abstract.html", "-Paper.pdf") }] },
    { identifiers: [{ kind: "url", value: "not a URL" }] },
    { identifiers: [second.identifiers[0], { kind: "url", value: url.replace("d89a66c7", "a89a66c7") }] },
    { year: 2019 },
    { source_status: "retracted", status_reason: "Synthetic retraction notice." },
    { status_reason: "Synthetic status qualification." },
    { landscape_status: "exclude", landscape_reason: "Synthetic scope exclusion." },
    { landscape_reason: "Synthetic disposition qualification." },
  ];
  for (const change of cases) {
    const candidate = { ...second, ...change };
    const grouped = groupPaperSources([first, candidate]);
    assert.equal(grouped.length, 2, JSON.stringify(change));
    assert.equal(grouped[0], first);
    assert.equal(grouped[1], candidate);
  }
});

test("framework selection keeps authored records and relationships, including cycles, without inferring links", () => {
  const landscape = structuredClone(frameworkBasis.landscape);
  landscape.relationships.push({ ...landscape.relationships[0], relationship_id: "relationship.reverse", from_id: "framework.expected", to_id: "framework.overrun", relationship_type: "unresolved" });
  const before = JSON.stringify(landscape);
  const graph = buildFrameworkGraph(landscape);
  assert.equal(graph.nodes.length, 3);
  assert.equal(graph.edges.length, 2); // No inferred variant-parent or algorithm edges.
  assert.equal(graph.edges[1].record.relationship_type, "unresolved");
  assert.equal(graph.edges[1].record, landscape.relationships[1]);
  assert.equal(selectLandscapeRecord(landscape, "relationship.reverse").record, landscape.relationships[1]);
  assert.equal(selectLandscapeRecord(landscape, "algorithm.trajectory").kind, "algorithm");
  assert.equal(selectLandscapeRecord(landscape, "missing.after.update").id, "framework.expected");
  assert.equal(JSON.stringify(landscape), before);
});

test("incomplete historical maps retain list records but do not invent missing graph endpoints", () => {
  const landscape = { relationships: [{ relationship_id: "relation.old", from_id: "missing.a", to_id: "missing.b", title: "Recorded unresolved comparison" }] };
  assert.equal(buildFrameworkGraph(landscape).edges.length, 0);
  assert.equal(landscapeRecords(landscape).length, 1);
  assert.equal(selectLandscapeRecord({ topics: [{ topic_id: "old.topic" }] }), null);
});

test("authored comparisons involving algorithm families have selectable map endpoints", () => {
  const landscape = structuredClone(frameworkBasis.landscape);
  landscape.relationships.push({ ...landscape.relationships[0], relationship_id: "relationship.algorithm", from_id: "algorithm.trajectory", to_id: "variant.zero", relationship_type: "alternative" });
  const graph = buildFrameworkGraph(landscape);
  assert.equal(graph.nodes.find((node) => node.id === "algorithm.trajectory").kind, "algorithm");
  assert.equal(graph.edges.find((edge) => edge.id === "relationship.algorithm").record.from_id, "algorithm.trajectory");
  assert.equal(selectLandscapeRecord(landscape, "algorithm.trajectory").record, landscape.algorithm_families[0]);
});

test("evidence selection resolves exact member, run, and effective or historical entry version", () => {
  const source = frameworkSources[0]; const current = source.cards[0]; const original = current.assessment_history[0];
  const reference = frameworkBasis.landscape.frameworks[0].entry_refs[0];
  const resolved = resolveLandscapeEntry(frameworkSources, reference);
  assert.equal(resolved.card, current);
  assert.equal(resolved.historyIndex, null);
  assert.equal(resolved.assessmentKey, assessmentKey(current));
  const previous = resolveLandscapeEntry(frameworkSources, { ...reference, entry_sha256: original.entry_sha256 });
  assert.equal(previous.card, original);
  assert.equal(previous.currentCard, current);
  assert.equal(previous.historyIndex, 0);
  assert.notEqual(assessmentKey(source.cards[0]), assessmentKey(source.cards[1])); // Members may share entry IDs.
  assert.equal(resolveLandscapeEntry(frameworkSources, { ...reference, run_id: "another.run" }), null);
  assert.equal(resolveLandscapeEntry(frameworkSources, { ...reference, entry_sha256: "unknown.version" }), null);
  assert.equal(entryMatches(reference, { ...current, entry_sha256: undefined, lead_revision: undefined }), false);
  assert.equal(resolveLandscapeEntry(frameworkSources, { ...reference, entry_sha256: undefined }).card, current);
  const updatedSources = structuredClone(frameworkSources);
  const newer = updatedSources[0].cards[0];
  newer.assessment_history.unshift({ ...current, assessment_history: [] });
  newer.entry_sha256 = "e".repeat(64);
  assert.equal(resolveLandscapeEntry(updatedSources, reference).historyIndex, 0);
  assert.equal(resolveLandscapeEntry(updatedSources, { ...reference, entry_sha256: original.entry_sha256 }).historyIndex, 1); // A refresh cannot turn a retained digest into a different history row.
});

test("review findings remain scoped to checked versions and never transfer across members or runs", () => {
  const current = frameworkSources[0].cards[0]; const original = current.assessment_history[0];
  const findings = paperReviewFindings(frameworkBasis.scientific_review, current);
  assert.equal(findings.length, 1);
  assert.equal(findings[0].earlier, true);
  assert.equal(paperReviewFindings(frameworkBasis.scientific_review, original)[0].earlier, false);
  assert.equal(paperReviewFindings(frameworkBasis.scientific_review, frameworkSources[0].cards[1]).length, 0);
  const unbound = { findings: [{ ...frameworkBasis.scientific_review.findings[0], target: { ...original, entry_sha256: undefined } }] };
  assert.equal(paperReviewFindings(unbound, current).length, 0);
  assert.equal(paperReviewFindings(undefined, original).length, 0);
});
