export interface LatLon {
  lat: number;
  lon: number;
}

export interface GeocodeResponse {
  lat: number;
  lon: number;
  display_name: string;
}

export interface RouteResponse {
  polyline: [number, number][];  // [[lat, lon], ...]
  distance_m: number;
  duration_s: number;
  eta_iso: string;
}

export interface NavStatus {
  navigating: boolean;
  destination: { lat: number; lon: number; display_name: string; radius_ft?: number; radius_m?: number } | null;
  current_pos: LatLon | null;
  current_route: RouteResponse | null;
  pipeline_active: boolean;
  arrival: {
    active: boolean;
    arrived: boolean;
    destination: LatLon | null;
    last_distance_m: number | null;
    radius_m: number;
    cooldown_remaining_s: number;
  };
  ws_clients: number;
}

/** A ranked vehicle from GET /navigation/targets */
export interface RankedVehicle {
  vehicle_id:    string;
  vehicle_type:  string;
  make:          string;
  model:         string;
  color:         string;
  year_range:    string;
  plate:         string | null;
  confidence:    number;
  distance_ft:   number;
  hotlist_match: boolean;
  score:         number;
  latitude:      number;
  longitude:     number;
  timestamp:     number;
  camera_id:     string;
  fingerprint:   string;
}

/** WebSocket event payloads */
export type WsEvent =
  | { event: "ARRIVED"; lat: number; lon: number; destination: { lat: number; lon: number; display_name: string } | null }
  | { event: "STATUS"; navigating: boolean; arrived: boolean };


export interface DetectionRecord {
  id: number;
  timestamp: number;
  plate_text: string | null;
  vehicle_class: string | null;
  make: string | null;
  model: string | null;
  year_range: string | null;
  confidence: number | null;
  camera_id: string;
  detection_address: string | null;
  latitude: number | null;
  longitude: number | null;
  snapshot_path: string | null;
  plate_path: string | null;
  vehicle_path: string | null;
  composite_path: string | null;
  distance_m?: number | null;
}

export interface DetectionSearchResponse {
  address: string;
  total: number;
  detections: DetectionRecord[];
}
