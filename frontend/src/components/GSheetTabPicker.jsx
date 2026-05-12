import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { Loader2, CheckCircle2, AlertCircle, Sparkles } from "lucide-react";
import { Input } from "./ui/input";
import { Label } from "./ui/label";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * Smart Google Sheet tab picker.
 *
 * UX flow:
 *   1. User pastes ANY tab URL of a spreadsheet (or just the bare /edit URL).
 *   2. After 600ms idle, we call GET /api/gsheet/tabs?url=... — backend
 *      reads the spreadsheet metadata and returns every tab (title, gid,
 *      row count, ready URL).
 *   3. If multiple tabs exist, we render a dropdown so the user picks
 *      which tab to attach. Single-tab sheets auto-select.
 *   4. The final URL (with the right `#gid=X`) is propagated to the
 *      parent via onChange so the existing upload logic keeps working
 *      with no other changes.
 *
 * Props:
 *   - token            : auth token for the API call
 *   - value            : current full sheet URL (with gid) — controlled
 *   - onChange(url)    : called with the final URL whenever it changes
 *   - testIdPrefix     : prefix for data-testid attributes (e.g. "ut-df")
 *   - placeholder      : input placeholder (optional)
 *   - inputClass       : input className (optional)
 *   - hint             : extra hint node rendered under the picker
 */
export default function GSheetTabPicker({
  token,
  value,
  onChange,
  testIdPrefix,
  placeholder = "https://docs.google.com/spreadsheets/d/.../edit",
  inputClass = "",
  hint = null,
}) {
  // The URL the user types — kept separate from the resolved final URL so
  // the dropdown doesn't fight the input field while the user is editing.
  const [rawUrl, setRawUrl] = useState(value || "");
  const [tabs, setTabs] = useState([]);
  const [writeEnabled, setWriteEnabled] = useState(false);
  const [selectedGid, setSelectedGid] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const debounceRef = useRef(null);

  // Keep rawUrl in sync if parent resets `value` externally (e.g. after a
  // successful save the form is cleared).
  useEffect(() => {
    if ((value || "") !== rawUrl && (!value || value === "")) {
      setRawUrl("");
      setTabs([]);
      setSelectedGid(null);
      setError("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  // Debounced fetch whenever the URL changes
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const url = (rawUrl || "").trim();
    if (!url || !/docs\.google\.com\/spreadsheets/i.test(url)) {
      setTabs([]);
      setSelectedGid(null);
      setError("");
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      setError("");
      try {
        const r = await axios.get(`${API}/gsheet/tabs`, {
          params: { url },
          headers: { Authorization: `Bearer ${token}` },
        });
        const fetched = r.data?.tabs || [];
        setTabs(fetched);
        setWriteEnabled(!!r.data?.write_enabled);
        if (fetched.length === 0) {
          setError("Spreadsheet found but it has no readable tabs.");
          onChange?.(url);
          return;
        }
        // Pick gid from URL if present, else default to first tab
        const m = url.match(/[?&#]gid=(\d+)/);
        const urlGid = m ? Number(m[1]) : null;
        const match = urlGid != null
          ? fetched.find((t) => t.gid === urlGid)
          : null;
        const chosen = match || fetched[0];
        setSelectedGid(chosen.gid);
        onChange?.(chosen.url);
      } catch (e) {
        const msg = e?.response?.data?.detail || e?.message || "Could not read sheet";
        setError(msg);
        setTabs([]);
        setSelectedGid(null);
        // Still propagate raw URL so the legacy fallback works
        onChange?.(url);
      } finally {
        setLoading(false);
      }
    }, 600);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawUrl, token]);

  const handleSelect = (gidStr) => {
    const gid = Number(gidStr);
    setSelectedGid(gid);
    const tab = tabs.find((t) => t.gid === gid);
    if (tab) onChange?.(tab.url);
  };

  return (
    <div className="space-y-2">
      <Label className="text-zinc-300 flex items-center gap-2">
        Google Sheet URL
        {writeEnabled && (
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
            title="Service account is configured — used rows will be deleted from the live sheet"
            data-testid={`${testIdPrefix}-live-badge`}
          >
            <Sparkles className="w-3 h-3" /> LIVE EDIT
          </span>
        )}
      </Label>
      <div className="relative">
        <Input
          value={rawUrl}
          onChange={(e) => setRawUrl(e.target.value)}
          placeholder={placeholder}
          className={inputClass}
          data-testid={`${testIdPrefix}-gsheet-url`}
        />
        {loading && (
          <Loader2
            className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-zinc-400"
            data-testid={`${testIdPrefix}-loading`}
          />
        )}
      </div>

      {/* Tab dropdown — only shown when we successfully fetched tabs */}
      {tabs.length > 0 && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/40 p-3 space-y-2">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>
              Found <span className="text-zinc-100 font-semibold">{tabs.length}</span>{" "}
              tab{tabs.length === 1 ? "" : "s"} in this spreadsheet — pick one to attach:
            </span>
          </div>
          <select
            value={selectedGid ?? ""}
            onChange={(e) => handleSelect(e.target.value)}
            className="w-full rounded-md bg-zinc-900 text-zinc-100 border border-zinc-700 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500/50"
            data-testid={`${testIdPrefix}-tab-select`}
          >
            {tabs.map((t) => (
              <option key={t.gid} value={t.gid}>
                {t.title}  ·  {t.row_count.toLocaleString()} rows  ·  {t.column_count} cols
              </option>
            ))}
          </select>
          <div className="text-[11px] text-zinc-500 leading-relaxed">
            One spreadsheet, unlimited uploads — keep separate tabs for{" "}
            <span className="text-zinc-300 font-mono">proxies</span>,{" "}
            <span className="text-zinc-300 font-mono">user_agents</span>,{" "}
            <span className="text-zinc-300 font-mono">leads-CA</span>,{" "}
            <span className="text-zinc-300 font-mono">leads-TX</span>,
            etc., and attach each to its own upload.
          </div>
        </div>
      )}

      {error && (
        <div
          className="flex items-start gap-2 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded p-2"
          data-testid={`${testIdPrefix}-error`}
        >
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {hint}
    </div>
  );
}
