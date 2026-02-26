// ─── User & Auth ───

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: "admin" | "supervisor" | "agent";
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

// ─── Detections ───

export interface PlateRead {
  id: string;
  plate_text: string;
  plate_state: string | null;
  plate_type: string | null;
  confidence: number;
  plate_image_path: string | null;
  raw_ocr: string | null;
  created_at: string;
}

export interface Detection {
  id: string;
  agent_id: string | null;
  session_id: string | null;
  vehicle_type: string | null;
  vehicle_color: string | null;
  vehicle_make: string | null;
  vehicle_model: string | null;
  vehicle_year: number | null;
  vehicle_confidence: number | null;
  image_path: string | null;
  thumbnail_path: string | null;
  latitude: number | null;
  longitude: number | null;
  address: string | null;
  heading: number | null;
  speed: number | null;
  extra: Record<string, unknown>;
  created_at: string;
  plate_reads: PlateRead[];
}

export interface DetectionList {
  items: Detection[];
  total: number;
  page: number;
  page_size: number;
}

// ─── Hot List ───

export interface HotListEntry {
  id: string;
  plate_text: string;
  plate_state: string | null;
  case_number: string | null;
  lender_name: string | null;
  order_type: string;
  vehicle_year: number | null;
  vehicle_make: string | null;
  vehicle_model: string | null;
  vehicle_color: string | null;
  vin: string | null;
  debtor_name: string | null;
  debtor_address: string | null;
  is_active: boolean;
  priority: "low" | "normal" | "high" | "critical";
  notes: string | null;
  created_at: string;
  updated_at: string;
  expires_at: string | null;
}

export interface HotListAlert {
  id: string;
  hotlist_entry_id: string;
  detection_id: string | null;
  plate_text_matched: string;
  match_confidence: number;
  latitude: number | null;
  longitude: number | null;
  address: string | null;
  status: "new" | "acknowledged" | "dispatched" | "resolved" | "false_positive";
  acknowledged_at: string | null;
  resolved_at: string | null;
  notes: string | null;
  created_at: string;
  hotlist_entry: HotListEntry | null;
}

// ─── Camera ───

export interface CameraStatus {
  is_connected: boolean;
  resolution: string;
  fps: number;
  night_mode: boolean;
  ir_enabled: boolean;
  ptz_position: { pan: number; tilt: number; zoom: number };
  streaming: boolean;
  rtsp_url: string | null;
}

// ─── WebSocket Events ───

export interface WSAlert {
  type: "hotlist_alert";
  alert_id: string;
  hotlist_entry_id: string;
  plate_text: string;
  confidence: number;
  vehicle: {
    type?: string;
    color?: string;
    make?: string;
    model?: string;
    year?: number;
  };
  location: { lat?: number; lng?: number; address?: string };
  image_path?: string;
  timestamp: string;
}

export type WSMessage = WSAlert | { type: string; data?: unknown; timestamp: string };

// ─── Navigation ───

export type AppView =
  | "scan"
  | "alerts"
  | "map"
  | "search"
  | "history"
  | "hotlist"
  | "settings";
