import React, { useEffect, useId, useMemo, useRef, useState } from "react";
import { buildTheoryGraph, hasExactRef, humanLabel, relatedNodes, scoped } from "../research";
import { MathText, ResearchDocument, SourceRef } from "./Shared";
import { P3ProofAudit, TheoryLiteratureLinks } from "./PhaseEvidence";
import { conversationsForTarget } from "../assumptionConversations";
import { ActionButton } from "./Visuals";
import { TheoryConditions } from "./TheoryConditions";
import { TheoryAssessmentAccount, TheorySupportBadge, theoryAssessmentTone, theorySupportPresentation } from "./TheoryAssessment";

function nodePresentation(node, probes) {
  const support = theorySupportPresentation({ ...node.claim, ...node });
  const status = support.status;
  const adverseProbe = probes.some((probe) => probe.outcome === "fails_as_stated");
  const adverse = ["contradicted", "retracted"].includes(status) || support.reassessed && status === "rejected";
  const missingProof = node.kind === "claim" && support.missingProof;
  const uncertain = node.kind === "unresolved" || node.cycleAffected || missingProof || ["incomplete", "conditional"].includes(status) || support.reassessed && support.tone === "warn";
  const tone = adverse ? "fail" : uncertain || adverseProbe ? "warn" : "mut";
  const notices = [
    adverse ? humanLabel(status) : null,
    adverseProbe ? "Review probe scope" : null,
    node.cycleAffected ? "Circular support" : null,
    node.kind === "unresolved" ? "Support not resolved" : null,
    missingProof ? "Needs proof support" : null,
    ["incomplete", "conditional"].includes(status) ? humanLabel(status) : null,
    support.reassessed && status && !adverse && !["incomplete", "conditional"].includes(status) ? humanLabel(status) : null,
  ].filter(Boolean);
  const kindLabel = node.kind === "claim" ? support.reassessed ? "Claim" : `Claim · ${support.label}` : node.kind === "assumption" ? "Assumption" : "Unresolved reference";
  return { tone, notices, kindLabel, adverseProbe, proofStatus: support.proofStatus };
}

function GraphLegend() {
  const items = [
    { label: "Assumption", rounded: true },
    { label: "Claim" },
    { label: "Cited proof", dashed: true },
    { label: "Needs support or probe review", tone: "warn" },
    { label: "Contradicted or retracted", tone: "fail" },
    { label: "Selected", selected: true },
  ];
  return <div className="graph-legend" role="list" aria-label="Theory graph key">{items.map(({ label, rounded, dashed, tone, selected }) => <span className="graph-legend-item" role="listitem" key={label}>
    <svg width="34" height="24" viewBox="0 0 34 24" aria-hidden="true" focusable="false">
      {selected && <rect x="1" y="1" width="32" height="22" rx="5" fill="none" stroke="var(--accent)" strokeWidth="2" />}
      <rect x="5" y="5" width="24" height="14" rx={rounded ? 7 : 2} fill={selected ? "var(--panel-selected)" : "var(--panel)"} stroke={tone === "fail" ? "var(--danger)" : tone === "warn" ? "var(--warn)" : "var(--graph-edge)"} strokeWidth="1.5" strokeDasharray={dashed ? "4 2" : undefined} />
    </svg>{label}
  </span>)}</div>;
}

function StatementPreview({ value }) {
  if (!value) return <p className="note">No statement in this version.</p>;
  if (typeof value === "string") return <ResearchDocument text={value} />;
  return <>{value.latex && <MathText latex={value.latex} />}<ResearchDocument text={value.text || value.statement || value.summary || value} />{value.status && <p className="note">Status: {humanLabel(typeof value.status === "string" ? value.status : JSON.stringify(value.status))}</p>}</>;
}

