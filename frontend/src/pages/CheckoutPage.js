import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import axios from "axios";
import { Sparkles, ArrowLeft, Loader2 } from "lucide-react";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function CheckoutPage() {
  const { planId } = useParams();
  const navigate = useNavigate();
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ customer_name: "", customer_email: "" });

  useEffect(() => {
    axios.get(`${API}/crypto/plans`)
      .then(r => {
        const p = (r.data.plans || []).find(x => x.id === planId);
        if (!p) {
          toast.error("Plan not found");
          navigate("/pricing");
          return;
        }
        setPlan(p);
      })
      .catch(() => {
        toast.error("Failed to load plan");
        navigate("/pricing");
      })
      .finally(() => setLoading(false));
  }, [planId, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.customer_name.trim() || !form.customer_email.trim()) {
      toast.error("Please fill all fields");
      return;
    }
    setSubmitting(true);
    try {
      const r = await axios.post(`${API}/crypto/orders/create`, {
        plan_id: planId,
        customer_name: form.customer_name.trim(),
        customer_email: form.customer_email.trim().toLowerCase(),
        network: "TRC20",
      });
      navigate(`/order/${r.data.id}`);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create order");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center text-white">
        <Loader2 className="animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0f0a18] to-[#0a0a0f] text-white" data-testid="checkout-page">
      <header className="border-b border-white/5 backdrop-blur-md sticky top-0 z-50 bg-[#0a0a0f]/80">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <Sparkles className="text-[#A78BFA]" size={22} />
            <span className="text-xl font-bold tracking-tight">KREXION</span>
          </a>
          <a href="/pricing" className="text-sm text-[#A1A1AA] hover:text-white flex items-center gap-1.5" data-testid="back-to-pricing">
            <ArrowLeft size={14} /> Back to pricing
          </a>
        </div>
      </header>

      <div className="max-w-3xl mx-auto px-6 py-12">
        <h1 className="text-3xl font-bold mb-2">Checkout</h1>
        <p className="text-[#A1A1AA] text-sm mb-8">Enter your details to receive the license key by email.</p>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
          {/* Form */}
          <form onSubmit={handleSubmit} className="md:col-span-3 bg-white/[0.03] border border-white/10 rounded-xl p-6 space-y-4">
            <div>
              <label className="block text-sm text-[#A1A1AA] mb-1.5">Full name</label>
              <input
                type="text"
                required
                value={form.customer_name}
                onChange={e => setForm({ ...form, customer_name: e.target.value })}
                placeholder="John Doe"
                className="w-full bg-[#0f0a18] border border-white/10 rounded-md px-3 py-2.5 text-sm focus:outline-none focus:border-[#A78BFA] transition"
                data-testid="checkout-name-input"
              />
            </div>
            <div>
              <label className="block text-sm text-[#A1A1AA] mb-1.5">Email address</label>
              <input
                type="email"
                required
                value={form.customer_email}
                onChange={e => setForm({ ...form, customer_email: e.target.value })}
                placeholder="you@example.com"
                className="w-full bg-[#0f0a18] border border-white/10 rounded-md px-3 py-2.5 text-sm focus:outline-none focus:border-[#A78BFA] transition"
                data-testid="checkout-email-input"
              />
              <p className="text-xs text-[#71717A] mt-1">Your license key will be sent here.</p>
            </div>
            <div>
              <label className="block text-sm text-[#A1A1AA] mb-1.5">Payment network</label>
              <div className="bg-[#0f0a18] border border-white/10 rounded-md px-3 py-2.5 text-sm flex items-center justify-between">
                <span>USDT — Tron (TRC-20)</span>
                <span className="text-xs bg-[#22C55E]/20 text-[#22C55E] px-2 py-0.5 rounded">Lowest fees</span>
              </div>
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="w-full bg-[#A78BFA] text-black font-semibold py-3 rounded-md hover:bg-[#C4B5FD] transition disabled:opacity-50"
              data-testid="checkout-submit-button"
            >
              {submitting ? "Creating order…" : `Continue to payment — ${plan?.price_usdt} USDT`}
            </button>
            <p className="text-xs text-[#71717A] text-center">
              You'll get a wallet address + QR code on the next screen.
            </p>
          </form>

          {/* Summary */}
          <aside className="md:col-span-2 bg-white/[0.03] border border-white/10 rounded-xl p-6 h-fit sticky top-24">
            <h3 className="text-sm font-semibold text-[#A1A1AA] uppercase tracking-wider mb-4">Order summary</h3>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-[#A1A1AA]">Plan</span>
                <span className="font-medium">{plan?.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#A1A1AA]">Duration</span>
                <span className="font-medium">
                  {plan?.duration_days === 1 ? "1 day" : `${plan?.duration_days} days`}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#A1A1AA]">Network</span>
                <span className="font-medium">TRC-20</span>
              </div>
              <div className="border-t border-white/10 pt-3 mt-3 flex justify-between text-base">
                <span className="font-semibold">Total</span>
                <span className="font-bold">{plan?.price_usdt} USDT</span>
              </div>
            </div>
            <div className="mt-5 text-xs text-[#71717A] space-y-1">
              <p>• No subscription — one-time payment</p>
              <p>• License delivered within 30 min after payment</p>
              <p>• Refundable up to 24h if license not delivered</p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
