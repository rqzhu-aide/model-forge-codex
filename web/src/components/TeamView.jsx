import React, { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { humanLabel } from "../research";
import { EMPTY_MEMBER_FORM, memberForm, memberDraft, refreshMemberDrafts, memberUpdatePayload, providerIsControlled, providerLabel } from "../teamSettings";
import { ProviderConfigNotice, EffectiveProviderSettings } from "./ProviderSettings";
import ProviderFileEditor from "./ProviderFileEditor";
import { ProviderProbe } from "./ProviderProbe";
import { hasUnsavedProviderChanges, teamProbeSignature } from "../providerProbe";
import { REASONING_EFFORTS } from "../providerEditor";
import { ActionButton } from "./Visuals";

const ROLE_LABELS = {
  research_lead: "Research Lead",
  theorist: "Theorist",
  data_analyst: "Data Analyst",
  outside_reviewer: "Outside Reviewer",
};
const orderedRoles = (members) => [
  ...Object.keys(ROLE_LABELS).filter((role) => Object.hasOwn(members, role)),
  ...Object.keys(members).filter((role) => !Object.hasOwn(ROLE_LABELS, role)),
];
const roleLabel = (role) => ROLE_LABELS[role] || humanLabel(role);

export default function TeamView({ projectId }) {
  const [members, setMembers] = useState({});
  const [options, setOptions] = useState({ openai_models: [] });
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState(EMPTY_MEMBER_FORM);
  const [providerConfig, setProviderConfig] = useState(null);
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [optionsError, setOptionsError] = useState(null);
  const [editingProviderFile, setEditingProviderFile] = useState(false);
  const editorRegion = useRef(null);
  const drafts = useRef({});
  const saveLock = useRef(false);
  const selectedRef = useRef(null);
  const loadId = useRef(0);
  const draftKey = `model-forge-team-draft:${projectId}`;

  const persistDrafts = () => { try { sessionStorage.setItem(draftKey, JSON.stringify(drafts.current)); } catch {} };
  const load = async () => {
    const requestId = ++loadId.current;
    setRefreshing(true);
    const [projectResult, optionsResult] = await Promise.allSettled([api.project(projectId), api.providerOptions()]);
    if (requestId !== loadId.current) return;
    const nextOptions = optionsResult.status === "fulfilled" ? optionsResult.value : null;
    if (nextOptions) { setOptions({ ...nextOptions, openai_models: nextOptions.openai_models || [] }); setOptionsError(null); }
    else setOptionsError(optionsResult.reason.message);
    if (projectResult.status === "fulfilled") {
      const project = projectResult.value;
      const loadedMembers = project.members || {};
      const config = project.provider_config?.error ? project.provider_config : nextOptions?.provider_config?.error ? nextOptions.provider_config : project.provider_config || nextOptions?.provider_config || null;
      setProviderConfig(config);
      setMembers(loadedMembers);
      drafts.current = refreshMemberDrafts(loadedMembers, drafts.current, config);
      persistDrafts();
      const role = Object.hasOwn(loadedMembers, selectedRef.current) ? selectedRef.current : orderedRoles(loadedMembers)[0];
      selectedRef.current = role || null;
      setSelected(role || null);
      setForm(role ? memberForm(loadedMembers[role], drafts.current[role], config) : EMPTY_MEMBER_FORM);
      setError(null);
    } else {
      setError(projectResult.reason.message);
      // A valid options response has no effective member values. Keep the last
      // coherent snapshot if the project refresh fails, but block a known bad file.
      if (nextOptions?.provider_config?.error) setProviderConfig(nextOptions.provider_config);
    }
    setLoading(false); setRefreshing(false);
  };
  useEffect(() => {
    drafts.current = {};
    try { const stored = JSON.parse(sessionStorage.getItem(draftKey) || "{}"); if (stored && typeof stored === "object" && !Array.isArray(stored)) drafts.current = stored; } catch {}
    selectedRef.current = null;
    setSelected(null); setMembers({}); setProviderConfig(null); setLoading(true); setMsg(null); setEditingProviderFile(false);
    load();
    return () => { loadId.current += 1; };
  }, [projectId]);
  useEffect(() => { if (editingProviderFile) editorRegion.current?.focus(); }, [editingProviderFile]);
  const remember = (next) => {
    if (saving) return;
    const reconciled = memberForm(members[selected], next, providerConfig);
    setForm(reconciled);
    if (selected) drafts.current[selected] = memberDraft(members[selected], reconciled, providerConfig);
    persistDrafts();
    setMsg(null);
  };
  const choose = (role) => { if (saving) return; selectedRef.current = role; setSelected(role); setForm(memberForm(members[role], drafts.current[role], providerConfig)); setMsg(null); };
  const dirty = selected && Object.keys(memberDraft(members[selected], form, providerConfig)).length > 0;
  const controlled = selected && providerIsControlled(members[selected], providerConfig);
  const providerDirty = !controlled && selected && hasUnsavedProviderChanges(members[selected], form);
  const reasoningEfforts = options.reasoning_efforts?.length ? options.reasoning_efforts : REASONING_EFFORTS;

  const set = (k) => (e) => remember({ ...form, [k]: e.target.value });

  const save = async () => {
    if (saveLock.current) return;
    let payload;
    try { payload = memberUpdatePayload(members[selected], form, providerConfig); } catch (e) { setError(e.message); return; }
    saveLock.current = true; setSaving(true);
    setError(null); setMsg(null);
    try {
      await api.updateMember(projectId, selected, payload);
      delete drafts.current[selected];
      persistDrafts();
      setMsg("Saved. Applies to this member's next turn.");
      await load();
    } catch (e) { setError(e.message); } finally { saveLock.current = false; setSaving(false); }
  };

  return (
    <>
      <header className="page">
        <div>
          <h1 className="serif">Team Settings</h1>
          <div className="sub">Agent models, providers, instructions, and context settings.
            Changes apply to the next turn.</div>
        </div>
      </header>

      {error && <div className="error" role="alert">{error} <ActionButton action="retry" onClick={load} disabled={saving || refreshing}>Reload settings</ActionButton></div>}
      {loading && <p className="note" role="status">Loading team settings…</p>}
      {optionsError && <div className="note warn">Agent model choices could not be refreshed: {optionsError} <ActionButton action="retry" onClick={load} disabled={saving || refreshing}>Retry refresh</ActionButton></div>}
      <ProviderConfigNotice config={providerConfig} refreshing={refreshing} disabled={saving} onRefresh={load}
        onEdit={editingProviderFile ? undefined : () => setEditingProviderFile(true)} />
      {editingProviderFile && <section className="team-provider-editor-region" ref={editorRegion} tabIndex={-1} aria-label="Configure agent models and providers">
        <ProviderFileEditor projectId={projectId} initialRole={selected} reasoningEfforts={reasoningEfforts}
          onSaved={load} onClose={() => setEditingProviderFile(false)} />
      </section>}
      {msg && <div className="banner">{msg}</div>}
      {dirty && <div className="context-note">Unsaved changes are kept in this browser session when you switch members or return to research. <button className="source-link" disabled={saving} onClick={() => { delete drafts.current[selected]; persistDrafts(); setForm(memberForm(members[selected])); }}>Discard this member's draft</button></div>}

      <div className="grid team-grid" hidden={editingProviderFile}>
        <div className="card">
          <h2>Team</h2>
          {orderedRoles(members).map((role) => (
            <button key={role} className={`member ${role === selected ? "sel" : ""}`} disabled={saving}
              onClick={() => choose(role)} aria-pressed={role === selected}>
              <b>{roleLabel(role)}</b>
              <div className="meta">
                {providerConfig?.error ? "Provider file needs attention" : <>{providerLabel(members[role])}{" · "}{members[role].model} · {members[role].reasoning_effort}</>}
              </div>
            </button>
          ))}
        </div>

        {selected && (
          <div>
            <div className="card">
              <h2>{roleLabel(selected)} · agent model &amp; provider</h2>
              <div className="body">
                {controlled ? <EffectiveProviderSettings member={members[selected]} invalid={Boolean(providerConfig?.error)}
                  onEdit={() => setEditingProviderFile(true)} disabled={saving} /> : <>
                <div className="team-provider-actions"><span className="note">These settings apply to this project.</span>
                  <ActionButton action="edit" onClick={() => setEditingProviderFile(true)} disabled={saving}>Configure provider and API key</ActionButton></div>
                <div className="field">
                  <label>Provider mode</label>
                  <div className="segs">
                    <button className={`seg ${form.provider === "openai" ? "on" : ""}`} aria-pressed={form.provider === "openai"}
                      onClick={() => remember({ ...form, provider: "openai" })}>OpenAI account</button>
                    <button className={`seg ${form.provider === "custom" ? "on" : ""}`} aria-pressed={form.provider === "custom"}
                      onClick={() => remember({ ...form, provider: "custom" })}>Custom provider</button>
                  </div>
                </div>

                {form.provider === "openai" ? (
                  <div className="tworow">
                    <div className="field">
                      <label>Agent model</label>
                      <input aria-label="Agent model" value={form.model} onChange={set("model")} list="team-model-options" />
                      <datalist id="team-model-options">{options.openai_models.map((m) => <option key={m} value={m} />)}</datalist>
                    </div>
                    <div className="field">
                      <label>Reasoning effort</label>
                      <select aria-label="Reasoning effort" value={form.reasoning_effort} onChange={set("reasoning_effort")}>
                        {!reasoningEfforts.includes(form.reasoning_effort) && <option value={form.reasoning_effort}>{form.reasoning_effort} (current setting)</option>}
                        {reasoningEfforts.map((r) => <option key={r}>{r}</option>)}
                      </select>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="tworow">
                      <div className="field">
                        <label>Provider ID</label>
                        <input aria-label="Provider ID" value={form.provider_id} onChange={set("provider_id")} placeholder="custom_provider" />
                      </div>
                      <div className="field">
                        <label>Agent model</label>
                        <input aria-label="Agent model" value={form.model} onChange={set("model")} placeholder="model-id" />
                      </div>
                    </div>
                    <div className="tworow">
                      <div className="field">
                        <label>Base URL</label>
                        <input aria-label="Base URL" value={form.provider_base_url} onChange={set("provider_base_url")}
                          placeholder="https://api.example.com/v1" />
                        <div className="hint">Responses-compatible endpoint.</div>
                      </div>
                      <div className="field">
                        <label>API key environment variable</label>
                        <input aria-label="API key environment variable" value={form.provider_env_key} onChange={set("provider_env_key")}
                          placeholder="PROVIDER_API_KEY" />
                        <div className="hint">Variable name only; the key stays on the host.</div>
                      </div>
                    </div>
                      <div className="field">
                      <label>Reasoning effort</label>
                      <select aria-label="Reasoning effort" value={form.reasoning_effort} onChange={set("reasoning_effort")}>
                        {!reasoningEfforts.includes(form.reasoning_effort) && <option value={form.reasoning_effort}>{form.reasoning_effort} (current setting)</option>}
                        {reasoningEfforts.map((r) => <option key={r}>{r}</option>)}
                      </select>
                    </div>
                  </>
                )}
                </>}

                {members[selected].provider === "openai" && !members[selected].credential_configured &&
                  <p className="note warn">Connect your account in Workspace → OpenAI Account, then return here to test this member. Choose a model and reasoning level available to that account.</p>}
                {providerDirty && <div className="team-provider-actions"><ActionButton action="save" variant="primary" onClick={save} disabled={saving}>{saving ? "Saving…" : "Save member settings"}</ActionButton></div>}
                <ProviderProbe key={selected} signature={teamProbeSignature(members[selected], form, providerConfig, selected)}
                  onProbe={() => api.probeProvider(projectId, selected)} disabled={saving || providerDirty || Boolean(providerConfig?.error)}
                  disabledReason={providerDirty ? "Save your model and provider changes before testing this connection." : providerConfig?.error ? "Correct the provider configuration before testing." : null} />

                <h3 className="team-context-heading">Context parameters</h3>
                <div className="field">
                  <label>Auto-compact threshold (input tokens)</label>
                  <input aria-label="Auto-compact threshold" value={form.auto_compact_tokens} onChange={set("auto_compact_tokens")}
                    placeholder="0" inputMode="numeric" />
                  <div className="hint">Compact this member's thread when its cumulative input
                    tokens cross this threshold. 0 = never. Long threads get expensive without it.</div>
                </div>

                <div className="field">
                  <label>Rotation threshold (input tokens)</label>
                  <input aria-label="Rotation threshold" value={form.max_turn_input_tokens} onChange={set("max_turn_input_tokens")}
                    placeholder="0" inputMode="numeric" />
                  <div className="hint">Checked after a turn against the thread's reported cumulative
                    input tokens. When reached, the next turn uses a fresh thread. This does not
                    cap the current turn's cost. 0 = off.</div>
                </div>
              </div>
            </div>

            <div className="card">
              <h2>Member instructions</h2>
              <div className="body">
                <textarea aria-label="Member instructions" rows={8} value={form.soul} onChange={set("soul")} />
                <div style={{ display: "flex", justifyContent: "space-between",
                              alignItems: "center", marginTop: 8 }}>
                  <span className="note">
                    Global-scope instructions in this member's Codex home; applies to the next turn.
                  </span>
                    <ActionButton action="save" variant="primary" onClick={save} disabled={saving || !dirty}>{saving ? "Saving…" : "Save member"}</ActionButton>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
