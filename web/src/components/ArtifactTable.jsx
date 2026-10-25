import React, { useLayoutEffect, useRef, useState } from "react";
import { humanLabel } from "../research";
import { ActionButton } from "./Visuals";
import { tablePageIdentity, tablePageUrl, tableReadings, tableResumeOffset } from "../tableReading";
import { isVisibleElement } from "../dialogFocus";

const INLINE_PAGE_SIZE = 25;

// CSV numbers arrive as strings. Only recognize plain decimal/scientific values;
// leave identifiers, leading-zero codes, authored intervals and missing markers alone.
export function artifactTableCell(value) {
  if (value === null || value === undefined || value === "") return { text: "Not recorded" };
  if (typeof value === "object") return { text: JSON.stringify(value) };
  if (typeof value === "number" && !Number.isFinite(value)) return { text: "Not recorded" };
  const decimal = typeof value === "string" && /^-?(?:0|[1-9]\d*)(?:\.\d+(?:[eE][+-]?\d+)?|[eE][+-]?\d+)$/.test(value);
  const number = decimal ? Number(value) : value;
  if (typeof number !== "number" || !Number.isFinite(number)
      || (Number.isInteger(number) && !Number.isSafeInteger(number))
      || (number !== 0 && Math.abs(number) < 2.2250738585072014e-308)
      || (decimal && number === 0 && /[1-9]/.test(value.split(/[eE]/)[0]))) return { text: String(value) };
  // Six significant digits keep small differences in results readable, while
  // the original value remains available on the cell and in the saved artifact.
  const magnitude = Math.abs(number);
  const text = number === 0 ? "0" : magnitude < 1e-4 || magnitude >= 1e7
    ? number.toExponential(5).replace(/(\.\d*?[1-9])0+(?=e)|\.0+(?=e)/, "$1")
    : number.toLocaleString(undefined, { maximumSignificantDigits: 6 });
  const rounded = Number(number.toPrecision(6)) !== number;
  return { text, ...(rounded || (decimal && text !== value) ? { original: String(value) } : {}) };
}

export function artifactTablePage(table, inlineOffset = 0) {
  const rows = table.rows || []; const total = table.total_rows ?? rows.length;
  const inline = rows.length > INLINE_PAGE_SIZE && !table.truncated && !table.next_page_url && !table.previous_page_url && !table.row_offset && total === rows.length;
  return { rows: inline ? rows.slice(inlineOffset, inlineOffset + INLINE_PAGE_SIZE) : rows, offset: inline ? inlineOffset : table.row_offset || 0, total, inline };
}

