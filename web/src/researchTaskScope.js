const isMethodId = (value) => typeof value === "string" && value.startsWith("method.") && value.length > 7;

// A project task can name specific methods without becoming work for every
// method. Missing method identities leave the existing scope rules in charge.
export function researchTaskAppliesToMethod(item, methodId, branch, modelRef) {
  if (item?.kind !== "research_task") return true;
  const selected = [methodId, modelRef?.identity?.stable_id, modelRef?.stable_id, branch].find(isMethodId);
  if (!selected) return true;
  const affected = (Array.isArray(item.affected_record_ids) ? item.affected_record_ids : []).filter(isMethodId);
  return !affected.length || affected.includes(selected);
}
