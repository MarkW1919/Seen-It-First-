import { useState, useEffect, useRef, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapContainer, TileLayer, Marker, Polyline, Popup, useMap } from "react-leaflet";
import { icon, LatLngTuple } from "leaflet";
import { useWebSocket } from "../hooks/useWebSocket";
import { TargetList } from "../components/TargetList";
import { PREVIEW_ALERTS, type PreviewAlert } from "../mock/previewAlerts";
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
const RADIUS_MAX_FT = 1320;   // ¼ mile
const RADIUS_DEFAULT_FT = 300;
const GPS_POST_INTERVAL_MS = 2000;

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


type PreviewMode = "base" | "route" | "arrived";

const PREVIEW_ROUTE: RouteResponse = {
  distance_m: 4820,
  duration_s: 660,
  eta_iso: "2026-01-01T14:35:00.000Z",
  polyline: [
    [37.4232, -122.0866],
    [37.4225, -122.0848],
    [37.4214, -122.0831],
    [37.4199, -122.0817],
    [37.4182, -122.0802],
  ],
};

const PREVIEW_TARGETS: RankedVehicle[] = [
  {
    vehicle_id: "veh-top-001",
    vehicle_type: "suv",
    make: "ford",
    model: "explorer",
    color: "black",
    year_range: "2018-2021",
    plate: "8ABC123",
    confidence: 0.92,
    distance_ft: 128,
    hotlist_match: true,
    score: 98.4,
    latitude: 37.4221,
    longitude: -122.0841,
    timestamp: Date.now(),
    camera_id: "cam-front-1",
    fingerprint: "d9f30eab82aa4a45bb4f451f9f0f1307",
  },
  {
    vehicle_id: "veh-002",
    vehicle_type: "sedan",
    make: "toyota",
    model: "camry",
    color: "silver",
    year_range: "2017-2019",
    plate: null,
    confidence: 0.81,
    distance_ft: 206,
    hotlist_match: false,
    score: 76.1,
    latitude: 37.4216,
    longitude: -122.0834,
    timestamp: Date.now(),
    camera_id: "cam-side-2",
    fingerprint: "8217bc923f7442be8d3247f5cbafe0cc",
  },
];

function getPreviewMode(): PreviewMode | null {
  if (typeof window === "undefined") return null;
  const mode = new URLSearchParams(window.location.search).get("preview");
  if (mode === "base" || mode === "route" || mode === "arrived") return mode;
  return null;
}


function getPreviewAlertId(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("alert");
}

