import type {
  User,
  Token,
  Detection,
  DetectionList,
  HotListEntry,
  HotListAlert,
  CameraStatus,
  PlateRead,
} from "../types";

// ─── Demo User ───

export const DEMO_USER: User = {
  id: "demo-user-001",
  email: "demo@reposcanpro.com",
  full_name: "Demo Agent",
  role: "admin",
  is_active: true,
  created_at: new Date().toISOString(),
};

export const DEMO_TOKEN: Token = {
  access_token: "demo-token",
  refresh_token: "demo-refresh",
  token_type: "bearer",
};

// ─── Camera ───

export const DEMO_CAMERA_STATUS: CameraStatus = {
  is_connected: true,
  resolution: "1920x1080",
  fps: 28.4,
  night_mode: false,
  ir_enabled: false,
  ptz_position: { pan: 0, tilt: -5, zoom: 1 },
  streaming: true,
  rtsp_url: "rtsp://localhost:8554/stream",
};

// ─── Hot List Entries ───

export const DEMO_HOTLIST: HotListEntry[] = [
  {
    id: "hl-001",
    plate_text: "ABC1234",
    plate_state: "TX",
    case_number: "REPO-2026-0847",
    lender_name: "First National Auto Finance",
    order_type: "repossession",
    vehicle_year: 2022,
    vehicle_make: "Ford",
    vehicle_model: "F-150",
    vehicle_color: "white",
    vin: "1FTFW1E80NFA12345",
    debtor_name: "James Wilson",
    debtor_address: "4521 Elm Street, Dallas TX 75201",
    is_active: true,
    priority: "high",
    notes: "Subject parks in apartment complex lot B. Best approach 6-8 AM.",
    created_at: "2026-02-10T14:30:00Z",
    updated_at: "2026-02-14T09:15:00Z",
    expires_at: "2026-03-10T00:00:00Z",
  },
  {
    id: "hl-002",
    plate_text: "XYZ7890",
    plate_state: "CA",
    case_number: "REPO-2026-0912",
    lender_name: "Pacific Credit Union",
    order_type: "repossession",
    vehicle_year: 2021,
    vehicle_make: "Honda",
    vehicle_model: "Civic",
    vehicle_color: "blue",
    vin: "2HGFC2F59MH567890",
    debtor_name: "Maria Rodriguez",
    debtor_address: "789 Oak Ave, Los Angeles CA 90012",
    is_active: true,
    priority: "critical",
    notes: "Skip trace indicates subject moved. Check employer address on file.",
    created_at: "2026-02-08T10:00:00Z",
    updated_at: "2026-02-15T16:45:00Z",
    expires_at: null,
  },
  {
    id: "hl-003",
    plate_text: "DEF4567",
    plate_state: "FL",
    case_number: "REPO-2026-0763",
    lender_name: "Sunshine Auto Lending",
    order_type: "repossession",
    vehicle_year: 2020,
    vehicle_make: "Chevrolet",
    vehicle_model: "Silverado",
    vehicle_color: "black",
    vin: "3GCUYDED5LG123456",
    debtor_name: "Robert Chen",
    debtor_address: "2200 Palm Blvd, Miami FL 33101",
    is_active: true,
    priority: "normal",
    notes: null,
    created_at: "2026-02-12T08:20:00Z",
    updated_at: "2026-02-12T08:20:00Z",
    expires_at: "2026-04-01T00:00:00Z",
  },
  {
    id: "hl-004",
    plate_text: "GHI2345",
    plate_state: "AZ",
    case_number: "REPO-2026-1001",
    lender_name: "Desert Financial",
    order_type: "repossession",
    vehicle_year: 2023,
    vehicle_make: "Toyota",
    vehicle_model: "Camry",
    vehicle_color: "silver",
    vin: null,
    debtor_name: "Sarah Johnson",
    debtor_address: "1500 Cactus Rd, Phoenix AZ 85001",
    is_active: true,
    priority: "low",
    notes: "Voluntary surrender attempted - debtor unresponsive.",
    created_at: "2026-02-14T11:00:00Z",
    updated_at: "2026-02-14T11:00:00Z",
    expires_at: null,
  },
];

// ─── Detections ───

function makeDetection(
  id: string,
  plate: string,
  state: string,
  confidence: number,
  vehicle: { type: string; color: string; make: string; model: string; year: number },
  lat: number,
  lng: number,
  address: string,
  minutesAgo: number,
): Detection {
  const created = new Date(Date.now() - minutesAgo * 60000).toISOString();
  const plateRead: PlateRead = {
    id: `pr-${id}`,
    plate_text: plate,
    plate_state: state,
    plate_type: "standard",
    confidence,
    plate_image_path: null,
    raw_ocr: plate,
    created_at: created,
  };
  return {
    id: `det-${id}`,
    agent_id: DEMO_USER.id,
    session_id: null,
    vehicle_type: vehicle.type,
    vehicle_color: vehicle.color,
    vehicle_make: vehicle.make,
    vehicle_model: vehicle.model,
    vehicle_year: vehicle.year,
    vehicle_confidence: 0.88 + Math.random() * 0.1,
    image_path: null,
    thumbnail_path: null,
    latitude: lat,
    longitude: lng,
    address,
    heading: Math.random() * 360,
    speed: 15 + Math.random() * 30,
    extra: {},
    created_at: created,
    plate_reads: [plateRead],
  };
}

