import { useEffect, useState } from "react";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { toast } from "sonner";
import { Plus, Trash2, Play, Edit2, Shield, ExternalLink, ChevronDown, ChevronUp } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function authHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export default function FraudDetectionTab() {
  const [settings, setSettings] = useState({ personal_filter_enabled: false, fallback_to_defaults: true });
  const [services, setServices] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState({}); // { service: bool }
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState(null); // account being edited or {service, ...} for new
  const [form, setForm] = useState({});

  const load = async () => {
    setLoading(true);
    try {
      const [s, sv, ac] = await Promise.all([
        axios.get(`${API}/fraud/settings`, { headers: authHeaders() }),
        axios.get(`${API}/fraud/services`, { headers: authHeaders() }),
        axios.get(`${API}/fraud/accounts`, { headers: authHeaders() }),
      ]);
      setSettings(s.data);
      setServices(sv.data.services || []);
      setAccounts(ac.data || []);
      // Auto-expand services with accounts
      const exp = {};
      for (const a of ac.data || []) exp[a.service] = true;
      setExpanded(exp);
    } catch (e) {
      toast.error("Failed to load fraud settings");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const saveSettings = async (patch) => {
    const next = { ...settings, ...patch };
    setSettings(next);
    try {
      await axios.put(`${API}/fraud/settings`, next, { headers: authHeaders() });
      toast.success("Fraud settings saved");
    } catch (e) {
      toast.error("Failed to save settings");
      load();
    }
  };

  const openAdd = (svc) => {
    setEditing({ isNew: true, service: svc.key });
    setForm({
      service: svc.key,
      account_name: "",
      api_key: "",
      api_user: svc.needs_user ? "" : "",
      enabled: true,
      priority: 100,
      quota_daily: 0,
    });
    setDialogOpen(true);
  };

  const openEdit = (acc) => {
    setEditing({ isNew: false, ...acc });
    setForm({ ...acc });
    setDialogOpen(true);
  };

  const saveAccount = async () => {
    try {
      if (editing.isNew) {
        await axios.post(`${API}/fraud/accounts`, form, { headers: authHeaders() });
        toast.success("Account added");
      } else {
        const patch = {};
        for (const k of ["account_name", "api_key", "api_user", "enabled", "priority", "quota_daily", "endpoint"]) {
          if (form[k] !== undefined) patch[k] = form[k];
        }
        await axios.put(`${API}/fraud/accounts/${editing.id}`, patch, { headers: authHeaders() });
        toast.success("Account updated");
      }
      setDialogOpen(false);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    }
  };

  const deleteAccount = async (id) => {
    if (!window.confirm("Delete this account?")) return;
    try {
      await axios.delete(`${API}/fraud/accounts/${id}`, { headers: authHeaders() });
      toast.success("Deleted");
      load();
    } catch (e) {
      toast.error("Delete failed");
    }
  };

  const testAccount = async (acc) => {
    try {
      const res = await axios.post(`${API}/fraud/accounts/${acc.id}/test`, { ip: "1.1.1.1" }, { headers: authHeaders() });
      if (res.data.ok) {
        toast.success(`Account working ✓ (score ${res.data.result?.vpn_score ?? "?"})`);
      } else {
        toast.error(`Test failed: ${res.data.reason || "unknown"}`);
      }
    } catch (e) {
      toast.error("Test failed");
    }
  };

  const toggleEnable = async (acc) => {
    try {
      await axios.put(`${API}/fraud/accounts/${acc.id}`, { enabled: !acc.enabled }, { headers: authHeaders() });
      load();
    } catch { toast.error("Failed"); }
  };

  const accountsFor = (svcKey) => accounts.filter((a) => a.service === svcKey);

  return (
    <div className="space-y-6" data-testid="fraud-detection-tab">
      {/* Master Control */}
      <Card className="bg-[var(--brand-card)] border-[var(--brand-border)]">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Shield size={20} /> Fraud Detection — Master Control
              </CardTitle>
              <CardDescription className="mt-1">
                Filter incoming traffic on RUT, CPI, Bulk Test, Browser Profiles, and click flows.
                Master toggle is OFF by default &mdash; when OFF, Krexion falls back to its built-in defaults.
                Only your customer settings are used when ON.
              </CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between p-4 rounded-lg border border-[var(--brand-border)] bg-[#0F172A]">
            <div>
              <div className="font-medium">Enable my personal fraud filter</div>
              <p className="text-xs text-[var(--brand-muted)] mt-1">
                When ON, IP fraud checks use YOUR provider accounts below (auto-rotate on quota / rate limit).
                When OFF, Krexion&apos;s built-in defaults are used exactly as before.
              </p>
            </div>
            <Switch
              checked={!!settings.personal_filter_enabled}
              onCheckedChange={(v) => saveSettings({ personal_filter_enabled: v })}
              data-testid="fraud-master-toggle"
            />
          </div>

          <div className="flex items-center justify-between p-4 rounded-lg border border-[var(--brand-border)] bg-[#0F172A]">
            <div>
              <div className="font-medium">If my providers fail (rate-limited / down)</div>
              <p className="text-xs text-[var(--brand-muted)] mt-1">
                Automatically fall back to Krexion&apos;s built-in fraud APIs if all your enabled accounts fail.
                Recommended ON.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-[var(--brand-muted)]">Fallback to Krexion defaults</span>
              <Switch
                checked={!!settings.fallback_to_defaults}
                onCheckedChange={(v) => saveSettings({ fallback_to_defaults: v })}
                data-testid="fraud-fallback-toggle"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Per-service accounts */}
      {services.map((svc) => {
        const svcAccounts = accountsFor(svc.key);
        const isOpen = expanded[svc.key] ?? svcAccounts.length > 0;
        return (
          <Card key={svc.key} className="bg-[var(--brand-card)] border-[var(--brand-border)]" data-testid={`fraud-service-${svc.key}`}>
            <CardHeader
              className="cursor-pointer"
              onClick={() => setExpanded({ ...expanded, [svc.key]: !isOpen })}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <CardTitle className="text-base">{svc.name}</CardTitle>
                  <Badge variant="secondary" className="bg-[#1E293B]">Accounts ({svcAccounts.length})</Badge>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={svc.signup_url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={(e) => e.stopPropagation()}
                    className="text-xs text-[#60A5FA] hover:underline flex items-center gap-1"
                  >
                    Get API key <ExternalLink size={12} />
                  </a>
                  {isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
              </div>
            </CardHeader>
            {isOpen && (
              <CardContent className="space-y-3">
                {svcAccounts.length === 0 && (
                  <div className="text-sm text-[var(--brand-muted)] italic">
                    No accounts added yet &mdash; Krexion&apos;s built-in default is used until you add one.
                  </div>
                )}
                {svcAccounts.length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow className="border-[var(--brand-border)] hover:bg-transparent">
                        <TableHead>Account name</TableHead>
                        {svc.needs_user && <TableHead>Username</TableHead>}
                        <TableHead>API key</TableHead>
                        <TableHead>Enabled</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Quota</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {svcAccounts.map((acc) => (
                        <TableRow key={acc.id} className="border-[var(--brand-border)]" data-testid={`fraud-account-row-${acc.id}`}>
                          <TableCell className="font-medium">{acc.account_name}</TableCell>
                          {svc.needs_user && <TableCell className="font-mono text-xs">{acc.api_user || "—"}</TableCell>}
                          <TableCell className="font-mono text-xs">
                            {acc.api_key ? "•".repeat(8) + acc.api_key.slice(-4) : "—"}
                          </TableCell>
                          <TableCell>
                            <Switch checked={!!acc.enabled} onCheckedChange={() => toggleEnable(acc)} data-testid={`fraud-toggle-${acc.id}`} />
                          </TableCell>
                          <TableCell className="text-xs">{acc.priority}</TableCell>
                          <TableCell className="text-xs">
                            {acc.quota_daily ? `${acc.quota_used}/${acc.quota_daily}` : "unlimited"}
                          </TableCell>
                          <TableCell className="text-right space-x-1">
                            <Button size="sm" variant="ghost" onClick={() => testAccount(acc)} title="Test" data-testid={`fraud-test-${acc.id}`}>
                              <Play size={14} />
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => openEdit(acc)} title="Edit" data-testid={`fraud-edit-${acc.id}`}>
                              <Edit2 size={14} />
                            </Button>
                            <Button size="sm" variant="ghost" onClick={() => deleteAccount(acc.id)} title="Delete" data-testid={`fraud-delete-${acc.id}`}>
                              <Trash2 size={14} className="text-red-400" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
                <Button
                  size="sm"
                  variant="outline"
                  className="border-[var(--brand-border)]"
                  onClick={() => openAdd(svc)}
                  data-testid={`fraud-add-${svc.key}`}
                >
                  <Plus size={14} className="mr-1" /> Add {svc.name} account
                </Button>
              </CardContent>
            )}
          </Card>
        );
      })}

      {/* Add/Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="bg-[var(--brand-card)] border-[var(--brand-border)] max-w-lg" data-testid="fraud-account-dialog">
          <DialogHeader>
            <DialogTitle>{editing?.isNew ? "Add" : "Edit"} account</DialogTitle>
            <DialogDescription>
              {editing?.isNew ? "Add a new API-key account for this fraud service." : "Update this account's credentials or settings."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label>Account name</Label>
              <Input value={form.account_name || ""} onChange={(e) => setForm({ ...form, account_name: e.target.value })}
                     placeholder="e.g. Primary US, Backup EU" data-testid="fraud-form-name" />
            </div>
            {(services.find((s) => s.key === (editing?.service || form.service))?.needs_user) && (
              <div>
                <Label>API username</Label>
                <Input value={form.api_user || ""} onChange={(e) => setForm({ ...form, api_user: e.target.value })}
                       placeholder="required by this service" data-testid="fraud-form-user" />
              </div>
            )}
            <div>
              <Label>API key</Label>
              <Input value={form.api_key || ""} onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                     placeholder="your api key" data-testid="fraud-form-key" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label>Priority</Label>
                <Input type="number" value={form.priority ?? 100} onChange={(e) => setForm({ ...form, priority: parseInt(e.target.value) || 100 })}
                       data-testid="fraud-form-priority" />
                <p className="text-xs text-[var(--brand-muted)] mt-1">Lower = tried first</p>
              </div>
              <div>
                <Label>Daily quota (0 = unlimited)</Label>
                <Input type="number" value={form.quota_daily ?? 0} onChange={(e) => setForm({ ...form, quota_daily: parseInt(e.target.value) || 0 })}
                       data-testid="fraud-form-quota" />
              </div>
            </div>
            <div>
              <Label>Custom endpoint (optional)</Label>
              <Input value={form.endpoint || ""} onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
                     placeholder="Leave blank for service default" data-testid="fraud-form-endpoint" />
            </div>
            <div className="flex items-center justify-between p-3 rounded border border-[var(--brand-border)]">
              <span>Enabled</span>
              <Switch checked={!!form.enabled} onCheckedChange={(v) => setForm({ ...form, enabled: v })} data-testid="fraud-form-enabled" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={saveAccount} data-testid="fraud-form-save">
              {editing?.isNew ? "Add account" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
