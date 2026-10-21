import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./reading-position-preview.jsx";
import "./ui-density-options.css";

const options = [ ["current", "Current"], ["compact", "A · Compact cards"], ["reader", "B · Reading first"], ["rail", "C · Utility rail"] ];
const initial = new URLSearchParams(location.search).get("density");
document.documentElement.dataset.density = options.some(([id]) => id === initial) ? initial : "compact";
function DensityControls() {
  const [density, setDensity] = useState(document.documentElement.dataset.density);
  return <details className="density-controls"><summary>Design options · {options.find(([id]) => id === density)[1]}</summary><p>Isolated preview with synthetic research. Scientific text and controls are unchanged.</p><div role="group" aria-label="Design option">{options.map(([id, title]) => <button key={id} aria-pressed={density === id} onClick={() => { document.documentElement.dataset.density = id; setDensity(id); }}>{title}</button>)}</div></details>;
}
createRoot(document.getElementById("density-controls")).render(<DensityControls />);
