// Provider connection probe helpers (Team Settings + provider file editor).
// A probe result applies to one exact settings snapshot; these signatures let
// the UI drop a stale result the moment the relevant settings change.

export const PROBE_CHECK_ORDER = ["configuration", "connection", "model_response", "tool_exchange", "final_response"];

export const PROBE_CHECK_LABELS = {
  configuration: "Configuration",
  connection: "Connection",
  model_response: "Model response",
  tool_exchange: "Tool exchange",
  final_response: "Final response",
};

const pick = (source, keys) =>
  Object.fromEntries(keys.map((key) => [key, source && source[key] != null ? source[key] : null]));

const MEMBER_PROBE_FIELDS = [
  "provider", "provider_id", "provider_base_url", "provider_env_key",
  "model", "reasoning_effort", "provider_source", "credential_source", "credential_configured",
];

// Team Settings probes the SAVED member settings. The signature also covers
// the unsaved form draft and the provider file status, so editing the form or
// changing the file clears a result that no longer describes what is shown.
export function teamProbeSignature(member, form, providerConfig, role = null) {
  return JSON.stringify({
    role,
    member: pick(member, MEMBER_PROBE_FIELDS),
    form: pick(form, ["provider", "provider_id", "provider_base_url", "provider_env_key", "model", "reasoning_effort"]),
    file: providerConfig ? { active: Boolean(providerConfig.active), error: providerConfig.error || null } : null,
  });
}

export const hasUnsavedProviderChanges = (member, form) =>
  ["provider", "provider_id", "provider_base_url", "provider_env_key", "model", "reasoning_effort"]
    .some((key) => String(member?.[key] ?? "") !== String(form?.[key] ?? ""));

// The provider file editor probes the UNSAVED draft document. The signature
// covers exactly the tables that become this member's draft document.
export function editorProbeSignature(editor, role) {
  return JSON.stringify({ member: editor?.members?.[role] ?? null, shared: editor?.shared ?? null });
}

// Signature-keyed probe lifecycle, independent of the view layer: a signature
// change clears the displayed result and retires any in-flight probe, so a
// stale response can never be shown against settings it did not test.
export class ProbeController {
  constructor() {
    this.signature = null;
    this.runId = 0;
    this.state = { pending: false, result: null, error: null };
  }

  // Sync to the current settings signature; returns true when state was reset.
  sync(signature) {
    if (this.signature === signature) return false;
    this.signature = signature;
    this.runId += 1;
    this.state = { pending: false, result: null, error: null };
    return true;
  }

  async probe(onProbe) {
    const id = ++this.runId;
    this.state = { pending: true, result: null, error: null };
    try {
      const result = await onProbe();
      if (id === this.runId) this.state = { pending: false, result, error: null };
    } catch (error) {
      if (id === this.runId) this.state = { pending: false, result: null, error };
    }
    return this.state;
  }
}
