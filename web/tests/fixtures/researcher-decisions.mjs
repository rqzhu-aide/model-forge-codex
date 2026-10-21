// Illustrative authoring fixtures, never scientific records in a user project.
const source = (id, index, generation = "generation.illustrative") => ({ kind: "phase_issue", branch: "trunk", phase: "P2", family: "attention_items", generation_id: generation, sha256: "a".repeat(64), run_id: "run.illustrative", package_id: "package.illustrative", object_id: id, entry_pointer: `/attention_items/${index}` });
const item = (id, index, body) => ({ attention_id: id, phase: "P2", target_phase: "P2", branch: "trunk", kind: "researcher_decision", disposition: "open", severity: "major", responsible_role: "research_lead", scope: { kind: "project" }, published_at: "2026-10-20T12:00:00Z", authored_order: index, explanation_target: source(id, index), generation_ref: source(id, index), ...body });

export const populationChoice = item("decision.population", 10, {
  decision_priority: "interpretation", response_kind: "choice", question: "Who must receive a risk prediction?",
  context_markdown: "At prediction time $s$, the target is either all surviving patients, $T>s$, or those alive and under observation, $T>s, C>s$. Here $T$ is death time and $C$ is the end of observation.",
  likely_consequence: "Restricting the population changes who can use the prediction. Neither choice establishes that the available data identify the desired risk.",
  options: [
    { id: "survivors", label: "All surviving patients", consequence: "Matches cohort-wide use. The team must address incomplete follow-up and history before supporting this claim." },
    { id: "observed", label: "Patients still under observation", consequence: "Fits a follow-up workflow. Results cannot automatically be applied to patients who have left observation." },
  ],
  recommendation: "Retain **all surviving patients** for cohort-wide use. Choose the narrower target only if that restriction matches the intended application.",
  information_limits: "The cohort's observation and death-ascertainment records have not been supplied. This illustrative question does not establish censoring assumptions.",
});
export const studyFact = item("decision.information-support", 11, {
  decision_priority: "data", response_kind: "study_fact", question: "What patient, event and feature counts are available?",
  context_markdown: "Supply the eligible patient count, observed deaths, baseline feature dimension and encoded history dimension, if known.",
  likely_consequence: "These counts determine whether the proposed calculation is feasible for the actual cohort. Conditional synthetic work can proceed while the counts remain unknown.",
});
export const resourceChoice = item("decision.prediction-cost", 0, {
  published_at: "2026-10-21T12:00:00Z", decision_priority: "resources", response_kind: "choice", question: "Is a slower offline prediction workflow acceptable?",
  context_markdown: "The proposed history representation may require an offline batch calculation rather than an immediate response during a visit.",
  likely_consequence: "A batch workflow preserves the proposed representation but cannot serve an immediate-use application.",
  options: [
    { id: "batch", label: "Allow offline batch prediction", consequence: "Keep the proposed history representation and evaluate its runtime before planning deployment." },
    { id: "immediate", label: "Require a response during the visit", consequence: "The team must investigate a cheaper representation and assess the scientific effects of that compromise." },
  ], recommendation: "Allow a batch workflow if it fits the intended use. No measured runtime is available yet.",
});
export const legacyQuestion = item("decision.legacy-schedule", 2, {
  question: "How were observation times chosen?", context_markdown: "Earlier work asked whether the visit schedule was fixed in advance or prompted by changing health.",
  likely_consequence: "The team needs collection records to assess what the observed trajectories can support.",
  options: "Earlier discussion mentioned scheduled and event-triggered visits. These are historical prose, not authored selectable responses.",
});
export const decisionFixtureItems = [resourceChoice, studyFact, populationChoice, legacyQuestion];
