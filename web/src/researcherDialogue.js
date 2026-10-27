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

// Scope follows exact identities, never model titles or a branch alone.
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
