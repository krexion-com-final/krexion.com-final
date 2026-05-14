import { useEffect, useRef } from "react";

/**
 * Cursor-following vertical wavy lines (spotlight effect).
 * Used as a global animated background on Login + every Dashboard page.
 *
 * Color follows the active theme — reads CSS variable `--brand-primary`
 * from <html> and re-syncs whenever the theme changes (MutationObserver
 * on the documentElement style attribute).
 *
 * Props:
 *   intensity (number 0-1, default 1) — opacity multiplier for the lines
 *   lineCount (number, default 60)    — number of vertical lines
 *   zIndex   (number, default 0)      — canvas stacking position
 */

// Convert hex (#RRGGBB / #RGB / rgba / rgb / hsl) to [r,g,b]
function colorToRgb(input) {
  if (!input) return [79, 127, 255];
  const s = String(input).trim();
  // #RRGGBB or #RGB
  if (s.startsWith("#")) {
    let hex = s.slice(1);
    if (hex.length === 3) hex = hex.split("").map((c) => c + c).join("");
    if (hex.length === 6) {
      return [
        parseInt(hex.slice(0, 2), 16),
        parseInt(hex.slice(2, 4), 16),
        parseInt(hex.slice(4, 6), 16),
      ];
    }
  }
  // rgb(r,g,b) or rgba(r,g,b,a)
  const m = s.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
  if (m) return [parseInt(m[1], 10), parseInt(m[2], 10), parseInt(m[3], 10)];
  // Fallback
  return [79, 127, 255];
}

function readBrandPrimary() {
  if (typeof window === "undefined") return [79, 127, 255];
  const val = getComputedStyle(document.documentElement)
    .getPropertyValue("--brand-primary")
    .trim();
  return colorToRgb(val || "#4F7FFF");
}

export default function WavyBackground({
  intensity = 1,
  lineCount = 60,
  zIndex = 0,
}) {
  const canvasRef = useRef(null);
  const rawMouseRef = useRef({
    x: typeof window !== "undefined" ? window.innerWidth / 2 : 0,
    y: typeof window !== "undefined" ? window.innerHeight / 2 : 0,
  });
  const smoothMouseRef = useRef({ ...rawMouseRef.current });
  const rgbRef = useRef([79, 127, 255]);

  useEffect(() => {
    rgbRef.current = readBrandPrimary();
    // Watch for theme changes (ThemeContext writes inline style on <html>)
    const observer = new MutationObserver(() => {
      rgbRef.current = readBrandPrimary();
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["style", "data-theme-mode"],
    });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const onMove = (e) => {
      rawMouseRef.current = { x: e.clientX, y: e.clientY };
    };
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const lines = [];
    for (let i = 0; i < lineCount; i++) {
      const startX = (canvas.width / lineCount) * i;
      const points = [];
      for (let y = 0; y <= canvas.height; y += 5) points.push({ y });
      lines.push({
        points,
        baseX: startX,
        amplitude: 30 + Math.random() * 50,
        frequency: 0.003 + Math.random() * 0.002,
        speed: 0.2 + Math.random() * 0.3,
        phase: Math.random() * Math.PI * 2,
        opacity: (0.15 + Math.random() * 0.25) * intensity,
        mouseInfluence: 0,
      });
    }

    let raf;
    let time = 0;
    const animate = () => {
      // Smoothly chase the real cursor — softer lag = smoother spotlight
      smoothMouseRef.current.x +=
        (rawMouseRef.current.x - smoothMouseRef.current.x) * 0.06;
      smoothMouseRef.current.y +=
        (rawMouseRef.current.y - smoothMouseRef.current.y) * 0.06;
      const mx = smoothMouseRef.current.x;
      const my = smoothMouseRef.current.y;

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      time += 0.01;

      const [r, g, b] = rgbRef.current;

      for (const line of lines) {
        const dx = Math.abs(line.baseX - mx);
        const spotlightR = 500;
        const target =
          dx < spotlightR ? Math.max(0, (spotlightR - dx) / spotlightR) : 0;
        line.mouseInfluence += (target - line.mouseInfluence) * 0.035;
        if (line.mouseInfluence < 0.01) continue;

        ctx.beginPath();
        const finalOpacity = line.opacity * (0.5 + line.mouseInfluence * 0.7);
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${finalOpacity})`;
        ctx.lineWidth = 2.2;
        ctx.lineCap = "round";

        for (let i = 0; i < line.points.length; i++) {
          const p = line.points[i];
          const a = line.amplitude * line.mouseInfluence;
          const w1 =
            Math.sin(p.y * line.frequency + time * line.speed + line.phase) * a;
          const w2 =
            Math.sin(p.y * line.frequency * 0.5 + time * line.speed * 0.7) *
            (a * 0.4);
          const dy = Math.abs(p.y - my);
          const dist = Math.sqrt(dx * dx + dy * dy);
          const pull = Math.max(0, (300 - dist) / 300) * 80 * line.mouseInfluence;
          const x = line.baseX + w1 + w2 + pull;
          if (i === 0) ctx.moveTo(x, p.y);
          else ctx.lineTo(x, p.y);
        }
        ctx.stroke();
      }
      raf = requestAnimationFrame(animate);
    };
    animate();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [intensity, lineCount]);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 pointer-events-none"
      style={{ zIndex, width: "100vw", height: "100vh" }}
      aria-hidden="true"
      data-testid="wavy-background"
    />
  );
}
