import { useEffect, useState } from "react";
import axios from "axios";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Label } from "./ui/label";
import { Server, ExternalLink } from "lucide-react";
import { Link } from "react-router-dom";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * Reusable dropdown that lets the customer pick which Proxy Provider
 * (from settings) to use for the current action. Empty selection ⇒
 * caller uses its existing default proxy flow (100% backward compat).
 *
 * Props
 * ─────
 *   value              currently selected provider id (string) or ""
 *   onChange(id)       fires with the new id (or "" for default)
 *   label              optional label above the select (default "Proxy source")
 *   labelDefault       optional text for the "default" option
 *   className          extra classes for the wrapper
 *   testIdPrefix       prefix for data-testids (default "proxy-provider-select")
 */
export default function ProxyProviderSelect({
  value = "",
  onChange = () => {},
  label = "Proxy source",
  labelDefault = "(default — existing proxy flow)",
  className = "",
  testIdPrefix = "proxy-provider-select",
}) {
  const [providers, setProviders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const token = localStorage.getItem("token");
    axios
      .get(`${API}/proxy-providers`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then((r) => { if (mounted) setProviders((r.data || []).filter((p) => p.enabled)); })
      .catch(() => {})
      .finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, []);

  return (
    <div className={className}>
      {label && (
        <div className="flex items-center justify-between mb-1">
          <Label className="flex items-center gap-1 text-sm">
            <Server size={12} /> {label}
          </Label>
          <Link
            to="/settings"
            className="text-[10px] text-[#60A5FA] hover:underline flex items-center gap-1"
            title="Manage proxy providers"
          >
            manage <ExternalLink size={10} />
          </Link>
        </div>
      )}
      <Select value={value || "__default__"} onValueChange={(v) => onChange(v === "__default__" ? "" : v)}>
        <SelectTrigger data-testid={`${testIdPrefix}-trigger`}>
          <SelectValue placeholder={loading ? "Loading…" : labelDefault} />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__default__" data-testid={`${testIdPrefix}-default`}>{labelDefault}</SelectItem>
          {providers.map((p) => (
            <SelectItem key={p.id} value={p.id} data-testid={`${testIdPrefix}-item-${p.id}`}>
              {p.name} · {p.kind.replace("_", " ")}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {!loading && providers.length === 0 && (
        <p className="text-[10px] text-[var(--brand-muted)] mt-1">
          No providers yet — <Link to="/settings" className="text-[#60A5FA] hover:underline">add one in Settings › Proxy Providers</Link>.
        </p>
      )}
    </div>
  );
}
