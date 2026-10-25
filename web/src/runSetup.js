import { humanLabel } from "./research.js";

const ROLE_LABELS = {
  research_lead: "Research Lead", theorist: "Theorist",
  data_analyst: "Data Analyst", outside_reviewer: "Outside Reviewer",
};

// Use the API's effective member projection: it includes provider-file defaults,
// member overrides, environment keys and retained member account credentials.
export function runSetupStatus(project) {
  if (project?.provider_config?.error) return {
    summary: "Provider settings need attention.",
    issues: [project.provider_config.error], needsOpenAI: false,
  };
  const members = Object.entries(project?.members || {});
  const missing = members.filter(([, member]) => member.credential_configured === false);
  const unknown = members.filter(([, member]) => typeof member.credential_configured !== "boolean");
  const issues = missing.map(([role, member]) => {
    const name = ROLE_LABELS[role] || humanLabel(role);
    if (member.credential_source === "account") return `${name}: OpenAI account credentials are not configured.`;
    if (member.credential_source === "environment" && member.provider_env_key) return `${name}: ${member.provider_env_key} is unavailable to the backend. Check the provider and environment in Team Settings.`;
    return `${name}: provider credentials are not configured. Check Team Settings.`;
  });
  if (unknown.length) issues.push(`Credential status is unavailable for ${unknown.map(([role]) => ROLE_LABELS[role] || humanLabel(role)).join(", ")}. Check Team Settings.`);
  const configured = members.length - missing.length - unknown.length;
  return {
    summary: !members.length ? "Team credential status is unavailable."
      : missing.length || unknown.length ? `Credentials configured for ${configured} of ${members.length} team members.`
        : `Credentials configured for all ${members.length} team members.`,
    issues,
    needsOpenAI: missing.some(([, member]) => member.credential_source === "account"),
  };
}
