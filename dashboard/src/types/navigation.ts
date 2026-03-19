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
  polyline: [number, number][];
  distance_m: number;
  duration_s: number;
  eta_iso: string;
}

export interface NavStatus {
  navigating: boolean;
  destination: {
    lat: number;
    lon: number;
    display_name: string;
    radius_ft?: number;
    radius_m?: number;
  } | null;
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

export interface RankedVehicle {
  vehicle_id: string;
  vehicle_type: string;
  make: string;
  model: string;
  color: string;
  year_range: string;
  plate: string | null;
  confidence: number;
  distance_ft: number;
  hotlist_match: boolean;
  score: number;
  latitude: number;
  longitude: number;
  timestamp: number;
  camera_id: string;
  fingerprint: string;
}

export interface AlertEvent {
  event: "ALERT";
  plate: string;
  vehicle_class: string | null;
  camera_id: string;
  confidence: number;
  timestamp: number;
  reason: string;
  priority: string;
  track_id: number;
}

export interface DetectionEvent {
  event: "DETECTION";
  track_id: number;
  camera_id: string;
  bbox?: number[];
  vehicle_class?: string | null;
  make?: string | null;
  model?: string | null;
  color?: string | null;
  year_range?: string | null;
  fingerprint?: string;
  vehicle_conf?: number;
  plate_text?: string | null;
  plate_conf?: number;
  timestamp: number;
  vehicle_path?: string;
  plate_path?: string;
  composite_path?: string;
}

export type WsEvent =
  | { event: "ARRIVED"; lat: number; lon: number; destination: { lat: number; lon: number; display_name: string } | null }
  | { event: "STATUS"; navigating: boolean; arrived: boolean }
  | AlertEvent
  | DetectionEvent;

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

export interface RuntimeCameraSummary {
  camera_id: string;
  name: string;
  status: string;
  fps: number;
  queue_depth: number;
  last_frame_age_s: number | null;
}

export interface RuntimeStatusResponse {
  pipeline_active: boolean;
  navigating: boolean;
  arrived: boolean;
  ws_clients: number;
  operator_gps: LatLon | null;
  cameras: RuntimeCameraSummary[];
}

export interface RecentEventsResponse {
  total: number;
  events: Array<AlertEvent | DetectionEvent>;
}

export interface OperatorProfile {
  hotlist_refresh_sec: number;
  arrival_distance_ft: number;
  show_traffic_overlays: boolean;
  ocr_confidence_threshold: number;
  max_tracked_vehicles: number;
  auto_checkin_on_arrival: boolean;
  silent_shift_mode: boolean;
  low_storage_warning: boolean;
}
