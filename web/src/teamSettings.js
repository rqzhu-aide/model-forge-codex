export const EMPTY_MEMBER_FORM = {
  model: "gpt-6.1-sol", reasoning_effort: "xhigh", provider: "openai",
  provider_id: "", provider_base_url: "", provider_env_key: "", soul: "",
  auto_compact_tokens: "0", max_turn_input_tokens: "0",
};

const PROVIDER_FIELDS = ["model", "reasoning_effort", "provider", "provider_id", "provider_base_url", "provider_env_key"];
const MEMBER_FIELDS = ["soul", "auto_compact_tokens", "max_turn_input_tokens"];

// The backend marks each file-governed member with provider_source "file"; an
// invalid file blocks provider edits everywhere until repaired.
export const providerIsControlled = (member = {}, config = {}) => Boolean(config?.error || member.provider_source === "file");
const editableFields = (member, config) => providerIsControlled(member, config) ? MEMBER_FIELDS : [...PROVIDER_FIELDS, ...MEMBER_FIELDS];

export function memberForm(member = {}, draft = {}, config = {}) {
  const form = Object.fromEntries(Object.entries(EMPTY_MEMBER_FORM).map(([key, fallback]) => [key, String(member[key] ?? fallback)]));
  for (const key of editableFields(member, config)) {
    if (draft && Object.hasOwn(draft, key)) form[key] = String(draft[key] ?? "");
  }
  return form;
}

// Persist only editable changes, so an old manual-provider draft cannot override
// the file's effective settings when refreshing or switching team members.
export function memberDraft(member, form, config) {
  const baseline = memberForm(member);
  return Object.fromEntries(editableFields(member, config).filter((key) => String(form[key] ?? "") !== baseline[key]).map((key) => [key, String(form[key] ?? "")]));
}

export function refreshMemberDrafts(members, drafts, config) {
  return Object.fromEntries(Object.entries(members).flatMap(([role, member]) => {
    const draft = memberDraft(member, memberForm(member, drafts[role], config), config);
    return Object.keys(draft).length ? [[role, draft]] : [];
  }));
}

export function memberUpdatePayload(member, form, config) {
  const payload = Object.fromEntries(editableFields(member, config).map((key) => [key, form[key]]));
  for (const key of ["auto_compact_tokens", "max_turn_input_tokens"]) {
    const value = String(form[key] || "0");
    if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Error("Token settings must be nonnegative whole numbers.");
    payload[key] = Number(value);
  }
  return payload;
}

export const providerLabel = (member = {}) => member.provider === "custom" ? member.provider_id || "Custom provider" : "OpenAI account";
