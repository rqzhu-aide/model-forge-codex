import { hasExactRef, humanLabel, sameRef } from "./research.js";
import { sameMethodIdentity } from "./methodWorkspace.js";

export const isEmpiricalTarget = (target) => target?.kind === "empirical_question" && target?.phase === "P4";

export const isTheoryComponentTarget = (target) => hasExactRef(target) && target.phase === "P3"
  && ["theory_record", "complete_theory"].includes(target.family)
  && ["statement", "assumption"].includes(target.kind) && Boolean(target.object_id);

export function theoryComponentRequest(intent, target, label) {
  if (!isTheoryComponentTarget(target)) return null;
  const assessment = intent === "assessment";
  const targetLabel = label || humanLabel(target.object_id);
  return {
    phase: "P3", branch: target.branch, target: structuredClone(target), targetLabel,
    mode: assessment ? "p3.assessment" : "p3.theory_revision",
    title: assessment ? "Request an assessment" : "Request a theory revision",
    instructions: assessment
      ? `Assess the selected component "${targetLabel}" in this exact theory source. Explain its reasoning, qualifications, support, and open questions. Save a separate assessment without changing the published theory.`
      : `Revise the current theory account, scoped to the selected component "${targetLabel}" and its affected consequences. Preserve stable statement identities and unrelated statements. Account for changed conditions, dependent claims, and relevant empirical interpretations. Publish the resulting qualified account after the theorist's work, independent analyst audit, and lead integration.`,
  };
}

export function empiricalFollowupRequest(question) {
  if (!isEmpiricalTarget(question?.followup_target) || !hasExactRef(question.followup_target)) return null;
  return {
    phase: "P4", branch: question.followup_target.branch,
    title: "Request another experimental check", targetLabel: question.title || question.hypothesis,
    target: structuredClone(question.followup_target),
    caseLabels: question.case_labels || (question.followup_target.case_ids || []).map(humanLabel),
    theoryContext: question.theory_context,
    instructions: `Revisit this experimental question: ${question.title || question.hypothesis || question.question_id}\n\n${question.caption || question.design || ""}\n\nUse the exact inspected evaluation as context. Assess this question against the current method and theory, and explain what the new check establishes and what remains unresolved.`,
  };
}

export function modesForRequest(request, modes) {
  if (request.phase === "P2") return modes.filter((m) => m.mode === "p2.full_catalog");
  if (isEmpiricalTarget(request.target)) return modes.filter((m) => ["p4.preliminary", "p4.comprehensive"].includes(m.mode));
  if (!request.target) return modes.filter((m) => m.mode !== "p3.assessment");
  return modes.filter((m) => m.mode === (request.mode === "p3.assessment" ? "p3.assessment" : "p3.theory_revision"));
}

export function defaultTheoryMode(modes) {
  return modes.find(item => item.mode === "p3.theory_revision" && item.ready)?.mode
    || modes.find(item => item.mode === "p3.theory_establishment")?.mode || "";
}

export function targetIsStale(request, currentTargetRef, currentMethodRef, currentTheoryAligned) {
  // P4 follow-ups deliberately retain the inspected historical generation.
  // The server verifies that generation and its selected objects at launch.
  if (!request.target || isEmpiricalTarget(request.target)) return false;
  if (!hasExactRef(currentTargetRef) || !sameRef(request.target, currentTargetRef)
    || request.branch && request.target.branch !== request.branch || currentTheoryAligned === false) return true;
  // Prepared component work belongs to both the inspected theory and the exact
  // method. A retained theory reference alone cannot establish applicability.
  if (request.methodRef !== undefined || currentMethodRef !== undefined) {
    const exactMethod = ref => Boolean(ref?.stable_id && Number.isInteger(ref.version) && ref.definition_sha256);
    return !exactMethod(request.methodRef) || !exactMethod(currentMethodRef) || !sameMethodIdentity(request.methodRef, currentMethodRef);
  }
  return false;
}

export function theoryLinkDestination(reference, currentReference) {
  if (!hasExactRef(reference)) return "unavailable";
  return sameRef(reference, currentReference) ? "current_graph" : "inspected_source";
}

export function theoryComponent(document, id) {
  const entries = [...(document?.statements || []), ...(document?.assumptions || [])];
  return entries.find((item) => item.statement_id === id || item.assumption_id === id);
}
