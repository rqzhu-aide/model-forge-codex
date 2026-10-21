import React, { useEffect, useState } from "react";
import { PROBE_CHECK_LABELS, PROBE_CHECK_ORDER, ProbeController } from "../providerProbe";
import { ActionButton } from "./Visuals";

const STATUS_TITLES = { ok: "Connection verified", partial: "Partial success", failed: "Connection test failed" };
const CHECK_STATE_LABELS = { ok: "OK", failed: "Failed", skipped: "Not reached" };

// Pure rendering of one probe result. scopeLabel says which settings snapshot
// the result applies to ("Saved settings" / "Unsaved draft").
export function ProviderProbeResult({ result, scopeLabel }) {
  if (!result) return null;
  const status = Object.hasOwn(STATUS_TITLES, result.status) ? result.status : "failed";
  return <div className={`provider-probe-result ${status}`} role="status">
    <div className="provider-probe-summary">
      <strong>{STATUS_TITLES[status]}</strong>
      <span className="note">
        {scopeLabel}{result.simulated ? " · simulated backend" : ""}
        {typeof result.elapsed_ms === "number" ? ` · ${(result.elapsed_ms / 1000).toFixed(1)}s` : ""}
      </span>
    </div>
    <p>{result.summary}</p>
    {result.failure?.message && result.failure.message !== result.summary &&
      <p className="provider-probe-failure">{result.failure.message}</p>}
    <ul className="provider-probe-checks">
      {PROBE_CHECK_ORDER.map((stage) => {
        const state = result.checks?.[stage] || "skipped";
        return <li key={stage} className={`provider-probe-check ${state}`}>
          <span>{PROBE_CHECK_LABELS[stage] || stage}</span>
          <span className="provider-probe-check-state">{CHECK_STATE_LABELS[state] || state}</span>
        </li>;
      })}
    </ul>
  </div>;
}

// One probe button plus its latest result. The ProbeController drops the
// displayed result and retires any in-flight probe when `signature` changes
// (the settings a new probe would test), so a stale response is never shown
// against settings it did not test.
export function ProviderProbe({ signature, onProbe, disabled = false, scope = "saved", disabledReason = null }) {
  const [controller] = useState(() => new ProbeController());
  const [, setRevision] = useState(0);
  const refresh = () => setRevision((n) => n + 1);
  useEffect(() => { if (controller.sync(signature)) refresh(); }, [signature]);
  const { pending, result, error } = controller.state;

  const probe = async () => {
    if (disabled || controller.state.pending) return;
    controller.sync(signature);
    const request = controller.probe(onProbe);
    refresh();
    await request;
    refresh();
  };

  return <div className="provider-probe">
    <div className="provider-probe-actions">
      <ActionButton action="check" onClick={probe} disabled={disabled || pending}>
        {pending ? "Testing connection…" : scope === "draft" ? "Test these settings" : "Test saved settings"}</ActionButton>
      <span className="note">{disabledReason || (scope === "draft"
        ? "Tests the values shown here without saving. Sends a short live test and may use provider tokens."
        : "Tests this member's saved connection. Sends a short live test and may use provider tokens.")}</span>
    </div>
    {error && <div className="error" role="alert">{error.message || String(error)}</div>}
    <ProviderProbeResult result={result}
      scopeLabel={result?.scope === "draft" ? "Unsaved draft" : "Saved settings"} />
  </div>;
}
