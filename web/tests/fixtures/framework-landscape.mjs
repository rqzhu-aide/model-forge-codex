// Synthetic UI fixture only. Never publish this data into a research project.
const originalRef = { role: "theorist", family: "theory_literature", run_id: "run.fixture", entry_id: "entry.shared", entry_sha256: "a".repeat(64) };
const currentRef = { ...originalRef, entry_sha256: "b".repeat(64) };
const generation = { branch: "trunk", phase: "P1", family: "research_basis", run_id: "run.fixture", generation_id: "generation.fixture", sha256: "c".repeat(64) };
const common = {
  assumptions_markdown: "Let $0<\\gamma<1$, $c_t\\geq0$, and $C^\\pi=\\sum_{t=0}^{\\infty}\\gamma^t c_t$ with $\\mathbb E_\\pi[C^\\pi]<\\infty$.",
  explanation_markdown: "The criterion is a functional of the discounted cost distribution.",
  entry_refs: [currentRef], support_status: "partially_supported", limitations: ["This fixture records a comparison, not a proof certification."],
};

export const frameworkBasis = {
  branch: "trunk", phase: "P1", generation_ref: generation,
  landscape: {
    summary_markdown: "Fixture landscape: distinguish the formulation from the algorithm used to solve it.",
    frameworks: [
      { ...common, framework_id: "framework.expected", title: "Expected discounted cost", formulation_markdown: "$$\\max_\\pi J_r(\\pi) \\quad\\text{subject to}\\quad \\mathbb E_\\pi[C^\\pi]\\leq b.$$", relevance_markdown: "A constraint on the expectation of the total discounted cost." },
      { ...common, framework_id: "framework.overrun", title: "Expected budget overrun", formulation_markdown: "$$\\max_\\pi J_r(\\pi) \\quad\\text{subject to}\\quad \\mathbb E_\\pi[(C^\\pi-b)_+]\\leq\\delta.$$", relevance_markdown: "A constraint on the expected positive excess above a fixed budget." },
    ],
    variants: [{ ...common, variant_id: "variant.zero", framework_id: "framework.overrun", title: "Zero permitted expected overrun", formulation_markdown: "$\\mathbb E_\\pi[(C^\\pi-b)_+]=0$.", changes_markdown: "Set $\\delta=0$ while retaining the same random total $C^\\pi$.", consequences_markdown: "Then $C^\\pi\\leq b$ almost surely." }],
    relationships: [{ ...common, relationship_id: "relationship.bound", from_id: "framework.overrun", to_id: "framework.expected", title: "Overrun gives a shifted expected-cost bound", relationship_type: "generalization", formulation_markdown: "$$C^\\pi\\leq b+(C^\\pi-b)_+\\quad\\Longrightarrow\\quad \\mathbb E_\\pi[C^\\pi]\\leq b+\\delta.$$", assumptions_markdown: "The same $b$ and the same admissible policy must be used in both criteria.", explanation_markdown: "The resulting bound uses the shifted threshold, not the original expected-cost budget." }],
    algorithm_families: [{ ...common, algorithm_family_id: "algorithm.trajectory", framework_ids: ["framework.overrun"], title: "Trajectory primal-dual family", formulation_markdown: "$L(\\pi,\\lambda)=J_r(\\pi)-\\lambda(\\mathbb E_\\pi[(C^\\pi-b)_+]-\\delta)$, $\\lambda\\geq0$.", computational_requirements_markdown: "Requires trajectory costs with an explicit discounted-tail approximation." }],
    topics: [],
  },
  scientific_review: {
    scope_markdown: "The lead checked the cost criterion in the referenced entry. Other claims were not checked.",
    limitations: ["The cited source is synthetic test data; no source was scientifically reviewed in this test."],
    findings: [{ finding_id: "finding.original", target: originalRef, status: "corrected", assessment_markdown: "The original entry described a probability, while the formulation uses expected positive excess.", evidence_locations: ["Fixture equation (2)."] }],
  },
};

const original = { ...originalRef, formulation_markdown: "$\\Pr_\\pi(C^\\pi>b)\\leq\\delta$.", explanation_markdown: "Original fixture submission, preserved unchanged.", generation_ref: { ...generation, family: "theory_literature" }, entry_pointer: "/papers/0" };
export const frameworkSources = [{ source_id: "source.fixture", title: "Fixture paper on budget criteria", authors: ["Fixture Author"], year: 2026, identifiers: [{ kind: "doi", value: "10.12345/fixture" }], cards: [{
  ...original, ...currentRef, formulation_markdown: "$\\mathbb E_\\pi[(C^\\pi-b)_+]\\leq\\delta$.", explanation_markdown: "Current lead-corrected fixture entry.",
  lead_revision: { role: "research_lead", entry_sha256: currentRef.entry_sha256, previous_entry_sha256: originalRef.entry_sha256, generation_ref: generation, entry_pointer: "/entry_corrections/0", correction: { target: originalRef, reason_markdown: "Expected excess and exceedance probability are different criteria.", evidence_locations: ["Fixture equation (2)."] } },
  assessment_history: [original],
}, { ...original, role: "data_analyst", family: "empirical_literature", entry_sha256: "d".repeat(64), formulation_markdown: "Independent analyst fixture formulation.", assessment_history: [] }] }];
