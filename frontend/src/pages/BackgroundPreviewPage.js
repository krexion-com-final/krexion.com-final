import { useState } from "react";
import WavyBackground from "../components/WavyBackground";
import AuroraBackground from "../components/AuroraBackground";
import ParticleBackground from "../components/ParticleBackground";
import GridBackground from "../components/GridBackground";
import StarfieldBackground from "../components/StarfieldBackground";

/**
 * Public preview page to compare 5 background styles for the login screen.
 * Open: /bg-preview
 */
const OPTIONS = [
  {
    key: "current",
    title: "Current — Wavy Lines",
    description: "Cursor-following vertical wavy lines (the one you have now).",
    render: () => <WavyBackground intensity={1} lineCount={150} />,
  },
  {
    key: "aurora",
    title: "Option 1 — Aurora Gradient",
    description:
      "Soft drifting blue/violet/cyan glow blobs. Calm, premium, no cursor tracking.",
    render: () => <AuroraBackground />,
  },
  {
    key: "particles",
    title: "Option 2 — Particle Constellation",
    description:
      "Floating dots connected by faint lines. Subtle cursor attraction. Classic tech / AI feel.",
    render: () => <ParticleBackground />,
  },
  {
    key: "grid",
    title: "Option 3 — Cyber Grid",
    description:
      "Slow-moving grid with a glowing spotlight under your cursor. Ops-dashboard vibe.",
    render: () => <GridBackground />,
  },
  {
    key: "starfield",
    title: "Option 4 — Starfield",
    description:
      "Slowly drifting stars + occasional shooting star. Deep-space, very minimal CPU.",
    render: () => <StarfieldBackground />,
  },
];

export default function BackgroundPreviewPage() {
  const [active, setActive] = useState("aurora");
  const current = OPTIONS.find((o) => o.key === active) || OPTIONS[0];

  return (
    <div
      className="relative min-h-screen w-full overflow-hidden text-white"
      data-testid="bg-preview-page"
    >
      {current.render()}

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 py-12">
        <div className="w-full max-w-3xl rounded-2xl border border-white/10 bg-black/60 p-8 backdrop-blur-xl">
          <p className="text-xs uppercase tracking-[0.3em] text-blue-400">
            Krexion · Background Preview
          </p>
          <h1 className="mt-2 text-3xl font-bold sm:text-4xl">
            {current.title}
          </h1>
          <p className="mt-3 max-w-2xl text-sm text-white/70">
            {current.description}
          </p>

          <div className="mt-8 grid grid-cols-1 gap-2 sm:grid-cols-5">
            {OPTIONS.map((o) => (
              <button
                key={o.key}
                data-testid={`bg-option-${o.key}`}
                onClick={() => setActive(o.key)}
                className={`rounded-lg px-3 py-2 text-xs font-medium transition ${
                  active === o.key
                    ? "bg-blue-500 text-white shadow-lg shadow-blue-500/30"
                    : "border border-white/15 bg-white/5 text-white/80 hover:bg-white/10"
                }`}
              >
                {o.title.replace(/^.*?— /, "")}
              </button>
            ))}
          </div>

          <div className="mt-8 rounded-xl border border-white/10 bg-white/[0.04] p-5">
            <p className="text-sm text-white/80">
              Mock login card preview ↓ (same shape as your real login page)
            </p>
            <div className="mt-4 space-y-3">
              <input
                className="w-full rounded-full bg-white/90 px-4 py-2 text-sm text-black outline-none"
                placeholder="you@example.com"
                readOnly
                data-testid="preview-mock-email"
              />
              <input
                className="w-full rounded-full bg-white/90 px-4 py-2 text-sm text-black outline-none"
                placeholder="••••••••"
                readOnly
                data-testid="preview-mock-password"
              />
              <button
                className="w-full rounded-full bg-blue-500 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-600"
                data-testid="preview-mock-signin"
              >
                Sign In →
              </button>
            </div>
          </div>

          <p className="mt-6 text-center text-xs text-white/50">
            Bata dein kaun-sa pasand aaya (Current / Aurora / Particles / Grid /
            Starfield) — main usay login, admin login aur dashboard sab pe
            permanent set kar doon ga.
          </p>
        </div>
      </div>
    </div>
  );
}
