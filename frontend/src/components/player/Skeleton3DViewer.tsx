"use client";

/**
 * Khung xương 3D HLV - HV (dữ liệu skeleton3d.json do server tạo khi chấm, xem
 * backend/ai_engine/visualizers/skeleton_3d.py). Học viên đã được căn Procrustes về HLV như khi tính điểm
 * PA-MPJPE; khớp lệch quá ngưỡng tô đỏ. Truyền `time` (giây video HV) để khung xương đi theo video.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { mediaUrl } from "../../services/api";

interface SkeletonFrame {
  c: number[][];
  s: number[][];
  e: number[];
  cf: number;
  sf: number;
  t: number | null;
}
interface SkeletonSide {
  names: string[];
  bones: [number, number][];
  tolerance: number;
  frames: SkeletonFrame[];
}
type Mode = "overlay" | "side" | "coach" | "student";

const COACH = "#60a5fa";
const STUDENT = "#34d399";
const BAD = "#f87171";
const GRID = "#334155";
const BG = "#0b1220";
const SIDE_LABELS: Record<string, string> = { left: "Bên Trái", right: "Bên Phải", fused: "Fusion 2 góc" };

export function Skeleton3DViewer({ url, time }: { url: string; time?: number }) {
  const [sides, setSides] = useState<Record<string, SkeletonSide> | null>(null);
  const [failed, setFailed] = useState(false);
  const [side, setSide] = useState<string>("");
  const [mode, setMode] = useState<Mode>("overlay");
  const [playing, setPlaying] = useState(time === undefined);
  const [idx, setIdx] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const view = useRef({ yaw: -0.6, pitch: 0.2, zoom: 1 });
  const drag = useRef<[number, number] | null>(null);

  useEffect(() => {
    let alive = true;
    setFailed(false);
    fetch(mediaUrl(url))
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d: { sides: Record<string, SkeletonSide> }) => {
        if (!alive) return;
        setSides(d.sides);
        setSide(Object.keys(d.sides)[0] || "");
        setIdx(0);
      })
      .catch(() => alive && setFailed(true));
    return () => {
      alive = false;
    };
  }, [url]);

  const data = sides && side ? sides[side] : null;

  // Đi theo video: chọn cặp frame có thời điểm video HV gần nhất
  useEffect(() => {
    if (time === undefined || !data) return;
    let best = -1;
    let gap = Infinity;
    data.frames.forEach((f, k) => {
      if (f.t === null) return;
      const g = Math.abs(f.t - time);
      if (g < gap) {
        gap = g;
        best = k;
      }
    });
    if (best >= 0) {
      setPlaying(false);
      setIdx(best);
    }
  }, [time, data]);

  // Tự phát khi không gắn với video
  useEffect(() => {
    if (!playing || !data) return;
    const timer = window.setInterval(() => setIdx((i) => (i + 1) % data.frames.length), 80);
    return () => window.clearInterval(timer);
  }, [playing, data]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !data || !data.frames.length) return;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = BG;
    ctx.fillRect(0, 0, w, h);

    const { yaw, pitch, zoom } = view.current;
    const project = (p: number[], shift: number): [number, number] => {
      const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
      const x1 = cy * p[0] + sy * p[2];
      const z1 = -sy * p[0] + cy * p[2];
      const y1 = cp * p[1] - sp * z1;
      const z2 = sp * p[1] + cp * z1;
      const d = 6 / (6 + z2);
      const s = Math.min(w * (shift ? 0.5 : 1), h) * 0.26 * zoom;
      return [w * (0.5 + shift) + x1 * d * s, h * 0.55 - y1 * d * s];
    };
    const floorY = Math.min(...data.frames.flatMap((f) => f.c.map((p) => p[1])));
    const drawGrid = (shift: number) => {
      ctx.strokeStyle = GRID;
      ctx.lineWidth = 1;
      for (let g = -2; g <= 2; g++) {
        const a = project([g * 0.5, floorY, -1], shift), b = project([g * 0.5, floorY, 1], shift);
        const c = project([-1, floorY, g * 0.5], shift), d = project([1, floorY, g * 0.5], shift);
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]); ctx.lineTo(b[0], b[1]);
        ctx.moveTo(c[0], c[1]); ctx.lineTo(d[0], d[1]);
        ctx.stroke();
      }
    };
    const drawSkeleton = (pts: number[][], color: string, errs: number[] | null, shift: number, width: number) => {
      const p2 = pts.map((p) => project(p, shift));
      ctx.lineWidth = width;
      ctx.lineCap = "round";
      ctx.strokeStyle = color;
      data.bones.forEach(([a, b]) => {
        ctx.beginPath();
        ctx.moveTo(p2[a][0], p2[a][1]);
        ctx.lineTo(p2[b][0], p2[b][1]);
        ctx.stroke();
      });
      p2.forEach((q, j) => {
        const bad = errs !== null && errs[j] > data.tolerance;
        ctx.fillStyle = bad ? BAD : color;
        ctx.beginPath();
        ctx.arc(q[0], q[1], bad ? 5 : 3, 0, 2 * Math.PI);
        ctx.fill();
      });
    };

    const f = data.frames[Math.min(idx, data.frames.length - 1)];
    const sideBySide = mode === "side";
    const shiftC = sideBySide ? -0.25 : 0;
    const shiftS = sideBySide ? 0.25 : 0;
    drawGrid(shiftC);
    if (sideBySide) drawGrid(shiftS);
    if (mode !== "student") drawSkeleton(f.c, COACH, null, shiftC, sideBySide ? 3 : 4);
    if (mode !== "coach") drawSkeleton(f.s, STUDENT, f.e, shiftS, 3);
  }, [data, idx, mode]);

  useEffect(() => {
    draw();
  }, [draw]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => draw());
    ro.observe(canvas);
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      view.current.zoom = Math.max(0.4, Math.min(4, view.current.zoom * (e.deltaY < 0 ? 1.1 : 0.9)));
      draw();
    };
    canvas.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      ro.disconnect();
      canvas.removeEventListener("wheel", onWheel);
    };
  }, [draw]);

  if (failed) {
    return <p className="text-xs text-slate-500">Bài nộp này chưa có dữ liệu khung xương 3D (chấm trước khi có tính năng này).</p>;
  }
  if (!data) return <p className="text-xs text-slate-500">Đang tải khung xương 3D...</p>;

  const f = data.frames[Math.min(idx, data.frames.length - 1)];
  const mean = f.e.reduce((a, b) => a + b, 0) / f.e.length;
  const worst = f.e
    .map((e, j) => [e, j] as const)
    .filter(([e]) => e > data.tolerance)
    .sort((a, b) => b[0] - a[0])
    .slice(0, 3)
    .map(([e, j]) => `${data.names[j]} ${Math.round(e * 100)}%`);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {Object.keys(sides || {}).length > 1 &&
          Object.keys(sides || {}).map((s) => (
            <button
              key={s}
              onClick={() => { setSide(s); setIdx(0); }}
              className={`rounded-lg px-3 py-1 font-semibold ${s === side ? "bg-blue-600 text-white" : "bg-slate-800 text-slate-300 hover:bg-slate-700"}`}
            >
              {SIDE_LABELS[s] || s}
            </button>
          ))}
        <button
          onClick={() => setPlaying((p) => !p)}
          className="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-3 py-1 font-semibold text-slate-200 hover:bg-slate-700"
        >
          {playing ? <><Pause className="h-3.5 w-3.5" /> Dừng</> : <><Play className="h-3.5 w-3.5" /> Tự phát</>}
        </button>
        <input
          type="range"
          min={0}
          max={data.frames.length - 1}
          value={Math.min(idx, data.frames.length - 1)}
          onChange={(e) => { setPlaying(false); setIdx(Number(e.target.value)); }}
          aria-label="Tua khung xương theo thời gian"
          className="min-w-[160px] flex-1"
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as Mode)}
          aria-label="Chế độ hiển thị khung xương"
          className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1 text-slate-200"
        >
          <option value="overlay">Chồng lên nhau</option>
          <option value="side">Cạnh nhau</option>
          <option value="coach">Chỉ HLV</option>
          <option value="student">Chỉ học viên</option>
        </select>
      </div>
      <canvas
        ref={canvasRef}
        aria-label="Khung xương 3D HLV và học viên"
        className="h-[380px] w-full cursor-grab touch-none rounded-xl border border-slate-800"
        onPointerDown={(e) => { drag.current = [e.clientX, e.clientY]; e.currentTarget.setPointerCapture(e.pointerId); }}
        onPointerMove={(e) => {
          if (!drag.current) return;
          view.current.yaw += (e.clientX - drag.current[0]) * 0.01;
          view.current.pitch = Math.max(-1.4, Math.min(1.4, view.current.pitch + (e.clientY - drag.current[1]) * 0.01));
          drag.current = [e.clientX, e.clientY];
          draw();
        }}
        onPointerUp={() => { drag.current = null; }}
      />
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: COACH }} />HLV</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: STUDENT }} />Học viên</span>
        <span><span className="mr-1 inline-block h-2.5 w-2.5 rounded-full" style={{ background: BAD }} />Khớp lệch &gt; {Math.round(data.tolerance * 100)}%</span>
        <span className="text-slate-300">
          Frame HLV {f.cf} ↔ HV {f.sf}{f.t !== null ? ` (${f.t.toFixed(2)}s)` : ""} · lệch TB {Math.round(mean * 100)}%
          {worst.length ? ` · khớp lệch: ${worst.join(", ")}` : " · không có khớp vượt ngưỡng"}
        </span>
      </div>
    </div>
  );
}
