import { hasExactRef, humanLabel, phaseLabel } from "./research.js";

const object = (value) => value && typeof value === "object" && !Array.isArray(value);
const recordRef = (value) => {
  const reference = value?.generation_ref || value?.source_ref || value;
  const pointer = value?.entry_pointer || value?.pointer, role = value?.source_role || reference?.source_role;
  return object(reference) && (pointer || role) ? { ...reference, ...(pointer ? { entry_pointer: pointer } : {}), ...(role ? { source_role: role } : {}) } : reference;
};

// An account owns its retained view. Never borrow a newer project's notation
// when its own snapshot is absent or cannot be loaded.
export function notationReference(record) {
  const reference = record?.notation_source_ref || record?._notation?.source_ref || record?.generation_ref || record?.source_ref;
  if (!hasExactRef(reference)) return null;
  const { entry_pointer, card_id, ...account } = reference;
  return account;
}

export function retainedNotation(record) {
  const value = record?._notation;
  return object(value) && Array.isArray(value.entries) ? value : null;
}

export function hasSharedNotation(record) {
  return Boolean(retainedNotation(record) || notationReference(record) && (record?.notation_snapshot || record?.structured?.notation_snapshot || record?._notation_available));
}

export function notationEntryTarget(snapshot, entry, reference) {
  const source = snapshot?.source_ref || reference;
  if (!hasExactRef(source) || !snapshot?.snapshot_sha256 || !entry?.entry_id) return null;
  return { ...source, kind: "notation_entry", snapshot_sha256: snapshot.snapshot_sha256, entry_id: entry.entry_id, object_id: entry.entry_id };
}

export function notationEntrySources(entry) {
  const seen = new Set();
  const tagged = (reference, source_role) => reference && { ...reference, source_role };
  return [...(entry?.ui_source_refs || []), tagged(entry?.definition_ref, "definition"), tagged(entry?.adoption_ref, "adoption"), ...(entry?.source_refs || []).map(reference => tagged(reference, "scientific"))].map(recordRef).filter((reference) => {
    if (!hasExactRef(reference)) return false;
    const key = JSON.stringify([reference.branch, reference.phase, reference.family, reference.generation_id, reference.sha256, reference.entry_pointer]);
    if (seen.has(key)) return false;
    seen.add(key); return true;
  });
}

const sameMethod = (left, right) => left?.stable_id && left.stable_id === right?.stable_id && left.definition_sha256 === right?.definition_sha256;
const accountScopeSource = entry => entry.account_scope_ref || entry.adoption_ref || {};
const sameAccount = (entry, account) => {
  const scope = entry.scope || {}, source = accountScopeSource(entry);
  const family = source.family || source.output_id?.split(".").slice(1).join(".") || scope.account_family;
  return (source.phase || scope.phase) === account?.phase && (source.branch || scope.branch) === account.branch
    && Boolean(source.run_id) && source.run_id === account.run_id && (!source.stage_id || source.stage_id === account.stage_id)
    && (!family || family === account.family);
};
const sourcePhaseLabel = phase => phase ? phaseLabel(phase).replace(/^Phase \d+ - /, "") : "Source";

export function notationGroups(snapshot, { section, methodIdentity, methodScope } = {}) {
  const account = snapshot?.account || {};
  const method = methodScope || methodIdentity || account.method_identity;
  const groups = new Map();
  for (const entry of snapshot?.entries || []) {
    if (entry.status === "retired") continue;
    const scope = entry.scope || {};
    if (methodScope && scope.method_identity && !sameMethod(scope.method_identity, methodScope)) continue;
    const source = accountScopeSource(entry);
    const local = scope.kind === "account" && sameAccount(entry, account);
    const matchingSection = !section || !scope.section || scope.section === section;
    const currentMethod = scope.kind === "method" && (!method || sameMethod(scope.method_identity, method));
    const rank = local && matchingSection ? 0 : currentMethod ? 1 : scope.kind === "study" ? 2 : 3;
    const label = scope.kind === "study" ? "Shared study" : scope.kind === "method" ? scope.label || "Method notation"
      : [sourcePhaseLabel(source.phase || scope.phase), scope.label || (scope.section && humanLabel(scope.section))].filter(Boolean).join(" · ");
    const sourceScope = scope.kind === "account" ? [source.phase, source.branch, source.run_id, source.stage_id, source.output_id || source.family] : null;
    const key = JSON.stringify([rank, label, scope.kind, scope.method_identity || null, scope.phase, scope.branch, scope.account_family, scope.section, sourceScope]);
    if (!groups.has(key)) groups.set(key, { key, label, rank, collapsed: rank === 3, entries: [], scope });
    groups.get(key).entries.push(entry);
  }
  return [...groups.values()].sort((a, b) => a.rank - b.rank);
}

export function correctionDispositions(response) {
  const dispositions = response?.dispositions || (response?.disposition ? [response.disposition] : []);
  return dispositions.flatMap((disposition) => {
    if (!response?.item || disposition.correction_ref?.revision !== response.item.revision) return [];
    const label = { adopted: "Adopted in later work", unchanged: "Definition retained", scientific_revision: "Referred for scientific revision" }[disposition.disposition];
    return label ? [{ label, reason: disposition.reason_markdown, source: disposition.source_ref }] : [];
  });
}

export function notationCorrectionSource(item) {
  return item?.topic === "notation_correction" ? (item.source_refs || []).find((reference) => reference.kind === "notation_entry") : null;
}

// This mirrors phase admission, rather than treating a project-scoped saved
// correction as permission to send a later result into an earlier phase.
export function notationCorrectionApplies(item, { phase, branch, modelRef, admittedRecords, admittedNotation } = {}) {
  if (item?.topic !== "notation_correction") return true;
  const source = notationCorrectionSource(item);
  if (!source || !phase) return false;
  const admitted = { P1: ["P1"], P2: ["P1", "P2"], P3: ["P1", "P2", "P3", "P4"], P4: ["P1", "P2", "P3", "P4"], P5: ["P1", "P2", "P3", "P4", "P5"] };
  if (!admitted[phase]?.includes(source.phase)) return false;
  const exactSource = Array.isArray(admittedRecords) && admittedRecords.some((record) =>
    ["phase", "branch", "family", "generation_id"].every((key) => source[key] === record[key])
    && Boolean(source.content_sha256 || source.sha256)
    && (source.content_sha256 || source.sha256) === (record.content_sha256 || record.sha256));
  const inheritedEntry = ["trunk", branch].includes(source.branch) && Boolean(source.entry_id)
    && admittedNotation?.entries?.some(entry => entry.entry_id === source.entry_id);
  if ((admittedRecords !== undefined || admittedNotation !== undefined) && !exactSource && !inheritedEntry) return false;
  const scope = source.notation_scope || item.notation_scope;
  if (scope?.method_identity && !sameMethod(scope.method_identity, modelRef?.identity || modelRef)) return false;
  return scope?.kind !== "account" || !scope.branch || scope.branch === "trunk" || scope.branch === branch;
}
