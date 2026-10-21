// Synthetic reading fixture, with exact source identities for two updates.
const roles = ["research_lead", "theorist", "data_analyst"];
const families = ["lead_literature", "theory_literature", "empirical_literature"];
export const literatureCollections = [2, 1].flatMap((update) => roles.map((role, index) => ({
  branch: "trunk", phase: "P1", role, family: families[index], is_current_package: update === 2,
  package_id: `package.update${update}`, published_at: `2026-09-${update === 2 ? "30" : "20"}T15:00:00Z`,
  search_scope: `${update === 2 ? "Current" : "Earlier"} ${role} search: primary papers about constrained estimation.`,
  coverage_limits: [update === 2 ? "This search did not examine dependent observations." : "This search did not examine recent preprints."],
  generation_ref: { branch: "trunk", phase: "P1", family: families[index], run_id: `run.update${update}`,
    package_id: `package.update${update}`, generation_id: `generation.${families[index]}.${update}`, sha256: String(update).repeat(64) },
})));
export const literatureLibrary = { branch: "trunk", phase: "P1", total_sources: 2,
  changes: { added: 1, updated: 0, rediscovered: 1 }, sources: [
    { source_id: "citation.earlier", title: "Earlier estimator remains relevant", cards: [{ role: "theorist", entry_id: "entry.earlier", from_earlier_run: true }] },
    { source_id: "citation.current", title: "Current paper about constraints", cards: [{ role: "data_analyst", entry_id: "entry.current" }] },
  ] };
export const literatureBasis = { branch: "trunk", phase: "P1", landscape: { summary_markdown: "The retained literature supports estimation under independent sampling. Dependence remains unresolved.", topics: [] },
  research_setting: { statement_markdown: "Estimate $\\theta$ from observations $X_1,\\ldots,X_n$." },
  coverage_limits: ["Dependent observations remain outside the checked scope."] };
