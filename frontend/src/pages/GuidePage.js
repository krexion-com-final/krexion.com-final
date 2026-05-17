import React, { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Sparkles, ArrowRight, ChevronDown, CheckCircle2, AlertCircle,
  Download, Wallet, Mail, Monitor, Activity, Settings,
  HelpCircle, Copy, ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import WavyBackground from "../components/WavyBackground";

const TOC = [
  { id: "overview", label: "1. Krexion Kya Hai?" },
  { id: "buy", label: "2. License Khareedna" },
  { id: "login", label: "3. Pehli Baar Login" },
  { id: "cloud", label: "4. Cloud Dashboard Use Karna" },
  { id: "links", label: "5. Tracking Links Banana" },
  { id: "install", label: "6. Desktop App Install" },
  { id: "heavy", label: "7. Heavy Features" },
  { id: "update", label: "8. Updates" },
  { id: "troubleshoot", label: "9. Troubleshooting" },
  { id: "faq", label: "10. FAQs" },
];

const copy = (text, msg = "Copied!") => {
  navigator.clipboard.writeText(text);
  toast.success(msg);
};

function Section({ id, title, icon: Icon, children }) {
  return (
    <motion.section
      id={id}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.5 }}
      className="scroll-mt-24 mb-14"
    >
      <h2 className="text-2xl font-bold flex items-center gap-3 mb-5 text-white">
        <Icon className="text-blue-400" size={22} />
        {title}
      </h2>
      <div className="text-zinc-300 leading-relaxed space-y-4">{children}</div>
    </motion.section>
  );
}

function Step({ n, title, children }) {
  return (
    <div className="flex gap-4 items-start mb-5">
      <div className="shrink-0 w-9 h-9 rounded-full bg-blue-500 text-white font-bold flex items-center justify-center shadow-lg shadow-blue-500/40">
        {n}
      </div>
      <div className="flex-1 pt-1.5">
        <h4 className="font-semibold text-white mb-1.5">{title}</h4>
        <div className="text-sm text-zinc-400 leading-relaxed">{children}</div>
      </div>
    </div>
  );
}

function Box({ kind = "info", title, children }) {
  const styles = {
    info: "bg-blue-500/10 border-blue-500/30 text-blue-100",
    warn: "bg-yellow-500/10 border-yellow-500/30 text-yellow-100",
    danger: "bg-red-500/10 border-red-500/30 text-red-100",
    success: "bg-green-500/10 border-green-500/30 text-green-100",
  };
  return (
    <div className={`border rounded-lg p-4 my-4 ${styles[kind]}`}>
      {title && <div className="font-semibold text-sm mb-1">{title}</div>}
      <div className="text-sm leading-relaxed">{children}</div>
    </div>
  );
}

