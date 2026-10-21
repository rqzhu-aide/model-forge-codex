import fs from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

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
    const identity = JSON.stringify([file.path, file.media_type]);
    let retained = cache.get(identity);
    if (!retained) {
      const bytes = readFile(file.path);
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
      return { identity: file.path, markdown: readRetained(key, file).bytes.toString("utf8") };
    },
  });
  return { ...input, assets, documents };
}
