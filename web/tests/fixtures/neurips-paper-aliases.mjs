// Synthetic assessments using the verified official NeurIPS URL alias pair.
const hash = "d89a66c7c80a29b1bdbab0f2a1a94af8";
export const neuripsSources = ["research_lead", "theorist"].map((role, index) => {
  const family = index ? "theory_literature" : "lead_literature";
  const source = {
    source_id: `source.armstrong2018.${index ? "occam" : "identifiability"}`,
    title: "Occam's razor is insufficient to infer the preferences of irrational agents",
    authors: ["Stuart Armstrong", "Sören Mindermann"], year: 2018, source_status: "active",
    identifiers: [{ kind: "url", value: `https://proceedings.neurips.cc/${index ? "paper" : "paper_files/paper"}/2018/hash/${hash}-Abstract.html` }],
  };
  return {
    ...source, source_ids: [source.source_id],
    search_provenance: [{ role, query: `Synthetic ${role} search` }],
    cards: [{
      role, family, run_id: "run.aliases", entry_id: `entry.${role}`, entry_sha256: String(index + 1).repeat(64),
      source_sha256: String(index + 3).repeat(64), canonical_source_id: source.source_id, source,
      explanation_markdown: `Synthetic ${role} assessment.`, formulation_markdown: `Synthetic ${role} mathematics.`,
      generation_ref: { branch: "trunk", phase: "P1", family, run_id: "run.aliases", generation_id: `generation.${role}`, sha256: String(index + 5).repeat(64) },
      entry_pointer: "/papers/0",
    }],
  };
});
