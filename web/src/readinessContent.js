const steps = { P1: "Complete a literature study", P2: "Develop and select a model", P3: "Complete theory development for the selected model", P4: "Complete an evaluation for the selected model", P5: "Assemble a technical report" };
const records = { theory_record: "the theoretical account", complete_theory: "the theoretical account", empirical_evidence_index: "the experimental evidence", empirical_index_candidate: "the experimental evidence", empirical_synthesis: "the experimental conclusions", empirical_synthesis_candidate: "the experimental conclusions", implementation_record: "the implementation and checks", implementation_candidate: "the implementation and checks", manuscript: "the manuscript", manuscript_candidate: "the manuscript", literature_synthesis: "the literature account", research_basis: "the research setting", technical_report: "the technical report", technical_report_candidate: "the technical report", method_catalog: "the model proposals" };
export function readinessReason(reason) {
  // Prefer stable reason codes when supplied; exact known legacy templates are
  // supported without reinterpreting unfamiliar diagnostics.
  if (reason && typeof reason === "object") {
    const known = { missing_report: "Assemble a technical report before requesting report review.", missing_manuscript: "Create a manuscript draft before requesting review.", method_not_selected: "Select a model before starting this work.", method_changed: "Select the current model version before starting this work." };
    return known[reason.code] || reason.message || "A required input is unavailable. Inspect the readiness details.";
  }
  const text = String(reason || "");
  const missing = text.match(/^(P[1-5]) has no published records on .+$/);
  if (missing) return `${steps[missing[1]]} before starting this work.`;
  const incomplete = text.match(/^(P[1-5]) needs (?:its complete current|a complete current) ([a-z_]+)(?: record| aligned to .+)$/);
  if (incomplete && records[incomplete[2]]) return `${steps[incomplete[1]]} so ${records[incomplete[2]]} is available for the current model.`;
  if (text === "A complete current theory package is required for this action") return "Complete theory development for the current model before requesting this work.";
  if (text === "A current manuscript is required for review") return "Create a manuscript draft before requesting review.";
  if (text === "Select an active registered method") return "Select a model before starting this work.";
  if (text === "The selected method changed; select its current definition before running") return "Select the current model version before starting this work.";
  return text;
}
export const readinessMessages = (reasons = []) => [...new Set(reasons.map(readinessReason).filter(Boolean))];
