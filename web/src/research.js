// Shared research semantics. Kept independent of React for focused contract checks.
export const PHASES = [["P1", "Phase 1 - Define and Explore"], ["P2", "Phase 2 - Propose Methods"], ["P3", "Phase 3 - Theory"], ["P4", "Phase 4 - Numerical Eval"], ["P5", "Phase 5 - Report"]];
export const phaseLabel = (phase) => PHASES.find(([id]) => id === phase)?.[1] || phase;
export const TERMINAL = new Set(["published", "assessed", "failed", "cancelled"]);
// The activity endpoint also closes while a run waits for researcher direction.
// Keep that state distinct from terminal work, since it can resume in another tab.
export const activityIsSettled = (state) => TERMINAL.has(state) || state === "awaiting_user";
export const shouldReconnectActivity = (previousState, nextState, closedState = null) => Boolean(nextState)
  && !activityIsSettled(nextState) && (activityIsSettled(previousState) || activityIsSettled(closedState));
export const OUTCOMES = {
  supported: ["ok", "Supported"], partially_supported: ["warn", "Partly supported"],
  contradicted: ["fail", "Contradicted"], inconclusive: ["warn", "Inconclusive"],
  not_assessed: ["mut", "Not assessed"], not_applicable: ["mut", "Not applicable"],
  mixed: ["warn", "Mixed"], no_advantage: ["mut", "No advantage"], not_evaluated: ["mut", "Not evaluated"],
  no_observed_advantage: ["mut", "No observed advantage"],
};
export const outcome = (state) => OUTCOMES[state] || ["mut", state ? humanLabel(state) : "Not assessed"];
export const humanLabel = (value = "") => String(value).replace(/^(statement|assumption|method|case|probe)\./, "").replace(/[_.-]+/g, " ").replace(/^\w/, (c) => c.toUpperCase());
export const modeLabel = (mode = "") => ({ "p2.full_catalog": "Model development", "p2.researcher_proposal": "Models with lead instructions", "p3.assessment": "Take another look", "p3.theory_revision": "Revise theory", "p3.theory_establishment": "Establish theory", "p4.preliminary": "Feasibility check", "p4.comprehensive": "Detailed evaluation" }[mode] || humanLabel(mode.replace(/^p\d\./, "")));
export const scoped = (items = [], branch, phase) => (Array.isArray(items) ? items : []).filter((item) => item && item.branch === branch && (!phase || item.phase === phase));
export const latestRunForScope = (runs = [], branch, phase) => runs.filter((run) => run.branch_id === branch && run.phase === phase).sort((a, b) => String(b.created_at || b.requested_at || b.run_id || "").localeCompare(String(a.created_at || a.requested_at || a.run_id || "")))[0];
export const refKey = (ref) => ref ? [ref.branch, ref.phase, ref.family, ref.generation_id, ref.sha256].join("|") : "";
export const sameRef = (a, b) => Boolean(a && b && refKey(a) === refKey(b));
export const hasExactRef = (ref) => Boolean(ref?.branch && ref?.phase && ref?.family && ref?.generation_id && ref?.sha256);
export const freshId = () => globalThis.crypto.randomUUID();
// Display precision never changes the retained value or rounds authored prose.
export function fmt(value, { uncertainty, kind } = {}) {
  if (typeof value !== "number") return value ?? "Not recorded";
  if (!Number.isFinite(value)) return "Not recorded";
  if (value === 0) return "0";
  if (kind === "count") return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
  const magnitude = Math.abs(value);
  if (Number.isInteger(value) && magnitude < 1e7 && !(Number.isFinite(uncertainty) && uncertainty > 0)) return value.toLocaleString();
  const digits = Number.isFinite(uncertainty) && uncertainty > 0
    ? Math.max(1, Math.min(15, Math.floor(Math.log10(magnitude)) - Math.floor(Math.log10(uncertainty)) + 2)) : 3;
  if (magnitude < 1e-4 || magnitude >= 1e7) return value.toExponential(digits - 1);
  return value.toLocaleString(undefined, { maximumSignificantDigits: digits });
}
export const fmtMs = (ms) => !Number.isFinite(ms) ? "Not recorded" : ms >= 60000 ? `${fmt(ms / 60000)} min` : ms >= 1000 ? `${fmt(ms / 1000)} s` : `${fmt(ms)} ms`;
export function fmtBudgetSeconds(seconds) {
  if (!Number.isFinite(seconds)) return "Not recorded";
  if (seconds === 0) return "0 s";
  if (seconds > 0 && seconds < 0.1) return "<0.1 s";
  if (seconds < 10) return `${Number(seconds.toFixed(1))} s`;
  const rounded = Math.round(seconds);
  if (rounded < 60) return `${rounded} s`;
  const minutes = Math.floor(rounded / 60); const remainder = rounded % 60;
  return `${minutes.toLocaleString()} min${remainder ? ` ${remainder} s` : ""}`;
}

export function normalizeModes(readiness) {
  return (readiness?.modes || []).map((m) => typeof m === "string"
    ? { mode: m, label: modeLabel(m), ready: Boolean(readiness.ready), reasons: readiness.reasons || [], basis: readiness.basis }
    : { ...m, mode: m.mode || m.mode_id, label: modeLabel(m.mode || m.mode_id) || m.label, ready: m.ready ?? Boolean(readiness.ready), reasons: m.reasons || [], basis: m.basis || readiness.basis });
}

