import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import {
  Sparkles, Zap, Shield, Globe, ArrowRight, Check, ChevronDown,
  Activity, Layers, Cpu, Lock, MailCheck,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const FEATURES = [
  {
    icon: Activity,
    title: "Real Browser Traffic",
    desc: "Drive genuine, human-like clicks through real Chrome instances — not headless bots.",
  },
  {
    icon: Layers,
    title: "Massive Proxy Pool",
    desc: "Plug in residential, ISP, or mobile proxies. Built-in checker validates them at scale.",
  },
  {
    icon: Cpu,
    title: "CPI Job Orchestrator",
    desc: "Run Cost-Per-Install campaigns across distributed worker devices with smart routing.",
  },
  {
    icon: Shield,
    title: "Form Filler + RUT",
    desc: "Auto-fill landing pages and emulate Real User Traffic patterns to stay under radar.",
  },
  {
    icon: Globe,
    title: "Geo & Carrier Targeting",
    desc: "Target by country, ISP, carrier, device, and browser fingerprint with surgical precision.",
  },
  {
    icon: MailCheck,
    title: "Email Validation Suite",
    desc: "Verify deliverability, separate cleaned lists, and feed only valid leads forward.",
  },
];

const FAQS = [
  {
    q: "How does payment work?",
    a: "We accept USDT (TRC-20) only. Pick a plan, send USDT to the wallet shown at checkout, paste your TxID, and your license is delivered to your email within 30 minutes after admin verification.",
  },
  {
    q: "Do I need a credit card or bank?",
    a: "No. Everything runs on crypto — no subscriptions, no recurring charges, no bank required. Pay only for the months you use.",
  },
  {
    q: "How many PCs can I activate?",
    a: "Starter: 1 PC. Pro: 3 PCs. Business: 10 PCs. Trial: 1 PC. Each license is tied to specific machine fingerprints.",
  },
  {
    q: "Can I get a refund?",
    a: "Yes — if your license is not delivered within 24 hours of TxID submission and on-chain confirmation, we refund in full. Otherwise sales are final.",
  },
  {
    q: "What if my payment is underpaid?",
    a: "We'll mark the order as rejected with the exact shortfall. Send the difference, resubmit your TxID, and we'll approve it.",
  },
  {
    q: "Is Krexion safe to run on my machine?",
    a: "Krexion runs locally inside its own sandboxed Chromium. It doesn't touch your system browser, cookies, or saved logins.",
  },
];

export default function HomePage() {
  const [plans, setPlans] = useState([]);
  const [openFaq, setOpenFaq] = useState(0);

  useEffect(() => {
    axios.get(`${API}/crypto/plans`)
      .then(r => setPlans(r.data.plans || []))
      .catch(() => setPlans([]));
  }, []);

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white overflow-x-hidden" data-testid="home-page">
      {/* Ambient backdrop */}
      <div className="pointer-events-none fixed inset-0 -z-10 opacity-60">
        <div className="absolute -top-32 -left-32 w-[520px] h-[520px] rounded-full bg-[#8B5CF6]/20 blur-[140px]" />
        <div className="absolute top-1/3 -right-40 w-[460px] h-[460px] rounded-full bg-[#3B82F6]/15 blur-[140px]" />
        <div className="absolute bottom-0 left-1/3 w-[380px] h-[380px] rounded-full bg-[#22C55E]/10 blur-[120px]" />
      </div>

      {/* Nav */}
      <header className="border-b border-white/5 backdrop-blur-md sticky top-0 z-50 bg-[#0a0a0f]/70">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="home-logo">
            <Sparkles className="text-[#A78BFA]" size={22} />
            <span className="text-xl font-bold tracking-tight">KREXION</span>
          </Link>
          <nav className="hidden md:flex items-center gap-7 text-sm">
            <a href="#features" className="text-[#A1A1AA] hover:text-white transition">Features</a>
            <a href="#pricing" className="text-[#A1A1AA] hover:text-white transition">Pricing</a>
            <a href="#faq" className="text-[#A1A1AA] hover:text-white transition">FAQ</a>
            <Link to="/login" className="text-[#A1A1AA] hover:text-white transition" data-testid="nav-login">Login</Link>
            <Link to="/pricing" className="bg-white text-black px-4 py-1.5 rounded-md font-medium hover:bg-gray-200 transition" data-testid="nav-get-started">
              Get started
            </Link>
          </nav>
          <Link to="/pricing" className="md:hidden bg-white text-black px-3 py-1.5 rounded-md text-xs font-medium">
            Start
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-7xl mx-auto px-6 pt-24 pb-20 text-center">
        <div className="inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 mb-7 text-xs">
          <Zap size={12} className="text-[#A78BFA]" />
          Now accepting USDT — no bank, no credit card, instant activation
        </div>
        <h1 className="text-5xl sm:text-6xl lg:text-7xl font-extrabold tracking-tight leading-[1.05] mb-6">
          Real traffic.<br/>
          <span className="bg-gradient-to-r from-[#A78BFA] via-[#C4B5FD] to-[#8B5CF6] bg-clip-text text-transparent">
            Real conversions.
          </span>
        </h1>
        <p className="text-lg text-[#A1A1AA] max-w-2xl mx-auto mb-9 leading-relaxed">
          Krexion drives genuine, browser-based traffic through real Chrome — backed by a massive
          proxy pool, smart targeting, and a CPI orchestrator built for affiliates and growth teams.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <Link
            to="/pricing"
            className="bg-[#A78BFA] text-black font-semibold px-7 py-3.5 rounded-lg hover:bg-[#C4B5FD] transition inline-flex items-center gap-2"
            data-testid="hero-cta-pricing"
          >
            See plans <ArrowRight size={16} />
          </Link>
          <a
            href="#features"
            className="border border-white/15 px-7 py-3.5 rounded-lg hover:bg-white/5 transition text-sm"
          >
            How it works
          </a>
        </div>
        <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-6 max-w-3xl mx-auto text-center">
          {[
            { v: "10M+", l: "Clicks delivered" },
            { v: "120+", l: "Countries supported" },
            { v: "99.9%", l: "Uptime" },
            { v: "<30 min", l: "License delivery" },
          ].map(s => (
            <div key={s.l}>
              <div className="text-2xl font-bold text-white">{s.v}</div>
              <div className="text-xs text-[#71717A] mt-1">{s.l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-20 scroll-mt-20">
        <div className="text-center mb-14">
          <div className="text-xs uppercase tracking-widest text-[#A78BFA] mb-3">Built for scale</div>
          <h2 className="text-3xl sm:text-4xl font-bold mb-3">Everything you need to run traffic at scale</h2>
          <p className="text-[#A1A1AA] max-w-2xl mx-auto text-sm">
            From single landing-page tests to multi-thousand-PC campaigns — one platform, fully self-hosted under your license.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              data-testid={`feature-card-${f.title.toLowerCase().replace(/\s+/g, '-')}`}
              className="group bg-white/[0.03] border border-white/10 rounded-xl p-6 hover:border-[#A78BFA]/30 hover:bg-white/[0.05] transition-all"
            >
              <div className="w-10 h-10 rounded-lg bg-[#A78BFA]/15 border border-[#A78BFA]/30 flex items-center justify-center mb-4 group-hover:bg-[#A78BFA]/25 transition">
                <f.icon className="text-[#A78BFA]" size={18} />
              </div>
              <h3 className="font-semibold mb-1.5">{f.title}</h3>
              <p className="text-sm text-[#A1A1AA] leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing (compact) */}
      <section id="pricing" className="max-w-7xl mx-auto px-6 py-20 scroll-mt-20">
        <div className="text-center mb-12">
          <div className="text-xs uppercase tracking-widest text-[#A78BFA] mb-3">Pricing</div>
          <h2 className="text-3xl sm:text-4xl font-bold mb-3">Simple plans, USDT only</h2>
          <p className="text-[#A1A1AA] text-sm max-w-xl mx-auto">
            One-time payments. Pay per month — no auto-renewal, no surprises.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {plans.length === 0 ? (
            <div className="col-span-full text-center text-[#71717A] py-10 text-sm">Loading plans…</div>
          ) : plans.map(plan => (
            <div
              key={plan.id}
              data-testid={`home-plan-${plan.id}`}
              className={`rounded-2xl p-6 flex flex-col relative ${
                plan.is_popular
                  ? "bg-gradient-to-b from-[#1e1530] to-[#0f0a18] border-2 border-[#A78BFA]"
                  : "bg-white/[0.03] border border-white/10"
              }`}
            >
              {plan.is_popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-[#A78BFA] text-black text-[10px] font-bold px-3 py-1 rounded-full">
                  MOST POPULAR
                </div>
              )}
              <h3 className="font-bold text-lg mb-1">{plan.name}</h3>
              <p className="text-xs text-[#71717A] min-h-[28px] mb-3">{plan.description}</p>
              <div className="flex items-baseline gap-1 mb-4">
                <span className="text-3xl font-bold">{plan.price_usdt}</span>
                <span className="text-xs text-[#A1A1AA]">USDT</span>
                <span className="text-xs text-[#71717A] ml-1">
                  / {plan.duration_days === 1 ? "1 day" : `${plan.duration_days} days`}
                </span>
              </div>
              <ul className="space-y-1.5 mb-5 flex-1">
                {(plan.features || []).slice(0, 4).map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-xs">
                    <Check size={12} className="text-[#A78BFA] shrink-0 mt-0.5" />
                    <span className="text-[#D4D4D8]">{f}</span>
                  </li>
                ))}
              </ul>
              <Link
                to={`/checkout/${plan.id}`}
                data-testid={`home-pick-${plan.id}`}
                className={`w-full text-center py-2 rounded-lg text-sm font-medium transition ${
                  plan.is_popular
                    ? "bg-[#A78BFA] text-black hover:bg-[#C4B5FD]"
                    : "bg-white/5 border border-white/10 hover:bg-white/10"
                }`}
              >
                Pick {plan.name}
              </Link>
            </div>
          ))}
        </div>
        <div className="text-center mt-8">
          <Link to="/pricing" className="text-sm text-[#A78BFA] hover:text-white inline-flex items-center gap-1" data-testid="see-all-plans">
            Compare full plans <ArrowRight size={13} />
          </Link>
        </div>
      </section>

      {/* How payment works */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-8 md:p-10">
          <div className="text-center mb-8">
            <div className="text-xs uppercase tracking-widest text-[#22C55E] mb-2">Crypto checkout in 3 steps</div>
            <h2 className="text-2xl font-bold">From payment to license in under 30 minutes</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {[
              { n: "1", t: "Pick your plan", d: "Choose Starter, Pro, or Business based on your scale." },
              { n: "2", t: "Send USDT-TRC20", d: "Pay from any wallet (Binance, Trust, OKX). We give you the address + QR." },
              { n: "3", t: "Submit your TxID", d: "Paste your transaction ID — we verify on-chain and email your license." },
            ].map(s => (
              <div key={s.n} className="bg-[#0a0a0f] border border-white/10 rounded-xl p-5">
                <div className="w-9 h-9 rounded-full bg-[#A78BFA] text-black font-bold flex items-center justify-center mb-3">{s.n}</div>
                <h4 className="font-semibold mb-1">{s.t}</h4>
                <p className="text-xs text-[#A1A1AA] leading-relaxed">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="max-w-3xl mx-auto px-6 py-20 scroll-mt-20">
        <div className="text-center mb-10">
          <div className="text-xs uppercase tracking-widest text-[#A78BFA] mb-3">FAQ</div>
          <h2 className="text-3xl sm:text-4xl font-bold">Questions, answered</h2>
        </div>
        <div className="space-y-3">
          {FAQS.map((item, idx) => {
            const open = openFaq === idx;
            return (
              <div
                key={idx}
                data-testid={`faq-item-${idx}`}
                className="bg-white/[0.03] border border-white/10 rounded-xl overflow-hidden"
              >
                <button
                  onClick={() => setOpenFaq(open ? -1 : idx)}
                  className="w-full flex items-center justify-between text-left px-5 py-4 hover:bg-white/[0.02] transition"
                  data-testid={`faq-toggle-${idx}`}
                >
                  <span className="font-medium text-sm">{item.q}</span>
                  <ChevronDown size={16} className={`text-[#A1A1AA] transition-transform ${open ? "rotate-180" : ""}`} />
                </button>
                {open && (
                  <div className="px-5 pb-4 text-sm text-[#A1A1AA] leading-relaxed border-t border-white/5">
                    <div className="pt-3">{item.a}</div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* CTA strip */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="bg-gradient-to-br from-[#1e1530] to-[#0a0a0f] border border-[#A78BFA]/30 rounded-2xl p-10 text-center">
          <Lock className="mx-auto mb-4 text-[#A78BFA]" size={28} />
          <h2 className="text-2xl sm:text-3xl font-bold mb-3">Ready to send real traffic?</h2>
          <p className="text-[#A1A1AA] text-sm mb-6 max-w-lg mx-auto">
            Try Krexion for 1 day at just 3 USDT. No commitment, no auto-renewal.
          </p>
          <Link
            to="/pricing"
            className="bg-[#A78BFA] text-black font-semibold px-8 py-3 rounded-lg hover:bg-[#C4B5FD] transition inline-flex items-center gap-2"
            data-testid="footer-cta-pricing"
          >
            Start your trial <ArrowRight size={16} />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 mt-10">
        <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#71717A]">
          <div className="flex items-center gap-2">
            <Sparkles className="text-[#A78BFA]" size={14} />
            <span className="font-semibold text-white">KREXION</span>
            <span>© {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center gap-5">
            <Link to="/pricing" className="hover:text-white">Pricing</Link>
            <Link to="/login" className="hover:text-white">Login</Link>
            <a href="mailto:support@krexion.com" className="hover:text-white">Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
