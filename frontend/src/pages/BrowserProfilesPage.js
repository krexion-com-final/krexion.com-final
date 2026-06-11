/* eslint-disable react-hooks/exhaustive-deps */
import { useState, useEffect, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { toast } from "sonner";
import {
  Plus,
  Trash2,
  Play,
  StopCircle,
  Copy,
  Download,
  Globe,
  Smartphone,
  Monitor,
  Shield,
  RefreshCw,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/browser-profiles`;

const COUNTRY_OPTIONS = [
  "US","GB","CA","AU","DE","FR","ES","IT","NL","BR","MX","IN","PK","BD","ID","PH","JP","KR","TR","AE","SA","ZA","NG","KE","RU","UA","PL","PT","SE","NO","DK","FI",
];

const DEFAULT_NEW = {
  name: "",
  notes: "",
  country: "us",
  language: "en-US",
  timezone: "America/New_York",
  device_type: "desktop",
  os: "windows",
  user_agent: "",
  viewport: { width: 1920, height: 1080 },
  is_mobile: false,
  has_touch: false,
  device_scale_factor: 1,
  locale: "en-US",
  accept_language: "en-US,en;q=0.9",
  start_url: "https://www.google.com/",
  tags: [],
  proxy: {
    enabled: false,
    server: "",
    username: "",
    password: "",
    use_proxyjet: false,
    proxyjet_country: "US",
    proxyjet_state: "",
  },
  anti_detect: {
    master: true,
    tls_prewarm: true,
    behavioral_bio: true,
    ip_warmup: false,
    browser_variant: "rotate",
    identity_persist: true,
    paranoia_mode: false,
  },
  referrer: {
    enabled: false,
    pro_mode: true,
    platform_weights: { google: 50, facebook: 25, tiktok: 25 },
    email_weights: {},
    social_wrapper: true,
    inapp_deep_path: true,
    strip_search_path: true,
    network_click_chain: false,
    search_engine: "google",
    search_keywords: "",
    brand: "",
  },
};

export default function BrowserProfilesPage() {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(DEFAULT_NEW);
  const [editingId, setEditingId] = useState(null);
  const [statusMap, setStatusMap] = useState({}); // id → status info

  const authHeaders = useMemo(() => {
    const t = localStorage.getItem("token");
    return { Authorization: `Bearer ${t}`, "Content-Type": "application/json" };
  }, []);

  const fetchProfiles = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/`, { headers: authHeaders });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const d = await r.json();
      setProfiles(d.profiles || []);
    } catch (e) {
      toast.error(`Failed to load profiles: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfiles();
  }, []);

  const handleQuickGenerate = async (deviceType = "desktop") => {
    try {
      const r = await fetch(`${API}/quick-generate`, {
        method: "POST", headers: authHeaders,
        body: JSON.stringify({ device_type: deviceType, country: form.country || "us" }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      toast.success(`Profile "${d.profile.name}" created`);
      fetchProfiles();
    } catch (e) { toast.error(`Quick generate failed: ${e.message}`); }
  };

  const handleCreate = async () => {
    if (!form.name.trim()) { toast.error("Name is required"); return; }
    try {
      const url = editingId ? `${API}/${editingId}` : `${API}/`;
      const method = editingId ? "PUT" : "POST";
      const r = await fetch(url, {
        method, headers: authHeaders, body: JSON.stringify(form),
      });
      if (!r.ok) throw new Error(await r.text());
      toast.success(editingId ? "Profile updated" : "Profile created");
      setShowCreate(false); setEditingId(null); setForm(DEFAULT_NEW);
      fetchProfiles();
    } catch (e) { toast.error(`Save failed: ${e.message}`); }
  };

  const handleEdit = async (id) => {
    try {
      const r = await fetch(`${API}/${id}`, { headers: authHeaders });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      // Backend strips storage_state from response — that's fine for edit
      const p = d.profile || {};
      setForm({
        ...DEFAULT_NEW,
        ...p,
        proxy: { ...DEFAULT_NEW.proxy, ...(p.proxy || {}) },
        anti_detect: { ...DEFAULT_NEW.anti_detect, ...(p.anti_detect || {}) },
        referrer: { ...DEFAULT_NEW.referrer, ...(p.referrer || {}) },
      });
      setEditingId(id); setShowCreate(true);
    } catch (e) { toast.error(`Load profile failed: ${e.message}`); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this profile? Storage state will be lost.")) return;
    try {
      const r = await fetch(`${API}/${id}`, { method: "DELETE", headers: authHeaders });
      if (!r.ok) throw new Error(await r.text());
      toast.success("Profile deleted"); fetchProfiles();
    } catch (e) { toast.error(`Delete failed: ${e.message}`); }
  };

  const handleClone = async (id) => {
    try {
      const r = await fetch(`${API}/${id}/clone`, { method: "POST", headers: authHeaders });
      if (!r.ok) throw new Error(await r.text());
      toast.success("Profile cloned"); fetchProfiles();
    } catch (e) { toast.error(`Clone failed: ${e.message}`); }
  };

  const handleLaunch = async (id, startUrl) => {
    try {
      const r = await fetch(`${API}/${id}/launch`, {
        method: "POST", headers: authHeaders,
        body: JSON.stringify({ start_url: startUrl || undefined }),
      });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      setStatusMap((m) => ({ ...m, [id]: { ...d } }));
      if (d.desktop_available) {
        toast.success("Launch queued — desktop app will open the browser");
      } else {
        toast.warning("Profile saved — install the Krexion desktop app to launch", { duration: 6000 });
      }
      fetchProfiles();
    } catch (e) { toast.error(`Launch failed: ${e.message}`); }
  };

  const handleStop = async (id) => {
    try {
      const r = await fetch(`${API}/${id}/stop`, { method: "POST", headers: authHeaders });
      if (!r.ok) throw new Error(await r.text());
      toast.success("Stop signal sent"); fetchProfiles();
    } catch (e) { toast.error(`Stop failed: ${e.message}`); }
  };

  const handleExport = async () => {
    try {
      const r = await fetch(`${API}/export/all`, { headers: authHeaders });
      if (!r.ok) throw new Error(await r.text());
      const d = await r.json();
      const blob = new Blob([JSON.stringify(d, null, 2)], { type: "application/json" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `krexion-browser-profiles-${new Date().toISOString().slice(0,10)}.json`;
      link.click();
      toast.success(`Exported ${d.count} profiles`);
    } catch (e) { toast.error(`Export failed: ${e.message}`); }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-3xl font-bold bg-gradient-to-r from-fuchsia-400 via-purple-400 to-cyan-400 bg-clip-text text-transparent">
              🌐 Browser Profiles
            </h1>
            <p className="text-zinc-400 text-sm mt-1">
              AdsPower / GoLogin-style manual browsing profiles. Each profile uses the FULL Krexion anti-detect stack — same anti-detect engine that powers Real User Traffic.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              data-testid="bp-quick-desktop"
              onClick={() => handleQuickGenerate("desktop")}
              className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white"
            >
              <Plus className="w-4 h-4 mr-1" /> Quick Desktop
            </Button>
            <Button
              data-testid="bp-quick-mobile"
              onClick={() => handleQuickGenerate("mobile")}
              className="bg-cyan-600 hover:bg-cyan-700 text-white"
            >
              <Smartphone className="w-4 h-4 mr-1" /> Quick Mobile
            </Button>
            <Button
              data-testid="bp-open-create"
              onClick={() => { setEditingId(null); setForm(DEFAULT_NEW); setShowCreate(true); }}
              variant="outline" className="border-zinc-700 text-zinc-300"
            >
              <Plus className="w-4 h-4 mr-1" /> Custom Profile
            </Button>
            <Button data-testid="bp-export" onClick={handleExport} variant="outline" className="border-zinc-700 text-zinc-300">
              <Download className="w-4 h-4 mr-1" /> Export
            </Button>
            <Button data-testid="bp-refresh" onClick={fetchProfiles} variant="outline" className="border-zinc-700 text-zinc-300">
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* Info banner */}
        <div className="mb-6 p-3 rounded-lg bg-amber-950/20 border border-amber-700/40 text-xs text-amber-200 flex items-start gap-2">
          <Shield className="w-4 h-4 mt-0.5 text-amber-300" />
          <div>
            <span className="font-semibold">How it works:</span> Configure profile here in the cloud. Click <span className="text-amber-300">Launch</span> → your Krexion desktop app picks up the job → opens a HEADED Chromium with all anti-detect injected + cookies/localStorage seeded from previous sessions. Manual browsing fully anonymous, looks like a real user. Storage state syncs back here so you can resume across devices.
          </div>
        </div>

        {/* Profile list */}
        {profiles.length === 0 ? (
          <Card className="bg-zinc-900/50 border-zinc-800 mt-4">
            <CardContent className="py-12 text-center text-zinc-500">
              <Globe className="w-12 h-12 mx-auto mb-3 text-zinc-700" />
              <p>No profiles yet. Click <span className="text-fuchsia-400 font-semibold">Quick Desktop</span> or <span className="text-cyan-400 font-semibold">Quick Mobile</span> for a one-click profile.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {profiles.map((p) => (
              <Card key={p.id} className="bg-zinc-900/60 border-zinc-800 hover:border-fuchsia-700/40 transition" data-testid={`bp-card-${p.id}`}>
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-base text-zinc-100 truncate">{p.name}</CardTitle>
                      <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                        <Badge variant="outline" className="text-[10px] bg-zinc-900 border-zinc-700 text-zinc-300">
                          {p.device_type === "mobile" ? <Smartphone className="w-3 h-3 mr-0.5" /> : <Monitor className="w-3 h-3 mr-0.5" />}
                          {p.device_type}
                        </Badge>
                        <Badge variant="outline" className="text-[10px] bg-zinc-900 border-zinc-700 text-zinc-300">{(p.country || "?").toUpperCase()}</Badge>
                        {p.anti_detect?.master && (
                          <Badge variant="outline" className="text-[10px] bg-fuchsia-950/40 border-fuchsia-700/60 text-fuchsia-300">
                            <Shield className="w-3 h-3 mr-0.5" /> AD
                          </Badge>
                        )}
                        <Badge variant="outline" className={`text-[10px] ${p.status === 'running' ? 'bg-emerald-950/40 border-emerald-700 text-emerald-300' : p.status === 'launching' ? 'bg-amber-950/40 border-amber-700 text-amber-300' : 'bg-zinc-900 border-zinc-700 text-zinc-400'}`}>
                          {p.status || "idle"}
                        </Badge>
                      </div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-0 pb-3">
                  <div className="text-[11px] text-zinc-500 truncate mb-2" title={p.user_agent}>
                    {(p.user_agent || "").slice(0, 60)}…
                  </div>
                  <div className="text-[11px] text-zinc-500 mb-3">
                    {p.viewport?.width}×{p.viewport?.height} · {p.locale} · {p.total_launches || 0} launches
                    {p.storage_state_stats?.cookie_count > 0 && (
                      <span className="text-emerald-400 ml-1">· {p.storage_state_stats.cookie_count} cookies</span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {p.status === "running" || p.status === "launching" ? (
                      <Button data-testid={`bp-stop-${p.id}`} onClick={() => handleStop(p.id)} size="sm" className="bg-red-600 hover:bg-red-700 text-white h-7 text-xs">
                        <StopCircle className="w-3 h-3 mr-1" /> Stop
                      </Button>
                    ) : (
                      <Button data-testid={`bp-launch-${p.id}`} onClick={() => handleLaunch(p.id)} size="sm" className="bg-emerald-600 hover:bg-emerald-700 text-white h-7 text-xs">
                        <Play className="w-3 h-3 mr-1" /> Launch
                      </Button>
                    )}
                    <Button data-testid={`bp-edit-${p.id}`} onClick={() => handleEdit(p.id)} variant="outline" size="sm" className="border-zinc-700 text-zinc-300 h-7 text-xs">
                      Edit
                    </Button>
                    <Button data-testid={`bp-clone-${p.id}`} onClick={() => handleClone(p.id)} variant="outline" size="sm" className="border-zinc-700 text-zinc-300 h-7 text-xs">
                      <Copy className="w-3 h-3" />
                    </Button>
                    <Button data-testid={`bp-delete-${p.id}`} onClick={() => handleDelete(p.id)} variant="outline" size="sm" className="border-red-900/60 text-red-400 hover:bg-red-950/40 h-7 text-xs">
                      <Trash2 className="w-3 h-3" />
                    </Button>
                  </div>
                  {statusMap[p.id]?.message && (
                    <div className="mt-2 text-[10px] text-amber-300/80 italic">{statusMap[p.id].message}</div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Create / Edit dialog */}
        {showCreate && (
          <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4" onClick={() => setShowCreate(false)}>
            <div className="bg-zinc-950 border border-zinc-800 rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
              <div className="p-5 border-b border-zinc-800 sticky top-0 bg-zinc-950 z-10">
                <h2 className="text-xl font-semibold text-zinc-100">{editingId ? "Edit Profile" : "New Browser Profile"}</h2>
              </div>
              <div className="p-5 space-y-4">
                {/* Basic */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label className="text-zinc-300 text-xs">Name</Label>
                    <Input data-testid="bp-form-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                      className="bg-zinc-900 border-zinc-700 text-zinc-100" placeholder="Marketing Account US #1" />
                  </div>
                  <div>
                    <Label className="text-zinc-300 text-xs">Country</Label>
                    <select data-testid="bp-form-country" value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value.toLowerCase() })}
                      className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-zinc-100 rounded px-2 py-1.5 text-sm">
                      {COUNTRY_OPTIONS.map((c) => <option key={c} value={c.toLowerCase()}>{c}</option>)}
                    </select>
                  </div>
                  <div>
                    <Label className="text-zinc-300 text-xs">Device Type</Label>
                    <select data-testid="bp-form-device" value={form.device_type}
                      onChange={(e) => {
                        const mob = e.target.value === "mobile";
                        setForm({ ...form, device_type: e.target.value, is_mobile: mob, has_touch: mob, device_scale_factor: mob ? 3 : 1, os: mob ? "ios" : "windows" });
                      }}
                      className="w-full mt-1 bg-zinc-900 border border-zinc-700 text-zinc-100 rounded px-2 py-1.5 text-sm">
                      <option value="desktop">Desktop</option>
                      <option value="mobile">Mobile</option>
                    </select>
                  </div>
                  <div>
                    <Label className="text-zinc-300 text-xs">Start URL</Label>
                    <Input data-testid="bp-form-starturl" value={form.start_url} onChange={(e) => setForm({ ...form, start_url: e.target.value })}
                      className="bg-zinc-900 border-zinc-700 text-zinc-100" />
                  </div>
                  <div className="col-span-2">
                    <Label className="text-zinc-300 text-xs">User Agent <span className="text-zinc-500">(leave blank = auto-generate)</span></Label>
                    <Input data-testid="bp-form-ua" value={form.user_agent} onChange={(e) => setForm({ ...form, user_agent: e.target.value })}
                      className="bg-zinc-900 border-zinc-700 text-zinc-100 font-mono text-xs" placeholder="Auto" />
                  </div>
                  <div>
                    <Label className="text-zinc-300 text-xs">Viewport Width</Label>
                    <Input type="number" value={form.viewport.width}
                      onChange={(e) => setForm({ ...form, viewport: { ...form.viewport, width: parseInt(e.target.value) || 1920 } })}
                      className="bg-zinc-900 border-zinc-700 text-zinc-100" />
                  </div>
                  <div>
                    <Label className="text-zinc-300 text-xs">Viewport Height</Label>
                    <Input type="number" value={form.viewport.height}
                      onChange={(e) => setForm({ ...form, viewport: { ...form.viewport, height: parseInt(e.target.value) || 1080 } })}
                      className="bg-zinc-900 border-zinc-700 text-zinc-100" />
                  </div>
                  <div className="col-span-2">
                    <Label className="text-zinc-300 text-xs">Notes</Label>
                    <Textarea data-testid="bp-form-notes" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                      rows={2} className="bg-zinc-900 border-zinc-700 text-zinc-100" placeholder="Optional notes (e.g. 'Used for advertiser X login')" />
                  </div>
                </div>

                {/* Anti-Detect */}
                <div className="p-3 rounded-lg border border-fuchsia-500/30 bg-fuchsia-950/10">
                  <label className="flex items-center justify-between cursor-pointer">
                    <div>
                      <span className="text-fuchsia-300 text-sm font-semibold">🛡️ Anti-Detect</span>
                      <p className="text-[11px] text-zinc-400 mt-0.5">One toggle — auto-tunes all internal protection layers.</p>
                    </div>
                    <input data-testid="bp-form-antidetect"
                      type="checkbox"
                      checked={form.anti_detect.master}
                      onChange={(e) => setForm({ ...form, anti_detect: {
                        ...form.anti_detect, master: e.target.checked,
                        tls_prewarm: e.target.checked,
                        behavioral_bio: e.target.checked,
                        browser_variant: e.target.checked ? "rotate" : "auto",
                        identity_persist: e.target.checked,
                      }})}
                      className="w-5 h-5 rounded accent-fuchsia-500" />
                  </label>
                </div>

                {/* Proxy */}
                <div className="p-3 rounded-lg border border-cyan-500/30 bg-cyan-950/10">
                  <label className="flex items-center justify-between cursor-pointer mb-2">
                    <span className="text-cyan-300 text-sm font-semibold">🌍 Proxy</span>
                    <input data-testid="bp-form-proxy-enable"
                      type="checkbox"
                      checked={form.proxy.enabled}
                      onChange={(e) => setForm({ ...form, proxy: { ...form.proxy, enabled: e.target.checked } })}
                      className="w-4 h-4 rounded accent-cyan-500" />
                  </label>
                  {form.proxy.enabled && (
                    <div className="space-y-2">
                      <label className="flex items-center gap-2 text-xs text-zinc-300">
                        <input type="checkbox" checked={form.proxy.use_proxyjet}
                          onChange={(e) => setForm({ ...form, proxy: { ...form.proxy, use_proxyjet: e.target.checked } })}
                          className="w-4 h-4 rounded accent-cyan-500" />
                        Use ProxyJet Auto (unique sticky session per profile)
                      </label>
                      {!form.proxy.use_proxyjet && (
                        <div className="grid grid-cols-2 gap-2">
                          <Input placeholder="http://host:port" value={form.proxy.server}
                            onChange={(e) => setForm({ ...form, proxy: { ...form.proxy, server: e.target.value } })}
                            className="bg-zinc-900 border-zinc-700 text-zinc-100 text-xs" />
                          <div />
                          <Input placeholder="username" value={form.proxy.username}
                            onChange={(e) => setForm({ ...form, proxy: { ...form.proxy, username: e.target.value } })}
                            className="bg-zinc-900 border-zinc-700 text-zinc-100 text-xs" />
                          <Input placeholder="password" type="password" value={form.proxy.password}
                            onChange={(e) => setForm({ ...form, proxy: { ...form.proxy, password: e.target.value } })}
                            className="bg-zinc-900 border-zinc-700 text-zinc-100 text-xs" />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
              <div className="p-4 border-t border-zinc-800 flex justify-end gap-2 sticky bottom-0 bg-zinc-950">
                <Button onClick={() => { setShowCreate(false); setEditingId(null); }} variant="outline" className="border-zinc-700 text-zinc-300">Cancel</Button>
                <Button data-testid="bp-form-save" onClick={handleCreate} className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white">
                  {editingId ? "Save Changes" : "Create Profile"}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
