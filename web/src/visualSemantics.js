// These colors describe execution, not the scientific result of the work.
// In particular, a stopped or unrecognized state must never imply success.
const active = new Set(["requested", "running", "validating", "correcting", "promoting", "stopping"]);
const complete = new Set(["published", "assessed", "completed", "succeeded"]);
const failed = new Set(["failed", "infrastructure_error", "input_error", "output_error", "timed_out"]);

export function executionStatus(state) {
  const value = typeof state === "string" && state.trim() ? state.trim() : "unknown";
  const label = value === "awaiting_user" ? "Waiting for your direction"
    : value === "stopping" ? "Stopping work"
      : value.replace(/[_.-]+/g, " ").replace(/^\w/, (letter) => letter.toUpperCase());
  const tone = value === "awaiting_user" ? "warn"
    : active.has(value) ? "run"
      : complete.has(value) ? "ok"
        : failed.has(value) ? "fail" : "mut";
  return { tone, label };
}
