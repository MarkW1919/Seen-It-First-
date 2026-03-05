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
  destination: { lat: number; lon: number; display_name: string } | null;
  current_pos: LatLon | null;
  pipeline_active: boolean;
  arrival: {
    active: boolean;
    arrived: boolean;
    destination: LatLon | null;
    last_distance_m: number | null;
    radius_m: number;
  };
  ws_clients: number;
}

/** WebSocket event payloads */
export type WsEvent =
  | { event: "ARRIVED"; lat: number; lon: number; destination: { lat: number; lon: number; display_name: string } | null }
  | { event: "STATUS"; navigating: boolean; arrived: boolean };
