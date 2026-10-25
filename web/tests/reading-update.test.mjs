import test from "node:test";
import assert from "node:assert/strict";
import { preserveReadingUpdate } from "../src/readingPosition.js";

function fixture({ focus = true } = {}) {
  const names = ["window", "document", "getComputedStyle", "ResizeObserver", "setTimeout", "clearTimeout"];
  const previous = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const listeners = new Map(); const timers = new Map(); const observers = []; const scrolls = []; const focusOptions = []; const details = []; let sequence = 0; let focusCalls = 0;
  const node = (value, y, height = 47) => ({ isConnected: true, parentElement: null, tagName: "SECTION", y, height,
    closest: () => null, getClientRects() { return this.hidden ? [] : [{}]; }, contains(element) { return element === this; },
    getBoundingClientRect() { return { top: this.y - window.scrollY, bottom: this.y + this.height - window.scrollY }; },
    hasAttribute: name => name === "data-reading-anchor", getAttribute: () => value,
    focus(options) { focusCalls++; focusOptions.push(options); document.activeElement = this; for (const callback of [...listeners.get("focusin") || []]) callback(); },
  });
  const row = node("rerun-questions", 8901.0625);
  const control = node(null, 8907.0625, 28); control.tagName = "BUTTON";
  const elements = new Set([row, control]);
  const root = { isConnected: true, contains: element => elements.has(element) && element.isConnected,
    querySelectorAll: selector => selector.startsWith("details") ? details.filter(element => element.isConnected) : [row] };
  globalThis.document = { body: { tagName: "BODY" } };
  document.activeElement = focus ? control : document.body;
  globalThis.window = { innerHeight: 720, scrollY: 8564,
    addEventListener: (name, callback) => { if (!listeners.has(name)) listeners.set(name, new Set()); listeners.get(name).add(callback); },
    removeEventListener: (name, callback) => listeners.get(name)?.delete(callback),
    scrollTo: options => { scrolls.push(options); window.scrollY = options.top; },
  };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block" });
  globalThis.ResizeObserver = class {
    constructor(callback) { this.callback = callback; this.connected = true; observers.push(this); }
    observe(element) { assert.equal(element, root); }
    disconnect() { this.connected = false; }
  };
  globalThis.setTimeout = callback => { const id = ++sequence; timers.set(id, callback); return id; };
  globalThis.clearTimeout = id => timers.delete(id);
  return { root, row, control, scrolls, listeners, timers, focusOptions,
    disclosure({ anchor = "further-work", text = "Edit instructions and settings", hidden = false, y = control.y } = {}) {
      const detail = node(anchor, y); detail.tagName = "DETAILS"; detail.open = true;
      const summary = node(null, y, 28); summary.tagName = "SUMMARY"; summary.textContent = text; summary.parentElement = detail; summary.hidden = hidden;
      detail.querySelector = () => summary; details.push(detail); elements.add(detail); elements.add(summary);
      return { detail, summary, remove() { detail.isConnected = summary.isConnected = false; } };
    },
    resize: () => { for (const observer of observers) if (observer.connected) observer.callback(); },
    action: name => { for (const callback of [...listeners.get(name) || []]) callback(); },
    expire: () => { for (const callback of [...timers.values()]) callback(); },
    focusCalls: () => focusCalls,
    cleanup() { for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; } },
  };
}

test("publication replacement and a delayed exhibit preserve the visible focused control without refocusing", () => {
  const view = fixture();
  try {
    const update = preserveReadingUpdate(view.root);
    // The recorded publication changed both document layout and native scroll anchoring.
    view.control.y = 8781.625; window.scrollY = 8768.5;
    update.restore();
    assert.equal(view.control.getBoundingClientRect().top, 343.0625);
    view.control.y += 216; view.resize();
    assert.equal(view.control.getBoundingClientRect().top, 343.0625);
    assert.equal(view.focusCalls(), 0);
    const count = view.scrolls.length; view.resize();
    assert.equal(view.scrolls.length, count, "An unchanged poll must not scroll again.");
    update.dispose();
  } finally { view.cleanup(); }
});

test("an unfocused reader retains its current anchor, captured after reading during the fetch", () => {
  const view = fixture({ focus: false });
  try {
    window.scrollY += 120; // The reader moved before the response became ready.
    const top = view.row.getBoundingClientRect().top;
    const update = preserveReadingUpdate(view.root);
    view.row.y -= 330;
    update.restore();
    assert.equal(view.row.getBoundingClientRect().top, top);
    assert.equal(document.activeElement.tagName, "BODY"); assert.equal(view.focusCalls(), 0);
    update.dispose();
  } finally { view.cleanup(); }
});

