import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import { icon, type LatLngTuple } from "leaflet";
import { useWebSocket } from "../hooks/useWebSocket";
import { TargetList } from "../components/TargetList";
import type {
  DetectionRecord,
  DetectionSearchResponse,
  GeocodeResponse,
  NavStatus,
  OperatorProfile,
  RankedVehicle,
  RouteResponse,
  RuntimeStatusResponse,
  WsEvent,
} from "../types/navigation";

const RADIUS_MIN_FT = 1;
const RADIUS_MAX_FT = 1320;
const RADIUS_DEFAULT_FT = 300;
const GPS_POST_INTERVAL_MS = 2000;
const STATUS_REFRESH_MS = 5000;

const PREVIEW_CAMERAS = [
  { camera_id: "cam-front-left", name: "Front Left", status: "Online", fps: 29.8, queue_depth: 1, last_frame_age_s: 0.1 },
  { camera_id: "cam-front-right", name: "Front Right", status: "Online", fps: 30.1, queue_depth: 1, last_frame_age_s: 0.1 },
  { camera_id: "cam-rear-left", name: "Rear Left", status: "Online", fps: 27.2, queue_depth: 2, last_frame_age_s: 0.2 },
  { camera_id: "cam-rear-right", name: "Rear Right", status: "Offline", fps: 0.0, queue_depth: 0, last_frame_age_s: null },
] as const;

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
    camera_id: "cam-front-left",
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
    camera_id: "cam-front-right",
    fingerprint: "8217bc923f7442be8d3247f5cbafe0cc",
  },
];

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

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: object): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((detail as { detail?: string }).detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

function formatDistance(m: number): string {
  if (m >= 1000) return `${(m / 1000).toFixed(1)} km`;
  return `${Math.round(m)} m`;
}

function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

function formatEta(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

function cameraBadge(name: string): string {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
  return initials || "CAM";
}

function getPreviewMode(): "base" | "route" | "arrived" | null {
  if (typeof window === "undefined") return null;
  const mode = new URLSearchParams(window.location.search).get("preview");
  if (mode === "base" || mode === "route" || mode === "arrived") return mode;
  return null;
}

function MapRecenter({ center }: { center: LatLngTuple }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, map.getZoom());
  }, [center, map]);
  return null;
}

interface Props {
  onStateChange: (state: {
    arrived?: boolean;
    gpsLocked?: boolean;
    navigating?: boolean;
    camOnline?: number;
  }) => void;
}

