import { useEffect, useState } from "react";
import axios from "axios";
import { Plus, Trash2, Copy, ExternalLink, Globe, Smartphone, Apple } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const empty = {
  name: "",
  android_url: "",
  ios_url: "",
  desktop_url: "",
  fallback_url: "https://www.google.com/",
};

export default function CPISmartLinksPage() {
  const [links, setLinks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(empty);

  const token = localStorage.getItem("token");
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const load = async () => {
    try {
      const r = await axios.get(`${API}/cpi/smartlinks`, auth);
      setLinks(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load smart-links");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const onCreate = async () => {
    if (!form.name) { toast.error("Name required"); return; }
    if (!form.android_url && !form.ios_url && !form.desktop_url) {
      toast.error("Provide at least one OS URL");
      return;
    }
    try {
      await axios.post(`${API}/cpi/smartlinks`, form, auth);
      toast.success("Smart-link created");
      setOpen(false);
      setForm(empty);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Create failed");
    }
  };

  const onDelete = async (id) => {
    if (!window.confirm("Delete this smart-link?")) return;
    try {
      await axios.delete(`${API}/cpi/smartlinks/${id}`, auth);
      toast.success("Deleted");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  const linkUrl = (code) => `${process.env.REACT_APP_BACKEND_URL}/api/cpi/sl/${code}`;

  const onCopy = (code) => {
    navigator.clipboard.writeText(linkUrl(code));
    toast.success("Smart-link copied to clipboard");
  };

  return (
    <div className="space-y-6" data-testid="cpi-smartlinks-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">CPI Smart Links</h1>
          <p className="text-sm text-muted-foreground">One link, OS-aware redirect — Android/iOS/Desktop branching</p>
        </div>
        <Button onClick={() => setOpen(true)} data-testid="cpi-sl-new-btn">
          <Plus className="h-4 w-4 mr-2" /> New Smart Link
        </Button>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : links.length === 0 ? (
        <div className="border rounded-lg p-8 text-center text-sm text-muted-foreground">
          No smart-links yet. Create one to get a single URL that routes by OS.
        </div>
      ) : (
        <div className="space-y-3">
          {links.map((l) => (
            <div key={l.id} className="border rounded-lg p-4 space-y-3" data-testid={`cpi-sl-card-${l.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="font-medium">{l.name}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <code className="text-xs bg-muted px-2 py-1 rounded font-mono">{linkUrl(l.code)}</code>
                    <Button size="sm" variant="ghost" onClick={() => onCopy(l.code)}><Copy className="h-3 w-3" /></Button>
                    <a href={linkUrl(l.code)} target="_blank" rel="noreferrer">
                      <Button size="sm" variant="ghost"><ExternalLink className="h-3 w-3" /></Button>
                    </a>
                  </div>
                </div>
                <Button size="sm" variant="ghost" onClick={() => onDelete(l.id)}><Trash2 className="h-4 w-4" /></Button>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <Badge variant="secondary"><Globe className="h-3 w-3 mr-1" /> {l.total_clicks} total</Badge>
                <Badge variant="outline"><Smartphone className="h-3 w-3 mr-1" /> {l.android_clicks} Android</Badge>
                <Badge variant="outline"><Apple className="h-3 w-3 mr-1" /> {l.ios_clicks} iOS</Badge>
                <Badge variant="outline">{l.desktop_clicks} Desktop</Badge>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-muted-foreground">
                {l.android_url && <div>📱 Android → <span className="font-mono break-all">{l.android_url}</span></div>}
                {l.ios_url && <div>🍎 iOS → <span className="font-mono break-all">{l.ios_url}</span></div>}
                {l.desktop_url && <div>💻 Desktop → <span className="font-mono break-all">{l.desktop_url}</span></div>}
                {l.fallback_url && <div>↘ Fallback → <span className="font-mono break-all">{l.fallback_url}</span></div>}
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>New Smart Link</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g., VPN Offer Universal" data-testid="cpi-sl-name-input" />
            </div>
            <div className="space-y-2">
              <Label>Android URL</Label>
              <Input value={form.android_url} onChange={(e) => setForm({ ...form, android_url: e.target.value })} placeholder="https://... or APK URL" />
            </div>
            <div className="space-y-2">
              <Label>iOS URL</Label>
              <Input value={form.ios_url} onChange={(e) => setForm({ ...form, ios_url: e.target.value })} placeholder="https://apps.apple.com/..." />
            </div>
            <div className="space-y-2">
              <Label>Desktop URL</Label>
              <Input value={form.desktop_url} onChange={(e) => setForm({ ...form, desktop_url: e.target.value })} placeholder="https://your-landing-page.com" />
            </div>
            <div className="space-y-2">
              <Label>Fallback URL</Label>
              <Input value={form.fallback_url} onChange={(e) => setForm({ ...form, fallback_url: e.target.value })} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={onCreate} data-testid="cpi-sl-create-btn">Create</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
