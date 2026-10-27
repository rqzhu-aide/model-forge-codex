import React, { useEffect, useId, useState } from "react";
import { api } from "../api";
import {
  EDITOR_ROLES, ROLE_LABELS, REASONING_EFFORTS, EMPTY_CONNECTION,
  editorFromDocument, documentFromEditor, maskKey, isShimConnection, blankDocument,
} from "../providerEditor";
import { editorProbeSignature } from "../providerProbe";
import { ProviderProbe } from "./ProviderProbe";
import { ActionButton } from "./Visuals";

// A stored key is masked (•••••• + last characters) until the researcher
// reveals it; the raw key never enters the DOM while masked.
export function SecretKeyField({ label = "API key", value, onChange, ariaLabel }) {
  const inputId = useId();
  const [revealed, setRevealed] = useState(false);
  const [edited, setEdited] = useState(false);
  const masked = Boolean(value) && !revealed && !edited;
  return <div className="field">
    <label htmlFor={inputId}>{label}</label>
    <div className="key-input-row">
      <input id={inputId} type={revealed ? "text" : "password"} value={masked ? maskKey(value) : value} readOnly={masked}
        aria-label={ariaLabel || label} placeholder="Paste the provider key" autoComplete="off" spellCheck="false"
        onFocus={() => { if (masked) setRevealed(true); }}
        onChange={(e) => { setEdited(true); onChange(e.target.value); }} />
      {value ? <button type="button" className="btn ghost" aria-pressed={revealed}
        onClick={() => { setRevealed(!revealed); setEdited(false); }}>{revealed ? "Hide" : "Show"}</button> : null}
    </div>
    <div className="hint">{masked
      ? "Stored key, masked except its last characters. Focus the field or choose Show to view or replace it."
      : "The key is visible only in this browser. It is saved into the provider file, never into research artifacts or logs."}</div>
  </div>;
}

function ModelEffortFields({ value, onChange, prefix, inherit = false, shared, reasoningEfforts = REASONING_EFFORTS }) {
  const inputId = useId();
  return <div className="tworow">
    <div className="field">
      <label htmlFor={`${inputId}-model`}>{inherit ? "Agent model override (optional)" : "Agent model"}</label>
      <input id={`${inputId}-model`} aria-label={`${prefix} model`} value={value.model} onChange={(e) => onChange({ ...value, model: e.target.value })}
        placeholder={inherit ? shared?.model || "Inherit the shared model" : "model-id"} />
      <div className="hint">{inherit ? `Leave blank to use ${shared?.model || "the shared model"}.` : "Enter the exact model name supplied by your provider."}</div>
    </div>
    <div className="field">
      <label htmlFor={`${inputId}-effort`}>Reasoning effort</label>
      <select id={`${inputId}-effort`} aria-label={`${prefix} reasoning effort`} value={value.reasoning_effort}
        onChange={(e) => onChange({ ...value, reasoning_effort: e.target.value })}>
        {inherit && <option value="">Shared default{shared?.reasoning_effort ? ` (${shared.reasoning_effort})` : ""}</option>}
        {value.reasoning_effort && !reasoningEfforts.includes(value.reasoning_effort) && <option value={value.reasoning_effort}>{value.reasoning_effort} (current setting)</option>}
        {reasoningEfforts.map((effort) => <option key={effort} value={effort}>{effort}</option>)}
      </select>
      <div className="hint">Use a reasoning level supported by this model.</div>
    </div>
  </div>;
}

