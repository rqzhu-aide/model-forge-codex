export const portableDocumentCss = "body{box-sizing:border-box;max-width:64rem;margin:2rem auto;padding:0 1.4rem;color:#20242c;font:17px/1.65 Georgia,serif;overflow-wrap:anywhere}img,svg{max-width:100%}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd0d6;padding:.5rem;text-align:left}aside{background:#eef2f5;padding:1rem;font:14px/1.5 sans-serif}pre{overflow:auto}h1,h2,h3{line-height:1.25}.report-table,.report-equation{display:block;max-width:100%;overflow-x:auto}.report-table{overflow-wrap:normal}.report-equation .katex-display>.katex{min-width:max-content}a:focus-visible,.report-table:focus-visible,.report-equation:focus-visible{outline:2px solid #2c5c87;outline-offset:3px}:target{scroll-margin-top:1rem}";

export function retainedDownloadName(file, key) {
  return file?.export_filename || (file?.authored_path || key || "supporting-file").split(/[\\/]/).at(-1);
}

export function dataUriText(uri) {
  const match = /^data:[^,]*;base64,([^#]*)/.exec(uri || "");
  return match ? Buffer.from(match[1], "base64").toString("utf8") : null;
}

export function retainedTable(uri, mediaType) {
  if (mediaType !== "application/json") return null;
  const text = dataUriText(uri);
  if (text === null) return null;
  let value;
  try { value = JSON.parse(text); } catch { return null; }
  const rows = Array.isArray(value) ? value : value?.rows;
  if (!Array.isArray(rows) || !rows.length || !rows.every(row => row && typeof row === "object" && !Array.isArray(row))) return null;
  const declared = Array.isArray(value.columns) && value.columns.every(column => typeof column === "string"
    || column && typeof column.key === "string" && (column.label == null || typeof column.label === "string"));
  const columns = (declared ? value.columns : [...new Set(rows.flatMap(row => Object.keys(row)))])
    .map(column => typeof column === "string" ? { key: column, label: column } : column);
  return columns.length ? { columns, rows, ...(typeof value.caption === "string" ? { caption: value.caption } : {}) } : null;
}

export const reproductionMaterial = (key, file) => {
  const name = file.authored_path || key;
  return /\.(?:py|r|sh|toml|ya?ml)$/i.test(name)
    || /(?:^|\/)(?:readme(?:\.[^/]*)?|requirements[^/]*\.txt|[^/]*(?:config|environment)[^/]*\.json)$/i.test(name);
};
