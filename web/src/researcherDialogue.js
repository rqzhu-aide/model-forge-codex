// Copies of question answers have one owner: their original question or pause.
// Answer references alone can also be evidence for a genuine interpretation.
export function answerContextOwner(item, answers = []) {
  if (!item) return null;
  const linked = answers.flatMap(answer => [answer, ...(answer.history || [])].map(version => ({ ...version, attention_id: answer.attention_id || answer.issue_id })))
    .find(answer => answer.context_ref?.item_id === item.item_id);
  if (linked) return { attention_id: linked.attention_id, question_ref: linked.question_ref || linked.attention?.explanation_target, answer_revision: linked.revision };
  if (item.item_id?.startsWith("context.answer.")) return item.answer_refs?.find(ref => ref.kind === "researcher_answer") || {};
  return null;
}

// Confirmation accepts an account; it does not make the team its researcher
// author. Match the confirmed revision so a later direct correction can retain
// its own attribution. Citations and answer references alone do not name authors.
export function contextAttribution(item, context) {
  const confirmedProposal = context?.proposals?.some(proposal => proposal.status === "confirmed"
    && proposal.item?.item_id === item?.item_id && proposal.confirmed_item_revision != null
    && proposal.confirmed_item_revision === item?.revision);
  if (confirmedProposal || ["evidence_supported", "proposed_assumption"].includes(item?.origin)) {
    return { author: "team", confirmedByResearcher: Boolean(confirmedProposal) };
  }
  return { author: ["researcher_reported", "unknown"].includes(item?.origin) ? "researcher" : "unverified",
    confirmedByResearcher: false };
}

// Scope follows exact identities, never model titles or a branch alone.
export function contextScopeIdentity(scope) {
  if (scope?.kind !== "model") return scope?.kind ? { kind: scope.kind } : null;
  const model = scope.model_ref || {}, reference = model.identity || model;
  const identity = ["stable_id", "version", "definition_sha256"].every(key => reference[key] != null)
    ? { stable_id: reference.stable_id, version: reference.version, definition_sha256: reference.definition_sha256 }
    : { generation_id: model.generation_id, sha256: model.sha256 || model.content_sha256 };
  return { kind: "model", branch: scope.branch, model_ref: identity };
}

export function contextApplies(scope, branch, modelRef) {
  if (scope?.kind === "project") return true;
  if (scope?.kind !== "model" || scope.branch !== branch || !modelRef) return false;
  const expected = scope.model_ref || {};
  const expectedIdentity = expected.identity || expected;
  const actualIdentity = modelRef.identity || modelRef;
  const keys = ["stable_id", "version", "definition_sha256"];
  if (keys.every((key) => expectedIdentity[key] != null)) return keys.every((key) => expectedIdentity[key] === actualIdentity[key]);
  return Boolean(expected.generation_id && (expected.sha256 || expected.content_sha256))
    && expected.generation_id === modelRef.generation_id
    && (expected.sha256 || expected.content_sha256) === (modelRef.sha256 || modelRef.content_sha256);
}
