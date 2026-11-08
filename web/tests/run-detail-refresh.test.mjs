import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { sharedPackage } from "../scripts/shared-deps.mjs";

const require = createRequire(import.meta.url);
const { build } = require(sharedPackage("vite", "node_modules/esbuild/lib/main.js"));
const directory = fs.mkdtempSync(path.join(os.tmpdir(), "model-forge-run-refresh-"));
const bundle = path.join(directory, "run.cjs");
const src = fileURLToPath(new URL("../src", import.meta.url)).replaceAll("\\", "/");
await build({ stdin: { contents: `import React from 'react'; export {default as RunDetail,RunActivity} from '${src}/components/RunDetail.jsx'; export {api} from '${src}/api.js'; export const dispatcher=React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED.ReactCurrentDispatcher;`, resolveDir: src },
  outfile: bundle, bundle: true, platform: "node", format: "cjs", jsx: "automatic", loader: { ".css": "empty" },
  alias: { react: sharedPackage("react"), "react-dom": sharedPackage("react-dom"), katex: sharedPackage("katex") }, logLevel: "silent" });
const ui = require(bundle); fs.unlinkSync(bundle); fs.rmdirSync(directory);
const noop = () => {};

// Exercise shipped effects, request overlap and handlers without a live server.
function mount(Component, initialProps) {
  const slots = []; let cursor = 0; let pending = []; let dirty = true; let props = initialProps; let tree;
  const memo = (factory, dependencies) => {
    const index = cursor++; const previous = slots[index];
    if (!previous || dependencies.some((value, offset) => !Object.is(value, previous.dependencies[offset]))) slots[index] = { value: factory(), dependencies };
    return slots[index].value;
  };
  const hooks = {
    useState(initial) {
      const index = cursor++;
      if (!slots[index]) slots[index] = { value: typeof initial === "function" ? initial() : initial };
      return [slots[index].value, update => { const value = typeof update === "function" ? update(slots[index].value) : update; if (!Object.is(value, slots[index].value)) { slots[index].value = value; dirty = true; } }];
    },
    useRef(initial) { const index = cursor++; return (slots[index] ||= { value: { current: initial } }).value; },
    useMemo: memo,
    useEffect(run, dependencies) {
      const index = cursor++; const previous = slots[index];
      if (!previous || dependencies.some((value, offset) => !Object.is(value, previous.dependencies[offset]))) { slots[index] = { dependencies, cleanup: previous?.cleanup }; pending.push({ index, run }); }
    },
  };
  return { get tree() { return tree; }, update(changes) { props = { ...props, ...changes }; dirty = true; },
    async settle() {
      for (let turn = 0; turn < 20; turn++) {
        if (dirty) {
          dirty = false; cursor = 0; pending = []; const previous = ui.dispatcher.current;
          try { ui.dispatcher.current = hooks; tree = Component(props); } finally { ui.dispatcher.current = previous; }
          for (const { index, run } of pending) { slots[index].cleanup?.(); slots[index].cleanup = run(); }
        }
        await new Promise(resolve => setImmediate(resolve));
        if (!dirty) return;
      }
      throw new Error("The bounded run fixture did not settle.");
    },
    unmount() { for (const slot of slots) slot?.cleanup?.(); },
  };
}
function nodes(tree) {
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  return tree && typeof tree === "object" && tree.props ? [tree, ...nodes(tree.props.children)] : [];
}
const technicalRecord = tree => nodes(tree).find(node => node.type?.name === "TechnicalRecord");
const disclosure = (tree, label) => nodes(tree).find(node => node.type === "details" && nodes(node.props.children).some(child => child.type === "summary" && child.props.children === label));

