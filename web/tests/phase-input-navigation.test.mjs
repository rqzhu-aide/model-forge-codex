import test from "node:test";
import assert from "node:assert/strict";
import { navigatePhaseInput, phaseInputDestination } from "../src/phaseInputNavigation.js";

function fixture({ reduced = false } = {}) {
  const names = ["window", "getComputedStyle", "MutationObserver", "requestAnimationFrame", "cancelAnimationFrame", "setTimeout", "clearTimeout"];
  const previous = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const frames = new Map(); const timers = new Map(); const scrolls = []; const focused = []; let sequence = 0;
  class Element {
    constructor(tag, attributes = {}, y = 0) { this.tagName = tag.toUpperCase(); this.attributes = attributes; this.children = []; this.parentElement = null; this.isConnected = true; this.y = y; this.open = false; this.textContent = ""; this.display = "block"; }
    append(child) { this.children.push(child); child.parentElement = this; return child; }
    contains(element) { return element === this || this.children.some(child => child.contains(element)); }
    matches(selector) {
      return selector.split(",").some(part => {
        if (part === ":disabled") return Boolean(this.disabled);
        if (part.startsWith(".")) return this.attributes.class?.split(" ").includes(part.slice(1));
        if (part.startsWith("[")) { const [, name, value] = part.match(/^\[([^=\]]+)(?:=["']?([^\]"']+)["']?)?\]/) || []; return name && this.hasAttribute(name) && (value === undefined || this.getAttribute(name) === value); }
        return this.tagName === part.toUpperCase();
      });
    }
    closest(selector) { for (let element = this; element; element = element.parentElement) if (element.matches(selector)) return element; return null; }
    querySelectorAll(selector) { return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]); }
    querySelector(selector) { return selector === ":scope > summary" ? this.children.find(child => child.tagName === "SUMMARY") : this.querySelectorAll(selector)[0] || null; }
    hasAttribute(name) { return Object.hasOwn(this.attributes, name); }
    getAttribute(name) { return this.attributes[name] ?? null; }
    setAttribute(name, value) { this.attributes[name] = value; }
    removeAttribute(name) { delete this.attributes[name]; }
    getClientRects() { return this.isConnected && this.display !== "none" ? [{}] : []; }
    getBoundingClientRect() { const top = this.y - window.scrollY; return { top, bottom: top + 100, height: 100 }; }
    focus(options) { focused.push({ element: this, options }); }
  }
  globalThis.window = { scrollY: 800, innerHeight: 700, matchMedia: () => ({ matches: reduced }), scrollTo: options => { scrolls.push(options); window.scrollY = options.top; } };
  globalThis.getComputedStyle = element => ({ visibility: "visible", display: element.display, top: "0px" });
  globalThis.MutationObserver = class { observe() {} disconnect() {} };
  globalThis.requestAnimationFrame = callback => { const id = ++sequence; frames.set(id, callback); return id; };
  globalThis.cancelAnimationFrame = id => frames.delete(id);
  globalThis.setTimeout = callback => { const id = ++sequence; timers.set(id, callback); return id; };
  globalThis.clearTimeout = id => timers.delete(id);
  const flush = () => { const pending = [...frames.values()]; frames.clear(); for (const callback of pending) callback(); };
  const root = new Element("div", { "data-reader-ready": "true" });
  const toolbar = root.append(new Element("header", { class: "project-toolbar" }, 800));
  toolbar.getBoundingClientRect = () => ({ top: 0, bottom: 80, height: 80 });
  const card = root.append(new Element("details", { "data-reading-anchor": "further-work" }, 780)); card.open = true;
  card.append(new Element("summary", {}, 780));
  const origin = card.append(new Element("button", { "data-phase-input-origin": "unanswered" }, 850));
  const outer = root.append(new Element("details", { "data-reading-anchor": "phase-decisions" }, 1500));
  outer.append(new Element("summary", {}, 1500));
  const anchor = 'issue:["question.a","P4","method.a","/attention_items/0", "exact-source"]';
  const question = outer.append(new Element("details", { "data-reading-anchor": anchor }, 1600));
  const summary = question.append(new Element("summary", {}, 1600));
  const editor = question.append(new Element("textarea", {}, 1700)); editor.value = "Retain my unsaved answer.";
  const props = { root, origin, anchor, scope: "project:P4:method.a" };
  return { Element, root, card, origin, outer, question, summary, editor, props, frames, timers, scrolls, focused, flush,
    cleanup() { for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; } },
  };
}

