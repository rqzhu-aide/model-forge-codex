import React, { createContext, useContext, useEffect, useId, useRef, useState } from "react";
import { api } from "../api";
import { sourceEntry } from "../researchContent";
import { phaseLabel, sameRef } from "../research";
import { correctionDispositions, hasSharedNotation, notationEntrySources, notationEntryTarget, notationGroups, notationReference, retainedNotation } from "../sharedNotation";
import { Dialog, MathText, ResearchDocument, SourceRef } from "./Shared";
import { ActionButton } from "./Visuals";
import "../sharedNotation.css";

const NotationContext = createContext({});
export const NotationProvider = NotationContext.Provider;

export function NotationLookup({ record, onSource, section, entryId, methodScope, label = "Notation" }) {
  const [opened, setOpened] = useState(null);
  const available = hasSharedNotation(record);
  if (!available && !opened) return null;
  const openedSource = notationReference(opened?.record), currentSource = notationReference(record);
  const newerRecord = available && openedSource && currentSource && !sameRef(openedSource, currentSource) ? record : null;
  return <><ActionButton action="details" variant="link" aria-haspopup="dialog" disabled={!available} onClick={() => setOpened({ record, methodScope })}>{label}</ActionButton>
    {opened && <NotationDialog record={opened.record} methodScope={opened.methodScope} newerRecord={newerRecord} onViewNewer={() => setOpened({ record, methodScope })} section={section} entryId={entryId} onSource={onSource} onClose={() => setOpened(null)} />}</>;
}

export function NotationDialog({ record, newerRecord, onViewNewer, section, entryId, methodScope, onSource, onClose, returnFocus }) {
  const sourceKey = JSON.stringify(notationReference(record));
  const previousSource = useRef(sourceKey), definitions = useRef(null);
  useEffect(() => {
    if (previousSource.current !== sourceKey) definitions.current?.focus();
    previousSource.current = sourceKey;
  }, [sourceKey]);
  return <Dialog title="Notation" className="shared-notation" onClose={onClose} returnFocus={returnFocus}>
    {newerRecord && <p className="note" role="status">A newer result is available. <ActionButton action="details" variant="link" onClick={onViewNewer}>View newer definitions</ActionButton></p>}
    <div ref={definitions} tabIndex={-1} role="region" aria-label="Notation definitions"><NotationContent key={sourceKey} record={record} section={section} entryId={entryId} methodScope={methodScope} onSource={onSource} /></div>
  </Dialog>;
}

export function NotationContent({ record, section, entryId, methodScope, onSource }) {
  const context = useContext(NotationContext);
  const retained = retainedNotation(record);
  const reference = notationReference(record);
  const sourceKey = JSON.stringify(reference);
  const [loaded, setLoaded] = useState(() => retained ? { notation: retained } : { loading: true });
  const [attempt, setAttempt] = useState(0);
  const [source, setSource] = useState(null);
  useEffect(() => {
    if (retained) { setLoaded({ notation: retained }); return; }
    if (!reference || !context.projectId) { setLoaded({ error: "The notation saved with this result is unavailable." }); return; }
    let active = true;
    setLoaded({ loading: true });
    api.notation(context.projectId, reference).then((result) => {
      if (active) setLoaded(result?.notation && Array.isArray(result.notation.entries) ? result : { error: "The notation saved with this result is unavailable." });
    }).catch((error) => { if (active) setLoaded({ error: error.message }); });
    return () => { active = false; };
  }, [sourceKey, attempt]);
  if (loaded.loading) return <p className="note" role="status">Loading this result's notation…</p>;
  if (loaded.error) return <div className="note warn" role="alert"><p>{loaded.error}</p><ActionButton action="retry" onClick={() => setAttempt((value) => value + 1)}>Retry</ActionButton></div>;
  const snapshot = loaded.notation;
  const groups = notationGroups(snapshot, { section, methodScope, methodIdentity: record?.method_identity || record?.method?.identity });
  const sources = context.projectId ? setSource : onSource || context.onSource;
  return <div className="notation-content">
    <p className="note notation-context">{methodScope ? "Definitions for this method and the shared study." : "Definitions used in this result."} A proof or comparison may use its own symbols.</p>
    {!groups.length && <p className="note">No active notation definitions are saved with this result.</p>}
    {groups.map((group) => group.collapsed ? <details className="research-details notation-scope" key={group.key} open={entryId && group.entries.some((entry) => entry.entry_id === entryId) ? true : undefined}><summary>{group.label}</summary><NotationRows {...{ snapshot, reference, sources, entryId }} entries={group.entries} /></details>
      : <section className="notation-scope" key={group.key}><h3>{group.label}</h3><NotationRows {...{ snapshot, reference, sources, entryId }} entries={group.entries} /></section>)}
    <SourceRef reference={snapshot.source_ref || reference} onOpen={sources} label="Result source" />
    {source && <NotationSource projectId={context.projectId} reference={source} onClose={() => setSource(null)} />}
  </div>;
}

