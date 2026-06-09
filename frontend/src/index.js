import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import App from "./App";

// Suppress a benign ResizeObserver loop warning that surfaces from
// libraries like react-flow under React strict-mode + CRA's overlay.
// Reference: https://github.com/facebook/create-react-app/issues/11862
const RESIZE_OBS_RE = /ResizeObserver loop (limit exceeded|completed with undelivered notifications)/;
window.addEventListener("error", (e) => {
  if (e && e.message && RESIZE_OBS_RE.test(e.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});
window.addEventListener("unhandledrejection", (e) => {
  if (e && e.reason && typeof e.reason.message === "string" && RESIZE_OBS_RE.test(e.reason.message)) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
