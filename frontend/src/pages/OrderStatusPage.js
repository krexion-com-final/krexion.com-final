import React, { useEffect, useState, useCallback } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { Sparkles, Copy, CheckCircle, AlertTriangle, Clock, Loader2, ExternalLink } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function timeLeft(expiresAt) {
  if (!expiresAt) return null;
  const diff = new Date(expiresAt) - new Date();
  if (diff <= 0) return "expired";
  const m = Math.floor(diff / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

export default function OrderStatusPage() {
  const { orderId } = useParams();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [txInput, setTxInput] = useState("");
  const [submittingTx, setSubmittingTx] = useState(false);
  const [tick, setTick] = useState(0);

  const fetchOrder = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/crypto/orders/${orderId}`);
      setOrder(r.data);
    } catch (err) {
      toast.error("Order not found");
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    fetchOrder();
    // Poll for status updates every 8s (admin approval will reflect)
    const id = setInterval(fetchOrder, 8000);
    return () => clearInterval(id);
  }, [fetchOrder]);

  // re-render every second to update timer
  useEffect(() => {
    const t = setInterval(() => setTick(x => x + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const copyAddress = async () => {
    try {
      await navigator.clipboard.writeText(order.wallet_address);
      toast.success("Wallet address copied!");
    } catch {
      toast.error("Could not copy");
    }
  };

  const submitTx = async () => {
    if (!txInput.trim() || txInput.trim().length < 10) {
      toast.error("Please enter a valid TxID");
      return;
    }
    setSubmittingTx(true);
    try {
      const r = await axios.post(`${API}/crypto/orders/${orderId}/submit-txid`, {
        tx_id: txInput.trim(),
      });
      setOrder(r.data);
      toast.success("TxID submitted! Admin will verify shortly.");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to submit TxID");
    } finally {
      setSubmittingTx(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-white">
        <Loader2 className="animate-spin" />
      </div>
    );
  }
  if (!order) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-white">
        Order not found
      </div>
    );
  }

  const status = order.status;
  const left = timeLeft(order.expires_at);
  const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(order.wallet_address)}&bgcolor=0a0a0f&color=ffffff&qzone=2`;

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0f0a18] to-[#0a0a0f] text-white" data-testid="order-page">
      <header className="border-b border-white/5 backdrop-blur-md sticky top-0 z-50 bg-[#0a0a0f]/80">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <Sparkles className="text-[#A78BFA]" size={22} />
            <span className="text-xl font-bold tracking-tight">KREXION</span>
          </a>
          <div className="text-xs text-[#A1A1AA]">
            Order ID: <span className="font-mono text-white">{order.id}</span>
          </div>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-10">
        {/* Status Banner */}
        {status === "approved" && (
          <div className="bg-[#22C55E]/10 border border-[#22C55E]/30 rounded-xl p-6 mb-6 text-center" data-testid="banner-approved">
            <CheckCircle className="mx-auto mb-3 text-[#22C55E]" size={40} />
            <h2 className="text-2xl font-bold text-[#22C55E] mb-2">Payment Verified — License Issued!</h2>
            <p className="text-sm text-[#A1A1AA] mb-4">Your license key is below. We've also emailed it to you.</p>
            <div className="bg-[#0f0a18] border border-white/10 rounded-lg p-4 max-w-md mx-auto">
              <div className="text-[10px] uppercase tracking-widest text-[#71717A] mb-2">Your License Key</div>
              <div className="font-mono text-lg font-bold tracking-wider break-all" data-testid="license-key-display">{order.license_key}</div>
              <button
                onClick={() => { navigator.clipboard.writeText(order.license_key); toast.success("License key copied!"); }}
                className="mt-3 text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded inline-flex items-center gap-1.5"
              >
                <Copy size={11} /> Copy
              </button>
            </div>
            <p className="text-xs text-[#71717A] mt-4">Plan: {order.plan_name} • {order.duration_days} days</p>
          </div>
        )}

        {status === "rejected" && (
          <div className="bg-[#EF4444]/10 border border-[#EF4444]/30 rounded-xl p-6 mb-6 text-center" data-testid="banner-rejected">
            <AlertTriangle className="mx-auto mb-3 text-[#EF4444]" size={40} />
            <h2 className="text-2xl font-bold text-[#EF4444] mb-2">Payment Rejected</h2>
            <p className="text-sm text-[#A1A1AA] mb-2">{order.reject_reason || "Payment could not be verified."}</p>
            <p className="text-xs text-[#71717A] mt-3">
              Need help? Reply to the rejection email or contact us.
            </p>
          </div>
        )}

        {status === "expired" && (
          <div className="bg-[#71717A]/10 border border-white/10 rounded-xl p-6 mb-6 text-center">
            <Clock className="mx-auto mb-3 text-[#71717A]" size={40} />
            <h2 className="text-xl font-bold mb-2">Order Expired</h2>
            <p className="text-sm text-[#A1A1AA]">This order's 30-minute window has passed. Please start a new order.</p>
            <a href="/pricing" className="inline-block mt-4 bg-white text-black px-4 py-2 rounded font-medium">Start over</a>
          </div>
        )}

        {(status === "pending" || status === "submitted") && (
          <>
            {/* Step indicator */}
            <div className="flex items-center justify-between mb-6 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-[#A78BFA] text-black font-bold flex items-center justify-center">1</div>
                <span>Send USDT</span>
              </div>
              <div className="flex-1 h-px bg-white/10 mx-3" />
              <div className="flex items-center gap-2">
                <div className={`w-6 h-6 rounded-full font-bold flex items-center justify-center ${status === "submitted" ? "bg-[#A78BFA] text-black" : "bg-white/10 text-white"}`}>2</div>
                <span className={status === "submitted" ? "text-white" : "text-[#71717A]"}>Submit TxID</span>
              </div>
              <div className="flex-1 h-px bg-white/10 mx-3" />
              <div className="flex items-center gap-2">
                <div className="w-6 h-6 rounded-full bg-white/10 text-[#71717A] font-bold flex items-center justify-center">3</div>
                <span className="text-[#71717A]">Get license</span>
              </div>
            </div>

            {left && left !== "expired" && status === "pending" && (
              <div className="bg-[#F59E0B]/10 border border-[#F59E0B]/30 rounded-lg p-3 mb-5 text-center text-sm">
                ⏰ Send payment within <span className="font-bold text-[#F59E0B]" data-testid="time-left">{left}</span>
              </div>
            )}

            {status === "submitted" && (
              <div className="bg-[#3B82F6]/10 border border-[#3B82F6]/30 rounded-lg p-3 mb-5 text-center text-sm" data-testid="banner-submitted">
                ⏳ TxID submitted — waiting for admin verification (usually within 30 minutes).
                This page will update automatically.
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
              {/* Payment details */}
              <div className="md:col-span-3 bg-white/[0.03] border border-white/10 rounded-xl p-6">
                <h2 className="text-lg font-bold mb-1">Pay {order.amount_usdt} USDT</h2>
                <p className="text-xs text-[#A1A1AA] mb-5">Send exactly this amount via <strong>USDT — Tron (TRC-20)</strong> network.</p>

                <div className="bg-[#0f0a18] border border-white/10 rounded-lg p-4 mb-4">
                  <div className="text-[10px] uppercase tracking-widest text-[#71717A] mb-1.5">Wallet address</div>
                  <div className="font-mono text-xs sm:text-sm break-all leading-relaxed" data-testid="wallet-address">{order.wallet_address}</div>
                  <button
                    onClick={copyAddress}
                    data-testid="copy-address-button"
                    className="mt-3 text-xs bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded inline-flex items-center gap-1.5"
                  >
                    <Copy size={11} /> Copy address
                  </button>
                </div>

                <div className="bg-[#0f0a18] border border-white/10 rounded-lg p-4 mb-4">
                  <div className="text-[10px] uppercase tracking-widest text-[#71717A] mb-1.5">Amount</div>
                  <div className="font-mono text-2xl font-bold">{order.amount_usdt} <span className="text-sm text-[#71717A]">USDT</span></div>
                </div>

                <div className="text-xs text-[#A1A1AA] space-y-1 p-3 bg-[#F59E0B]/5 border border-[#F59E0B]/20 rounded-lg">
                  <p>⚠ <strong>Important:</strong></p>
                  <p>• Use <strong>TRC-20</strong> network only (BEP-20 / ERC-20 won't reach us)</p>
                  <p>• Send <strong>exactly {order.amount_usdt}</strong> USDT (or you'll need to send the difference)</p>
                  <p>• Save your <strong>TxID</strong> after sending — you'll need it below</p>
                </div>
              </div>

              {/* QR code */}
              <div className="md:col-span-2 bg-white/[0.03] border border-white/10 rounded-xl p-6 text-center">
                <div className="text-[10px] uppercase tracking-widest text-[#71717A] mb-3">Scan QR with wallet app</div>
                <img src={qrUrl} alt="QR Code" className="mx-auto rounded-lg border border-white/10" data-testid="qr-code" />
                <p className="text-xs text-[#71717A] mt-3">Trust Wallet, Binance, OKX, etc.</p>
              </div>
            </div>

            {/* TxID submit */}
            {status === "pending" && (
              <div className="mt-6 bg-white/[0.03] border border-white/10 rounded-xl p-6">
                <h3 className="font-bold mb-1">Step 2: Submit your TxID after sending</h3>
                <p className="text-xs text-[#A1A1AA] mb-4">After your transaction confirms (1-3 min), paste the TxID here. We'll verify and email your license key.</p>
                <div className="flex flex-col sm:flex-row gap-2">
                  <input
                    type="text"
                    placeholder="0xabc123... or transaction hash"
                    value={txInput}
                    onChange={e => setTxInput(e.target.value)}
                    className="flex-1 bg-[#0f0a18] border border-white/10 rounded-md px-3 py-2.5 text-sm font-mono focus:outline-none focus:border-[#A78BFA]"
                    data-testid="txid-input"
                  />
                  <button
                    onClick={submitTx}
                    disabled={submittingTx}
                    className="bg-[#A78BFA] text-black font-semibold px-6 py-2.5 rounded-md hover:bg-[#C4B5FD] transition disabled:opacity-50"
                    data-testid="submit-txid-button"
                  >
                    {submittingTx ? "Submitting…" : "Submit TxID"}
                  </button>
                </div>
              </div>
            )}

            {status === "submitted" && order.tx_id && (
              <div className="mt-6 bg-white/[0.03] border border-white/10 rounded-xl p-4 text-xs">
                <div className="text-[#71717A] mb-1">Submitted TxID:</div>
                <div className="font-mono break-all text-[#A78BFA]">{order.tx_id}</div>
                <a
                  href={`https://tronscan.org/#/transaction/${order.tx_id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#A78BFA] hover:text-white inline-flex items-center gap-1 mt-2 text-xs"
                >
                  View on Tronscan <ExternalLink size={10} />
                </a>
              </div>
            )}
          </>
        )}

        {/* Order summary */}
        <div className="mt-6 bg-white/[0.02] border border-white/5 rounded-xl p-4 text-xs">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div><div className="text-[#71717A]">Plan</div><div className="font-medium">{order.plan_name}</div></div>
            <div><div className="text-[#71717A]">Customer</div><div className="font-medium truncate">{order.customer_name}</div></div>
            <div><div className="text-[#71717A]">Email</div><div className="font-medium truncate">{order.customer_email}</div></div>
            <div><div className="text-[#71717A]">Status</div><div className="font-medium capitalize">{status}</div></div>
          </div>
        </div>
      </div>
    </div>
  );
}
