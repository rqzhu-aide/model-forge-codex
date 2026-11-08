// Small browser surface for exercising the real reading and navigation helpers.
export function navigationDom() {
  const names = ["window", "document", "getComputedStyle", "MutationObserver", "requestAnimationFrame", "cancelAnimationFrame", "setTimeout", "clearTimeout"];
  const previous = Object.fromEntries(names.map(name => [name, globalThis[name]]));
  const frames = new Map(), observers = new Set(), focused = [], scrolls = []; let serial = 0;
  class Element {
    constructor(tag, attributes = {}, y = 0) { this.tagName = tag.toUpperCase(); this.attributes = attributes; this.children = []; this.parentElement = null; this.isConnected = true; this.y = y; this.open = false; this.textContent = ""; this.dataset = {}; }
    append(child) { this.children.push(child); child.parentElement = this; return child; }
    contains(element) { return this === element || this.children.some(child => child.contains(element)); }
    matches(selector) {
      return selector.split(",").some(part => {
        if (part === ":disabled") return Boolean(this.disabled);
        if (part.startsWith(".")) return this.attributes.class?.split(" ").includes(part.slice(1));
        if (part.startsWith("[")) { const [, name, value] = part.match(/^\[([^=\]]+)(?:=["']?([^\]"']+)["']?)?\]/) || []; return name && this.hasAttribute(name) && (value === undefined || this.getAttribute(name) === value) && (!part.includes(":not") || this.getAttribute("data-card-role") !== "history"); }
        return this.tagName === part.toUpperCase();
      });
    }
    closest(selector) { for (let element = this; element; element = element.parentElement) if (element.matches(selector)) return element; return null; }
    querySelectorAll(selector) { return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]); }
    querySelector(selector) { return selector === ":scope > summary" ? this.children.find(child => child.tagName === "SUMMARY") : this.querySelectorAll(selector)[0] || null; }
    getAttribute(name) { return this.attributes[name] ?? null; }
    hasAttribute(name) { return Object.hasOwn(this.attributes, name); }
    setAttribute(name, value) { this.attributes[name] = value; }
    removeAttribute(name) { delete this.attributes[name]; }
    getClientRects() { return this.isConnected ? [{}] : []; }
    getBoundingClientRect() { return { top: this.y - window.scrollY, bottom: this.y - window.scrollY + 100, height: 100 }; }
    focus(options) { focused.push({ element: this, options }); document.activeElement = this; }
    addEventListener() {}
  }
  globalThis.document = { body: {}, hidden: false, addEventListener() {}, removeEventListener() {} };
  document.activeElement = document.body;
  globalThis.window = { scrollY: 800, innerHeight: 700, addEventListener() {}, removeEventListener() {}, matchMedia: () => ({ matches: true }), scrollTo(options) { scrolls.push(options); this.scrollY = options.top; } };
  globalThis.getComputedStyle = () => ({ visibility: "visible", display: "block", top: "0px" });
  globalThis.MutationObserver = class { constructor(callback) { this.callback = callback; } observe() { observers.add(this); } disconnect() { observers.delete(this); } };
  globalThis.requestAnimationFrame = callback => { const id = ++serial; frames.set(id, callback); return id; };
  globalThis.cancelAnimationFrame = id => frames.delete(id);
  globalThis.setTimeout = () => ++serial; globalThis.clearTimeout = () => {};
  const root = new Element("div", { "data-reader-ready": "true" });
  const saved = () => {
    root.children = [];
    const footer = root.append(new Element("section", { "data-reading-anchor": "saved-input" }, 780));
    const badge = footer.append(new Element("details", { "data-reading-anchor": "saved-input-phase:P1" }, 820)); badge.open = true;
    const badgeSummary = badge.append(new Element("summary", {}, 820));
    const item = badge.append(new Element("details", { "data-reading-anchor": "saved-input-answer:exact" }, 850)); item.open = true;
    item.append(new Element("summary", {}, 850));
    const origin = item.append(new Element("button", { "data-phase-input-origin": "saved-input-review:exact" }, 890));
    return { footer, badge, badgeSummary, item, origin };
  };
  return { Element, root, saved, focused, scrolls,
    flush() { for (let cycle = 0; frames.size && cycle < 10; cycle++) { const pending = [...frames.values()]; frames.clear(); for (const callback of pending) callback(); } },
    changed() { for (const observer of [...observers]) observer.callback(); },
    cleanup() { for (const name of names) { if (previous[name] === undefined) delete globalThis[name]; else globalThis[name] = previous[name]; } },
  };
}
