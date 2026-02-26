import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import { useQuery } from "@tanstack/react-query";
import { useGeolocation } from "../hooks/useGeolocation";
import { useAppStore } from "../store";
import { api } from "../services/api";
import { formatVehicleDescription } from "../utils/format";

// Fix Leaflet default marker icon
import iconUrl from "leaflet/dist/images/marker-icon.png";
import iconShadow from "leaflet/dist/images/marker-shadow.png";

const DefaultIcon = L.icon({
  iconUrl,
  shadowUrl: iconShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
});
L.Marker.prototype.options.icon = DefaultIcon;

// Alert marker
const alertIcon = L.divIcon({
  className: "alert-marker",
  html: '<div style="width:20px;height:20px;background:#ef4444;border-radius:50%;border:3px solid white;box-shadow:0 0 10px rgba(239,68,68,0.6);"></div>',
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

// Detection marker
const detectionIcon = L.divIcon({
  className: "detection-marker",
  html: '<div style="width:12px;height:12px;background:#3b82f6;border-radius:50%;border:2px solid white;"></div>',
  iconSize: [12, 12],
  iconAnchor: [6, 6],
});

// GPS marker
const gpsIcon = L.divIcon({
  className: "gps-marker",
  html: '<div style="width:16px;height:16px;background:#22c55e;border-radius:50%;border:3px solid white;box-shadow:0 0 8px rgba(34,197,94,0.5);"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

function MapFollower() {
  const map = useMap();
  const { position } = useGeolocation();
  const mapFollowGps = useAppStore((s) => s.mapFollowGps);

  useEffect(() => {
    if (position && mapFollowGps) {
      map.setView([position.latitude, position.longitude], map.getZoom());
    }
  }, [position, mapFollowGps, map]);

  return null;
}

export default function MapView() {
  const { position } = useGeolocation();
  const mapFollowGps = useAppStore((s) => s.mapFollowGps);
  const setMapFollowGps = useAppStore((s) => s.setMapFollowGps);
  const activeAlerts = useAppStore((s) => s.activeAlerts);

  // Fetch recent detections with locations
  const { data: detections } = useQuery({
    queryKey: ["detections", "map"],
    queryFn: () => api.getDetections({ page_size: 100 }),
    refetchInterval: 15000,
  });

  const detectionsWithLocation =
    detections?.items.filter((d) => d.latitude && d.longitude) || [];

  const center: [number, number] = position
    ? [position.latitude, position.longitude]
    : [39.8283, -98.5795]; // US center

  return (
    <div className="h-full flex flex-col">
      {/* Map controls */}
      <div className="absolute top-14 right-3 z-[1000] flex flex-col gap-2">
        <button
          onClick={() => setMapFollowGps(!mapFollowGps)}
          className={`p-2 rounded-lg shadow-lg ${
            mapFollowGps
              ? "bg-primary-600 text-white"
              : "bg-slate-700 text-slate-300"
          }`}
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>

      <MapContainer
        center={center}
        zoom={position ? 15 : 5}
        className="flex-1 w-full"
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <MapFollower />

        {/* Current position */}
        {position && (
          <Marker
            position={[position.latitude, position.longitude]}
            icon={gpsIcon}
          >
            <Popup>
              <div className="text-slate-900">
                <strong>Your Location</strong>
                <br />
                {position.speed !== null && `${(position.speed * 2.237).toFixed(0)} mph`}
              </div>
            </Popup>
          </Marker>
        )}

        {/* Alert markers */}
        {activeAlerts
          .filter((a) => a.latitude && a.longitude)
          .map((alert) => (
            <Marker
              key={alert.id}
              position={[alert.latitude!, alert.longitude!]}
              icon={alertIcon}
            >
              <Popup>
                <div className="text-slate-900">
                  <strong className="text-red-600">
                    ALERT: {alert.plate_text_matched}
                  </strong>
                  <br />
                  Confidence: {(alert.match_confidence * 100).toFixed(0)}%
                  <br />
                  {alert.address}
                  <br />
                  <small>{new Date(alert.created_at).toLocaleString()}</small>
                </div>
              </Popup>
            </Marker>
          ))}

        {/* Detection markers */}
        {detectionsWithLocation.map((det) => (
          <Marker
            key={det.id}
            position={[det.latitude!, det.longitude!]}
            icon={detectionIcon}
          >
            <Popup>
              <div className="text-slate-900">
                {det.plate_reads[0] && (
                  <strong>{det.plate_reads[0].plate_text}</strong>
                )}
                <br />
                {formatVehicleDescription(det)}
                <br />
                <small>{new Date(det.created_at).toLocaleString()}</small>
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
