#!/usr/bin/env node
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const help = `Model Forge: your local research workbench

Usage: npx @rqzhu-aide/model-forge-codex@latest web [options]

Commands:
  web       Start the workbench and open your browser. Keep this terminal open.
  status    Show whether your workbench is running.
  stop      Stop it when no research run is active.

Options:
  --python PATH     Shared Python 3.11+ executable (or set MF_PYTHON).
  --data-root PATH  Research directory (default: ~/.model-forge-codex).
  --port NUMBER     Local port (default: 8766).
  --no-open         Start without opening a browser.
  --help            Show this help.
  --version         Show the package version.

First-time Python setup, using your shared Python installation:
  python -m pip install --user "fastapi>=0.115" "uvicorn>=0.30" "jsonschema>=4.20" "httpx>=0.27" "openai-codex>=0.147,<0.148"

No project environment is created. Configure model access in the workbench.
`;

export function parseOptions(args) {
  const { values, positionals } = parseArgs({ args, allowPositionals: true, options: {
    python: { type: "string" }, "data-root": { type: "string" }, port: { type: "string" },
    "no-open": { type: "boolean" }, help: { type: "boolean", short: "h" },
    version: { type: "boolean", short: "v" },
  } });
  if (positionals.length > 1 || (positionals[0] && !["web", "status", "stop"].includes(positionals[0]))) {
    throw new Error("Choose web, status, or stop. Use --help for instructions.");
  }
  if (values.port && (!/^\d+$/.test(values.port) || Number(values.port) < 1024 || Number(values.port) > 65535)) {
    throw new Error("--port must be an integer between 1024 and 65535.");
  }
  if (values["no-open"] && positionals[0] && positionals[0] !== "web") {
    throw new Error("--no-open is only available with web.");
  }
  return { command: positionals[0] || "web", values };
}

function windowsPythonCandidates() {
  if (process.platform !== "win32") return [];
  const bases = [path.join(os.homedir(), "AppData", "Local", "Python"),
    path.join(os.homedir(), "AppData", "Local", "Programs", "Python")];
  return bases.flatMap((base) => {
    try {
      return fs.readdirSync(base, { withFileTypes: true }).filter((entry) => entry.isDirectory())
        .sort((a, b) => b.name.localeCompare(a.name, undefined, { numeric: true }))
        .map((entry) => [path.join(base, entry.name, "python.exe"), []]);
    } catch { return []; }
  });
}

export function findPython(explicit, { env = process.env, run = spawnSync, candidates } = {}) {
  const selected = explicit || env.MF_PYTHON;
  const choices = selected ? [[selected, []]] : candidates || [
    ...(process.platform === "win32" ? [["py", ["-3"]]] : []),
    ["python3", []], ["python", []], ...windowsPythonCandidates(),
  ];
  const probe = "import json,sys; print(json.dumps({'executable':sys.executable,'supported':sys.version_info >= (3,11),'shared':sys.prefix == sys.base_prefix}))";
  for (const [command, prefix] of choices) {
    const result = run(command, [...prefix, "-B", "-c", probe], {
      encoding: "utf8", timeout: 10000, windowsHide: true, shell: false, env,
    });
    if (result.error || result.status !== 0) continue;
    try {
      const info = JSON.parse(result.stdout.trim());
      if (info.supported && info.shared && info.executable) return info.executable;
    } catch { /* An unrelated executable or launcher did not return a Python probe. */ }
  }
  throw new Error(`${selected ? "The selected Python is unavailable, older than 3.11, or a virtual environment." : "A shared Python 3.11+ installation was not found."}\nInstall Python for your user or machine, then use --python PATH or set MF_PYTHON. Use --help for the required packages.`);
}

export function userPath(value, cwd = process.cwd()) {
  if (value === "~") return os.homedir();
  if (/^~[\\/]/.test(value)) return path.resolve(os.homedir(), value.slice(2));
  return path.resolve(cwd, value);
}

export async function main(args = process.argv.slice(2)) {
  const { command, values } = parseOptions(args);
  if (values.help) { console.log(help); return 0; }
  if (values.version) { console.log(JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8")).version); return 0; }
  if (Number(process.versions.node.split(".")[0]) < 22) throw new Error("Use a shared Node.js 22 or newer installation.");
  const python = findPython(values.python);
  let appRoot = root;
  if (command === "web") {
    const snapshot = spawnSync(python, ["-B", path.join(root, "scripts", "npm_launcher.py"), "snapshot", "--node", process.execPath], {
      encoding: "utf8", timeout: 60000, windowsHide: true, shell: false,
      env: { ...process.env, PYTHONPATH: path.join(root, "src"), PYTHONDONTWRITEBYTECODE: "1" },
    });
    if (snapshot.error || snapshot.status !== 0) {
      throw new Error(snapshot.stderr?.trim() || snapshot.error?.message || "Could not prepare the application release.");
    }
    appRoot = JSON.parse(snapshot.stdout).app_root;
  }
  const forwarded = ["-B", path.join(appRoot, "scripts", "npm_launcher.py"), command, "--node", process.execPath];
  if (values["data-root"]) forwarded.push("--data-root", userPath(values["data-root"]));
  if (values.port) forwarded.push("--port", values.port);
  if (values["no-open"]) forwarded.push("--no-open");
  // User paths belong to the invoking terminal, never the transient npm cache.
  const environment = { ...process.env };
  for (const name of ["MF_CODEX_HOME", "CODEX_HOME", "MF_P4_PYTHON", "MF_CODEX_PROVIDER_CONFIG", "MF_SHARED_NODE_MODULES"]) {
    if (environment[name]) environment[name] = userPath(environment[name]);
  }
  const child = spawn(python, forwarded, {
    cwd: appRoot, stdio: "inherit", windowsHide: true, shell: false,
    detached: process.platform !== "win32",
    env: { ...environment, PYTHONPATH: path.join(appRoot, "src"), PYTHONDONTWRITEBYTECODE: "1",
      PYTHONUNBUFFERED: "1", PATH: `${path.dirname(process.execPath)}${path.delimiter}${process.env.PATH || ""}` },
  });
  // Windows delivers console Ctrl+C to Python. On POSIX the separate child
  // session gets exactly one forwarded signal, avoiding Uvicorn's forced exit.
  const interrupt = () => { if (process.platform !== "win32") child.kill("SIGINT"); };
  const terminate = () => { if (process.platform !== "win32") child.kill("SIGTERM"); };
  process.on("SIGINT", interrupt);
  process.on("SIGTERM", terminate);
  return await new Promise((resolve, reject) => {
    const cleanup = () => { process.off("SIGINT", interrupt); process.off("SIGTERM", terminate); };
    child.once("error", (error) => { cleanup(); reject(new Error(`Could not start shared Python: ${error.message}`)); });
    child.once("exit", (code, signal) => { cleanup(); resolve(code ?? (signal === "SIGINT" ? 130 : 1)); });
  });
}

if (process.argv[1] && fs.realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().then((code) => { process.exitCode = code; }).catch((error) => {
    console.error(`Model Forge: ${error.message}`);
    process.exitCode = 1;
  });
}