// A complete custom connection: own id, endpoint, model, effort, and exactly
// one credential (key in the file or an environment variable name).
export function ConnectionFields({ value, onChange, prefix, reasoningEfforts }) {
  const inputId = useId();
  const set = (key) => (e) => onChange({ ...value, [key]: e.target.value });
  return <>
    <div className="tworow">
      <div className="field">
        <label htmlFor={`${inputId}-provider`}>Provider name / ID</label>
        <input id={`${inputId}-provider`} aria-label={`${prefix} provider ID`} value={value.id} onChange={set("id")} placeholder="my-provider" />
        <div className="hint">A name you choose, using letters, numbers, hyphens, or underscores.</div>
      </div>
      <div className="field">
        <label htmlFor={`${inputId}-url`}>Base URL</label>
        <input id={`${inputId}-url`} aria-label={`${prefix} base URL`} value={value.base_url} onChange={set("base_url")}
          placeholder="https://api.example.com/v1" />
        <div className="hint">Responses-compatible endpoint, without embedded credentials or query parameters.</div>
      </div>
    </div>
    <ModelEffortFields value={value} onChange={onChange} prefix={prefix} reasoningEfforts={reasoningEfforts} />
    <div className="field">
      <label>Credentials</label>
      <div className="segs">
        <button type="button" className={`seg ${value.credential === "file" ? "on" : ""}`} aria-pressed={value.credential === "file"}
          onClick={() => onChange({ ...value, credential: "file" })}>Enter API key</button>
        <button type="button" className={`seg ${value.credential === "env" ? "on" : ""}`} aria-pressed={value.credential === "env"}
          onClick={() => onChange({ ...value, credential: "env" })}>Environment variable</button>
      </div>
    </div>
    {value.credential === "env"
      ? <div className="field">
          <label htmlFor={`${inputId}-env`}>API key environment variable</label>
          <input id={`${inputId}-env`} aria-label={`${prefix} API key environment variable`} value={value.api_key_env} onChange={set("api_key_env")}
            placeholder="PROVIDER_API_KEY" />
          <div className="hint">Variable name only; the backend process reads the key from its environment.</div>
        </div>
      : <SecretKeyField value={value.api_key} onChange={(api_key) => onChange({ ...value, api_key })} ariaLabel={`${prefix} API key`} />}
    {isShimConnection(value) && <p className="note">This connection points at the local Responses shim. Which key
      the provider actually receives depends on how the shim was started: with <code>--auth env</code> (the default)
      the key here is only the shim's placeholder and the shim uses the real key from its own env file; with{" "}
      <code>--auth forward</code> the shim forwards this connection's key, so the real key belongs here.</p>}
  </>;
}

export function MemberEditor({ role, value, defaultExists, shared, reasoningEfforts, onChange, probe = null }) {
  const label = ROLE_LABELS[role] || role;
  const choose = (mode) => onChange({
    ...value, mode,
    model: mode === "default" ? value.model : value.model || EMPTY_CONNECTION.model,
    reasoning_effort: mode === "default" ? value.reasoning_effort : value.reasoning_effort || EMPTY_CONNECTION.reasoning_effort,
  });
  return <section className="provider-member-editor" aria-label={`${label} provider`}>
    <h3>{label}</h3>
    <div className="segs">
      <button type="button" className={`seg ${value.mode === "default" ? "on" : ""}`} aria-pressed={value.mode === "default"}
        disabled={!defaultExists} onClick={() => choose("default")}>Shared default</button>
      <button type="button" className={`seg ${value.mode === "openai" ? "on" : ""}`} aria-pressed={value.mode === "openai"}
        onClick={() => choose("openai")}>OpenAI account</button>
      <button type="button" className={`seg ${value.mode === "custom" ? "on" : ""}`} aria-pressed={value.mode === "custom"}
        onClick={() => choose("custom")}>Custom provider</button>
    </div>
    {value.mode === "ungoverned" && <p className="note">This member uses its saved project settings. Choose OpenAI account or Custom provider above to configure it across projects.
      {defaultExists ? "" : " Choose Shared connection to add a default for the team."}</p>}
    {value.mode === "default" && !defaultExists && <p className="note warn">This member's model/effort override needs
      the shared connection below. Add it, or choose another provider for this member.</p>}
    {value.mode === "default" && <>
      <ModelEffortFields value={value} onChange={onChange} prefix={label} inherit shared={shared} reasoningEfforts={reasoningEfforts} />
      <div className="hint">Uses the shared connection below. Model and reasoning overrides apply only to this member.</div>
    </>}
    {value.mode === "openai" && <>
      <ModelEffortFields value={value} onChange={onChange} prefix={label} reasoningEfforts={reasoningEfforts} />
      <p className="note">Uses the connected OpenAI account on this host: one shared sign-in; each member gets its own conversation.</p>
    </>}
    {value.mode === "custom" && <>
      <ConnectionFields value={value} onChange={onChange} prefix={label} reasoningEfforts={reasoningEfforts} />
      <div className="hint">A complete connection of its own: it never inherits a key or endpoint from anywhere else.</div>
    </>}
    {probe}
  </section>;
}

function SharedDefaultSection({ shared, onChange, reasoningEfforts }) {
  return <section className="provider-shared-default">
    <h3>Shared connection</h3>
    {shared ? <>
      <p className="note">Changes here apply to every member using Shared default, across all projects.</p>
      <div className="field">
        <label>Connection type</label>
        <div className="segs">
          <button type="button" className={`seg ${shared.type === "openai" ? "on" : ""}`} aria-pressed={shared.type === "openai"}
            onClick={() => onChange({ ...shared, type: "openai" })}>OpenAI account</button>
          <button type="button" className={`seg ${shared.type === "custom" ? "on" : ""}`} aria-pressed={shared.type === "custom"}
            onClick={() => onChange({ ...shared, type: "custom" })}>Custom provider</button>
        </div>
      </div>
      {shared.type === "openai" && <>
        <ModelEffortFields value={shared} onChange={onChange} prefix="Shared default" reasoningEfforts={reasoningEfforts} />
        <p className="note">Uses the connected OpenAI account on this host: one shared sign-in; each member gets its own conversation.</p>
      </>}
      {shared.type === "custom" && <ConnectionFields value={shared} onChange={onChange} prefix="Shared default" reasoningEfforts={reasoningEfforts} />}
    </> : <p className="note">No shared default. Members without their own table keep their per-project saved settings.</p>}
  </section>;
}

export function ProviderFileEditorForm({ view, editor, onEditorChange, onSave, onRemove, onRefresh, onClose,
                                         saving = false, saveError = null, conflict = false, savedNotice = false,
                                         confirmingRemove = false, onToggleRemove,
                                         draftKept = false, onReapplyDraft, onDiscardDraft, projectId = null,
                                         selectedRole = EDITOR_ROLES[0], onSelectRole, reasoningEfforts = REASONING_EFFORTS }) {
  const defaultExists = Boolean(editor.shared);
  const setMember = (role) => (member) => onEditorChange({ ...editor, members: { ...editor.members, [role]: member } });
  const setShared = (shared) => onEditorChange({ ...editor, shared });
  // Adding or removing the default re-maps the members whose meaning depends on it.
  const addShared = () => onEditorChange({
    shared: { ...EMPTY_CONNECTION, type: "openai" },
    members: Object.fromEntries(EDITOR_ROLES.map((role) => {
      const member = editor.members[role];
      return [role, member.mode === "ungoverned" ? { ...member, mode: "default" } : member];
    })),
  });
  const removeShared = () => onEditorChange({
    shared: null,
    members: Object.fromEntries(EDITOR_ROLES.map((role) => {
      const member = editor.members[role];
      return [role, member.mode === "default" ? { ...member, mode: "ungoverned" } : member];
    })),
  });
  return <div className="card provider-file-editor">
    <div className="provider-editor-heading"><h2>Configure agent models and providers</h2>
      <ActionButton action="back" onClick={onClose} disabled={saving}>Back to team settings</ActionButton></div>
    <div className="body">
      <p className="note">Choose a member, enter its provider and model, then test the settings before saving.
        Saved changes apply across all projects from the next turn. Running turns keep their current settings.</p>
      {view.error && <div className="note warn" role="alert">The file on disk is currently invalid: {view.error}{" "}
        Correct it here or in a text editor; saving a valid configuration replaces it.</div>}
      {conflict && <div className="note warn provider-conflict" role="alert">Provider settings changed outside this
        editor. Review the latest settings before saving. Your unsaved edits stay available.{" "}
        <ActionButton action="retry" onClick={onRefresh} disabled={saving}>Refresh editor</ActionButton></div>}
      {!conflict && draftKept && <div className="note warn provider-conflict" role="alert">Provider settings changed
        outside this editor. Review the latest settings before saving; your unsaved edits were kept.{" "}
        <button type="button" className="btn ghost" onClick={onReapplyDraft} disabled={saving}>Reapply your edits</button>{" "}
        <button type="button" className="btn ghost" onClick={onDiscardDraft} disabled={saving}>Discard your edits</button></div>}
      {saveError && <div className="error" role="alert">{saveError}</div>}
      {savedNotice && <div className="banner" role="status">Saved. New turns read the updated settings; running turns keep their captured settings.</div>}
      <fieldset className="provider-editor-fields" disabled={saving}>
        <legend className="sr-only">Provider and model settings</legend>
        <div className="provider-member-picker" role="group" aria-label="Choose a member to configure">
          {EDITOR_ROLES.map((role) => <button key={role} type="button" className={`btn ${selectedRole === role ? "" : "ghost"}`}
            aria-pressed={selectedRole === role} onClick={() => onSelectRole?.(role)}>{ROLE_LABELS[role]}</button>)}
          <button type="button" className={`btn ${selectedRole === "shared" ? "" : "ghost"}`}
            aria-pressed={selectedRole === "shared"} onClick={() => onSelectRole?.("shared")}>Shared connection</button>
        </div>
        {EDITOR_ROLES.map((role) => <div key={role} hidden={selectedRole !== role}>
          <MemberEditor role={role} value={editor.members[role]} defaultExists={defaultExists} shared={editor.shared}
            reasoningEfforts={reasoningEfforts} onChange={setMember(role)} />
        </div>)}
        <div hidden={selectedRole !== "shared" && editor.members[selectedRole]?.mode !== "default"}>
          <SharedDefaultSection shared={editor.shared} onChange={setShared} reasoningEfforts={reasoningEfforts} />
          <div className="btnrow provider-editor-actions">{editor.shared
            ? <button type="button" className="btn ghost" onClick={removeShared}>Remove shared default</button>
            : <button type="button" className="btn ghost" onClick={addShared}>Add shared default</button>}</div>
        </div>
      </fieldset>
      {projectId && EDITOR_ROLES.map((role) => editor.members[role].mode !== "ungoverned" && <div key={role} hidden={selectedRole !== role}>
        <ProviderProbe signature={editorProbeSignature(editor, role)} disabled={saving} scope="draft"
          onProbe={() => api.probeProvider(projectId, role, documentFromEditor(editor))} />
      </div>)}
      {selectedRole === "shared" && <p className="note">Choose a member that uses Shared default to test this connection with its model and reasoning settings.</p>}
      <div className="btnrow provider-editor-actions">
        <ActionButton action="save" variant="primary" onClick={onSave} disabled={saving || conflict || draftKept}>{saving ? "Saving…" : "Save model and provider settings"}</ActionButton>
        <ActionButton action="back" onClick={onClose} disabled={saving}>Back to team settings</ActionButton>
      </div>
      <details className="provider-file-details"><summary>Configuration file and reset</summary>
        <p className="note">Settings are stored in <code className="provider-config-path">{view.path}</code>
          You can also edit this file directly. Saving here validates the settings and normalizes file formatting.
          API keys stay in this local file and are never written to research artifacts or logs.</p>
        <div className="btnrow provider-editor-actions">
        {view.exists && !confirmingRemove &&
          <button type="button" className="btn ghost" onClick={onToggleRemove} disabled={saving}>Remove provider file</button>}
        {view.exists && confirmingRemove && <>
          <button type="button" className="btn danger" onClick={onRemove} disabled={saving}>Confirm removal</button>
          <button type="button" className="btn ghost" onClick={onToggleRemove} disabled={saving}>Keep file</button>
        </>}
        </div>
        {confirmingRemove && <p className="note warn">Removing the file restores each member's per-project saved settings.</p>}
      </details>
    </div>
  </div>;
}

export default function ProviderFileEditor({ onSaved, onClose, projectId = null, initialRole, reasoningEfforts }) {
  const [selectedRole, setSelectedRole] = useState(EDITOR_ROLES.includes(initialRole) ? initialRole : EDITOR_ROLES[0]);
  const [view, setView] = useState(null);
  const [editor, setEditor] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [conflict, setConflict] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedNotice, setSavedNotice] = useState(false);
  const [confirmingRemove, setConfirmingRemove] = useState(false);
  // A credential-containing draft lives only in this component's memory — never
  // in browser persistent storage. It survives a refresh so the researcher can
  // reapply unsaved edits onto the latest file; there is no automatic merge.
  const [draft, setDraft] = useState(null);

  const load = async () => {
    setLoadError(null); setConflict(false); setConfirmingRemove(false);
    try {
      const next = await api.providerEditor();
      setView(next);
      setEditor(next.document ? editorFromDocument(next.document) : null);
    } catch (e) { setLoadError(e.message); }
  };
  useEffect(() => { load(); }, []);

  // Refresh after a conflict: keep the unsaved edits, load the latest file.
  const refreshPreservingDraft = async () => {
    if (editor) setDraft(editor);
    await load();
  };

  const persist = async (document) => {
    if (saving || !view) return;
    setSaving(true); setSaveError(null); setConflict(false);
    try {
      await api.saveProviderConfig(view.token, document);
      await load();
      setDraft(null);
      setSavedNotice(true);
      onSaved?.();
    } catch (e) {
      if (e.status === 409) setConflict(true);
      else setSaveError(e.message);
    } finally { setSaving(false); }
  };

  // Editing the latest view supersedes the stashed draft (no silent clobber on reapply).
  const change = (next) => { setEditor(next); setSavedNotice(false); setSaveError(null); setDraft(null); };
  const reapplyDraft = () => {
    if (draft) { setEditor(draft); setSavedNotice(false); }
    setDraft(null);
  };

  if (loadError) {
    return <div className="card provider-file-editor"><h2>Configure agent models and providers</h2><div className="body">
      <div className="error" role="alert">{loadError}{" "}
        <ActionButton action="retry" onClick={load}>Reload provider settings</ActionButton></div>
      <div className="btnrow provider-editor-actions">
        <ActionButton action="close" onClick={onClose}>Close editor</ActionButton>
      </div>
    </div></div>;
  }
  if (!view) return <p className="note" role="status">Loading model and provider settings…</p>;
  if (!editor) {
    // The file is not parseable TOML: repair it by hand, or replace it here.
    return <div className="card provider-file-editor"><h2>Configure agent models and providers</h2><div className="body">
      <div className="note warn" role="alert">The provider file is not valid TOML{view.error ? `: ${view.error}` : ""}{" "}
        Fix it in a text editor, or replace it from here.</div>
      <div className="btnrow">
        <button type="button" className="btn" onClick={() => setEditor(editorFromDocument(null))}>Start a fresh replacement</button>
        <ActionButton action="close" onClick={onClose}>Close editor</ActionButton>
      </div>
    </div></div>;
  }
  return <ProviderFileEditorForm key={view.token} view={view} editor={editor} onEditorChange={change}
    onSave={() => persist(documentFromEditor(editor))} onRemove={() => persist(blankDocument())}
    onRefresh={refreshPreservingDraft} onClose={onClose} saving={saving} saveError={saveError} conflict={conflict}
    savedNotice={savedNotice} confirmingRemove={confirmingRemove} onToggleRemove={() => setConfirmingRemove(!confirmingRemove)}
    draftKept={Boolean(draft)} onReapplyDraft={reapplyDraft} onDiscardDraft={() => setDraft(null)} projectId={projectId}
    selectedRole={selectedRole} onSelectRole={setSelectedRole} reasoningEfforts={reasoningEfforts} />;
}