test("exact source anchors tolerate JSON and pointers, reject ambiguity, and skip hidden siblings", () => {
  const f = fixture();
  try {
    assert.equal(phaseInputDestination(f.root, f.props.anchor), f.question);
    f.outer.append(new f.Element("details", { "data-reading-anchor": `${f.props.anchor}:different-source` }));
    assert.equal(phaseInputDestination(f.root, f.props.anchor), f.question);
    const duplicate = f.outer.append(new f.Element("details", { "data-reading-anchor": f.props.anchor }));
    assert.equal(phaseInputDestination(f.root, f.props.anchor), null);
    duplicate.attributes.hidden = "";
    assert.equal(phaseInputDestination(f.root, f.props.anchor), f.question);
    assert.equal(phaseInputDestination(f.root, "issue:missing"), null);
  } finally { f.cleanup(); }
});

test("explicit navigation opens every disclosure and focuses the question summary below the sticky header once", () => {
  const f = fixture(); let navigated = 0;
  try {
    const session = navigatePhaseInput({ ...f.props, onNavigated: () => navigated++ });
    assert.ok(f.outer.open && f.question.open); assert.equal(f.focused.length, 0);
    f.flush();
    assert.equal(session.focusTarget, f.summary);
    assert.deepEqual(f.focused, [{ element: f.summary, options: { preventScroll: true } }]);
    assert.deepEqual(f.scrolls, [{ top: 1504, behavior: "smooth" }]);
    assert.equal(f.question.getAttribute("data-phase-input-highlight"), "true");
    assert.equal(f.editor.value, "Retain my unsaved answer.");
    f.flush();
    assert.equal(navigated, 1); assert.equal(f.focused.length, 1); assert.equal(f.scrolls.length, 1);
    for (const callback of [...f.timers.values()]) callback();
    assert.equal(f.question.hasAttribute("data-phase-input-highlight"), false);
    session.dispose();
  } finally { f.cleanup(); }
});

test("Back restores the exact prior reading offset, open summary disclosure and invoking control without editing drafts", () => {
  const f = fixture();
  try {
    const session = navigatePhaseInput(f.props); f.flush(); f.card.open = false;
    assert.equal(session.back(), true); assert.equal(session.back(), false);
    f.flush();
    assert.equal(f.card.open, true);
    assert.deepEqual(f.scrolls.at(-1), { top: 800, behavior: "instant" });
    assert.deepEqual(f.focused.at(-1), { element: f.origin, options: { preventScroll: true } });
    assert.equal(f.editor.value, "Retain my unsaved answer.");
    assert.equal(f.question.hasAttribute("data-phase-input-highlight"), false);
    f.flush(); assert.equal(f.focused.length, 2);
  } finally { f.cleanup(); }
});

test("heading destinations use a programmatic focus target and reduced motion disables smooth scroll", () => {
  const f = fixture({ reduced: true });
  try {
    const context = f.root.append(new f.Element("section", { "data-reading-anchor": "researcher-dialogue" }, 1900));
    const heading = context.append(new f.Element("h3", {}, 1920));
    context.append(new f.Element("textarea", {}, 1960));
    const session = navigatePhaseInput({ ...f.props, anchor: "researcher-dialogue" }); f.flush();
    assert.equal(session.focusTarget, heading); assert.equal(heading.getAttribute("tabindex"), "-1");
    assert.deepEqual(f.scrolls, [{ top: 1824, behavior: "instant" }]);
    session.dispose();
  } finally { f.cleanup(); }
});