// Dependency references must resolve to registered objects. Never turn a missing
// statement into an assumption, and never invent a DAG ordering for a cycle.
export function buildTheoryGraph(claimMap, glossary = {}, registeredAssumptions = []) {
  const nodes = new Map();
  const issues = [];
  for (const claim of Array.isArray(claimMap?.claims) ? claimMap.claims : []) {
    if (!claim?.statement_id) { issues.push("A claim has no statement identifier."); continue; }
    if (nodes.has(claim.statement_id)) { issues.push(`Duplicate statement: ${claim.statement_id}`); continue; }
    nodes.set(claim.statement_id, { id: claim.statement_id, kind: "claim", claim, ...glossary[claim.statement_id], label: claim.label || glossary[claim.statement_id]?.label || humanLabel(claim.statement_id) });
  }
  const assumptions = [...registeredAssumptions, ...Object.entries(glossary).filter(([, g]) => g.statement_type === "assumption" || g.kind === "assumption").map(([id, g]) => ({ assumption_id: id, ...g }))];
  for (const assumption of assumptions) {
    const id = assumption.assumption_id || assumption.id;
    if (id && !nodes.has(id)) nodes.set(id, { ...assumption, ...glossary[id], id, kind: "assumption", label: assumption.label || glossary[id]?.label || humanLabel(id) });
  }
  const edges = [];
  for (const node of [...nodes.values()].filter((n) => n.kind === "claim")) {
    for (const from of new Set(Array.isArray(node.claim.depends_on) ? node.claim.depends_on : [])) {
      if (!nodes.has(from)) {
        nodes.set(from, { id: from, kind: "unresolved", label: humanLabel(from) });
        issues.push(`Unresolved dependency: ${from}`);
      }
      edges.push({ from, to: node.id });
    }
  }
  const indegree = new Map([...nodes.keys()].map((id) => [id, edges.filter((e) => e.to === id).length]));
  const levels = new Map([...nodes.keys()].map((id) => [id, 0]));
  const queue = [...nodes.keys()].filter((id) => !indegree.get(id));
  const visited = new Set();
  while (queue.length) {
    const id = queue.shift(); visited.add(id);
    for (const edge of edges.filter((e) => e.from === id)) {
      levels.set(edge.to, Math.max(levels.get(edge.to), levels.get(id) + 1));
      indegree.set(edge.to, indegree.get(edge.to) - 1);
      if (!indegree.get(edge.to)) queue.push(edge.to);
    }
  }
  const blocked = [...nodes.keys()].filter((id) => !visited.has(id));
  if (blocked.length) issues.push("Circular dependency detected. The marked claims form a cycle or depend on one; their ordering cannot establish proof support.");
  for (const id of blocked) { levels.set(id, 1); nodes.get(id).cycleAffected = true; }
  return { nodes: [...nodes.values()], edges, levels, issues };
}

export function relatedNodes(graph, id, direction = "both") {
  const found = new Set([id]);
  const walk = (reverse) => {
    const queue = [id]; const seen = new Set([id]);
    while (queue.length) {
      const current = queue.shift();
      for (const edge of graph.edges) {
        if ((reverse ? edge.to : edge.from) !== current) continue;
        const next = reverse ? edge.from : edge.to;
        if (!seen.has(next)) { seen.add(next); found.add(next); queue.push(next); }
      }
    }
  };
  if (direction !== "downstream") walk(true);
  if (direction !== "upstream") walk(false);
  return found;
}

export function diagnosticOverview(diagnostics = []) {
  const stability = diagnostics.flatMap((d) => d.stability || []);
  const health = diagnostics.flatMap((d) => d.solver_health || []);
  return {
    unstable: stability.filter((row) => row.seed_flip === true).length,
    stabilityRows: stability.length,
    underRepeated: stability.filter((row) => row.assessment !== "not_applicable" && (!Number.isFinite(row.n_seeds) || row.n_seeds < 2)).length,
    // The recorded count includes unrun cases and reported nonconvergence.
    incompleteOrNonconverged: health.reduce((sum, row) => sum + (Number(row.n_failures) || 0), 0),
    recordedChecks: health.reduce((sum, row) => sum + (Number(row.n_runs) || 0), 0),
  };
}

// Method-freshness display for published P3–P5 work. The status object is the
// backend's derived projection (methods.py); the UI only renders it.
export function methodUpdateMessage(status) {
  if (!status || status.status === "current") return null;
  if (status.status === "needs_update") {
    const used = status.recorded_identity?.version ?? status.recorded_version;
    return `Needs update: this work used model version ${used ?? "an earlier version"}. The current model is version ${status.current_version}.`;
  }
  return status.message || "This work's model applicability cannot be established.";
}

export function methodStatusBadge(status) {
  if (!status || status.status === "current") return null;
  return status.status === "needs_update" ? ["warn", "Needs update"] : ["mut", "Applicability unknown"];
}

export function phaseOutputStatus(method, phase) {
  return (method?.dependent_outputs || []).find((output) => output.phase === phase) || null;
}

export function phaseLaunchLabel(phase, outputStatus) {
  if (phase === "P3" && outputStatus?.status === "needs_update" && outputStatus.current_version)
    return `Update theory for model v${outputStatus.current_version}`;
  if (phase === "P3") return "Develop theory";
  if (phase === "P4") return "Prepare evaluation";
  return `Run ${phaseLabel(phase)}`;
}