// Each page comes from the verified artifact or complete inline table. Never
// infer column units or numerical uncertainty from a header or a caption.
export default function ArtifactTable({ table, title = "Recorded results", caption, describedBy }) {
  const tableContent = JSON.stringify(table); const identity = tablePageIdentity(table);
  const remembered = identity && tableReadings.get(identity);
  const saved = remembered?.content === tableContent ? remembered : null;
  const [page, setPage] = useState(table); const [busy, setBusy] = useState(Boolean(saved?.offset)); const [error, setError] = useState(null);
  const [inlineOffset, setInlineOffset] = useState(0);
  const request = useRef(0); const region = useRef(null);
  const coordinates = useRef(null);
  const pageRef = useRef(page); pageRef.current = page;
  // Generated tables are reconstructed during polling, even when unchanged.
  useLayoutEffect(() => {
    request.current += 1; setPage(table); setBusy(false); setError(null); setInlineOffset(0);
    if (identity && remembered && !saved) tableReadings.delete(identity);
    const offset = tableResumeOffset(table, saved?.offset);
    coordinates.current = saved ? { top: saved.top, left: saved.left } : { top: 0, left: 0 };
    if (offset && offset !== (table.row_offset || 0)) load(tablePageUrl(identity, offset), false);
    return () => {
      request.current += 1;
      if (identity && isVisibleElement(region.current) && tablePageIdentity(pageRef.current) === identity) tableReadings.set(identity, { content: tableContent, offset: pageRef.current.row_offset || 0, top: region.current.scrollTop, left: region.current.scrollLeft });
    };
  }, [tableContent]);
  useLayoutEffect(() => {
    if (busy || !coordinates.current || !region.current) return;
    const apply = () => {
      if (!coordinates.current || !isVisibleElement(region.current)) return;
      region.current.scrollTop = coordinates.current.top; region.current.scrollLeft = coordinates.current.left;
      coordinates.current = null;
    };
    apply();
    const disclosures = [];
    for (let parent = region.current.parentElement; parent; parent = parent.parentElement) if (parent.tagName === "DETAILS") { disclosures.push(parent); parent.addEventListener("toggle", apply); }
    return () => disclosures.forEach((details) => details.removeEventListener("toggle", apply));
  }, [page, busy]);
  const remember = (next = page) => {
    if (identity) tableReadings.set(identity, { content: tableContent, offset: next.row_offset || 0, top: region.current?.scrollTop || 0, left: region.current?.scrollLeft || 0 });
  };
  const moveInline = (offset) => { setInlineOffset(offset); region.current?.focus(); };
  const load = async (url, focus = true) => {
    if (focus && busy || !/^\/api\//.test(url || "")) return;
    const token = ++request.current; setBusy(true); setError(null);
    try {
      const response = await fetch(url); if (!response.ok) throw new Error("The saved table page could not be loaded.");
      const next = await response.json();
      if (!Array.isArray(next.columns) || !Array.isArray(next.rows) || next.rows.length > 200) throw new Error("The saved table page is invalid.");
      if (identity && tablePageIdentity(next) !== identity) throw new Error("The saved table source changed. Return to its current source.");
      if (request.current === token) {
        setPage(next);
        if (focus) { coordinates.current = { top: 0, left: region.current?.scrollLeft || 0 }; region.current?.focus({ preventScroll: true }); }
        if (focus) remember(next);
      }
    } catch (failure) { if (request.current === token) setError(failure.message); }
    finally { if (request.current === token) setBusy(false); }
  };
  if (!page?.columns?.length) return null;
  const { rows, offset, total, inline } = artifactTablePage(page, inlineOffset);
  const hasRoundedValues = rows.some((row) => page.columns.some((column) => artifactTableCell(row[column.key]).original));
  return <div className="artifact-table" aria-busy={busy} data-reading-pending={busy}>
    <div ref={region} onScroll={() => remember()} data-reading-anchor={identity ? `table:${identity}` : undefined} className="table-scroll" tabIndex={0} role="region" aria-label={title}><table aria-describedby={describedBy}>
      <caption className="sr-only">{caption || title}</caption>
      <thead><tr>{page.columns.map((column) => <th scope="col" key={column.key}>{!column.label || column.label === column.key ? humanLabel(column.key) : column.label}{column.unit && <span className="table-unit"> ({column.unit})</span>}</th>)}</tr></thead>
      <tbody>{rows.map((row, index) => <tr key={offset + index}>{page.columns.map((column) => { const cell = artifactTableCell(row[column.key]); return <td key={column.key} title={cell.original ? `Recorded value: ${cell.original}` : undefined}>{cell.text}</td>; })}</tr>)}</tbody>
    </table></div>
    {hasRoundedValues && <p className="note">Values are rounded for display; the original table retains full precision.</p>}
    {(page.truncated || offset > 0 || total > rows.length) && <div className="table-pagination"><p className="note" role="status">Rows {rows.length ? offset + 1 : 0} to {offset + rows.length} of {total}. Each page preserves the saved row order.</p><div className="btnrow">{inline ? <><ActionButton action="details" disabled={offset === 0} onClick={() => moveInline(offset - INLINE_PAGE_SIZE)}>Previous rows</ActionButton><ActionButton action="details" disabled={offset + rows.length >= total} onClick={() => moveInline(offset + INLINE_PAGE_SIZE)}>Next rows</ActionButton></> : <>{page.previous_page_url && <ActionButton action="details" disabled={busy} onClick={() => load(page.previous_page_url)}>Previous rows</ActionButton>}{page.next_page_url && <ActionButton action="details" disabled={busy} onClick={() => load(page.next_page_url)}>Next rows</ActionButton>}</>}</div>{!inline && !page.next_page_url && !page.previous_page_url && <p className="note">The original table contains the complete results.</p>}</div>}
    {error && <p className="error" role="alert">{error}</p>}
  </div>;
}
