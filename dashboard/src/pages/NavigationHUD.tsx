import { useState, useEffect, useRef, useCallback, type CSSProperties } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap } from "react-leaflet";
import { icon, type LatLngTuple } from "leaflet";
import { useWebSocket } from "../hooks/useWebSocket";
import { TargetList } from "../components/TargetList";
import type {
  GeocodeResponse,
  RouteResponse,
  NavStatus,
  WsEvent,
  RankedVehicle,
  DetectionSearchResponse,
  DetectionRecord,
} from "../types/navigation";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const RADIUS_MIN_FT = 1;
const RADIUS_MAX_FT = 1320;
const RADIUS_DEFAULT_FT = 300;
const GPS_POST_INTERVAL_MS = 2000;
const CAMERAS = [
  { id: "cam-front-1", label: "FL", name: "Front Left", status: "Online" },
  { id: "cam-side-2", label: "FR", name: "Front Right", status: "Online" },
  { id: "cam-rear-3", label: "RL", name: "Rear Left", status: "Online" },
  { id: "cam-west-4", label: "RR", name: "Rear Right", status: "Offline" },
];

const PREVIEW_TARGETS: RankedVehicle[] = [
  {
    vehicle_id: "veh-top-001", vehicle_type: "suv", make: "ford", model: "explorer",
    color: "black", year_range: "2018-2021", plate: "8ABC123", confidence: 0.92,
    distance_ft: 128, hotlist_match: true, score: 98.4, latitude: 37.4221,
    longitude: -122.0841, timestamp: Date.now(), camera_id: "cam-front-1",
    fingerprint: "d9f30eab82aa4a45bb4f451f9f0f1307",
  },
  {
    vehicle_id: "veh-002", vehicle_type: "sedan", make: "toyota", model: "camry",
    color: "silver", year_range: "2017-2019", plate: null, confidence: 0.81,
    distance_ft: 206, hotlist_match: false, score: 76.1, latitude: 37.4216,
    longitude: -122.0834, timestamp: Date.now(), camera_id: "cam-side-2",
    fingerprint: "8217bc923f7442be8d3247f5cbafe0cc",
  },
];

// Leaflet icons
const blueIcon = icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});
const redIcon = icon({
  iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});

