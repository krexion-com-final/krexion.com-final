import { useEffect, useRef } from "react";

/**
 * Option 3 — Animated Cyber Grid.
 * Subtle moving grid with a glowing spotlight at cursor.
 * Looks like a futuristic ops-dashboard.
 */
export default function GridBackground({ zIndex = 0 }) {
  const canvasRef = useRef(null);
  const mouseRef = useRef({
    x: typeof window !== "undefined" ? window.innerWidth / 2 : 0,
    y: typeof window !== "undefined" ? window.innerHeight / 2 : 0,
  });

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
    const onMove = (e) => (mouseRef.current = { x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", onMove);

    const cell = 44;
    let offset = 0;

    const tick = () => {
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Spotlight radial gradient
      const { x: mx, y: my } = mouseRef.current;
      const spot = ctx.createRadialGradient(mx, my, 0, mx, my, 320);
      spot.addColorStop(0, "rgba(79,127,255,0.30)");
      spot.addColorStop(0.5, "rgba(79,127,255,0.06)");
      spot.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = spot;
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Animated grid
      offset = (offset + 0.25) % cell;
      ctx.strokeStyle = "rgba(79,127,255,0.15)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      for (let x = -cell + offset; x <= canvas.width; x += cell) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
      }
      for (let y = -cell + offset; y <= canvas.height; y += cell) {
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
      }
      ctx.stroke();

      // Brighter grid near cursor (mask by distance)
      ctx.save();
      const mask = ctx.createRadialGradient(mx, my, 0, mx, my, 260);
      mask.addColorStop(0, "rgba(79,127,255,0.9)");
      mask.addColorStop(1, "rgba(79,127,255,0)");
      ctx.strokeStyle = mask;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      for (let x = -cell + offset; x <= canvas.width; x += cell) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, canvas.height);
      }
      for (let y = -cell + offset; y <= canvas.height; y += cell) {
        ctx.moveTo(0, y);
        ctx.lineTo(canvas.width, y);
      }
      ctx.stroke();
      ctx.restore();

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMove);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      data-testid="grid-background"
      style={{
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100vh",
        zIndex,
        pointerEvents: "none",
      }}
    />
  );
}