async function withRun(state, action) {
  const originals = { window: globalThis.window, document: globalThis.document, EventSource: globalThis.EventSource, setInterval: globalThis.setInterval, clearInterval: globalThis.clearInterval, setTimeout: globalThis.setTimeout, clearTimeout: globalThis.clearTimeout };
  const originalNow = Date.now; const originalApi = { run: ui.api.run, correctionPreview: ui.api.correctionPreview };
  const listeners = new Map(); const intervals = new Set(); const retries = new Map(); const streams = []; let now = 0; let reads = 0; let previews = 0;
  let current = { run_id: "run.same", phase: "P3", branch_id: "method.a", mode: "p3.develop", state, instructions: "The recorded scientific request.", target: { generation_id: "theory.one", sha256: "a".repeat(64) } };
  const listen = (type, callback) => listeners.set(type, callback);
  const unlisten = (type, callback) => { if (listeners.get(type) === callback) listeners.delete(type); };
  globalThis.window = { addEventListener: listen, removeEventListener: unlisten };
  globalThis.document = { hidden: false, addEventListener: listen, removeEventListener: unlisten };
  globalThis.setInterval = callback => { intervals.add(callback); return callback; };
  globalThis.clearInterval = callback => intervals.delete(callback);
  globalThis.setTimeout = (callback, delay) => { retries.set(callback, delay); return callback; };
  globalThis.clearTimeout = callback => retries.delete(callback);
  Date.now = () => now;
  globalThis.EventSource = class {
    constructor(url) { this.url = url; this.closed = false; streams.push(this); }
    close() { this.closed = true; }
    message(event) { this.onmessage({ data: JSON.stringify(event) }); }
  };
  ui.api.run = async () => { reads++; return { ...current }; };
  ui.api.correctionPreview = async () => { previews++; return { eligible: current.state === "failed", attempts_remaining: 2 }; };
  const view = mount(ui.RunDetail, { projectId: "project.test", runId: "run.same", onBack: noop });
  const clock = { view, streams, listeners, intervals, retries, get reads() { return reads; }, get previews() { return previews; },
    get run() { return current; }, set run(value) { current = value; }, setReader(reader) { ui.api.run = reader; },
    async advance(milliseconds) { now += milliseconds; for (const callback of intervals) callback(); await view.settle(); },
  };
  try { await view.settle(); await action(clock); }
  finally { view.unmount(); Object.assign(globalThis, originals); Object.assign(ui.api, originalApi); Date.now = originalNow; }
}

test("terminal run checks stay bounded and reconnect a corrected or requeued run", async () => {
  for (const [terminal, resumed] of [["failed", "correcting"], ["cancelled", "queued"], ["published", "running"]]) {
    await withRun(terminal, async clock => {
      clock.streams[0].message({ type: "stream.closed", state: terminal }); await clock.view.settle();
      const initial = clock.reads;
      for (let tick = 0; tick < 4; tick++) await clock.advance(3000);
      assert.equal(clock.reads, initial, "Settled runs do not rebuild on each active-work tick.");
      clock.run = { ...clock.run, state: resumed };
      await clock.advance(3000);
      assert.equal(clock.reads, initial + 1);
      assert.equal(clock.streams.length, 2, `${terminal} -> ${resumed} restarts activity without a new run ID.`);
      await clock.advance(3000);
      assert.equal(clock.reads, initial + 2, "Resumed work returns to the active cadence.");
      assert.equal(clock.previews, clock.reads);
    });
  }
});

test("waiting input stays prompt and a fast external resume uses the stream-closed state", async () => {
  await withRun("awaiting_user", async clock => {
    await clock.advance(3000); assert.equal(clock.reads, 2);
    clock.streams[0].message({ type: "stream.closed", state: "awaiting_user" }); await clock.view.settle();
    clock.run = { ...clock.run, state: "running" }; await clock.advance(3000);
    assert.equal(clock.streams.length, 2);
  });
  await withRun("running", async clock => {
    clock.streams[0].message({ type: "stream.closed", state: "awaiting_user" }); await clock.view.settle();
    assert.equal(clock.streams.length, 2, "A fast resume cannot strand a closed stream when both run snapshots say running.");
    const current = clock.streams[1];
    clock.streams[0].onerror();
    assert.equal(current.closed, false, "Late callbacks from the previous stream cannot close the replacement.");
  });
});

