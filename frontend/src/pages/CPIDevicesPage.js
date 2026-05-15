import { useEffect, useState } from "react";
import axios from "axios";
import { Trash2, Smartphone, Apple, AlertCircle, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import useVisibleInterval from "../hooks/useVisibleInterval";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const dot = (s) => ({
  online: "bg-green-500",
  busy: "bg-yellow-500",
  offline: "bg-gray-400",
  error: "bg-red-500",
  needs_attention: "bg-amber-500",
}[s] || "bg-gray-400");

export default function CPIDevicesPage() {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);

  const token = localStorage.getItem("token");
  const auth = { headers: { Authorization: `Bearer ${token}` } };

  const load = async () => {
    try {
      const r = await axios.get(`${API}/cpi/devices`, auth);
      setDevices(r.data || []);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to load devices");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);
  useVisibleInterval(load, 5000);

  const onDelete = async (id) => {
    if (!window.confirm("Remove this device? Worker will need to re-register.")) return;
    try {
      await axios.delete(`${API}/cpi/devices/${id}`, auth);
      toast.success("Device removed");
      load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  const isIos = (t) => t === "ios_real";
  const successRate = (d) => d.total_installs ? Math.round(((d.successful_installs || 0) / d.total_installs) * 100) : 0;

  return (
    <div className="space-y-6" data-testid="cpi-devices-page">
      <div>
        <h1 className="text-2xl font-bold">CPI Devices</h1>
        <p className="text-sm text-muted-foreground">Phones connected to your home-PC worker. Devices auto-register on first heartbeat.</p>
      </div>

      {loading ? (
        <div className="text-sm text-muted-foreground">Loading…</div>
      ) : devices.length === 0 ? (
        <div className="border rounded-lg p-8 text-center space-y-3">
          <AlertCircle className="h-10 w-10 mx-auto text-muted-foreground" />
          <div className="text-sm text-muted-foreground">No devices registered yet.</div>
          <div className="text-xs text-muted-foreground max-w-md mx-auto">
            Run <code className="bg-muted px-1 py-0.5 rounded">KREXION-CPI-WORKER-START.bat</code> on your home PC.
            The worker will detect connected Android (adb) and iOS (libimobiledevice) devices and register them automatically.
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {devices.map((d) => (
            <div key={d.id} className="border rounded-lg p-4 space-y-3" data-testid={`cpi-device-card-${d.id}`}>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  {isIos(d.device_type) ? <Apple className="h-5 w-5" /> : <Smartphone className="h-5 w-5" />}
                  <div>
                    <div className="font-medium">{d.label}</div>
                    <div className="text-xs text-muted-foreground">{d.model || d.device_type}</div>
                  </div>
                </div>
                <span className={`h-2 w-2 rounded-full ${dot(d.status)}`} title={d.status}></span>
              </div>
              <div className="flex flex-wrap gap-1.5 text-xs">
                <Badge variant="outline">{d.device_type}</Badge>
                {d.os_version && <Badge variant="outline">{d.os_version}</Badge>}
                <Badge variant={d.status === "online" ? "default" : "secondary"}>{d.status}</Badge>
              </div>
              {d.needs_action && (
                <div className="text-xs text-amber-500 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" /> {d.needs_action}
                </div>
              )}
              <div className="grid grid-cols-3 gap-2 text-xs pt-2 border-t">
                <div>
                  <div className="text-muted-foreground">Installs</div>
                  <div className="font-medium">{d.total_installs || 0}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Success</div>
                  <div className="font-medium">{d.successful_installs || 0}</div>
                </div>
                <div>
                  <div className="text-muted-foreground">Rate</div>
                  <div className="font-medium">{successRate(d)}%</div>
                </div>
              </div>
              <div className="flex justify-between items-center pt-1">
                <span className="text-[10px] text-muted-foreground font-mono">{d.device_id.slice(0, 14)}</span>
                <Button size="sm" variant="ghost" onClick={() => onDelete(d.id)} data-testid={`cpi-device-delete-${d.id}`}>
                  <Trash2 className="h-3 w-3" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
