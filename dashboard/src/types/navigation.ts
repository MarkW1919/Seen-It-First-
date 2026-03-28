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

/** A plate detection row for the live detection table */
export interface PlateDetection {
  id:         string;           // unique row id (track_id + timestamp)
  plate1:     string;           // primary OCR read
  plate2:     string;           // secondary / alternate read (or same as plate1)
  state:      string;           // US state abbreviation
  camera_id:  string;           // e.g. "cam_1", "cam_3"
  confidence: number;           // plate OCR confidence 0–1
  is_hotlist: boolean;
  timestamp:  number;           // unix epoch seconds
  image_url:  string | null;    // evidence snapshot URL (future)
}

/** WebSocket event payloads */
export type WsEvent =
  | { event: "ARRIVED"; lat: number; lon: number; destination: { lat: number; lon: number; display_name: string } | null }
  | { event: "STATUS";  navigating: boolean; arrived: boolean }
  | {
      event:        "DETECTION";
      track_id:     string;
      plate_text:   string;
      camera_id:    string;
      plate_conf:   number;
      vehicle_class: string;
      vehicle_conf: number;
      bbox:         number[];
      timestamp:    number;
      state?:       string;
      image_url?:   string;
    }
  | {
      event:        "ALERT";
      plate:        string;
      vehicle_class: string;
      camera_id:    string;
      confidence:   number;
      timestamp:    number;
      reason:       string;
      priority:     string;
      track_id:     string;
    };