const FAQS = [
  { q: "INSTALL.bat double-click karne par window turant band ho jaati hai — kya karoon?",
    a: "Sabse common wajah: aap ne ZIP extract nahi ki. ZIP file pe right-click → \"Extract All...\" karein → naye folder ke ANDER se INSTALL.bat chalayein. Doosri wajah: UAC popup \"No\" ho gaya — INSTALL.bat pe right-click → \"Run as administrator\" select karein.",
  },
  { q: "Welcome email nahi mila — kya karoon?",
    a: "Spam / Promotions folder check karein. Resend domain verified hai so email guaranteed deliver hoti hai. Agar 1 hour ke baad bhi nahi mile, support@krexion.com pe order ID + email forward karein.",
  },
  { q: "USDT bhej diya but order ab tak Pending hai — itna time kyu?",
    a: "Tron blockchain pe confirmation 1-2 min mein hoti hai. Admin manually approve karta hai — max 30 min (peak time pe 1 hour). 1 hour ke baad bhi pending? Support contact karein.",
  },
  { q: "Maine kam USDT bhej diya — abhi kya?",
    a: "Admin reject kar dega \"Underpaid\" reason ke saath aur aap ko email aayegi. Difference amount aap ke wallet pe wapas nahi aayegi — naya order create karein full amount ke liye, ya difference bhejne ki request support se karein.",
  },
  { q: "Krexion install ke baad Docker icon dikha — yeh kya hai?",
    a: "Yeh shouldn't happen — humara installer Docker Desktop ko fully hide karta hai. Agar dikh raha hai to STARThere.txt mein given email pe screenshot bhejein, hum fix bhej denge. Aap ki branding hamesha sirf Krexion hi rehni chahiye.",
  },
  { q: "License key kahan daalein?",
    a: "Direct license key daalne ki zaroorat nahi — welcome email mein jo email/password aaya hai, wahi krexion.com/login pe daalein → dashboard automatically activate ho jata hai.",
  },
  { q: "1 license multiple PCs pe use kar sakta hun?",
    a: "Cloud dashboard (krexion.com) unlimited devices se access hota hai. Desktop install per-plan: Starter 1 PC, Pro 3 PCs, Business 10 PCs, Trial 1 PC.",
  },
  { q: "Refund policy?",
    a: "Agar payment confirm ke 24 hours mein license nahi mile → 100% refund. Otherwise sale final hai (crypto ka nature hai).",
  },
];

