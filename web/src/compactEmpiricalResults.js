// Display selection uses recorded topics, author priority and column roles.
// Titles and project-specific exhibit IDs never determine a table's purpose.
const columnName = (column) => String(column.key || "").replace(/[^a-z0-9]/gi, "").toLowerCase();
const designColumns = new Set(["contrast", "comparison", "condition", "scenario", "study", "studygroup", "method", "comparator"]);
const usable = (exhibit) => exhibit.source_verified !== false && !exhibit.source_error
  && (exhibit.table?.columns?.length && exhibit.table?.rows?.length
    || exhibit.artifact_url && String(exhibit.media_type || "").startsWith("image/"));

export function empiricalTableRoles(table = {}) {
  const columns = table.columns || [];
  const contrast = columns.find((column) => ["contrast", "comparison"].includes(columnName(column)));
  const study = columns.find((column) => ["study", "studygroup"].includes(columnName(column)));
  const difference = columns.some((column) => /difference|effect|gain/.test(columnName(column)));
  const uncertainty = columns.some((column) => /standarderror|mcse|confidenceinterval|uncertainty/.test(columnName(column)));
  return { contrast, paired: Boolean(contrast && difference && uncertainty), prior: Boolean(study && new Set((table.rows || []).map((row) => row[study.key]).filter((value) => value != null)).size > 1) };
}

export function primaryEmpiricalExhibits(routed = [], summary) {
  const priority = summary?.decision_summary?.headline_exhibit_ids || [];
  const candidates = routed.filter(({ exhibit, topic }) => {
    if (!["comparisons", "actual_data"].includes(topic) || !usable(exhibit)) return false;
    const ref = exhibit.generation_ref, owner = summary?.generation_ref;
    return !owner || ["branch", "phase", "run_id", "package_id"].every((key) => !owner[key] || !ref?.[key] || owner[key] === ref[key]);
  }).sort((a, b) => {
    const rank = ({ exhibit }) => priority.includes(exhibit.exhibit_id) ? priority.indexOf(exhibit.exhibit_id) : priority.length;
    return rank(a) - rank(b);
  });
  const selected = [];
  const add = (entry) => { if (entry && selected.length < 2 && !selected.includes(entry)) selected.push(entry); };
  // The Lead's available headline choices precede any inferred display role.
  // Use column roles within that set, then fill any vacancy from other evidence.
  for (const group of [candidates.filter(({ exhibit }) => priority.includes(exhibit.exhibit_id)), candidates.filter(({ exhibit }) => !priority.includes(exhibit.exhibit_id))]) {
    add(group.find(({ exhibit }) => empiricalTableRoles(exhibit.table).paired));
    add(group.find(({ exhibit }) => empiricalTableRoles(exhibit.table).prior));
    group.forEach(add);
  }
  return selected;
}

export function empiricalExhibitSize(exhibit = {}) {
  const table = exhibit.table;
  if (!table?.columns?.length) return String(exhibit.media_type || "").startsWith("image/") ? "1 figure" : "Saved exhibit";
  const known = Number.isInteger(table.total_rows) ? table.total_rows : !(table.truncated || table.next_page_url || table.previous_page_url || table.row_offset) ? (table.rows || []).length : null;
  return `${known == null ? "Row count unavailable" : `${known} ${known === 1 ? "row" : "rows"}`} · ${table.columns.length} ${table.columns.length === 1 ? "column" : "columns"}`;
}

export function empiricalExhibitPreview(exhibit, limit = 6) {
  const table = exhibit.table;
  if (!table?.columns?.length) return { exhibit };
  const { contrast, paired } = empiricalTableRoles(table);
  // Show the first saved contrast across conditions, including empty joint
  // subsets. Selecting only successful or finite estimates would distort it.
  const first = table.rows?.[0]?.[contrast?.key];
  const selected = paired && first != null ? table.rows.filter((row) => row[contrast.key] === first) : table.rows || [];
  const rows = selected.slice(0, limit);
  // Only design labels can move into the caption. Equal estimates, counts or
  // standard errors are results in their own right, even when they are zero.
  const sharedColumns = rows.length > 1 ? table.columns.filter(column => {
    const value = rows[0][column.key];
    return designColumns.has(columnName(column)) && typeof value === "string" && value.trim() !== ""
      && rows.every(row => row[column.key] === value);
  }) : [];
  const remaining = table.columns.filter(column => !sharedColumns.includes(column));
  const factor = sharedColumns.length > 0 && remaining.length > 0;
  const { row_offset, total_rows, truncated, next_page_url, previous_page_url, ...content } = table;
  return {
    exhibit: { ...exhibit, table: { ...content, columns: factor ? remaining : table.columns, rows } },
    sharedColumns: factor ? sharedColumns.map(column => ({ ...column, value: rows[0][column.key] })) : [],
    contrast: paired && first != null ? first : null, count: rows.length,
  };
}
