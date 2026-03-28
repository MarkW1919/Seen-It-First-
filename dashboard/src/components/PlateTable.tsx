import React, { useEffect, useRef } from "react";
import type { PlateDetection } from "../types/navigation";

// ── Wireframe seed rows (match the reference image) ──────────────────────
export const SEED_DETECTIONS: PlateDetection[] = [
  { id: "s1", plate1: "9KPN665", plate2: "PN665",   state: "CA", camera_id: "cam_3", confidence: 0.95, is_hotlist: false, timestamp: Date.now() / 1000 - 2,  image_url: null },
  { id: "s2", plate1: "9AJA734", plate2: "9AIA734", state: "CA", camera_id: "cam_2", confidence: 0.88, is_hotlist: false, timestamp: Date.now() / 1000 - 5,  image_url: null },
  { id: "s3", plate1: "5HCG067", plate2: "5MCG067", state: "CA", camera_id: "cam_2", confidence: 0.82, is_hotlist: false, timestamp: Date.now() / 1000 - 9,  image_url: null },
  { id: "s4", plate1: "6UCJ466", plate2: "6UCI466", state: "CA", camera_id: "cam_3", confidence: 0.91, is_hotlist: false, timestamp: Date.now() / 1000 - 14, image_url: null },
  { id: "s5", plate1: "6MWM749", plate2: "5MWM749", state: "CA", camera_id: "cam_3", confidence: 0.79, is_hotlist: false, timestamp: Date.now() / 1000 - 19, image_url: null },
  { id: "s6", plate1: "9EWG944", plate2: "9FWG944", state: "CA", camera_id: "cam_3", confidence: 0.86, is_hotlist: false, timestamp: Date.now() / 1000 - 25, image_url: null },
];

// Camera id → display label
const CAM_LABELS: Record<string, string> = {
  cam_1: "Camera 1",
  cam_2: "Camera 2",
  cam_3: "Camera 3",
  cam_4: "Camera 4",
};

function camLabel(id: string): string {
  return CAM_LABELS[id] ?? id;
}