export default function GuidePage() {
  const [openFaq, setOpenFaq] = useState(0);

  return (
    <div className="min-h-screen bg-black text-white relative" data-testid="guide-page">
      <WavyBackground />

      {/* Ambient blue glows */}
      <div className="pointer-events-none fixed inset-0 -z-10">
        <div className="absolute -top-32 -left-32 w-[420px] h-[420px] rounded-full bg-blue-500/15 blur-[120px]" />
        <div className="absolute bottom-0 right-0 w-[420px] h-[420px] rounded-full bg-blue-600/10 blur-[140px]" />
      </div>

      {/* Nav */}
      <header className="border-b border-white/5 backdrop-blur-md sticky top-0 z-50 bg-black/70">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <Sparkles className="text-blue-400" size={22} />
            <span className="text-xl font-bold tracking-tight">KREXION</span>
          </Link>
          <nav className="flex items-center gap-5 text-sm">
            <Link to="/pricing" className="text-zinc-400 hover:text-white">Pricing</Link>
            <Link to="/download" className="text-zinc-400 hover:text-white">Download</Link>
            <Link to="/guide" className="text-white">Guide</Link>
            <Link to="/login" className="text-zinc-400 hover:text-white">Login</Link>
          </nav>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 pt-12 pb-20">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 bg-blue-500/10 border border-blue-500/30 rounded-full px-4 py-1.5 mb-5 text-xs">
            <HelpCircle size={12} className="text-blue-400" />
            Complete Customer Guide — Roman Urdu + English
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight mb-4">
            Krexion <span className="bg-clip-text text-transparent" style={{ backgroundImage: "linear-gradient(90deg, #60A5FA, #3B82F6, #93C5FD)" }}>A to Z</span> Guide
          </h1>
          <p className="text-zinc-400 max-w-2xl mx-auto text-sm">
            Pehli khareed se daily use tak — sab kuch step-by-step. Koi confusion ho to yeh guide khol kar dekho.
          </p>
        </motion.div>

        <div className="grid lg:grid-cols-[260px_1fr] gap-10">
          {/* TOC sidebar */}
          <aside className="lg:sticky lg:top-24 self-start">
            <div className="bg-white/[0.03] border border-white/10 rounded-xl p-4 mb-4">
              <div className="text-xs uppercase tracking-widest text-blue-400 mb-3">Contents</div>
              <ul className="space-y-1.5 text-sm">
                {TOC.map(t => (
                  <li key={t.id}>
                    <a
                      href={`#${t.id}`}
                      className="text-zinc-400 hover:text-white block py-1 transition"
                      data-testid={`toc-${t.id}`}
                    >
                      {t.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
            <a
              href="https://krexion.com/Krexion-User-Package.zip"
              download
              className="block bg-blue-500 hover:bg-blue-400 text-white font-semibold px-4 py-2.5 rounded-lg text-center text-sm shadow-lg shadow-blue-500/30 transition"
              data-testid="guide-download-btn"
            >
              <Download size={14} className="inline mr-1.5" />
              Download Installer
            </a>
          </aside>

          {/* Content */}
          <main className="min-w-0">
            <Section id="overview" title="1. Krexion Kya Hai?" icon={Sparkles}>
              <p>Krexion ek complete traffic management SaaS platform hai. Aap ko milta hai:</p>
              <ul className="list-disc list-inside space-y-1.5 ml-2 text-sm text-zinc-400">
                <li><strong className="text-white">Cloud Dashboard</strong> at krexion.com — kahin se b login, kisi b device se</li>
                <li><strong className="text-white">Tracking Links</strong> at krexion.com/r/xxx — 24/7 live, aap ka PC band ho to bhi</li>
                <li><strong className="text-white">Proxy Check</strong> — 1000+ proxies parallel, aap ke PC pe chalega</li>
                <li><strong className="text-white">Real User Traffic</strong> — real Chrome instances, not bots</li>
                <li><strong className="text-white">Form Filler + CPI Worker</strong> — sab tools ek package mein</li>
              </ul>
              <Box kind="info">
                Cloud (online) + Local install — dono mil ke ek hybrid SaaS banate hain. 95% kaam aap krexion.com pe online karte hain. Sirf heavy features ke liye desktop app PC pe install hota hai.
              </Box>
            </Section>

            <Section id="buy" title="2. License Khareedna (USDT-TRC20)" icon={Wallet}>
              <Step n="1" title="Plan choose karein">
                <Link to="/pricing" className="text-blue-400 hover:underline">krexion.com/pricing</Link> visit karein — 4 plans hain:
                <ul className="list-disc list-inside mt-2 space-y-0.5">
                  <li>Trial — 3 USDT / 1 day (test ke liye)</li>
                  <li>Starter — 50 USDT / month / 1 PC</li>
                  <li>Pro — 80 USDT / month / 3 PCs ⭐ Popular</li>
                  <li>Business — 200 USDT / month / 10 PCs</li>
                </ul>
              </Step>
              <Step n="2" title="Checkout form bharein">
                Apna naam + email daalein. <strong className="text-yellow-400">SAHI EMAIL DAALEIN</strong> — login credentials + license isi pe aayenge.
              </Step>
              <Step n="3" title="USDT (TRC-20) bhejein">
                Wallet address dikhayi jaayegi + QR code. Binance / Trust / OKX / Tronlink se{" "}
                <strong className="text-yellow-400">EXACT amount</strong> bhejein.{" "}
                <strong className="text-red-400">Network ZAROORI TRC-20 ho</strong> (BEP-20 / ERC-20 NOT accepted).
                <Box kind="warn" title="Tip">
                  Wallet address copy karne se pehle phir se check karein. Crypto irreversible hota hai.
                </Box>
              </Step>
              <Step n="4" title="TxID submit karein">
                Bhejne ke baad Tronscan.org se Transaction ID (TxID) copy karein → order page pe paste → "Submit TxID" click. Status "Submitted - Pending Verification" ho jayega.
              </Step>
              <Step n="5" title="License email arrive">
                Admin verify karega (max 30 min, peak time 1 hour). Approved hote hi:
                <ul className="list-disc list-inside mt-1.5 text-xs space-y-0.5">
                  <li>License Key: KRX-XXXX-XXXX-XXXX-XXXX</li>
                  <li>Login email + auto-generated 12-char password</li>
                  <li>Download link installer ka</li>
                </ul>
              </Step>
            </Section>

            <Section id="login" title="3. Pehli Baar Login" icon={Mail}>
              <Step n="1" title="krexion.com/login pe jaayein">
                Welcome email kholein → email + auto-password copy karein → login form mein paste karein.
              </Step>
              <Step n="2" title="Dashboard open hota hai">
                Cloud dashboard kholti hai. Yahan se 95% kaam hota hai — Links, Clicks, Campaigns, Settings sab.
              </Step>
              <Box kind="info" title="Security tip">
                Pehle login ke baad Settings → Profile mein password change kar lein (apni marzi ka strong password rakhein).
              </Box>
            </Section>

            <Section id="cloud" title="4. Cloud Dashboard Use Karna" icon={Monitor}>
              <p>Krexion.com pe login hone ke baad sidebar mein yeh sections milein gay:</p>
              <ul className="list-disc list-inside ml-2 space-y-1 text-sm text-zinc-400">
                <li><strong className="text-white">Dashboard</strong> — overview, clicks/conversions chart, top links</li>
                <li><strong className="text-white">Links</strong> — apne tracking links create karein, manage karein</li>
                <li><strong className="text-white">Clicks</strong> — har click ka detail (IP, geo, device, time)</li>
                <li><strong className="text-white">Conversions</strong> — sales tracking</li>
                <li><strong className="text-white">Proxies</strong> — proxies add karein, status check karein</li>
                <li><strong className="text-white">Real User Traffic</strong> — jobs schedule karein</li>
                <li><strong className="text-white">Form Filler</strong> — auto-fill landing pages</li>
                <li><strong className="text-white">Settings</strong> — profile, password, API keys</li>
              </ul>
            </Section>

            <Section id="links" title="5. Tracking Links Banana" icon={Activity}>
              <Step n="1" title="Sidebar mein Links pe click">
                Phir top right "+ New Link" button click karein.
              </Step>
              <Step n="2" title="Form fill karein">
                Name (e.g., "Facebook Ad Campaign A") + Offer URL (jahan customer redirect ho).
              </Step>
              <Step n="3" title="Link generate hoga">
                <code className="bg-white/10 px-2 py-1 rounded text-blue-400 text-xs">https://krexion.com/r/abc123</code>
                {" "}— is link ko aap ne ads / social posts mein use karna hai.
              </Step>
              <Box kind="success">
                <CheckCircle2 size={14} className="inline mr-1" />
                Yeh link 24/7 live rahega — aap ka PC band ho ya internet off, click tracking nonstop chalega.
              </Box>
            </Section>

            <Section id="install" title="6. Desktop App Install (Heavy Features ke liye)" icon={Download}>
              <p>Cloud dashboard light kaam ke liye perfect hai. Heavy features (Proxy Check, RUT, Form Filler) ke liye desktop app install karein:</p>

              <Step n="1" title="Installer download karein">
                <Link to="/download" className="text-blue-400 hover:underline">krexion.com/download</Link> pe jaa kar bada blue "Download installer" button click karein. ZIP file (~23 KB) download hogi.
              </Step>

              <Step n="2" title="ZIP EXTRACT KAREIN (zaroori!)">
                <Box kind="danger" title="ZAROORI — yeh galti har customer karta hai">
                  ZIP ke andar se INSTALL.bat <strong>NA</strong> chalayein. Pehle extract karein:
                  <ol className="list-decimal list-inside mt-2 space-y-0.5 text-xs">
                    <li>Krexion-User-Package.zip pe <strong>right-click</strong></li>
                    <li>"Extract All..." click karein</li>
                    <li>"Extract" button click karein</li>
                    <li>Naye folder ke <strong>ANDER</strong> jayein</li>
                  </ol>
                </Box>
              </Step>

              <Step n="3" title="INSTALL.bat double-click karein">
                Extracted folder mein <code className="bg-white/10 px-1.5 py-0.5 rounded text-xs">INSTALL.bat</code> file pe double-click. UAC popup pe "Yes" / "Haan" click karein.
                <Box kind="warn" title="Agar popup turant band ho jaye">
                  INSTALL.bat pe right-click → "Run as administrator" select karein.
                </Box>
              </Step>

              <Step n="4" title="20-30 min wait karein">
                Installer 8 steps automatically chalayega:
                <ul className="list-disc list-inside mt-1.5 text-xs space-y-0.5">
                  <li>System check (10 sec)</li>
                  <li>Windows features (1-3 min)</li>
                  <li>System engine update (1-2 min)</li>
                  <li>Krexion runtime install (5-10 min)</li>
                  <li>Engine start (1-5 min)</li>
                  <li>Code download (1-2 min)</li>
                  <li>Build + start containers (5-15 min)</li>
                  <li>Source hardening (10 sec)</li>
                </ul>
              </Step>

              <Step n="5" title="Browser khud khulta hai">
                Install complete hone par browser <code className="bg-white/10 px-1.5 py-0.5 rounded text-xs">https://krexion.com/login</code> pe khulta hai. Wohi email + password daalein jo email mein mila tha.
              </Step>

              <Box kind="info">
                Install hone ke baad Krexion silently background mein chalta hai. Reboot ke baad bhi automatic start hota hai. Desktop pe sirf "Krexion" shortcut milega.
              </Box>
            </Section>

            <Section id="heavy" title="7. Heavy Features (Proxy / RUT / Form Filler)" icon={Settings}>
              <p>Desktop app install hone ke baad, krexion.com dashboard pe yeh features unlock ho jate hain. Aap ne kuch alag se nahi karna — sab same dashboard se control hota hai, sirf execution aap ke PC pe hoti hai.</p>
              <ul className="list-disc list-inside ml-2 space-y-1 text-sm text-zinc-400">
                <li><strong className="text-white">Proxy Bulk Test</strong> — 1000+ proxies paste karein → "Test All" → parallel batches chalti hain</li>
                <li><strong className="text-white">Real User Traffic</strong> — Job create karein → schedule → real Chrome aap ke PC pe chalega</li>
                <li><strong className="text-white">Form Filler</strong> — landing page URL + form fields → auto-fill chalti hai</li>
              </ul>
            </Section>

            <Section id="update" title="8. Updates (Auto-Notification)" icon={Sparkles}>
              <p>Jab bhi Krexion ki new version aati hai, aap ke dashboard pe top par notification banner aata hai:</p>
              <ul className="list-disc list-inside ml-2 space-y-1 text-sm text-zinc-400">
                <li><span className="text-blue-300">Recommended</span> (blue) — dismissable, jab chahein install karein</li>
                <li><span className="text-red-300">Critical</span> (red) — security fix, install zaroori</li>
              </ul>
              <Step n="1" title="View & Install click">
                Banner pe "View & install" button click karein → modal khulta hai with release notes.
              </Step>
              <Step n="2" title="Install update click">
                Container automatically rebuild ho jata hai (~90 sec). App reload hoti hai. Aap ka data + license intact rehte hain.
              </Step>
            </Section>

            <Section id="troubleshoot" title="9. Troubleshooting" icon={AlertCircle}>
              <div className="space-y-4">
                <div className="bg-white/[0.03] border border-white/10 rounded-lg p-4">
                  <h4 className="font-semibold text-yellow-300 mb-1.5 text-sm">INSTALL.bat popup turant band ho jata hai</h4>
                  <p className="text-xs text-zinc-400">Sabse common wajah ZIP extract nahi ki. Right-click → Extract All. Doosri wajah UAC "No" — right-click → Run as administrator.</p>
                </div>
                <div className="bg-white/[0.03] border border-white/10 rounded-lg p-4">
                  <h4 className="font-semibold text-yellow-300 mb-1.5 text-sm">"PowerShell scripts blocked" error</h4>
                  <p className="text-xs text-zinc-400">Antivirus ya Windows S Mode ki wajah se. Antivirus temporary disable karein, ya Windows S Mode se exit karein (Settings → Activation).</p>
                </div>
                <div className="bg-white/[0.03] border border-white/10 rounded-lg p-4">
                  <h4 className="font-semibold text-yellow-300 mb-1.5 text-sm">Install fail at "engine starting"</h4>
                  <p className="text-xs text-zinc-400">BIOS mein virtualization (VT-x / AMD-V) enable karein. PC restart karein. INSTALL.bat dobara chalayein.</p>
                </div>
                <div className="bg-white/[0.03] border border-white/10 rounded-lg p-4">
                  <h4 className="font-semibold text-yellow-300 mb-1.5 text-sm">Login welcome email nahi mila</h4>
                  <p className="text-xs text-zinc-400">Spam / Promotions folder check karein. Phir bhi nahi mile → support@krexion.com pe order ID send karein.</p>
                </div>
                <div className="bg-white/[0.03] border border-white/10 rounded-lg p-4">
                  <h4 className="font-semibold text-yellow-300 mb-1.5 text-sm">Order Pending 1 hour se zyada</h4>
                  <p className="text-xs text-zinc-400">Peak time pe normal hai. 2 hour ke baad bhi pending → support@krexion.com pe TxID + order ID forward karein.</p>
                </div>
              </div>
              <Box kind="info" title="Install log file kahan hai?">
                Install fail hone par Desktop pe <code className="bg-black/30 px-1.5 py-0.5 rounded text-xs">Krexion-Install-Log.txt</code> file save hoti hai. Yeh file support team ko bhejein.
              </Box>
            </Section>

            <Section id="faq" title="10. FAQs" icon={HelpCircle}>
              <div className="space-y-3">
                {FAQS.map((f, idx) => {
                  const open = openFaq === idx;
                  return (
                    <div key={idx} className="bg-white/[0.03] border border-white/10 rounded-xl overflow-hidden">
                      <button
                        onClick={() => setOpenFaq(open ? -1 : idx)}
                        data-testid={`guide-faq-${idx}`}
                        className="w-full flex items-center justify-between text-left px-5 py-4 hover:bg-white/[0.02]"
                      >
                        <span className="font-medium text-sm">{f.q}</span>
                        <ChevronDown size={16} className={`text-zinc-400 transition-transform ${open ? "rotate-180 text-blue-400" : ""}`} />
                      </button>
                      {open && (
                        <div className="px-5 pb-4 text-sm text-zinc-400 leading-relaxed border-t border-white/5">
                          <div className="pt-3">{f.a}</div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </Section>

            <Section id="contact" title="Still stuck?" icon={HelpCircle}>
              <div className="bg-gradient-to-br from-blue-600/20 to-black border border-blue-500/30 rounded-2xl p-8 text-center">
                <h3 className="text-xl font-bold mb-2">Support team aap ke saath hai</h3>
                <p className="text-sm text-zinc-400 mb-5">Email karein order ID + screenshots + Krexion-Install-Log.txt ke saath, 24 hours mein reply guaranteed.</p>
                <a
                  href="mailto:support@krexion.com"
                  className="inline-flex items-center gap-2 bg-blue-500 hover:bg-blue-400 text-white font-semibold px-6 py-3 rounded-lg shadow-lg shadow-blue-500/30 transition"
                  data-testid="guide-support-email"
                >
                  <Mail size={16} /> support@krexion.com
                </a>
              </div>
            </Section>
          </main>
        </div>
      </div>

      <footer className="border-t border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-zinc-500">
          <div className="flex items-center gap-2">
            <Sparkles className="text-blue-400" size={14} />
            <span className="font-semibold text-white">KREXION</span>
            <span>© {new Date().getFullYear()}</span>
          </div>
          <div className="flex items-center gap-5">
            <Link to="/pricing" className="hover:text-white">Pricing</Link>
            <Link to="/download" className="hover:text-white">Download</Link>
            <Link to="/guide" className="hover:text-white">Guide</Link>
            <Link to="/login" className="hover:text-white">Login</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
