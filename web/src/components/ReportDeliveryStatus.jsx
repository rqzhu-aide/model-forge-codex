import React from "react";
import { SourceRef } from "./Shared";

export default function ReportDeliveryStatus({ state, onSource, includeHistory = false }) {
  if (!state) return null;
  return <section className="report-delivery-status" aria-label="Report delivery">
    <p className="note">{state.message}{state.portable_export_check === "passed" && " Export check passed."}</p>
    {includeHistory && state.authored_delivery_note && <p className="note">{state.authored_delivery_note}</p>}
    {includeHistory && state.report_ref && onSource && <SourceRef reference={state.report_ref} onOpen={onSource} label="Report checked at publication" />}
  </section>;
}
