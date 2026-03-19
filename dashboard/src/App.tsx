import { useState, useCallback, type CSSProperties } from "react";
import NavigationHUD from "./pages/NavigationHUD";
import CameraViews from "./pages/CameraViews";
import HotlistAlerts from "./pages/HotlistAlerts";
import FieldSettings from "./pages/FieldSettings";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
type Tab = "nav" | "hotlist" | "cameras" | "settings";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "nav", label: "Navigation HUD", icon: "◎" },
  { id: "hotlist", label: "Hotlist Alerts", icon: "⚠" },
  { id: "cameras", label: "Camera Views", icon: "◩" },
  { id: "settings", label: "Settings", icon: "⚙" },
];

// ---------------------------------------------------------------------------
// Determine initial tab from URL
// ---------------------------------------------------------------------------
function getInitialTab(): Tab {
  const p = new URLSearchParams(window.location.search).get("screen");
  if (p === "cameras") return "cameras";
  if (p === "settings") return "settings";
  if (p === "hotlist") return "hotlist";
  return "nav";
}

// ---------------------------------------------------------------------------
// App Shell
// ---------------------------------------------------------------------------
export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>(getInitialTab);
  const [arrived, setArrived] = useState(false);
  const [gpsLocked, setGpsLocked] = useState(false);
  const [navigating, setNavigating] = useState(false);
  const [camOnline, setCamOnline] = useState(0);

  const handleNavState = useCallback((state: {
    arrived?: boolean;
    gpsLocked?: boolean;
    navigating?: boolean;
    camOnline?: number;
  }) => {
    if (state.arrived !== undefined) setArrived(state.arrived);
    if (state.gpsLocked !== undefined) setGpsLocked(state.gpsLocked);
    if (state.navigating !== undefined) setNavigating(state.navigating);
    if (state.camOnline !== undefined) setCamOnline(state.camOnline);
  }, []);

  return (
    <div style={S.shell}>
      {/* ── Top Bar ─────────────────────────────────────────────── */}
      <header style={S.header}>
        <div style={S.brand}>
          <span style={S.logo}>SEEN-IT-FIRST</span>
          <span style={S.edition}>EDGE</span>
        </div>
        <nav style={S.tabBar}>
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                ...S.tabBtn,
                ...(activeTab === tab.id ? S.tabActive : {}),
              }}
            >
              <span style={S.tabIcon}>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
      </header>

      {/* ── Arrived Banner ──────────────────────────────────────── */}
      {arrived && (
        <div style={S.arrivedBanner}>
          <span style={S.arrivedIcon}>●</span>
          ARRIVED AT LOCATION — LPR SCANNING ACTIVATED
        </div>
      )}

      {/* ── Main Content ────────────────────────────────────────── */}
      <main style={S.main}>
        {activeTab === "nav" && <NavigationHUD onStateChange={handleNavState} />}
        {activeTab === "hotlist" && <HotlistAlerts />}
        {activeTab === "cameras" && <CameraViews />}
        {activeTab === "settings" && <FieldSettings />}
      </main>

      {/* ── Status Bar ──────────────────────────────────────────── */}
      <footer style={S.statusBar}>
        <StatusPill
          label="GPS"
          value={gpsLocked ? "Locked" : "Searching"}
          color={gpsLocked ? "#22c55e" : "#f59e0b"}
        />
        <StatusPill label="DB" value="Online" color="#22c55e" />
        <StatusPill
          label="CAM"
          value={`${camOnline}/4 Online`}
          color={camOnline >= 3 ? "#22c55e" : camOnline >= 1 ? "#f59e0b" : "#ef4444"}
        />
        <StatusPill label="Storage" value="OK" color="#22c55e" />
        <div style={S.statusSpacer} />
        <span style={S.modeLabel}>
          {navigating
            ? "Navigating · Route active"
            : arrived
              ? "On scene · Scanning"
              : "Navigation idle · Quad-scan mode"}
        </span>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status Pill sub-component
// ---------------------------------------------------------------------------
function StatusPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={S.pill}>
      <span style={{ ...S.pillDot, background: color }} />
      <span style={S.pillLabel}>{label}:</span>
      <span style={S.pillValue}>{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const S: Record<string, CSSProperties> = {
  shell: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    overflow: "hidden",
    background: "#080c14",
  },

  // Header
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 1rem",
    height: "52px",
    background: "linear-gradient(180deg, #111827 0%, #0c1220 100%)",
    borderBottom: "1px solid #1e293b",
    flexShrink: 0,
    zIndex: 10,
  },
  brand: {
    display: "flex",
    alignItems: "baseline",
    gap: "0.5rem",
  },
  logo: {
    fontWeight: 800,
    fontSize: "1rem",
    letterSpacing: "0.12em",
    color: "#3b82f6",
  },
  edition: {
    fontSize: "0.65rem",
    fontWeight: 700,
    letterSpacing: "0.15em",
    color: "#475569",
    border: "1px solid #334155",
    borderRadius: "4px",
    padding: "1px 5px",
  },
  tabBar: {
    display: "flex",
    gap: "4px",
  },
  tabBtn: {
    display: "flex",
    alignItems: "center",
    gap: "6px",
    padding: "8px 14px",
    borderRadius: "8px",
    fontSize: "0.82rem",
    fontWeight: 600,
    color: "#94a3b8",
    background: "transparent",
    border: "1px solid transparent",
    transition: "all 0.15s ease",
    minHeight: "38px",
  },
  tabActive: {
    color: "#e8edf5",
    background: "rgba(37, 99, 235, 0.15)",
    border: "1px solid #2563eb",
  },
  tabIcon: {
    fontSize: "0.9rem",
  },

  // Arrived banner
  arrivedBanner: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    background: "linear-gradient(90deg, #15803d, #16a34a, #15803d)",
    color: "#fff",
    fontWeight: 800,
    fontSize: "0.95rem",
    padding: "10px",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    flexShrink: 0,
    animation: "pulse-glow 2s ease-in-out infinite",
  },
  arrivedIcon: {
    color: "#4ade80",
    fontSize: "1.1rem",
  },

  // Main
  main: {
    flex: 1,
    overflow: "hidden",
    position: "relative",
  },

  // Status bar
  statusBar: {
    display: "flex",
    alignItems: "center",
    gap: "12px",
    padding: "0 1rem",
    height: "32px",
    background: "#0c1220",
    borderTop: "1px solid #1e293b",
    flexShrink: 0,
    fontSize: "0.72rem",
    fontFamily: "'SF Mono', 'Fira Code', 'Cascadia Code', monospace",
  },
  pill: {
    display: "flex",
    alignItems: "center",
    gap: "5px",
  },
  pillDot: {
    width: "7px",
    height: "7px",
    borderRadius: "50%",
    flexShrink: 0,
  },
  pillLabel: {
    color: "#64748b",
    fontWeight: 600,
  },
  pillValue: {
    color: "#94a3b8",
  },
  statusSpacer: {
    flex: 1,
  },
  modeLabel: {
    color: "#475569",
    fontStyle: "italic",
  },
};
