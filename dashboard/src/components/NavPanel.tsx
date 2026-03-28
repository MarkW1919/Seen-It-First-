import React from "react";
import type { GeocodeResponse, RouteResponse } from "../types/navigation";

const RADIUS_MIN_FT = 1;
const RADIUS_MAX_FT = 1320;

function fmtDist(m: number) {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}
function fmtEta(iso: string) {
  try { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
}
function fmtDur(s: number) {
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)}h ${m % 60}min`;
}

interface Props {
  // Address / destination
  address: string;
  onAddressChange: (v: string) => void;
  geocoded: GeocodeResponse | null;
  onSearch: () => void;
  searchPending: boolean;

  // Route
  route: RouteResponse | null;

  // Radius
  arrivalRadiusFt: number;
  onRadiusChange: (v: number) => void;

  // State flags
  navigating: boolean;
  arrived: boolean;
  gpsLocked: boolean;
  pipelineActive: boolean;
  wsConnected: boolean;
  detectionCount: number;

  // Mutations
  onStart: () => void;
  onStop: () => void;
  startPending: boolean;
  stopPending: boolean;

  errorMsg: string | null;

  // View toggle
  view: "cameras" | "map";
  onViewChange: (v: "cameras" | "map") => void;
}

export function NavPanel(p: Props) {
  const canStart = p.geocoded !== null && !p.navigating && !p.arrived;
  const anyLoading = p.searchPending || p.startPending || p.stopPending;

  return (
    <aside style={s.panel}>
      {/* ── Brand ─────────────────────────────────────────────── */}
      <div style={s.brand}>
        <div style={s.brandMark}>SIF</div>
        <div>
          <div style={s.brandName}>Seen-It-First</div>
          <div style={s.brandSub}>Tactical LPR System</div>
        </div>
      </div>

      {/* ── View Toggle ─────────────────────────────────────── */}
      <div style={s.viewToggle}>
        <button
          style={{ ...s.viewBtn, ...(p.view === "cameras" ? s.viewBtnActive : {}) }}
          onClick={() => p.onViewChange("cameras")}
        >
          📷 Cameras
        </button>
        <button
          style={{ ...s.viewBtn, ...(p.view === "map" ? s.viewBtnActive : {}) }}
          onClick={() => p.onViewChange("map")}
        >
          🗺 Map
        </button>
      </div>

      {/* ── System Status ─────────────────────────────────── */}
      <div style={s.card}>
        <div style={s.cardTitle}>System</div>
        <StatusRow label="GPS" active={p.gpsLocked} yes="Locked" no="No Signal" />
        <StatusRow label="Network" active={p.wsConnected} yes="Connected" no="Offline" />
        <StatusRow
          label="LPR Pipeline"
          active={p.pipelineActive}
          yes="ACTIVE"
          no="IDLE"
          activeColor="#22c55e"
          inactiveColor="#f59e0b"
        />
        <div style={s.statRow}>
          <span style={s.statLabel}>Detections</span>
          <span style={s.statVal}>{p.detectionCount}</span>
        </div>
      </div>

      {/* ── Destination ──────────────────────────────────── */}
      <div style={s.card}>
        <div style={s.cardTitle}>Destination</div>
        <input
          style={s.input}
          type="text"
          placeholder="lat,lon  or  cached address…"
          value={p.address}
          onChange={(e) => p.onAddressChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && p.address.trim() && !p.navigating) {
              p.onSearch();
            }
          }}
          disabled={p.navigating || anyLoading}
        />
        <button
          style={{ ...s.btn, ...s.btnSecondary }}
          onClick={p.onSearch}
          disabled={!p.address.trim() || p.navigating || anyLoading}
        >
          {p.searchPending ? "Resolving…" : "Resolve"}
        </button>

        {p.geocoded && (
          <div style={s.geocodeBox}>
            <div style={s.geocodePin}>📍 {p.geocoded.display_name}</div>
            <div style={s.geocodeCoords}>
              {p.geocoded.lat.toFixed(5)}, {p.geocoded.lon.toFixed(5)}
            </div>
          </div>
        )}
      </div>

      {/* ── Arrival Radius ───────────────────────────────── */}
      <div style={s.card}>
        <div style={s.cardTitle}>Arrival Trigger</div>
        <input
          type="range"
          min={RADIUS_MIN_FT}
          max={RADIUS_MAX_FT}
          step={10}
          value={p.arrivalRadiusFt}
          onChange={(e) => p.onRadiusChange(Number(e.target.value))}
          disabled={p.navigating}
          style={s.slider}
        />
        <div style={s.sliderVal}>
          <strong style={{ color: "#e2e8f0" }}>{p.arrivalRadiusFt} ft</strong>
          <span style={{ color: "#475569", fontSize: "0.65rem" }}>
            ({(p.arrivalRadiusFt * 0.3048).toFixed(0)} m)
          </span>
        </div>
      </div>

      {/* ── Route Info ──────────────────────────────────── */}
      {p.route && (
        <div style={s.card}>
          <div style={s.cardTitle}>Route</div>
          <InfoRow label="Distance" value={fmtDist(p.route.distance_m)} />
          <InfoRow label="ETA"      value={fmtEta(p.route.eta_iso)} />
          <InfoRow label="Drive"    value={fmtDur(p.route.duration_s)} />
        </div>
      )}

      {/* ── Navigation Action ───────────────────────────── */}
      <div style={s.card}>
        {!p.navigating && !p.arrived ? (
          <button
            style={{ ...s.btn, ...s.btnGreen }}
            onClick={p.onStart}
            disabled={!canStart || anyLoading}
          >
            {p.startPending ? "Starting…" : "▶  Start Navigation"}
          </button>
        ) : (
          <button
            style={{ ...s.btn, ...s.btnRed }}
            onClick={p.onStop}
            disabled={anyLoading}
          >
            {p.stopPending ? "Stopping…" : "■  Stop Navigation"}
          </button>
        )}
      </div>

      {/* ── Error ───────────────────────────────────────── */}
      {p.errorMsg && (
        <div style={s.error}>⚠ {p.errorMsg}</div>
      )}

      <div style={{ flex: 1 }} />

      {/* ── Footer ─────────────────────────────────────── */}
      <div style={s.footer}>
        <span>v1.0 · Jetson Orin Nano Super</span>
      </div>
    </aside>
  );
}

/* ── Sub-components ─────────────────────────────────────────────────────── */

function StatusRow({
  label, active, yes, no,
  activeColor = "#22c55e",
  inactiveColor = "#64748b",
}: {
  label: string; active: boolean;
  yes: string; no: string;
  activeColor?: string; inactiveColor?: string;
}) {
  return (
    <div style={s.statRow}>
      <span style={s.statLabel}>{label}</span>
      <span style={{
        fontSize: "0.65rem",
        fontWeight: 700,
        padding: "1px 7px",
        borderRadius: "999px",
        background: active ? activeColor : inactiveColor,
        color: "#fff",
        letterSpacing: "0.04em",
      }}>
        {active ? yes : no}
      </span>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={s.statRow}>
      <span style={s.statLabel}>{label}</span>
      <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "#e2e8f0" }}>{value}</span>
    </div>
  );
}

/* ── Styles ─────────────────────────────────────────────────────────────── */
const s = {
  panel: {
    width: 248,
    minWidth: 248,
    background: "#0d1528",
    borderRight: "1px solid #1e3a5f",
    display: "flex",
    flexDirection: "column" as const,
    gap: "8px",
    padding: "10px 8px",
    overflowY: "auto" as const,
    flexShrink: 0,
  },
  brand: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    paddingBottom: "8px",
    borderBottom: "1px solid #1e3a5f",
    marginBottom: "2px",
  },
  brandMark: {
    width: 34,
    height: 34,
    background: "#1d4ed8",
    borderRadius: "6px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "0.75rem",
    fontWeight: 900,
    color: "#fff",
    letterSpacing: "0.05em",
    flexShrink: 0,
  },
  brandName: {
    fontSize: "0.82rem",
    fontWeight: 700,
    color: "#e2e8f0",
    letterSpacing: "0.02em",
  },
  brandSub: {
    fontSize: "0.6rem",
    color: "#475569",
    letterSpacing: "0.04em",
    marginTop: "1px",
  },
  viewToggle: {
    display: "flex",
    gap: "4px",
  },
  viewBtn: {
    flex: 1,
    padding: "5px",
    border: "1px solid #1e3a5f",
    borderRadius: "4px",
    background: "transparent",
    color: "#64748b",
    fontSize: "0.68rem",
    fontWeight: 600,
    cursor: "pointer",
    letterSpacing: "0.02em",
  },
  viewBtnActive: {
    background: "#1e3a5f",
    borderColor: "#2563eb",
    color: "#93c5fd",
  },
  card: {
    background: "#0f1f3d",
    border: "1px solid #1e3a5f",
    borderRadius: "6px",
    padding: "8px",
    display: "flex",
    flexDirection: "column" as const,
    gap: "5px",
  },
  cardTitle: {
    fontSize: "0.6rem",
    fontWeight: 700,
    textTransform: "uppercase" as const,
    letterSpacing: "0.1em",
    color: "#334155",
    marginBottom: "2px",
  },
  statRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    minHeight: "1.5rem",
  },
  statLabel: {
    fontSize: "0.72rem",
    color: "#64748b",
  },
  statVal: {
    fontSize: "0.8rem",
    fontWeight: 700,
    fontFamily: "monospace",
    color: "#e2e8f0",
  },
  input: {
    background: "#0a1020",
    border: "1px solid #1e3a5f",
    borderRadius: "4px",
    color: "#e2e8f0",
    padding: "5px 8px",
    fontSize: "0.75rem",
    outline: "none",
    width: "100%",
    fontFamily: "monospace",
  },
  slider: {
    width: "100%",
    accentColor: "#2563eb",
    cursor: "pointer",
  },
  sliderVal: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: "0.78rem",
  },
  geocodeBox: {
    background: "#0a1020",
    border: "1px solid #1e3a5f",
    borderRadius: "4px",
    padding: "6px",
  },
  geocodePin: {
    fontSize: "0.7rem",
    color: "#93c5fd",
    wordBreak: "break-word" as const,
  },
  geocodeCoords: {
    fontSize: "0.6rem",
    color: "#334155",
    fontFamily: "monospace",
    marginTop: "2px",
  },
  btn: {
    width: "100%",
    padding: "7px",
    borderRadius: "5px",
    fontWeight: 700,
    fontSize: "0.78rem",
    cursor: "pointer",
    border: "none",
    letterSpacing: "0.02em",
  },
  btnSecondary: {
    background: "#1e3a5f",
    color: "#93c5fd",
  },
  btnGreen: {
    background: "#166534",
    color: "#86efac",
    border: "1px solid #16a34a",
  },
  btnRed: {
    background: "#7f1d1d",
    color: "#fca5a5",
    border: "1px solid #dc2626",
  },
  error: {
    background: "#300a0a",
    border: "1px solid #7f1d1d",
    borderRadius: "4px",
    color: "#fca5a5",
    fontSize: "0.7rem",
    padding: "6px 8px",
  },
  footer: {
    fontSize: "0.58rem",
    color: "#1e3a5f",
    textAlign: "center" as const,
    padding: "4px 0",
    fontFamily: "monospace",
  },
} as const;
