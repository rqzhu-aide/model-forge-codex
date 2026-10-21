import React from "react";

// One outline family for actions throughout the workbench. The surrounding
// control supplies its accessible name, so these icons remain decorative.
const symbols = {
  ask: <path d="M21 11.5a8.4 8.4 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.4 8.4 0 0 1-3.8-.9L3 21l1.9-5.7a8.4 8.4 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.4 8.4 0 0 1 3.8-.9h.5a8.5 8.5 0 0 1 8 8v.5Z" />,
  details: <path d="m9 5 7 7-7 7" />,
  back: <path d="m15 5-7 7 7 7" />,
  source: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 13h8M8 17h5" /></>,
  run: <path d="m8 4 12 8-12 8Z" />,
  continue: <path d="m8 4 12 8-12 8Z" />,
  check: <><circle cx="10.5" cy="10.5" r="7.5" /><path d="m16 16 5 5M7 10.5l2.5 2.5 4-4" /></>,
  repair: <path d="m14.7 6.3 3 3L22 5a6 6 0 0 1-8 8L6.1 21a2.1 2.1 0 0 1-3-3L11 10a6 6 0 0 1 8-8Z" />,
  retry: <><path d="M21 7v5h-5M3 17v-5h5" /><path d="M5.1 7a8 8 0 0 1 13.2-3L21 7M3 17l2.7 3A8 8 0 0 0 18.9 17" /></>,
  pause: <><path d="M6 4h4v16H6ZM14 4h4v16h-4Z" /></>,
  stop: <rect x="5" y="5" width="14" height="14" rx="1" />,
  edit: <><path d="m16 3 5 5M3 21l5-1L21 7a2.1 2.1 0 0 0-3-3L5 17Z" /><path d="m5 17 3 3" /></>,
  save: <><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h12l4 4v12a2 2 0 0 1-2 2Z" /><path d="M7 3v6h9V3M7 21v-8h10v8" /></>,
  close: <path d="m6 6 12 12M6 18 18 6" />,
};

export function ActionIcon({ name }) {
  if (!symbols[name]) return null;
  return <svg className="ui-action-icon" data-icon={name} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">{symbols[name]}</svg>;
}

export function ActionButton({ action, uiRole = "system", variant = "secondary", children, className = "", type = "button", ...props }) {
  const style = variant === "primary" ? "" : variant === "danger" ? "danger" : "ghost";
  const base = variant === "link" ? ["source-link"] : ["btn", style];
  return <button {...props} type={type} className={[...base, "ui-action", className].filter(Boolean).join(" ")} data-action={action} data-ui-role={uiRole}>
    <ActionIcon name={action} />{children}
  </button>;
}
