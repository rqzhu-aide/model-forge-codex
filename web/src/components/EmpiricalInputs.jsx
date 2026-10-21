import React, { useEffect, useId, useState } from "react";
import { api } from "../api";
import { humanLabel } from "../research";
import { ActionButton } from "./Visuals";

export const MAX_INPUT_BYTES = 64 * 1024 * 1024;

export function fileContentBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("This file could not be read. Select it again or choose another file."));
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.readAsDataURL(file);
  });
}

export default function EmpiricalInputs({ projectId, selected = [], onChange, disabled, onBusyChange }) {
  const id = useId();
  const [inputs, setInputs] = useState([]); const [loading, setLoading] = useState(true);
  const [file, setFile] = useState(null); const [role, setRole] = useState("dataset");
  const [description, setDescription] = useState(""); const [mapping, setMapping] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState(null); const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true; setLoading(true);
    api.inputs(projectId).then((value) => { if (active) { setInputs(value.inputs || []); setError(null); } })
      .catch((failure) => { if (active) setError(failure.message); }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId, retry]);
  const toggle = (inputId, checked) => onChange(checked ? [...selected, inputId] : selected.filter((value) => value !== inputId));
  const importFile = async () => {
    if (!file || busy || disabled) return;
    if (file.size > MAX_INPUT_BYTES) { setError("Choose a file smaller than 64 MiB."); return; }
    setBusy(true); onBusyChange?.(true); setError(null);
    try {
      const input = await api.importInput(projectId, { filename: file.name, role, content_base64: await fileContentBase64(file), description, mapping: mapping.trim() ? { notes: mapping } : {} });
      setInputs((previous) => [...previous.filter((item) => item.input_id !== input.input_id), input]);
      if (!selected.includes(input.input_id)) onChange([...selected, input.input_id]);
      setFile(null); setDescription(""); setMapping("");
      const control = document.getElementById(`${id}-file`); if (control) control.value = "";
    } catch (failure) { setError(failure.message); }
    finally { setBusy(false); onBusyChange?.(false); }
  };
  const missing = selected.filter((inputId) => !inputs.some((item) => item.input_id === inputId));
  return <fieldset className="empirical-inputs" disabled={disabled || busy}><legend>Data, code and configuration for this evaluation</legend>
    <p className="note">Select up to 32 local files to retain for this run. Importing or selecting files does not start work. The run uses a frozen copy of the selected bytes.</p>
    {loading && <p className="note" role="status">Loading retained inputs…</p>}
    {inputs.map((input) => <label className="check-label empirical-input-choice" key={input.input_id}><input type="checkbox" checked={selected.includes(input.input_id)} disabled={selected.length >= 32 && !selected.includes(input.input_id)} onChange={(event) => toggle(input.input_id, event.target.checked)} /><span><b>{input.filename}</b><span className="note">{humanLabel(input.role)} · {(input.size_bytes / 1024).toLocaleString(undefined, { maximumFractionDigits: 1 })} KiB{input.description && ` · ${input.description}`}</span></span></label>)}
    {selected.length >= 32 && <p className="note">32 inputs selected. Remove one to select a replacement.</p>}
    {!loading && missing.map((inputId) => <div className="btnrow note warn" key={inputId}><span>A selected input is unavailable: {inputId}</span><ActionButton action="close" onClick={() => toggle(inputId, false)}>Remove unavailable input</ActionButton></div>)}
    <details className="research-details"><summary>Import a local file</summary><div className="empirical-input-import">
      <div className="field"><label htmlFor={`${id}-role`}>File role</label><select id={`${id}-role`} value={role} onChange={(event) => setRole(event.target.value)}><option value="dataset">Dataset</option><option value="code">Model code</option><option value="configuration">Configuration</option></select></div>
      <div className="field"><label htmlFor={`${id}-file`}>Local file (up to 64 MiB)</label><input id={`${id}-file`} type="file" onChange={(event) => { setFile(event.target.files?.[0] || null); setError(null); }} /></div>
      <div className="field contribution-surface"><label htmlFor={`${id}-description`}>Description (optional)</label><input id={`${id}-description`} value={description} onChange={(event) => setDescription(event.target.value)} /></div>
      {role === "dataset" && <div className="field contribution-surface"><label htmlFor={`${id}-mapping`}>Variable mapping (optional)</label><textarea id={`${id}-mapping`} rows={2} value={mapping} onChange={(event) => setMapping(event.target.value)} placeholder="Column meanings, units, outcome and independent sampling unit" /></div>}
      <ActionButton action="save" uiRole="research" disabled={!file || busy || disabled || selected.length >= 32} onClick={importFile}>{busy ? "Importing…" : "Import and select file"}</ActionButton>
    </div></details>
    {error && <p className="error" role="alert">{error} <ActionButton action="retry" onClick={() => setRetry((value) => value + 1)}>Refresh retained inputs</ActionButton></p>}
  </fieldset>;
}