function fmtTime(epochSec: number): string {
  return new Date(epochSec * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function confColor(c: number): string {
  if (c >= 0.90) return "#22c55e";
  if (c >= 0.75) return "#f59e0b";
  return "#ef4444";
}

// Tiny plate thumbnail placeholder
function PlateThumbnail({ isHotlist, plate }: { isHotlist: boolean; plate: string }) {
  return (
    <div style={{
      width: 52,
      height: 32,
      background: isHotlist ? "#450a0a" : "#0f2040",
      border: `1px solid ${isHotlist ? "#ef4444" : "#1e3a5f"}`,
      borderRadius: 3,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexShrink: 0,
    }}>
      {/* Miniature plate representation */}
      <div style={{
        width: 42,
        height: 22,
        background: isHotlist ? "#7f1d1d" : "#1e3a5f",
        border: `1px solid ${isHotlist ? "#dc2626" : "#2563eb"}`,
        borderRadius: 2,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: "0.45rem",
        fontFamily: "monospace",
        fontWeight: 700,
        color: "#e2e8f0",
        letterSpacing: "0.04em",
        overflow: "hidden",
      }}>
        {plate.slice(0, 7)}
      </div>
    </div>
  );
}

interface Props {
  detections: PlateDetection[];
  totalCount: number;
}

export function PlateTable({ detections, totalCount }: Props) {
  const tbodyRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to top when new detections arrive (newest first)
  useEffect(() => {
    tbodyRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [detections.length]);

  return (
    <div style={s.root}>
      {/* ── Table header ─────────────────────────────────────────── */}
      <div style={s.tableHead}>
        <div style={{ ...s.th, width: 68 }}>Image</div>
        <div style={{ ...s.th, flex: 1.2 }}>Plate 1</div>
        <div style={{ ...s.th, flex: 1.2 }}>Plate 2</div>
        <div style={{ ...s.th, width: 52 }}>State</div>
        <div style={{ ...s.th, flex: 1 }}>Camera</div>
        <div style={{ ...s.th, width: 54 }}>Conf</div>
        <div style={{ ...s.th, width: 74 }}>Time</div>
      </div>

      {/* ── Scrollable body ──────────────────────────────────────── */}
      <div ref={tbodyRef} style={s.tableBody}>
        {detections.length === 0 && (
          <div style={s.emptyMsg}>Waiting for plate detections…</div>
        )}

        {detections.map((row, idx) => (
          <div
            key={row.id}
            style={{
              ...s.row,
              background: row.is_hotlist
                ? "rgba(127,29,29,0.25)"
                : idx % 2 === 0
                  ? "rgba(14,22,40,0.7)"
                  : "rgba(10,15,30,0.9)",
              borderLeft: `3px solid ${row.is_hotlist ? "#ef4444" : "transparent"}`,
            }}
          >
            {/* Image thumbnail */}
            <div style={{ ...s.td, width: 68 }}>
              <PlateThumbnail isHotlist={row.is_hotlist} plate={row.plate1} />
            </div>

            {/* Plate 1 */}
            <div style={{ ...s.td, flex: 1.2 }}>
              <span style={row.is_hotlist ? s.plateHotlist : s.plate}>{row.plate1}</span>
              {row.is_hotlist && (
                <span style={s.hotlistBadge}>HOTLIST</span>
              )}
            </div>

            {/* Plate 2 */}
            <div style={{ ...s.td, flex: 1.2 }}>
              <span style={s.plateDim}>{row.plate2}</span>
            </div>

            {/* State */}
            <div style={{ ...s.td, width: 52 }}>
              <span style={s.stateChip}>{row.state}</span>
            </div>

            {/* Camera */}
            <div style={{ ...s.td, flex: 1 }}>
              <span style={s.camChip}>{camLabel(row.camera_id)}</span>
            </div>

            {/* Confidence */}
            <div style={{ ...s.td, width: 54 }}>
              <span style={{ ...s.confVal, color: confColor(row.confidence) }}>
                {(row.confidence * 100).toFixed(0)}%
              </span>
            </div>

            {/* Time */}
            <div style={{ ...s.td, width: 74 }}>
              <span style={s.timeVal}>{fmtTime(row.timestamp)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* ── Footer ─────────────────────────────────────────────── */}
      <div style={s.footer}>
        <span style={s.footerText}>
          {detections.length} shown · {totalCount} total reads
        </span>
        <span style={s.footerDot} />
        <span style={s.footerText}>Live · updates automatically</span>
      </div>
    </div>
  );
}

/* ── Styles ────────────────────────────────────────────────────────────── */
const s = {
  root: {
    display: "flex",
    flexDirection: "column" as const,
    height: "100%",
    background: "#080e1c",
    borderTop: "1px solid #1e3a5f",
    overflow: "hidden",
  },
  tableHead: {
    display: "flex",
    alignItems: "center",
    padding: "0 8px",
    height: 32,
    background: "#0f172a",
    borderBottom: "1px solid #1e3a5f",
    flexShrink: 0,
    gap: 4,
  },
  th: {
    fontSize: "0.62rem",
    fontWeight: 700,
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    color: "#475569",
    userSelect: "none" as const,
    paddingLeft: 4,
  },
  tableBody: {
    flex: 1,
    overflowY: "auto" as const,
    overflowX: "hidden" as const,
  },
  row: {
    display: "flex",
    alignItems: "center",
    padding: "4px 8px",
    gap: 4,
    minHeight: 44,
    borderBottom: "1px solid rgba(30,58,95,0.3)",
    transition: "background 0.2s",
  },
  td: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    overflow: "hidden",
    flexShrink: 0,
  },
  plate: {
    fontFamily: "monospace",
    fontWeight: 700,
    fontSize: "0.85rem",
    color: "#e2e8f0",
    letterSpacing: "0.06em",
  },
  plateHotlist: {
    fontFamily: "monospace",
    fontWeight: 700,
    fontSize: "0.85rem",
    color: "#fca5a5",
    letterSpacing: "0.06em",
  },
  plateDim: {
    fontFamily: "monospace",
    fontWeight: 400,
    fontSize: "0.78rem",
    color: "#64748b",
    letterSpacing: "0.04em",
  },
  hotlistBadge: {
    fontSize: "0.52rem",
    fontWeight: 800,
    background: "#dc2626",
    color: "#fff",
    padding: "1px 4px",
    borderRadius: "2px",
    letterSpacing: "0.06em",
    flexShrink: 0,
  },
  stateChip: {
    fontSize: "0.75rem",
    fontWeight: 700,
    fontFamily: "monospace",
    color: "#93c5fd",
    background: "rgba(29,78,216,0.2)",
    padding: "1px 6px",
    borderRadius: "2px",
    border: "1px solid rgba(59,130,246,0.3)",
  },
  camChip: {
    fontSize: "0.7rem",
    color: "#94a3b8",
    fontWeight: 500,
  },
  confVal: {
    fontSize: "0.72rem",
    fontWeight: 700,
    fontFamily: "monospace",
  },
  timeVal: {
    fontSize: "0.62rem",
    color: "#475569",
    fontFamily: "monospace",
  },
  emptyMsg: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    height: "100%",
    color: "#334155",
    fontSize: "0.8rem",
    letterSpacing: "0.04em",
  },
  footer: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "4px 10px",
    background: "#0f172a",
    borderTop: "1px solid #1e3a5f",
    flexShrink: 0,
  },
  footerText: {
    fontSize: "0.6rem",
    color: "#334155",
    fontFamily: "monospace",
  },
  footerDot: {
    width: 3,
    height: 3,
    borderRadius: "50%",
    background: "#334155",
    flexShrink: 0,
  },
} as const;
