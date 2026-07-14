import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { toast } from "sonner";
import { Server, Zap, Copy, Settings2, ExternalLink, Loader2, Download } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Countries + US states shortlists — used only for provider kinds that
// support geo params (native_proxyjet). For other kinds the geo fields
// are hidden automatically.
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
const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
  "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
  "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
  "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
  "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
];

const PROXY_TYPES = [
  { value: "http",     label: "HTTP" },
  { value: "https",    label: "HTTPS" },
  { value: "socks5",   label: "SOCKS5" },
  { value: "socks5h",  label: "SOCKS5H (remote DNS)" },
  { value: "socks4",   label: "SOCKS4" },
];

/**
 * "My Proxy Providers" — provider-agnostic on-demand proxy generator.
 *
 *   • Dropdown of every enabled provider the customer added under
 *     Settings › Proxy Providers.
 *   • Batch generator (count / format / country / state / session mode)
 *     that works for ALL provider kinds — no ProxyJet-specific setup
 *     required. Whichever provider the customer picked here is used.
 *   • Output textarea with Copy / Download.
 *
 * Backward compat: If the customer has zero providers, the card just
 * links them to Settings and the legacy ProxyJet flow below remains
 * the source of truth.
 */
export default function MyProxyProvidersCard() {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState("");

  // Batch generator state
  const [count, setCount] = useState(10);
  const [proxyType, setProxyType] = useState("http");
  const [country, setCountry] = useState("US");
  const [state, setState] = useState("");
  const [sessionMode, setSessionMode] = useState("rotating"); // rotating | sticky
  const [stickyMinutes, setStickyMinutes] = useState(10);
  const [generating, setGenerating] = useState(false);
  const [output, setOutput] = useState("");

  const authHeaders = () => {
    const token = localStorage.getItem("token");
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/proxy-providers`, { headers: authHeaders() });
      const enabled = (r.data || []).filter((p) => p.enabled);
      setProviders(enabled);
      if (enabled.length > 0 && !selectedId) {
        setSelectedId(enabled[0].id);
        setProxyType(enabled[0].proxy_type || "http");
      }
    } catch (e) {
      // silent — user might not have providers yet
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const selected = providers.find((p) => p.id === selectedId);
  // v2.6.2 — native_proxyjet kind removed. If a legacy provider still
  // exists with this kind (from before the change), keep the geo/
  // sticky UI functional so nothing breaks.
  const supportsGeo = selected?.kind === "native_proxyjet";
  const supportsSticky = selected?.kind === "native_proxyjet";

  // Auto-sync proxy type when provider changes (only if user hasn't
  // explicitly overridden — keep it simple: always match provider's
  // native type on provider change).
  useEffect(() => {
    if (selected?.proxy_type) setProxyType(selected.proxy_type);
  }, [selectedId, selected]);

  const kindLabel = (k) => (k || "").replace(/_/g, " ");

  const generateBatch = async () => {
    if (!selectedId) {
      toast.error("Pick a provider first");
      return;
    }
    const n = Math.max(1, Math.min(parseInt(count, 10) || 10, 5000));
    setGenerating(true);
    setOutput("");
    try {
      const r = await axios.post(
        `${API}/proxy-providers/${selectedId}/generate-batch`,
        {
          count: n,
          country: supportsGeo ? (country || "").trim().toUpperCase() : null,
          state: supportsGeo ? (state || "").trim().toUpperCase() : null,
          sticky_minutes: supportsSticky && sessionMode === "sticky"
            ? Math.max(1, Math.min(parseInt(stickyMinutes, 10) || 10, 120))
            : null,
          proxy_type: proxyType,
        },
        { headers: authHeaders() }
      );
      const lines = (r.data?.proxies || []).join("\n");
      setOutput(lines);
      toast.success(`Generated ${r.data?.count || 0} proxies from ${selected?.name || "provider"}`);
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
    const fname = `${(selected?.name || "provider").replace(/[^a-z0-9_-]/gi, "_")}-${proxyType}-${output.split("\n").length}.txt`;
    a.download = fname;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="bg-gradient-to-br from-blue-950/30 to-indigo-950/30 border-blue-500/30" data-testid="my-proxy-providers-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-blue-200">
              <Server size={18} className="text-blue-400" /> My Proxy Providers
              {providers.length > 0 && (
                <Badge variant="secondary" className="bg-blue-500/20 text-blue-200 border-blue-500/30 ml-2">
                  {providers.length} active
                </Badge>
              )}
            </CardTitle>
            <CardDescription className="mt-1 text-zinc-400">
              Pick any provider you added in Settings and pull proxies on-demand in whichever format
              you need (HTTP / SOCKS5 / etc). The same provider is used automatically by RUT,
              Browser Profiles, and CPI — no per-page setup required.
            </CardDescription>
          </div>
          <Link
            to="/settings"
            className="text-xs text-blue-300 hover:text-blue-200 flex items-center gap-1 shrink-0"
            data-testid="my-proxy-providers-manage-link"
          >
            <Settings2 size={14} /> Manage <ExternalLink size={12} />
          </Link>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="text-sm text-zinc-500 italic">Loading providers…</div>
        ) : providers.length === 0 ? (
          <div className="text-sm text-zinc-400 italic py-2">
            You haven&apos;t added any proxy providers yet.
            <Link to="/settings" className="text-blue-300 hover:underline ml-1">
              Add one in Settings › Proxy Providers
            </Link>
            &nbsp;— then generate proxies here or use the dropdown on RUT / Browser Profiles / CPI.
          </div>
        ) : (
          <>
            {/* Provider picker */}
            <div>
              <Label className="text-xs text-blue-200 uppercase tracking-wider mb-1 block">Provider</Label>
              <Select value={selectedId} onValueChange={setSelectedId}>
                <SelectTrigger data-testid="my-proxy-providers-select" className="bg-zinc-900/50">
                  <SelectValue placeholder="Pick a provider" />
                </SelectTrigger>
                <SelectContent>
                  {providers.map((p) => (
                    <SelectItem key={p.id} value={p.id} data-testid={`my-proxy-providers-option-${p.id}`}>
                      {p.name} · {kindLabel(p.kind)} · {(p.proxy_type || "").toUpperCase()}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {selected && (
                <p className="text-[10px] text-zinc-500 mt-1">
                  Selected: <span className="text-blue-300 font-medium">{selected.name}</span>{" · "}
                  <span className="text-zinc-400">{kindLabel(selected.kind)}</span>{" · "}
                  <span className="uppercase text-blue-300">{selected.proxy_type}</span>
                </p>
              )}
            </div>

            {/* Batch generator */}
            <div className="pt-3 mt-1 border-t border-blue-500/20 space-y-3">
              <div className="flex items-center gap-2">
                <Zap size={14} className="text-amber-300" />
                <h4 className="text-sm font-semibold text-white">Generate proxies on-demand</h4>
              </div>
              <p className="text-[11px] text-zinc-400 leading-relaxed">
                Pick how many / format / geo (when supported) and grab a batch of proxy strings
                you can paste anywhere. All formats are supported —
                <b className="text-blue-300"> HTTP, HTTPS, SOCKS5, SOCKS5H, SOCKS4</b>.
              </p>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <div>
                  <Label className="text-xs text-zinc-300">How many</Label>
                  <Input
                    type="number"
                    min={1}
                    max={5000}
                    value={count}
                    onChange={(e) => setCount(e.target.value)}
                    className="bg-zinc-900/60 border-zinc-700 text-white"
                    data-testid="mpp-gen-count"
                  />
                </div>
                <div>
                  <Label className="text-xs text-zinc-300">Format</Label>
                  <select
                    value={proxyType}
                    onChange={(e) => setProxyType(e.target.value)}
                    className="w-full h-10 px-2 rounded-md bg-zinc-900/60 border border-zinc-700 text-white text-sm"
                    data-testid="mpp-gen-format"
                  >
                    {PROXY_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                {supportsGeo && (
                  <>
                    <div>
                      <Label className="text-xs text-zinc-300">Country</Label>
                      <select
                        value={country}
                        onChange={(e) => {
                          setCountry(e.target.value);
                          if (e.target.value !== "US") setState("");
                        }}
                        className="w-full h-10 px-2 rounded-md bg-zinc-900/60 border border-zinc-700 text-white text-sm"
                        data-testid="mpp-gen-country"
                      >
                        {COUNTRIES.map((c) => (
                          <option key={c.code} value={c.code}>{c.code} — {c.label}</option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <Label className="text-xs text-zinc-300">
                        State {country !== "US" && <span className="text-zinc-500">(US only)</span>}
                      </Label>
                      <select
                        value={state}
                        onChange={(e) => setState(e.target.value)}
                        disabled={country !== "US"}
                        className="w-full h-10 px-2 rounded-md bg-zinc-900/60 border border-zinc-700 text-white text-sm disabled:opacity-50"
                        data-testid="mpp-gen-state"
                      >
                        <option value="">— Any state —</option>
                        {US_STATES.map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                  </>
                )}
                {supportsSticky && (
                  <div>
                    <Label className="text-xs text-zinc-300">Session type</Label>
                    <select
                      value={sessionMode}
                      onChange={(e) => setSessionMode(e.target.value)}
                      className="w-full h-10 px-2 rounded-md bg-zinc-900/60 border border-zinc-700 text-white text-sm"
                      data-testid="mpp-gen-session-mode"
                    >
                      <option value="rotating">Rotating (fresh IP / connect)</option>
                      <option value="sticky">Sticky (hold IP X minutes)</option>
                    </select>
                  </div>
                )}
              </div>

              {supportsSticky && sessionMode === "sticky" && (
                <div>
                  <Label className="text-xs text-zinc-300">Sticky duration (minutes, 1–120)</Label>
                  <Input
                    type="number"
                    min={1}
                    max={120}
                    value={stickyMinutes}
                    onChange={(e) => setStickyMinutes(e.target.value)}
                    className="bg-zinc-900/60 border-zinc-700 text-white md:w-1/3"
                    data-testid="mpp-gen-sticky-min"
                  />
                </div>
              )}

              <Button
                onClick={generateBatch}
                disabled={generating || !selectedId}
                className="bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="my-proxy-providers-generate-btn"
              >
                {generating
                  ? <><Loader2 className="animate-spin mr-2" size={14} />Generating…</>
                  : <><Zap size={14} className="mr-2" />Generate {count} {proxyType.toUpperCase()} {parseInt(count, 10) === 1 ? "proxy" : "proxies"}</>}
              </Button>

              {output && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <Label className="text-xs text-zinc-400">
                      <span className="text-blue-300 font-semibold">{output.split("\n").length}</span> proxies ready
                    </Label>
                    <div className="flex gap-2">
                      <Button
                        onClick={copyOutput}
                        variant="outline"
                        size="sm"
                        className="h-7 px-2 text-blue-300 border-blue-500/40 hover:bg-blue-500/10"
                        data-testid="my-proxy-providers-copy-btn"
                      >
                        <Copy size={12} className="mr-1" /> Copy
                      </Button>
                      <Button
                        onClick={downloadOutput}
                        variant="outline"
                        size="sm"
                        className="h-7 px-2 text-emerald-300 border-emerald-500/40 hover:bg-emerald-500/10"
                        data-testid="my-proxy-providers-download-btn"
                      >
                        <Download size={12} className="mr-1" /> Download .txt
                      </Button>
                    </div>
                  </div>
                  <textarea
                    value={output}
                    readOnly
                    className="w-full h-40 px-2 py-1 rounded-md bg-zinc-950/70 border border-zinc-700 text-white font-mono text-xs"
                    data-testid="my-proxy-providers-output"
                  />
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
