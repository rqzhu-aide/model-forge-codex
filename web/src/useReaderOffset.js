import { useLayoutEffect } from "react";

// Measure the sticky header, including wrapped phase labels and open activity.
// Updating the offset must never move a reader who is already on the page.
export function observeReaderOffset(root) {
  const toolbar = root?.querySelector(".project-toolbar");
  if (!toolbar) return;
  const update = () => {
    const top = Number.parseFloat(getComputedStyle(toolbar).top) || 0;
    const offset = `${Math.ceil(toolbar.getBoundingClientRect().height + Math.max(0, top) + 12)}px`;
    if (root.style.getPropertyValue("--reader-scroll-offset") !== offset) root.style.setProperty("--reader-scroll-offset", offset);
  };
  update();
  const observer = typeof ResizeObserver === "function" ? new ResizeObserver(update) : null;
  observer?.observe(toolbar);
  window.addEventListener("resize", update);
  return () => { observer?.disconnect(); window.removeEventListener("resize", update); };
}

export function useReaderOffset(root) {
  // The reader replaces its loading screen, so measure the committed element
  // rather than assuming the ref existed on the component's first render.
  useLayoutEffect(() => observeReaderOffset(root.current));
}
