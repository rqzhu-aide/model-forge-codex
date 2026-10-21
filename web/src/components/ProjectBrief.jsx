import React, { useRef, useState } from "react";
import { api } from "../api";
import { Dialog, ResearchDocument } from "./Shared";
import { ActionButton } from "./Visuals";

export function ProjectBriefEditor({ project, activeRunCount = 0, onClose, onSaved }) {
  const initial = useRef({ name: project.name || "", research_instructions: project.research_instructions || "" });
  const [form, setForm] = useState(initial.current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const lock = useRef(false);
  const changes = Object.fromEntries(Object.entries(form).filter(([key, value]) => value !== initial.current[key]));
  const update = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));
  const save = async (event) => {
    event.preventDefault();
    if (lock.current || !form.name.trim() || !Object.keys(changes).length) return;
    lock.current = true; setBusy(true); setError(null);
    try {
      const result = await api.updateProject(project.project_id, changes);
      onSaved(result.project);
    } catch (e) { setError(e.message); }
    finally { lock.current = false; setBusy(false); }
  };
  return <Dialog title="Edit project instructions" busy={busy} onClose={onClose}>
    <form onSubmit={save}>
      <p className="note">These instructions guide the team across research phases. Each run keeps the brief it started with.</p>
      {activeRunCount > 0 && <p className="context-note">Work in progress will continue with its saved brief. These edits apply to new runs.</p>}
      <div className="field"><label htmlFor="brief-name">Project name</label><input id="brief-name" required value={form.name} onChange={update("name")} disabled={busy} /></div>
      <div className="field contribution-surface"><label htmlFor="brief-instructions">Problem brief</label><textarea id="brief-instructions" rows={10} value={form.research_instructions} onChange={update("research_instructions")} disabled={busy} aria-describedby="brief-instructions-hint" placeholder="Describe the target, intended use, how observations arise, available information, and useful performance or constraints." /><p className="hint" id="brief-instructions-hint">Data are optional. Confirmed understanding retains its own authority and provenance when this brief changes. Use Discuss your problem to correct it directly.</p></div>
      {project.setting_amendments?.length > 0 && <details className="research-details contribution-surface"><summary>Saved changes to the setting ({project.setting_amendments.length})</summary><p className="note">These instructions accompany new runs. The published formulation remains the author's recorded statement.</p>{project.setting_amendments.map((item, i) => <div key={i}><p className="note">{item.created_at?.slice(0, 16).replace("T", " ")}</p><ResearchDocument text={item.text} /></div>)}</details>}
      {error && <p className="error" role="alert">{error}</p>}
      <div className="btnrow"><ActionButton action="save" uiRole="research" variant="primary" type="submit" disabled={busy || !form.name.trim() || !Object.keys(changes).length}>{busy ? "Saving…" : "Save project instructions"}</ActionButton><ActionButton action="close" onClick={onClose} disabled={busy}>Cancel</ActionButton></div>
    </form>
  </Dialog>;
}

export default function ProjectBrief({ project, activeRunCount, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);
  return <section className="card project-brief" data-card-role="research" aria-label="Project instructions">
    <div className="project-brief-header card-heading"><h2>Project instructions</h2><ActionButton action="edit" uiRole="research" onClick={() => { setEditing(true); setSaved(false); }}>Edit project instructions</ActionButton></div>
    <div className="project-brief-content contribution-surface">
      <p className="note">The research question, direction, and constraints for your team.</p>
      {project.research_instructions?.trim() ? <details className="research-details"><summary>Read project instructions</summary><ResearchDocument text={project.research_instructions} /></details> : <p className="note">Describe the research you want to pursue.</p>}
      {saved && <p className="note" role="status">Project instructions saved. New runs will use them.</p>}
    </div>
    {editing && <ProjectBriefEditor project={project} activeRunCount={activeRunCount} onClose={() => setEditing(false)} onSaved={(updated) => { onSaved(updated); setEditing(false); setSaved(true); }} />}
  </section>;
}