test("hidden tabs skip refresh work and visible/focus returns force current run and preview checks", async () => {
  await withRun("failed", async clock => {
    globalThis.document.hidden = true; await clock.advance(30000);
    clock.listeners.get("visibilitychange")(); clock.listeners.get("focus")();
    clock.streams[0].message({ type: "stage.running" }); await clock.view.settle();
    assert.equal(clock.reads, 1);
    clock.run = { ...clock.run, state: "queued" };
    globalThis.document.hidden = false; clock.listeners.get("visibilitychange")(); await clock.view.settle();
    assert.equal(clock.reads, 2); assert.equal(clock.streams.length, 2);
    clock.listeners.get("focus")(); await clock.view.settle();
    assert.equal(clock.reads, 3); assert.equal(clock.previews, 3);
    clock.view.unmount(); assert.equal(clock.intervals.size, 0); assert.equal(clock.listeners.size, 0);
    assert.ok(clock.streams.every(stream => stream.closed));
  });
});

test("pending refreshes never overlap and abandoned scope results do not repaint the run", async () => {
  await withRun("running", async clock => {
    let resolve; let requests = 0;
    clock.setReader(() => { requests++; return new Promise(done => { resolve = done; }); });
    await clock.advance(3000); clock.listeners.get("focus")(); await clock.advance(3000);
    assert.equal(requests, 1);
    clock.view.unmount(); resolve({ ...clock.run, terminal_reason: "Late stale result" }); await clock.view.settle();
    assert.ok(!JSON.stringify(clock.view.tree).includes("Late stale result"));
  });
});

test("requested source and complete execution JSON are formatted only while their disclosure is open", async () => {
  await withRun("running", async clock => {
    let formats = 0;
    clock.run = { ...clock.run, target: { generation_id: "exact.version", toJSON() { formats++; return { generation_id: this.generation_id }; } } };
    await clock.advance(3000);
    assert.equal(formats, 0); assert.equal(technicalRecord(clock.view.tree), undefined);
    disclosure(clock.view.tree, "Requested work and source").props.onToggle({ currentTarget: { open: true } }); await clock.view.settle();
    const record = technicalRecord(clock.view.tree); const rendered = mount(record.type, record.props); await rendered.settle();
    assert.match(rendered.tree.props.children, /exact.version/); assert.equal(formats, 1);
    rendered.update(record.props); await rendered.settle(); assert.equal(formats, 1, "An unchanged open record retains its formatted JSON.");
    disclosure(clock.view.tree, "Requested work and source").props.onToggle({ currentTarget: { open: false } }); await clock.view.settle();
    assert.equal(technicalRecord(clock.view.tree), undefined);
    disclosure(clock.view.tree, "Execution detail, usage, and member threads").props.onToggle({ currentTarget: { open: true } }); await clock.view.settle();
    const execution = technicalRecord(clock.view.tree); const full = mount(execution.type, execution.props); await full.settle();
    assert.match(full.tree.props.children, /run.same|exact.version/); assert.equal(formats, 2);
  });
});

test("opening technical activity retains every original event beyond the recent summary limit", async () => {
  let formats = 0;
  const events = Array.from({ length: 65 }, (_, index) => ({ _key: `client.${index}`, type: "heartbeat", message: `completed: command ${index}`, payload: { toJSON() { formats++; return { original: index }; } } }));
  const view = mount(ui.RunActivity, { run: { state: "running" }, events, connection: "live" }); await view.settle();
  assert.equal(formats, 0); assert.equal(technicalRecord(view.tree), undefined);
  const log = nodes(view.tree).find(node => node.props["data-technical-activity"] === "true");
  log.props.onToggle({ currentTarget: { open: true } }); await view.settle();
  const record = technicalRecord(view.tree); const full = mount(record.type, record.props); await full.settle();
  const saved = JSON.parse(full.tree.props.children);
  assert.equal(saved.length, 65); assert.equal(formats, 65);
  assert.equal(saved[0].message, "completed: command 0"); assert.equal(saved.at(-1).payload.original, 64);
  assert.ok(saved.every(event => !Object.hasOwn(event, "_key")));
  assert.ok(events.every(event => event._key.startsWith("client.")), "The lazy projection never mutates recorded events.");
  log.props.onToggle({ currentTarget: { open: false } }); await view.settle();
  assert.equal(technicalRecord(view.tree), undefined);
});
