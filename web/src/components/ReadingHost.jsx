import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { MethodReadingWindow } from "./MethodReadingWindow";

const ReadingContext = createContext({ available: false, scope: {}, open() {}, close() {} });
const ordered = value => Array.isArray(value) ? value.map(ordered)
  : value && typeof value === "object" ? Object.fromEntries(Object.keys(value).sort().map(key => [key, ordered(value[key])])) : value ?? null;
export const readingDocumentKey = (scope, name, sources) => JSON.stringify(ordered([scope, name, sources]));
export const useReadingHost = () => useContext(ReadingContext);

function returnToCard(trigger, fallback) {
  const root = trigger?.closest?.('[data-reader-ready="true"]');
  const card = trigger?.closest?.(".card");
  const title = card?.querySelector("h2")?.textContent;
  return () => {
    if (trigger?.isConnected) return trigger;
    const replacement = title && [...(root?.querySelectorAll(".card h2") || [])].find(heading => heading.textContent === title);
    if (replacement) { replacement.tabIndex = -1; return replacement; }
    return typeof fallback === "function" ? fallback() : fallback;
  };
}

// The project owns this above keyed phase views. A publication can replace a
// child without replacing the exact document the researcher is reading.
export default function ReadingHost({ scope, snapshot, onChange, returnFocus, children }) {
  const [local, setLocal] = useState(null);
  const setDocument = onChange || setLocal;
  const document = onChange ? snapshot : local;
  const scopeKey = JSON.stringify([scope?.projectId, scope?.phase, scope?.branch]);
  useEffect(() => { setDocument(null); }, [scopeKey]);
  const context = useMemo(() => ({ available: true, scope,
    open: (value, trigger) => setDocument({ ...value, projectId: scope?.projectId, phase: scope?.phase,
      readerScope: scopeKey, trigger: trigger || value.trigger,
      returnFocus: value.returnFocus || returnToCard(trigger || value.trigger, returnFocus) }),
    close: () => setDocument(null),
  }), [scopeKey, setDocument]);
  const visible = document && (!document.readerScope || document.readerScope === scopeKey)
    && (!document.projectId || document.projectId === scope?.projectId)
    && (!document.phase || document.phase === scope?.phase);
  return <ReadingContext.Provider value={context}>{children}
    {visible && <MethodReadingWindow key={document.key} snapshot={document} onClose={context.close}
      returnFocus={document.returnFocus || (() => document.trigger?.isConnected ? document.trigger
        : typeof returnFocus === "function" ? returnFocus() : returnFocus)} />}
  </ReadingContext.Provider>;
}
