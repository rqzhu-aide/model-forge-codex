import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "../../src/styles.css";
import { api } from "../../src/api";
import ProviderFileEditor from "../../src/components/ProviderFileEditor";

// Browser-only synthetic state. No backend mode, network requests, persistent
// browser storage, or real credentials. Backend behavior has separate tests.
let revision = 1;
const token = () => `sha256:synthetic-${revision}`;
const connection = (id, base_url) => ({ type: "custom", id, base_url, model: "synthetic-model", reasoning_effort: "high", api_key_keep: token() });
let saved = { provider: connection("shared", "https://shared.example.test/v1"), members: {
  theorist: connection("theory", "https://theory.example.test/v1"),
  data_analyst: { ...connection("environment", "https://environment.example.test/v1"), api_key_keep: undefined, api_key_env: "SYNTHETIC_PROVIDER_KEY" },
} };
const clone = value => JSON.parse(JSON.stringify(value));
const conflict = () => Object.assign(new Error("The provider file changed on disk since this editor loaded. Refresh the editor and try again."), { status: 409 });
const refreshMarkers = () => {
  for (const table of [saved.provider, ...Object.values(saved.members)]) if (table.api_key_keep) table.api_key_keep = token();
};
const check = table => {
  if (table.type === "custom" && !table.api_key && !table.api_key_env && !table.api_key_keep) throw new Error("Custom providers require exactly one of api_key or api_key_env.");
  if (table.api_key_keep && table.api_key_keep !== token()) throw conflict();
};
api.providerEditor = async () => ({ path: "synthetic-preview/providers.toml", exists: true, token: token(), document: clone(saved) });
api.saveProviderConfig = async (expected, document) => {
  if (expected !== token()) throw conflict();
  for (const table of [document.provider, ...Object.values(document.members)]) check(table);
  saved = clone(document); revision += 1;
  for (const table of [saved.provider, ...Object.values(saved.members)]) {
    if (table.api_key) { delete table.api_key; table.api_key_keep = token(); }
  }
  refreshMarkers();
  return { ok: true, token: token() };
};
api.probeProvider = async (project, role, document) => {
  const table = document.members[role]?.type ? document.members[role] : { ...document.provider, ...document.members[role] };
  check(table);
  return { status: "ok", simulated: true, scope: "draft", model: table.model, summary: "Synthetic fixture verified the selected draft.", elapsed_ms: 2,
    checks: { configuration: "ok", connection: "ok", model_response: "ok", tool_exchange: "ok", final_response: "ok" } };
};
function Preview() {
  const [open, setOpen] = useState(true);
  const [saves, setSaves] = useState(0);
  const [changes, setChanges] = useState(0);
  const [narrow, setNarrow] = useState(false);
  return <main style={{ maxWidth: narrow ? 390 : 1050, margin: "24px auto", padding: 12 }}>
    <h1>Provider credential preview</h1>
    <p>Disposable synthetic fixture. No model requests or saved workspace settings.</p>
    <div className="btnrow">
      <button className="btn ghost" onClick={() => { revision += 1; refreshMarkers(); setChanges(changes + 1); }}>Simulate file change</button>
      <button className="btn ghost" onClick={() => setNarrow(!narrow)}>{narrow ? "Use wide layout" : "Use narrow layout"}</button>
      {!open && <button className="btn" onClick={() => setOpen(true)}>Open provider editor</button>}
    </div>
    <p role="status">Successful saves: {saves}. External changes: {changes}.</p>
    {open && <ProviderFileEditor projectId="project.synthetic-provider-preview" initialRole="theorist" onClose={() => setOpen(false)} onSaved={() => setSaves(saves + 1)} />}
  </main>;
}
createRoot(document.getElementById("root")).render(<Preview />);