// Keep the lookup mounted when it was itself opened inside a source reader.
// The ordinary project source window has one selected account, so reusing its
// selection here would discard this lookup's scroll position and invoker.
export function NotationSource({ projectId, reference, onClose }) {
  const [loaded, setLoaded] = useState({ loading: true }); const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true; setLoaded({ loading: true });
    api.recordBody(projectId, reference.branch, reference.phase, reference.family, reference.generation_id)
      .then((body) => { if (active) setLoaded({ body }); })
      .catch((failure) => { if (active) setLoaded({ error: failure.message }); });
    return () => { active = false; };
  }, [projectId, JSON.stringify(reference), attempt]);
  const body = loaded.body;
  return <Dialog title="Research source" onClose={onClose}>
    {loaded.loading ? <p className="note" role="status">Loading the exact definition source…</p> : loaded.error ? <div className="error" role="alert"><p>{loaded.error}</p><ActionButton action="retry" onClick={() => setAttempt((value) => value + 1)}>Retry</ActionButton></div>
      : <><ResearchDocument text={reference.entry_pointer || reference.card_id ? sourceEntry(body, reference.entry_pointer, reference.card_id) : typeof body === "string" ? body : body?.body_md || body?.text || body} /><details className="research-details"><summary>Complete record and reference</summary><pre className="record">{JSON.stringify(reference, null, 2)}</pre><pre className="record">{typeof body === "string" ? body : JSON.stringify(body, null, 2)}</pre></details></>}
  </Dialog>;
}

function NotationRows({ entries, snapshot, reference, sources, entryId }) {
  const context = useContext(NotationContext);
  const [correcting, setCorrecting] = useState(() => {
    const entry = entries.find((item) => item.entry_id === entryId);
    const target = entry && notationEntryTarget(snapshot, entry, reference);
    return target ? { target, entry } : null;
  });
  return <><dl className="notation-entries">{entries.map((entry) => {
    const target = notationEntryTarget(snapshot, entry, reference);
    const refs = notationEntrySources(entry);
    return <div className="notation-entry" key={entry.entry_id} data-notation-entry={entry.entry_id}>
      <dt><MathText latex={entry.symbol_latex} display={false} /></dt>
      <dd><ResearchDocument text={entry.definition_markdown} /><ResearchDocument text={entry.meaning_markdown} />
        {entry.source_symbol_mapping && <details className="research-details notation-mapping"><summary>Source symbol correspondence</summary>{entry.source_symbol_mapping.source_symbol_latex && <p>Source symbol: <MathText latex={entry.source_symbol_mapping.source_symbol_latex} display={false} /></p>}<ResearchDocument text={typeof entry.source_symbol_mapping === "string" ? entry.source_symbol_mapping : entry.source_symbol_mapping.explanation_markdown || entry.source_symbol_mapping.meaning_markdown || entry.source_symbol_mapping} /></details>}
        <div className="btnrow notation-entry-actions">{refs.map((ref, index) => <SourceRef key={index} reference={ref} onOpen={sources} label={{ definition: "Definition source", adoption: "Adoption source", scientific: "Scientific source" }[ref.source_role] || "Scientific source"} />)}
          {target && context.onDiscuss && <ActionButton action="ask" variant="link" uiRole="research" aria-haspopup="dialog" onClick={() => context.onDiscuss({ ...target, label: `Meaning of \\(${entry.symbol_latex}\\)`, statement: [entry.definition_markdown, entry.meaning_markdown].filter(Boolean).join("\n\n"), assessmentPurpose: "model_dialogue", responsible_role: "research_lead" })}>Explain</ActionButton>}
          {target && context.projectId && <ActionButton action="edit" variant="link" uiRole="research" aria-haspopup="dialog" onClick={() => setCorrecting({ target, entry })}>Correct</ActionButton>}
        </div>
      </dd>
    </div>;
  })}</dl>{correcting && <NotationCorrection key={JSON.stringify(correcting.target)} {...correcting} projectId={context.projectId} onSaved={context.onSaved} onSource={sources} onClose={() => setCorrecting(null)} />}</>;
}

