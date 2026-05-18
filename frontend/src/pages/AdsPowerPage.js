import React, { useEffect, useState, useMemo } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Loader2,
  Trash2,
  Plus,
  Key,
  Globe,
  Cpu,
  PlayCircle,
  CheckCircle2,
  AlertCircle,
  Copy,
  Check,
  Download,
  Eraser,
  Zap,
  Wifi,
  WifiOff,
  ShieldCheck,
} from "lucide-react";

const API = (process.env.REACT_APP_BACKEND_URL || "") + "/api";

const APPS = [
  { key: "instagram", label: "Instagram", color: "from-pink-500 to-purple-500" },
  { key: "facebook", label: "Facebook", color: "from-blue-600 to-blue-500" },
  { key: "tiktok", label: "TikTok", color: "from-pink-500 to-cyan-500" },
  { key: "youtube", label: "YouTube", color: "from-red-600 to-red-500" },
  { key: "whatsapp", label: "WhatsApp", color: "from-green-600 to-green-500" },
  { key: "gsearch", label: "Google Search", color: "from-blue-500 to-yellow-500" },
  { key: "gchrome", label: "Chrome (mobile)", color: "from-blue-500 to-green-500" },
  { key: "pinterest", label: "Pinterest", color: "from-red-500 to-rose-500" },
  { key: "snapchat", label: "Snapchat", color: "from-yellow-400 to-yellow-300" },
  { key: "chrome", label: "Browser", color: "from-slate-500 to-slate-400" },
];

