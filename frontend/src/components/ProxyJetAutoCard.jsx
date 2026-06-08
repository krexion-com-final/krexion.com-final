import { useEffect, useState } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Badge } from "./ui/badge";
import { toast } from "sonner";
import {
  Zap,
  Eye,
  EyeOff,
  Check,
  X,
  Loader2,
  RotateCcw,
  Globe,
  ShieldCheck,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// US state codes — appended via ProxyJet's `-st-{XX}` filter so the
// residential pool resolves to that state only.
const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
  "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
  "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
  "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
];

// Country list for the dropdown (ProxyJet supports many — keep the
// shortlist that matters most for traffic campaigns; user can paste a
// custom 2-letter code as well).
const COUNTRIES = [
  { code: "US", label: "United States" },
  { code: "CA", label: "Canada" },
  { code: "GB", label: "United Kingdom" },
  { code: "DE", label: "Germany" },
  { code: "FR", label: "France" },
  { code: "AU", label: "Australia" },
  { code: "BR", label: "Brazil" },
  { code: "IN", label: "India" },
  { code: "JP", label: "Japan" },
  { code: "IT", label: "Italy" },
  { code: "ES", label: "Spain" },
  { code: "NL", label: "Netherlands" },
  { code: "MX", label: "Mexico" },
];

/**
 * ProxyJetAutoCard — UI for the one-time ProxyJet credential setup +
 * usage stats + test-connection button. Drop this anywhere; it manages
 * its own state and talks directly to /api/proxyjet/*.
 */
