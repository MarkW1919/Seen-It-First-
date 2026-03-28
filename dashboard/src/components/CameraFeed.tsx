import React, { useState, useEffect, useRef } from "react";

export interface CameraInfo {
  id: string;
  label: string;
  active: boolean;
}

const DEFAULT_CAMERAS: CameraInfo[] = [
  { id: "cam_1", label: "Camera 1", active: true },
  { id: "cam_2", label: "Camera 2", active: true },
  { id: "cam_3", label: "Camera 3", active: true },
  { id: "cam_4", label: "Camera 4", active: false },
];

// Simulated detections for wireframe overlay
interface Overlay {
  id: string;
  plate: string;
  conf: number;
  x: number; // percent
  y: number;
  w: number;
  h: number;
  isHotlist?: boolean;
}

const MOCK_OVERLAYS: Record<string, Overlay[]> = {
  cam_1: [
    { id: "a", plate: "6UCJ466", conf: 0.91, x: 38, y: 40, w: 26, h: 38 },
  ],
  cam_2: [
    { id: "b", plate: "9AJA734", conf: 0.88, x: 55, y: 35, w: 22, h: 36 },
    { id: "c", plate: "5HCG067", conf: 0.79, x: 20, y: 45, w: 18, h: 28 },
  ],
  cam_3: [
    { id: "d", plate: "9KPN665", conf: 0.95, x: 42, y: 28, w: 30, h: 42, isHotlist: false },
    { id: "e", plate: "6MWM749", conf: 0.83, x: 10, y: 55, w: 16, h: 22 },
  ],
  cam_4: [],
};

interface Props {
  activeCamId?: string;
  onCamChange?: (id: string) => void;
  pipelineActive: boolean;
}

