import React from "react";
import { ActionButton } from "./Visuals";
import { fmt, fmtMs, humanLabel } from "../research";
import { MathText, ResearchDocument, ResearchInline, SourceRef } from "./Shared";
import { OriginalTheoristAccount, TheorySupportBadge } from "./TheoryAssessment";

/* Phase evidence panels (design/15 §5): structured diagnostics rendered from
   the P4 diagnostics record / exhibits, and the P3 claim map + falsification
   log. Never prose-parsed. */

const inScope = (x, branch) => x.branch === branch;

// Native disclosures are captured with the reader's scroll position. Splitting
// after the preview keeps every row once and restores expansion on reopen.
function DiagnosticRows({ rows, renderTable }) {
  return <>{renderTable(rows.slice(0, 5))}{rows.length > 5 && <details className="research-details diagnostic-row-expansion"><summary>Show all {rows.length} rows</summary>{renderTable(rows.slice(5))}</details>}</>;
}

export function DiagnosticsTables({ d, metrics = {} }) {
  const metricLabel = row => metrics[row.metric_id || row.metric]?.name || d.metric_labels?.[row.metric_id || row.metric] || row.metric_id || row.metric || "Not recorded";
  return (
        <div style={{ marginBottom: 14 }}>
          <h3>Diagnostics</h3>
          {(d.headline_numbers?.length > 0) && (
            <>
            <DiagnosticRows rows={d.headline_numbers} renderTable={(rows) => <div className="table-scroll" tabIndex={0} role="region" aria-label="Diagnostic table, scroll to inspect all columns"><table>
              <thead><tr><th>Case</th><th>Metric</th><th>Unit</th><th>Estimate</th><th>Uncertainty</th><th>Usable repetitions</th><th>Recorded interval</th><th>Interval level</th></tr></thead>
              <tbody>
                {rows.map((r, j) => (
                  <tr key={j}>
                    <td className="rid"><ResearchInline text={r.case_id} /></td><td><ResearchInline text={metricLabel(r)} /></td><td><ResearchInline text={r.unit || metrics[r.metric_id || r.metric]?.unit || metrics[r.metric_id || r.metric]?.units || "Not recorded"} /></td>
                    <td><b>{fmt(r.estimate, { uncertainty: r.mcse })}</b></td><td className="note">{r.uncertainty_kind === "not_applicable" ? "Not applicable" : r.uncertainty_kind === "not_assessed" ? "Not assessed" : r.uncertainty_kind === "custom" ? "See protocol" : Number.isFinite(r.mcse) ? `MCSE ${fmt(r.mcse)}` : "Not assessed"}</td>
                    <td>{fmt(r.n_replicates, { kind: "count" })}</td><td className="note">{r.ci_lo != null && r.ci_hi != null ? `[${fmt(r.ci_lo)}, ${fmt(r.ci_hi)}]` : "Not recorded"}</td><td>{typeof r.confidence_level === "number" ? `${fmt(r.confidence_level * 100)}%` : "Not recorded"}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>} />
            </>
          )}
          {d.stability?.length > 0 && (
            <>
              <h3 style={{ marginTop: 10 }}>Stability across seeds</h3>
              <DiagnosticRows rows={d.stability} renderTable={(rows) => <div className="table-scroll" tabIndex={0} role="region" aria-label="Diagnostic table, scroll to inspect all columns"><table>
                <thead><tr><th>Case</th><th>Metric</th><th>Mean ± sd</th><th>Seeds</th><th>Verdict flips?</th></tr></thead>
                <tbody>
                  {rows.map((r, j) => (
                    <tr key={j}>
                      <td className="rid"><ResearchInline text={r.case_id} /></td><td><ResearchInline text={metricLabel(r)} /></td>
                      <td>{fmt(r.mean, { uncertainty: r.sd })} ± {fmt(r.sd)}</td>
                      <td className="note">{fmt(r.n_seeds, { kind: "count" })}</td>
                      <td><span className={`pill ${r.seed_flip === true ? "fail" : r.assessment === "not_applicable" || r.assessment === "not_assessed" || r.n_seeds < 2 || r.seed_flip == null ? "mut" : "ok"}`}>{r.assessment === "not_applicable" ? "Not applicable" : r.assessment === "not_assessed" ? "Not assessed" : r.seed_flip === true ? "Unstable" : r.n_seeds < 2 ? "Not repeated" : r.seed_flip == null ? "Not assessed" : "No recorded flip"}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table></div>} />
            </>
          )}
          <div className="duo">
            {d.solver_health?.length > 0 && (
              <div>
                <h3>Completion and convergence</h3>
                <p className="note">Includes unrun cases, failed attempts and reported nonconvergence; this is not a count of solver failures.</p>
                <div className="table-scroll" tabIndex={0} role="region" aria-label="Diagnostic table, scroll to inspect all columns"><table>
                  <thead><tr><th>Regime</th><th>Recorded checks</th><th>Incomplete or nonconverged</th><th>Share</th></tr></thead>
                  <tbody>
                    {d.solver_health.map((r, j) => (
                      <tr key={j}>
                        <td><ResearchInline text={r.regime} /></td><td>{fmt(r.n_runs, { kind: "count" })}</td>
                        <td>{fmt(r.n_failures, { kind: "count" })}</td>
                        <td>{typeof r.failure_rate === "number" ? `${fmt(r.failure_rate * 100)}%` : "Not assessed"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table></div>
              </div>
            )}
            {d.runtime && (
              <div>
                <h3>Computational cost</h3>
                <div className="table-scroll" tabIndex={0} role="region" aria-label="Diagnostic table, scroll to inspect all columns"><table>
                  <thead><tr><th>Case</th><th>Mean</th><th>Max</th></tr></thead>
                  <tbody>
                    {(d.runtime.per_case || []).map((r, j) => (
                      <tr key={j}><td className="rid"><ResearchInline text={r.case_id} /></td><td>{fmtMs(r.mean_ms)}</td><td>{fmtMs(r.max_ms)}</td></tr>
                    ))}
                    <tr><td><b>Sum of case times</b></td><td colSpan="2"><b>{fmtMs(d.runtime.total_ms)}</b></td></tr>
                  </tbody>
                </table></div>
                {d.environment && (
                  <div className="note" style={{ marginTop: 6 }}>
                    Python environment: {d.environment.python} · {d.environment.platform}
                    {d.environment.packages ? " · " + Object.entries(d.environment.packages).map(([k, v]) => `${k} ${v}`).join(", ") : ""}
                  </div>
                )}
                {d.regenerated_by && (
                  <div className="note">Recorded regeneration script: <code>{d.regenerated_by}</code>. Aggregate/source checks do not rerun the original experiments.</div>
                )}
              </div>
            )}
          </div>
        </div>
  );
}

export function TheoryLiteratureLinks({ claim, onSource }) {
  const links = claim?.novelty_links || [];
  return <ul>{(claim?.novelty_refs || []).map((id) => {
    const matches = links.filter((item) => item.identifier === id);
    return <li key={id} title={id}>{matches.length ? matches.map((link, index) => <div key={index}>{link.label || humanLabel(id)}{link.generation_ref ? <SourceRef reference={link.generation_ref} onOpen={onSource} label="Read supporting literature" /> : <p className="note">{link.source_error || "The exact literature source is not linked in this record."}</p>}</div>) : <>{humanLabel(id)}<p className="note">The exact literature source is not linked in this record.</p></>}</li>;
  })}</ul>;
}

export function P3ProofAudit({ claimMaps, falsificationLogs, branch, nodes = [], onSelect, onSource }) {
  const cms = claimMaps.filter((c) => c.phase === "P3" && inScope(c, branch));
  const fls = falsificationLogs.filter((f) => f.phase === "P3" && inScope(f, branch));
  if (!cms.length && !fls.length) return null;
  const labelFor = (id) => nodes.find((node) => node.id === id)?.label || humanLabel(id);
  const component = (id) => id && nodes.some((node) => node.id === id && node.kind !== "unresolved") && onSelect
    ? <ActionButton action="details" variant="link" title={id} onClick={() => onSelect(id)}>{labelFor(id)}</ActionButton>
    : <span title={id}>{labelFor(id) || "Not recorded"}</span>;
  return <>
    {cms.map((c, i) => <section key={i}>
      <h3>Claims and their support</h3>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Claim inventory, scroll to inspect all columns"><table>
        <thead><tr><th>Statement</th><th>Assessment / support</th><th>Depends on</th><th>Relation to the literature</th></tr></thead>
        <tbody>{(c.claims || []).map((cl, j) => <tr key={j}>
          <td>{component(cl.statement_id)}{cl.latex && <MathText latex={cl.latex} />}</td>
          <td><TheorySupportBadge statement={cl} /><OriginalTheoristAccount statement={cl} onSource={onSource} compact /></td>
          <td>{cl.depends_on?.length ? cl.depends_on.map((id) => <div key={id}>{component(id)}</div>) : "None recorded"}</td>
          <td>{cl.novelty_refs?.length ? <TheoryLiteratureLinks claim={cl} onSource={onSource} /> : "None recorded"}</td>
        </tr>)}</tbody>
      </table></div>
      <SourceRef reference={c.theory_generation_ref || c.generation_ref} onOpen={onSource} label="Complete claim source" />
    </section>)}
    {fls.map((f, i) => <section key={i}>
      <h3>Attempts to challenge the claims</h3>
      <div className="table-scroll" tabIndex={0} role="region" aria-label="Theory probes, scroll to inspect all columns"><table>
        <thead><tr><th>Probe</th><th>Target</th><th>Outcome</th><th>What was tested</th></tr></thead>
        <tbody>{(f.probes || []).map((pr, j) => <tr key={j}>
          <td title={pr.probe_id}>{pr.label || humanLabel(pr.probe_id)}</td><td>{component(pr.target_statement)}</td>
          <td><span className={`pill ${pr.outcome === "holds" ? "ok" : pr.outcome === "fails_as_stated" ? "fail" : "mut"}`}>{humanLabel(pr.outcome) || "Not recorded"}</span></td>
          <td>{pr.method && <ResearchDocument text={pr.method} headingLevel={4} />}<ResearchDocument text={pr.detail} headingLevel={4} /></td>
        </tr>)}</tbody>
      </table></div>
      <SourceRef reference={f.generation_ref} onOpen={onSource} label="Complete probe source" />
    </section>)}
  </>;
}
