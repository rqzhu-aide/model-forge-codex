import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
// Fonts ship with the client: no remote requests at runtime.
import "@fontsource-variable/ibm-plex-sans/wght.css";
import "@fontsource-variable/ibm-plex-sans/wght-italic.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "@fontsource/marcellus/400.css";
import "./styles.css";

createRoot(document.getElementById("root")).render(<App />);