const PLATFORMS = [
  { key: "any", label: "Any" },
  { key: "android", label: "Android" },
  { key: "ios", label: "iOS" },
  { key: "desktop", label: "Desktop" },
];

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function AdsPowerPage() {
  const [configs, setConfigs] = useState([]);
  const [states, setStates] = useState([]);
  const [hasProxyCreds, setHasProxyCreds] = useState(false);
  const [proxyCredsMasked, setProxyCredsMasked] = useState("");

  const [showAddCfg, setShowAddCfg] = useState(false);
  const [newCfg, setNewCfg] = useState({ name: "", api_key: "" });
  const [showProxy, setShowProxy] = useState(false);
  const [proxyForm, setProxyForm] = useState({ base_user: "", base_pass: "" });

  const [selectedCfg, setSelectedCfg] = useState(null);
  const [count, setCount] = useState(10);
  const [state, setState] = useState("California");
  const [namePrefix, setNamePrefix] = useState("krexion");
  const [app, setApp] = useState("instagram");
  const [platform, setPlatform] = useState("any");
  const [wipeExisting, setWipeExisting] = useState(true);
  const [pushToAdspower, setPushToAdspower] = useState(false);
  const [verifyUniqueIps, setVerifyUniqueIps] = useState(false);
  const [testingCfg, setTestingCfg] = useState(null);
  const [cfgTestResult, setCfgTestResult] = useState({}); // {cid: {ok,message}}

  const [job, setJob] = useState(null);
  const [polling, setPolling] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [exporting, setExporting] = useState(false);
  const [clearing, setClearing] = useState(false);

  useEffect(() => {
    refreshAll();
    loadProfiles();
  }, []);

  async function refreshAll() {
    try {
      const [c, s, p] = await Promise.all([
        axios.get(`${API}/adspower/configs`, { headers: authHeaders() }),
        axios.get(`${API}/adspower/states`, { headers: authHeaders() }),
        axios.get(`${API}/adspower/proxy-creds`, { headers: authHeaders() }),
      ]);
      setConfigs(c.data.configs || []);
      setStates(s.data.states || []);
      setHasProxyCreds(p.data.has_creds);
      setProxyCredsMasked(p.data.base_user_masked || "");
      if ((c.data.configs || []).length > 0 && !selectedCfg) {
        setSelectedCfg(c.data.configs[0].id);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load Profile Builder data");
    }
  }

  async function loadProfiles() {
    try {
      const r = await axios.get(`${API}/adspower/profiles?limit=500`, { headers: authHeaders() });
      setProfiles(r.data.profiles || []);
    } catch {
      /* silent */
    }
  }

  async function addConfig() {
    if (!newCfg.api_key) return toast.error("API key required");
    try {
      await axios.post(`${API}/adspower/configs`, newCfg, { headers: authHeaders() });
      toast.success("AdsPower config saved");
      setShowAddCfg(false);
      setNewCfg({ name: "", api_key: "" });
      refreshAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  }

  async function deleteConfig(id) {
    if (!window.confirm("Delete this AdsPower config?")) return;
    await axios.delete(`${API}/adspower/configs/${id}`, { headers: authHeaders() });
    toast.success("Deleted");
    if (selectedCfg === id) setSelectedCfg(null);
    refreshAll();
  }

  async function testConfig(id) {
    setTestingCfg(id);
    setCfgTestResult((prev) => ({ ...prev, [id]: null }));
    try {
      const r = await axios.post(`${API}/adspower/configs/${id}/test`, {}, { headers: authHeaders() });
      setCfgTestResult((prev) => ({ ...prev, [id]: r.data }));
      if (r.data.ok) toast.success(r.data.message || "AdsPower API connected");
      else toast.error(r.data.message || "AdsPower test failed");
    } catch (e) {
      const msg = e.response?.data?.detail || "Test failed";
      setCfgTestResult((prev) => ({ ...prev, [id]: { ok: false, message: msg } }));
      toast.error(msg);
    } finally {
      setTestingCfg(null);
    }
  }

  async function saveProxyCreds() {
    if (!proxyForm.base_user || !proxyForm.base_pass) return toast.error("Both fields required");
    await axios.post(`${API}/adspower/proxy-creds`, proxyForm, { headers: authHeaders() });
    toast.success("ProxyJet credentials saved");
    setShowProxy(false);
    setProxyForm({ base_user: "", base_pass: "" });
    refreshAll();
  }

  async function clearAll() {
    if (!window.confirm("This will delete ALL your saved profiles. Continue?")) return;
    setClearing(true);
    try {
      const r = await axios.delete(`${API}/adspower/profiles`, { headers: authHeaders() });
      toast.success(`Deleted ${r.data.deleted_profiles} profiles`);
      setProfiles([]);
      setJob(null);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Clear failed");
    } finally {
      setClearing(false);
    }
  }

  async function exportXlsx() {
    setExporting(true);
    try {
      const r = await axios.get(`${API}/adspower/profiles/export`, {
        headers: authHeaders(),
        responseType: "blob",
      });
      const url = URL.createObjectURL(new Blob([r.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `krexion_profiles_${Date.now()}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`Exported ${profiles.length} profiles to Excel`);
    } catch (e) {
      toast.error("Export failed");
    } finally {
      setExporting(false);
    }
  }

  async function generate() {
    if (!selectedCfg) return toast.error("Select an AdsPower config first");
    if (!hasProxyCreds) return toast.error("Save ProxyJet credentials first");
    if (count < 1 || count > 200) return toast.error("Count must be 1-200");

    try {
      const r = await axios.post(
        `${API}/adspower/generate`,
        {
          config_id: selectedCfg,
          count,
          state,
          name_prefix: namePrefix,
          wipe_existing: wipeExisting,
          push_to_adspower: pushToAdspower,
          ua_config: { app, platform },
        },
        { headers: authHeaders() }
      );
      toast.success(`Job started — count ${r.data.count}${r.data.wiped?.deleted_profiles ? ` · wiped ${r.data.wiped.deleted_profiles} old` : ""}`);
      pollJob(r.data.job_id);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Generate failed");
    }
  }

  async function pollJob(jobId) {
    setPolling(true);
    let stop = false;
    while (!stop) {
      try {
        const r = await axios.get(`${API}/adspower/jobs/${jobId}`, { headers: authHeaders() });
        setJob(r.data);
        if (["done", "failed"].includes(r.data.status)) {
          stop = true;
          setPolling(false);
          if (r.data.status === "done") {
            toast.success(`${r.data.profiles.length} profiles created in seconds!`);
            loadProfiles();
          } else toast.error("Job failed - check errors panel");
        }
      } catch {
        stop = true;
        setPolling(false);
      }
      if (!stop) await new Promise((r) => setTimeout(r, 700));
    }
  }

  const appMeta = useMemo(() => APPS.find((a) => a.key === app) || APPS[0], [app]);

  return (
    <>
      <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6" data-testid="adspower-page">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white inline-flex items-center gap-2">
              <Zap size={22} className="text-amber-400" /> Profile Builder
            </h1>
            <p className="text-sm text-[#71717A] mt-1 max-w-2xl">
              Bulk AdsPower-compatible profiles in seconds. Each profile gets a unique sticky US residential IP (ProxyJet, 30-min lock) + a realistic in-app User Agent for the app you target. Export to Excel and bulk-import into AdsPower.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {profiles.length > 0 && (
              <>
                <button
                  onClick={exportXlsx}
                  disabled={exporting}
                  data-testid="export-xlsx"
                  className="inline-flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 transition disabled:opacity-50"
                >
                  {exporting ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
                  Export {profiles.length} ({"  .xlsx"})
                </button>
                <button
                  onClick={clearAll}
                  disabled={clearing}
                  data-testid="clear-all-profiles"
                  className="inline-flex items-center gap-2 text-xs px-3 py-2 rounded-lg bg-red-500/15 text-red-300 border border-red-500/30 hover:bg-red-500/25 transition disabled:opacity-50"
                >
                  {clearing ? <Loader2 size={13} className="animate-spin" /> : <Eraser size={13} />}
                  Clear all
                </button>
              </>
            )}
          </div>
        </div>

        {/* --- Setup row --- */}
        <div className="grid md:grid-cols-2 gap-4">
          {/* AdsPower configs */}
          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white inline-flex items-center gap-2">
                <Key size={15} /> AdsPower API configs
              </h3>
              <button
                onClick={() => setShowAddCfg(true)}
                data-testid="add-adspower-config"
                className="text-xs inline-flex items-center gap-1 px-2 py-1 rounded bg-[#3B82F6] text-black font-semibold hover:bg-[#60A5FA]"
              >
                <Plus size={12} /> Add
              </button>
            </div>
            {configs.length === 0 ? (
              <div className="text-xs text-[#71717A] py-4 text-center">No configs yet - add your AdsPower API key</div>
            ) : (
              <div className="space-y-2">
                {configs.map((c) => {
                  const tr = cfgTestResult[c.id];
                  return (
                    <div
                      key={c.id}
                      className={`rounded border transition ${
                        selectedCfg === c.id
                          ? "bg-[#3B82F6]/10 border-[#3B82F6]/50"
                          : "border-white/10 hover:border-white/20"
                      }`}
                    >
                      <label className="flex items-center gap-3 p-2 cursor-pointer">
                        <input
                          type="radio"
                          checked={selectedCfg === c.id}
                          onChange={() => setSelectedCfg(c.id)}
                          data-testid={`select-config-${c.id}`}
                        />
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-white font-medium truncate inline-flex items-center gap-2">
                            {c.name}
                            {tr && tr.ok && (
                              <span className="text-[10px] inline-flex items-center gap-1 text-emerald-300 bg-emerald-500/10 border border-emerald-500/30 px-1.5 py-0.5 rounded-full">
                                <Wifi size={9} /> Connected
                              </span>
                            )}
                            {tr && !tr.ok && (
                              <span className="text-[10px] inline-flex items-center gap-1 text-red-300 bg-red-500/10 border border-red-500/30 px-1.5 py-0.5 rounded-full">
                                <WifiOff size={9} /> Failed
                              </span>
                            )}
                          </div>
                          <div className="text-[10px] text-[#71717A] truncate font-mono">AdsPower API · {c.api_key_masked}</div>
                        </div>
                        <button
                          onClick={(e) => { e.preventDefault(); testConfig(c.id); }}
                          disabled={testingCfg === c.id}
                          data-testid={`test-config-${c.id}`}
                          className="text-xs inline-flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 disabled:opacity-50"
                        >
                          {testingCfg === c.id ? <Loader2 size={11} className="animate-spin" /> : <ShieldCheck size={11} />}
                          Test
                        </button>
                        <button
                          onClick={(e) => { e.preventDefault(); deleteConfig(c.id); }}
                          data-testid={`delete-config-${c.id}`}
                          className="text-[#71717A] hover:text-red-400 p-1"
                        >
                          <Trash2 size={14} />
                        </button>
                      </label>
                      {tr && !tr.ok && tr.message && (
                        <div className="text-[10px] text-red-300/80 px-3 pb-2 pt-0 break-words">
                          {tr.message}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ProxyJet creds */}
          <div className="bg-white/[0.03] border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-white inline-flex items-center gap-2">
                <Globe size={15} /> ProxyJet credentials
              </h3>
              <button
                onClick={() => setShowProxy(true)}
                data-testid="edit-proxy-creds"
                className="text-xs px-2 py-1 rounded bg-white/10 text-white hover:bg-white/20"
              >
                {hasProxyCreds ? "Update" : "Set up"}
              </button>
            </div>
            {hasProxyCreds ? (
              <div className="text-xs text-emerald-300 inline-flex items-center gap-2">
                <CheckCircle2 size={14} /> Saved: <code className="font-mono bg-black/40 px-2 py-0.5 rounded">{proxyCredsMasked}</code>
              </div>
            ) : (
              <div className="text-xs text-amber-300 inline-flex items-center gap-2">
                <AlertCircle size={14} /> Add your ProxyJet username + password (from ProxyJet dashboard "Proxy Generator").
              </div>
            )}
          </div>
        </div>

        {/* --- App picker --- */}
        <div className="bg-white/[0.03] border border-white/10 rounded-xl p-5">
          <h3 className="text-sm font-bold text-white inline-flex items-center gap-2 mb-4">
            <Cpu size={15} /> Target app &amp; platform
          </h3>
          <div className="text-xs text-[#71717A] mb-2">App / platform — UAs are tuned for this app</div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
            {APPS.map((a) => (
              <button
                key={a.key}
                onClick={() => setApp(a.key)}
                data-testid={`app-${a.key}`}
                className={`text-xs font-semibold px-3 py-2.5 rounded-lg border transition text-left ${
                  app === a.key
                    ? `bg-gradient-to-br ${a.color} text-white border-white/30 shadow-lg`
                    : "bg-white/[0.02] border-white/10 text-[#A1A1AA] hover:border-white/30 hover:text-white"
                }`}
              >
                {a.label}
              </button>
            ))}
          </div>
          <div className="text-xs text-[#71717A] mt-4 mb-2">Operating system</div>
          <div className="flex flex-wrap gap-2">
            {PLATFORMS.map((p) => (
              <button
                key={p.key}
                onClick={() => setPlatform(p.key)}
                data-testid={`platform-${p.key}`}
                className={`text-xs font-semibold px-4 py-2 rounded-lg border transition ${
                  platform === p.key
                    ? "bg-[#3B82F6] text-black border-[#3B82F6]"
                    : "bg-white/[0.02] border-white/10 text-[#A1A1AA] hover:border-white/30 hover:text-white"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* --- Generate form --- */}
        <div className="bg-white/[0.03] border border-white/10 rounded-xl p-5">
          <h3 className="text-sm font-bold text-white inline-flex items-center gap-2 mb-4">
            <PlayCircle size={15} /> Generate profiles
          </h3>
          {selectedCfg ? (
            <div className="mb-4 inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-full bg-[#3B82F6]/15 border border-[#3B82F6]/30 text-[#93C5FD]" data-testid="active-config-banner">
              <Key size={11} />
              Profiles will be created on AdsPower account: <b className="text-white">{(configs.find((c) => c.id === selectedCfg) || {}).name || "—"}</b>
            </div>
          ) : (
            <div className="mb-4 inline-flex items-center gap-2 text-xs px-3 py-1.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-300">
              <AlertCircle size={11} /> Select an AdsPower API config above first
            </div>
          )}
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-[#71717A] block mb-1">Count (1-200)</label>
              <input
                type="number"
                min={1}
                max={200}
                value={count}
                onChange={(e) => {
                  const v = parseInt(e.target.value);
                  if (Number.isNaN(v)) return setCount(1);
                  setCount(Math.max(1, Math.min(200, v)));
                }}
                data-testid="generate-count"
                className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-[#71717A] block mb-1">US State (sticky IP region)</label>
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                data-testid="generate-state"
                className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm"
              >
                {states.map((s) => (
                  <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-[#71717A] block mb-1">Name prefix</label>
              <input
                type="text"
                value={namePrefix}
                onChange={(e) => setNamePrefix(e.target.value)}
                data-testid="generate-prefix"
                className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm"
                placeholder="krexion"
              />
              <div className="text-[10px] text-[#71717A] mt-1">e.g. {namePrefix}-{state.replace(/_/g, "")}-001</div>
            </div>
            <div className="flex items-end">
              <button
                onClick={generate}
                disabled={polling}
                data-testid="generate-button"
                className={`w-full inline-flex items-center justify-center gap-2 font-bold px-4 py-2.5 rounded-lg bg-gradient-to-r ${appMeta.color} text-white hover:opacity-90 transition disabled:opacity-60`}
              >
                {polling ? <Loader2 size={15} className="animate-spin" /> : <Zap size={16} />}
                {polling ? "Building…" : `Build ${count} now`}
              </button>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-4">
            <label className="text-xs inline-flex items-center gap-2 px-3 py-2 rounded-lg border bg-white/[0.02] border-white/10 text-[#A1A1AA] hover:border-white/20 cursor-pointer">
              <input
                type="checkbox"
                checked={wipeExisting}
                onChange={(e) => setWipeExisting(e.target.checked)}
                data-testid="wipe-existing-toggle"
                className="accent-red-500"
              />
              <Eraser size={12} className="text-red-300" />
              Delete existing profiles before building
            </label>
            <label className="text-xs inline-flex items-center gap-2 px-3 py-2 rounded-lg border bg-white/[0.02] border-white/10 text-[#A1A1AA] hover:border-white/20 cursor-pointer">
              <input
                type="checkbox"
                checked={verifyUniqueIps}
                onChange={(e) => setVerifyUniqueIps(e.target.checked)}
                data-testid="verify-unique-ips-toggle"
                className="accent-amber-500"
              />
              <ShieldCheck size={12} className="text-amber-300" />
              Verify each proxy gives a unique IP (slower — checks ipify before saving)
            </label>
            <label className="text-xs inline-flex items-center gap-2 px-3 py-2 rounded-lg border bg-white/[0.02] border-white/10 text-[#A1A1AA] hover:border-white/20 cursor-pointer">
              <input
                type="checkbox"
                checked={pushToAdspower}
                onChange={(e) => setPushToAdspower(e.target.checked)}
                data-testid="push-adspower-toggle"
                className="accent-emerald-500"
              />
              <CheckCircle2 size={12} className="text-emerald-300" />
              Also push directly into AdsPower (requires local PC online)
            </label>
          </div>
        </div>

        {/* --- Job progress --- */}
        {job && <JobProgress job={job} />}

        {/* --- Profiles table --- */}
        {profiles.length > 0 && <ProfilesTable profiles={profiles} />}
      </div>

      {/* Add config modal */}
      {showAddCfg && (
        <div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0f0a18] border border-[#3B82F6]/40 rounded-2xl w-full max-w-md p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Add AdsPower API</h3>
            <p className="text-[11px] text-[#71717A] -mt-2">
              Open <span className="font-semibold text-white">AdsPower → API → Local API</span> and paste your <span className="font-semibold text-white">API key</span> below. That's it — Krexion handles the connection automatically.
            </p>
            <input
              placeholder="Name (e.g. Main account)"
              value={newCfg.name}
              onChange={(e) => setNewCfg({ ...newCfg, name: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm"
              data-testid="new-cfg-name"
            />
            <input
              placeholder="API Key (from AdsPower → API Settings)"
              value={newCfg.api_key}
              onChange={(e) => setNewCfg({ ...newCfg, api_key: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm font-mono"
              data-testid="new-cfg-key"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowAddCfg(false)} className="px-3 py-1.5 text-sm text-[#A1A1AA] hover:text-white">Cancel</button>
              <button onClick={addConfig} data-testid="save-new-cfg" className="px-4 py-2 bg-[#3B82F6] text-black font-bold rounded text-sm">Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Proxy creds modal */}
      {showProxy && (
        <div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0f0a18] border border-[#3B82F6]/40 rounded-2xl w-full max-w-md p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">ProxyJet credentials</h3>
            <p className="text-xs text-[#71717A]">
              ProxyJet dashboard → Proxy Generator → copy <b>Proxy Username</b> + <b>Proxy Password</b>.
            </p>
            <input
              placeholder="Base username (e.g. 260202i9bQO)"
              value={proxyForm.base_user}
              onChange={(e) => setProxyForm({ ...proxyForm, base_user: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm font-mono"
              data-testid="proxy-base-user"
            />
            <input
              placeholder="Base password"
              value={proxyForm.base_pass}
              onChange={(e) => setProxyForm({ ...proxyForm, base_pass: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm font-mono"
              data-testid="proxy-base-pass"
            />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowProxy(false)} className="px-3 py-1.5 text-sm text-[#A1A1AA] hover:text-white">Cancel</button>
              <button onClick={saveProxyCreds} data-testid="save-proxy-creds" className="px-4 py-2 bg-[#3B82F6] text-black font-bold rounded text-sm">Save</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function JobProgress({ job }) {
  const pct = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;
  const colors = {
    running: "bg-blue-500/15 border-blue-500/30 text-blue-300",
    creating_profiles: "bg-amber-500/15 border-amber-500/30 text-amber-300",
    done: "bg-emerald-500/15 border-emerald-500/30 text-emerald-300",
    failed: "bg-red-500/15 border-red-500/30 text-red-300",
  };
  return (
    <div className="bg-white/[0.03] border border-white/10 rounded-xl p-5 space-y-4" data-testid="job-progress">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <div className="text-xs text-[#71717A] mb-1">Job · {job.id.slice(0, 8)}</div>
          <div className={`inline-block text-xs font-bold uppercase tracking-wider px-2 py-1 rounded border ${colors[job.status] || ""}`}>
            {job.status.replace(/_/g, " ")}
          </div>
        </div>
        <div className="text-sm text-white">
          <span className="font-bold">{job.progress}</span>
          <span className="text-[#71717A]"> / {job.total}</span>
        </div>
      </div>
      <div className="w-full bg-black/40 rounded-full h-2 overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-[#3B82F6] to-[#60A5FA] transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      {job.errors && job.errors.length > 0 && (
        <div className="bg-red-500/10 border border-red-500/30 rounded p-3 text-xs text-red-300 max-h-32 overflow-auto">
          {job.errors.map((e, i) => <div key={i}>· {e}</div>)}
        </div>
      )}
    </div>
  );
}

function ProfilesTable({ profiles }) {
  const [copiedKey, setCopiedKey] = useState(null);
  function copy(val, key) {
    navigator.clipboard.writeText(val);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1200);
  }
  return (
    <div className="bg-white/[0.03] border border-white/10 rounded-xl p-4 space-y-3" data-testid="profiles-table">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-bold text-white">Generated profiles ({profiles.length})</h3>
        <div className="text-[10px] text-[#71717A]">Latest at top · 30-min sticky IP lock</div>
      </div>
      <div className="overflow-auto max-h-[500px] border border-white/10 rounded">
        <table className="w-full text-xs">
          <thead className="bg-white/[0.04] text-[#71717A] sticky top-0">
            <tr>
              <th className="text-left px-3 py-2">#</th>
              <th className="text-left px-3 py-2">Name</th>
              <th className="text-left px-3 py-2">IP</th>
              <th className="text-left px-3 py-2">Device</th>
              <th className="text-left px-3 py-2">Platform</th>
              <th className="text-left px-3 py-2">UA</th>
              <th className="text-left px-3 py-2">Account</th>
              <th className="text-left px-3 py-2">Push</th>
            </tr>
          </thead>
          <tbody>
            {profiles.map((p, i) => (
              <tr key={p.id || i} className="border-t border-white/5" data-testid={`profile-row-${i}`}>
                <td className="px-3 py-2 text-[#71717A]">{i + 1}</td>
                <td className="px-3 py-2 text-white font-mono whitespace-nowrap">{p.name}</td>
                <td className="px-3 py-2 text-emerald-300 font-mono whitespace-nowrap">
                  {p.ip ? (
                    <span className="inline-flex items-center gap-1">
                      {p.ip}
                      <button onClick={() => copy(p.ip, `ip-${i}`)} className="text-[#71717A] hover:text-white">
                        {copiedKey === `ip-${i}` ? <Check size={11} /> : <Copy size={11} />}
                      </button>
                    </span>
                  ) : (
                    <span className="text-[#71717A]">— sticky</span>
                  )}
                </td>
                <td className="px-3 py-2 text-[#A1A1AA]">{p.device_label || "-"}</td>
                <td className="px-3 py-2 text-[#A1A1AA]">{p.ua_platform || "-"}</td>
                <td className="px-3 py-2 text-emerald-300 font-mono max-w-md">
                  <div className="truncate" title={p.user_agent}>{p.user_agent}</div>
                </td>
                <td className="px-3 py-2 text-[#A1A1AA] whitespace-nowrap">{p.config_name || "—"}</td>
                <td className="px-3 py-2 text-[#A1A1AA] text-[10px]">{p.push_status || "skipped"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