export const DEMO_DETECTIONS: Detection[] = [
  makeDetection("001", "ABC1234", "TX", 0.97, { type: "truck", color: "white", make: "Ford", model: "F-150", year: 2022 }, 32.7767, -96.7970, "4521 Elm St, Dallas TX", 2),
  makeDetection("002", "LMN8901", "TX", 0.93, { type: "car", color: "red", make: "Nissan", model: "Altima", year: 2019 }, 32.7800, -96.8005, "Ross Ave & Harwood St, Dallas TX", 5),
  makeDetection("003", "PQR3456", "OK", 0.91, { type: "suv", color: "gray", make: "Jeep", model: "Cherokee", year: 2021 }, 32.7755, -96.7945, "Main St & Commerce, Dallas TX", 8),
  makeDetection("004", "STU6789", "TX", 0.95, { type: "car", color: "black", make: "BMW", model: "3 Series", year: 2023 }, 32.7810, -96.7990, "2100 McKinney Ave, Dallas TX", 12),
  makeDetection("005", "VWX2345", "TX", 0.89, { type: "van", color: "white", make: "Ford", model: "Transit", year: 2020 }, 32.7730, -96.7960, "Elm St & Griffin, Dallas TX", 15),
  makeDetection("006", "DEF4567", "FL", 0.94, { type: "truck", color: "black", make: "Chevrolet", model: "Silverado", year: 2020 }, 32.7785, -96.8020, "1800 Main St, Dallas TX", 20),
  makeDetection("007", "YZA8901", "CA", 0.88, { type: "car", color: "blue", make: "Honda", model: "Accord", year: 2018 }, 32.7740, -96.7930, "Pacific Ave & Akard, Dallas TX", 25),
  makeDetection("008", "BCD1234", "TX", 0.96, { type: "suv", color: "white", make: "Toyota", model: "4Runner", year: 2022 }, 32.7820, -96.7950, "Live Oak St, Dallas TX", 30),
  makeDetection("009", "EFG5678", "NM", 0.90, { type: "car", color: "silver", make: "Hyundai", model: "Elantra", year: 2021 }, 32.7760, -96.8010, "Wood St & Lamar, Dallas TX", 38),
  makeDetection("010", "HIJ9012", "TX", 0.92, { type: "truck", color: "red", make: "Ram", model: "1500", year: 2023 }, 32.7795, -96.7975, "Canton St & Exposition, Dallas TX", 45),
];

// First detection matches a hot list entry
export const DEMO_ALERTS: HotListAlert[] = [
  {
    id: "alert-001",
    hotlist_entry_id: "hl-001",
    detection_id: "det-001",
    plate_text_matched: "ABC1234",
    match_confidence: 0.97,
    latitude: 32.7767,
    longitude: -96.7970,
    address: "4521 Elm St, Dallas TX",
    status: "new",
    acknowledged_at: null,
    resolved_at: null,
    notes: null,
    created_at: DEMO_DETECTIONS[0].created_at,
    hotlist_entry: DEMO_HOTLIST[0],
  },
  {
    id: "alert-002",
    hotlist_entry_id: "hl-003",
    detection_id: "det-006",
    plate_text_matched: "DEF4567",
    match_confidence: 0.94,
    latitude: 32.7785,
    longitude: -96.8020,
    address: "1800 Main St, Dallas TX",
    status: "new",
    acknowledged_at: null,
    resolved_at: null,
    notes: null,
    created_at: DEMO_DETECTIONS[5].created_at,
    hotlist_entry: DEMO_HOTLIST[2],
  },
];

export const DEMO_DETECTION_LIST: DetectionList = {
  items: DEMO_DETECTIONS,
  total: DEMO_DETECTIONS.length,
  page: 1,
  page_size: 50,
};

export const DEMO_PLATE_STATS = {
  total_reads: 1847,
  unique_plates: 1203,
  top_states: [
    { state: "TX", count: 892 },
    { state: "OK", count: 201 },
    { state: "CA", count: 156 },
    { state: "FL", count: 112 },
    { state: "LA", count: 89 },
  ],
};

export const DEMO_SYSTEM_INFO = {
  version: "1.0.0",
  hostname: "reposcan-jetson-01",
  platform: "Linux-5.15.136-aarch64-Jetson-Orin-Nano",
  timestamp: new Date().toISOString(),
};
