import { hasExactRef } from "./research.js";

export const GOAL_POINTER = "/research_setting/research_goal_markdown";
export function hasConciseP1Account(record) {
  const version = record?.catalog_pin?.catalog_version;
  const match = typeof version === "string" && /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match || !/^[a-f0-9]{64}$/i.test(record.catalog_pin.catalog_manifest_sha256 || "")) return false;
  const [, major, minor] = match.map(Number);
  return major > 1 || major === 1 && minor >= 23;
}

export function goalSource(basis) {
  if (!basis?.research_setting?.research_goal_markdown || !hasExactRef(basis.generation_ref)) return null;
  return { ...basis.generation_ref, kind: "research_goal", entry_pointer: GOAL_POINTER };
}
export function currentGoalSource(records = []) {
  const current = records.find(record => record.branch === "trunk" && record.phase === "P1" && record.family === "research_basis");
  if (!current) return null;
  const reference = { branch: "trunk", phase: "P1", family: "research_basis", generation_id: current.generation_id,
    sha256: current.content_sha256 ?? current.sha256 ?? "", run_id: current.run_id ?? current.source_run_id ?? "",
    stage_id: current.stage_id, package_id: current.package_id };
  return hasExactRef(reference) ? { ...reference, kind: "research_goal", entry_pointer: GOAL_POINTER } : null;
}
export function goalSourceKey(reference) {
  if (!reference) return "";
  return JSON.stringify([reference.branch, reference.phase, reference.family, reference.generation_id, reference.sha256,
    reference.run_id, reference.package_id, reference.entry_pointer]);
}
export function goalContextTarget(context, basis) {
  const source = goalSource(basis);
  return context?.dialogue_target && source ? { ...context.dialogue_target, goal_source_ref: source,
    phase: "P1", branch: "trunk", label: "Research goal", responsible_role: "research_lead" } : null;
}
export function goalCorrections(context, reference) {
  return (context?.items || []).filter(item => item.status === "confirmed" && item.topic === "research_goal"
    && item.scope?.kind === "project" && item.source_refs?.some(ref => goalSourceKey(ref) === goalSourceKey(reference)));
}
