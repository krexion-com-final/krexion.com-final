import React, { useEffect, useState, useRef } from "react";
import { createPortal } from "react-dom";
import axios from "axios";
import { Bug, X, Copy, Trash2, AlertCircle, CheckCircle2 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const MAX_EVENTS = 50;

/**
 * v2.1.5 — TEMPORARY Diagnostic Console.
 *
 * Captures every axios request + response (success or failure) into
 * an in-memory ring buffer + ALSO mirrors it to the cloud via
 * /api/debug/log so admins can review remotely. Each entry stores:
 *   - method, url, request headers (auth redacted), request body
 *   - response status, response headers, response body / error
 *   - duration ms
 *   - bridge job_id if returned
 *
 * UI: floating bottom-right button → expanding panel with table of
 * events, click row to see full JSON, one-click copy of the whole
 * event to clipboard so the customer can paste it back to support.
 *
 * Activated globally by installing an axios interceptor on import.
 */

// Ring buffer (module-level so all components share it)
const EVENTS = [];
const LISTENERS = new Set();

const SENSITIVE_HEADERS = new Set([
  "authorization", "cookie", "set-cookie", "x-krexion-license"
]);

function redactHeaders(h) {
  if (!h) return {};
  const out = {};
  for (const k in h) {
    const lower = k.toLowerCase();
    if (SENSITIVE_HEADERS.has(lower)) {
      out[k] = `<redacted ${String(h[k]).slice(0, 4)}...>`;
    } else {
      out[k] = h[k];
    }
  }
  return out;
}

function bodyPreview(body) {
  if (body == null) return null;
  if (body instanceof FormData) {
    const obj = {};
    for (const [k, v] of body.entries()) {
      obj[k] = v instanceof File
        ? `<File ${v.name} ${v.size}b>`
        : (typeof v === "string" && v.length > 500 ? v.slice(0, 500) + "..." : v);
    }
    return { __type: "FormData", fields: obj };
  }
  if (typeof body === "string") {
    return body.length > 2000 ? body.slice(0, 2000) + "..." : body;
  }
  return body;
}

function pushEvent(ev) {
  // v2.1.6: skip our OWN debug-log calls so we don't create an
  // infinite recursion (every captured event would POST to
  // /api/debug/log which would itself be captured -> POST -> ...
  // and the ring buffer would fill with debug_log entries instead
  // of the real call the customer wants to inspect).
  if ((ev.url || "").includes("/api/debug/log")) return;
  EVENTS.unshift(ev);
  if (EVENTS.length > MAX_EVENTS) EVENTS.pop();
  LISTENERS.forEach((fn) => fn([...EVENTS]));
  // Mirror to cloud (fire-and-forget)
  try {
    axios.post(`${BACKEND_URL}/api/debug/log`, {
      method: ev.method,
      url: ev.url,
      status: ev.status,
      duration_ms: ev.duration_ms,
      error: ev.error || null,
      request_body: ev.request_body,
      response_body: ev.response_body,
    }, {
      headers: { Authorization: `Bearer ${localStorage.getItem("token") || ""}` },
      timeout: 5000,
    }).catch(() => {});
  } catch { /* noop */ }
}

// Install axios interceptors ONCE on module load
let installed = false;
function installInterceptors() {
  if (installed) return;
  installed = true;
  axios.interceptors.request.use((cfg) => {
    cfg.__start = Date.now();
    return cfg;
  });
  axios.interceptors.response.use(
    (resp) => {
      const cfg = resp.config || {};
      pushEvent({
        ts: new Date().toISOString(),
        method: (cfg.method || "GET").toUpperCase(),
        url: cfg.url || "",
        status: resp.status,
        duration_ms: Date.now() - (cfg.__start || Date.now()),
        request_headers: redactHeaders(cfg.headers),
        request_body: bodyPreview(cfg.data),
        response_body: bodyPreview(resp.data),
        ok: true,
      });
      return resp;
    },
    (err) => {
      const cfg = err?.config || {};
      const resp = err?.response;
      pushEvent({
        ts: new Date().toISOString(),
        method: (cfg.method || "GET").toUpperCase(),
        url: cfg.url || "",
        status: resp?.status || 0,
        duration_ms: Date.now() - (cfg.__start || Date.now()),
        request_headers: redactHeaders(cfg.headers),
        request_body: bodyPreview(cfg.data),
        response_body: bodyPreview(resp?.data),
        error: err.message,
        ok: false,
      });
      return Promise.reject(err);
    }
  );
}

export default function DebugConsole() {
  const [open, setOpen] = useState(false);
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(null);
  const containerRef = useRef(null);

  useEffect(() => {
    installInterceptors();
    const onChange = (list) => setEvents(list);
    LISTENERS.add(onChange);
    setEvents([...EVENTS]);
    return () => LISTENERS.delete(onChange);
  }, []);

  const errorCount = events.filter((e) => !e.ok).length;

  const copyEvent = (ev) => {
    navigator.clipboard.writeText(JSON.stringify(ev, null, 2));
  };

  const copyAll = () => {
    navigator.clipboard.writeText(JSON.stringify(events, null, 2));
  };

  const clearAll = () => {
    EVENTS.length = 0;
    LISTENERS.forEach((fn) => fn([]));
  };

  return (
    <>
      {/* Floating launcher button */}
      <button
        onClick={() => setOpen(true)}
        data-testid="debug-console-button"
        className={`fixed bottom-4 right-4 z-[9999] px-3 py-2 rounded-full shadow-2xl text-xs font-bold flex items-center gap-2 transition ${
          errorCount > 0
            ? "bg-rose-500 text-white animate-pulse"
            : "bg-[#0f0a18] text-[#94a3b8] border border-white/20 hover:bg-[#3B82F6] hover:text-black"
        }`}
        title="Open Debug Console"
      >
        <Bug size={14} />
        Debug {errorCount > 0 ? `(${errorCount} errors)` : ""}
      </button>

      {open && createPortal(
        <div
          className="fixed inset-0 z-[2147483647] bg-black/85 backdrop-blur-md p-4 overflow-hidden"
          style={{position:"fixed", top:0, left:0, right:0, bottom:0}}
          onClick={(e)=>{ if(e.target===e.currentTarget) setOpen(false); }}
          ref={containerRef}
        >
          <div className="max-w-6xl mx-auto h-full bg-[#0f0a18] border border-[#3B82F6]/40 rounded-2xl flex flex-col overflow-hidden">
            <div className="p-4 border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Bug size={18} className="text-[#3B82F6]" />
                <h3 className="text-white font-bold text-base">Debug Console</h3>
                <span className="text-xs text-[#94a3b8]">
                  {events.length} events · {errorCount} errors
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={copyAll}
                  data-testid="debug-copy-all"
                  className="text-xs px-3 py-1.5 rounded bg-[#3B82F6]/15 border border-[#3B82F6]/30 text-[#93C5FD] hover:bg-[#3B82F6]/25 inline-flex items-center gap-1.5"
                >
                  <Copy size={12} /> Copy ALL
                </button>
                <button
                  onClick={clearAll}
                  className="text-xs px-3 py-1.5 rounded bg-rose-500/15 border border-rose-500/30 text-rose-300 hover:bg-rose-500/25 inline-flex items-center gap-1.5"
                >
                  <Trash2 size={12} /> Clear
                </button>
                <button onClick={() => setOpen(false)} className="text-[#94a3b8] hover:text-white"><X size={18}/></button>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 flex-1 overflow-hidden">
              <div className="border-r border-white/10 overflow-y-auto">
                {events.length === 0 && (
                  <div className="p-6 text-center text-[#71717A] text-sm">
                    No API calls captured yet. Trigger an action (e.g. click "Send 10 Real Clicks") and they'll appear here in real time.
                  </div>
                )}
                {events.map((ev, i) => (
                  <button
                    key={i}
                    onClick={() => setSelected(ev)}
                    className={`w-full text-left p-3 border-b border-white/5 hover:bg-white/5 transition ${
                      selected === ev ? "bg-[#3B82F6]/10" : ""
                    }`}
                  >
                    <div className="flex items-center gap-2 text-xs">
                      {ev.ok
                        ? <CheckCircle2 size={13} className="text-emerald-400" />
                        : <AlertCircle size={13} className="text-rose-400" />
                      }
                      <span className={`font-bold ${ev.ok ? "text-emerald-300" : "text-rose-300"}`}>
                        {ev.status || "ERR"}
                      </span>
                      <span className="text-[#94a3b8] font-mono uppercase">{ev.method}</span>
                      <span className="text-white truncate flex-1" title={ev.url}>
                        {ev.url.replace(BACKEND_URL || "", "")}
                      </span>
                      <span className="text-[#71717A]">{ev.duration_ms}ms</span>
                    </div>
                    {!ev.ok && ev.response_body?.detail && (
                      <div className="mt-1 text-[10px] text-rose-300/80 truncate">
                        {typeof ev.response_body.detail === "string"
                          ? ev.response_body.detail
                          : JSON.stringify(ev.response_body.detail).slice(0, 120)}
                      </div>
                    )}
                  </button>
                ))}
              </div>

              <div className="overflow-y-auto p-4">
                {!selected && (
                  <div className="text-[#71717A] text-sm text-center mt-12">
                    ← Select an event to see full request/response details
                  </div>
                )}
                {selected && (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-xs text-[#94a3b8]">{selected.ts}</div>
                      <button
                        onClick={() => copyEvent(selected)}
                        data-testid="debug-copy-event"
                        className="text-xs px-2 py-1 rounded bg-[#3B82F6] text-black font-bold inline-flex items-center gap-1.5"
                      >
                        <Copy size={11} /> Copy this event
                      </button>
                    </div>
                    <Detail title="Request" data={{
                      method: selected.method,
                      url: selected.url,
                      headers: selected.request_headers,
                      body: selected.request_body,
                    }} />
                    <Detail title="Response" data={{
                      status: selected.status,
                      duration_ms: selected.duration_ms,
                      error: selected.error,
                      body: selected.response_body,
                    }} />
                  </div>
                )}
              </div>
            </div>

            <div className="p-3 border-t border-white/10 text-[10px] text-[#71717A]">
              📌 Debug capture is local + mirrored to /api/debug/log on the
              cloud. Click "Copy ALL" to get every request as JSON for support.
              Sensitive headers (Authorization / License) are redacted.
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

function Detail({ title, data }) {
  return (
    <div className="rounded-lg bg-black/40 border border-white/10 overflow-hidden">
      <div className="px-3 py-1.5 text-xs uppercase tracking-wider text-[#94a3b8] bg-white/5 border-b border-white/10">
        {title}
      </div>
      <pre className="p-3 text-[11px] text-emerald-200 font-mono overflow-x-auto whitespace-pre-wrap break-all max-h-72 overflow-y-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </div>
  );
}
