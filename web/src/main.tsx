import React from "react";
import { createRoot } from "react-dom/client";
import { useGLTF } from "@react-three/drei";
import { App } from "./components/App";
import { loadConfig } from "./config";
import "./styles.css";

// Decode Draco-compressed GLBs from the import pipeline / external assets.
useGLTF.setDecoderPath("https://www.gstatic.com/draco/versioned/decoders/1.5.7/");

const root = document.getElementById("root");
if (!root) {
  throw new Error("Missing #root element");
}

void loadConfig().then(() => {
  createRoot(root).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  );
});
