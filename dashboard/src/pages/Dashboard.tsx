/**
 * Dashboard — main wireframe layout.
 *
 * Layout:
 *   ┌─ NavPanel (248px) ─┬─ Main (flex-1) ─────────────────────┐
 *   │                    │  view="cameras":                     │
 *   │  Brand             │    CameraFeed (top 58%)              │
 *   │  View Toggle       │    PlateTable (bottom 42%)           │
 *   │  System Status     │                                      │
 *   │  Destination       │  view="map":                         │
 *   │  Arrival Radius    │    Leaflet map (NavigationPage body) │
 *   │  Route Info        │                                      │
 *   │  Start/Stop        │                                      │
 *   └────────────────────┴──────────────────────────────────────┘
 *   └─ StatusBar (28px) ───────────────────────────────────────┘
 *
 * State is managed here and passed down to child components.
 * WebSocket events (DETECTION, ALERT, ARRIVED) are processed here.
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  MapContainer, TileLayer, Marker, Polyline, Popup, useMap,
} from "react-leaflet";
import { icon, type LatLngTuple } from "leaflet";

import { useWebSocket } from "../hooks/useWebSocket";
import { NavPanel } from "../components/NavPanel";
import { CameraFeed } from "../components/CameraFeed";
import { PlateTable, SEED_DETECTIONS } from "../components/PlateTable";
import { StatusBar } from "../components/StatusBar";
import { TargetList } from "../components/TargetList";

import type {
  GeocodeResponse, RouteResponse, NavStatus, WsEvent, PlateDetection,
} from "../types/navigation";

// ── Constants ────────────────────────────────────────────────────────────
const RADIUS_DEFAULT_FT  = 300;
const GPS_INTERVAL_MS    = 2000;
const MAX_PLATE_ROWS     = 120;  // rolling window kept in state
const DEFAULT_CENTER: LatLngTuple = [39.5, -98.35];

// ── Leaflet icons ────────────────────────────────────────────────────────
const blueIcon = icon({
  iconUrl:    "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl:  "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize:   [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});
const redIcon = icon({
  iconUrl:    "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png",
  shadowUrl:  "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize:   [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34],
});

function MapRecenter({ center }: { center: LatLngTuple }) {
  const map = useMap();
  useEffect(() => { map.setView(center, map.getZoom()); }, [center, map]);
  return null;
}

// ── API helpers ──────────────────────────────────────────────────────────
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

// ── WS detection → PlateDetection converter ──────────────────────────────
let _idSeq = 0;
function wsToPlate(ev: Extract<WsEvent, { event: "DETECTION" }>): PlateDetection {
  return {
    id:         `det-${++_idSeq}`,
    plate1:     ev.plate_text,
    plate2:     ev.plate_text,          // backend may add alt-read field later
    state:      ev.state ?? "??",
    camera_id:  ev.camera_id,
    confidence: ev.plate_conf,
    is_hotlist: false,
    timestamp:  ev.timestamp,
    image_url:  ev.image_url ?? null,
  };
}

function wsAlertToPlate(ev: Extract<WsEvent, { event: "ALERT" }>): PlateDetection {
  return {
    id:         `alt-${++_idSeq}`,
    plate1:     ev.plate,
    plate2:     ev.plate,
    state:      "??",
    camera_id:  ev.camera_id,
    confidence: ev.confidence,
    is_hotlist: true,
    timestamp:  ev.timestamp,
    image_url:  null,
  };
}

// ── Dashboard ────────────────────────────────────────────────────────────
export default function Dashboard() {
  const qc = useQueryClient();

  // ── View ──────────────────────────────────────────────────────
  const [view, setView] = useState<"cameras" | "map">("cameras");

  // ── Navigation state ──────────────────────────────────────────
  const [address, setAddress]       = useState("");
  const [geocoded, setGeocoded]     = useState<GeocodeResponse | null>(null);
  const [route, setRoute]           = useState<RouteResponse | null>(null);
  const [arrivalRadiusFt, setRadius] = useState(RADIUS_DEFAULT_FT);
  const [navigating, setNavigating] = useState(false);
  const [arrived, setArrived]       = useState(false);
  const [errorMsg, setErrorMsg]     = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [alertCount, setAlertCount] = useState(0);

  // ── GPS ───────────────────────────────────────────────────────
  const [currentPos, setCurrentPos] = useState<[number, number] | null>(null);
  const currentPosRef = useRef<[number, number] | null>(null);
  const mapCenter: LatLngTuple = currentPos ?? DEFAULT_CENTER;

  // ── Plate detections (newest first) ──────────────────────────
  const [detections, setDetections] = useState<PlateDetection[]>(SEED_DETECTIONS);
  const totalCountRef = useRef(SEED_DETECTIONS.length);

  // ── Nav status polling ────────────────────────────────────────
  useQuery<NavStatus>({
    queryKey: ["nav-status"],
    queryFn: () => fetch("/navigation/status").then((r) => r.json()),
    refetchInterval: navigating ? 5000 : false,
    enabled: navigating,
  });

  // ── WebSocket ─────────────────────────────────────────────────
  const handleWs = useCallback((ev: WsEvent) => {
    if (ev.event === "ARRIVED") {
      setArrived(true);
      setNavigating(false);
      qc.invalidateQueries({ queryKey: ["nav-status"] });
    } else if (ev.event === "STATUS") {
      setWsConnected(true);
    } else if (ev.event === "DETECTION") {
      const row = wsToPlate(ev);
      totalCountRef.current += 1;
      setDetections((prev) => [row, ...prev].slice(0, MAX_PLATE_ROWS));
    } else if (ev.event === "ALERT") {
      const row = wsAlertToPlate(ev);
      setAlertCount((c) => c + 1);
      totalCountRef.current += 1;
      setDetections((prev) => [row, ...prev].slice(0, MAX_PLATE_ROWS));
    }
  }, [qc]);

  useWebSocket(handleWs);

  // Mark WS connected once the hook mounts (STATUS event arrives on connect)
  useEffect(() => {
    const timer = setTimeout(() => setWsConnected(true), 3500);
    return () => clearTimeout(timer);
  }, []);

  // ── Browser Geolocation ───────────────────────────────────────
  useEffect(() => {
    if (!navigator.geolocation) return;
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        const coords: [number, number] = [pos.coords.latitude, pos.coords.longitude];
        setCurrentPos(coords);
        currentPosRef.current = coords;
      },
      (err) => console.warn("Geolocation:", err.message),
      { enableHighAccuracy: true, maximumAge: 5000 },
    );
    return () => navigator.geolocation.clearWatch(id);
  }, []);

  // ── GPS POST interval ─────────────────────────────────────────
  useEffect(() => {
    if (!navigating && !arrived) return;
    const iv = setInterval(() => {
      const pos = currentPosRef.current;
      if (pos) post("/navigation/gps", { lat: pos[0], lon: pos[1] }).catch(() => {});
    }, GPS_INTERVAL_MS);
    return () => clearInterval(iv);
  }, [navigating, arrived]);

  // ── Geocode mutation ──────────────────────────────────────────
  const geocodeMut = useMutation<GeocodeResponse, Error, string>({
    mutationFn: (addr) => post<GeocodeResponse>("/navigation/geocode", { address: addr }),
    onSuccess: (data) => { setGeocoded(data); setRoute(null); setErrorMsg(null); },
    onError: (err) => setErrorMsg(`Geocode failed: ${err.message}`),
  });

  // ── Route mutation ────────────────────────────────────────────
  const routeMut = useMutation<RouteResponse, Error, void>({
    mutationFn: async () => {
      if (!currentPos || !geocoded) throw new Error("GPS or destination not set");
      return post<RouteResponse>("/navigation/route", {
        start_lat: currentPos[0], start_lon: currentPos[1],
        dest_lat:  geocoded.lat,  dest_lon:  geocoded.lon,
      });
    },
    onSuccess: (data) => setRoute(data),
    onError: (err) => setErrorMsg(`Routing failed: ${err.message}`),
  });

  useEffect(() => {
    if (geocoded && currentPos && !route) routeMut.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geocoded, currentPos]);

  // ── Start mutation ────────────────────────────────────────────
  const startMut = useMutation<unknown, Error, void>({
    mutationFn: async () => {
      if (!geocoded) throw new Error("No destination");
      return post("/navigation/start", {
        dest_lat: geocoded.lat, dest_lon: geocoded.lon,
        display_name: geocoded.display_name,
        radius_ft: arrivalRadiusFt,
      });
    },
    onSuccess: () => { setNavigating(true); setArrived(false); setErrorMsg(null); },
    onError: (err) => setErrorMsg(`Start failed: ${err.message}`),
  });

  // ── Stop mutation ─────────────────────────────────────────────
  const stopMut = useMutation<unknown, Error, void>({
    mutationFn: () => post("/navigation/stop", {}),
    onSuccess: () => {
      setNavigating(false); setArrived(false); setRoute(null);
      setGeocoded(null); setAddress(""); setErrorMsg(null);
    },
    onError: (err) => setErrorMsg(`Stop failed: ${err.message}`),
  });

  // ── Derived ───────────────────────────────────────────────────
  const pipelineActive = arrived || !navigating;
  const routePolyline: LatLngTuple[] | undefined = route?.polyline.map(
    ([lat, lon]) => [lat, lon] as LatLngTuple,
  );

  // ── Render ────────────────────────────────────────────────────
  return (
    <div style={s.root}>

      {/* ── ARRIVED banner ────────────────────────────────────── */}
      {arrived && (
        <div style={s.arrivedBanner}>
          ◉ ARRIVED AT DESTINATION — LPR SCANNING ACTIVE
        </div>
      )}

      {/* ── Body ──────────────────────────────────────────────── */}
      <div style={s.body}>

        {/* ── Left nav panel ──────────────────────────────────── */}
        <NavPanel
          address={address}
          onAddressChange={setAddress}
          geocoded={geocoded}
          onSearch={() => address.trim() && geocodeMut.mutate(address.trim())}
          searchPending={geocodeMut.isPending}
          route={route}
          arrivalRadiusFt={arrivalRadiusFt}
          onRadiusChange={setRadius}
          navigating={navigating}
          arrived={arrived}
          gpsLocked={!!currentPos}
          pipelineActive={pipelineActive}
          wsConnected={wsConnected}
          detectionCount={totalCountRef.current}
          onStart={() => startMut.mutate()}
          onStop={() => stopMut.mutate()}
          startPending={startMut.isPending}
          stopPending={stopMut.isPending}
          errorMsg={errorMsg}
          view={view}
          onViewChange={setView}
        />

        {/* ── Main content area ────────────────────────────────── */}
        <div style={s.main}>

          {view === "cameras" && (
            <>
              {/* Camera feed — top 58% */}
              <div style={s.cameraPanel}>
                <CameraFeed pipelineActive={pipelineActive} />
              </div>

              {/* Divider */}
              <div style={s.divider} />

              {/* Plate detection table — bottom 42% */}
              <div style={s.tablePanel}>
                <PlateTable
                  detections={detections}
                  totalCount={totalCountRef.current}
                />
              </div>
            </>
          )}

          {view === "map" && (
            <div style={s.mapWrapper}>
              {/* Target vehicle list shown when scanning */}
              {arrived && (
                <div style={s.targetOverlay}>
                  <TargetList scanning={arrived} />
                </div>
              )}

              <MapContainer
                center={mapCenter}
                zoom={13}
                style={{ height: "100%", width: "100%" }}
              >
                <TileLayer
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                />
                {currentPos && <MapRecenter center={currentPos} />}
                {currentPos && (
                  <Marker position={currentPos} icon={blueIcon}>
                    <Popup>Current Position</Popup>
                  </Marker>
                )}
                {geocoded && (
                  <Marker position={[geocoded.lat, geocoded.lon]} icon={redIcon}>
                    <Popup>{geocoded.display_name}</Popup>
                  </Marker>
                )}
                {routePolyline && routePolyline.length > 0 && (
                  <Polyline
                    positions={routePolyline}
                    color="#3b82f6"
                    weight={4}
                    opacity={0.85}
                  />
                )}
              </MapContainer>
            </div>
          )}

        </div>
      </div>

      {/* ── Status bar ─────────────────────────────────────────── */}
      <StatusBar
        gpsLocked={!!currentPos}
        wsConnected={wsConnected}
        pipelineActive={pipelineActive}
        fps={15}
        cameraCount={3}
        detectionCount={totalCountRef.current}
        alertCount={alertCount}
        navigating={navigating}
      />
    </div>
  );
}

