import React from "react";
import { empiricalExhibitPreview, empiricalExhibitSize } from "../compactEmpiricalResults";
import { EmpiricalExhibit } from "./EmpiricalQuestion";
import EmpiricalReadingButton from "./EmpiricalReading";

export default function CompactEmpiricalExhibit({ exhibit, primary = false, anchorId, readingAnchor, onSource }) {
  const preview = primary ? empiricalExhibitPreview(exhibit) : null;
  const title = exhibit.title || "Recorded exhibit";
  const table = Boolean(exhibit.table?.columns?.length);
  return <div id={primary ? undefined : anchorId} tabIndex={primary ? undefined : -1}
    data-reading-anchor={primary ? undefined : readingAnchor} className={primary ? "empirical-primary-exhibit" : "empirical-supporting-exhibit"}>
    {primary && <>
      <EmpiricalExhibit exhibit={preview.exhibit} sharedColumns={preview.sharedColumns} anchorId={anchorId} readingAnchor={readingAnchor} onSource={onSource} preview />
      {table && <p className="note empirical-preview-count">Showing {preview.count} {preview.count === 1 ? "row" : "rows"}{preview.contrast != null ? " for the first recorded contrast" : ""}.</p>}
    </>}
    <EmpiricalReadingButton kind="p4-exhibit" title={primary ? `Complete ${table ? "table" : "exhibit"}: ${title}` : title}
      sizeLabel={empiricalExhibitSize(exhibit)} input={{ exhibit }}
      renderBody={(input, openSource) => <EmpiricalExhibit exhibit={input.exhibit} onSource={openSource} />}
      onSource={onSource} />
    {!primary && exhibit.source_error && <p className="note warn" role="alert">{exhibit.source_error}</p>}
    {!primary && exhibit.source_verified === false && !exhibit.source_error && <p className="note warn">The saved exhibit could not be verified.</p>}
  </div>;
}
