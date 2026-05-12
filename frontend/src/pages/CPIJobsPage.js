import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Plus, Play, Square, Pause, Trash2, Activity, Package } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Switch } from "../components/ui/switch";
import { Badge } from "../components/ui/badge";
import { Progress } from "../components/ui/progress";
import { toast } from "sonner";
import useVisibleInterval from "../hooks/useVisibleInterval";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusColor = (s) => ({
  queued: "secondary",
  running: "default",
  paused: "outline",
  completed: "secondary",
  stopped: "destructive",
  failed: "destructive",
}[s] || "secondary");

export default function CPIJobsPage() {
  const navigate = useNavigate();
  const [jobs, setJobs] = useState([]);
  const [offers, setOffers] = useState([]);
  const [proxyUploads, setProxyUploads] = useState([]);
  const [uaUploads, setUaUploads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [proxyMode, setProxyMode] = useState("paste");   // "paste" | "uploaded"
  const [uaMode, setUaMode] = useState("paste");
  const [form, setForm] = useState({
    offer_id: "",
    target_count: 10,
    concurrency: 2,
    delay_min_seconds: 60,
    delay_max_seconds: 300,
    settle_seconds: 45,
    proxiesText: "",
    uasText: "",
    leadsText: "",
    upload_proxy_id: "",
    upload_ua_id: "",
    auto_consume: true,
  });

  const token = localStorage.getItem("token");
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const load = async () => {
    setLoading(true);
    try {
      const [j, o, ups, uas] = await Promise.all([
        axios.get(`${API}/cpi/jobs`, auth),
        axios.get(`${API}/cpi/offers?status=active`, auth),
        axios.get(`${API}/uploads?type=proxies`, auth).catch(() => ({ data: [] })),
        axios.get(`${API}/uploads?type=user_agents`, auth).catch(() => ({ data: [] })),
      ]);
      setJobs(j.data || []);
      setOffers(o.data || []);
      setProxyUploads(ups.data || []);
      setUaUploads(uas.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);
  useVisibleInterval(load, 5000);

  const parseLeads = (txt) => {
    return txt.split("\n").map(l => l.trim()).filter(Boolean).map(line => {
      const [email, first, last, phone] = line.split(",").map(s => (s || "").trim());
      return { email: email || "", first: first || "", last: last || "", phone: phone || "" };
    });
  };

  const onCreate = async () => {
    if (!form.offer_id) { toast.error("Select an offer"); return; }
    const proxies = proxyMode === "paste"
      ? form.proxiesText.split("\n").map(s => s.trim()).filter(Boolean)
      : [];
    const user_agents = uaMode === "paste"
      ? form.uasText.split("\n").map(s => s.trim()).filter(Boolean)
      : [];
    const leads = parseLeads(form.leadsText);

    if (proxyMode === "paste" && proxies.length === 0) { toast.error("Paste at least one proxy or pick from Uploaded Things"); return; }
    if (proxyMode === "uploaded" && !form.upload_proxy_id) { toast.error("Pick a proxies upload"); return; }
    if (uaMode === "paste" && user_agents.length === 0) { toast.error("Paste at least one UA or pick from Uploaded Things"); return; }
    if (uaMode === "uploaded" && !form.upload_ua_id) { toast.error("Pick a UAs upload"); return; }

    try {
      await axios.post(`${API}/cpi/jobs`, {
        offer_id: form.offer_id,
        target_count: parseInt(form.target_count) || 10,
        concurrency: parseInt(form.concurrency) || 2,
        delay_min_seconds: parseInt(form.delay_min_seconds) || 60,
        delay_max_seconds: parseInt(form.delay_max_seconds) || 300,
        settle_seconds: parseInt(form.settle_seconds) || 45,
        proxies, user_agents, leads,
        upload_proxy_id: proxyMode === "uploaded" ? form.upload_proxy_id : null,
        upload_ua_id: uaMode === "uploaded" ? form.upload_ua_id : null,
        auto_consume: form.auto_consume,
      }, auth);
      toast.success("Job created (queued). Click ▶ to start.");
      setOpen(false);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Create failed");
    }
  };

  const action = async (id, kind) => {
    try {
      await axios.post(`${API}/cpi/jobs/${id}/${kind}`, {}, auth);
      toast.success(`Job ${kind}ed`);
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || `Failed to ${kind}`);
    }
  };

  const onDelete = async (id) => {
    if (!window.confirm("Delete this job?")) return;
    try {
      await axios.delete(`${API}/cpi/jobs/${id}`, auth);
      toast.success("Job deleted");
      load();
    } catch (e) { toast.error(e.response?.data?.detail || "Delete failed"); }
  };

  return (
    <div className="space-y-6" data-testid="cpi-jobs-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">CPI Jobs</h1>
          <p className="text-sm text-muted-foreground">Create and monitor install jobs — workers pick up automatically</p>
        </div>
        <Button onClick={() => setOpen(true)} data-testid="cpi-job-new-btn">
          <Plus className="h-4 w-4 mr-2" /> New Job
        </Button>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : jobs.length === 0 ? (
        <div className="border rounded-lg p-8 text-center text-sm text-muted-foreground">
          No jobs yet. Create your first install job above.
        </div>
      ) : (
        <div className="border rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="text-left p-3">Offer</th>
                <th className="text-left p-3">OS</th>
                <th className="text-left p-3">Status</th>
                <th className="text-left p-3">Progress</th>
                <th className="text-left p-3">Pools</th>
                <th className="text-right p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => {
                const total = j.target_count || 1;
                const done = (j.completed || 0) + (j.failed || 0);
                const pct = Math.round((done / total) * 100);
                return (
                  <tr key={j.id} className="border-t" data-testid={`cpi-job-row-${j.id}`}>
                    <td className="p-3 font-medium">{j.offer_name}</td>
                    <td className="p-3">{j.target_os}</td>
                    <td className="p-3"><Badge variant={statusColor(j.status)}>{j.status}</Badge></td>
                    <td className="p-3 min-w-[180px]">
                      <div className="space-y-1">
                        <Progress value={pct} className="h-2" />
                        <div className="text-xs text-muted-foreground">
                          {j.completed || 0}✓ · {j.failed || 0}✗ · {j.in_progress || 0}↻ / {total}
                        </div>
                      </div>
                    </td>
                    <td className="p-3 text-xs text-muted-foreground">
                      {j.proxies_count || 0} proxy · {j.uas_count || 0} UA · {j.leads_count || 0} leads
                    </td>
                    <td className="p-3 text-right space-x-1">
                      <Button size="sm" variant="ghost" onClick={() => navigate(`/cpi/jobs/${j.id}`)} data-testid={`cpi-job-view-${j.id}`}>
                        <Activity className="h-4 w-4" />
                      </Button>
                      {(j.status === "queued" || j.status === "paused") && (
                        <Button size="sm" variant="ghost" onClick={() => action(j.id, "start")} data-testid={`cpi-job-start-${j.id}`}>
                          <Play className="h-4 w-4" />
                        </Button>
                      )}
                      {j.status === "running" && (
                        <>
                          <Button size="sm" variant="ghost" onClick={() => action(j.id, "pause")}><Pause className="h-4 w-4" /></Button>
                          <Button size="sm" variant="ghost" onClick={() => action(j.id, "stop")}><Square className="h-4 w-4" /></Button>
                        </>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => onDelete(j.id)}><Trash2 className="h-4 w-4" /></Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New CPI Install Job</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2 col-span-2">
                <Label>Offer *</Label>
                <Select value={form.offer_id} onValueChange={(v) => setForm({ ...form, offer_id: v })}>
                  <SelectTrigger data-testid="cpi-job-offer-select"><SelectValue placeholder="Select offer" /></SelectTrigger>
                  <SelectContent>
                    {offers.map(o => (
                      <SelectItem key={o.id} value={o.id}>
                        {o.name} · {o.target_os} · ${(o.payout || 0).toFixed(2)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Total Installs</Label>
                <Input type="number" value={form.target_count} onChange={(e) => setForm({ ...form, target_count: e.target.value })} data-testid="cpi-job-count-input" />
              </div>
              <div className="space-y-2">
                <Label>Concurrency</Label>
                <Input type="number" value={form.concurrency} onChange={(e) => setForm({ ...form, concurrency: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>Min Delay (s)</Label>
                <Input type="number" value={form.delay_min_seconds} onChange={(e) => setForm({ ...form, delay_min_seconds: e.target.value })} />
              </div>
              <div className="space-y-2">
                <Label>Max Delay (s)</Label>
                <Input type="number" value={form.delay_max_seconds} onChange={(e) => setForm({ ...form, delay_max_seconds: e.target.value })} />
              </div>
              <div className="space-y-2 col-span-2">
                <Label>Settle Wait After Install (s)</Label>
                <Input type="number" value={form.settle_seconds} onChange={(e) => setForm({ ...form, settle_seconds: e.target.value })} />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Proxies *</Label>
              <Tabs value={proxyMode} onValueChange={setProxyMode}>
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="paste">Paste</TabsTrigger>
                  <TabsTrigger value="uploaded"><Package className="h-3 w-3 mr-1" /> From Uploaded Things ({proxyUploads.length})</TabsTrigger>
                </TabsList>
                <TabsContent value="paste">
                  <Textarea rows={4} value={form.proxiesText} onChange={(e) => setForm({ ...form, proxiesText: e.target.value })} placeholder="proxy.host.com:8080:user:pass (one per line)" data-testid="cpi-job-proxies-input" />
                </TabsContent>
                <TabsContent value="uploaded">
                  <Select value={form.upload_proxy_id} onValueChange={(v) => setForm({ ...form, upload_proxy_id: v })}>
                    <SelectTrigger><SelectValue placeholder="Select uploaded proxies batch" /></SelectTrigger>
                    <SelectContent>
                      {proxyUploads.length === 0 && <div className="p-3 text-xs text-muted-foreground">No uploaded proxy batches. Upload via Uploaded Things page first.</div>}
                      {proxyUploads.map(u => (
                        <SelectItem key={u.id} value={u.id}>
                          {u.name} · {u.items_count || u.items?.length || 0} items
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TabsContent>
              </Tabs>
            </div>

            <div className="space-y-2">
              <Label>User Agents *</Label>
              <Tabs value={uaMode} onValueChange={setUaMode}>
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="paste">Paste</TabsTrigger>
                  <TabsTrigger value="uploaded"><Package className="h-3 w-3 mr-1" /> From Uploaded Things ({uaUploads.length})</TabsTrigger>
                </TabsList>
                <TabsContent value="paste">
                  <Textarea rows={3} value={form.uasText} onChange={(e) => setForm({ ...form, uasText: e.target.value })} placeholder="Mozilla/5.0 ... (one per line)" data-testid="cpi-job-uas-input" />
                </TabsContent>
                <TabsContent value="uploaded">
                  <Select value={form.upload_ua_id} onValueChange={(v) => setForm({ ...form, upload_ua_id: v })}>
                    <SelectTrigger><SelectValue placeholder="Select uploaded UAs batch" /></SelectTrigger>
                    <SelectContent>
                      {uaUploads.length === 0 && <div className="p-3 text-xs text-muted-foreground">No uploaded UA batches. Upload via Uploaded Things page first.</div>}
                      {uaUploads.map(u => (
                        <SelectItem key={u.id} value={u.id}>
                          {u.name} · {u.os_tag || "any"} · {u.items_count || u.items?.length || 0} items
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TabsContent>
              </Tabs>
            </div>

            <div className="space-y-2">
              <Label>Lead Data (CSV: email,first,last,phone — optional)</Label>
              <Textarea rows={3} value={form.leadsText} onChange={(e) => setForm({ ...form, leadsText: e.target.value })} placeholder="john@example.com,John,Doe,+15551234567" />
            </div>

            <div className="flex items-center justify-between border rounded-lg p-3 bg-muted/30">
              <div>
                <Label className="text-sm font-medium">Auto-consume used resources</Label>
                <p className="text-xs text-muted-foreground">Each used proxy/UA gets removed from its Uploaded Things batch after the job finishes — same as Real User Traffic.</p>
              </div>
              <Switch checked={form.auto_consume} onCheckedChange={(v) => setForm({ ...form, auto_consume: v })} data-testid="cpi-job-auto-consume" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={onCreate} data-testid="cpi-job-create-btn">Create Job</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