/* ── Styles ─────────────────────────────────────────────────────────────── */
const s = {
  root: {
    display: "flex",
    flexDirection: "column" as const,
    height: "100vh",
    overflow: "hidden",
    background: "#050b14",
    color: "#e2e8f0",
  },
  arrivedBanner: {
    background: "#14532d",
    borderBottom: "1px solid #16a34a",
    color: "#86efac",
    textAlign: "center" as const,
    fontWeight: 800,
    fontSize: "0.85rem",
    padding: "6px",
    letterSpacing: "0.1em",
    flexShrink: 0,
  },
  body: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column" as const,
    overflow: "hidden",
  },
  cameraPanel: {
    flex: "0 0 58%",
    overflow: "hidden",
  },
  divider: {
    height: 2,
    background: "linear-gradient(90deg, #1e3a5f 0%, #2563eb 50%, #1e3a5f 100%)",
    flexShrink: 0,
  },
  tablePanel: {
    flex: "0 0 42%",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column" as const,
  },
  mapWrapper: {
    flex: 1,
    position: "relative" as const,
    overflow: "hidden",
  },
  targetOverlay: {
    position: "absolute" as const,
    top: 10,
    right: 10,
    width: 280,
    maxHeight: "90%",
    overflowY: "auto" as const,
    zIndex: 1000,
    background: "rgba(10,15,28,0.92)",
    border: "1px solid #1e3a5f",
    borderRadius: "8px",
    padding: "8px",
  },
} as const;
