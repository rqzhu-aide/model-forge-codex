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
