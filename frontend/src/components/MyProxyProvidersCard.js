import { useEffect, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { toast } from "sonner";
import { Server, Zap, Copy, Settings2, ExternalLink } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * "My Proxy Providers" card — mirrors ProxyJetAutoCard on the Proxies
 * page but shows a DROPDOWN of every provider the customer added under
 * Settings › Proxy Providers, plus a Generate button that pulls one
 * fresh proxy from the selected provider (via /api/proxy-providers/
 * {id}/test).
 *
 * 100% opt-in — if the customer has no providers, this card just links
 * them to Settings and the ProxyJet card / manual paste flow below
 * remain the only source of truth (backward compat).
 */
export default function MyProxyProvidersCard() {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState("");
  const [generating, setGenerating] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const r = await axios.get(`${API}/proxy-providers`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      const enabled = (r.data || []).filter((p) => p.enabled);
      setProviders(enabled);
      if (enabled.length > 0 && !selectedId) setSelectedId(enabled[0].id);
    } catch (e) {
      // silent — user might not have providers yet
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const generate = async () => {
    if (!selectedId) {
      toast.error("Pick a provider first");
      return;
    }
    setGenerating(true);
    setLastResult(null);
    try {
      const token = localStorage.getItem("token");
      const r = await axios.post(
        `${API}/proxy-providers/${selectedId}/test`,
        {},
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      );
      if (r.data.ok) {
        setLastResult(r.data.sample);
        toast.success("Fresh proxy generated");
      } else {
        toast.error(`Failed: ${r.data.error || "unknown"}`);
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Generate failed");
    } finally {
      setGenerating(false);
    }
  };

  const copyResult = () => {
    if (!lastResult) return;
    const line = lastResult.proxy || (lastResult.use_proxyjet ? `[Native ProxyJet · ${lastResult.country}${lastResult.state ? "-" + lastResult.state : ""}]` : "");
    if (!line) return;
    navigator.clipboard.writeText(line);
    toast.success("Copied");
  };

  const selected = providers.find((p) => p.id === selectedId);
  const kindLabel = (k) => (k || "").replace(/_/g, " ");

  return (
    <Card className="bg-gradient-to-br from-blue-950/30 to-indigo-950/30 border-blue-500/30" data-testid="my-proxy-providers-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-blue-200">
              <Server size={18} className="text-blue-400" /> My Proxy Providers
              {providers.length > 0 && <Badge variant="secondary" className="bg-blue-500/20 text-blue-200 border-blue-500/30 ml-2">{providers.length} active</Badge>}
            </CardTitle>
            <CardDescription className="mt-1 text-zinc-400">
              Pick any provider you added in Settings and pull a fresh proxy on demand. Every page that
              uses proxies (RUT, Browser Profiles, CPI) shows the same dropdown, so you never need to
              paste creds again.
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
      <CardContent>
        {loading ? (
          <div className="text-sm text-zinc-500 italic">Loading providers…</div>
        ) : providers.length === 0 ? (
          <div className="text-sm text-zinc-400 italic py-2">
            You haven&apos;t added any proxy providers yet.
            <Link to="/settings" className="text-blue-300 hover:underline ml-1">
              Add one in Settings › Proxy Providers
            </Link>
            &nbsp;— then generate proxies here or pick them from the dropdown on RUT / Browser Profiles / CPI.
          </div>
        ) : (
          <>
            <div className="flex flex-col md:flex-row gap-3">
              <div className="flex-1">
                <Select value={selectedId} onValueChange={setSelectedId}>
                  <SelectTrigger data-testid="my-proxy-providers-select">
                    <SelectValue placeholder="Pick a provider" />
                  </SelectTrigger>
                  <SelectContent>
                    {providers.map((p) => (
                      <SelectItem key={p.id} value={p.id} data-testid={`my-proxy-providers-option-${p.id}`}>
                        {p.name} &middot; {kindLabel(p.kind)} &middot; {p.proxy_type.toUpperCase()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button
                onClick={generate}
                disabled={generating || !selectedId}
                className="bg-blue-500 hover:bg-blue-600 text-white"
                data-testid="my-proxy-providers-generate-btn"
              >
                <Zap size={14} className="mr-1" />
                {generating ? "Generating…" : "Generate proxy"}
              </Button>
            </div>

            {selected && (
              <div className="mt-3 text-xs text-zinc-400">
                <span className="text-zinc-500">Selected:</span>{" "}
                <span className="text-blue-200 font-medium">{selected.name}</span>{" "}
                <span className="text-zinc-500">·</span>{" "}
                <span className="uppercase text-blue-300">{selected.proxy_type}</span>{" "}
                <span className="text-zinc-500">·</span>{" "}
                <span className="text-zinc-400">{kindLabel(selected.kind)}</span>
              </div>
            )}

            {lastResult && (
              <div className="mt-3 p-3 rounded-md border border-blue-500/30 bg-blue-950/40" data-testid="my-proxy-providers-result">
                <div className="text-[10px] text-blue-300 uppercase tracking-wider mb-1">Last generated</div>
                <div className="flex items-center justify-between gap-2">
                  <code className="text-xs text-blue-100 font-mono break-all">
                    {lastResult.proxy || (lastResult.use_proxyjet
                      ? `Native ProxyJet · ${lastResult.country}${lastResult.state ? "-" + lastResult.state : ""}`
                      : "—")}
                  </code>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={copyResult}
                    title="Copy"
                    data-testid="my-proxy-providers-copy-btn"
                  >
                    <Copy size={14} />
                  </Button>
                </div>
                <div className="mt-1 text-[10px] text-zinc-500">
                  This same provider is also available as a dropdown option on RUT, Browser Profiles, and CPI.
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
