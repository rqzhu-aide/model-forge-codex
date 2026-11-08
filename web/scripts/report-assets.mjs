import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { gzipSync } from "node:zlib";
import { retainedDownloadName } from "./report-portable-materials.mjs";

// Python resolves and verifies every declared source before this handoff. The
// renderer accesses this map only when it actually renders an image or link.
export function reportAssetInput(input, readFile = fs.readFileSync) {
  const files = input.asset_files || {};
  const inline = input.assets || {};
  const cache = new Map();
  const retainedFile = (key) => {
    if (!Object.hasOwn(files, key)) return undefined;
    const file = files[key];
    if (!file || typeof file.path !== "string" || !path.isAbsolute(file.path)
        || typeof file.media_type !== "string" || !file.media_type
        || typeof file.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(file.sha256)) {
      throw new Error(`The report asset ${key} has invalid retained file metadata`);
    }
    return file;
  };
  const readRetained = (key, file) => {
    const identity = JSON.stringify([file.path, file.media_type, file.content_base64]);
    let retained = cache.get(identity);
    if (!retained) {
      const bytes = file.content_base64 === undefined ? readFile(file.path) : Buffer.from(file.content_base64, "base64");
      const digest = createHash("sha256").update(bytes).digest("hex");
      if (digest !== file.sha256) throw new Error(`The report asset ${key} changed after source verification`);
      retained = { digest, bytes, uri: `data:${file.media_type};base64,${bytes.toString("base64")}` };
      cache.set(identity, retained);
    }
    if (retained.digest !== file.sha256) throw new Error(`The report asset ${key} has conflicting retained digests`);
    return retained;
  };
  const assets = new Proxy(Object.create(null), {
    get(_target, key) {
      if (typeof key !== "string") return undefined;
      if (Object.hasOwn(inline, key)) return inline[key];
      const file = retainedFile(key);
      return file ? readRetained(key, file).uri : undefined;
    },
  });
  const documents = new Proxy(Object.create(null), {
    get(_target, key) {
      if (typeof key !== "string") return undefined;
      const file = retainedFile(key);
      if (!file || !(file.media_type === "text/markdown" || /\.md$/i.test(file.path))) return undefined;
      return { identity: file.path, artifact_id: file.artifact_id, media_type: file.media_type, path: file.authored_path || key,
        markdown: readRetained(key, file).bytes.toString("utf8") };
    },
  });
  const downloadForAsset = key => {
    const file = retainedFile(key);
    if (!file) return undefined;
    const retained = readRetained(key, file);
    const filename = retainedDownloadName(file, key);
    if (!input.shareable_export || file.download_url || retained.bytes.length < 128 * 1024
        || !/^(?:text\/|application\/(?:json|x-ndjson|jsonl)(?:$|;))/i.test(file.media_type)) {
      return { url: file.download_url || retained.uri, filename };
    }
    if (!retained.gzip) retained.gzip = gzipSync(retained.bytes, { level: 9 });
    if (retained.gzip.length > retained.bytes.length / 2) return { url: retained.uri, filename };
    const delivery = { encoding: "gzip", media_type: "application/gzip", filename: filename + ".gz",
      sha256: createHash("sha256").update(retained.gzip).digest("hex"),
      decoded_filename: filename, decoded_sha256: retained.digest };
    return { url: `data:application/gzip;base64,${retained.gzip.toString("base64")}`, filename: delivery.filename,
      delivery, source_sha256: file.source_sha256 || file.sha256 };
  };
  // A shareable HTML edition is rendered from its declared Markdown companion.
  // The authored HTML remains an immutable private source, including its footer.
  const documentForHtml = (key) => {
    const file = retainedFile(key);
    if (!file || file.media_type !== "text/html") return undefined;
    const authored = file.authored_path || key;
    const markdownPath = authored.replace(/\.html?$/i, ".md");
    const matches = Object.entries(files).filter(([alias, value]) =>
      value.media_type === "text/markdown" && (value.authored_path || alias) === markdownPath);
    const identities = new Set(matches.map(([, value]) => value.path));
    if (identities.size !== 1) return undefined;
    const [alias, markdownFile] = matches[0];
    const document = documents[alias];
    return { ...document, source_sha256: markdownFile.source_sha256 || markdownFile.sha256,
      aliases: Object.entries(files).filter(([, value]) => value.path === file.path || value.path === markdownFile.path).map(([name]) => name) };
  };
  let print_document;
  if (input.print_material_id !== undefined && input.print_material_id !== null) {
    const selected = input.print_material_id;
    if (typeof selected !== "string" || !selected) throw new Error("Select one exact submitted Markdown artifact to print");
    const matches = Object.entries(files).filter(([, file]) => file?.artifact_id === selected);
    if (!matches.length) throw new Error("The selected print material is not a declared report artifact");
    const identities = new Set(matches.map(([, file]) => JSON.stringify([file.path, file.media_type, file.sha256])));
    if (identities.size !== 1) throw new Error("The selected print material has ambiguous retained source metadata");
    const identity = matches[0][1].path;
    if (Object.entries(files).some(([key, file]) => file?.path === identity && (input.primary_paths || []).includes(key))) {
      throw new Error("Select a supporting Markdown artifact rather than the primary report");
    }
    const [key] = matches.find(([alias]) => /\.md$/i.test(alias)) || matches[0];
    const document = documents[key];
    if (!document || document.media_type !== "text/markdown") throw new Error("The selected print material is not a retained Markdown document");
    print_document = document;
  }
  const primaryPaths = new Set(input.primary_paths || []);
  if (input.shareable_export) {
    for (const [key, file] of Object.entries(files)) {
      if (file.media_type === "text/html" && documentForHtml(key)?.aliases.some(alias => primaryPaths.has(alias))) primaryPaths.add(key);
    }
  }
  return { ...input, primary_paths: [...primaryPaths], assets, documents, print_document, documentForHtml, downloadForAsset };
}
