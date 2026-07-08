import { useEffect, useState } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { toast } from "sonner";
import { Plus, Trash2, Play, Edit2, Server } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function ProxyProvidersTab() {
  const [providers, setProviders] = useState([]);
  const [kinds, setKinds] = useState([]);
  const [proxyTypes, setProxyTypes] = useState(["http", "https", "socks5", "socks5h", "socks4"]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({});

  const load = async () => {
    setLoading(true);
    try {
      const [p, m] = await Promise.all([
        axios.get(`${API}/proxy-providers`, { headers: authHeaders() }),
        axios.get(`${API}/proxy-providers/_meta/kinds`, { headers: authHeaders() }),
      ]);
      setProviders(p.data || []);
      setKinds(m.data.kinds || []);
      setProxyTypes(m.data.proxy_types || proxyTypes);
    } catch (e) {
      toast.error("Failed to load proxy providers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing({ isNew: true });
    setForm({
      name: "",
      kind: "rotating_gateway",
      proxy_type: "http",
      enabled: true,
      config: {},
    });
    setDialogOpen(true);
  };

  const openEdit = (p) => {
    setEditing({ isNew: false, ...p });
    setForm({ ...p });
    setDialogOpen(true);
  };

  const save = async () => {
    if (!form.name || !form.kind) {
      toast.error("Name and Kind are required");
      return;
    }
    try {
      if (editing.isNew) {
        await axios.post(`${API}/proxy-providers`, form, { headers: authHeaders() });
        toast.success("Provider added");
      } else {
        const patch = {
          name: form.name,
          kind: form.kind,
          proxy_type: form.proxy_type,
          enabled: form.enabled,
          config: form.config || {},
        };
        await axios.put(`${API}/proxy-providers/${editing.id}`, patch, { headers: authHeaders() });
        toast.success("Provider updated");
      }
      setDialogOpen(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this provider?")) return;
    try {
      await axios.delete(`${API}/proxy-providers/${id}`, { headers: authHeaders() });
      toast.success("Deleted");
      load();
    } catch { toast.error("Delete failed"); }
  };

  const test = async (p) => {
    try {
      const res = await axios.post(`${API}/proxy-providers/${p.id}/test`, {}, { headers: authHeaders() });
      if (res.data.ok) {
        const s = res.data.sample || {};
        toast.success(`Test OK — ${s.use_proxyjet ? "ProxyJet " + (s.country || "") : (s.proxy ? s.proxy.slice(0, 40) + "…" : "resolved")}`);
      } else {
        toast.error(`Test failed: ${res.data.error || "unknown"}`);
      }
    } catch { toast.error("Test failed"); }
  };

  const toggleEnabled = async (p) => {
    try {
      await axios.put(`${API}/proxy-providers/${p.id}`, { enabled: !p.enabled }, { headers: authHeaders() });
      load();
    } catch { toast.error("Failed"); }
  };

  const currentKind = kinds.find((k) => k.key === (form.kind || "rotating_gateway")) || kinds[0];
  const kindLabel = (k) => kinds.find((x) => x.key === k)?.label || k;

  const summarizeConfig = (p) => {
    const c = p.config || {};
    switch (p.kind) {
      case "rotating_gateway":
        return `${c.gateway_host || "?"}:${c.gateway_port || "?"}`;
      case "api_endpoint":
        return c.api_url ? c.api_url.slice(0, 40) + (c.api_url.length > 40 ? "…" : "") : "no url";
      case "manual_list": {
        const lines = (c.lines || "").toString().split(/\r?\n/).filter(Boolean);
        return `${lines.length} lines`;
      }
      case "native_proxyjet":
        return `country: ${c.country || "US"}${c.state ? ", state: " + c.state : ""}`;
      default:
        return "";
    }
  };

  return (
    <div className="space-y-6" data-testid="proxy-providers-tab">
      <Card className="bg-[var(--brand-card)] border-[var(--brand-border)]">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Server size={20} /> Proxy Providers
              </CardTitle>
              <CardDescription className="mt-1">
                Add ANY proxy source &mdash; rotating gateways (Bright Data / Oxylabs / Soax / IPRoyal Gateway),
                REST-API endpoints (SmartProxy / Webshare / custom), manual lists, or Krexion&apos;s built-in
                ProxyJet with your country + state overrides. Any page that uses proxies (RUT, Browser
                Profiles, CPI, Proxy Test) will show a dropdown to pick which provider to use.
                When you have none, existing default flow runs unchanged.
              </CardDescription>
            </div>
            <Button size="sm" onClick={openNew} data-testid="proxy-provider-add-btn">
              <Plus size={14} className="mr-1" /> Add Provider
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {providers.length === 0 && (
            <div className="text-sm text-[var(--brand-muted)] italic py-4">
              No providers yet &mdash; click &quot;Add Provider&quot; to add your first one, or continue using Krexion&apos;s default proxy flow.
            </div>
          )}
          {providers.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow className="border-[var(--brand-border)] hover:bg-transparent">
                  <TableHead>Name</TableHead>
                  <TableHead>Kind</TableHead>
                  <TableHead>Proxy Type</TableHead>
                  <TableHead>Config</TableHead>
                  <TableHead>Enabled</TableHead>
                  <TableHead>Used</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {providers.map((p) => (
                  <TableRow key={p.id} className="border-[var(--brand-border)]" data-testid={`proxy-provider-row-${p.id}`}>
                    <TableCell className="font-medium">{p.name}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="bg-[#1E293B]">{kindLabel(p.kind)}</Badge>
                    </TableCell>
                    <TableCell className="font-mono text-xs uppercase">{p.proxy_type}</TableCell>
                    <TableCell className="text-xs text-[var(--brand-muted)]">{summarizeConfig(p)}</TableCell>
                    <TableCell>
                      <Switch checked={!!p.enabled} onCheckedChange={() => toggleEnabled(p)} data-testid={`proxy-provider-toggle-${p.id}`} />
                    </TableCell>
                    <TableCell className="text-xs">{p.use_count || 0}</TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button size="sm" variant="ghost" onClick={() => test(p)} title="Test" data-testid={`proxy-provider-test-${p.id}`}>
                        <Play size={14} />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => openEdit(p)} title="Edit" data-testid={`proxy-provider-edit-${p.id}`}>
                        <Edit2 size={14} />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => remove(p.id)} title="Delete" data-testid={`proxy-provider-delete-${p.id}`}>
                        <Trash2 size={14} className="text-red-400" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Add / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-[var(--brand-card)] border-[var(--brand-border)] max-w-2xl" data-testid="proxy-provider-dialog">
          <DialogHeader>
            <DialogTitle>{editing?.isNew ? "Add Proxy Provider" : "Update Provider"}</DialogTitle>
            <DialogDescription>
              Configure any proxy source Krexion should choose from. Options here appear as a dropdown
              on pages that use proxies (RUT, Browser Profiles, CPI, Proxy Test).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Name</Label>
                <Input value={form.name || ""} onChange={(e) => setForm({ ...form, name: e.target.value })}
                       placeholder="My New API Provider" data-testid="proxy-form-name" />
              </div>
              <div>
                <Label>Kind</Label>
                <Select value={form.kind || "rotating_gateway"}
                        onValueChange={(v) => setForm({ ...form, kind: v, config: {} })}>
                  <SelectTrigger data-testid="proxy-form-kind">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {kinds.map((k) => (
                      <SelectItem key={k.key} value={k.key}>{k.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Proxy Type</Label>
                <Select value={form.proxy_type || "http"}
                        onValueChange={(v) => setForm({ ...form, proxy_type: v })}>
                  <SelectTrigger data-testid="proxy-form-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {proxyTypes.map((t) => (
                      <SelectItem key={t} value={t}>{t.toUpperCase()}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end justify-between">
                <div>
                  <Label>Enabled</Label>
                  <div className="pt-2">
                    <Switch checked={!!form.enabled}
                            onCheckedChange={(v) => setForm({ ...form, enabled: v })}
                            data-testid="proxy-form-enabled" />
                  </div>
                </div>
              </div>
            </div>

            {currentKind && (
              <div className="text-xs text-[var(--brand-muted)] italic">
                {currentKind.description}
              </div>
            )}

            {currentKind && currentKind.fields.map((f) => {
              const val = (form.config && form.config[f.key]) || "";
              const set = (v) => setForm({ ...form, config: { ...(form.config || {}), [f.key]: v } });
              return (
                <div key={f.key}>
                  <Label>{f.label}</Label>
                  {f.type === "textarea" ? (
                    <Textarea rows={f.key === "lines" ? 6 : 3} value={val} onChange={(e) => set(e.target.value)}
                              placeholder={f.placeholder} data-testid={`proxy-form-cfg-${f.key}`} />
                  ) : f.type === "password" ? (
                    <Input type="password" value={val} onChange={(e) => set(e.target.value)}
                           placeholder={f.placeholder} data-testid={`proxy-form-cfg-${f.key}`} />
                  ) : (
                    <Input value={val} onChange={(e) => set(e.target.value)}
                           placeholder={f.placeholder} data-testid={`proxy-form-cfg-${f.key}`} />
                  )}
                </div>
              );
            })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={save} data-testid="proxy-form-save">
              {editing?.isNew ? "Add Provider" : "Update Provider"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
