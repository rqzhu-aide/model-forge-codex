export function isVisibleElement(element) {
  if (!element?.isConnected || !element.getClientRects().length || element.closest("[hidden],[inert]")) return false;
  // Chromium can retain layout rectangles inside a closed disclosure.
  for (let parent = element.parentElement; parent; parent = parent.parentElement) {
    if (parent.tagName === "DETAILS" && !parent.open && !parent.querySelector(":scope > summary")?.contains(element)) return false;
  }
  const style = getComputedStyle(element);
  return style.visibility !== "hidden" && style.display !== "none";
}
export function availableFocusTarget(element) {
  return isVisibleElement(element) && !element.matches(":disabled");
}
export function crossDocumentReturnTarget(box, element, ownerDocument) {
  // A nested source may have been opened by a link inside a same-origin frame.
  // Focusing only the frame loses that exact link and its keyboard position.
  try {
    if (!box || !element?.ownerDocument || element.ownerDocument === ownerDocument || !availableFocusTarget(element)) return null;
    let frame = element.ownerDocument.defaultView?.frameElement;
    while (frame) {
      if (!availableFocusTarget(frame)) return null;
      if (box.contains(frame)) return element;
      frame = frame.ownerDocument?.defaultView?.frameElement;
    }
  } catch { /* Inaccessible or detached frames retain the ordinary fallback. */ }
  return null;
}
export function dialogFocusTargets(box) {
  return [...box.querySelectorAll("button,input,textarea,select,a[href],summary,iframe,[tabindex]")].filter((element) => {
    if (!availableFocusTarget(element) || element.tabIndex < 0) return false;
    if (element.tagName === "SUMMARY" && element.parentElement?.querySelector(":scope > summary") !== element) return false;
    return !element.closest('input[type="hidden"]');
  }).sort((a, b) => (a.tabIndex || Infinity) - (b.tabIndex || Infinity));
}
