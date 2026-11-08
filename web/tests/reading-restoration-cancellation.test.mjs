import test from "node:test";
import assert from "node:assert/strict";
import { restoreReadingPosition } from "../src/readingPosition.js";

function environment(pending = true) {
  const names = ["window", "getComputedStyle", "MutationObserver", "requestAnimationFrame", "cancelAnimationFrame"];
  const originals = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const frames = new Map(), listeners = new Map(), observers = [], scrolls = [], focus = []; let sequence = 0;
  globalThis.window = {
    scrollY: 0,
    addEventListener(name, callback) { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(callback); },
    removeEventListener(name, callback) { listeners.get(name)?.delete(callback); },
    scrollTo(value) { scrolls.push(value); this.scrollY = value.top; },
  };
  globalThis.MutationObserver = class {
    constructor(callback) { this.callback = callback; observers.push(this); }
    observe() { this.active = true; }
    disconnect() { this.active = false; }
  };
  globalThis.requestAnimationFrame = callback => { frames.set(++sequence, callback); return sequence; };
  globalThis.cancelAnimationFrame = id => frames.delete(id);
  globalThis.getComputedStyle = () => ({ display: "block", visibility: "visible" });
  const target = { isConnected: true, getClientRects: () => [{}], closest: () => null, getAttribute: () => "saved-reading", getBoundingClientRect: () => ({ top: 900 - window.scrollY }), focus: value => focus.push(value) };
  const root = { querySelector: () => pending ? {} : null, querySelectorAll: selector => selector === "details" ? [] : [target] };
  const saved = { y: 900, offset: 0, anchor: { kind: "data-reading-anchor", value: "saved-reading" } };
  return { root, saved, scrolls, focus, frames,
    listenerCount: () => [...listeners.values()].reduce((count, values) => count + values.size, 0),
    input(name) { for (const callback of [...(listeners.get(name) || [])]) callback({ type: name }); },
    ready() { pending = false; for (const observer of observers) if (observer.active) observer.callback(); },
    flush() { const callbacks = [...frames.values()]; frames.clear(); for (const callback of callbacks) callback(); },
    cleanup() { for (const [name, value] of Object.entries(originals)) if (value === undefined) delete globalThis[name]; else globalThis[name] = value; },
  };
}

test("wheel, touch, pointer and keyboard input while loading cancel delayed scroll and focus", () => {
  for (const input of ["wheel", "touchstart", "pointerdown", "keydown"]) {
    const f = environment(); let restored = 0;
    try {
      const dispose = restoreReadingPosition(f.root, f.saved, true, () => restored++);
      assert.equal(f.frames.size, 0); assert.equal(f.listenerCount(), 4);
      f.input(input); window.scrollY = 1500; f.ready(); f.flush();
      assert.equal(window.scrollY, 1500); assert.deepEqual(f.scrolls, []); assert.deepEqual(f.focus, []);
      assert.equal(restored, 0); assert.equal(f.listenerCount(), 0); dispose();
    } finally { f.cleanup(); }
  }
});

test("reader input after loading but before the scheduled frame also cancels restoration", () => {
  const f = environment();
  try {
    const dispose = restoreReadingPosition(f.root, f.saved, true);
    f.ready(); assert.equal(f.frames.size, 1); f.input("pointerdown"); f.flush();
    assert.deepEqual(f.scrolls, []); assert.deepEqual(f.focus, []); assert.equal(f.listenerCount(), 0); dispose();
  } finally { f.cleanup(); }
});

test("explicit initial navigation restores once when loading settles and releases its listeners", () => {
  for (const pending of [false, true]) {
    const f = environment(pending); let restored = 0;
    try {
      const dispose = restoreReadingPosition(f.root, f.saved, true, root => { assert.equal(root, f.root); restored++; });
      if (pending) { assert.deepEqual(f.scrolls, []); f.ready(); }
      f.flush(); f.ready(); f.flush();
      assert.deepEqual(f.scrolls, [{ top: 900, behavior: "instant" }]); assert.deepEqual(f.focus, [{ preventScroll: true }]);
      assert.equal(restored, 1); assert.equal(f.listenerCount(), 0); dispose();
    } finally { f.cleanup(); }
  }
});

test("cleanup cancels pending observations, frames and reader-action listeners", () => {
  for (const pending of [false, true]) {
    const f = environment(pending);
    try {
      const dispose = restoreReadingPosition(f.root, f.saved, true); dispose();
      f.ready(); f.flush(); assert.deepEqual(f.scrolls, []); assert.deepEqual(f.focus, []); assert.equal(f.listenerCount(), 0);
    } finally { f.cleanup(); }
  }
});
