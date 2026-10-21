import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { captureRunOrigin, beginRunReturn } from "./runReturnFocus.js";
import { api } from "./api";
import ProjectView from "./components/ProjectView";
import RunDetail from "./components/RunDetail";
import TeamView from "./components/TeamView";
import { Dialog } from "./components/Shared";
import AccountDialog from "./components/AccountDialog";
import { ActionButton } from "./components/Visuals";
import { captureReadingPosition, normalizeNavigation, readerScope } from "./readingPosition";

function savedNavigation() {
  try { return normalizeNavigation(JSON.parse(sessionStorage.getItem("model-forge-navigation") || "{}")); } catch { return normalizeNavigation(null); }
}
function savedTheme() {
  try { return localStorage.getItem("model-forge-theme") === "dark" ? "dark" : "light"; } catch { return "light"; }
}
function SidebarIcon({ name }) {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {name === "menu" ? <path d="M4 6h16M4 12h16M4 18h16" /> : name === "sun" ? <><circle cx="12" cy="12" r="4" /><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.4 1.4m11.2 11.2L19 19M5 19l1.4-1.4M17.6 6.4L19 5" /></> : name === "moon" ? <path d="M20.7 13A9 9 0 0 1 11 3.3 9 9 0 1 0 20.7 13Z" /> : name === "team" ? <><path d="M4 7h16M4 17h16" /><circle cx="9" cy="7" r="3" /><circle cx="15" cy="17" r="3" /></> : <><circle cx="12" cy="12" r="9" /><circle cx="12" cy="9" r="3" /><path d="M5.7 18.3a6.5 6.5 0 0 1 12.6 0" /></>}
  </svg>;
}
export default function App() {
  const runOrigin = useRef(null); const runReturn = useRef(null);
  const initial = useRef(savedNavigation());
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState(initial.current.projectId || null);
  const [contexts, setContexts] = useState(initial.current.contexts || {});
  const [view, setView] = useState({ name: "project" });
  const [navigationEpoch, setNavigationEpoch] = useState(0);
  const [focusReading, setFocusReading] = useState(false);
  const main = useRef(null);
  const [navigationOpen, setNavigationOpen] = useState(false);
  const navigationToggle = useRef(null);
  const [theme, setTheme] = useState(savedTheme);
  const [accountOpen, setAccountOpen] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState(null);
  const [form, setForm] = useState({ name: "", instructions: "" });
  const saveLock = useRef(false);
  const closeNavigation = () => {
    setNavigationOpen(false);
    // Keep a visible focus return point before a mobile menu item disappears.
    if (navigationToggle.current?.getClientRects().length) navigationToggle.current.focus();
  };
  const load = async () => {
    setError(null);
    try {
      const data = await api.projects(); const list = data.projects || []; setProjects(list);
      setProjectId((current) => list.some((p) => p.project_id === current) ? current : list[0]?.project_id || null);
    } catch (e) { setError(e.message); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("model-forge-theme", theme); } catch {}
  }, [theme]);
  useEffect(() => { try { sessionStorage.setItem("model-forge-navigation", JSON.stringify({ projectId, contexts })); } catch {} }, [projectId, contexts]);
  const context = contexts[projectId] || { branch: "trunk", phase: "P1", selectedNode: null };
  const contextRef = useRef(null); contextRef.current = { projectId, contexts, context, view };
  const withPosition = (current) => {
    if (view.name !== "project" || !main.current?.querySelector("[data-reader-ready]")) return current;
    const position = captureReadingPosition(main.current); const scope = readerScope(context.phase, context.branch);
    const saved = current[projectId] || context;
    return { ...current, [projectId]: { ...saved, readers: { ...saved.readers, [scope]: { ...saved.readers?.[scope], position } } } };
  };
  const changeView = (next, nextProject = projectId, returning = false) => {
    if (!returning) { runReturn.current?.cancel(); runReturn.current = null; }
    setContexts(withPosition); setProjectId(nextProject); setView(next); setFocusReading(false); setNavigationEpoch((value) => value + 1);
  };
  const openRun = (runId, control) => {
    runOrigin.current = captureRunOrigin(main.current, control, `${projectId}:${context.phase}:${context.branch}`);
    changeView({ name: "run", runId });
  };
  const returnFromRun = () => {
    runReturn.current?.cancel(); runReturn.current = beginRunReturn(runOrigin.current); runOrigin.current = null;
    changeView({ name: "project" }, projectId, true);
  };
  useEffect(() => () => runReturn.current?.cancel(), []);
  const updateContext = ({ selectedNode, readerJump, ...change }) => {
    const navigates = change.phase && change.phase !== context.phase || change.branch && change.branch !== context.branch || readerJump;
    if (navigates) { runReturn.current?.cancel(); runReturn.current = null; runOrigin.current = null; setFocusReading(Boolean(readerJump)); setNavigationEpoch((value) => value + 1); }
    setContexts((current) => {
      const captured = navigates ? withPosition(current) : current;
      const next = { ...(captured[projectId] || context), ...change };
      if (selectedNode !== undefined || readerJump) {
        const scope = readerScope("P3", next.branch);
        next.readers = { ...next.readers, [scope]: { ...next.readers?.[scope], ...(selectedNode !== undefined ? { selectedNode } : {}), ...(readerJump ? { tab: "claims", selectedNode: readerJump.node, position: { anchor: { kind: "data-reading-anchor", value: "theory-inspector" }, offset: 24, y: 0, disclosures: [] } } : {}) } };
      }
      return { ...captured, [projectId]: next };
    });
  };
  const updateReader = (change) => setContexts((current) => {
    const saved = current[projectId] || context; const scope = readerScope(context.phase, context.branch);
    return { ...current, [projectId]: { ...saved, readers: { ...saved.readers, [scope]: { ...saved.readers?.[scope], ...change } } } };
  });
  useEffect(() => {
    const previous = history.scrollRestoration; history.scrollRestoration = "manual";
    const save = () => {
      const current = contextRef.current; const position = current.view.name === "project" && main.current?.querySelector("[data-reader-ready]") ? captureReadingPosition(main.current) : null;
      const scope = readerScope(current.context.phase, current.context.branch); const saved = current.contexts[current.projectId] || current.context;
      const savedContexts = position ? { ...current.contexts, [current.projectId]: { ...saved, readers: { ...saved.readers, [scope]: { ...saved.readers?.[scope], position } } } } : current.contexts;
      try { sessionStorage.setItem("model-forge-navigation", JSON.stringify({ projectId: current.projectId, contexts: savedContexts })); } catch {}
    };
    window.addEventListener("pagehide", save);
    return () => { window.removeEventListener("pagehide", save); history.scrollRestoration = previous; };
  }, []);
  const create = async (event) => {
    event.preventDefault(); if (saveLock.current) return;
    saveLock.current = true; setSaving(true); setCreateError(null);
    try {
      const result = await api.createProject(form.name.trim(), form.instructions);
      await load(); changeView({ name: "project" }, result.project_id); setCreating(false);
      setForm({ name: "", instructions: "" });
    } catch (e) { setCreateError(e.message); } finally { saveLock.current = false; setSaving(false); }
  };
  return <div id="app">
    <aside className={`app-sidebar${navigationOpen ? " navigation-open" : ""}`} aria-label="Project navigation">
      <button className="brand serif plain-button" onClick={() => { changeView({ name: "project" }); closeNavigation(); }}>Model Forge<small>Research workbench</small></button>
      <button type="button" className="mobile-navigation-toggle" ref={navigationToggle} aria-expanded={navigationOpen} aria-controls="sidebar-projects sidebar-workspace" onClick={() => setNavigationOpen((open) => !open)}><SidebarIcon name="menu" /><span>Projects &amp; settings</span></button>
      <div id="sidebar-projects" className="sidebar-projects">
      <div className="side-label">Projects</div>
      {projects.map((p) => <button key={p.project_id} className={`side-item ${p.project_id === projectId && view.name !== "team" ? "active" : ""}`} aria-current={p.project_id === projectId && view.name !== "team" ? "page" : undefined} onClick={() => { changeView({ name: "project" }, p.project_id); closeNavigation(); }}>{p.name}</button>)}
      <button className="btn ghost new-project" onClick={() => { setCreating(true); setCreateError(null); closeNavigation(); }}>New project</button>
      </div>
      <div id="sidebar-workspace" className="sidebar-workspace">
        <div className="side-label">Workspace</div>
        <button className={`side-item ${view.name === "team" ? "active" : ""}`} aria-current={view.name === "team" ? "page" : undefined} disabled={!projectId} title={!projectId ? "Open a project to configure its team" : undefined} onClick={() => { changeView({ name: "team" }); closeNavigation(); }}><SidebarIcon name="team" /><span>Team Settings</span></button>
        <div className="theme-control"><span id="appearance-label" className="theme-label">Appearance</span><div className="theme-options" role="group" aria-labelledby="appearance-label"><button className="theme-option" aria-label="Light theme" aria-pressed={theme === "light"} onClick={() => setTheme("light")}><SidebarIcon name="sun" />Light</button><button className="theme-option" aria-label="Dark theme" aria-pressed={theme === "dark"} onClick={() => setTheme("dark")}><SidebarIcon name="moon" />Dark</button></div></div>
        <button className="side-item" onClick={() => { setAccountOpen(true); closeNavigation(); }}><SidebarIcon name="account" /><span>OpenAI Account</span></button>
      </div>
    </aside>
    <main ref={main}>
      {error && <div className="error" role="alert">{error} <ActionButton action="retry" onClick={load}>Retry loading projects</ActionButton></div>}
      {loading && <p className="note" role="status">Loading projects…</p>}
      {!loading && !projectId && !error && <section className="empty-state"><h1 className="serif">Begin with your problem</h1><p>Develop a statistical model, ML model, or algorithm, inspect its justification and numerical evidence, and retain a technical report.</p><button className="btn" onClick={() => setCreating(true)}>Create project</button></section>}
      {projectId && view.name === "project" && <ProjectView key={projectId} projectId={projectId} context={context} reading={context.readers?.[readerScope(context.phase, context.branch)] || {}} onReadingChange={updateReader} restorationKey={navigationEpoch} focusReading={focusReading} runReturn={runReturn.current} returnScope={`${projectId}:${context.phase}:${context.branch}`} onReadingRestored={() => { runReturn.current = null; }} onContextChange={updateContext} onOpenRun={openRun} onProjectUpdated={(updated) => setProjects((current) => current.map((project) => project.project_id === updated.project_id ? { ...project, ...updated } : project))} />}
      {projectId && view.name === "run" && <RunDetail key={`${projectId}:${view.runId}`} projectId={projectId} runId={view.runId} onBack={returnFromRun} />}
      {projectId && view.name === "team" && <TeamView key={projectId} projectId={projectId} />}
    </main>
    {accountOpen && <AccountDialog onClose={() => setAccountOpen(false)} />}
    {creating && <Dialog title="Create a research project" busy={saving} onClose={() => { if (!saving) setCreating(false); }}><form onSubmit={create}>
      <div className="field"><label htmlFor="project-name">Project name</label><input id="project-name" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
      <div className="field contribution-surface"><label htmlFor="project-instructions">Problem brief</label><textarea id="project-instructions" required rows={7} value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} placeholder="Describe the problem, what you want the model to do, how observations arise, and your expectations or constraints." /><p className="hint">Use your own words. Data are optional, and unknown information can remain unknown. You can discuss and refine this account in every phase.</p></div>
      <details className="research-details"><summary>Prompts to help you begin</summary><ul><li>Who or what would be observed, and why would an observation enter the data?</li><li>What quantity, prediction, or decision should the model support?</li><li>Are data available, expected later, or absent? A conceptual problem is enough.</li><li>What performance, uncertainty, interpretability, or computational cost would be useful?</li></ul></details>
      {createError && <p className="error" role="alert">{createError}</p>}<button className="btn" disabled={saving || !form.name.trim() || !form.instructions.trim()}>{saving ? "Creating…" : "Create project"}</button>
    </form></Dialog>}
  </div>;
}
