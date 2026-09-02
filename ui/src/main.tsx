import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "./styles/nocturne.css";
import "./styles/phosphor/style.css";
import "./styles/daw.css";
import "./styles/app.css";

import { App } from "./App";

const container = document.getElementById("root");
if (!container) {
  throw new Error("Root container #root not found");
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
