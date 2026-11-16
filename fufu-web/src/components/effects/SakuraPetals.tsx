import { useEffect, useRef } from 'react';
import { useSettingsStore } from '@/stores/settingsStore';

interface Petal {
  x: number;
  y: number;
  size: number;
  speedY: number;
  speedX: number;
  rotation: number;
  rotationSpeed: number;
  opacity: number;
  swayPhase: number;
  swayAmp: number;
  color: string;
}

const COLORS = [
  'rgba(0,229,255,0.3)',
  'rgba(57,197,187,0.28)',
  'rgba(255,182,193,0.3)',
  'rgba(0,229,255,0.25)',
  'rgba(197,168,225,0.28)',
  'rgba(0,229,255,0.22)',
];

function createPetal(canvasW: number, canvasH: number): Petal {
  return {
    x: Math.random() * canvasW,
    y: -20 - Math.random() * canvasH,
    size: 6 + Math.random() * 14,
    speedY: 0.4 + Math.random() * 1.2,
    speedX: 0.15 + Math.random() * 0.35,
    rotation: Math.random() * Math.PI * 2,
    rotationSpeed: (Math.random() - 0.5) * 0.02,
    opacity: 0.4 + Math.random() * 0.4,
    swayPhase: Math.random() * Math.PI * 2,
    swayAmp: 0.5 + Math.random() * 1.5,
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
  };
}

function drawPetal(ctx: CanvasRenderingContext2D, p: Petal, time: number) {
  const sway = Math.sin(time * 0.001 + p.swayPhase) * p.swayAmp;
  const x = p.x + sway;
  const y = p.y;

  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(p.rotation);
  ctx.globalAlpha = p.opacity;
  ctx.fillStyle = p.color;

  // 樱花花瓣形状
  ctx.beginPath();
  const s = p.size;
  ctx.ellipse(0, 0, s * 0.5, s * 0.22, 0, 0, Math.PI * 2);
  ctx.fill();

  // 花瓣纹理
  ctx.fillStyle = 'rgba(255,255,255,0.2)';
  ctx.beginPath();
  ctx.ellipse(0, -s * 0.05, s * 0.15, s * 0.08, 0, 0, Math.PI * 2);
  ctx.fill();

  ctx.restore();
}

export default function SakuraPetals() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const petalsRef = useRef<Petal[]>([]);
  const animRef = useRef<number>(0);
  const showSakura = useSettingsStore((s) => s.settings.showSakura);
  const intensity = useSettingsStore((s) => s.settings.effectIntensity);

  const maxPetals = Math.round(15 + (intensity / 100) * 25);

  useEffect(() => {
    if (!showSakura) return;
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const resize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    // 初始化花瓣
    petalsRef.current = Array.from({ length: maxPetals }, () =>
      createPetal(canvas.width, canvas.height),
    );

    const startTime = performance.now();

    const tick = (now: number) => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      for (const p of petalsRef.current) {
        p.y += p.speedY;
        p.x += Math.sin(now * 0.0008 + p.swayPhase) * p.speedX;
        p.rotation += p.rotationSpeed;

        if (p.y > canvas.height + 40) {
          Object.assign(p, createPetal(canvas.width, canvas.height));
          p.y = -30;
        }
        if (p.x < -40) p.x = canvas.width + 30;
        if (p.x > canvas.width + 40) p.x = -30;

        drawPetal(ctx, p, now);
      }

      // 动态调整数量
      while (petalsRef.current.length < maxPetals) {
        petalsRef.current.push(createPetal(canvas.width, canvas.height));
      }
      while (petalsRef.current.length > maxPetals) {
        petalsRef.current.pop();
      }

      animRef.current = requestAnimationFrame(tick);
    };

    animRef.current = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(animRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [showSakura, maxPetals]);

  if (!showSakura) return null;

  return (
    <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none" style={{ zIndex: 0 }} />
  );
}
