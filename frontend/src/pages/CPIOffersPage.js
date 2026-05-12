import { useEffect, useState } from "react";
import axios from "axios";
import { Plus, Pencil, Trash2, Smartphone, Apple, Globe, Pause, Play, Copy } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const emptyOffer = {
  name: "",
  network: "",
  target_os: "android",
  tracker_url: "",
  apk_url: "",
  ipa_url: "",
  package_name: "",
  ios_app_id: "",
  payout: 0,
  geo: "",
  daily_cap: 0,
  notes: "",
  status: "active",
};

export default function CPIOffersPage() {
  const [offers, setOffers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyOffer);

  const token = localStorage.getItem("token");
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/cpi/offers`, auth);
      setOffers(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load offers");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const onCreate = () => { setEditing(null); setForm(emptyOffer); setOpen(true); };
  const onEdit = (o) => {
    setEditing(o);
    setForm({ ...emptyOffer, ...o });
    setOpen(true);
  };

  const onSave = async () => {
    try {
      const payload = { ...form, payout: parseFloat(form.payout) || 0, daily_cap: parseInt(form.daily_cap) || 0 };
      if (editing) {
        await axios.put(`${API}/cpi/offers/${editing.id}`, payload, auth);
        toast.success("Offer updated");
      } else {
        await axios.post(`${API}/cpi/offers`, payload, auth);
        toast.success("Offer created");
      }
      setOpen(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    }
  };

  const onDelete = async (id) => {
    if (!window.confirm("Delete this offer?")) return;
    try {
      await axios.delete(`${API}/cpi/offers/${id}`, auth);
      toast.success("Offer deleted");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  const osIcon = (os) => os === "ios" ? <Apple className="h-4 w-4" /> : os === "both" ? <Globe className="h-4 w-4" /> : <Smartphone className="h-4 w-4" />;

  return (
    <div className="space-y-6" data-testid="cpi-offers-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">CPI Offers</h1>
          <p className="text-sm text-muted-foreground">Cost-Per-Install offers — Android, iOS, or both</p>
        </div>
        <Button onClick={onCreate} data-testid="cpi-offer-new-btn">
          <Plus className="h-4 w-4 mr-2" /> New Offer
        </Button>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : offers.length === 0 ? (
        <div className="border rounded-lg p-8 text-center text-sm text-muted-foreground">
          No offers yet. Click "New Offer" to add your first CPI offer.
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">OS</th>
                <th className="text-left p-3">Network</th>
                <th className="text-left p-3">Payout</th>
                <th className="text-left p-3">Geo</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Stats</th>
                <th className="text-right p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {offers.map((o) => (
                <tr key={o.id} className="border-t" data-testid={`cpi-offer-row-${o.id}`}>
                  <td className="p-3 font-medium">{o.name}</td>
                  <td className="p-3"><span className="inline-flex items-center gap-1">{osIcon(o.target_os)} {o.target_os}</span></td>
                  <td className="p-3 text-muted-foreground">{o.network || "—"}</td>
                  <td className="p-3">${(o.payout || 0).toFixed(2)}</td>
                  <td className="p-3 text-muted-foreground">{o.geo || "Any"}</td>
                  <td className="p-3">
                    <Badge variant={o.status === "active" ? "default" : "secondary"}>{o.status}</Badge>
                  </td>
                  <td className="p-3 text-xs text-muted-foreground">
                    {o.total_conversions || 0} conv · ${(o.total_earnings || 0).toFixed(2)}
                  </td>
                  <td className="p-3 text-right space-x-1">
                    <Button size="sm" variant="ghost" onClick={() => onEdit(o)} data-testid={`cpi-offer-edit-${o.id}`}>
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => onDelete(o.id)} data-testid={`cpi-offer-delete-${o.id}`}>
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing ? "Edit Offer" : "New CPI Offer"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2 col-span-2">
              <Label>Offer Name *</Label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g., Private VPN US Tier1" data-testid="cpi-offer-name-input" />
            </div>
            <div className="space-y-2">
              <Label>Network</Label>
              <Input value={form.network} onChange={(e) => setForm({ ...form, network: e.target.value })} placeholder="taptrcks / Mobupps / etc." />
            </div>
            <div className="space-y-2">
              <Label>Target OS</Label>
              <Select value={form.target_os} onValueChange={(v) => setForm({ ...form, target_os: v })}>
                <SelectTrigger data-testid="cpi-offer-os-select"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="android">Android only</SelectItem>
                  <SelectItem value="ios">iOS only</SelectItem>
                  <SelectItem value="both">Both (universal)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2 col-span-2">
              <Label>Tracker URL *</Label>
              <Input value={form.tracker_url} onChange={(e) => setForm({ ...form, tracker_url: e.target.value })} placeholder="https://..." data-testid="cpi-offer-tracker-input" />
            </div>
            <div className="space-y-2">
              <Label>APK URL (Android direct install)</Label>
              <Input value={form.apk_url} onChange={(e) => setForm({ ...form, apk_url: e.target.value })} placeholder="https://.../app.apk" />
            </div>
            <div className="space-y-2">
              <Label>IPA URL (iOS sideload)</Label>
              <Input value={form.ipa_url} onChange={(e) => setForm({ ...form, ipa_url: e.target.value })} placeholder="https://.../app.ipa" />
            </div>
            <div className="space-y-2">
              <Label>Package Name (Android)</Label>
              <Input value={form.package_name} onChange={(e) => setForm({ ...form, package_name: e.target.value })} placeholder="com.example.app" />
            </div>
            <div className="space-y-2">
              <Label>iOS App ID</Label>
              <Input value={form.ios_app_id} onChange={(e) => setForm({ ...form, ios_app_id: e.target.value })} placeholder="id123456789" />
            </div>
            <div className="space-y-2">
              <Label>Payout per Install ($)</Label>
              <Input type="number" step="0.01" value={form.payout} onChange={(e) => setForm({ ...form, payout: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Daily Cap (0 = unlimited)</Label>
              <Input type="number" value={form.daily_cap} onChange={(e) => setForm({ ...form, daily_cap: e.target.value })} />
            </div>
            <div className="space-y-2 col-span-2">
              <Label>Allowed Geos (comma-separated ISO-2)</Label>
              <Input value={form.geo} onChange={(e) => setForm({ ...form, geo: e.target.value })} placeholder="US,UK,CA or PK,IN" />
            </div>
            <div className="space-y-2 col-span-2">
              <Label>Notes</Label>
              <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={2} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={onSave} data-testid="cpi-offer-save-btn">{editing ? "Save Changes" : "Create Offer"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
