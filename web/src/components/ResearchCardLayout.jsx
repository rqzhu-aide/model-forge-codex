import React from "react";

// Keep controls mounted once, in the stacked reading order. The desktop account
// spans the action and reading rows. Callers pass null for slots without content.
// Question rows share the layout without adding a complementary landmark each.
export default function ResearchCardLayout({ children, actions = null, resources = null,
  actionsLabel = "Actions", label = "Supporting reading", resourceElement = "aside", className, ...rest }) {
  const ResourceElement = resourceElement;
  const layoutClass = ["research-card-layout", (actions || resources) && "has-rail", actions && "has-actions"].filter(Boolean).join(" ");
  return <div className={["research-card-columns", className].filter(Boolean).join(" ")} {...rest}><div className={layoutClass}>
    {actions && <div className="research-card-actions" role="group" aria-label={actionsLabel}>{actions}</div>}
    <div className="research-card-account">{children}</div>
    {resources && <ResourceElement className="research-card-resources" role={resourceElement === "aside" ? undefined : "group"} aria-label={label}>{resources}</ResourceElement>}
  </div></div>;
}