export function NotationCorrection({ target, entry, projectId, onSaved, onSource, onClose }) {
  const id = useId(); const [loaded, setLoaded] = useState({ loading: true }); const [statement, setStatement] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState(""); const [saved, setSaved] = useState(false);
  const lock = useRef(false); const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    api.notationCorrection(projectId, target).then((result) => { if (active) { setLoaded(result); setStatement(result.item?.statement || ""); setError(""); } }).catch((failure) => { if (active) { setLoaded({}); setError(failure.message); } });
    return () => { active = false; };
  }, [projectId, JSON.stringify(target), attempt]);
  const reviewLatest = async () => {
    if (lock.current) return;
    lock.current = true; setBusy(true);
    try { setLoaded(await api.notationCorrection(projectId, target)); setError(""); }
    catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  };
  const save = async (event) => {
    event.preventDefault(); if (lock.current || !statement.trim()) return;
    lock.current = true; setBusy(true); setError(""); setSaved(false);
    try {
      const result = await api.saveNotationCorrection(projectId, { target, statement: statement.trim(), expected_revision: loaded.context_revision });
      setLoaded(result); setStatement(result.item?.statement || statement.trim()); setSaved(true); onSaved?.();
    } catch (failure) { setError(failure.message); }
    finally { lock.current = false; setBusy(false); }
  };
  const dispositions = correctionDispositions(loaded);
  const definitionPhase = { study: "P1", method: "P2" }[entry.scope?.kind];
  return <Dialog title="Correct a notation definition" className="notation-correction" busy={busy} onClose={onClose}>
    <p>Save a correction for future work. This saved result keeps its original definition.</p>
    {definitionPhase && target.phase !== definitionPhase && <p className="note notation-correction-routing">Saving here links your correction to the <span>{phaseLabel(target.phase)}</span> result. To include it in a <span>{phaseLabel(definitionPhase)}</span> revision, edit it from that phase’s notation view.</p>}
    <div className="notation-corrected-definition"><MathText latex={entry.symbol_latex} display={false} /><ResearchDocument text={entry.definition_markdown} /><ResearchDocument text={entry.meaning_markdown} /></div>
    {loaded.loading ? <p className="note" role="status">Loading your saved correction…</p> : <form className="researcher-input" data-ui-role="research" onSubmit={save}>
      <label className="field" htmlFor={`${id}-statement`}><span>Your correction</span><textarea id={`${id}-statement`} rows={5} value={statement} disabled={busy} onChange={(event) => { setStatement(event.target.value); setSaved(false); }} /></label>
      {error && <div className="error" role="alert"><p>{error}</p><ActionButton action="retry" disabled={busy} onClick={loaded.context_revision === undefined ? () => setAttempt((value) => value + 1) : reviewLatest}>{loaded.context_revision === undefined ? "Retry" : "Review latest saved context"}</ActionButton></div>}
      {saved && <p className="note" role="status">Correction saved for future work.</p>}
      {loaded.item && !saved && <p className="note">{statement === loaded.item.statement ? "Your correction is saved for future work." : "Save to use this update in future work. Work already started keeps its original inputs."}</p>}
      {loaded.item?.source_refs?.filter((source) => source.kind === "notation_entry").map((source, index) => <SourceRef key={index} reference={source} onOpen={onSource} label="Source addressed by saved correction" />)}
      {loaded.item && statement !== loaded.item.statement && <details className="research-details"><summary>Current saved correction</summary><ResearchDocument text={loaded.item.statement} /></details>}
      <div className="btnrow"><ActionButton action="save" uiRole="research" type="submit" disabled={busy || !statement.trim() || loaded.context_revision === undefined}>{busy ? "Saving…" : "Save correction"}</ActionButton></div>
    </form>}
    {dispositions.map((disposition, index) => <section className="notation-disposition" key={index}><h3>{disposition.label}</h3>{disposition.reason && <ResearchDocument text={disposition.reason} />}<SourceRef reference={disposition.source} onOpen={onSource} label="Team response source" /></section>)}
    {loaded.item?.history?.length > 0 && <details className="research-details"><summary>Earlier correction revisions</summary>{loaded.item.history.map((revision, index) => <ResearchDocument key={revision.revision || index} text={revision.statement} />)}</details>}
  </Dialog>;
}
