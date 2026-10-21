import { legacySummaryForDisplay } from "./researchMath.js";
import { contextApplies } from "./researcherDialogue.js";

// Join authored records by identity and producing run, never by title or prose.
export const proposalKey = (proposal) => `${proposal.generation_ref?.run_id || ""}:${proposal.proposal_id}`;
export const methodIdOf = (proposal) => proposal?.method?.identity?.stable_id;
export const summaryForDisplay = legacySummaryForDisplay;
// The writing contract belongs to the producing package, not the installed app.
// Missing or malformed provenance keeps the historical account explicit.
export function hasConciseP2Account(record) {
  const pin = record?.catalog_pin;
  const match = typeof pin?.catalog_version === "string" && /^(\d+)\.(\d+)\.(\d+)$/.exec(pin.catalog_version);
  if (!match || !/^[a-f0-9]{64}$/i.test(pin.catalog_manifest_sha256 || "")) return false;
  const [, major, minor] = match.map(Number);
  return major > 1 || major === 1 && minor >= 24;
}
export const catalogSelectionKey = (method) => {
  const identity = method.identity || method.current_identity || method.definition?.identity || {};
  return `catalog:${method.method_id || identity.stable_id}:${identity.version ?? method.version ?? ""}:${identity.definition_sha256 || ""}`;
};
export const catalogOnlyMethods = (methods = [], proposals = []) => methods.filter((method) =>
  !proposals.some((proposal) => sameMethodIdentity(proposal.method?.identity, method.identity || method.current_identity)));
export const sameMethodIdentity = (a, b) => Boolean(a?.stable_id && b?.stable_id &&
  a.stable_id === b.stable_id && a.version === b.version && a.definition_sha256 === b.definition_sha256);

export function catalogMethodForProposal(proposal, methods = []) {
  return methods.find((method) => sameMethodIdentity(proposal?.method?.identity, method.identity || method.current_identity));
}

// A proposal whose exact identity is absent from the catalog while its stable
// id lives on under a different version or definition is superseded history,
// not a retained method. "Earlier run" alone never marks a method superseded.
export function successorMethodForProposal(proposal, methods = []) {
  const stableId = methodIdOf(proposal);
  if (!stableId || catalogMethodForProposal(proposal, methods)) return null;
  return methods.find((method) => (method.identity || method.current_identity)?.stable_id === stableId) || null;
}

export function comparisonForProposal(proposal, comparisons = []) {
  const run = proposal.generation_ref?.run_id;
  const comparison = comparisons.find((item) => run && item.generation_ref?.run_id === run &&
    item.method_dispositions?.some((entry) => entry.proposal_id === proposal.proposal_id));
  return comparison ? { comparison, disposition: comparison.method_dispositions.find((entry) => entry.proposal_id === proposal.proposal_id) } : null;
}

// These authored sections live in indexed rows of an exact source record.
// Open the cited paragraph directly instead of the report's unrelated overview.
export function proposalSectionSource(record, proposalId, collection, field) {
  const rows = record?.[collection];
  if (!record?.generation_ref || !Array.isArray(rows)) return null;
  const index = rows.findIndex((row) => row?.proposal_id === proposalId);
  if (index < 0 || typeof rows[index][field] !== "string" || !rows[index][field].trim()) return null;
  return { ...record.generation_ref, entry_pointer: `/${collection}/${index}/${field}` };
}

export function orderedProposals(proposals = []) {
  const order = { research_lead: 0, theorist: 1, data_analyst: 2 };
  return [...proposals].sort((a, b) => (order[a.role] ?? 3) - (order[b.role] ?? 3));
}

export function methodRequests(items = [], methodId, branch, { includeShared = false, modelRef } = {}) {
  return items.filter((item) => {
    if (!item) return false;
    if (item.scope?.kind === "model") {
      // P2 publishes exact candidate identities on trunk before a model branch
      // exists. Reading that candidate later keeps its authored trunk scope.
      const identity = item.scope.model_ref?.identity || item.scope.model_ref;
      const source = item.generation_ref;
      const onCandidateBranch = item.phase === "P2" && item.branch === "trunk"
        && source?.phase === "P2" && source.branch === "trunk" && source.family === "attention_items"
        && ["generation_id", "sha256", "run_id", "package_id"].every((key) => typeof source[key] === "string" && source[key].trim())
        && item.scope.branch === "trunk" && branch === identity?.stable_id
        && typeof identity?.stable_id === "string" && identity.stable_id.trim()
        && Number.isInteger(identity.version) && identity.version > 0
        && typeof identity.definition_sha256 === "string" && identity.definition_sha256.trim();
      const scopeBranch = onCandidateBranch ? "trunk" : branch;
      return contextApplies(item.scope, scopeBranch, modelRef);
    }
    if (item.scope?.kind === "project") return includeShared;
    const origin = item.branch || item.branch_id;
    if (origin !== "trunk") return origin === branch || origin === methodId;
    // P1 references name setting/literature objects, not method branches.
    const ids = item.phase === "P2" ? item.affected_record_ids || [] : [];
    return ids.length ? Boolean(methodId && ids.includes(methodId)) : includeShared;
  });
}

export const methodAnswers = (answers = [], methodId, branch, options) => answers.filter((answer) =>
  methodRequests([answer.attention], methodId, branch, options).length);

// Selection rows come from the catalog assessment: each disposition is joined to
// its proposal by id and producing run, never by title or prose.
export function comparisonCandidates(comparison, proposals = [], status = "retain") {
  const runId = comparison?.generation_ref?.run_id;
  return (comparison?.method_dispositions || [])
    .filter((disposition) => disposition?.status === status)
    .map((disposition) => ({ disposition, proposal: proposals.find((proposal) =>
      proposal.proposal_id === disposition.proposal_id && (!runId || proposal.generation_ref?.run_id === runId)) }))
    .filter((entry) => entry.proposal);
}

// The lead's modification options live on the run-matched catalog assessment and
// name the exact proposal they modify.
export const modificationOptionsFor = (comparison, proposalId) =>
  (comparison?.modification_options || []).filter((option) => option?.applies_to === proposalId);

// A recorded selection is a registered catalog method identity-matched to a proposal.
export function recordedSelections(proposals = [], methods = []) {
  const seen = new Set();
  return proposals.map((proposal) => catalogMethodForProposal(proposal, methods)).filter((method) => {
    if (!method?.registered || seen.has(method.method_id)) return false;
    seen.add(method.method_id);
    return true;
  });
}
