// State model for the provider file editor (Team Settings → Edit provider file).
// Member-first: each member card chooses a shared default, the connected
// OpenAI account, or a complete custom connection. The shared [provider]
// default is optional and edited at the bottom. The file stays the single
// source of truth: the editor loads the raw document, and saves send a
// normalized document back to be validated and rewritten.
export const ROLE_LABELS = {
  research_lead: "Research Lead",
  theorist: "Theorist",
  data_analyst: "Data Analyst",
  outside_reviewer: "Outside Reviewer",
};
export const EDITOR_ROLES = Object.keys(ROLE_LABELS);
export const REASONING_EFFORTS = ["none", "minimal", "low", "medium", "high", "xhigh"];

export const EMPTY_CONNECTION = {
  type: "custom", id: "", base_url: "", model: "gpt-6.1-sol", reasoning_effort: "xhigh",
  credential: "file", api_key: "", api_key_env: "",
};
// mode: "default" (shared default, optional model/effort override) |
//       "openai" (member table with type "openai") |
//       "custom" (member table with a complete custom connection) |
//       "ungoverned" (no member table and no shared default — per-project settings)
// Blank model/effort in "default" mode means "inherit the shared default".
export const EMPTY_MEMBER_EDITOR = {
  mode: "ungoverned", model: "", reasoning_effort: "", id: "", base_url: "",
  credential: "file", api_key: "", api_key_env: "",
};

const text = (value) => String(value ?? "");

// Stored keys are masked by default, keeping the last characters visible so
// the researcher can recognize which key is on file.
export const maskKey = (value) => {
  const key = text(value);
  if (!key) return "";
  return "••••••" + (key.length > 4 ? key.slice(-4) : "");
};

// The local Responses shim has two auth modes: with --auth env (the default)
// the real provider key lives in the shim's own env file and the key stored
// here is only the shim's placeholder; with --auth forward the shim passes
// this connection's key through, so the real key belongs here. The editor
// cannot tell which mode is running, so it explains both.
export const isShimConnection = (connection = {}) =>
  text(connection.id) === "shim" || text(connection.base_url).includes("127.0.0.1:8780");

function connectionFromTable(table = {}) {
  return {
    ...EMPTY_CONNECTION,
    type: text(table.type) === "openai" ? "openai" : "custom",
    id: text(table.id),
    base_url: text(table.base_url),
    model: text(table.model),
    reasoning_effort: text(table.reasoning_effort) || "xhigh",
    credential: text(table.api_key_env) ? "env" : "file",
    api_key: text(table.api_key),
    api_key_env: text(table.api_key_env),
  };
}

const hasDefault = (document) => Boolean(document?.provider && Object.keys(document.provider).length);

// Editor document (raw providers.toml tables) -> editor state.
export function editorFromDocument(document) {
  const governed = hasDefault(document);
  const members = {};
  for (const role of EDITOR_ROLES) {
    const table = document && document.members ? document.members[role] : null;
    if (!table || typeof table !== "object") {
      members[role] = { ...EMPTY_MEMBER_EDITOR, mode: governed ? "default" : "ungoverned" };
    } else if (text(table.type) === "openai") {
      members[role] = { ...EMPTY_MEMBER_EDITOR, mode: "openai", model: text(table.model), reasoning_effort: text(table.reasoning_effort) || "xhigh" };
    } else if (text(table.type)) {
      members[role] = { ...EMPTY_MEMBER_EDITOR, ...connectionFromTable(table), mode: "custom" };
    } else {
      members[role] = { ...EMPTY_MEMBER_EDITOR, mode: "default", model: text(table.model), reasoning_effort: text(table.reasoning_effort) };
    }
  }
  return { shared: governed ? connectionFromTable(document.provider) : null, members };
}

const cleaned = (table) => Object.fromEntries(Object.entries(table)
  .map(([key, value]) => [key, text(value).trim()])
  .filter(([, value]) => value !== ""));

function connectionToTable(connection) {
  const table = { type: connection.type, model: connection.model, reasoning_effort: connection.reasoning_effort };
  if (connection.type === "custom") {
    table.id = connection.id;
    table.base_url = connection.base_url;
    if (connection.credential === "env") table.api_key_env = connection.api_key_env;
    else table.api_key = connection.api_key;
  }
  return cleaned(table);
}

// Editor state -> the PUT document. Blank fields are dropped; a member whose
// choice needs no table (ungoverned, or shared default without overrides)
// has its table removed. A blank shared default removes the [provider] table.
export function documentFromEditor(editor) {
  const document = { provider: editor.shared ? connectionToTable(editor.shared) : {}, members: {} };
  for (const role of EDITOR_ROLES) {
    const member = editor.members ? editor.members[role] : null;
    if (!member || member.mode === "ungoverned") continue;
    if (member.mode === "openai") {
      document.members[role] = cleaned({ type: "openai", model: member.model, reasoning_effort: member.reasoning_effort });
    } else if (member.mode === "custom") {
      document.members[role] = connectionToTable({ ...member, type: "custom" });
    } else {
      const table = cleaned({ model: member.model, reasoning_effort: member.reasoning_effort });
      if (Object.keys(table).length) document.members[role] = table;
    }
  }
  return document;
}

// A save with every field blank deletes the file, restoring per-member settings.
export const blankDocument = () => ({ provider: {}, members: {} });
