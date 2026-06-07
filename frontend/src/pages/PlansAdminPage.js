import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Switch } from "../components/ui/switch";
import { Plus, Trash2, Edit3, Save, X, RefreshCw, DollarSign, Tag, Star, EyeOff, Eye } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BLANK_PLAN = {
  id: "",
  name: "",
  price_usdt: 0,
  duration_days: 30,
  description: "",
  features: "",       // textarea (one feature per line)
  is_popular: false,
  enabled: true,
  sort_order: 0,
  original_price_usdt: "",
  discount_percent: "",
  badge_text: "",
};

const auth = () => {
  const t = localStorage.getItem("token");
  return t ? { Authorization: `Bearer ${t}` } : {};
};

export default function PlansAdminPage() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // plan being edited
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/admin/crypto/plans`, { headers: auth() });
      setPlans(r.data.plans || []);
    } catch (e) {
      toast.error("Failed to load plans: " + (e?.response?.data?.detail || e.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/admin/crypto/plans`, { headers: auth() });
        if (!cancelled) setPlans(r.data.plans || []);
      } catch (e) {
        if (!cancelled) toast.error("Failed to load plans: " + (e?.response?.data?.detail || e.message));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const startEdit = (p) => {
    setEditing({
      ...p,
      features: (p.features || []).join("\n"),
      original_price_usdt: p.original_price_usdt ?? "",
      discount_percent: p.discount_percent ?? "",
      badge_text: p.badge_text ?? "",
    });
  };

  const startCreate = () => {
    setEditing({ ...BLANK_PLAN, id: `plan-${Date.now().toString(36)}`, _new: true });
  };

  const save = async () => {
    if (!editing) return;
    const payload = {
      name: editing.name?.trim(),
      price_usdt: Number(editing.price_usdt),
      duration_days: Math.max(1, parseInt(editing.duration_days || 30, 10)),
      description: editing.description || "",
      features: (editing.features || "")
        .split("\n").map((s) => s.trim()).filter(Boolean),
      is_popular: !!editing.is_popular,
      enabled: !!editing.enabled,
      sort_order: parseInt(editing.sort_order || 0, 10),
      original_price_usdt: editing.original_price_usdt !== "" && editing.original_price_usdt !== null
        ? Number(editing.original_price_usdt) : null,
      discount_percent: editing.discount_percent !== "" && editing.discount_percent !== null
        ? parseInt(editing.discount_percent, 10) : null,
      badge_text: (editing.badge_text || "").trim() || null,
    };
    if (!payload.name || !(payload.price_usdt > 0)) {
      toast.error("Name and price required (price must be > 0)");
      return;
    }
    setSaving(true);
    try {
      if (editing._new) {
        await axios.post(`${API}/admin/crypto/plans`, { id: editing.id, ...payload }, { headers: auth() });
        toast.success("Plan created");
      } else {
        await axios.put(`${API}/admin/crypto/plans/${editing.id}`, payload, { headers: auth() });
        toast.success("Plan updated");
      }
      setEditing(null);
      load();
    } catch (e) {
      toast.error("Save failed: " + (e?.response?.data?.detail || e.message));
    } finally {
      setSaving(false);
    }
  };

  const remove = async (p) => {
    if (!window.confirm(`Delete plan "${p.name}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`${API}/admin/crypto/plans/${p.id}`, { headers: auth() });
      toast.success("Plan deleted");
      load();
    } catch (e) {
      toast.error("Delete failed: " + (e?.response?.data?.detail || e.message));
    }
  };

  const toggleEnabled = async (p) => {
    try {
      await axios.put(`${API}/admin/crypto/plans/${p.id}`, { enabled: !p.enabled }, { headers: auth() });
      load();
    } catch (e) {
      toast.error("Toggle failed: " + (e?.response?.data?.detail || e.message));
    }
  };

  return (
    <div className="space-y-6 max-w-7xl" data-testid="plans-admin-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Pricing Plans</h1>
          <p className="text-zinc-400">
            Create, edit, and discount the plans shown on <code>/pricing</code>.
            Changes are live immediately — customers see new prices on next page load.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={load} className="border-zinc-700 text-zinc-300" data-testid="plans-refresh-btn">
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh
          </Button>
          <Button onClick={startCreate} className="bg-purple-600 hover:bg-purple-700" data-testid="plans-add-btn">
            <Plus className="w-4 h-4 mr-2" /> Add plan
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="text-zinc-500 py-12 text-center">Loading…</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {plans.map((p) => (
            <Card key={p.id} className={`bg-zinc-900 border-zinc-800 ${!p.enabled ? "opacity-60" : ""}`} data-testid={`plan-row-${p.id}`}>
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <CardTitle className="text-white flex items-center gap-2">
                      {p.name}
                      {p.is_popular && (
                        <Badge className="bg-purple-600 text-[10px]">
                          <Star className="w-3 h-3 mr-0.5" /> Popular
                        </Badge>
                      )}
                    </CardTitle>
                    <CardDescription className="text-xs">{p.id}</CardDescription>
                  </div>
                  <div className="flex flex-col items-end">
                    {p.original_price_usdt && Number(p.original_price_usdt) > Number(p.price_usdt) && (
                      <span className="text-xs text-zinc-500 line-through">{p.original_price_usdt} USDT</span>
                    )}
                    <span className="text-xl font-bold text-white">{p.price_usdt} USDT</span>
                    {p.discount_percent && (
                      <Badge className="bg-pink-600 text-[10px] mt-1">-{p.discount_percent}%</Badge>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-zinc-400 text-sm min-h-[36px]">{p.description}</p>
                <div className="text-xs text-zinc-500">
                  {p.duration_days} day{p.duration_days === 1 ? "" : "s"} access · sort {p.sort_order}
                  {p.badge_text && <> · banner: <em className="text-pink-400">{p.badge_text}</em></>}
                </div>
                <ul className="text-xs text-zinc-400 space-y-1 pl-3 list-disc max-h-32 overflow-y-auto">
                  {(p.features || []).slice(0, 8).map((f, i) => <li key={i}>{f}</li>)}
                </ul>
                <div className="flex gap-2 pt-2">
                  <Button size="sm" variant="outline" onClick={() => startEdit(p)} className="border-zinc-700" data-testid={`plan-edit-${p.id}`}>
                    <Edit3 className="w-3 h-3 mr-1" /> Edit
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => toggleEnabled(p)} className="border-zinc-700" data-testid={`plan-toggle-${p.id}`}>
                    {p.enabled ? <><EyeOff className="w-3 h-3 mr-1" /> Hide</> : <><Eye className="w-3 h-3 mr-1" /> Show</>}
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => remove(p)} data-testid={`plan-delete-${p.id}`}>
                    <Trash2 className="w-3 h-3" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {editing && (
        <div
          className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setEditing(null); }}
        >
          <Card className="bg-zinc-900 border-zinc-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-white">
                  {editing._new ? "New plan" : `Edit: ${editing.name}`}
                </CardTitle>
                <Button size="sm" variant="ghost" onClick={() => setEditing(null)} className="text-zinc-400">
                  <X className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {editing._new && (
                <div>
                  <Label className="text-zinc-300 text-xs">Plan ID (URL-safe, e.g. starter, pro-annual)</Label>
                  <Input
                    value={editing.id}
                    onChange={(e) => setEditing({ ...editing, id: e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "") })}
                    className="bg-zinc-800 border-zinc-700 text-white"
                    data-testid="plan-form-id"
                  />
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label className="text-zinc-300 text-xs">Display name</Label>
                  <Input
                    value={editing.name}
                    onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                    className="bg-zinc-800 border-zinc-700 text-white"
                    data-testid="plan-form-name"
                  />
                </div>
                <div>
                  <Label className="text-zinc-300 text-xs">Duration (days)</Label>
                  <Input
                    type="number" min="1"
                    value={editing.duration_days}
                    onChange={(e) => setEditing({ ...editing, duration_days: e.target.value })}
                    className="bg-zinc-800 border-zinc-700 text-white"
                    data-testid="plan-form-duration"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <Label className="text-zinc-300 text-xs flex items-center gap-1">
                    <DollarSign className="w-3 h-3" /> Current price (USDT)
                  </Label>
                  <Input
                    type="number" step="0.01" min="0"
                    value={editing.price_usdt}
                    onChange={(e) => setEditing({ ...editing, price_usdt: e.target.value })}
                    className="bg-zinc-800 border-zinc-700 text-white"
                    data-testid="plan-form-price"
                  />
                </div>
                <div>
                  <Label className="text-zinc-300 text-xs">Original price (strike-through)</Label>
                  <Input
                    type="number" step="0.01" min="0" placeholder="optional"
                    value={editing.original_price_usdt}
                    onChange={(e) => setEditing({ ...editing, original_price_usdt: e.target.value })}
                    className="bg-zinc-800 border-zinc-700 text-white"
                    data-testid="plan-form-orig-price"
                  />
                </div>
                <div>
                  <Label className="text-zinc-300 text-xs">Discount % (badge)</Label>
                  <Input
                    type="number" min="0" max="100" placeholder="optional"
                    value={editing.discount_percent}
                    onChange={(e) => setEditing({ ...editing, discount_percent: e.target.value })}
                    className="bg-zinc-800 border-zinc-700 text-white"
                    data-testid="plan-form-discount"
                  />
                </div>
              </div>

              <div>
                <Label className="text-zinc-300 text-xs flex items-center gap-1">
                  <Tag className="w-3 h-3" /> Banner text (e.g. &quot;Black Friday&quot;, &quot;Limited Time&quot;)
                </Label>
                <Input
                  value={editing.badge_text}
                  onChange={(e) => setEditing({ ...editing, badge_text: e.target.value })}
                  className="bg-zinc-800 border-zinc-700 text-white"
                  placeholder="optional — shown above price"
                  data-testid="plan-form-badge"
                />
              </div>

              <div>
                <Label className="text-zinc-300 text-xs">Short description</Label>
                <Textarea
                  rows={2}
                  value={editing.description}
                  onChange={(e) => setEditing({ ...editing, description: e.target.value })}
                  className="bg-zinc-800 border-zinc-700 text-white"
                  data-testid="plan-form-desc"
                />
              </div>

              <div>
                <Label className="text-zinc-300 text-xs">Features (one per line)</Label>
                <Textarea
                  rows={6}
                  value={editing.features}
                  onChange={(e) => setEditing({ ...editing, features: e.target.value })}
                  className="bg-zinc-800 border-zinc-700 text-white font-mono text-xs"
                  placeholder={"10,000 clicks/month\n3 PC activations\nForm Filler + RUT\nEmail support"}
                  data-testid="plan-form-features"
                />
              </div>

              <div className="grid grid-cols-3 gap-3 items-center">
                <div>
                  <Label className="text-zinc-300 text-xs">Sort order</Label>
                  <Input
                    type="number"
                    value={editing.sort_order}
                    onChange={(e) => setEditing({ ...editing, sort_order: e.target.value })}
                    className="bg-zinc-800 border-zinc-700 text-white"
                    data-testid="plan-form-sort"
                  />
                </div>
                <div className="flex items-center gap-2 mt-5">
                  <Switch
                    checked={!!editing.is_popular}
                    onCheckedChange={(v) => setEditing({ ...editing, is_popular: v })}
                    data-testid="plan-form-popular"
                  />
                  <Label className="text-zinc-300 text-xs">Mark as Popular</Label>
                </div>
                <div className="flex items-center gap-2 mt-5">
                  <Switch
                    checked={!!editing.enabled}
                    onCheckedChange={(v) => setEditing({ ...editing, enabled: v })}
                    data-testid="plan-form-enabled"
                  />
                  <Label className="text-zinc-300 text-xs">Enabled (live)</Label>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-4 border-t border-zinc-800">
                <Button variant="outline" onClick={() => setEditing(null)} className="border-zinc-700 text-zinc-300">
                  Cancel
                </Button>
                <Button
                  onClick={save}
                  disabled={saving}
                  className="bg-green-600 hover:bg-green-700"
                  data-testid="plan-form-save"
                >
                  {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                  {editing._new ? "Create plan" : "Save changes"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
