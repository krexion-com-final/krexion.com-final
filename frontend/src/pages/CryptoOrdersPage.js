import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  RefreshCw, CheckCircle, XCircle, ExternalLink, Search, Copy,
  ArrowLeft, AlertTriangle, Loader2,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from "../components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CryptoOrdersPage() {
  const navigate = useNavigate();
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("submitted");
  const [search, setSearch] = useState("");
  const [verifyingId, setVerifyingId] = useState(null);
  const [actionId, setActionId] = useState(null);
  const [verifyResult, setVerifyResult] = useState(null);
  const [rejectDialog, setRejectDialog] = useState({ open: false, order: null, reason: "" });

  const adminToken = localStorage.getItem("adminToken") || localStorage.getItem("admin_token") || localStorage.getItem("token");

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params = filter && filter !== "all" ? `?status=${filter}` : "";
      const r = await axios.get(`${API}/admin/crypto/orders${params}`, {
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      setOrders(r.data.orders || []);
    } catch (err) {
      if (err.response?.status === 401) {
        toast.error("Session expired. Please login again.");
        navigate("/admin");
      } else {
        toast.error("Failed to load orders");
      }
    } finally {
      setLoading(false);
    }
  }, [filter, adminToken, navigate]);

  useEffect(() => { fetchOrders(); }, [fetchOrders]);

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(fetchOrders, 30000);
    return () => clearInterval(id);
  }, [fetchOrders]);

  const handleVerify = async (orderId) => {
    setVerifyingId(orderId);
    setVerifyResult(null);
    try {
      const r = await axios.get(`${API}/admin/crypto/orders/${orderId}/verify-onchain`, {
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      setVerifyResult({ orderId, ...r.data });
      if (r.data.ok) toast.success("On-chain verified ✓");
      else toast.warning(r.data.reason || "Verification failed");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Verification failed");
    } finally {
      setVerifyingId(null);
    }
  };

  const handleApprove = async (orderId) => {
    if (!window.confirm("Approve this order? A license key will be generated and (when email is configured) emailed to the customer.")) return;
    setActionId(orderId);
    try {
      const r = await axios.post(`${API}/admin/crypto/orders/${orderId}/approve`, {}, {
        headers: { Authorization: `Bearer ${adminToken}` },
      });
      toast.success(`Approved! License: ${r.data.license_key}`);
      fetchOrders();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Approve failed");
    } finally {
      setActionId(null);
    }
  };

  const handleReject = async () => {
    if (!rejectDialog.reason.trim()) {
      toast.error("Please provide a reason");
      return;
    }
    setActionId(rejectDialog.order.id);
    try {
      await axios.post(
        `${API}/admin/crypto/orders/${rejectDialog.order.id}/reject`,
        { reason: rejectDialog.reason.trim() },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success("Order rejected");
      setRejectDialog({ open: false, order: null, reason: "" });
      fetchOrders();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Reject failed");
    } finally {
      setActionId(null);
    }
  };

  const copy = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied!");
  };

  const filtered = orders.filter(o => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      o.id.toLowerCase().includes(q) ||
      o.customer_email.toLowerCase().includes(q) ||
      o.customer_name.toLowerCase().includes(q) ||
      (o.tx_id || "").toLowerCase().includes(q)
    );
  });

  const counts = {
    submitted: orders.filter(o => o.status === "submitted").length,
    pending: orders.filter(o => o.status === "pending").length,
    approved: orders.filter(o => o.status === "approved").length,
    rejected: orders.filter(o => o.status === "rejected").length,
    expired: orders.filter(o => o.status === "expired").length,
  };

  const statusBadge = (s) => {
    const m = {
      pending: { bg: "bg-[#71717A]", text: "Pending" },
      submitted: { bg: "bg-[#F59E0B] text-black", text: "Awaiting Verification" },
      approved: { bg: "bg-[#22C55E]", text: "Approved" },
      rejected: { bg: "bg-[#EF4444]", text: "Rejected" },
      expired: { bg: "bg-[#52525B]", text: "Expired" },
    };
    const c = m[s] || m.pending;
    return <Badge className={`${c.bg} text-xs`}>{c.text}</Badge>;
  };

  return (
    <div className="min-h-screen bg-[var(--brand-bg)] p-6 text-white" data-testid="crypto-orders-page">
      <div className="max-w-7xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/admin/dashboard")}
              className="text-[#A1A1AA] hover:text-white mb-2"
              data-testid="back-to-admin"
            >
              <ArrowLeft size={14} className="mr-1" /> Back to Admin
            </Button>
            <h1 className="text-3xl font-bold">Crypto Orders</h1>
            <p className="text-sm text-[#A1A1AA] mt-1">Verify USDT payments and issue licenses</p>
          </div>
          <Button onClick={fetchOrders} variant="outline" className="border-[var(--brand-border)]" data-testid="refresh-orders">
            <RefreshCw size={14} className={`mr-2 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>

        {/* Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {[
            { k: "submitted", l: "Awaiting", color: "text-[#F59E0B]" },
            { k: "pending", l: "Pending", color: "text-[#A1A1AA]" },
            { k: "approved", l: "Approved", color: "text-[#22C55E]" },
            { k: "rejected", l: "Rejected", color: "text-[#EF4444]" },
            { k: "expired", l: "Expired", color: "text-[#52525B]" },
          ].map(c => (
            <Card
              key={c.k}
              className={`bg-[var(--brand-card)] border-[var(--brand-border)] cursor-pointer hover:border-white/20 transition ${filter === c.k ? "ring-1 ring-[#A78BFA]" : ""}`}
              onClick={() => setFilter(c.k)}
              data-testid={`stat-${c.k}`}
            >
              <CardContent className="p-4">
                <div className={`text-2xl font-bold ${c.color}`}>{counts[c.k]}</div>
                <div className="text-xs text-[#A1A1AA] mt-1">{c.l}</div>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Filter + Search */}
        <Card className="bg-[var(--brand-card)] border-[var(--brand-border)] mb-4">
          <CardContent className="p-4 flex items-center gap-3 flex-wrap">
            <Tabs value={filter} onValueChange={setFilter}>
              <TabsList className="bg-[#0a0a0f] border border-[var(--brand-border)] p-1">
                <TabsTrigger value="submitted" data-testid="filter-submitted">Awaiting</TabsTrigger>
                <TabsTrigger value="pending" data-testid="filter-pending">Pending</TabsTrigger>
                <TabsTrigger value="approved" data-testid="filter-approved">Approved</TabsTrigger>
                <TabsTrigger value="rejected" data-testid="filter-rejected">Rejected</TabsTrigger>
                <TabsTrigger value="all" data-testid="filter-all">All</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="flex-1 min-w-[200px] relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#71717A]" />
              <Input
                placeholder="Search by Order ID, email, name, or TxID…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-9 bg-[#0a0a0f] border-[var(--brand-border)]"
                data-testid="search-orders"
              />
            </div>
          </CardContent>
        </Card>

        {/* Orders list */}
        <Card className="bg-[var(--brand-card)] border-[var(--brand-border)]">
          <CardContent className="p-0">
            {loading ? (
              <div className="p-12 text-center"><Loader2 className="animate-spin mx-auto text-[#A1A1AA]" /></div>
            ) : filtered.length === 0 ? (
              <div className="p-12 text-center text-[#A1A1AA]">No orders match the current filter.</div>
            ) : (
              <div className="divide-y divide-[var(--brand-border)]">
                {filtered.map(order => (
                  <div key={order.id} className="p-4 hover:bg-white/[0.02] transition" data-testid={`order-row-${order.id}`}>
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 items-start">
                      {/* Left: order info */}
                      <div className="lg:col-span-5 space-y-1.5">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs bg-white/10 px-2 py-0.5 rounded">{order.id}</span>
                          {statusBadge(order.status)}
                          <Badge className="bg-[#A78BFA] text-black text-xs">{order.plan_name}</Badge>
                          <span className="text-xs text-[#71717A]">{order.amount_usdt} USDT</span>
                        </div>
                        <div className="text-sm font-medium">{order.customer_name}</div>
                        <div className="text-xs text-[#A1A1AA]">{order.customer_email}</div>
                        <div className="text-xs text-[#71717A]">
                          {new Date(order.created_at).toLocaleString()}
                        </div>
                      </div>

                      {/* Middle: TxID */}
                      <div className="lg:col-span-4 text-xs">
                        {order.tx_id ? (
                          <>
                            <div className="text-[#71717A] mb-1">TxID</div>
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono text-[#A78BFA] truncate flex-1">{order.tx_id}</span>
                              <button onClick={() => copy(order.tx_id)} className="text-[#71717A] hover:text-white">
                                <Copy size={11} />
                              </button>
                              <a
                                href={`https://tronscan.org/#/transaction/${order.tx_id}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[#A78BFA] hover:text-white"
                                title="View on Tronscan"
                              >
                                <ExternalLink size={11} />
                              </a>
                            </div>
                            {verifyResult?.orderId === order.id && (
                              <div className={`mt-2 text-[10px] p-2 rounded ${verifyResult.ok ? "bg-[#22C55E]/10 text-[#22C55E]" : "bg-[#EF4444]/10 text-[#EF4444]"}`}>
                                {verifyResult.ok
                                  ? `✓ ${verifyResult.actual_amount} USDT received • ${verifyResult.confirmed ? "Confirmed" : "Pending confirms"}`
                                  : `✗ ${verifyResult.reason}`}
                              </div>
                            )}
                          </>
                        ) : (
                          <div className="text-[#71717A]">No TxID submitted yet</div>
                        )}
                        {order.license_key && (
                          <div className="mt-2">
                            <div className="text-[#71717A] mb-1">License</div>
                            <div className="font-mono text-[#22C55E] text-xs flex items-center gap-1.5">
                              {order.license_key}
                              <button onClick={() => copy(order.license_key)} className="text-[#71717A] hover:text-white">
                                <Copy size={10} />
                              </button>
                            </div>
                          </div>
                        )}
                        {order.reject_reason && (
                          <div className="mt-2 text-[10px] p-2 rounded bg-[#EF4444]/10 text-[#EF4444]">
                            ✗ {order.reject_reason}
                          </div>
                        )}
                      </div>

                      {/* Right: actions */}
                      <div className="lg:col-span-3 flex flex-col items-end gap-1.5">
                        {order.status === "submitted" && (
                          <>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleVerify(order.id)}
                              disabled={verifyingId === order.id}
                              className="border-[var(--brand-border)] w-full"
                              data-testid={`verify-${order.id}`}
                            >
                              {verifyingId === order.id ? <Loader2 size={12} className="animate-spin mr-1.5" /> : null}
                              Verify on-chain
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => handleApprove(order.id)}
                              disabled={actionId === order.id}
                              className="bg-[#22C55E] hover:bg-[#16A34A] w-full"
                              data-testid={`approve-${order.id}`}
                            >
                              <CheckCircle size={12} className="mr-1.5" /> Approve & issue license
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => setRejectDialog({ open: true, order, reason: "" })}
                              disabled={actionId === order.id}
                              className="border-[#EF4444]/30 text-[#EF4444] hover:bg-[#EF4444]/10 w-full"
                              data-testid={`reject-${order.id}`}
                            >
                              <XCircle size={12} className="mr-1.5" /> Reject
                            </Button>
                          </>
                        )}
                        {order.status === "pending" && (
                          <div className="text-[10px] text-[#71717A] flex items-center gap-1">
                            <AlertTriangle size={11} /> Waiting for customer to send payment
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Reject dialog */}
      <Dialog open={rejectDialog.open} onOpenChange={open => setRejectDialog({ ...rejectDialog, open })}>
        <DialogContent className="bg-[var(--brand-card)] border-[var(--brand-border)]">
          <DialogHeader>
            <DialogTitle>Reject Order</DialogTitle>
            <DialogDescription>
              Reason will be emailed to the customer. Be specific so they can correct & retry.
            </DialogDescription>
          </DialogHeader>
          <textarea
            value={rejectDialog.reason}
            onChange={e => setRejectDialog({ ...rejectDialog, reason: e.target.value })}
            placeholder="e.g. Underpayment — received only 75 USDT, need 80. Please send 5 USDT difference and resubmit TxID."
            rows={4}
            className="w-full bg-[#0a0a0f] border border-[var(--brand-border)] rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[#A78BFA]"
            data-testid="reject-reason-input"
          />
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setRejectDialog({ open: false, order: null, reason: "" })}>Cancel</Button>
            <Button onClick={handleReject} className="bg-[#EF4444] hover:bg-[#DC2626]" data-testid="confirm-reject">
              Reject Order
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
