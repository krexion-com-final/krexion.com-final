import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Trash2, Edit, Save, X, Megaphone, ArrowLeft, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const adminH = () => ({
  Authorization: `Bearer ${localStorage.getItem("adminToken")}`,
  "Content-Type": "application/json",
});

const THEMES = [
  { value: "info",    label: "Info (blue)",     bg: "bg-blue-500" },
  { value: "promo",   label: "Promo (purple)",  bg: "bg-fuchsia-500" },
  { value: "success", label: "Success (green)", bg: "bg-emerald-500" },
  { value: "warning", label: "Warning (amber)", bg: "bg-amber-500" },
  { value: "danger",  label: "Danger (red)",    bg: "bg-red-500" },
];

const EMPTY = {
  message: "",
  theme: "promo",
  cta_label: "",
  cta_url: "",
  starts_at: "",
  ends_at: "",
  is_active: true,
  priority: 0,
  dismissible: true,
};

export default function AdminBannersPage() {
  const [banners, setBanners] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState(EMPTY);

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${BACKEND_URL}/api/admin/banners`, { headers: adminH() });
      if (r.ok) setBanners(await r.json());
      else toast.error("Load failed");
    } catch (e) { toast.error(e.message); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const openNew = () => {
    setEditing("new");
    setDraft(EMPTY);
  };

  const openEdit = (b) => {
    setEditing(b.id);
    setDraft({ ...EMPTY, ...b });
  };

  const save = async () => {
    if (!draft.message.trim()) {
      toast.error("Message required");
      return;
    }
    try {
      const url = editing === "new" ? `${BACKEND_URL}/api/admin/banners` : `${BACKEND_URL}/api/admin/banners/${editing}`;
      const method = editing === "new" ? "POST" : "PATCH";
      const body = { ...draft };
      if (!body.cta_label) body.cta_label = null;
      if (!body.cta_url) body.cta_url = null;
      if (!body.starts_at) body.starts_at = null;
      if (!body.ends_at) body.ends_at = null;
      const r = await fetch(url, { method, headers: adminH(), body: JSON.stringify(body) });
      const d = await r.json();
      if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
      toast.success("Saved ✓");
      setEditing(null);
      load();
    } catch (e) {
      toast.error(e.message);
    }
  };

  const del = async (id) => {
    if (!window.confirm("Delete this banner?")) return;
    try {
      const r = await fetch(`${BACKEND_URL}/api/admin/banners/${id}`, { method: "DELETE", headers: adminH() });
      if (r.ok) { toast.success("Deleted"); load(); }
      else toast.error("Delete failed");
    } catch (e) { toast.error(e.message); }
  };

  const toggleActive = async (b) => {
    try {
      await fetch(`${BACKEND_URL}/api/admin/banners/${b.id}`, {
        method: "PATCH", headers: adminH(),
        body: JSON.stringify({ is_active: !b.is_active }),
      });
      load();
    } catch (e) { toast.error(e.message); }
  };

  const themeBg = (t) => THEMES.find((x) => x.value === t)?.bg || "bg-blue-500";

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6">
      <div className="max-w-6xl mx-auto space-y-4">
        <div className="flex items-center gap-3">
          <Link to="/admin/dashboard" className="p-2 rounded hover:bg-slate-800">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Megaphone className="w-6 h-6 text-fuchsia-500" />
            Banners & Announcements
          </h1>
          <div className="flex-1" />
          <button onClick={openNew} className="px-4 py-2 rounded bg-fuchsia-600 hover:bg-fuchsia-500 text-sm flex items-center gap-2" data-testid="admin-banner-new">
            <Plus className="w-4 h-4" /> New Banner
          </button>
        </div>

        <p className="text-sm text-slate-400">
          Banners shown on customer dashboard. Promote discounts, offers, system updates. Multiple banners stack by priority (highest first).
        </p>

        {editing && (
          <div className="bg-slate-900 border border-fuchsia-500/40 rounded-lg p-4 space-y-3" data-testid="admin-banner-editor">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{editing === "new" ? "New Banner" : "Edit Banner"}</h3>
              <button onClick={() => setEditing(null)} className="p-1 hover:bg-slate-800 rounded">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Message</label>
              <textarea
                value={draft.message}
                onChange={(e) => setDraft({ ...draft, message: e.target.value })}
                rows={2}
                className="w-full bg-slate-800 px-3 py-2 rounded text-sm outline-none focus:ring-2 focus:ring-fuchsia-500"
                placeholder="e.g. 🎉 Black Friday: 50% OFF Pro plan — Use code BF2026"
                data-testid="admin-banner-message"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Theme</label>
                <select
                  value={draft.theme}
                  onChange={(e) => setDraft({ ...draft, theme: e.target.value })}
                  className="w-full bg-slate-800 px-3 py-2 rounded text-sm"
                  data-testid="admin-banner-theme"
                >
                  {THEMES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Priority (higher = first)</label>
                <input
                  type="number"
                  value={draft.priority}
                  onChange={(e) => setDraft({ ...draft, priority: Number(e.target.value) })}
                  className="w-full bg-slate-800 px-3 py-2 rounded text-sm"
                  data-testid="admin-banner-priority"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">CTA Button Label (optional)</label>
                <input
                  value={draft.cta_label || ""}
                  onChange={(e) => setDraft({ ...draft, cta_label: e.target.value })}
                  placeholder="e.g. Claim Offer"
                  className="w-full bg-slate-800 px-3 py-2 rounded text-sm"
                  data-testid="admin-banner-cta-label"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">CTA Button URL (optional)</label>
                <input
                  value={draft.cta_url || ""}
                  onChange={(e) => setDraft({ ...draft, cta_url: e.target.value })}
                  placeholder="/pricing or https://…"
                  className="w-full bg-slate-800 px-3 py-2 rounded text-sm"
                  data-testid="admin-banner-cta-url"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Starts At (optional)</label>
                <input
                  type="datetime-local"
                  value={draft.starts_at ? draft.starts_at.slice(0, 16) : ""}
                  onChange={(e) => setDraft({ ...draft, starts_at: e.target.value ? new Date(e.target.value).toISOString() : "" })}
                  className="w-full bg-slate-800 px-3 py-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Ends At (optional)</label>
                <input
                  type="datetime-local"
                  value={draft.ends_at ? draft.ends_at.slice(0, 16) : ""}
                  onChange={(e) => setDraft({ ...draft, ends_at: e.target.value ? new Date(e.target.value).toISOString() : "" })}
                  className="w-full bg-slate-800 px-3 py-2 rounded text-sm"
                />
              </div>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} data-testid="admin-banner-active" />
                <span>Active</span>
              </label>
              <label className="flex items-center gap-2">
                <input type="checkbox" checked={draft.dismissible} onChange={(e) => setDraft({ ...draft, dismissible: e.target.checked })} data-testid="admin-banner-dismissible" />
                <span>Dismissible</span>
              </label>
            </div>

            {/* Preview */}
            <div>
              <div className="text-xs text-slate-400 mb-1">Preview</div>
              <div className={`${themeBg(draft.theme)} text-white px-4 py-2 rounded flex items-center gap-3`}>
                <Megaphone className="w-4 h-4 flex-shrink-0" />
                <span className="flex-1 text-sm">{draft.message || "Your message here…"}</span>
                {draft.cta_label && (
                  <span className="px-3 py-1 rounded bg-white/20 text-xs font-semibold">{draft.cta_label}</span>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditing(null)} className="px-4 py-2 rounded bg-slate-700 hover:bg-slate-600 text-sm">Cancel</button>
              <button onClick={save} className="px-4 py-2 rounded bg-fuchsia-600 hover:bg-fuchsia-500 text-sm flex items-center gap-2" data-testid="admin-banner-save">
                <Save className="w-4 h-4" /> Save
              </button>
            </div>
          </div>
        )}

        <div className="space-y-2">
          {loading && <div className="text-slate-500 p-6 text-center">Loading…</div>}
          {!loading && banners.length === 0 && (
            <div className="text-center py-12 border-2 border-dashed border-slate-700 rounded-lg">
              <Megaphone className="w-10 h-10 mx-auto mb-2 text-slate-600" />
              <div className="text-sm text-slate-500">No banners yet. Click <strong>New Banner</strong> to create one.</div>
            </div>
          )}
          {banners.map((b) => (
            <div key={b.id} className="bg-slate-800/50 border border-slate-700 rounded-lg p-3" data-testid={`admin-banner-row-${b.id}`}>
              <div className={`${themeBg(b.theme)} text-white px-3 py-2 rounded mb-2 flex items-center gap-2`}>
                <Megaphone className="w-4 h-4" />
                <span className="flex-1 text-sm">{b.message}</span>
                {b.cta_label && <span className="px-2 py-0.5 rounded bg-white/20 text-xs">{b.cta_label}</span>}
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-400">
                <span className={b.is_active ? "text-emerald-400" : "text-slate-500"}>
                  {b.is_active ? "● Active" : "○ Inactive"}
                </span>
                <span>Theme: {b.theme}</span>
                <span>Priority: {b.priority}</span>
                {b.starts_at && <span>From: {new Date(b.starts_at).toLocaleDateString()}</span>}
                {b.ends_at && <span>To: {new Date(b.ends_at).toLocaleDateString()}</span>}
                <div className="flex-1" />
                <button onClick={() => toggleActive(b)} className="p-1.5 rounded hover:bg-slate-700" title={b.is_active ? "Deactivate" : "Activate"}>
                  {b.is_active ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
                <button onClick={() => openEdit(b)} className="p-1.5 rounded hover:bg-slate-700" data-testid={`admin-banner-edit-${b.id}`}>
                  <Edit className="w-3.5 h-3.5" />
                </button>
                <button onClick={() => del(b.id)} className="p-1.5 rounded hover:bg-red-500/20 text-red-400" data-testid={`admin-banner-delete-${b.id}`}>
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
