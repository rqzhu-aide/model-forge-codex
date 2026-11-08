import { useLayoutEffect, useRef } from "react";

// Exact-document reading locations are session-only, with a bounded lifetime.
const positions = new Map();
export function captureReadingPosition(body) {
  return body ? { top: body.scrollTop,
    details: [...body.querySelectorAll("details")].map(element => element.open) } : null;
}
export function rememberReadingPosition(key, body) {
  const value = captureReadingPosition(body);
  if (!key || !value) return;
  positions.delete(key); positions.set(key, value);
  if (positions.size > 100) positions.delete(positions.keys().next().value);
}
export function restoreReadingPosition(key, body) {
  const saved = positions.get(key);
  if (!body || !saved) return false;
  [...body.querySelectorAll("details")].forEach((element, index) => { element.open = Boolean(saved.details[index]); });
  body.scrollTop = saved.top;
  return true;
}
export function locateSourceHeading(body, locator) {
  if (!body || typeof locator !== "string" || !locator.trim()) return false;
  const label = locator.trim();
  const matches = label.startsWith("#")
    ? [...body.querySelectorAll("[data-source-anchor]")].filter(anchor => anchor.getAttribute("data-source-anchor") === label.slice(1))
    : [...body.querySelectorAll("h1,h2,h3,h4,h5,h6")].filter(heading => {
    const text = heading.textContent?.trim() || "";
    return text === label || (text.startsWith(label) && /^[.\s:]/.test(text.slice(label.length, label.length + 1)));
  });
  if (matches.length !== 1) return false;
  // Move only this source reader, leaving the underlying research page in place.
  const heading = matches[0];
  body.scrollTop += heading.getBoundingClientRect().top - body.getBoundingClientRect().top;
  return true;
}

export function useReadingPosition({ key, ready = true, bodyRef, fragment, sourceLocator }) {
  const savedBeforeChange = useRef(null);
  const save = () => {
    if (ready) rememberReadingPosition(key, bodyRef.current);
  };
  // A loader may replace a completed body before its parent's layout cleanup.
  // Save while that body still exists, then leave this snapshot untouched.
  const saveBeforeChange = () => {
    if (!ready) return;
    const body = bodyRef.current;
    rememberReadingPosition(key, body);
    savedBeforeChange.current = { key, body };
  };
  useLayoutEffect(() => {
    if (!ready || !key) return;
    const body = bodyRef.current;
    savedBeforeChange.current = null;
    if (!fragment && !locateSourceHeading(body, sourceLocator)) restoreReadingPosition(key, body);
    return () => {
      if (savedBeforeChange.current?.key === key && savedBeforeChange.current.body === body) return;
      rememberReadingPosition(key, body);
    };
  }, [key, ready, bodyRef, fragment, sourceLocator]);
  return { save, onScroll: save, saveBeforeChange };
}
