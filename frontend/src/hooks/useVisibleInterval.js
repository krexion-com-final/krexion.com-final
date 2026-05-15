// useVisibleInterval.js
// ─────────────────────────────────────────────────────────────────────
// Drop-in `setInterval` replacement that automatically pauses the
// callback while the tab is in the background and resumes (with an
// immediate refresh) when the user comes back.
//
// Why this matters for Krexion performance:
//   The dashboard, uploaded-things, jobs, and CPI pages all poll the
//   backend every few seconds for live updates. A user who keeps 5 tabs
//   open in the background is doing 5x the work for zero benefit —
//   nobody is looking at those panels. This hook makes every interval
//   "honest": only burns CPU + bandwidth when the tab is actually
//   visible to the user.
//
// API mirrors `setInterval`:
//   useVisibleInterval(() => fetchUploads(), 30_000);
//
// Behavior:
//   • While document.hidden is false → ticks every `delayMs` like normal.
//   • When tab goes hidden → timer is cleared (no fetches).
//   • When tab becomes visible again → fires the callback IMMEDIATELY
//     (so the user sees fresh data within ~1 frame), then resumes the
//     normal interval.
//   • `enabled=false` lets callers temporarily disable polling without
//     unmounting (e.g., when a modal owns the data).

import { useEffect, useRef } from "react";

export default function useVisibleInterval(callback, delayMs, enabled = true) {
  const cbRef = useRef(callback);
  // Always call the latest closure — same trick React docs recommend.
  cbRef.current = callback;

  useEffect(() => {
    if (!enabled || delayMs == null || delayMs <= 0) return undefined;

    let timerId = null;

    const start = () => {
      if (timerId != null) return;
      timerId = setInterval(() => {
        try {
          cbRef.current && cbRef.current();
        } catch (e) {
          // Swallow — callbacks should never crash the interval.
          // Caller is responsible for their own error handling.
          // eslint-disable-next-line no-console
          console.error("[useVisibleInterval] callback threw:", e);
        }
      }, delayMs);
    };

    const stop = () => {
      if (timerId != null) {
        clearInterval(timerId);
        timerId = null;
      }
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        stop();
      } else {
        // Tab just came back — fire once immediately so the UI feels
        // instant, then re-arm the interval.
        try {
          cbRef.current && cbRef.current();
        } catch (e) {
          // eslint-disable-next-line no-console
          console.error("[useVisibleInterval] resume callback threw:", e);
        }
        start();
      }
    };

    if (!document.hidden) start();
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", onVisibilityChange);
      stop();
    };
  }, [delayMs, enabled]);
}