// ---------------------------------------------------------------------------
// Helpers
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
  try { return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
  catch { return iso; }
}
function formatDuration(s: number): string {
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)}h ${m % 60}min`;
}

function MapRecenter({ center }: { center: LatLngTuple }) {
  const map = useMap();
  useEffect(() => { map.setView(center, map.getZoom()); }, [center, map]);
  return null;
}

type PreviewMode = "base" | "route" | "arrived";
function getPreviewMode(): PreviewMode | null {
  if (typeof window === "undefined") return null;
  const m = new URLSearchParams(window.location.search).get("preview");
  if (m === "base" || m === "route" || m === "arrived") return m;
  return null;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface Props {
  onStateChange: (state: {
    arrived?: boolean;
    gpsLocked?: boolean;
    navigating?: boolean;
    camOnline?: number;
  }) => void;
}

// ---------------------------------------------------------------------------
// Navigation HUD
// ---------------------------------------------------------------------------
export default function NavigationHUD({ onStateChange }: Props) {
  const qc = useQueryClient();
  const previewMode = getPreviewMode();
  const isPreview = previewMode !== null;

  // View mode: quad cameras vs map
  const [viewMode, setViewMode] = useState<"cameras" | "map">("cameras");

  // Navigation state
  const [address, setAddress] = useState("");
  const [geocoded, setGeocoded] = useState<GeocodeResponse | null>(null);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [arrivalRadiusFt, setArrivalRadiusFt] = useState(RADIUS_DEFAULT_FT);
  const [currentPos, setCurrentPos] = useState<[number, number] | null>(
    isPreview ? [37.4220, -122.0841] : null,
  );
  const currentPosRef = useRef<[number, number] | null>(null);
  const [navigating, setNavigating] = useState(false);
  const [arrived, setArrived] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Investigation search
  const [searchPlate, setSearchPlate] = useState("");
  const [searchVin, setSearchVin] = useState("");
  const [searchMake, setSearchMake] = useState("");
  const [searchModel, setSearchModel] = useState("");

  // Detection history
  const [addressDetections, setAddressDetections] = useState<DetectionRecord[]>([]);
  const [selectedDetection, setSelectedDetection] = useState<DetectionRecord | null>(null);
  const [showDetectionsModal, setShowDetectionsModal] = useState(false);
  const [addressNotice, setAddressNotice] = useState<string | null>(null);

  // Recovery log
  const [recoveryFilter, setRecoveryFilter] = useState("all statuses");
  const [recoverySearch, setRecoverySearch] = useState("");

  // Notify parent of state changes
  useEffect(() => {
    onStateChange({
      arrived,
      gpsLocked: !!currentPos,
      navigating,
      camOnline: CAMERAS.filter((c) => c.status === "Online").length,
    });
  }, [arrived, currentPos, navigating, onStateChange]);

  // Auto-switch to map when navigating
  useEffect(() => {
    if (navigating && !arrived) setViewMode("map");
    if (arrived) setViewMode("cameras");
  }, [navigating, arrived]);

  // Preview mode setup
  useEffect(() => {
    if (!previewMode) return;
    setAddress("1600 Amphitheatre Parkway, Mountain View, CA");
    setGeocoded({ lat: 37.4182, lon: -122.0802, display_name: "Google Building 41, Amphitheatre Pkwy" });
    if (previewMode === "route") { setRoute({ polyline: [[37.4232,-122.0866],[37.4225,-122.0848],[37.4214,-122.0831],[37.4199,-122.0817],[37.4182,-122.0802]], distance_m: 4820, duration_s: 660, eta_iso: "2026-01-01T14:35:00.000Z" }); setNavigating(true); }
    if (previewMode === "arrived") { setNavigating(false); setArrived(true); }
  }, [previewMode]);

  // Map center
  const DEFAULT_CENTER: LatLngTuple = [39.5, -98.35];
  const mapCenter: LatLngTuple = currentPos ?? DEFAULT_CENTER;

  // Nav status polling
  const { data: navStatus } = useQuery<NavStatus>({
    queryKey: ["nav-status"],
    queryFn: async () => {
      const res = await fetch("/navigation/status");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<NavStatus>;
    },
    refetchInterval: navigating ? 5000 : false,
    enabled: !isPreview && navigating,
  });

  // WebSocket
  const handleWsEvent = useCallback((ev: WsEvent) => {
    if (ev.event === "ARRIVED") {
      setArrived(true);
      setNavigating(false);
      qc.invalidateQueries({ queryKey: ["nav-status"] });
    }
    if (ev.event === "STATUS") {
      setNavigating(ev.navigating);
      setArrived(ev.arrived);
    }
  }, [qc]);
  useWebSocket(handleWsEvent, !isPreview);

  // Hydrate from backend status
  useEffect(() => {
    if (!navStatus) return;
    setNavigating(navStatus.navigating);
    setArrived(navStatus.arrival.arrived);
    if (navStatus.destination) {
      setGeocoded((prev) => {
        if (prev && prev.lat === navStatus.destination!.lat && prev.lon === navStatus.destination!.lon) return prev;
        return { lat: navStatus.destination!.lat, lon: navStatus.destination!.lon, display_name: navStatus.destination!.display_name };
      });
      if (typeof navStatus.destination.radius_ft === "number") setArrivalRadiusFt(navStatus.destination.radius_ft);
    }
  }, [navStatus]);

  // Browser geolocation
  useEffect(() => {
    if (isPreview || !navigator.geolocation) return;
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const coords: [number, number] = [pos.coords.latitude, pos.coords.longitude];
        setCurrentPos(coords);
        currentPosRef.current = coords;
      },
      (err) => console.warn("Geolocation error:", err.message),
      { enableHighAccuracy: true, maximumAge: 5000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, [isPreview]);

  // GPS POST interval
  useEffect(() => {
    if (!navigating || isPreview) return;
    const interval = setInterval(() => {
      const pos = currentPosRef.current;
      if (pos) post("/navigation/gps", { lat: pos[0], lon: pos[1] }).catch(() => {});
    }, GPS_POST_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [navigating, isPreview]);

  // Address detection search
  const addressSearchMutation = useMutation<DetectionSearchResponse, Error, { address: string }>({
    mutationFn: ({ address: addr }) => post<DetectionSearchResponse>("/navigation/detections/search", {
      address: addr,
      radius_m: Math.max(60, Math.round(arrivalRadiusFt * 0.3048 * 1.5)),
      limit: 100,
    }),
    onSuccess: (data) => {
      setAddressDetections(data.detections);
      if (data.total === 0) {
        setAddressNotice("No prior detections found near this address.");
        setShowDetectionsModal(false);
      } else {
        setAddressNotice(`Found ${data.total} prior detection${data.total !== 1 ? "s" : ""} near this address.`);
        setShowDetectionsModal(true);
        setSelectedDetection(data.detections[0] ?? null);
      }
    },
    onError: () => {
      setAddressNotice("Unable to search prior detections.");
      setShowDetectionsModal(false);
    },
  });

  // Geocode
  const geocodeMutation = useMutation<GeocodeResponse, Error, string>({
    mutationFn: (addr) => post<GeocodeResponse>("/navigation/geocode", { address: addr }),
    onSuccess: (data) => {
      setGeocoded(data);
      setRoute(null);
      setErrorMsg(null);
      setAddressNotice(null);
      setAddressDetections([]);
      setSelectedDetection(null);
      setShowDetectionsModal(false);
      if (!isPreview) addressSearchMutation.mutate({ address: data.display_name });
    },
    onError: (err) => setErrorMsg(`Geocode failed: ${err.message}`),
  });

  // Route
  const routeMutation = useMutation<RouteResponse, Error, void>({
    mutationFn: async () => {
      if (!currentPos || !geocoded) throw new Error("GPS or destination not set");
      return post<RouteResponse>("/navigation/route", {
        start_lat: currentPos[0], start_lon: currentPos[1],
        dest_lat: geocoded.lat, dest_lon: geocoded.lon,
      });
    },
    onSuccess: (data) => setRoute(data),
    onError: (err) => setErrorMsg(`Routing failed: ${err.message}`),
  });

  // Auto-fetch route
  useEffect(() => {
    if (!isPreview && geocoded && currentPos && !route) routeMutation.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geocoded, currentPos, isPreview]);

  // Start navigation
  const startMutation = useMutation<unknown, Error, void>({
    mutationFn: async () => {
      if (!geocoded) throw new Error("No destination geocoded");
      return post("/navigation/start", {
        dest_lat: geocoded.lat, dest_lon: geocoded.lon,
        display_name: geocoded.display_name, radius_ft: arrivalRadiusFt,
      });
    },
    onSuccess: () => { setNavigating(true); setArrived(false); setErrorMsg(null); },
    onError: (err) => setErrorMsg(`Start failed: ${err.message}`),
  });

  // Stop navigation
  const stopMutation = useMutation<unknown, Error, void>({
    mutationFn: () => post("/navigation/stop", {}),
    onSuccess: () => {
      setNavigating(false); setArrived(false); setRoute(null);
      setGeocoded(null); setAddress(""); setErrorMsg(null);
    },
    onError: (err) => setErrorMsg(`Stop failed: ${err.message}`),
  });

  const routePolyline: LatLngTuple[] | undefined = route?.polyline.map(([lat, lon]) => [lat, lon] as LatLngTuple);
  const canStart = geocoded !== null && !navigating && !arrived && !isPreview;
  const isLoading = geocodeMutation.isPending || routeMutation.isPending || startMutation.isPending || stopMutation.isPending || addressSearchMutation.isPending;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div style={S.layout}>
      {/* ── Left Sidebar ──────────────────────────────────────── */}
      <aside style={S.sidebar}>
        {/* Destination */}
        <section style={S.card}>
          <h3 style={S.cardTitle}>DESTINATION</h3>
          <input
            style={S.input}
            type="text"
            placeholder="Enter address or place name"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && address.trim() && !isPreview) geocodeMutation.mutate(address.trim());
            }}
            disabled={navigating || isLoading || isPreview}
          />
          <button
            style={{ ...S.actionBtn, ...S.btnBlue, opacity: (!address.trim() || navigating || isLoading) ? 0.5 : 1 }}
            onClick={() => address.trim() && !isPreview && geocodeMutation.mutate(address.trim())}
            disabled={!address.trim() || navigating || isLoading || isPreview}
          >
            {geocodeMutation.isPending ? "Searching…" : "Search"}
          </button>
          {geocoded && (
            <div style={S.geoResult}>
              <div style={S.geoName}>📍 {geocoded.display_name}</div>
              <div style={S.geoCoords}>{geocoded.lat.toFixed(5)}, {geocoded.lon.toFixed(5)}</div>
            </div>
          )}
          {addressNotice && <div style={S.notice}>{addressNotice}</div>}
        </section>

        {/* Investigation Search */}
        <section style={S.card}>
          <h3 style={S.cardTitle}>INVESTIGATION SEARCH</h3>
          <div style={S.searchGrid}>
            <input style={S.inputSm} placeholder="Plate" value={searchPlate} onChange={(e) => setSearchPlate(e.target.value)} />
            <input style={S.inputSm} placeholder="VIN" value={searchVin} onChange={(e) => setSearchVin(e.target.value)} />
            <input style={S.inputSm} placeholder="Make" value={searchMake} onChange={(e) => setSearchMake(e.target.value)} />
            <input style={S.inputSm} placeholder="Model" value={searchModel} onChange={(e) => setSearchModel(e.target.value)} />
          </div>
          <input style={S.input} placeholder="Address (optional)" />
          <div style={S.hintText}>Search historical detections by plate, VIN, make/model, and optional address radius.</div>
          <button
            style={{ ...S.actionBtn, ...S.btnBlue }}
            onClick={() => {
              if (!isPreview && searchPlate.trim()) {
                geocodeMutation.mutate(searchPlate.trim());
              }
            }}
          >
            Run Search
          </button>
        </section>

        {/* Arrival Trigger Distance */}
        <section style={S.card}>
          <h3 style={S.cardTitle}>ARRIVAL TRIGGER DISTANCE</h3>
          <input
            type="range"
            min={RADIUS_MIN_FT}
            max={RADIUS_MAX_FT}
            step={1}
            value={arrivalRadiusFt}
            onChange={(e) => setArrivalRadiusFt(Number(e.target.value))}
            disabled={navigating || isPreview}
            style={{ width: "100%", accentColor: "#3b82f6" }}
          />
          <div style={S.sliderValue}>Current: <strong>{arrivalRadiusFt} ft</strong></div>
          <div style={S.sliderHint}>Range: {RADIUS_MIN_FT} ft – {RADIUS_MAX_FT} ft (¼ mile)</div>
        </section>

        {/* Route info (when available) */}
        {route && (
          <section style={S.card}>
            <h3 style={S.cardTitle}>ROUTE</h3>
            <InfoRow label="Distance" value={formatDistance(route.distance_m)} />
            <InfoRow label="Duration" value={formatDuration(route.duration_s)} />
            <InfoRow label="ETA" value={formatEta(route.eta_iso)} />
          </section>
        )}

        {/* Status */}
        <section style={S.card}>
          <h3 style={S.cardTitle}>STATUS</h3>
          <div style={S.statusRow}>
            <span style={S.statusLabel}>GPS</span>
            <Badge active={!!currentPos} activeText="Locked" inactiveText="No Signal" />
          </div>
          <div style={S.statusRow}>
            <span style={S.statusLabel}>Navigation</span>
            <Badge active={navigating} activeText="Active" inactiveText="Idle" />
          </div>
          <div style={S.statusRow}>
            <span style={S.statusLabel}>LPR Pipeline</span>
            <Badge
              active={arrived || !navigating}
              activeText="ACTIVE"
              inactiveText="IDLE (en route)"
              activeColor="#22c55e"
              inactiveColor="#f59e0b"
            />
          </div>
        </section>

        {/* Navigation Button */}
        <section style={S.card}>
          {!navigating && !arrived ? (
            <button
              style={{ ...S.actionBtn, ...S.btnGreen, opacity: canStart ? 1 : 0.5 }}
              onClick={() => startMutation.mutate()}
              disabled={!canStart || isLoading}
            >
              {startMutation.isPending ? "Starting…" : "▶ Start Navigation"}
            </button>
          ) : (
            <button
              style={{ ...S.actionBtn, ...S.btnRed }}
              onClick={() => stopMutation.mutate()}
              disabled={isLoading || isPreview}
            >
              {stopMutation.isPending ? "Stopping…" : "■ Stop Navigation"}
            </button>
          )}
        </section>

        {/* Error */}
        {errorMsg && <div style={S.errorBox}>⚠ {errorMsg}</div>}

        {/* Recovery Log */}
        <section style={S.card}>
          <h3 style={S.cardTitle}>RECOVERY LOG</h3>
          <div style={S.recoveryInfo}>Records: <strong>0</strong></div>
          <div style={S.searchGrid}>
            <select
              style={S.inputSm}
              value={recoveryFilter}
              onChange={(e) => setRecoveryFilter(e.target.value)}
            >
              <option>all statuses</option>
              <option>recovered</option>
              <option>missed</option>
              <option>pending</option>
            </select>
            <input
              style={S.inputSm}
              placeholder="plate / VIN / make"
              value={recoverySearch}
              onChange={(e) => setRecoverySearch(e.target.value)}
            />
          </div>
        </section>

        {/* Target vehicles (after arrival) */}
        <TargetList scanning={arrived} previewTargets={isPreview ? PREVIEW_TARGETS : undefined} />
      </aside>

      {/* ── Right Content (Quad Cameras / Map) ────────────────── */}
      <div style={S.content}>
        {/* View toggle */}
        <div style={S.viewToggle}>
          <button
            style={{ ...S.toggleBtn, ...(viewMode === "cameras" ? S.toggleActive : {}) }}
            onClick={() => setViewMode("cameras")}
          >
            Quad Cameras
          </button>
          <button
            style={{ ...S.toggleBtn, ...(viewMode === "map" ? S.toggleActive : {}) }}
            onClick={() => setViewMode("map")}
          >
            Route Map
          </button>

          {/* Nav info overlay */}
          {navigating && route && (
            <div style={S.navInfoOverlay}>
              <span style={S.navInfoItem}>Mode <strong>Navigation</strong></span>
              <span style={S.navInfoItem}>Next Turn <strong>Pending</strong></span>
              <span style={S.navInfoItem}>Distance <strong>{formatDistance(route.distance_m)}</strong></span>
              <span style={S.navInfoItem}>Proximity <strong>{arrived ? "On Scene" : "En Route"}</strong></span>
            </div>
          )}
          {!navigating && !arrived && (
            <div style={S.navInfoOverlay}>
              <span style={S.navInfoItem}>Mode <strong>Quad Scan</strong></span>
              <span style={S.navInfoItem}>Next Turn <strong>Pending</strong></span>
              <span style={S.navInfoItem}>Distance <strong>--</strong></span>
              <span style={S.navInfoItem}>Proximity <strong>Standby</strong></span>
            </div>
          )}
        </div>

        {/* Quad Camera View */}
        {viewMode === "cameras" && (
          <div style={S.quadGrid}>
            {CAMERAS.map((cam) => (
              <div key={cam.id} style={S.camCell}>
                <span style={{
                  ...S.camBadge,
                  background: cam.status === "Online" ? "#06b6d4" : "#64748b",
                }}>
                  {cam.label}
                </span>
                <div style={S.camFeed}>
                  Live Feed: {cam.name}
                </div>
                <div style={S.camName}>{cam.name}</div>
              </div>
            ))}
          </div>
        )}

        {/* Map View */}
        {viewMode === "map" && (
          <div style={S.mapWrapper}>
            <MapContainer center={mapCenter} zoom={13} style={{ height: "100%", width: "100%" }}>
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              />
              {currentPos && <MapRecenter center={currentPos} />}
              {currentPos && <Marker position={currentPos} icon={blueIcon}><Popup>Current Location</Popup></Marker>}
              {geocoded && <Marker position={[geocoded.lat, geocoded.lon]} icon={redIcon}><Popup>{geocoded.display_name}</Popup></Marker>}
              {routePolyline && routePolyline.length > 0 && (
                <Polyline positions={routePolyline} color="#3b82f6" weight={4} opacity={0.8} />
              )}
            </MapContainer>
          </div>
        )}

        {/* Bottom status strip */}
        <div style={S.bottomStrip}>
          {viewMode === "cameras"
            ? "Cameras minimized · awaiting hit event"
            : navigating
              ? "Route active · monitoring approach"
              : "Map idle · select destination to begin"
          }
        </div>
      </div>

      {/* ── Detection History Modal ───────────────────────────── */}
      {showDetectionsModal && (
        <div style={S.modalBackdrop} onClick={() => setShowDetectionsModal(false)}>
          <div style={S.modalPanel} onClick={(e) => e.stopPropagation()}>
            <div style={S.modalHeader}>
              <h3 style={{ margin: 0, fontSize: "1rem" }}>Detection History at Address</h3>
              <button style={S.modalClose} onClick={() => setShowDetectionsModal(false)}>✕</button>
            </div>
            <div style={S.modalBody}>
              <div style={S.modalList}>
                {addressDetections.map((d) => (
                  <button
                    key={d.id}
                    style={{ ...S.modalItem, ...(selectedDetection?.id === d.id ? S.modalItemActive : {}) }}
                    onClick={() => setSelectedDetection(d)}
                  >
                    <div style={{ fontWeight: 700 }}>{d.plate_text ?? "No Plate"}</div>
                    <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{d.make ?? "Unknown"} {d.model ?? ""} · {d.camera_id}</div>
                  </button>
                ))}
              </div>
              <div style={S.modalDetail}>
                {selectedDetection ? (
                  <>
                    <InfoRow label="Plate" value={selectedDetection.plate_text ?? "N/A"} />
                    <InfoRow label="Vehicle" value={selectedDetection.vehicle_class ?? "Unknown"} />
                    <InfoRow label="Make / Model" value={`${selectedDetection.make ?? "Unknown"} ${selectedDetection.model ?? ""}`} />
                    <InfoRow label="Address" value={selectedDetection.detection_address ?? "Unknown"} />
                    <InfoRow label="Coords" value={`${selectedDetection.latitude?.toFixed?.(5) ?? "-"}, ${selectedDetection.longitude?.toFixed?.(5) ?? "-"}`} />
                    {selectedDetection.composite_path && (
                      <img src={selectedDetection.composite_path} alt="Detection" style={S.detectionImg} />
                    )}
                  </>
                ) : (
                  <p style={{ color: "#94a3b8" }}>Select a detection to view details.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={S.infoRow}>
      <span style={S.infoLabel}>{label}</span>
      <span style={S.infoValue}>{value}</span>
    </div>
  );
}

function Badge({
  active, activeText, inactiveText,
  activeColor = "#22c55e", inactiveColor = "#64748b",
}: {
  active: boolean; activeText: string; inactiveText: string;
  activeColor?: string; inactiveColor?: string;
}) {
  return (
    <span style={{ ...S.badge, background: active ? activeColor : inactiveColor }}>
      {active ? activeText : inactiveText}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const S: Record<string, CSSProperties> = {
  layout: {
    display: "flex",
    height: "100%",
    overflow: "hidden",
  },

  // Sidebar
  sidebar: {
    width: "280px",
    minWidth: "260px",
    background: "#0c1220",
    borderRight: "1px solid #1e293b",
    padding: "0.75rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.6rem",
    overflowY: "auto",
    flexShrink: 0,
  },
  card: {
    background: "#111827",
    border: "1px solid #1e293b",
    borderRadius: "10px",
    padding: "0.75rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem",
  },
  cardTitle: {
    fontSize: "0.7rem",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "#64748b",
    margin: 0,
  },
  input: {
    background: "#1a2332",
    border: "1px solid #334155",
    borderRadius: "8px",
    color: "#e8edf5",
    padding: "10px 12px",
    fontSize: "0.875rem",
    outline: "none",
    width: "100%",
    minHeight: "42px",
  },
  inputSm: {
    background: "#1a2332",
    border: "1px solid #334155",
    borderRadius: "8px",
    color: "#e8edf5",
    padding: "8px 10px",
    fontSize: "0.82rem",
    outline: "none",
    width: "100%",
    minHeight: "38px",
  },
  searchGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "0.4rem",
  },
  hintText: {
    fontSize: "0.72rem",
    color: "#475569",
    lineHeight: 1.4,
  },
  actionBtn: {
    width: "100%",
    padding: "12px",
    borderRadius: "8px",
    fontWeight: 700,
    fontSize: "0.875rem",
    border: "none",
    minHeight: "48px",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    transition: "opacity 0.15s",
  },
  btnBlue: {
    background: "linear-gradient(180deg, #2563eb, #1d4ed8)",
    color: "#fff",
  },
  btnGreen: {
    background: "linear-gradient(180deg, #16a34a, #15803d)",
    color: "#fff",
  },
  btnRed: {
    background: "linear-gradient(180deg, #dc2626, #b91c1c)",
    color: "#fff",
  },
  geoResult: {
    padding: "0.5rem",
    background: "#1a2332",
    borderRadius: "6px",
  },
  geoName: {
    fontSize: "0.8rem",
    color: "#cbd5e1",
    wordBreak: "break-word",
  },
  geoCoords: {
    fontSize: "0.7rem",
    color: "#64748b",
    marginTop: "2px",
  },
  notice: {
    fontSize: "0.78rem",
    color: "#93c5fd",
  },
  sliderValue: {
    fontSize: "0.875rem",
    color: "#e8edf5",
    textAlign: "center",
  },
  sliderHint: {
    fontSize: "0.68rem",
    color: "#475569",
    textAlign: "center",
  },
  infoRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  infoLabel: {
    fontSize: "0.8rem",
    color: "#94a3b8",
  },
  infoValue: {
    fontSize: "0.875rem",
    fontWeight: 600,
    color: "#e8edf5",
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
    fontSize: "0.68rem",
    fontWeight: 700,
    padding: "3px 10px",
    borderRadius: "999px",
    color: "#fff",
    letterSpacing: "0.04em",
  },
  errorBox: {
    background: "#450a0a",
    border: "1px solid #ef4444",
    borderRadius: "8px",
    color: "#fca5a5",
    fontSize: "0.82rem",
    padding: "10px 12px",
  },
  recoveryInfo: {
    fontSize: "0.82rem",
    color: "#94a3b8",
  },

  // Content area
  content: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
    position: "relative",
  },
  viewToggle: {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    padding: "6px 10px",
    background: "#0c1220",
    borderBottom: "1px solid #1e293b",
    flexShrink: 0,
  },
  toggleBtn: {
    padding: "6px 14px",
    borderRadius: "6px",
    fontSize: "0.78rem",
    fontWeight: 600,
    color: "#94a3b8",
    background: "transparent",
    border: "1px solid transparent",
    minHeight: "32px",
  },
  toggleActive: {
    color: "#e8edf5",
    background: "rgba(37, 99, 235, 0.15)",
    border: "1px solid #2563eb",
  },
  navInfoOverlay: {
    marginLeft: "auto",
    display: "flex",
    gap: "16px",
    fontSize: "0.75rem",
    color: "#94a3b8",
  },
  navInfoItem: {
    display: "flex",
    gap: "6px",
  },

  // Quad cameras
  quadGrid: {
    flex: 1,
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gridTemplateRows: "1fr 1fr",
    gap: "4px",
    padding: "4px",
    background: "#080c14",
    overflow: "hidden",
  },
  camCell: {
    position: "relative",
    borderRadius: "8px",
    overflow: "hidden",
    border: "1px solid #1e293b",
    display: "flex",
    flexDirection: "column",
  },
  camBadge: {
    position: "absolute",
    top: "8px",
    left: "8px",
    fontSize: "0.7rem",
    fontWeight: 800,
    padding: "3px 8px",
    borderRadius: "6px",
    color: "#fff",
    zIndex: 2,
    letterSpacing: "0.05em",
  },
  camFeed: {
    flex: 1,
    display: "grid",
    placeItems: "center",
    background: "linear-gradient(145deg, #111827, #1e293b)",
    color: "#475569",
    fontWeight: 600,
    fontSize: "0.9rem",
  },
  camName: {
    padding: "8px 12px",
    fontSize: "0.82rem",
    fontWeight: 600,
    color: "#cbd5e1",
    background: "#111827",
    borderTop: "1px solid #1e293b",
  },

  // Map
  mapWrapper: {
    flex: 1,
    position: "relative",
    overflow: "hidden",
  },

  // Bottom strip
  bottomStrip: {
    padding: "8px 16px",
    fontSize: "0.78rem",
    color: "#475569",
    background: "#0c1220",
    borderTop: "1px solid #1e293b",
    textAlign: "center",
    fontStyle: "italic",
    flexShrink: 0,
  },

  // Modal
  modalBackdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(2,6,23,0.75)",
    display: "grid",
    placeItems: "center",
    zIndex: 120,
  },
  modalPanel: {
    width: "min(960px, 95vw)",
    background: "#0c1220",
    border: "1px solid #334155",
    borderRadius: "14px",
    padding: "1rem",
  },
  modalHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "0.75rem",
  },
  modalClose: {
    border: "1px solid #334155",
    borderRadius: "6px",
    background: "#111827",
    color: "#e8edf5",
    padding: "4px 10px",
    cursor: "pointer",
  },
  modalBody: {
    display: "grid",
    gridTemplateColumns: "260px 1fr",
    gap: "0.8rem",
  },
  modalList: {
    display: "flex",
    flexDirection: "column",
    gap: "0.4rem",
    maxHeight: "400px",
    overflowY: "auto",
  },
  modalItem: {
    textAlign: "left",
    padding: "0.5rem",
    borderRadius: "8px",
    border: "1px solid #1e293b",
    background: "#111827",
    color: "#e8edf5",
    cursor: "pointer",
  },
  modalItemActive: {
    border: "1px solid #3b82f6",
    background: "rgba(30,58,138,0.35)",
  },
  modalDetail: {
    border: "1px solid #1e293b",
    borderRadius: "8px",
    padding: "0.75rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.4rem",
  },
  detectionImg: {
    width: "100%",
    borderRadius: "8px",
    border: "1px solid #1e293b",
    objectFit: "cover",
    maxHeight: "180px",
    marginTop: "0.5rem",
  },
};
