import { useEffect, useRef } from "react";

/**
 * Option 1 — Aurora Gradient.
 * Soft, drifting blue/violet blobs that look like northern-lights.
 * Pure CSS+canvas blur. No cursor tracking. Cheap GPU.
 */
export default function AuroraBackground({ zIndex = 0 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let raf;
    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const blobs = [
      { x: 0.2, y: 0.3, r: 380, c: "#4F7FFF", sx: 0.0004, sy: 0.0003 },
      { x: 0.8, y: 0.2, r: 320, c: "#7B5CFF", sx: -0.0003, sy: 0.0005 },
      { x: 0.6, y: 0.8, r: 420, c: "#22D3EE", sx: 0.0005, sy: -0.0004 },
      { x: 0.3, y: 0.7, r: 300, c: "#4F7FFF", sx: -0.0004, sy: -0.0003 },
    ];

    const tick = (t) => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = "lighter";
      for (const b of blobs) {
        const cx = (b.x + Math.sin(t * b.sx) * 0.1) * canvas.width;
        const cy = (b.y + Math.cos(t * b.sy) * 0.1) * canvas.height;
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, b.r);
        grad.addColorStop(0, b.c + "AA");
        grad.addColorStop(0.5, b.c + "33");
        grad.addColorStop(1, "#00000000");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, b.r, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      data-testid="aurora-background"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        zIndex,
        pointerEvents: "none",
        filter: "blur(40px)",
      }}
    />
  );
}
