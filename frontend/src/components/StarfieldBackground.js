import { useEffect, useRef } from "react";

/**
 * Option 4 — Starfield (Hyperspace).
 * Slowly drifting stars + occasional shooting star.
 * Clean, deep-space feel. Very minimal CPU.
 */
export default function StarfieldBackground({ zIndex = 0, count = 220 }) {
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

    const stars = Array.from({ length: count }, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      z: Math.random() * 1 + 0.2,
      r: Math.random() * 1.4 + 0.3,
    }));

    let shooter = null;
    const maybeSpawnShooter = () => {
      if (shooter) return;
      if (Math.random() > 0.995) {
        shooter = {
          x: Math.random() * canvas.width,
          y: Math.random() * canvas.height * 0.4,
          vx: 6 + Math.random() * 4,
          vy: 2 + Math.random() * 2,
          life: 1,
        };
      }
    };

    const tick = () => {
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Stars
      for (const s of stars) {
        s.y += s.z * 0.25;
        if (s.y > canvas.height) {
          s.y = 0;
          s.x = Math.random() * canvas.width;
        }
        ctx.fillStyle = `rgba(${180 + s.z * 60},${200 + s.z * 40},255,${
          0.4 + s.z * 0.5
        })`;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r * s.z, 0, Math.PI * 2);
        ctx.fill();
      }

      // Shooting star
      maybeSpawnShooter();
      if (shooter) {
        const tailX = shooter.x - shooter.vx * 14;
        const tailY = shooter.y - shooter.vy * 14;
        const grad = ctx.createLinearGradient(
          shooter.x,
          shooter.y,
          tailX,
          tailY
        );
        grad.addColorStop(0, `rgba(180,210,255,${shooter.life})`);
        grad.addColorStop(1, "rgba(180,210,255,0)");
        ctx.strokeStyle = grad;
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.moveTo(shooter.x, shooter.y);
        ctx.lineTo(tailX, tailY);
        ctx.stroke();
        shooter.x += shooter.vx;
        shooter.y += shooter.vy;
        shooter.life -= 0.015;
        if (
          shooter.life <= 0 ||
          shooter.x > canvas.width + 100 ||
          shooter.y > canvas.height + 100
        )
          shooter = null;
      }

      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, [count]);

  return (
    <canvas
      ref={canvasRef}
      data-testid="starfield-background"
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