export default function ProxyJetAutoCard() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [showPwd, setShowPwd] = useState(false);
  const [configured, setConfigured] = useState(false);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("proxy-jet.io");
  const [port, setPort] = useState(1010);
  const [gateway, setGateway] = useState("ca");
  const [defaultCountry, setDefaultCountry] = useState("US");
  const [defaultState, setDefaultState] = useState("");
  const [product, setProduct] = useState("resi");

  const [lastTest, setLastTest] = useState(null); // { ok, exit_ip, round_trip_ms }
  const [usage, setUsage] = useState({ total_sessions_used: 0, last_24h: 0 });

  const token = () => localStorage.getItem("token");
  const auth = () => ({ headers: { Authorization: `Bearer ${token()}` } });

  const fetchCreds = async () => {
    try {
      const r = await axios.get(`${API}/proxyjet/credentials`, auth());
      if (r.data.configured) {
        setConfigured(true);
        setUsername(r.data.username || "");
        setPassword(""); // never pre-fill the actual password
        setServer(r.data.server || "proxy-jet.io");
        setPort(r.data.port || 1010);
        setGateway(r.data.gateway || "ca");
        setDefaultCountry(r.data.default_country || "US");
        setDefaultState(r.data.default_state || "");
        setProduct(r.data.product || "resi");
      } else {
        setConfigured(false);
      }
    } catch (e) {
      // Silent — endpoint may not exist on older backend, this card just hides
      setConfigured(false);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsage = async () => {
    try {
      const r = await axios.get(`${API}/proxyjet/usage`, auth());
      setUsage(r.data || { total_sessions_used: 0, last_24h: 0 });
    } catch (e) {
      // silent
    }
  };

  useEffect(() => {
    fetchCreds();
    fetchUsage();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const saveCreds = async () => {
    if (!username.trim() || !password.trim()) {
      toast.error("Username & password are required");
      return;
    }
    setSaving(true);
    try {
      await axios.post(
        `${API}/proxyjet/credentials`,
        {
          username: username.trim(),
          password: password.trim(),
          server: server.trim(),
          port: Number(port) || 1010,
          gateway: gateway.trim(),
          default_country: defaultCountry.trim().toUpperCase(),
          default_state: defaultState.trim().toUpperCase() || null,
          product: product.trim(),
        },
        auth()
      );
      toast.success("ProxyJet credentials saved");
      setConfigured(true);
      setPassword(""); // clear from state, masked on server now
      fetchUsage();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const deleteCreds = async () => {
    if (!window.confirm("Remove your saved ProxyJet credentials? (Used-session history is kept.)")) return;
    try {
      await axios.delete(`${API}/proxyjet/credentials`, auth());
      toast.success("ProxyJet credentials removed");
      setConfigured(false);
      setUsername("");
      setPassword("");
      setLastTest(null);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  const testConnection = async () => {
    setTesting(true);
    setLastTest(null);
    try {
      const r = await axios.post(`${API}/proxyjet/test`, {}, auth());
      setLastTest(r.data);
      if (r.data.ok) {
        toast.success(`✓ Exit IP: ${r.data.exit_ip} (${r.data.round_trip_ms}ms)`);
      } else {
        toast.error(`Test failed: ${r.data.error}`);
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Test failed");
    } finally {
      setTesting(false);
    }
  };

  const resetHistory = async () => {
    if (!window.confirm(
      "Reset the used-session history?\n\nThis lets previously-burned session IDs be picked again. " +
      "ONLY do this when you've rotated to a fresh ProxyJet pool. " +
      "Your credentials stay saved."
    )) return;
    try {
      const r = await axios.post(`${API}/proxyjet/reset-history`, {}, auth());
      toast.success(`Cleared ${r.data.deleted} session records`);
      fetchUsage();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Reset failed");
    }
  };

  if (loading) {
    return (
      <Card className="bg-[var(--brand-card)] border-[var(--brand-border)]" data-testid="proxyjet-card-loading">
        <CardContent className="py-6 text-center text-[#A1A1AA]">
          <Loader2 className="animate-spin inline mr-2" size={16} />
          Loading ProxyJet…
        </CardContent>
      </Card>
    );
  }

  return (
    <Card
      className="bg-gradient-to-br from-[#1e1b4b]/30 via-[var(--brand-card)] to-[var(--brand-card)] border border-indigo-500/30"
      data-testid="proxyjet-auto-card"
    >
      <CardHeader>
        <CardTitle className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-indigo-500/20">
              <Zap size={18} className="text-indigo-300" />
            </div>
            <span className="text-white">ProxyJet Auto Mode</span>
            {configured ? (
              <Badge className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
                <Check size={11} className="mr-1" /> configured
              </Badge>
            ) : (
              <Badge className="bg-amber-500/20 text-amber-300 border border-amber-500/40">
                not configured
              </Badge>
            )}
          </div>
          <div className="text-xs text-[#A1A1AA]">
            <ShieldCheck size={12} className="inline mr-1 text-emerald-400" />
            Every visit gets a unique unused IP
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-[#A1A1AA] leading-relaxed">
          Save your ProxyJet residential credentials <b>one time</b>. The Real-User-Traffic engine
          will then auto-generate a fresh <code className="text-indigo-300">session-ID</code> per
          visit and ProxyJet hands back a different residential exit-IP every time. We remember
          every session-ID this account has ever used so the <b>same exit-IP is never
          reused</b> on your offer URL — guaranteed unique clicks.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <Label className="text-xs text-[#A1A1AA]">Proxy Server</Label>
            <Input
              data-testid="pj-server"
              value={server}
              onChange={(e) => setServer(e.target.value)}
              placeholder="proxy-jet.io"
              className="bg-[var(--brand-bg)] border-[var(--brand-border)] text-white"
            />
          </div>
          <div>
            <Label className="text-xs text-[#A1A1AA]">Port</Label>
            <Input
              data-testid="pj-port"
              type="number"
              value={port}
              onChange={(e) => setPort(e.target.value)}
              placeholder="1010"
              className="bg-[var(--brand-bg)] border-[var(--brand-border)] text-white"
            />
          </div>
          <div>
            <Label className="text-xs text-[#A1A1AA]">Username</Label>
            <Input
              data-testid="pj-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="260202i9bQO"
              className="bg-[var(--brand-bg)] border-[var(--brand-border)] text-white font-mono"
            />
          </div>
          <div>
            <Label className="text-xs text-[#A1A1AA]">
              Password {configured && !password && <span className="text-emerald-400">(saved — leave blank to keep)</span>}
            </Label>
            <div className="relative">
              <Input
                data-testid="pj-password"
                type={showPwd ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={configured ? "•••••••• (saved)" : "eeTIJJ6Ot7gzPYG"}
                className="bg-[var(--brand-bg)] border-[var(--brand-border)] text-white font-mono pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-[#A1A1AA] hover:text-white"
                data-testid="pj-toggle-pwd"
              >
                {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
          <div>
            <Label className="text-xs text-[#A1A1AA]">Gateway sub-domain</Label>
            <Input
              data-testid="pj-gateway"
              value={gateway}
              onChange={(e) => setGateway(e.target.value)}
              placeholder="ca"
              className="bg-[var(--brand-bg)] border-[var(--brand-border)] text-white"
            />
            <p className="text-[10px] text-[#71717a] mt-1">e.g. <code>ca</code> → <code>ca.proxy-jet.io</code></p>
          </div>
          <div>
            <Label className="text-xs text-[#A1A1AA]">Default Country</Label>
            <select
              data-testid="pj-country"
              value={defaultCountry}
              onChange={(e) => {
                setDefaultCountry(e.target.value);
                if (e.target.value !== "US") setDefaultState("");
              }}
              className="w-full h-9 rounded-md bg-[var(--brand-bg)] border border-[var(--brand-border)] text-white px-2 text-sm"
            >
              {COUNTRIES.map((c) => (
                <option key={c.code} value={c.code}>{c.code} — {c.label}</option>
              ))}
            </select>
          </div>
          {defaultCountry === "US" && (
            <div>
              <Label className="text-xs text-[#A1A1AA]">
                Default State <span className="text-[10px] text-[#71717a]">(optional)</span>
              </Label>
              <select
                data-testid="pj-state"
                value={defaultState}
                onChange={(e) => setDefaultState(e.target.value)}
                className="w-full h-9 rounded-md bg-[var(--brand-bg)] border border-[var(--brand-border)] text-white px-2 text-sm"
              >
                <option value="">— Any state —</option>
                {US_STATES.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <p className="text-[10px] text-[#71717a] mt-1">
                Restrict exit IPs to a specific US state for geo-targeted offers.
              </p>
            </div>
          )}
        </div>

        <div className="flex flex-wrap gap-2 pt-1">
          <Button
            onClick={saveCreds}
            disabled={saving}
            data-testid="pj-save-btn"
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
          >
            {saving ? <Loader2 className="animate-spin mr-2" size={14} /> : <Check size={14} className="mr-2" />}
            {configured ? "Update Credentials" : "Save Credentials"}
          </Button>
          {configured && (
            <>
              <Button
                onClick={testConnection}
                disabled={testing}
                variant="outline"
                data-testid="pj-test-btn"
                className="border-indigo-500/40 text-indigo-300 hover:bg-indigo-500/10"
              >
                {testing ? <Loader2 className="animate-spin mr-2" size={14} /> : <Globe size={14} className="mr-2" />}
                Test Connection
              </Button>
              <Button
                onClick={resetHistory}
                variant="outline"
                data-testid="pj-reset-btn"
                className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10"
              >
                <RotateCcw size={14} className="mr-2" />
                Reset Used-IPs
              </Button>
              <Button
                onClick={deleteCreds}
                variant="outline"
                data-testid="pj-delete-btn"
                className="border-red-500/40 text-red-300 hover:bg-red-500/10 ml-auto"
              >
                <X size={14} className="mr-2" />
                Remove
              </Button>
            </>
          )}
        </div>

        {/* Test result */}
        {lastTest && (
          <div
            className={`text-xs rounded-md px-3 py-2 ${
              lastTest.ok
                ? "bg-emerald-500/10 border border-emerald-500/30 text-emerald-300"
                : "bg-red-500/10 border border-red-500/30 text-red-300"
            }`}
            data-testid="pj-test-result"
          >
            {lastTest.ok ? (
              <>
                <Check size={12} className="inline mr-1" />
                Exit IP <b className="font-mono">{lastTest.exit_ip}</b> via{" "}
                <span className="font-mono">{lastTest.gateway}</span> ·{" "}
                {lastTest.round_trip_ms}ms · session <span className="font-mono">{lastTest.session_id}</span>
              </>
            ) : (
              <>
                <X size={12} className="inline mr-1" />
                {lastTest.error}
              </>
            )}
          </div>
        )}

        {/* Usage stats */}
        {configured && (
          <div className="grid grid-cols-2 gap-3 pt-2 border-t border-[var(--brand-border)]/50">
            <div className="text-center">
              <p className="text-xl font-bold text-white" data-testid="pj-total-used">
                {usage.total_sessions_used?.toLocaleString?.() || 0}
              </p>
              <p className="text-[10px] text-[#A1A1AA] uppercase tracking-wide">Total Unique IPs Used</p>
            </div>
            <div className="text-center">
              <p className="text-xl font-bold text-indigo-300" data-testid="pj-24h-used">
                {usage.last_24h?.toLocaleString?.() || 0}
              </p>
              <p className="text-[10px] text-[#A1A1AA] uppercase tracking-wide">Last 24 hours</p>
            </div>
          </div>
        )}

        {/* 2026-06 — On-demand proxy generator. Lets the customer
            grab a fresh batch of unique exit-IPs without launching a
            RUT job (e.g. for pasting into AdsPower, an external scraper,
            or saving as an Uploaded-Things batch). Country/state default
            to the saved credential defaults but can be overridden per
            generation. Sticky/rotating toggle drives ProxyJet's
            sessTime parameter. */}
        {configured && (
          <ProxyJetGenerator
            defaultCountry={defaultCountry}
            defaultState={defaultState}
            onGenerated={() => fetchUsage()}
          />
        )}
      </CardContent>
    </Card>
  );
}

// ─── On-demand generator (one-shot batch download) ─────────────────
function ProxyJetGenerator({ defaultCountry, defaultState, onGenerated }) {
  const [gCount, setGCount] = useState(10);
  const [gCountry, setGCountry] = useState(defaultCountry || "US");
  const [gState, setGState] = useState(defaultState || "");
  // session_mode: "rotating" => sticky_minutes=null/0
  //               "sticky"   => sticky_minutes used as-typed
  const [sessionMode, setSessionMode] = useState("rotating");
  const [stickyMinutes, setStickyMinutes] = useState(10);
  const [generating, setGenerating] = useState(false);
  const [output, setOutput] = useState("");

  const generate = async () => {
    const n = Math.max(1, Math.min(parseInt(gCount, 10) || 1, 5000));
    setGenerating(true);
    setOutput("");
    try {
      const token = localStorage.getItem("token");
      const r = await axios.post(
        `${API}/proxyjet/generate-batch`,
        {
          count: n,
          country: (gCountry || "").trim().toUpperCase() || null,
          state: (gState || "").trim().toUpperCase() || null,
          sticky_minutes: sessionMode === "sticky"
            ? Math.max(1, Math.min(parseInt(stickyMinutes, 10) || 10, 120))
            : null,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      const lines = (r.data?.proxies || []).join("\n");
      setOutput(lines);
      toast.success(`Generated ${r.data?.count || 0} unique proxies`);
      if (onGenerated) await onGenerated();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const copyOutput = async () => {
    if (!output) return;
    try {
      await navigator.clipboard.writeText(output);
      toast.success("Copied to clipboard");
    } catch {
      toast.error("Copy failed — select & copy manually");
    }
  };

  const downloadOutput = () => {
    if (!output) return;
    const blob = new Blob([output + "\n"], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `proxyjet-${gCountry}${gState ? "-" + gState : ""}-${sessionMode}-${output.split("\n").length}.txt`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="pt-3 mt-3 border-t border-[var(--brand-border)]/50 space-y-3" data-testid="pj-generator">
      <div className="flex items-center gap-2">
        <Zap size={14} className="text-amber-300" />
        <h4 className="text-sm font-semibold text-white">Generate proxies on-demand</h4>
      </div>
      <p className="text-[11px] text-[#A1A1AA] leading-relaxed">
        Pick a country / state / session-type and grab a batch of unique exit-IPs you can paste anywhere.
        Every IP is recorded so the same one is never returned twice for this account.
      </p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <Label className="text-xs text-[#A1A1AA]">How many</Label>
          <Input
            type="number"
            min={1}
            max={5000}
            value={gCount}
            onChange={(e) => setGCount(e.target.value)}
            className="bg-zinc-900/60 border-[var(--brand-border)] text-white"
            data-testid="pj-gen-count"
          />
        </div>
        <div>
          <Label className="text-xs text-[#A1A1AA]">Country</Label>
          <select
            value={gCountry}
            onChange={(e) => setGCountry(e.target.value)}
            className="w-full h-10 px-2 rounded-md bg-zinc-900/60 border border-[var(--brand-border)] text-white text-sm"
            data-testid="pj-gen-country"
          >
            {COUNTRIES.map((c) => (
              <option key={c.code} value={c.code}>{c.code} — {c.label}</option>
            ))}
          </select>
        </div>
        <div>
          <Label className="text-xs text-[#A1A1AA]">State {gCountry !== "US" && <span className="text-zinc-500">(US only)</span>}</Label>
          <select
            value={gState}
            onChange={(e) => setGState(e.target.value)}
            disabled={gCountry !== "US"}
            className="w-full h-10 px-2 rounded-md bg-zinc-900/60 border border-[var(--brand-border)] text-white text-sm disabled:opacity-50"
            data-testid="pj-gen-state"
          >
            <option value="">— Any state —</option>
            {US_STATES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
        <div>
          <Label className="text-xs text-[#A1A1AA]">Session type</Label>
          <select
            value={sessionMode}
            onChange={(e) => setSessionMode(e.target.value)}
            className="w-full h-10 px-2 rounded-md bg-zinc-900/60 border border-[var(--brand-border)] text-white text-sm"
            data-testid="pj-gen-session-mode"
          >
            <option value="rotating">Rotating (fresh IP / connect)</option>
            <option value="sticky">Sticky (hold IP X minutes)</option>
          </select>
        </div>
      </div>

      {sessionMode === "sticky" && (
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label className="text-xs text-[#A1A1AA]">Sticky duration (minutes, 1–120)</Label>
            <Input
              type="number"
              min={1}
              max={120}
              value={stickyMinutes}
              onChange={(e) => setStickyMinutes(e.target.value)}
              className="bg-zinc-900/60 border-[var(--brand-border)] text-white"
              data-testid="pj-gen-sticky-min"
            />
          </div>
          <div className="text-[11px] text-[#A1A1AA] flex items-end pb-2">
            Same exit-IP is held for this many minutes per session — required for multi-page funnel flows.
          </div>
        </div>
      )}

      <Button
        onClick={generate}
        disabled={generating}
        data-testid="pj-gen-btn"
        className="bg-amber-600 hover:bg-amber-700 text-white"
      >
        {generating
          ? <><Loader2 className="animate-spin mr-2" size={14} />Generating…</>
          : <><Zap size={14} className="mr-2" />Generate {gCount} proxies</>}
      </Button>

      {output && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs text-[#A1A1AA]">
              {output.split("\n").length} proxies ready
            </Label>
            <div className="flex gap-2">
              <Button
                onClick={copyOutput}
                variant="outline"
                size="sm"
                className="h-7 px-2 text-indigo-300 border-indigo-500/40 hover:bg-indigo-500/10"
                data-testid="pj-gen-copy"
              >Copy</Button>
              <Button
                onClick={downloadOutput}
                variant="outline"
                size="sm"
                className="h-7 px-2 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/10"
                data-testid="pj-gen-download"
              >Download .txt</Button>
            </div>
          </div>
          <textarea
            value={output}
            readOnly
            className="w-full h-40 px-2 py-1 rounded-md bg-zinc-950/70 border border-[var(--brand-border)] text-white font-mono text-xs"
            data-testid="pj-gen-output"
          />
        </div>
      )}
    </div>
  );
}
