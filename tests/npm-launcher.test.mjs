import assert from "node:assert/strict";
import test from "node:test";
import path from "node:path";
import os from "node:os";
import { findPython, parseOptions, userPath } from "../bin/model-forge-codex.mjs";

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