export default function TheoryWorkbench({ claimMaps = [], falsificationLogs = [], glossaries = [], conversations = [], branch, selected, onSelect, onRequest, onSource, onAssumptionConversation, embedded = false, reading = {}, onReadingChange }) {
  const cm = scoped(claimMaps, branch, "P3")[0];
  const fl = scoped(falsificationLogs, branch, "P3")[0];
  const glossary = scoped(glossaries, branch, "P3")[0]?.glossary || {};
  const graph = useMemo(() => buildTheoryGraph(cm, glossary, cm?.assumptions || []), [cm, glossary]);
  const [hover, setHover] = useState(null); const [focus, setFocus] = useState(Boolean(reading.related)); const [search, setSearch] = useState(reading.search || "");
  const readingChange = useRef(onReadingChange); readingChange.current = onReadingChange;
  useEffect(() => { readingChange.current?.({ search, related: focus }); }, [search, focus]);
  const arrow = `theory-arrow-${useId().replace(/:/g, "")}`;
  const node = graph.nodes.find((n) => n.id === selected);
  const statement = node && { ...node.claim, ...node };
  const reference = cm?.theory_generation_ref || cm?.generation_ref;
  const linked = hasExactRef(reference) && ["theory_record", "complete_theory"].includes(reference.family);
  const selectionExists = graph.nodes.some((item) => item.id === selected);
  useEffect(() => { setHover(null); if (selected && !graph.nodes.some((n) => n.id === selected)) onSelect(null); }, [branch, cm?.generation_ref?.generation_id, cm?.theory_generation_ref?.generation_id, cm?.theory_generation_ref?.sha256, selectionExists]);
  if (!cm?.claims?.length) return <section className={embedded ? "theory-empty" : "card"} data-card-role={embedded ? undefined : "research"}>{!embedded && <h2>Claims, assumptions and proofs</h2>}<div className="body"><p className="note">{branch === "trunk" ? "Select a method to develop and inspect its theory." : "No theoretical claims have been recorded for this model yet."}</p></div></section>;
  const related = selected ? relatedNodes(graph, selected) : new Set(graph.nodes.map((n) => n.id));
  const visible = graph.nodes.filter((n) => (!focus || !selected || related.has(n.id)));
  const levelValues = [...new Set(visible.map((n) => graph.levels.get(n.id)))].sort((a, b) => a - b);
  const layers = levelValues.map((level) => visible.filter((n) => graph.levels.get(n.id) === level));
  const width = Math.max(480, Math.max(...layers.map((layer) => layer.length), 1) * 222 + 24);
  const height = Math.max(180, layers.length * 114 + 32);
  const positions = {};
  layers.forEach((layer, index) => layer.forEach((n, j) => { positions[n.id] = { x: (width - layer.length * 222) / 2 + 11 + j * 222, y: 18 + (layers.length - index - 1) * 114 }; }));
  const probesFor = (id) => (fl?.probes || []).filter((p) => p.target_statement === id);
  const targetFor = (n) => ({ ...reference, object_id: n.id, kind: n.kind === "claim" ? "statement" : "assumption" });
  const assumptionSource = node?.kind === "assumption" && linked && (cm.assumptions || []).find((assumption) => (assumption.assumption_id || assumption.id) === node.id);
  const conversationCount = assumptionSource ? conversationsForTarget(conversations, targetFor(node)).length : 0;
  const needsAttention = graph.nodes.filter((n) => nodePresentation(n, probesFor(n.id)).tone !== "mut");
  const detailNode = hover ? graph.nodes.find((n) => n.id === hover) : null;
  const revision = cm.revision_changes || cm.changes || [];
  return <section className={`${embedded ? "" : "card "}theory-workspace`} data-card-role={embedded ? undefined : "research"}>
    {embedded ? <h3>How the claims depend on each other</h3> : <h2>Theory dependency graph</h2>}
    <div className="body">
      {cm.source_warning && <p className="note warn">{cm.source_warning} Source browsing remains available. Publish a complete linked theory before requesting work on an individual component.</p>}
      {graph.issues.length > 0 && <div className="note warn" role="status"><b>Theory links need attention.</b><ul>{graph.issues.map((issue, i) => <li key={i}>{issue}</li>)}</ul></div>}
      {needsAttention.length > 0 && <div className="attention-components"><span className="note">Needs a closer look</span>{needsAttention.map((n) => <button key={n.id} className="chip" onClick={() => onSelect(n.id)}>{n.label}</button>)}</div>}
      <div className="graph-toolbar">
        <label className="field"><span className="visually-hidden">Find a theory component</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Find a statement or assumption" type="search" /></label>
        <label className="check-label"><input type="checkbox" checked={focus} disabled={!selected} onChange={(e) => setFocus(e.target.checked)} />Focus related components</label>
        <SourceRef reference={reference} onOpen={onSource} />
      </div>
      {search && <div className="search-results">{graph.nodes.filter((n) => `${n.label} ${n.id}`.toLowerCase().includes(search.toLowerCase())).map((n) => <ActionButton action="details" key={n.id} onClick={() => { onSelect(n.id); setSearch(""); }}>{n.label}</ActionButton>)}</div>}
      <div className={`graph-and-inspector ${node ? "has-selection" : ""}`}>
        <div className="graph-column">
          <p className="note graph-help">Hover or focus to preview. Select a component to inspect it and request a closer look. Arrows point from supporting components to the claims that use them.</p>
          <div className="graph-scroll" tabIndex={0} role="region" aria-label="Theory graph, scroll to explore">
            <svg viewBox={`0 0 ${width} ${height}`} width={width} height={height} role="group" aria-label="Theory dependency graph">
              <defs><marker id={arrow} viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 L8 4 L0 8z" fill="var(--graph-edge)" /></marker></defs>
              {graph.edges.filter((e) => positions[e.from] && positions[e.to]).map((e, i) => {
                const a = positions[e.from], b = positions[e.to]; const middle = (a.y + b.y + 72) / 2;
                const highlighted = selected && related.has(e.from) && related.has(e.to);
                return <path key={i} d={`M${a.x + 100} ${a.y} C${a.x + 100} ${middle},${b.x + 100} ${middle},${b.x + 100} ${b.y + 72}`} fill="none" stroke={highlighted ? "var(--accent)" : "var(--graph-edge)"} strokeWidth={highlighted ? 1.8 : 1.2} markerEnd={`url(#${arrow})`} />;
              })}
              {visible.map((n) => {
                const p = positions[n.id]; const probes = probesFor(n.id);
                const { tone, notices, kindLabel, adverseProbe, proofStatus } = nodePresentation(n, probes);
                const selectedHere = selected === n.id;
                const statusColor = tone === "fail" ? "var(--danger)" : tone === "warn" ? "var(--warn)" : "var(--ink-soft)";
                const probeLabel = !notices.length && probes.length && probes.every((probe) => probe.outcome === "holds") ? `${probes.length} recorded ${probes.length === 1 ? "probe held" : "probes held"}` : "";
                return <g key={n.id} role="button" tabIndex={0} aria-pressed={selectedHere} aria-label={[n.label, kindLabel, ...notices, adverseProbe ? "A probe records a failure. Inspect its tested scope and assumptions" : probeLabel].filter(Boolean).join(". ")} onMouseEnter={() => setHover(n.id)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(n.id)} onBlur={() => setHover(null)} onClick={() => onSelect(selectedHere ? null : n.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(selectedHere ? null : n.id); } }} className="theory-node" data-kind={n.kind} data-tone={tone}>
                  <rect className="theory-node-selection" x={p.x - 4} y={p.y - 4} width="208" height="80" rx={n.kind === "assumption" ? 27 : 10} fill="none" stroke={selectedHere || hover === n.id ? "var(--accent)" : "transparent"} strokeWidth={selectedHere ? 2.5 : 1.5} />
                  <rect className="theory-node-shape" x={p.x} y={p.y} width="200" height="72" rx={n.kind === "assumption" ? 23 : 6} fill={selectedHere ? "var(--panel-selected)" : "var(--panel)"} stroke={tone === "mut" ? "var(--graph-edge)" : statusColor} strokeWidth="1.5" strokeDasharray={n.kind === "claim" && proofStatus === "cited" ? "5 3" : undefined} />
                  <text className="theory-node-label" x={p.x + 100} y={p.y + 23} textAnchor="middle" fontSize="13" fill="var(--ink)">{n.label.length > 27 ? `${n.label.slice(0, 26)}…` : n.label}</text>
                  <text className="theory-node-kind" x={p.x + 100} y={p.y + 43} textAnchor="middle" fontSize="12" fill="var(--ink-soft)">{kindLabel}</text>
                  {(notices.length > 0 || probeLabel) && <text className="theory-node-status" x={p.x + 100} y={p.y + 61} textAnchor="middle" fontSize="12" fill={statusColor}>{notices[0] || probeLabel}</text>}
                </g>;
              })}
            </svg>
          </div>
          <GraphLegend />
          {detailNode && <div className="graph-preview" role="status"><b>{detailNode.label}</b>{(detailNode.latex || detailNode.claim?.latex) && <MathText latex={detailNode.latex || detailNode.claim.latex} />}{(detailNode.text || detailNode.claim?.text) && <ResearchDocument text={detailNode.text || detailNode.claim.text} />}</div>}
        </div>
        {node && <section className="tg-detail inspector" data-reading-anchor="theory-inspector" tabIndex={-1} aria-label={`Inspect ${node.label}`}>
          <div className="section-heading"><h3>{node.label}</h3><div className="assumption-heading-actions">
            {assumptionSource && onAssumptionConversation && <ActionButton action="ask" uiRole="research" className={`assumption-conversation-icon${conversationCount ? " has-history" : ""}`} title={conversationCount ? "Explain this assumption and view conversations" : "Explain this assumption"} aria-label={conversationCount ? `Explain this assumption. View assumption conversations (${conversationCount})` : "Explain this assumption"} aria-haspopup="dialog" onClick={() => onAssumptionConversation({ ...targetFor(node), label: node.label, statement: assumptionSource.text || assumptionSource.statement || node.text || node.statement, latex: assumptionSource.latex || node.latex })} />}
            <ActionButton action="close" onClick={() => onSelect(null)}>Close</ActionButton></div></div>
          {node.kind === "assumption" && !assumptionSource && <p className="note">A conversation needs this assumption's exact linked theory source. That source is not available for this graph item.</p>}
          {node.kind === "claim" ? !theorySupportPresentation(statement).reassessed && <TheorySupportBadge statement={statement} /> : <span className={`pill ${node.kind === "unresolved" ? "warn" : "mut"}`}>{humanLabel(node.kind)}</span>}
          {statement.status && <p className="note">Statement assessment: <span className={`pill ${theoryAssessmentTone(statement.status)}`}>{typeof statement.status === "string" ? humanLabel(statement.status) : JSON.stringify(statement.status)}</span></p>}
          {statement.latex && <MathText latex={statement.latex} />}
          <ResearchDocument text={statement.text || statement.statement || "The full statement is available in its theory source."} />
          <TheoryConditions statement={statement} />
          {node.kind !== "unresolved" && <div className="inspector-actions"><ActionButton action="check" uiRole="research" disabled={!linked || !onRequest} onClick={() => onRequest("assessment", targetFor(node), node.label)}>Request an assessment</ActionButton><ActionButton action="repair" uiRole="research" disabled={!linked || !onRequest} onClick={() => onRequest("repair", targetFor(node), node.label)}>Request a theory revision</ActionButton><p className="note">{linked ? "An assessment saves a separate check without changing the published theory. A theory revision can publish a changed account after the independent analyst audit and lead assessment." : "This component's exact theory source is unavailable. A linked theory generation is required before component work can be requested."}</p></div>}
          <TheoryAssessmentAccount statement={statement} onSource={onSource} />
          {node.kind === "claim" && graph.edges.some((e) => e.to === node.id) && <div className="inspector-group"><h4>Rests on</h4>{graph.edges.filter((e) => e.to === node.id).map((e) => <button key={e.from} className="chip" onClick={() => onSelect(e.from)}>{graph.nodes.find((n) => n.id === e.from)?.label}</button>)}</div>}
          {relatedNodes(graph, node.id, "downstream").size > 1 && <div className="inspector-group"><h4>Conclusions to reassess if this changes</h4>{graph.nodes.filter((n) => n.id !== node.id && relatedNodes(graph, node.id, "downstream").has(n.id)).map((n) => <button className="chip" key={n.id} onClick={() => onSelect(n.id)}>{n.label}</button>)}</div>}
          {node.claim?.novelty_refs?.length > 0 && <div className="inspector-group"><h4>Relation to the literature</h4><TheoryLiteratureLinks claim={node.claim} onSource={onSource} /></div>}
          <div className="inspector-group"><h4>Attempts to challenge this step</h4>{probesFor(node.id).length ? probesFor(node.id).map((probe) => <div className="probe-item" key={probe.probe_id}><span className={`pill ${probe.outcome === "fails_as_stated" ? "fail" : probe.outcome === "holds" ? "ok" : "mut"}`}>{humanLabel(probe.outcome)}</span><p><b>{probe.method}</b></p><ResearchDocument text={probe.detail} /></div>) : <p className="note">No targeted probes are recorded. This is not evidence that the step has been verified.</p>}</div>
          <SourceRef reference={reference} onOpen={onSource} />
        </section>}
      </div>
      {revision.length > 0 && <details className="research-details"><summary>What changed in this theory</summary>{revision.map((change, i) => <div className="revision-change" key={i}><h4>{change.label || humanLabel(change.statement_id || change.object_id || "Theory change")}</h4><div className="revision-comparison"><div><b>Previously</b><StatementPreview value={change.before} /></div><div><b>Now</b><StatementPreview value={change.after} /></div></div><ResearchDocument text={change.reason || change.summary || "No change explanation was recorded."} />{Array.isArray(change.affected) && change.affected.length > 0 && <div className="inspector-group"><h4>Affected conclusions</h4>{change.affected.map((id) => <button className="chip" key={id} onClick={() => onSelect(id)}>{humanLabel(id)}</button>)}</div>}</div>)}</details>}
      <details className="research-details"><summary>Full claim inventory and falsification log</summary><P3ProofAudit claimMaps={claimMaps} falsificationLogs={falsificationLogs} branch={branch} nodes={graph.nodes} onSelect={onSelect} onSource={onSource} /></details>
    </div>
  </section>;
}