test("first-run P3 preparation focuses the visible settings container when its summary is hidden", () => {
  const f = fixture();
  try {
    const settingsSummary = f.card.querySelector(":scope > summary"); settingsSummary.setAttribute("hidden", "");
    const fromIssue = f.question.append(new f.Element("button", {}, 1700));
    const session = navigatePhaseInput({ ...f.props, origin: fromIssue, anchor: "further-work", scope: "project:P3:method.a" }); f.flush();
    assert.equal(session.focusTarget, f.card); assert.equal(f.card.getAttribute("tabindex"), "-1");
    assert.deepEqual(f.focused, [{ element: f.card, options: { preventScroll: true } }]);
    assert.deepEqual(f.scrolls, [{ top: 684, behavior: "smooth" }]);
    assert.equal(f.editor.value, "Retain my unsaved answer.");
    session.dispose();
  } finally { f.cleanup(); }
});

test("changed sources or scope before the frame never focus a replacement question", () => {
  for (const change of ["source", "scope"]) {
    const f = fixture(); const notices = []; let scope = f.props.scope;
    try {
      const session = navigatePhaseInput({ ...f.props, currentScope: () => scope, onUnavailable: message => notices.push(message) });
      if (change === "source") f.question.attributes["data-reading-anchor"] = "issue:replacement";
      else scope = "project:P4:method.other";
      f.flush();
      assert.equal(f.focused.length, 0); assert.equal(f.scrolls.length, 0); assert.equal(notices.length, 1);
      assert.match(notices[0], /source has changed/); assert.equal(session.back(), false);
    } finally { f.cleanup(); }
  }
});

test("missing destinations leave disclosures and focus alone; disposing cancels navigation and emphasis", () => {
  const f = fixture(); const notices = [];
  try {
    assert.equal(navigatePhaseInput({ ...f.props, anchor: "missing", onUnavailable: message => notices.push(message) }), null);
    assert.equal(f.outer.open, false); assert.equal(f.question.open, false); assert.equal(notices.length, 1);
    const session = navigatePhaseInput(f.props); session.dispose(); f.flush();
    assert.equal(f.focused.length, 0); assert.equal(f.scrolls.length, 0); assert.equal(f.timers.size, 0);
  } finally { f.cleanup(); }
});

test("Back refuses a changed phase or method and never focuses an unrelated summary count", () => {
  const f = fixture(); const notices = []; let scope = f.props.scope;
  try {
    const session = navigatePhaseInput({ ...f.props, currentScope: () => scope, onUnavailable: message => notices.push(message) }); f.flush();
    scope = "project:P3:method.a";
    assert.equal(session.back(), false); f.flush();
    assert.equal(f.focused.length, 1); assert.equal(f.scrolls.length, 1); assert.equal(notices.length, 1);
  } finally { f.cleanup(); }
});

test("saving the final item returns Back focus to its same summary row when the count disappears", () => {
  const f = fixture();
  try {
    const row = f.card.append(new f.Element("div", { class: "input-summary-row", "data-reading-anchor": "rerun-questions" }, 820));
    const label = row.append(new f.Element("button", { class: "input-summary-label", "data-phase-input-origin": "questions" }, 825));
    f.card.children = f.card.children.filter(child => child !== f.origin); row.append(f.origin);
    const otherRow = f.card.append(new f.Element("div", { class: "input-summary-row", "data-reading-anchor": "rerun-understanding" }, 900));
    otherRow.append(new f.Element("button", { class: "input-summary-label" }, 910));
    const session = navigatePhaseInput(f.props); f.flush();
    f.origin.isConnected = false; row.children = row.children.filter(child => child !== f.origin);
    session.back(); f.flush();
    assert.equal(f.focused.at(-1).element, label);
    assert.deepEqual(f.scrolls.at(-1), { top: 800, behavior: "instant" });
  } finally { f.cleanup(); }
});