function buildPreviewRoute(start: [number, number], dest: [number, number]): RouteResponse {
  const points = 5;
  const polyline: [number, number][] = Array.from({ length: points }, (_, i) => {
    const t = i / (points - 1);
    return [
      start[0] + (dest[0] - start[0]) * t,
      start[1] + (dest[1] - start[1]) * t,
    ];
  });

  return {
    polyline,
    distance_m: 3100,
    duration_s: 520,
    eta_iso: "2026-01-01T14:22:00.000Z",
  };
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function NavigationPage() {
  const qc = useQueryClient();
  const previewMode = getPreviewMode();
  const previewAlertId = getPreviewAlertId();
  const selectedPreviewAlert = PREVIEW_ALERTS.find((a) => a.id === previewAlertId) ?? null;
  const isPreview = previewMode !== null;

  // Address input state
  const [address, setAddress] = useState("");
  const [geocoded, setGeocoded] = useState<GeocodeResponse | null>(null);
  const [route, setRoute] = useState<RouteResponse | null>(null);

  // Arrival radius (feet) — displayed and sent to backend on start
  const [arrivalRadiusFt, setArrivalRadiusFt] = useState(RADIUS_DEFAULT_FT);

  // GPS from browser — map display uses state; GPS posts use a ref to avoid
  // restarting the posting interval every time the position changes
  const [currentPos, setCurrentPos] = useState<[number, number] | null>(
    isPreview ? [37.4220, -122.0841] : null,
  );
  const currentPosRef = useRef<[number, number] | null>(null);

  // Navigation session state
  const [navigating, setNavigating] = useState(false);
  const [arrived, setArrived] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [selectedAlert, setSelectedAlert] = useState<PreviewAlert | null>(null);
  const [addressDetections, setAddressDetections] = useState<DetectionRecord[]>([]);
  const [selectedDetection, setSelectedDetection] = useState<DetectionRecord | null>(null);
  const [showDetectionsModal, setShowDetectionsModal] = useState(false);
  const [addressNotice, setAddressNotice] = useState<string | null>(null);


  useEffect(() => {
    if (!previewMode) return;

    if (selectedPreviewAlert) {
      setSelectedAlert(selectedPreviewAlert);
      setAddress(`${selectedPreviewAlert.latitude.toFixed(5)}, ${selectedPreviewAlert.longitude.toFixed(5)}`);
      setGeocoded({
        lat: selectedPreviewAlert.latitude,
        lon: selectedPreviewAlert.longitude,
        display_name: `${selectedPreviewAlert.camera} alert location`,
      });
      setRoute(buildPreviewRoute([37.4220, -122.0841], [selectedPreviewAlert.latitude, selectedPreviewAlert.longitude]));
      setNavigating(true);
      setArrived(false);
      return;
    }

    setSelectedAlert(null);
    setAddress("1600 Amphitheatre Parkway, Mountain View, CA");
    setGeocoded({
      lat: 37.4182,
      lon: -122.0802,
      display_name: "Google Building 41, Amphitheatre Pkwy, Mountain View",
    });

    if (previewMode === "base") {
      setRoute(null);
      setNavigating(false);
      setArrived(false);
      return;
    }

    setRoute(PREVIEW_ROUTE);

    if (previewMode === "route") {
      setNavigating(true);
      setArrived(false);
      return;
    }

    setNavigating(false);
    setArrived(true);
  }, [previewMode, selectedPreviewAlert]);

  // Default map centre (continental US) — overridden by GPS
  const DEFAULT_CENTER: LatLngTuple = [39.5, -98.35];
  const mapCenter: LatLngTuple = currentPos ?? DEFAULT_CENTER;

  // ------------------------------------------------------------------
  // Navigation status polling (only while navigating)
  // ------------------------------------------------------------------
  const { data: navStatus } = useQuery<NavStatus>({
    queryKey: ["nav-status"],
    queryFn: async () => {
      const res = await fetch("/navigation/status");
      if (!res.ok) throw new Error(`Failed to fetch navigation status (${res.status})`);
      return res.json() as Promise<NavStatus>;
    },
    refetchInterval: navigating ? 5000 : false,
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<NavStatus>;
    },
    refetchInterval: navigating ? 5000 : false,
    enabled: !isPreview && navigating,
  });

  // ------------------------------------------------------------------
  // WebSocket — receive ARRIVED event
  // ------------------------------------------------------------------
  const handleWsEvent = useCallback((ev: WsEvent) => {
    if (ev.event === "ARRIVED") {
      setArrived(true);
      setNavigating(false);
      qc.invalidateQueries({ queryKey: ["nav-status"] });
      return;
    }

    if (ev.event === "STATUS") {
      setNavigating(ev.navigating);
      setArrived(ev.arrived);
    }
  }, [qc]);

  useWebSocket(handleWsEvent, !isPreview);

  // ------------------------------------------------------------------
  // Hydrate local UI state from backend status snapshots.
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!navStatus) return;
    setNavigating(navStatus.navigating);
    setArrived(navStatus.arrival.arrived);

    const destination = navStatus.destination;
    if (destination) {
      setGeocoded((prev) => {
        if (prev && prev.lat === destination.lat && prev.lon === destination.lon) {
          return prev;
        }
        return {
          lat: destination.lat,
          lon: destination.lon,
          display_name: destination.display_name,
        };
      });
      setArrivalRadiusFt(
        typeof destination.radius_ft === "number" ? destination.radius_ft : RADIUS_DEFAULT_FT,
      );
    }
  }, [navStatus]);

  // ------------------------------------------------------------------
  // Browser Geolocation — watchPosition updates the map marker only.
  // GPS position is also stored in a ref for the posting interval below.
  // ------------------------------------------------------------------
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

  // ------------------------------------------------------------------
  // GPS POST interval — sends position to backend every 2s.
  // Only runs while navigating; cleared automatically when navigating
  // becomes false (navigation stopped or ARRIVED received).
  // ------------------------------------------------------------------
  useEffect(() => {
    if (isPreview || (!navigating && !arrived)) return;

    const interval = setInterval(() => {
      const pos = currentPosRef.current;
      if (pos) {
        post("/navigation/gps", { lat: pos[0], lon: pos[1] }).catch(() => {/* ignore */});
      }
    }, GPS_POST_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [navigating, arrived, isPreview]);

  // ------------------------------------------------------------------
  // Search detections near selected address
  // ------------------------------------------------------------------
  const addressSearchMutation = useMutation<DetectionSearchResponse, Error, { address: string }>({
    mutationFn: ({ address }) => post<DetectionSearchResponse>("/navigation/detections/search", {
      address,
      radius_m: Math.max(60, Math.round(arrivalRadiusFt * 0.3048 * 1.5)),
      limit: 100,
    }),
    onSuccess: (data) => {
      setAddressDetections(data.detections);
      if (data.total === 0) {
        setAddressNotice("No prior detections found near this address.");
        setShowDetectionsModal(false);
        setSelectedDetection(null);
      } else {
        setAddressNotice(`Found ${data.total} prior detection${data.total !== 1 ? "s" : ""} near this address.`);
        setShowDetectionsModal(true);
        setSelectedDetection(data.detections[0] ?? null);
      }
    },
    onError: () => {
      setAddressNotice("Unable to search prior detections for this address.");
      setShowDetectionsModal(false);
    },
  });

  // ------------------------------------------------------------------
  // Geocode mutation
  // ------------------------------------------------------------------
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
      if (!isPreview) {
        addressSearchMutation.mutate({ address: data.display_name });
      }
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
    if (!isPreview && geocoded && currentPos && !route) {
      routeMutation.mutate();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geocoded, currentPos, isPreview]);

  // ------------------------------------------------------------------
  // Start navigation mutation — includes arrivalRadiusFt
  // ------------------------------------------------------------------
  const startMutation = useMutation<unknown, Error, void>({
    mutationFn: async () => {
      if (!geocoded) throw new Error("No destination geocoded");
      return post("/navigation/start", {
        dest_lat: geocoded.lat,
        dest_lon: geocoded.lon,
        display_name: geocoded.display_name,
        radius_ft: arrivalRadiusFt,
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

  const canStart = geocoded !== null && !navigating && !arrived && !isPreview;
  const isLoading =
    geocodeMutation.isPending ||
    routeMutation.isPending ||
    startMutation.isPending ||
    stopMutation.isPending ||
    addressSearchMutation.isPending;

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

      {isPreview && (
        <div style={styles.previewBanner}>
          Preview mode: use <code>?preview=base</code>, <code>?preview=route</code>, or <code>?preview=arrived</code> in the URL.
        </div>
      )}


      {showDetectionsModal && (
        <div style={styles.modalBackdrop} onClick={() => setShowDetectionsModal(false)}>
          <div style={styles.modalPanel} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeaderRow}>
              <h3 style={{ margin: 0 }}>Detection History at Address</h3>
              <button style={styles.modalCloseBtn} onClick={() => setShowDetectionsModal(false)}>✕</button>
            </div>
            <div style={styles.modalBodyGrid}>
              <div style={styles.modalList}>
                {addressDetections.map((d) => (
                  <button
                    key={d.id}
                    style={{ ...styles.modalListItem, ...(selectedDetection?.id === d.id ? styles.modalListItemActive : {}) }}
                    onClick={() => setSelectedDetection(d)}
                  >
                    <div style={{ fontWeight: 700 }}>{d.plate_text ?? "No Plate"}</div>
                    <div style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{d.make ?? "Unknown"} {d.model ?? ""} · {d.camera_id}</div>
                  </button>
                ))}
              </div>
              <div style={styles.modalDetail}>
                {selectedDetection ? (
                  <>
                    <div style={styles.routeRow}><span style={styles.routeLabel}>Plate</span><span style={styles.routeValue}>{selectedDetection.plate_text ?? "N/A"}</span></div>
                    <div style={styles.routeRow}><span style={styles.routeLabel}>Vehicle</span><span style={styles.routeValue}>{selectedDetection.vehicle_class ?? "Unknown"}</span></div>
                    <div style={styles.routeRow}><span style={styles.routeLabel}>Make / Model</span><span style={styles.routeValue}>{selectedDetection.make ?? "Unknown"} {selectedDetection.model ?? ""}</span></div>
                    <div style={styles.routeRow}><span style={styles.routeLabel}>Address</span><span style={styles.routeValue}>{selectedDetection.detection_address ?? "Unknown"}</span></div>
                    <div style={styles.routeRow}><span style={styles.routeLabel}>Coords</span><span style={styles.routeValue}>{selectedDetection.latitude?.toFixed?.(5) ?? "-"}, {selectedDetection.longitude?.toFixed?.(5) ?? "-"}</span></div>
                    {selectedDetection.composite_path && (
                      <img src={selectedDetection.composite_path} alt="Detection composite" style={styles.alertPhoto} />
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
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && address.trim() && !isPreview) {
                  geocodeMutation.mutate(address.trim());
                }
              }}
              disabled={navigating || isLoading || isPreview}
            />
            <div style={{ color: "#94a3b8", fontSize: "0.75rem", marginTop: "0.5rem", marginBottom: "0.5rem" }}>
              Enter address or place name, then press Enter or Search.
            </div>
            <button
              style={{ ...styles.btn, ...styles.btnSecondary }}
              onClick={() => address.trim() && !isPreview && geocodeMutation.mutate(address.trim())}
              disabled={!address.trim() || navigating || isLoading || isPreview}
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
            {addressNotice && (
              <div style={styles.addressNotice}>{addressNotice}</div>
            )}
          </section>

          {/* Arrival radius slider */}
          <section style={styles.card}>
            <h2 style={styles.cardTitle}>Arrival Trigger Distance</h2>
            <input
              type="range"
              min={RADIUS_MIN_FT}
              max={RADIUS_MAX_FT}
              step={1}
              value={arrivalRadiusFt}
              onChange={(e) => setArrivalRadiusFt(Number(e.target.value))}
              disabled={navigating || isPreview}
              style={styles.slider}
            />
            <div style={styles.sliderValue}>
              Current: <strong>{arrivalRadiusFt} ft</strong>
            </div>
            <div style={styles.sliderHint}>
              Range: {RADIUS_MIN_FT} ft – {RADIUS_MAX_FT} ft (¼ mile)
            </div>
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
                disabled={isLoading || isPreview}
              >
                {stopMutation.isPending ? "Stopping…" : "■ Stop Navigation"}
              </button>
            )}
          </section>

          {/* Error display */}
          {errorMsg && (
            <div style={styles.errorBox}>⚠ {errorMsg}</div>
          )}

          {selectedAlert && (
            <section style={styles.card}>
              <h2 style={styles.cardTitle}>Selected LPR Alert</h2>
              <img src={selectedAlert.photoUrl} alt={`Scan of ${selectedAlert.plate}`} style={styles.alertPhoto} />
              <div style={styles.routeRow}><span style={styles.routeLabel}>Plate</span><span style={styles.routeValue}>{selectedAlert.plate}</span></div>
              <div style={styles.routeRow}><span style={styles.routeLabel}>Vehicle</span><span style={styles.routeValue}>{selectedAlert.vehicle}</span></div>
              <div style={styles.routeRow}><span style={styles.routeLabel}>Make / Model</span><span style={styles.routeValue}>{selectedAlert.make} {selectedAlert.model}</span></div>
              <div style={styles.routeRow}><span style={styles.routeLabel}>Color / Year</span><span style={styles.routeValue}>{selectedAlert.color} / {selectedAlert.yearRange}</span></div>
              <div style={styles.routeRow}><span style={styles.routeLabel}>Camera</span><span style={styles.routeValue}>{selectedAlert.camera}</span></div>
              <div style={styles.routeRow}><span style={styles.routeLabel}>Time</span><span style={styles.routeValue}>{selectedAlert.ts}</span></div>
              <div style={styles.routeRow}><span style={styles.routeLabel}>Coordinates</span><span style={styles.routeValue}>{selectedAlert.latitude.toFixed(5)}, {selectedAlert.longitude.toFixed(5)}</span></div>
              <div style={styles.routeRow}><span style={styles.routeLabel}>Confidence</span><span style={styles.routeValue}>{(selectedAlert.confidence * 100).toFixed(0)}%</span></div>
            </section>
          )}

          {/* Vehicle detection cards — visible after ARRIVED */}
          <TargetList scanning={arrived} previewTargets={isPreview ? PREVIEW_TARGETS : undefined} />
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
  previewBanner: {
    margin: "0.5rem 1rem 0",
    padding: "0.65rem 0.9rem",
    borderRadius: "10px",
    border: "1px solid #0ea5e9",
    background: "rgba(14, 165, 233, 0.12)",
    color: "#7dd3fc",
    fontSize: "0.85rem",
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
  slider: {
    width: "100%",
    accentColor: "#3b82f6",
    cursor: "pointer",
  },
  sliderValue: {
    fontSize: "0.875rem",
    color: "#e2e8f0",
    textAlign: "center" as const,
  },
  sliderHint: {
    fontSize: "0.7rem",
    color: "#475569",
    textAlign: "center" as const,
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
  addressNotice: {
    marginTop: "0.3rem",
    fontSize: "0.78rem",
    color: "#93c5fd",
  },
  alertPhoto: {
    width: "100%",
    borderRadius: "8px",
    border: "1px solid #334155",
    objectFit: "cover" as const,
    maxHeight: "160px",
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
  modalBackdrop: {
    position: "fixed" as const,
    inset: 0,
    background: "rgba(2,6,23,0.65)",
    display: "grid",
    placeItems: "center",
    zIndex: 120,
  },
  modalPanel: {
    width: "min(980px, 95vw)",
    background: "#0b1220",
    border: "1px solid #334155",
    borderRadius: "12px",
    padding: "0.9rem",
  },
  modalHeaderRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "0.6rem",
  },
  modalCloseBtn: {
    border: "1px solid #334155",
    borderRadius: "6px",
    background: "#111827",
    color: "#e2e8f0",
    cursor: "pointer",
  },
  modalBodyGrid: {
    display: "grid",
    gridTemplateColumns: "260px 1fr",
    gap: "0.8rem",
  },
  modalList: {
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.5rem",
    maxHeight: "420px",
    overflowY: "auto" as const,
  },
  modalListItem: {
    textAlign: "left" as const,
    padding: "0.55rem",
    borderRadius: "8px",
    border: "1px solid #334155",
    background: "#111827",
    color: "#e2e8f0",
    cursor: "pointer",
  },
  modalListItemActive: {
    border: "1px solid #3b82f6",
    background: "rgba(30,58,138,0.35)",
  },
  modalDetail: {
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "0.7rem",
    display: "flex",
    flexDirection: "column" as const,
    gap: "0.45rem",
  },
} as const;
