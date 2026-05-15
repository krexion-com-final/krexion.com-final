import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { Check, Sparkles, Zap, ArrowRight } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PricingPage() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    axios.get(`${API}/crypto/plans`)
      .then(r => setPlans(r.data.plans || []))
      .catch(() => setPlans([]))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = (planId) => {
    navigate(`/checkout/${planId}`);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-[#0a0a0f] via-[#0f0a18] to-[#0a0a0f] text-white" data-testid="pricing-page">
      {/* Header */}
      <header className="border-b border-white/5 backdrop-blur-md sticky top-0 z-50 bg-[#0a0a0f]/80">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <Sparkles className="text-[#A78BFA]" size={22} />
            <span className="text-xl font-bold tracking-tight">KREXION</span>
          </a>
          <nav className="flex items-center gap-6 text-sm">
            <a href="/" className="text-[#A1A1AA] hover:text-white transition">Home</a>
            <a href="/pricing" className="text-white">Pricing</a>
            <a href="/login" className="text-[#A1A1AA] hover:text-white transition">Login</a>
            <a href="/login" className="bg-white text-black px-4 py-1.5 rounded-md font-medium hover:bg-gray-200 transition" data-testid="header-signup-button">
              Sign Up
            </a>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-20 pb-12 text-center">
        <div className="inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-1 mb-6 text-xs">
          <Zap size={12} className="text-[#A78BFA]" />
          Pay with USDT • No bank required • Instant activation
        </div>
        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight mb-4">
          Simple, transparent <span className="text-[#A78BFA]">pricing</span>
        </h1>
        <p className="text-lg text-[#A1A1AA] max-w-2xl mx-auto">
          Pick a plan, pay with USDT-TRC20 from any wallet, and start sending real traffic in minutes.
          No subscriptions, no hidden fees.
        </p>
      </section>

      {/* Plans */}
      <section className="max-w-7xl mx-auto px-6 pb-20">
        {loading ? (
          <div className="text-center text-[#71717A] py-20">Loading plans…</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
            {plans.map((plan) => (
              <div
                key={plan.id}
                data-testid={`plan-card-${plan.id}`}
                className={`relative rounded-2xl p-6 flex flex-col transition-all hover:scale-[1.02] ${
                  plan.is_popular
                    ? "bg-gradient-to-b from-[#1e1530] to-[#0f0a18] border-2 border-[#A78BFA] shadow-2xl shadow-[#8B5CF6]/20"
                    : "bg-white/[0.03] border border-white/10 hover:border-white/20"
                }`}
              >
                {plan.is_popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#A78BFA] text-black text-xs font-bold px-3 py-1 rounded-full">
                    MOST POPULAR
                  </div>
                )}
                <div className="mb-4">
                  <h3 className="text-xl font-bold mb-1">{plan.name}</h3>
                  <p className="text-xs text-[#A1A1AA] min-h-[32px]">{plan.description}</p>
                </div>

                <div className="mb-5">
                  <div className="flex items-baseline gap-1">
                    <span className="text-4xl font-bold">{plan.price_usdt}</span>
                    <span className="text-[#A1A1AA] text-sm">USDT</span>
                  </div>
                  <div className="text-xs text-[#71717A] mt-1">
                    {plan.duration_days === 1 ? "1 day access" : `${plan.duration_days} days access`}
                  </div>
                </div>

                <ul className="space-y-2 mb-6 flex-1">
                  {(plan.features || []).map((f, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <Check size={15} className="text-[#A78BFA] shrink-0 mt-0.5" />
                      <span className="text-[#D4D4D8]">{f}</span>
                    </li>
                  ))}
                </ul>

                <button
                  onClick={() => handleSelect(plan.id)}
                  data-testid={`select-plan-${plan.id}`}
                  className={`w-full py-2.5 rounded-lg font-medium transition-all flex items-center justify-center gap-2 ${
                    plan.is_popular
                      ? "bg-[#A78BFA] text-black hover:bg-[#C4B5FD]"
                      : "bg-white/5 text-white border border-white/10 hover:bg-white/10"
                  }`}
                >
                  Get started <ArrowRight size={15} />
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* FAQ-lite */}
      <section className="max-w-4xl mx-auto px-6 pb-20">
        <h2 className="text-2xl font-bold mb-6 text-center">How payment works</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { n: "1", t: "Pick a plan", d: "Choose the plan that fits your scale." },
            { n: "2", t: "Pay with USDT", d: "Send USDT-TRC20 from any wallet (Binance, Trust, etc.) to our address." },
            { n: "3", t: "Get your license", d: "Submit your TxID — we verify and email your license key within minutes." },
          ].map((s) => (
            <div key={s.n} className="bg-white/[0.03] border border-white/10 rounded-xl p-5">
              <div className="w-8 h-8 rounded-full bg-[#A78BFA] text-black font-bold flex items-center justify-center mb-3">{s.n}</div>
              <h4 className="font-semibold mb-1">{s.t}</h4>
              <p className="text-sm text-[#A1A1AA]">{s.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 text-center text-xs text-[#71717A]">
        © {new Date().getFullYear()} Krexion. Engineered for traffic that converts.
      </footer>
    </div>
  );
}
