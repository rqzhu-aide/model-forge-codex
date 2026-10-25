import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import os from "node:os";
import { findPython, main, normalizeUserPaths, parseOptions, userPath } from "../bin/model-forge-codex.mjs";

test("research paths resolve against the user's terminal rather than npm's cache", () => {
  const terminal = path.resolve("researcher's workspace");
  assert.equal(userPath("./study", terminal), path.join(terminal, "study"));
  assert.equal(userPath("~/study", terminal), path.join(os.homedir(), "study"));
  assert.equal(userPath("~", terminal), os.homedir());
});

test("the public command accepts paths with spaces without shell interpretation", () => {
  const { command, values } = parseOptions(["web", "--python", "C:/Python shared/python.exe", "--data-root", "C:/researcher's work", "--port", "18766", "--no-open"]);
  assert.equal(command, "web");
  assert.equal(values["data-root"], "C:/researcher's work");
  let invocation;
  const executable = findPython(values.python, { env: {}, run: (...args) => {
    invocation = args;
    return { status: 0, stdout: JSON.stringify({ supported: true, shared: true, executable: values.python }) };
  } });
  assert.equal(executable, values.python);
  assert.equal(invocation[0], values.python);
  assert.equal(invocation[2].shell, false);
});

test("an explicitly selected invalid Python does not silently choose another", () => {
  const calls = [];
  assert.throws(() => findPython("chosen-python", { env: {}, run: (exe) => {
    calls.push(exe);
    return { status: 0, stdout: JSON.stringify({ supported: true, shared: false, executable: exe }) };
  } }), /virtual environment/);
  assert.deepEqual(calls, ["chosen-python"]);
});

test("automatic discovery skips old Python and project environments", () => {
  const versions = { old: { shared: true, supported: false }, venv: { shared: false, supported: true }, shared: { shared: true, supported: true } };
  assert.equal(findPython(undefined, { env: {}, candidates: [["old", []], ["venv", []], ["shared", []]], run: (exe) => ({
    status: 0, stdout: JSON.stringify({ ...versions[exe], executable: exe }),
  }) }), "shared");
});

test("invalid arguments stop before launching Python or changing a running app", () => {
  for (const args of [["web", "--port", "0"], ["web", "--port", "8766abc"], ["web", "--port", "65536"], ["delete"], ["web", "extra"], ["stop", "--no-open"], ["web", "--unknown"]]) {
    assert.throws(() => parseOptions(args));
  }
});

test("R overrides retain terminal-relative path semantics before the retained-release cwd change", () => {
  const terminal = path.resolve("researcher's workspace");
  const absolute = path.resolve("shared R", "Rscript");
  for (const [input, expected] of [
    ["./shared R/Rscript", path.join(terminal, "shared R", "Rscript")],
    [absolute, absolute],
    ["~/shared R/Rscript", path.join(os.homedir(), "shared R", "Rscript")],
    ["~", os.homedir()],
    ["Rscript", path.join(terminal, "Rscript")],
    ["./missing R/Rscript", path.join(terminal, "missing R", "Rscript")],
  ]) {
    const original = { MF_P4_RSCRIPT: input, MF_P4_PYTHON: "./shared Python/python", OTHER: "relative" };
    const normalized = normalizeUserPaths(original, terminal);
    assert.equal(normalized.MF_P4_RSCRIPT, expected);
    assert.equal(normalized.MF_P4_PYTHON, path.join(terminal, "shared Python", "python"));
    assert.equal(normalized.OTHER, "relative");
    assert.equal(original.MF_P4_RSCRIPT, input);
  }
  assert.equal(Object.hasOwn(normalizeUserPaths({}, terminal), "MF_P4_RSCRIPT"), false);
});

test("MF_PYTHON uses its probed executable and explicit --python takes precedence", () => {
  const selected = path.resolve("shared Python", "python");
  const explicit = path.resolve("another shared Python", "python");
  const calls = [];
  const run = (exe) => {
    calls.push(exe);
    return { status: 0, stdout: JSON.stringify({ supported: true, shared: true, executable: exe }) };
  };
  assert.equal(findPython(undefined, { env: { MF_PYTHON: selected }, run }), selected);
  assert.equal(findPython(explicit, { env: { MF_PYTHON: selected }, run }), explicit);
  assert.deepEqual(calls, [selected, explicit]);
  calls.length = 0;
  assert.throws(() => findPython(undefined, { env: { MF_PYTHON: selected }, run: (exe) => {
    calls.push(exe);
    return { status: 1, stdout: "" };
  } }), /selected Python is unavailable/);
  assert.deepEqual(calls, [selected]);
});

test("help keeps package installation and all commands on the same selected Python", async () => {
  const messages = [];
  const log = console.log;
  console.log = (message) => messages.push(message);
  try { assert.equal(await main(["--help"]), 0); } finally { console.log = log; }
  const help = messages.join("\n");
  assert.match(help, /https:\/\/github\.com\/rqzhu-aide\/model-forge-codex\/blob\/main\/docs\/installation\.md/);
  assert.match(help, /Keep MF_PYTHON set in this shell for web, status and stop/);
  if (process.platform === "win32") {
    assert.match(help, /\$mfPython = py -3 -c "import sys; print\(sys\.executable\)"/);
    assert.match(help, /& \$mfPython -m pip install --user/);
    assert.match(help, /\$env:MF_PYTHON = \$mfPython/);
  } else {
    assert.match(help, /"\$mf_python" -m pip install --user/);
    assert.match(help, /export MF_PYTHON="\$mf_python"/);
  }
});
