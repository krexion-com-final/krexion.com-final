import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Sparkles, Download, Shield, Cpu, HardDrive, Wifi,
  Check, Copy, ArrowRight, Lock,
} from "lucide-react";
import { toast } from "sonner";
import WavyBackground from "../components/WavyBackground";

const INSTALLER_URL = "/Krexion-User-Package.zip";
const INSTALLER_SHA256 = "b21b9f7d7803d3748dfa3e41d5d5a5eee4127b3b592bf2a56395275f6a1502bc";
const INSTALLER_VERSION = "1.0.4";

export default function DownloadPage() {
  const copyHash = async () => {
    try {
      await navigator.clipboard.writeText(INSTALLER_SHA256);
      toast.success("SHA-256 hash copied!");
    } catch {
      toast.error("Could not copy");
    }
  };

  return (
    <div className="min-h-screen bg-black text-white relative" data-testid="download-page">
      <WavyBackground />

      {/* Ambient backdrop — blue glow */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute -top-32 -left-32 w-[520px] h-[520px] rounded-full bg-blue-500/15 blur-[140px]" />
        <div className="absolute top-1/3 -right-40 w-[460px] h-[460px] rounded-full bg-cyan-500/10 blur-[140px]" />
      </div>

      {/* Nav */}
      <header className="border-b border-white/5 backdrop-blur-md sticky top-0 z-50 bg-black/70">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="download-logo">
            <Sparkles className="text-blue-400" size={22} />
            <span className="text-xl font-bold tracking-tight">KREXION</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <Link to="/pricing" className="text-zinc-400 hover:text-white">Pricing</Link>
            <Link to="/download" className="text-white">Download</Link>
            <Link to="/guide" className="text-zinc-400 hover:text-white">Guide</Link>
            <Link to="/login" className="text-zinc-400 hover:text-white">Login</Link>
          </nav>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-10 text-center">
        <div className="inline-flex items-center gap-2 bg-white/5 border border-white/10 rounded-full px-4 py-1.5 mb-6 text-xs">
          <Download size={12} className="text-[#3B82F6]" />
          Optional desktop install • Version {INSTALLER_VERSION} • Windows 10/11 (64-bit)
        </div>
        <h1 className="text-5xl sm:text-6xl font-bold tracking-tight mb-5 leading-tight">
          Download <span className="text-[#3B82F6]">Krexion</span>
        </h1>
        <p className="text-lg text-[#A1A1AA] max-w-2xl mx-auto mb-3">
          The Krexion dashboard works fully online at <Link to="/login" className="text-white underline hover:text-[#3B82F6]">krexion.com/login</Link>.
        </p>
        <p className="text-sm text-[#71717A] max-w-xl mx-auto mb-9">
          This installer is only needed if you want to run heavy local features like Real User Traffic, Form Filler, or CPI Worker on your own PC.
        </p>

        <a
          href={INSTALLER_URL}
          download="Krexion-User-Package.zip"
          data-testid="download-installer-button"
          className="inline-flex items-center gap-3 bg-[#3B82F6] text-black font-bold px-10 py-4 rounded-xl hover:bg-[#60A5FA] transition shadow-2xl shadow-[#2563EB]/30"
        >
          <Download size={20} />
          Download installer (.zip)
          <ArrowRight size={18} />
        </a>

        <div className="mt-4 text-xs text-[#71717A]">
          ~20 KB ZIP • Auto-downloads Krexion runtime (~600 MB) during install
        </div>
      </section>

      {/* Pre-checks */}
      <section className="max-w-5xl mx-auto px-6 py-10">
        <h2 className="text-sm uppercase tracking-widest text-[#3B82F6] mb-4 text-center">System requirements</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { icon: HardDrive, t: "20 GB free disk", d: "SSD recommended" },
            { icon: Cpu, t: "8 GB RAM", d: "16 GB for Pro/Business" },
            { icon: Shield, t: "Windows 10/11 64-bit", d: "Admin rights needed" },
            { icon: Wifi, t: "Stable internet", d: "For first-time install" },
          ].map((s, i) => (
            <div key={i} className="bg-white/[0.03] border border-white/10 rounded-xl p-5 text-center">
              <s.icon size={20} className="text-[#3B82F6] mx-auto mb-2" />
              <div className="font-semibold text-sm mb-1">{s.t}</div>
              <div className="text-xs text-[#71717A]">{s.d}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Install steps */}
      <section className="max-w-4xl mx-auto px-6 py-10">
        <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-8">
          <h2 className="text-xl font-bold mb-6">Installation in 4 steps</h2>
          <ol className="space-y-5">
            {[
              {
                t: "Download & extract",
                d: "Right-click the ZIP → \"Extract All\". Keep all files together in one folder.",
              },
              {
                t: "Run INSTALL.bat",
                d: "Double-click INSTALL.bat. Click \"Yes\" on the UAC prompt. Wait 20–30 minutes (one-time setup).",
              },
              {
                t: "Login or register",
                d: "Browser opens automatically. Use the email + password from your Krexion welcome email, or register a new account.",
              },
              {
                t: "Enter license key",
                d: "In the Setup Wizard, paste the license key from your email. Krexion activates and you're ready.",
              },
            ].map((step, i) => (
              <li key={i} className="flex gap-4">
                <div className="shrink-0 w-9 h-9 rounded-full bg-[#3B82F6] text-black font-bold flex items-center justify-center text-sm">
                  {i + 1}
                </div>
                <div className="flex-1 pt-1">
                  <div className="font-semibold mb-1">{step.t}</div>
                  <p className="text-sm text-[#A1A1AA] leading-relaxed">{step.d}</p>
                </div>
              </li>
            ))}
          </ol>

          <div className="mt-7 p-4 bg-[#F59E0B]/5 border border-[#F59E0B]/20 rounded-lg">
            <div className="flex gap-2 items-start text-sm">
              <Lock size={15} className="text-[#F59E0B] shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold text-[#F59E0B]">No license yet?</span>{" "}
                <span className="text-[#A1A1AA]">
                  Buy one at{" "}
                  <Link to="/pricing" className="text-[#3B82F6] hover:text-white underline">
                    krexion.com/pricing
                  </Link>{" "}
                  starting at 3 USDT for a 1-day trial.
                </span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* File integrity */}
      <section className="max-w-4xl mx-auto px-6 py-10">
        <div className="bg-white/[0.03] border border-white/10 rounded-xl p-6">
          <div className="flex items-center gap-2 mb-3">
            <Check size={16} className="text-[#22C55E]" />
            <span className="text-sm font-semibold">File integrity (SHA-256)</span>
          </div>
          <div className="flex items-center gap-2 bg-[#0a0a0f] border border-white/10 rounded-md p-3 font-mono text-[11px] sm:text-xs break-all">
            <span className="flex-1 text-[#3B82F6]">{INSTALLER_SHA256}</span>
            <button
              onClick={copyHash}
              className="text-[#71717A] hover:text-white shrink-0"
              data-testid="copy-sha-button"
              title="Copy hash"
            >
              <Copy size={13} />
            </button>
          </div>
          <p className="text-xs text-[#71717A] mt-3">
            Verify with PowerShell: <code className="bg-white/5 px-1.5 py-0.5 rounded text-[#3B82F6]">Get-FileHash -Algorithm SHA256 Krexion-User-Package.zip</code>
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section className="max-w-4xl mx-auto px-6 pb-20">
        <h2 className="text-lg font-bold mb-4">Common questions</h2>
        <div className="space-y-3">
          {[
            {
              q: "Will any third-party tools pop up during install?",
              a: "No. The installer runs in the background and only shows Krexion-branded progress. Helper engines run silently — you'll never see them.",
            },
            {
              q: "Can I install on multiple PCs?",
              a: "Yes, up to your plan limit (Starter: 1, Pro: 3, Business: 10, Trial: 1). Each install is bound to a unique machine fingerprint.",
            },
            {
              q: "I lost my license email — what now?",
              a: <>Login at <Link to="/login" className="text-[#3B82F6]">krexion.com/login</Link> with the credentials we emailed; your license is shown there. Or email <a href="mailto:support@krexion.com" className="text-[#3B82F6]">support@krexion.com</a>.</>,
            },
            {
              q: "Does Krexion run after PC restart?",
              a: "Yes — Krexion auto-starts in the background. Open the desktop shortcut to access the dashboard.",
            },
          ].map((f, i) => (
            <details key={i} className="bg-white/[0.03] border border-white/10 rounded-xl group" data-testid={`download-faq-${i}`}>
              <summary className="px-5 py-4 cursor-pointer text-sm font-medium hover:bg-white/[0.02] list-none flex items-center justify-between">
                {f.q}
                <span className="text-[#A1A1AA] group-open:rotate-180 transition-transform">▾</span>
              </summary>
              <div className="px-5 pb-4 text-sm text-[#A1A1AA] leading-relaxed">{f.a}</div>
            </details>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-[#71717A]">
          <div className="flex items-center gap-2">
            <Sparkles className="text-[#3B82F6]" size={14} />
            <span className="font-semibold text-white">KREXION</span>
            <span>© {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center gap-5">
            <Link to="/pricing" className="hover:text-white">Pricing</Link>
            <Link to="/guide" className="hover:text-white">Guide</Link>
            <Link to="/login" className="hover:text-white">Login</Link>
            <a href="mailto:support@krexion.com" className="hover:text-white">Support</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
