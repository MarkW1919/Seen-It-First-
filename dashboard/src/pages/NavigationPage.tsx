import React, { useState, useEffect, useRef, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap } from "react-leaflet";
import { icon, LatLngTuple } from "leaflet";
import { useWebSocket } from "../hooks/useWebSocket";
import type {
  GeocodeResponse,
  RouteResponse,
  NavStatus,
  WsEvent,
} from "../types/navigation";

// ---------------------------------------------------------------------------
// Leaflet icon helpers (fix default icon path in Vite)
// ---------------------------------------------------------------------------
const blueIcon = icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

const redIcon = icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
});

// ---------------------------------------------------------------------------
// Helper: re-centre map when current position changes
// ---------------------------------------------------------------------------
function MapRecenter({ center }: { center: LatLngTuple }) {
  const map = useMap();
  useEffect(() => { map.setView(center, map.getZoom()); }, [center, map]);
  return null;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------
async function post<T>(path: string, body: object): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((err as { detail?: string }).detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

function formatDistance(m: number): string {
  return m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${Math.round(m)} m`;
}

function formatEta(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)}h ${m % 60}min`;
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function NavigationPage() {
  const qc = useQueryClient();

  // Address input state
  const [address, setAddress] = useState("");
  const [geocoded, setGeocoded] = useState<GeocodeResponse | null>(null);
  const [route, setRoute] = useState<RouteResponse | null>(null);

  // GPS from browser
  const [currentPos, setCurrentPos] = useState<[number, number] | null>(null);
  const gpsWatchId = useRef<number | null>(null);

  // Navigation session state
  const [navigating, setNavigating] = useState(false);
  const [arrived, setArrived] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Default map centre (continental US) — overridden by GPS
  const DEFAULT_CENTER: LatLngTuple = [39.5, -98.35];
  const mapCenter: LatLngTuple = currentPos ?? DEFAULT_CENTER;

  // ------------------------------------------------------------------
  // Navigation status polling (only while navigating)
  // ------------------------------------------------------------------
  useQuery<NavStatus>({
    queryKey: ["nav-status"],
    queryFn: () => fetch("/navigation/status").then((r) => r.json()),
    refetchInterval: navigating ? 5000 : false,
    enabled: navigating,
  });

  // ------------------------------------------------------------------
  // WebSocket — receive ARRIVED event
  // ------------------------------------------------------------------
  const handleWsEvent = useCallback((ev: WsEvent) => {
    if (ev.event === "ARRIVED") {
      setArrived(true);
      setNavigating(false);
      qc.invalidateQueries({ queryKey: ["nav-status"] });
    }
  }, [qc]);

  useWebSocket(handleWsEvent);

  // ------------------------------------------------------------------
  // Browser Geolocation — watch position and POST to backend
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!navigator.geolocation) return;

    gpsWatchId.current = navigator.geolocation.watchPosition(
      (pos) => {
        const { latitude: lat, longitude: lon } = pos.coords;
        setCurrentPos([lat, lon]);

        // Always POST GPS; backend ignores it when navigation is inactive
        post("/navigation/gps", { lat, lon }).catch(() => {/* ignore */});
      },
      (err) => console.warn("Geolocation error:", err.message),
      { enableHighAccuracy: true, maximumAge: 5000 },
    );

    return () => {
      if (gpsWatchId.current !== null) {
        navigator.geolocation.clearWatch(gpsWatchId.current);
      }
    };
  }, []);

  // ------------------------------------------------------------------
  // Geocode mutation
  // ------------------------------------------------------------------
  const geocodeMutation = useMutation<GeocodeResponse, Error, string>({
    mutationFn: (addr) => post<GeocodeResponse>("/navigation/geocode", { address: addr }),
    onSuccess: (data) => {
      setGeocoded(data);
      setRoute(null);
      setErrorMsg(null);
    },
    onError: (err) => setErrorMsg(`Geocode failed: ${err.message}`),
  });

  // ------------------------------------------------------------------
  // Route mutation (triggered when we have both current pos + destination)
  // ------------------------------------------------------------------
  const routeMutation = useMutation<RouteResponse, Error, void>({
    mutationFn: async () => {
      if (!currentPos || !geocoded) throw new Error("GPS or destination not set");
      return post<RouteResponse>("/navigation/route", {
        start_lat: currentPos[0],
        start_lon: currentPos[1],
        dest_lat: geocoded.lat,
        dest_lon: geocoded.lon,
      });
    },
    onSuccess: (data) => setRoute(data),
    onError: (err) => setErrorMsg(`Routing failed: ${err.message}`),
  });

  // Auto-fetch route when geocoded destination is set
  useEffect(() => {
    if (geocoded && currentPos && !route) {
      routeMutation.mutate();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geocoded, currentPos]);

  // ------------------------------------------------------------------
  // Start navigation mutation
  // ------------------------------------------------------------------
  const startMutation = useMutation<unknown, Error, void>({
    mutationFn: async () => {
      if (!geocoded) throw new Error("No destination geocoded");
      return post("/navigation/start", {
        dest_lat: geocoded.lat,
        dest_lon: geocoded.lon,
        display_name: geocoded.display_name,
      });
    },
    onSuccess: () => {
      setNavigating(true);
      setArrived(false);
      setErrorMsg(null);
    },
    onError: (err) => setErrorMsg(`Start failed: ${err.message}`),
  });

  // ------------------------------------------------------------------
  // Stop navigation mutation
  // ------------------------------------------------------------------
  const stopMutation = useMutation<unknown, Error, void>({
    mutationFn: () => post("/navigation/stop", {}),
    onSuccess: () => {
      setNavigating(false);
      setArrived(false);
      setRoute(null);
      setGeocoded(null);
      setAddress("");
      setErrorMsg(null);
    },
    onError: (err) => setErrorMsg(`Stop failed: ${err.message}`),
  });

  // ------------------------------------------------------------------
  // Render helpers
  // ------------------------------------------------------------------
  const routePolyline: LatLngTuple[] | undefined = route?.polyline.map(
    ([lat, lon]) => [lat, lon] as LatLngTuple,
  );

  const canStart = geocoded !== null && !navigating && !arrived;
  const isLoading =
    geocodeMutation.isPending ||
    routeMutation.isPending ||
    startMutation.isPending ||
    stopMutation.isPending;

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div style={styles.page}>
      {/* ── Header ─────────────────────────────────────────────── */}
      <header style={styles.header}>
        <span style={styles.logo}>Seen-It-First</span>
        <span style={styles.headerTitle}>Navigation &amp; LPR Activation</span>
      </header>

      {/* ── ARRIVED Banner ──────────────────────────────────────── */}
      {arrived && (
        <div style={styles.arrivedBanner}>
          🎯 ARRIVED AT LOCATION — SCANNING ACTIVATED
        </div>
      )}

      {/* ── Main layout ─────────────────────────────────────────── */}
      <div style={styles.layout}>
        {/* ── Sidebar ───────────────────────────────────────────── */}
        <aside style={styles.sidebar}>
          {/* Address input */}
          <section style={styles.card}>
            <h2 style={styles.cardTitle}>Destination</h2>
            <input
              style={styles.input}
              type="text"
              placeholder="Enter address or place name…"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && address.trim()) {
                  geocodeMutation.mutate(address.trim());
                }
              }}
              disabled={navigating || isLoading}
            />
            <button
              style={{ ...styles.btn, ...styles.btnSecondary }}
              onClick={() => address.trim() && geocodeMutation.mutate(address.trim())}
              disabled={!address.trim() || navigating || isLoading}
            >
              {geocodeMutation.isPending ? "Searching…" : "Search"}
            </button>

            {geocoded && (
              <div style={styles.geocodeResult}>
                <div style={styles.geocodeLabel}>📍 {geocoded.display_name}</div>
                <div style={styles.geocodeCoords}>
                  {geocoded.lat.toFixed(5)}, {geocoded.lon.toFixed(5)}
                </div>
              </div>
            )}
          </section>

          {/* Route info */}
          {route && (
            <section style={styles.card}>
              <h2 style={styles.cardTitle}>Route</h2>
              <div style={styles.routeRow}>
                <span style={styles.routeLabel}>Distance</span>
                <span style={styles.routeValue}>{formatDistance(route.distance_m)}</span>
              </div>
              <div style={styles.routeRow}>
                <span style={styles.routeLabel}>Duration</span>
                <span style={styles.routeValue}>{formatDuration(route.duration_s)}</span>
              </div>
              <div style={styles.routeRow}>
                <span style={styles.routeLabel}>ETA</span>
                <span style={styles.routeValue}>{formatEta(route.eta_iso)}</span>
              </div>
            </section>
          )}

          {/* Navigation status */}
          <section style={styles.card}>
            <h2 style={styles.cardTitle}>Status</h2>
            <div style={styles.statusRow}>
              <span style={styles.statusLabel}>GPS</span>
              <StatusBadge active={!!currentPos} activeText="Locked" inactiveText="No Signal" />
            </div>
            <div style={styles.statusRow}>
              <span style={styles.statusLabel}>Navigation</span>
              <StatusBadge active={navigating} activeText="Active" inactiveText="Idle" />
            </div>
            <div style={styles.statusRow}>
              <span style={styles.statusLabel}>LPR Pipeline</span>
              <StatusBadge
                active={arrived || !navigating}
                activeText="ACTIVE"
                inactiveText="IDLE (en route)"
                activeColor="#22c55e"
                inactiveColor="#f59e0b"
              />
            </div>
          </section>

          {/* Actions */}
          <section style={styles.card}>
            {!navigating && !arrived ? (
              <button
                style={{ ...styles.btn, ...styles.btnPrimary }}
                onClick={() => startMutation.mutate()}
                disabled={!canStart || isLoading}
              >
                {startMutation.isPending ? "Starting…" : "▶ Start Navigation"}
              </button>
            ) : (
              <button
                style={{ ...styles.btn, ...styles.btnDanger }}
                onClick={() => stopMutation.mutate()}
                disabled={isLoading}
              >
                {stopMutation.isPending ? "Stopping…" : "■ Stop Navigation"}
              </button>
            )}
          </section>

          {/* Error display */}
          {errorMsg && (
            <div style={styles.errorBox}>⚠ {errorMsg}</div>
          )}
        </aside>

        {/* ── Map ───────────────────────────────────────────────── */}
        <div style={styles.mapWrapper}>
          <MapContainer
            center={mapCenter}
            zoom={13}
            style={{ height: "100%", width: "100%" }}
          >
            <TileLayer
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            />

            {/* Re-centre on current position */}
            {currentPos && <MapRecenter center={currentPos} />}

            {/* Current GPS position marker */}
            {currentPos && (
              <Marker position={currentPos} icon={blueIcon}>
                <Popup>Current Location</Popup>
              </Marker>
            )}

            {/* Destination marker */}
            {geocoded && (
              <Marker position={[geocoded.lat, geocoded.lon]} icon={redIcon}>
                <Popup>{geocoded.display_name}</Popup>
              </Marker>
            )}

            {/* Route polyline */}
            {routePolyline && routePolyline.length > 0 && (
              <Polyline positions={routePolyline} color="#3b82f6" weight={4} opacity={0.8} />
            )}
          </MapContainer>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StatusBadge sub-component
