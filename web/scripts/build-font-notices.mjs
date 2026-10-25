import fs from "node:fs/promises";
import path from "node:path";
import { sharedPackage } from "./shared-deps.mjs";

const fonts = [
  ["@fontsource-variable/ibm-plex-sans", "IBM-PLEX-SANS-LICENSE.txt"],
  ["@fontsource/ibm-plex-mono", "IBM-PLEX-MONO-LICENSE.txt"],
  ["@fontsource/marcellus", "MARCELLUS-LICENSE.txt"],
];

export async function buildFontNotices(outDir) {
  const notices = [];
  await fs.mkdir(outDir, { recursive: true });
  for (const [name, license] of fonts) {
    const metadata = JSON.parse(await fs.readFile(sharedPackage(name, "package.json"), "utf8"));
    await fs.copyFile(sharedPackage(name, "LICENSE"), path.join(outDir, license));
    notices.push(`${name} ${metadata.version} is distributed under ${metadata.license}; see ${license}.`);
  }
  await fs.writeFile(path.join(outDir, "FONT-NOTICE.txt"),
    "The built interface includes these self-hosted fonts:\n" + notices.join("\n") + "\n");
}
