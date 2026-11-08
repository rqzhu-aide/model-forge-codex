// Poll responses are JSON, so compare their actual contents rather than a run
// or generation ID. Unchanged children keep their mounted reader identities.
export function reuseUnchangedJson(previous, next) {
  if (Object.is(previous, next)) return previous;
  if (!previous || !next || typeof previous !== "object" || typeof next !== "object"
    || Array.isArray(previous) !== Array.isArray(next)) return next;
  const keys = Object.keys(next); const previousKeys = Object.keys(previous);
  let unchanged = keys.length === previousKeys.length;
  let reusedChild = false;
  const values = keys.map((key) => {
    const exists = Object.hasOwn(previous, key);
    const value = exists ? reuseUnchangedJson(previous[key], next[key]) : next[key];
    unchanged &&= exists && Object.is(value, previous[key]);
    reusedChild ||= !Object.is(value, next[key]);
    return value;
  });
  if (unchanged) return previous;
  if (!reusedChild) return next;
  return Array.isArray(next) ? values : Object.fromEntries(keys.map((key, index) => [key, values[index]]));
}