for (const action of ["wheel", "touchstart", "pointerdown", "keydown", "focusin", "scope-change", "timeout"]) {
  test(`${action} ends update preservation before a later layout change`, () => {
    const view = fixture();
    try {
      const update = preserveReadingUpdate(view.root); update.restore();
      if (action === "scope-change") update.dispose();
      else if (action === "timeout") view.expire();
      else view.action(action);
      window.scrollY += 200; view.control.y += 300;
      const y = window.scrollY; view.resize(); update.restore();
      assert.equal(window.scrollY, y); assert.equal(view.scrolls.length, 0);
      assert.ok([...view.listeners.values()].every(callbacks => callbacks.size === 0));
    } finally { view.cleanup(); }
  });
}

test("reader navigation between capture and commit cancels restoration", () => {
  const view = fixture();
  try {
    const update = preserveReadingUpdate(view.root);
    view.action("wheel"); window.scrollY = 9000; view.control.y += 500;
    update.restore();
    assert.equal(window.scrollY, 9000); assert.equal(view.scrolls.length, 0);
  } finally { view.cleanup(); }
});

test("removal of the focused control never redirects focus to another control", () => {
  const view = fixture();
  try {
    const update = preserveReadingUpdate(view.root); view.control.isConnected = false;
    update.restore();
    assert.equal(view.scrolls.length, 0); assert.equal(view.focusCalls(), 0);
  } finally { view.cleanup(); }
});

test("a keyed preparation replacement retains the same anchored summary focus and reading offset", () => {
  const view = fixture();
  try {
    const before = view.disclosure(); document.activeElement = before.summary;
    const offset = before.summary.getBoundingClientRect().top;
    const update = preserveReadingUpdate(view.root);
    // Supersession changes the editor's method scope to shared preparation.
    // React removes the old keyed subtree, and the browser drops focus to body.
    before.remove(); document.activeElement = document.body;
    const after = view.disclosure({ y: before.summary.y + 300 });
    assert.equal(before.summary.isConnected, false); assert.equal(document.activeElement, document.body);
    update.restore();
    assert.equal(document.activeElement, after.summary); assert.equal(view.focusCalls(), 1);
    assert.deepEqual(view.focusOptions, [{ preventScroll: true }]);
    assert.equal(after.summary.getBoundingClientRect().top, offset);
    after.summary.y += 216; view.resize();
    assert.equal(after.summary.getBoundingClientRect().top, offset, "Its own focusin does not cancel delayed layout preservation.");
    assert.equal(view.focusCalls(), 1);
    view.action("keydown"); after.summary.y += 100; const y = window.scrollY; view.resize();
    assert.equal(window.scrollY, y, "A later keyboard action still cancels preservation.");
  } finally { view.cleanup(); }
});

for (const change of ["different-label", "different-anchor", "hidden", "ambiguous", "reader-focus", "reader-action"]) {
  test(`a replaced disclosure does not recover focus after ${change}`, () => {
    const view = fixture();
    try {
      const before = view.disclosure(); document.activeElement = before.summary;
      const update = preserveReadingUpdate(view.root);
      before.remove(); document.activeElement = document.body;
      view.disclosure({ text: change === "different-label" ? "Another choice" : undefined,
        anchor: change === "different-anchor" ? "another-section" : undefined, hidden: change === "hidden" });
      if (change === "ambiguous") view.disclosure();
      if (change === "reader-focus") document.activeElement = view.control;
      if (change === "reader-action") view.action("pointerdown");
      update.restore();
      assert.equal(view.focusCalls(), 0); assert.equal(view.scrolls.length, 0);
    } finally { view.cleanup(); }
  });
}

test("removing one of two matching disclosures does not redirect focus to its unrelated survivor", () => {
  const view = fixture();
  try {
    const before = view.disclosure(); view.disclosure(); document.activeElement = before.summary;
    const update = preserveReadingUpdate(view.root);
    before.remove(); document.activeElement = document.body;
    update.restore();
    assert.equal(document.activeElement, document.body); assert.equal(view.focusCalls(), 0);
  } finally { view.cleanup(); }
});

test("an abandoned commit or disconnected reader releases its listeners", () => {
  for (const abandoned of [true, false]) {
    const view = fixture();
    try {
      const update = preserveReadingUpdate(view.root);
      if (abandoned) view.expire(); else { view.root.isConnected = false; update.restore(); }
      assert.ok([...view.listeners.values()].every(callbacks => callbacks.size === 0));
      assert.equal(view.scrolls.length, 0);
    } finally { view.cleanup(); }
  }
});
