// Resume coordinates only. Rows are always fetched again from the verified source.
export const tableReadings = new Map();

export function tablePageIdentity(table) {
  const path = table?.next_page_url || table?.previous_page_url;
  if (!/^\/api\/v1\/projects\/[^/]+\/runs\/[^/]+\/outputs\/[^/]+\/table\?/.test(path || "")) return null;
  const url = new URL(path, "http://local.invalid");
  if (!/^[a-f0-9]{64}$/i.test(url.searchParams.get("sha256") || "") || !url.searchParams.get("path") || !url.searchParams.get("exhibit_id")) return null;
  url.searchParams.delete("offset"); url.searchParams.sort();
  return url.pathname + url.search;
}

export function tableResumeOffset(table, offset) {
  const size = Number.isInteger(table?.page_size) && table.page_size > 0 ? table.page_size : 200;
  const total = table?.total_rows;
  return Number.isInteger(offset) && offset >= 0 && Number.isInteger(total) && offset < total && offset % size === 0 ? offset : 0;
}

export function tablePageUrl(identity, offset) {
  if (!identity) return null;
  const url = new URL(identity, "http://local.invalid"); url.searchParams.set("offset", String(offset));
  return url.pathname + url.search;
}
