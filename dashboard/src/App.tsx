import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import NavigationHUD from "./pages/NavigationHUD";
import CameraViews from "./pages/CameraViews";
import HotlistAlerts from "./pages/HotlistAlerts";
import FieldSettings from "./pages/FieldSettings";
import type { NavStatus, RuntimeStatusResponse } from "./types/navigation";

type Tab = "nav" | "hotlist" | "cameras" | "settings";

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: "nav", label: "Navigation HUD", icon: "NAV" },
  { id: "hotlist", label: "Hotlist Alerts", icon: "HOT" },
  { id: "cameras", label: "Camera Ops", icon: "CAM" },
  { id: "settings", label: "Settings", icon: "CFG" },
];

function getInitialTab(): Tab {
  const p = new URLSearchParams(window.location.search).get("screen");
  if (p === "cameras") return "cameras";
  if (p === "settings") return "settings";
  if (p === "hotlist") return "hotlist";
  return "nav";
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>(getInitialTab);
  const [arrivedState, setArrivedState] = useState(false);
  const [gpsLockedState, setGpsLockedState] = useState(false);
  const [navigatingState, setNavigatingState] = useState(false);
  const [camOnlineState, setCamOnlineState] = useState(0);

  const runtimeQuery = useQuery<RuntimeStatusResponse>({
    queryKey: ["app-runtime-status"],
    queryFn: async () => {
      const res = await fetch("/navigation/runtime");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<RuntimeStatusResponse>;
    },
    refetchInterval: 5_000,
  });

  const statusQuery = useQuery<NavStatus>({
    queryKey: ["app-nav-status"],
    queryFn: async () => {
      const res = await fetch("/navigation/status");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<NavStatus>;
    },
    refetchInterval: 5_000,
  });

  const handleNavState = useCallback((state: {
    arrived?: boolean;
    gpsLocked?: boolean;
    navigating?: boolean;
    camOnline?: number;
  }) => {
    if (state.arrived !== undefined) setArrivedState(state.arrived);
    if (state.gpsLocked !== undefined) setGpsLockedState(state.gpsLocked);
    if (state.navigating !== undefined) setNavigatingState(state.navigating);
    if (state.camOnline !== undefined) setCamOnlineState(state.camOnline);
  }, []);

  const arrived = statusQuery.data?.arrival.arrived ?? arrivedState;
  const navigating = statusQuery.data?.navigating ?? navigatingState;
  const gpsLocked = runtimeQuery.data?.operator_gps !== null && runtimeQuery.data?.operator_gps !== undefined
    ? true
    : gpsLockedState;
  const camOnline = runtimeQuery.data?.cameras
    ? runtimeQuery.data.cameras.filter((camera) => camera.status === "Online").length
    : camOnlineState;
  const totalCameras = runtimeQuery.data?.cameras.length ?? 4;
  const camStatusColor = totalCameras > 0 && camOnline === totalCameras
    ? "#22c55e"
    : camOnline >= 1
      ? "#f59e0b"
      : "#ef4444";

  useEffect(() => {
    const url = new URL(window.location.href);
    if (activeTab === "nav") {
      url.searchParams.delete("screen");
    } else {
      url.searchParams.set("screen", activeTab);
    }
    window.history.replaceState({}, "", url);
  }, [activeTab]);

  return (
    <div style={S.shell}>
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

      {arrived && (
        <div style={S.arrivedBanner}>
          <span style={S.arrivedIcon}>LIVE</span>
          ARRIVED AT LOCATION - LPR SCANNING ACTIVE
        </div>
      )}

      <main style={S.main}>
        {activeTab === "nav" && <NavigationHUD onStateChange={handleNavState} />}
        {activeTab === "hotlist" && <HotlistAlerts />}
        {activeTab === "cameras" && <CameraViews />}
        {activeTab === "settings" && <FieldSettings />}
      </main>

      <footer style={S.statusBar}>
        <StatusPill
          label="GPS"
          value={gpsLocked ? "Locked" : "Searching"}
          color={gpsLocked ? "#22c55e" : "#f59e0b"}
        />
        <StatusPill label="DB" value="Online" color="#22c55e" />
        <StatusPill
          label="CAM"
          value={`${camOnline}/${totalCameras} Online`}
          color={camStatusColor}
        />
        <StatusPill label="Storage" value="OK" color="#22c55e" />
        <div style={S.statusSpacer} />
        <span style={S.modeLabel}>
          {navigating
            ? "Navigating | route active"
            : arrived
              ? "On scene | scanning"
              : "Navigation idle | quad scan mode"}
        </span>
      </footer>
    </div>
  );
}

function StatusPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={S.pill}>
      <span style={{ ...S.pillDot, background: color }} />
      <span style={S.pillLabel}>{label}:</span>
      <span style={S.pillValue}>{value}</span>
    </div>
  );
}

const S: Record<string, CSSProperties> = {
  shell: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    overflow: "hidden",
    background: "#080c14",
  },
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
    fontSize: "0.72rem",
    fontWeight: 800,
    letterSpacing: "0.08em",
    color: "#7dd3fc",
  },
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
  },
  arrivedIcon: {
    fontSize: "0.72rem",
    fontWeight: 800,
    color: "#dcfce7",
  },
  main: {
    flex: 1,
    overflow: "hidden",
    position: "relative",
  },
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
