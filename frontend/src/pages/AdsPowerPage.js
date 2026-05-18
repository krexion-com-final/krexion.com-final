import React, { useEffect, useState } from "react";
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
} from "lucide-react";

const API = (process.env.REACT_APP_BACKEND_URL || "") + "/api/adspower";

const UA_LABELS = {
  windows_chrome: "Windows · Chrome",
  windows_edge: "Windows · Edge",
  mac_chrome: "macOS · Chrome",
  mac_safari: "macOS · Safari",
  iphone_safari: "iPhone · Safari",
  android_chrome: "Android · Chrome",
};

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
  const [newCfg, setNewCfg] = useState({ name: "", host: "http://local.adspower.net:50325", api_key: "" });
  const [showProxy, setShowProxy] = useState(false);
  const [proxyForm, setProxyForm] = useState({ base_user: "", base_pass: "" });

  const [selectedCfg, setSelectedCfg] = useState(null);
  const [count, setCount] = useState(10);
  const [state, setState] = useState("California");
  const [namePrefix, setNamePrefix] = useState("krexion");
  const [uaTemplates, setUaTemplates] = useState(["windows_chrome", "mac_chrome"]);

  const [job, setJob] = useState(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    refreshAll();
  }, []);

  async function refreshAll() {
    try {
      const [c, s, p] = await Promise.all([
        axios.get(`${API}/configs`, { headers: authHeaders() }),
        axios.get(`${API}/states`, { headers: authHeaders() }),
        axios.get(`${API}/proxy-creds`, { headers: authHeaders() }),
      ]);
      setConfigs(c.data.configs || []);
      setStates(s.data.states || []);
      setHasProxyCreds(p.data.has_creds);
      setProxyCredsMasked(p.data.base_user_masked || "");
      if ((c.data.configs || []).length > 0 && !selectedCfg) {
        setSelectedCfg(c.data.configs[0].id);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load AdsPower data");
    }
  }

  async function addConfig() {
    if (!newCfg.api_key) return toast.error("API key required");
    try {
      await axios.post(`${API}/configs`, newCfg, { headers: authHeaders() });
      toast.success("AdsPower config saved");
      setShowAddCfg(false);
      setNewCfg({ name: "", host: "http://local.adspower.net:50325", api_key: "" });
      refreshAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  }

  async function deleteConfig(id) {
    if (!window.confirm("Delete this AdsPower config?")) return;
    await axios.delete(`${API}/configs/${id}`, { headers: authHeaders() });
    toast.success("Deleted");
    if (selectedCfg === id) setSelectedCfg(null);
    refreshAll();
  }

  async function saveProxyCreds() {
    if (!proxyForm.base_user || !proxyForm.base_pass) return toast.error("Both fields required");
    await axios.post(`${API}/proxy-creds`, proxyForm, { headers: authHeaders() });
    toast.success("ProxyJet credentials saved");
    setShowProxy(false);
    setProxyForm({ base_user: "", base_pass: "" });
    refreshAll();
  }

  function toggleUa(key) {
    setUaTemplates((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  async function generate() {
    if (!selectedCfg) return toast.error("Select an AdsPower config first");
    if (!hasProxyCreds) return toast.error("Save ProxyJet credentials first");
    if (uaTemplates.length === 0) return toast.error("Pick at least one UA template");
    if (count < 1 || count > 100) return toast.error("Count must be 1-100");

    try {
      const r = await axios.post(
        `${API}/generate`,
        {
          config_id: selectedCfg,
          count,
          state,
          ua_templates: uaTemplates,
          name_prefix: namePrefix,
        },
        { headers: authHeaders() }
      );
      toast.success(`Job started (${r.data.job_id.slice(0, 8)}...)`);
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
        const r = await axios.get(`${API}/jobs/${jobId}`, { headers: authHeaders() });
        setJob(r.data);
        if (["done", "failed"].includes(r.data.status)) {
          stop = true;
          setPolling(false);
          if (r.data.status === "done") toast.success(`${r.data.profiles.length} profiles created!`);
          else toast.error("Job failed - check errors panel");
        }
      } catch {
        stop = true;
        setPolling(false);
      }
      if (!stop) await new Promise((r) => setTimeout(r, 2500));
    }
  }

  return (
    <>
      <div className="max-w-6xl mx-auto p-4 sm:p-6 space-y-6" data-testid="adspower-page">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white">Profile Builder</h1>
            <p className="text-sm text-[#71717A] mt-1">
              Bulk AdsPower antidetect profiles with unique sticky US IPs (ProxyJet residential) + diverse user agents. 30-min IP lock so sessions don't rotate while you work.
            </p>
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
                {configs.map((c) => (
                  <label
                    key={c.id}
                    className={`flex items-center gap-3 p-2 rounded border cursor-pointer transition ${
                      selectedCfg === c.id
                        ? "bg-[#3B82F6]/10 border-[#3B82F6]/50"
                        : "border-white/10 hover:border-white/20"
                    }`}
                  >
                    <input
                      type="radio"
                      checked={selectedCfg === c.id}
                      onChange={() => setSelectedCfg(c.id)}
                      data-testid={`select-config-${c.id}`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white font-medium truncate">{c.name}</div>
                      <div className="text-[10px] text-[#71717A] truncate font-mono">{c.host} · {c.api_key_masked}</div>
                    </div>
                    <button
                      onClick={(e) => { e.preventDefault(); deleteConfig(c.id); }}
                      data-testid={`delete-config-${c.id}`}
                      className="text-[#71717A] hover:text-red-400 p-1"
                    >
                      <Trash2 size={14} />
                    </button>
                  </label>
                ))}
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
                <AlertCircle size={14} /> Add your ProxyJet username + password (visible in your ProxyJet dashboard "Proxy Generator").
              </div>
            )}
          </div>
        </div>

        {/* --- Generate form --- */}
        <div className="bg-white/[0.03] border border-white/10 rounded-xl p-5">
          <h3 className="text-sm font-bold text-white inline-flex items-center gap-2 mb-4">
            <Cpu size={15} /> Generate profiles
          </h3>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-[#71717A] block mb-1">Count (1-100)</label>
              <input
                type="number"
                min={1}
                max={100}
                value={count}
                onChange={(e) => setCount(parseInt(e.target.value) || 1)}
                data-testid="generate-count"
                className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm"
              />
            </div>
            <div>
              <label className="text-xs text-[#71717A] block mb-1">US State</label>
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
                className="w-full inline-flex items-center justify-center gap-2 font-bold px-4 py-2.5 rounded-lg bg-[#3B82F6] text-black hover:bg-[#60A5FA] transition disabled:opacity-60"
              >
                {polling ? <Loader2 size={15} className="animate-spin" /> : <PlayCircle size={16} />}
                {polling ? "Running…" : "Generate profiles"}
              </button>
            </div>
          </div>
          <div className="mt-5">
            <div className="text-xs text-[#71717A] mb-2">User-agent mix (pick one or many)</div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(UA_LABELS).map(([k, label]) => (
                <label
                  key={k}
                  className={`text-xs inline-flex items-center gap-2 px-3 py-1.5 rounded-full border cursor-pointer transition ${
                    uaTemplates.includes(k)
                      ? "bg-[#3B82F6]/15 border-[#3B82F6]/50 text-[#93C5FD]"
                      : "bg-white/[0.02] border-white/10 text-[#A1A1AA] hover:border-white/20"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={uaTemplates.includes(k)}
                    onChange={() => toggleUa(k)}
                    data-testid={`ua-toggle-${k}`}
                    className="accent-[#3B82F6]"
                  />
                  {label}
                </label>
              ))}
            </div>
          </div>
        </div>

        {/* --- Job progress --- */}
        {job && <JobProgress job={job} />}
      </div>

      {/* Add config modal */}
      {showAddCfg && (
        <div className="fixed inset-0 z-[100] bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#0f0a18] border border-[#3B82F6]/40 rounded-2xl w-full max-w-md p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Add AdsPower API</h3>
            <input
              placeholder="Name (e.g. Main account)"
              value={newCfg.name}
              onChange={(e) => setNewCfg({ ...newCfg, name: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm"
              data-testid="new-cfg-name"
            />
            <input
              placeholder="Host (default ok)"
              value={newCfg.host}
              onChange={(e) => setNewCfg({ ...newCfg, host: e.target.value })}
              className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-white text-sm font-mono"
              data-testid="new-cfg-host"
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
  const [copyIp, setCopyIp] = useState(null);
  function copy(text) {
    navigator.clipboard.writeText(text);
    setCopyIp(text);
    setTimeout(() => setCopyIp(null), 1500);
  }
  const pct = job.total > 0 ? Math.round((job.progress / job.total) * 100) : 0;
  const colors = {
    allocating_ips: "bg-blue-500/15 border-blue-500/30 text-blue-300",
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
      {job.profiles && job.profiles.length > 0 && (
        <div className="overflow-auto max-h-96 border border-white/10 rounded">
          <table className="w-full text-xs">
            <thead className="bg-white/[0.04] text-[#71717A]">
              <tr>
                <th className="text-left px-3 py-2">#</th>
                <th className="text-left px-3 py-2">Name</th>
                <th className="text-left px-3 py-2">IP</th>
                <th className="text-left px-3 py-2">AdsPower ID</th>
              </tr>
            </thead>
            <tbody>
              {job.profiles.map((p, i) => (
                <tr key={i} className="border-t border-white/5" data-testid={`profile-row-${i}`}>
                  <td className="px-3 py-2 text-[#71717A]">{i + 1}</td>
                  <td className="px-3 py-2 text-white font-mono">{p.name}</td>
                  <td className="px-3 py-2 text-emerald-300 font-mono inline-flex items-center gap-1">
                    {p.ip}
                    <button onClick={() => copy(p.ip)} className="text-[#71717A] hover:text-white">
                      {copyIp === p.ip ? <Check size={11} /> : <Copy size={11} />}
                    </button>
                  </td>
                  <td className="px-3 py-2 text-[#A1A1AA] font-mono">{p.adspower_id || "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
