import React from "react";
import { providerLabel } from "../teamSettings";
import { ActionButton } from "./Visuals";

export function ProviderConfigNotice({ config, refreshing = false, disabled = false, onRefresh, onEdit }) {
  if (!config) return null;
  const invalid = Boolean(config.error);
  return <div className={`provider-config-notice ${invalid ? "invalid" : config.active ? "active" : ""}`} role={invalid ? "alert" : undefined}>
    <div>
      <strong>{invalid ? "Provider settings need attention" : "Agent models and providers"}</strong>
      <p>{invalid ? "Open configuration to fix provider settings. Member instructions and token thresholds can still be saved."
        : config.active ? "Choose each member's provider, model, API key, and reasoning effort. Shared provider defaults and member overrides apply to the next turn across all projects."
          : "Configure agent models and providers across projects, or use the member settings below for this project."}</p>
      {invalid && <p className="provider-config-error">{config.error}</p>}
    </div>
    <div className="provider-config-actions">
      {onEdit && <ActionButton action="edit" variant="primary" onClick={onEdit} disabled={disabled}>Configure agent models and providers</ActionButton>}
      <ActionButton action="retry" onClick={onRefresh} disabled={disabled || refreshing}>{refreshing ? "Refreshing…" : "Refresh settings"}</ActionButton>
    </div>
  </div>;
}

export function EffectiveProviderSettings({ member, invalid = false, onEdit, disabled = false }) {
  if (invalid) return <div className="effective-provider"><p className="note warn">Provider settings are unavailable until the provider file is corrected.</p>
    {onEdit && <ActionButton action="edit" variant="primary" onClick={onEdit} disabled={disabled}>Configure provider</ActionButton>}</div>;
  const source = { file: "Provider file", environment: "Host environment", account: "OpenAI account" }[member.credential_source];
  return <div className="effective-provider">
    <div className="effective-provider-heading"><div>Saved connection <span className="note">Shared across projects. Use Configure provider to change this member's model, provider, API key, or reasoning effort.</span></div>
      {onEdit && <ActionButton action="edit" variant="primary" onClick={onEdit} disabled={disabled}>Configure provider</ActionButton>}</div>
    <dl>
      <div><dt>Provider</dt><dd>{providerLabel(member)}</dd></div>
      <div><dt>Agent model</dt><dd>{member.model || "Not specified"}</dd></div>
      <div><dt>Reasoning effort</dt><dd>{member.reasoning_effort || "Not specified"}</dd></div>
      {source && <div><dt>Credentials</dt><dd>{source}{typeof member.credential_configured === "boolean" && <span className={member.credential_configured ? "provider-status" : "provider-status missing"}>{member.credential_configured ? "Configured" : "Not configured"}</span>}</dd></div>}
      {member.provider === "custom" && member.provider_base_url && <div className="provider-detail-wide"><dt>Base URL</dt><dd>{member.provider_base_url}</dd></div>}
      {member.credential_source === "environment" && member.provider_env_key && <div className="provider-detail-wide"><dt>API key environment variable</dt><dd>{member.provider_env_key}</dd></div>}
    </dl>
  </div>;
}