export default function NavigationHUD({ onStateChange }: Props) {
  const queryClient = useQueryClient();
  const previewMode = getPreviewMode();
  const isPreview = previewMode !== null;

  const [viewMode, setViewMode] = useState<"cameras" | "map">("cameras");
  const [address, setAddress] = useState("");
  const [geocoded, setGeocoded] = useState<GeocodeResponse | null>(null);
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [arrivalRadiusFt, setArrivalRadiusFt] = useState(RADIUS_DEFAULT_FT);
  const [currentPos, setCurrentPos] = useState<[number, number] | null>(isPreview ? [37.422, -122.0841] : null);
  const currentPosRef = useRef<[number, number] | null>(currentPos);
  const arrivalRadiusHydratedRef = useRef(false);
  const [navigating, setNavigating] = useState(false);
  const [arrived, setArrived] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [addressDetections, setAddressDetections] = useState<DetectionRecord[]>([]);
  const [selectedDetection, setSelectedDetection] = useState<DetectionRecord | null>(null);
  const [showDetectionsModal, setShowDetectionsModal] = useState(false);
  const [addressNotice, setAddressNotice] = useState<string | null>(null);

  const runtimeQuery = useQuery<RuntimeStatusResponse>({
    queryKey: ["runtime-status"],
    queryFn: () => fetchJson<RuntimeStatusResponse>("/navigation/runtime"),
    enabled: !isPreview,
    refetchInterval: STATUS_REFRESH_MS,
  });

  const navStatusQuery = useQuery<NavStatus>({
    queryKey: ["nav-status"],
    queryFn: () => fetchJson<NavStatus>("/navigation/status"),
    enabled: !isPreview,
    refetchInterval: STATUS_REFRESH_MS,
  });

  const profileQuery = useQuery<OperatorProfile>({
    queryKey: ["operator-profile"],
    queryFn: () => fetchJson<OperatorProfile>("/navigation/operator-profile"),
    enabled: !isPreview,
    staleTime: 30000,
  });

  const handleWsEvent = useCallback((event: WsEvent) => {
    if (event.event === "ARRIVED") {
      setArrived(true);
      setNavigating(false);
      queryClient.invalidateQueries({ queryKey: ["nav-status"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-status"] });
      return;
    }

    if (event.event === "STATUS") {
      setNavigating(event.navigating);
      setArrived(event.arrived);
    }
  }, [queryClient]);
  useWebSocket(handleWsEvent, !isPreview);

  useEffect(() => {
    if (!previewMode) return;

    setAddress("1600 Amphitheatre Parkway, Mountain View, CA");
    setGeocoded({
      lat: 37.4182,
      lon: -122.0802,
      display_name: "Google Building 41, Amphitheatre Pkwy",
    });

    if (previewMode === "route") {
      setRoute({
        polyline: [
          [37.4232, -122.0866],
          [37.4225, -122.0848],
          [37.4214, -122.0831],
          [37.4199, -122.0817],
          [37.4182, -122.0802],
        ],
        distance_m: 4820,
        duration_s: 660,
        eta_iso: "2026-01-01T14:35:00.000Z",
      });
      setNavigating(true);
      setArrived(false);
    }

    if (previewMode === "arrived") {
      setNavigating(false);
      setArrived(true);
    }
  }, [previewMode]);

  useEffect(() => {
    if (profileQuery.data && !arrivalRadiusHydratedRef.current) {
      setArrivalRadiusFt(profileQuery.data.arrival_distance_ft);
      arrivalRadiusHydratedRef.current = true;
    }
  }, [profileQuery.data]);

  useEffect(() => {
    const runtimeGps = runtimeQuery.data?.operator_gps;
    if (!runtimeGps) return;
    const coords: [number, number] = [runtimeGps.lat, runtimeGps.lon];
    setCurrentPos(coords);
    currentPosRef.current = coords;
  }, [runtimeQuery.data?.operator_gps]);

  useEffect(() => {
    const navStatus = navStatusQuery.data;
    if (!navStatus) return;

    setNavigating(navStatus.navigating);
    setArrived(navStatus.arrival.arrived);

    if (navStatus.destination) {
      setGeocoded({
        lat: navStatus.destination.lat,
        lon: navStatus.destination.lon,
        display_name: navStatus.destination.display_name,
      });
      setAddress(navStatus.destination.display_name);
      if (typeof navStatus.destination.radius_ft === "number") {
        setArrivalRadiusFt(navStatus.destination.radius_ft);
      }
    }

    if (navStatus.current_route) {
      setRoute(navStatus.current_route);
    }

    if (navStatus.current_pos) {
      const coords: [number, number] = [navStatus.current_pos.lat, navStatus.current_pos.lon];
      setCurrentPos(coords);
      currentPosRef.current = coords;
    }
  }, [navStatusQuery.data]);

  useEffect(() => {
    if (navigating && !arrived) setViewMode("map");
    if (arrived) setViewMode("cameras");
  }, [navigating, arrived]);

  useEffect(() => {
    if (isPreview || !navigator.geolocation) return;
    const watcher = navigator.geolocation.watchPosition(
      (position) => {
        const coords: [number, number] = [position.coords.latitude, position.coords.longitude];
        setCurrentPos(coords);
        currentPosRef.current = coords;
      },
      (error) => {
        console.warn("Geolocation error:", error.message);
      },
      { enableHighAccuracy: true, maximumAge: 5000 },
    );

    return () => navigator.geolocation.clearWatch(watcher);
  }, [isPreview]);

  useEffect(() => {
    if (!navigating || isPreview) return;

    const interval = setInterval(() => {
      const coords = currentPosRef.current;
      if (!coords) return;
      post("/navigation/gps", { lat: coords[0], lon: coords[1] }).catch(() => {
        // Keep the HUD running even if a single GPS post fails.
      });
    }, GPS_POST_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [navigating, isPreview]);

  const addressSearchMutation = useMutation<DetectionSearchResponse, Error, { address: string }>({
    mutationFn: ({ address: searchAddress }) => post<DetectionSearchResponse>("/navigation/detections/search", {
      address: searchAddress,
      radius_m: Math.max(60, Math.round(arrivalRadiusFt * 0.3048 * 1.5)),
      limit: 100,
    }),
    onSuccess: (data) => {
      setAddressDetections(data.detections);
      if (data.total === 0) {
        setAddressNotice("No prior detections found near this destination.");
        setShowDetectionsModal(false);
        setSelectedDetection(null);
      } else {
        setAddressNotice(`Found ${data.total} prior detection${data.total === 1 ? "" : "s"} near this destination.`);
        setSelectedDetection(data.detections[0] ?? null);
      }
    },
    onError: (error) => {
      setAddressNotice(`Unable to search prior detections: ${error.message}`);
      setShowDetectionsModal(false);
      setSelectedDetection(null);
    },
  });

  const geocodeMutation = useMutation<GeocodeResponse, Error, string>({
    mutationFn: (query) => post<GeocodeResponse>("/navigation/geocode", { address: query }),
    onSuccess: (data) => {
      setGeocoded(data);
      setAddress(data.display_name);
      setRoute(null);
      setErrorMsg(null);
      setAddressNotice("Checking nearby detections for this destination...");
      setAddressDetections([]);
      setSelectedDetection(null);
      setShowDetectionsModal(false);
      if (!isPreview) {
        addressSearchMutation.mutate({ address: data.display_name });
      }
    },
    onError: (error) => {
      setErrorMsg(`Geocode failed: ${error.message}`);
    },
  });

  const routeMutation = useMutation<RouteResponse, Error, void>({
    mutationFn: async () => {
      if (!currentPos || !geocoded) {
        throw new Error("GPS position or destination is unavailable.");
      }
      return post<RouteResponse>("/navigation/route", {
        start_lat: currentPos[0],
        start_lon: currentPos[1],
        dest_lat: geocoded.lat,
        dest_lon: geocoded.lon,
      });
    },
    onSuccess: (data) => {
      setRoute(data);
      setErrorMsg(null);
    },
    onError: (error) => {
      setErrorMsg(`Routing failed: ${error.message}`);
    },
  });

  useEffect(() => {
    if (!isPreview && geocoded && currentPos && !route && !routeMutation.isPending) {
      routeMutation.mutate();
    }
  }, [currentPos, geocoded, isPreview, route, routeMutation]);

  const startMutation = useMutation<unknown, Error, void>({
    mutationFn: async () => {
      if (!geocoded) throw new Error("No destination selected.");
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
      queryClient.invalidateQueries({ queryKey: ["nav-status"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-status"] });
    },
    onError: (error) => {
      setErrorMsg(`Start failed: ${error.message}`);
    },
  });

  const stopMutation = useMutation<unknown, Error, void>({
    mutationFn: () => post("/navigation/stop", {}),
    onSuccess: () => {
      setNavigating(false);
      setArrived(false);
      setRoute(null);
      setGeocoded(null);
      setAddress("");
      setAddressDetections([]);
      setSelectedDetection(null);
      setShowDetectionsModal(false);
      setAddressNotice(null);
      setErrorMsg(null);
      queryClient.invalidateQueries({ queryKey: ["nav-status"] });
      queryClient.invalidateQueries({ queryKey: ["runtime-status"] });
    },
    onError: (error) => {
      setErrorMsg(`Stop failed: ${error.message}`);
    },
  });

  const liveCameras = isPreview ? [...PREVIEW_CAMERAS] : runtimeQuery.data?.cameras ?? [];
  const onlineCameraCount = liveCameras.filter((camera) => camera.status === "Online").length;
  const activeRoute = route ?? navStatusQuery.data?.current_route ?? null;
  const routePolyline = activeRoute?.polyline.map(([lat, lon]) => [lat, lon] as LatLngTuple);
  const canStart = Boolean(geocoded && currentPos && !navigating && !arrived && !isPreview);
  const isLoading = geocodeMutation.isPending || addressSearchMutation.isPending || routeMutation.isPending || startMutation.isPending || stopMutation.isPending;
  const mapCenter: LatLngTuple = currentPos ?? [39.5, -98.35];
  const runtimePipelineActive = runtimeQuery.data?.pipeline_active ?? (arrived || !navigating);
  const recentDistance = navStatusQuery.data?.arrival.last_distance_m;

  useEffect(() => {
    onStateChange({
      arrived,
      gpsLocked: currentPos !== null,
      navigating,
      camOnline: onlineCameraCount,
    });
  }, [arrived, currentPos, navigating, onStateChange, onlineCameraCount]);

  const selectedDetectionImage = useMemo(
    () => selectedDetection?.composite_path ?? selectedDetection?.snapshot_path ?? selectedDetection?.vehicle_path ?? null,
    [selectedDetection],
  );

  return (
    <div style={S.layout}>
      <aside style={S.sidebar}>
        <section style={S.card}>
          <h3 style={S.cardTitle}>Destination</h3>
          <input
            style={S.input}
            type="text"
            placeholder="Enter address or place name"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && address.trim() && !isPreview) {
                geocodeMutation.mutate(address.trim());
              }
            }}
            disabled={navigating || isLoading || isPreview}
          />
          <button
            style={{ ...S.actionBtn, ...S.btnBlue, opacity: !address.trim() || navigating || isLoading ? 0.5 : 1 }}
            onClick={() => address.trim() && !isPreview && geocodeMutation.mutate(address.trim())}
            disabled={!address.trim() || navigating || isLoading || isPreview}
          >
            {geocodeMutation.isPending ? "Searching..." : "Search destination"}
          </button>
          {geocoded && (
            <div style={S.resultBox}>
              <div style={S.resultTitle}>{geocoded.display_name}</div>
              <div style={S.resultMeta}>{geocoded.lat.toFixed(5)}, {geocoded.lon.toFixed(5)}</div>
            </div>
          )}
          {addressNotice && <div style={S.notice}>{addressNotice}</div>}
        </section>

        <section style={S.card}>
          <h3 style={S.cardTitle}>Address intelligence</h3>
          {!geocoded && (
            <p style={S.helperText}>Search a destination first to look for prior detections stored near that location.</p>
          )}
          {geocoded && addressSearchMutation.isPending && (
            <p style={S.helperText}>Searching nearby historical detections...</p>
          )}
          {geocoded && !addressSearchMutation.isPending && addressDetections.length === 0 && (
            <p style={S.helperText}>No stored detections are currently associated with this destination.</p>
          )}
          {addressDetections.length > 0 && (
            <>
              <div style={S.infoRow}>
                <span style={S.infoLabel}>Stored detections</span>
                <span style={S.infoValue}>{addressDetections.length}</span>
              </div>
              <div style={S.infoRow}>
                <span style={S.infoLabel}>Most recent plate</span>
                <span style={S.infoValue}>{addressDetections[0]?.plate_text ?? "No plate"}</span>
              </div>
              <button style={{ ...S.actionBtn, ...S.btnSlate }} onClick={() => setShowDetectionsModal(true)}>
                Review nearby detections
              </button>
            </>
          )}
        </section>

        <section style={S.card}>
          <h3 style={S.cardTitle}>Arrival trigger distance</h3>
          <input
            type="range"
            min={RADIUS_MIN_FT}
            max={RADIUS_MAX_FT}
            step={1}
            value={arrivalRadiusFt}
            onChange={(event) => setArrivalRadiusFt(Number(event.target.value))}
            disabled={navigating || isPreview}
            style={S.slider}
          />
          <div style={S.infoRow}>
            <span style={S.infoLabel}>Current radius</span>
            <span style={S.infoValue}>{arrivalRadiusFt} ft</span>
          </div>
          <div style={S.helperText}>
            Default profile value: {profileQuery.data?.arrival_distance_ft ?? RADIUS_DEFAULT_FT} ft
          </div>
        </section>

        <section style={S.card}>
          <h3 style={S.cardTitle}>Route summary</h3>
          {activeRoute ? (
            <>
              <div style={S.infoRow}>
                <span style={S.infoLabel}>Distance</span>
                <span style={S.infoValue}>{formatDistance(activeRoute.distance_m)}</span>
              </div>
              <div style={S.infoRow}>
                <span style={S.infoLabel}>Duration</span>
                <span style={S.infoValue}>{formatDuration(activeRoute.duration_s)}</span>
              </div>
              <div style={S.infoRow}>
                <span style={S.infoLabel}>ETA</span>
                <span style={S.infoValue}>{formatEta(activeRoute.eta_iso)}</span>
              </div>
            </>
          ) : (
            <p style={S.helperText}>Route data will appear here after a destination is geocoded and the current position is available.</p>
          )}
        </section>

        <section style={S.card}>
          <h3 style={S.cardTitle}>Runtime status</h3>
          <div style={S.infoRow}>
            <span style={S.infoLabel}>GPS</span>
            <Badge active={currentPos !== null} activeText="Locked" inactiveText="No signal" />
          </div>
          <div style={S.infoRow}>
            <span style={S.infoLabel}>Navigation</span>
            <Badge active={navigating} activeText="Active" inactiveText="Idle" />
          </div>
          <div style={S.infoRow}>
            <span style={S.infoLabel}>Pipeline</span>
            <Badge active={runtimePipelineActive} activeText="Active" inactiveText="Paused" activeColor="#22c55e" inactiveColor="#f59e0b" />
          </div>
          <div style={S.infoRow}>
            <span style={S.infoLabel}>Cameras online</span>
            <span style={S.infoValue}>{onlineCameraCount}/{liveCameras.length}</span>
          </div>
          <div style={S.infoRow}>
            <span style={S.infoLabel}>WS clients</span>
            <span style={S.infoValue}>{runtimeQuery.data?.ws_clients ?? 0}</span>
          </div>
          <div style={S.infoRow}>
            <span style={S.infoLabel}>Distance to scene</span>
            <span style={S.infoValue}>{recentDistance === null || recentDistance === undefined ? "Unknown" : formatDistance(recentDistance)}</span>
          </div>
        </section>

        <section style={S.card}>
          <h3 style={S.cardTitle}>Mission action</h3>
          {!navigating && !arrived ? (
            <button style={{ ...S.actionBtn, ...S.btnGreen, opacity: canStart ? 1 : 0.5 }} onClick={() => startMutation.mutate()} disabled={!canStart || isLoading}>
              {startMutation.isPending ? "Starting..." : "Start navigation"}
            </button>
          ) : (
            <button style={{ ...S.actionBtn, ...S.btnRed }} onClick={() => stopMutation.mutate()} disabled={isLoading || isPreview}>
              {stopMutation.isPending ? "Stopping..." : "Stop navigation"}
            </button>
          )}
          <p style={S.helperText}>
            Starting navigation pauses scanning until arrival. Once on scene, the target board resumes automatically.
          </p>
        </section>

        {errorMsg && <div style={S.errorBox}>{errorMsg}</div>}

        <TargetList
          scanning={arrived}
          previewTargets={isPreview ? PREVIEW_TARGETS : undefined}
          maxTargets={profileQuery.data?.max_tracked_vehicles ?? 10}
        />
      </aside>

      <div style={S.content}>
        <div style={S.viewToggle}>
          <button style={{ ...S.toggleBtn, ...(viewMode === "cameras" ? S.toggleActive : {}) }} onClick={() => setViewMode("cameras")}>Runtime cameras</button>
          <button style={{ ...S.toggleBtn, ...(viewMode === "map" ? S.toggleActive : {}) }} onClick={() => setViewMode("map")}>Route map</button>
          <div style={S.overlayMeta}>
            <span style={S.overlayItem}>Mode: <strong>{arrived ? "On scene" : navigating ? "Navigation" : "Standby"}</strong></span>
            <span style={S.overlayItem}>Cameras: <strong>{onlineCameraCount}/{liveCameras.length}</strong></span>
            <span style={S.overlayItem}>Pipeline: <strong>{runtimePipelineActive ? "Active" : "Paused"}</strong></span>
            {activeRoute && <span style={S.overlayItem}>ETA: <strong>{formatEta(activeRoute.eta_iso)}</strong></span>}
          </div>
        </div>

        {viewMode === "cameras" && (
          <div style={S.cameraGrid}>
            {liveCameras.length === 0 ? (
              <div style={S.emptyPanel}>No runtime cameras are currently configured.</div>
            ) : (
              liveCameras.map((camera) => (
                <div key={camera.camera_id} style={S.cameraCard}>
                  <div style={S.cameraBadge}>{cameraBadge(camera.name)}</div>
                  <div style={S.cameraTelemetry}>Runtime telemetry</div>
                  <div style={S.cameraName}>{camera.name}</div>
                  <div style={S.cameraStats}>Status: {camera.status}</div>
                  <div style={S.cameraStats}>FPS: {camera.fps.toFixed(1)}</div>
                  <div style={S.cameraStats}>Queue: {camera.queue_depth}</div>
                  <div style={S.cameraStats}>
                    Last frame: {camera.last_frame_age_s === null ? "n/a" : `${camera.last_frame_age_s.toFixed(1)}s ago`}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {viewMode === "map" && (
          <div style={S.mapWrapper}>
            <MapContainer center={mapCenter} zoom={13} style={{ height: "100%", width: "100%" }}>
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              />
              {currentPos && <MapRecenter center={currentPos} />}
              {currentPos && (
                <Marker position={currentPos} icon={blueIcon}>
                  <Popup>Current position</Popup>
                </Marker>
              )}
              {geocoded && (
                <Marker position={[geocoded.lat, geocoded.lon]} icon={redIcon}>
                  <Popup>{geocoded.display_name}</Popup>
                </Marker>
              )}
              {routePolyline && routePolyline.length > 0 && <Polyline positions={routePolyline} color="#3b82f6" weight={4} opacity={0.85} />}
            </MapContainer>
          </div>
        )}

        <div style={S.bottomStrip}>
          {viewMode === "cameras"
            ? `Runtime telemetry loaded | ${onlineCameraCount}/${liveCameras.length} cameras online`
            : navigating
              ? "Route active | monitoring approach to destination"
              : "Map idle | select a destination to begin"}
        </div>
      </div>

      {showDetectionsModal && (
        <div style={S.modalBackdrop} onClick={() => setShowDetectionsModal(false)}>
          <div style={S.modalPanel} onClick={(event) => event.stopPropagation()}>
            <div style={S.modalHeader}>
              <h3 style={{ margin: 0, fontSize: "1rem" }}>Detection history at destination</h3>
              <button style={S.modalClose} onClick={() => setShowDetectionsModal(false)}>Close</button>
            </div>
            <div style={S.modalBody}>
              <div style={S.modalList}>
                {addressDetections.map((detection) => (
                  <button
                    key={detection.id}
                    style={{ ...S.modalItem, ...(selectedDetection?.id === detection.id ? S.modalItemActive : {}) }}
                    onClick={() => setSelectedDetection(detection)}
                  >
                    <div style={{ fontWeight: 700 }}>{detection.plate_text ?? "No plate"}</div>
                    <div style={S.modalSubtext}>{detection.make ?? "Unknown"} {detection.model ?? ""} | {detection.camera_id}</div>
                  </button>
                ))}
              </div>
              <div style={S.modalDetail}>
                {selectedDetection ? (
                  <>
                    <InfoRow label="Plate" value={selectedDetection.plate_text ?? "N/A"} />
                    <InfoRow label="Vehicle" value={selectedDetection.vehicle_class ?? "Unknown"} />
                    <InfoRow label="Make / Model" value={`${selectedDetection.make ?? "Unknown"} ${selectedDetection.model ?? ""}`.trim()} />
                    <InfoRow label="Address" value={selectedDetection.detection_address ?? "Unknown"} />
                    <InfoRow label="Coords" value={`${selectedDetection.latitude?.toFixed?.(5) ?? "-"}, ${selectedDetection.longitude?.toFixed?.(5) ?? "-"}`} />
                    {selectedDetectionImage && <div style={S.imagePath}>Evidence path: {selectedDetectionImage}</div>}
                  </>
                ) : (
                  <p style={S.helperText}>Select a stored detection to inspect the runtime detail.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={S.infoRow}>
      <span style={S.infoLabel}>{label}</span>
      <span style={S.infoValue}>{value}</span>
    </div>
  );
}

function Badge({
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
    <span style={{ ...S.badge, background: active ? activeColor : inactiveColor }}>
      {active ? activeText : inactiveText}
    </span>
  );
}

const S: Record<string, CSSProperties> = {
  layout: {
    display: "flex",
    height: "100%",
    overflow: "hidden",
  },
  sidebar: {
    width: "310px",
    minWidth: "290px",
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
    padding: "0.85rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.55rem",
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
  actionBtn: {
    width: "100%",
    padding: "12px",
    borderRadius: "8px",
    fontWeight: 700,
    fontSize: "0.84rem",
    border: "none",
    minHeight: "46px",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    cursor: "pointer",
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
  btnSlate: {
    background: "#1a2332",
    color: "#e8edf5",
    border: "1px solid #334155",
  },
  slider: {
    width: "100%",
    accentColor: "#3b82f6",
  },
  resultBox: {
    padding: "0.65rem",
    background: "#1a2332",
    borderRadius: "8px",
    border: "1px solid #334155",
  },
  resultTitle: {
    fontSize: "0.82rem",
    color: "#e2e8f0",
    wordBreak: "break-word",
  },
  resultMeta: {
    fontSize: "0.72rem",
    color: "#64748b",
    marginTop: "4px",
  },
  notice: {
    fontSize: "0.78rem",
    color: "#93c5fd",
  },
  helperText: {
    margin: 0,
    fontSize: "0.76rem",
    lineHeight: 1.45,
    color: "#94a3b8",
  },
  infoRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "12px",
  },
  infoLabel: {
    fontSize: "0.8rem",
    color: "#94a3b8",
  },
  infoValue: {
    fontSize: "0.84rem",
    fontWeight: 600,
    color: "#e8edf5",
    textAlign: "right",
  },
  badge: {
    fontSize: "0.68rem",
    fontWeight: 700,
    padding: "4px 10px",
    borderRadius: "999px",
    color: "#fff",
    letterSpacing: "0.04em",
    textTransform: "uppercase",
  },
  errorBox: {
    background: "#450a0a",
    border: "1px solid #ef4444",
    borderRadius: "8px",
    color: "#fca5a5",
    fontSize: "0.82rem",
    padding: "10px 12px",
  },
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
    gap: "8px",
    padding: "8px 10px",
    background: "#0c1220",
    borderBottom: "1px solid #1e293b",
    flexShrink: 0,
  },
  toggleBtn: {
    padding: "7px 14px",
    borderRadius: "8px",
    border: "1px solid #334155",
    background: "#111827",
    color: "#94a3b8",
    fontSize: "0.8rem",
    fontWeight: 700,
    cursor: "pointer",
  },
  toggleActive: {
    background: "rgba(37, 99, 235, 0.15)",
    border: "1px solid #2563eb",
    color: "#e8edf5",
  },
  overlayMeta: {
    display: "flex",
    gap: "12px",
    marginLeft: "auto",
    flexWrap: "wrap",
    justifyContent: "flex-end",
  },
  overlayItem: {
    fontSize: "0.75rem",
    color: "#94a3b8",
  },
  cameraGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
    gap: "12px",
    padding: "12px",
    overflow: "auto",
    background: "#080c14",
    flex: 1,
  },
  cameraCard: {
    position: "relative",
    borderRadius: "14px",
    border: "1px solid #1e293b",
    background: "linear-gradient(180deg, rgba(17,24,39,0.98), rgba(11,18,32,0.96))",
    minHeight: "220px",
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "flex-end",
    gap: "6px",
  },
  cameraBadge: {
    position: "absolute",
    top: "12px",
    left: "12px",
    background: "#0f172a",
    border: "1px solid #334155",
    color: "#7dd3fc",
    fontWeight: 800,
    fontSize: "0.8rem",
    borderRadius: "999px",
    padding: "4px 10px",
  },
  cameraTelemetry: {
    fontSize: "0.72rem",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#64748b",
  },
  cameraName: {
    fontSize: "1rem",
    fontWeight: 700,
    color: "#e8edf5",
  },
  cameraStats: {
    fontSize: "0.82rem",
    color: "#94a3b8",
  },
  emptyPanel: {
    border: "1px dashed #334155",
    borderRadius: "12px",
    padding: "24px",
    color: "#94a3b8",
    fontSize: "0.9rem",
    background: "#0c1220",
  },
  mapWrapper: {
    flex: 1,
    minHeight: 0,
  },
  bottomStrip: {
    padding: "10px 14px",
    borderTop: "1px solid #1e293b",
    background: "#0c1220",
    color: "#64748b",
    fontSize: "0.78rem",
    flexShrink: 0,
  },
  modalBackdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(2, 6, 23, 0.82)",
    display: "grid",
    placeItems: "center",
    zIndex: 50,
  },
  modalPanel: {
    width: "min(980px, 92vw)",
    maxHeight: "80vh",
    background: "#0b1220",
    border: "1px solid #1e293b",
    borderRadius: "14px",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  modalHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "14px 16px",
    borderBottom: "1px solid #1e293b",
  },
  modalClose: {
    background: "#111827",
    color: "#e8edf5",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "8px 12px",
    cursor: "pointer",
  },
  modalBody: {
    display: "grid",
    gridTemplateColumns: "280px 1fr",
    minHeight: 0,
    flex: 1,
  },
  modalList: {
    borderRight: "1px solid #1e293b",
    overflowY: "auto",
    padding: "12px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
  modalItem: {
    width: "100%",
    textAlign: "left",
    background: "#111827",
    border: "1px solid #1e293b",
    borderRadius: "10px",
    padding: "10px 12px",
    color: "#e8edf5",
    cursor: "pointer",
  },
  modalItemActive: {
    border: "1px solid #2563eb",
    background: "rgba(37, 99, 235, 0.12)",
  },
  modalSubtext: {
    fontSize: "0.76rem",
    color: "#94a3b8",
    marginTop: "4px",
  },
  modalDetail: {
    padding: "16px",
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    overflowY: "auto",
  },
  imagePath: {
    fontSize: "0.78rem",
    color: "#93c5fd",
    wordBreak: "break-word",
    background: "#111827",
    border: "1px solid #1e293b",
    borderRadius: "8px",
    padding: "10px 12px",
  },
};