// ---------------------------------------------------------------------------
function StatusBadge({
  active,
  activeText,
  inactiveText,
  activeColor = "#22c55e",
  inactiveColor = "#64748b",
}: {
  active: boolean;
  activeText: string;
  inactiveText: string;
  activeColor?: string;
  inactiveColor?: string;
}) {
  return (
    <span
      style={{
        ...styles.badge,
        backgroundColor: active ? activeColor : inactiveColor,
      }}
    >
      {active ? activeText : inactiveText}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Inline styles (no CSS framework dependency)
// ---------------------------------------------------------------------------
const styles = {
  page: {
    display: "flex",
    flexDirection: "column" as const,
    height: "100vh",
    overflow: "hidden",
    background: "#0f172a",
    color: "#e2e8f0",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    padding: "0.75rem 1.25rem",
    background: "#1e293b",
    borderBottom: "1px solid #334155",
    flexShrink: 0,
  },
  logo: {
    fontWeight: 700,
    fontSize: "1.1rem",
    color: "#3b82f6",
    letterSpacing: "0.02em",
  },
  headerTitle: {
    fontSize: "0.9rem",
    color: "#94a3b8",
  },
  arrivedBanner: {
    background: "#16a34a",
    color: "#fff",
    textAlign: "center" as const,
    fontWeight: 700,
    fontSize: "1.1rem",
    padding: "0.75rem",
    letterSpacing: "0.05em",
    flexShrink: 0,
    animation: "pulse 2s ease-in-out infinite",
  },
  layout: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },
  sidebar: {
    width: "320px",
    minWidth: "260px",
    background: "#1e293b",
    borderRight: "1px solid #334155",
    padding: "1rem",
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.75rem",
    overflowY: "auto" as const,
    flexShrink: 0,
  },
  card: {
    background: "#0f172a",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "0.875rem",
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.5rem",
  },
  cardTitle: {
    fontSize: "0.75rem",
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.08em",
    color: "#64748b",
    marginBottom: "0.25rem",
  },
  input: {
    background: "#1e293b",
    border: "1px solid #475569",
    borderRadius: "6px",
    color: "#e2e8f0",
    padding: "0.5rem 0.75rem",
    fontSize: "0.875rem",
    outline: "none",
    width: "100%",
  },
  btn: {
    width: "100%",
    padding: "0.6rem 1rem",
    borderRadius: "6px",
    fontWeight: 600,
    fontSize: "0.875rem",
    cursor: "pointer",
    border: "none",
    transition: "opacity 0.15s",
  },
  btnPrimary: {
    background: "#3b82f6",
    color: "#fff",
  },
  btnSecondary: {
    background: "#334155",
    color: "#e2e8f0",
  },
  btnDanger: {
    background: "#ef4444",
    color: "#fff",
  },
  geocodeResult: {
    marginTop: "0.25rem",
    padding: "0.5rem",
    background: "#1e293b",
    borderRadius: "6px",
  },
  geocodeLabel: {
    fontSize: "0.8rem",
    color: "#cbd5e1",
    wordBreak: "break-word" as const,
  },
  geocodeCoords: {
    fontSize: "0.7rem",
    color: "#64748b",
    marginTop: "0.2rem",
  },
  routeRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  routeLabel: {
    fontSize: "0.8rem",
    color: "#94a3b8",
  },
  routeValue: {
    fontSize: "0.875rem",
    fontWeight: 600,
    color: "#e2e8f0",
  },
  statusRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    minHeight: "1.75rem",
  },
  statusLabel: {
    fontSize: "0.8rem",
    color: "#94a3b8",
  },
  badge: {
    fontSize: "0.7rem",
    fontWeight: 700,
    padding: "0.2rem 0.5rem",
    borderRadius: "999px",
    color: "#fff",
    letterSpacing: "0.04em",
  },
  errorBox: {
    background: "#450a0a",
    border: "1px solid #ef4444",
    borderRadius: "6px",
    color: "#fca5a5",
    fontSize: "0.8rem",
    padding: "0.5rem 0.75rem",
  },
  mapWrapper: {
    flex: 1,
    position: "relative" as const,
    overflow: "hidden",
  },
} as const;