export function CameraFeed({ activeCamId, onCamChange, pipelineActive }: Props) {
  const [activeId, setActiveId] = useState(activeCamId ?? "cam_3");
  const [frameCount, setFrameCount] = useState(0);
  const [fps, setFps] = useState(15);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Simulate frame counter ticking
  useEffect(() => {
    timerRef.current = setInterval(() => {
      if (pipelineActive) {
        setFrameCount((c) => c + 1);
        setFps(14 + Math.round(Math.random() * 2));
      }
    }, 67); // ~15 fps
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [pipelineActive]);

  const handleCamSelect = (id: string) => {
    setActiveId(id);
    onCamChange?.(id);
  };

  const activeCam = DEFAULT_CAMERAS.find((c) => c.id === activeId) ?? DEFAULT_CAMERAS[2];
  const overlays = MOCK_OVERLAYS[activeId] ?? [];

  return (
    <div style={s.root}>
      {/* ── Camera tab bar ─────────────────────────────────────── */}
      <div style={s.tabBar}>
        {DEFAULT_CAMERAS.map((cam) => (
          <button
            key={cam.id}
            onClick={() => handleCamSelect(cam.id)}
            style={{
              ...s.tab,
              ...(activeId === cam.id ? s.tabActive : s.tabInactive),
            }}
          >
            <span style={{
              ...s.camDot,
              backgroundColor: cam.active ? "#22c55e" : "#475569",
            }} />
            {cam.label}
          </button>
        ))}

        <div style={s.tabSpacer} />

        {/* Live indicator */}
        <div style={s.liveChip}>
          <span style={{ ...s.liveDot, backgroundColor: pipelineActive ? "#ef4444" : "#475569" }} />
          {pipelineActive ? "LIVE" : "IDLE"}
        </div>
      </div>

      {/* ── Feed area ─────────────────────────────────────────── */}
      <div style={s.feedArea}>
        {/* Wireframe grid pattern — represents camera feed */}
        <svg style={s.gridSvg} width="100%" height="100%">
          <defs>
            <pattern id="camGrid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e3a5f" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#camGrid)" />
        </svg>

        {/* Horizon line (wireframe road/scene) */}
        <div style={s.horizon} />

        {/* Road / lane wireframe */}
        <svg style={{ position: "absolute", bottom: 0, left: 0, width: "100%", height: "50%", opacity: 0.15 }}>
          {/* Lane lines */}
          <line x1="50%" y1="0%" x2="15%" y2="100%" stroke="#60a5fa" strokeWidth="1" strokeDasharray="8 6" />
          <line x1="50%" y1="0%" x2="85%" y2="100%" stroke="#60a5fa" strokeWidth="1" strokeDasharray="8 6" />
          <line x1="50%" y1="20%" x2="50%" y2="100%" stroke="#94a3b8" strokeWidth="0.5" strokeDasharray="12 8" />
        </svg>

        {/* Vehicle wireframe body */}
        <svg style={{ position: "absolute", left: "35%", top: "15%", width: "30%", height: "55%", opacity: 0.25 }}>
          {/* SUV body outline */}
          <rect x="5%" y="40%" width="90%" height="45%" rx="3" fill="none" stroke="#94a3b8" strokeWidth="1.5" />
          <rect x="15%" y="15%" width="70%" height="35%" rx="4" fill="none" stroke="#94a3b8" strokeWidth="1.5" />
          {/* Wheels */}
          <circle cx="22%" cy="85%" r="10%" fill="none" stroke="#64748b" strokeWidth="1.5" />
          <circle cx="78%" cy="85%" r="10%" fill="none" stroke="#64748b" strokeWidth="1.5" />
          {/* Windshield */}
          <rect x="20%" y="18%" width="60%" height="28%" rx="2" fill="none" stroke="#60a5fa" strokeWidth="1" />
        </svg>

        {/* Detection overlays */}
        {overlays.map((ov) => (
          <div
            key={ov.id}
            style={{
              position: "absolute",
              left:   `${ov.x}%`,
              top:    `${ov.y}%`,
              width:  `${ov.w}%`,
              height: `${ov.h}%`,
              border: `2px solid ${ov.isHotlist ? "#ef4444" : "#3b82f6"}`,
              boxShadow: `0 0 8px ${ov.isHotlist ? "rgba(239,68,68,0.5)" : "rgba(59,130,246,0.4)"}`,
              borderRadius: "2px",
            }}
          >
            {/* Plate label on detection box */}
            <div style={{
              position: "absolute",
              bottom: "100%",
              left: 0,
              background: ov.isHotlist ? "#dc2626" : "#1d4ed8",
              color: "#fff",
              fontSize: "0.6rem",
              fontFamily: "monospace",
              fontWeight: 700,
              padding: "1px 4px",
              whiteSpace: "nowrap",
              letterSpacing: "0.06em",
            }}>
              {ov.plate} {(ov.conf * 100).toFixed(0)}%
            </div>

            {/* Corner accents */}
            <Corner pos="tl" color={ov.isHotlist ? "#ef4444" : "#3b82f6"} />
            <Corner pos="tr" color={ov.isHotlist ? "#ef4444" : "#3b82f6"} />
            <Corner pos="bl" color={ov.isHotlist ? "#ef4444" : "#3b82f6"} />
            <Corner pos="br" color={ov.isHotlist ? "#ef4444" : "#3b82f6"} />
          </div>
        ))}

        {/* Camera label overlay */}
        <div style={s.camLabel}>
          {activeCam.label.toUpperCase()}
        </div>

        {/* HUD stats overlay */}
        <div style={s.hudStats}>
          <span style={s.hudItem}>{fps} FPS</span>
          <span style={s.hudItem}>1920×1080</span>
          <span style={s.hudItem}>FRAME {frameCount.toString().padStart(6, "0")}</span>
        </div>

        {/* Pipeline inactive overlay */}
        {!pipelineActive && (
          <div style={s.inactiveOverlay}>
            <div style={s.inactiveMsg}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#64748b" strokeWidth="1.5">
                <path d="M15 10l4.553-2.07A1 1 0 0121 8.82v6.36a1 1 0 01-1.447.89L15 14M4 8h8a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2v-4a2 2 0 012-2z" />
              </svg>
              <span>LPR IDLE — En Route to Destination</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* Corner accent marks for detection boxes */
function Corner({ pos, color }: { pos: "tl" | "tr" | "bl" | "br"; color: string }) {
  const size = 8;
  const style: React.CSSProperties = {
    position: "absolute",
    width: size,
    height: size,
    borderColor: color,
    borderStyle: "solid",
    borderWidth: 0,
  };
  if (pos === "tl") { style.top = -1; style.left = -1; style.borderTopWidth = 2; style.borderLeftWidth = 2; }
  if (pos === "tr") { style.top = -1; style.right = -1; style.borderTopWidth = 2; style.borderRightWidth = 2; }
  if (pos === "bl") { style.bottom = -1; style.left = -1; style.borderBottomWidth = 2; style.borderLeftWidth = 2; }
  if (pos === "br") { style.bottom = -1; style.right = -1; style.borderBottomWidth = 2; style.borderRightWidth = 2; }
  return <div style={style} />;
}

/* ── Styles ────────────────────────────────────────────────────────────── */
const s = {
  root: {
    display: "flex",
    flexDirection: "column" as const,
    height: "100%",
    background: "#0a0f1e",
    overflow: "hidden",
  },
  tabBar: {
    display: "flex",
    alignItems: "center",
    gap: "2px",
    padding: "4px 8px",
    background: "#0f172a",
    borderBottom: "1px solid #1e3a5f",
    flexShrink: 0,
  },
  tab: {
    display: "flex",
    alignItems: "center",
    gap: "5px",
    padding: "4px 10px",
    border: "1px solid transparent",
    borderRadius: "4px",
    cursor: "pointer",
    fontSize: "0.72rem",
    fontWeight: 600,
    letterSpacing: "0.04em",
    transition: "all 0.12s",
  },
  tabActive: {
    background: "#1e3a5f",
    borderColor: "#2563eb",
    color: "#93c5fd",
  },
  tabInactive: {
    background: "transparent",
    color: "#64748b",
  },
  tabSpacer: {
    flex: 1,
  },
  camDot: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    flexShrink: 0,
  },
  liveChip: {
    display: "flex",
    alignItems: "center",
    gap: "5px",
    padding: "3px 10px",
    background: "#0f172a",
    border: "1px solid #334155",
    borderRadius: "4px",
    fontSize: "0.68rem",
    fontWeight: 700,
    letterSpacing: "0.1em",
    color: "#94a3b8",
  },
  liveDot: {
    width: 7,
    height: 7,
    borderRadius: "50%",
    animation: "pulse 1.4s ease-in-out infinite",
  },
  feedArea: {
    flex: 1,
    position: "relative" as const,
    overflow: "hidden",
    background: "#050b14",
  },
  gridSvg: {
    position: "absolute" as const,
    inset: 0,
  },
  horizon: {
    position: "absolute" as const,
    top: "48%",
    left: 0,
    right: 0,
    height: "1px",
    background: "linear-gradient(90deg, transparent, #1e3a5f 20%, #1e3a5f 80%, transparent)",
  },
  camLabel: {
    position: "absolute" as const,
    top: 8,
    left: 10,
    fontSize: "0.6rem",
    fontWeight: 700,
    letterSpacing: "0.12em",
    color: "#475569",
    fontFamily: "monospace",
  },
  hudStats: {
    position: "absolute" as const,
    top: 8,
    right: 8,
    display: "flex",
    gap: "8px",
  },
  hudItem: {
    fontSize: "0.58rem",
    fontFamily: "monospace",
    color: "#22c55e",
    background: "rgba(0,0,0,0.6)",
    padding: "1px 5px",
    borderRadius: "2px",
    letterSpacing: "0.04em",
  },
  inactiveOverlay: {
    position: "absolute" as const,
    inset: 0,
    background: "rgba(5,11,20,0.75)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  inactiveMsg: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: "8px",
    color: "#475569",
    fontSize: "0.75rem",
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
  },
} as const;
