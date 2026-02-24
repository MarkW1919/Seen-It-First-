import type {
  Detection,
  DetectionList,
  HotListEntry,
  HotListAlert,
  CameraStatus,
  Token,
  User,
} from "../types";
import {
  DEMO_USER,
  DEMO_TOKEN,
  DEMO_DETECTION_LIST,
  DEMO_DETECTIONS,
  DEMO_HOTLIST,
  DEMO_ALERTS,
  DEMO_CAMERA_STATUS,
  DEMO_PLATE_STATS,
  DEMO_SYSTEM_INFO,
} from "./mockData";

const BASE_URL = "/api";

class ApiClient {
  private token: string | null = null;
  private _demoMode = false;

  // In-memory demo state
  private _demoHotlist = [...DEMO_HOTLIST];
  private _demoAlerts = [...DEMO_ALERTS];
  private _demoCameraStatus = { ...DEMO_CAMERA_STATUS };

  get isDemoMode() {
    return this._demoMode;
  }

  setDemoMode(enabled: boolean) {
    this._demoMode = enabled;
  }

  setToken(token: string | null) {
    this.token = token;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers["Authorization"] = `Bearer ${this.token}`;
    }

    const res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(error.detail || `HTTP ${res.status}`);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  }

  // ─── Auth ───

  async login(email: string, password: string): Promise<Token> {
    if (this._demoMode) {
      await delay(300);
      return DEMO_TOKEN;
    }
    return this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  }

  async register(
    email: string,
    password: string,
    full_name: string
  ): Promise<User> {
    if (this._demoMode) {
      await delay(300);
      return { ...DEMO_USER, email, full_name };
    }
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    });
  }

  async refreshToken(refresh_token: string): Promise<Token> {
    if (this._demoMode) return DEMO_TOKEN;
    return this.request("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    });
  }

  async getMe(): Promise<User> {
    if (this._demoMode) return DEMO_USER;
    return this.request("/auth/me");
  }

  // ─── Detections ───

  async getDetections(params?: {
    page?: number;
    page_size?: number;
    session_id?: string;
    start_date?: string;
    end_date?: string;
  }): Promise<DetectionList> {
    if (this._demoMode) {
      await delay(200);
      return DEMO_DETECTION_LIST;
    }
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (params?.session_id) query.set("session_id", params.session_id);
    if (params?.start_date) query.set("start_date", params.start_date);
    if (params?.end_date) query.set("end_date", params.end_date);
    return this.request(`/detections?${query}`);
  }

  async getDetection(id: string): Promise<Detection> {
    if (this._demoMode) {
      await delay(150);
      return DEMO_DETECTIONS.find((d) => d.id === id) || DEMO_DETECTIONS[0];
    }
    return this.request(`/detections/${id}`);
  }

  // ─── Search ───

  async searchPlate(
    q: string,
    exact?: boolean,
    page?: number
  ): Promise<DetectionList> {
    if (this._demoMode) {
      await delay(300);
      const upper = q.toUpperCase();
      const filtered = DEMO_DETECTIONS.filter((d) =>
        d.plate_reads.some((pr) =>
          exact
            ? pr.plate_text === upper
            : pr.plate_text.includes(upper)
        )
      );
      return {
        items: filtered,
        total: filtered.length,
        page: 1,
        page_size: 50,
      };
    }
    const query = new URLSearchParams({ q });
    if (exact) query.set("exact", "true");
    if (page) query.set("page", String(page));
    return this.request(`/search/plate?${query}`);
  }

  async searchNearby(
    lat: number,
    lng: number,
    radius?: number
  ): Promise<DetectionList> {
    if (this._demoMode) {
      await delay(200);
      return DEMO_DETECTION_LIST;
    }
    const query = new URLSearchParams({
      lat: String(lat),
      lng: String(lng),
    });
    if (radius) query.set("radius", String(radius));
    return this.request(`/search/nearby?${query}`);
  }

  // ─── Hot List ───

  async getHotListEntries(active_only?: boolean): Promise<HotListEntry[]> {
    if (this._demoMode) {
      await delay(200);
      return active_only !== false
        ? this._demoHotlist.filter((e) => e.is_active)
        : this._demoHotlist;
    }
    const query = new URLSearchParams();
    if (active_only !== undefined) query.set("active_only", String(active_only));
    return this.request(`/hotlist/entries?${query}`);
  }

  async createHotListEntry(
    data: Partial<HotListEntry>
  ): Promise<HotListEntry> {
    if (this._demoMode) {
      await delay(300);
      const entry: HotListEntry = {
        id: `hl-${Date.now()}`,
        plate_text: data.plate_text || "",
        plate_state: data.plate_state || null,
        case_number: data.case_number || null,
        lender_name: data.lender_name || null,
        order_type: data.order_type || "repossession",
        vehicle_year: data.vehicle_year || null,
        vehicle_make: data.vehicle_make || null,
        vehicle_model: data.vehicle_model || null,
        vehicle_color: data.vehicle_color || null,
        vin: data.vin || null,
        debtor_name: data.debtor_name || null,
        debtor_address: data.debtor_address || null,
        is_active: true,
        priority: data.priority || "normal",
        notes: data.notes || null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        expires_at: null,
      };
      this._demoHotlist.unshift(entry);
      return entry;
    }
    return this.request("/hotlist/entries", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateHotListEntry(
    id: string,
    data: Partial<HotListEntry>
  ): Promise<HotListEntry> {
    if (this._demoMode) {
      await delay(200);
      const idx = this._demoHotlist.findIndex((e) => e.id === id);
      if (idx >= 0) {
        this._demoHotlist[idx] = { ...this._demoHotlist[idx], ...data } as HotListEntry;
        return this._demoHotlist[idx];
      }
      return this._demoHotlist[0];
    }
    return this.request(`/hotlist/entries/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteHotListEntry(id: string): Promise<void> {
    if (this._demoMode) {
      await delay(200);
      this._demoHotlist = this._demoHotlist.filter((e) => e.id !== id);
      return;
    }
    return this.request(`/hotlist/entries/${id}`, { method: "DELETE" });
  }

  async getAlerts(status?: string): Promise<HotListAlert[]> {
    if (this._demoMode) {
      await delay(200);
      return status
        ? this._demoAlerts.filter((a) => a.status === status)
        : this._demoAlerts;
    }
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    return this.request(`/hotlist/alerts?${query}`);
  }

  async updateAlert(
    id: string,
    data: { status?: string; notes?: string }
  ): Promise<HotListAlert> {
    if (this._demoMode) {
      await delay(200);
      const idx = this._demoAlerts.findIndex((a) => a.id === id);
      if (idx >= 0) {
        if (data.status) this._demoAlerts[idx] = { ...this._demoAlerts[idx], status: data.status as HotListAlert["status"] };
        if (data.notes !== undefined) this._demoAlerts[idx] = { ...this._demoAlerts[idx], notes: data.notes };
        return this._demoAlerts[idx];
      }
      return this._demoAlerts[0];
    }
    return this.request(`/hotlist/alerts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  // ─── Plates ───

  async getRecentPlates(limit?: number) {
    if (this._demoMode) {
      await delay(150);
      return DEMO_DETECTIONS.flatMap((d) => d.plate_reads).slice(0, limit || 100);
    }
    const query = new URLSearchParams();
    if (limit) query.set("limit", String(limit));
    return this.request(`/plates/recent?${query}`);
  }

  async getPlateStats() {
    if (this._demoMode) {
      await delay(150);
      return DEMO_PLATE_STATS;
    }
    return this.request("/plates/stats");
  }

  // ─── Camera ───

  async getCameraStatus(): Promise<CameraStatus> {
    if (this._demoMode) {
      // Simulate fluctuating FPS
      return {
        ...this._demoCameraStatus,
        fps: 27 + Math.random() * 3,
      };
    }
    return this.request("/camera/status");
  }

  async sendPTZCommand(cmd: {
    pan?: number;
    tilt?: number;
    zoom?: number;
    speed?: number;
  }) {
    // Client-side boundary enforcement (matches backend/camera limits)
    const PTZ_LIMITS = {
      PAN_MIN: -180, PAN_MAX: 180,
      TILT_MIN: -70, TILT_MAX: 70,
      ZOOM_MIN: 1, ZOOM_MAX: 30,
    };

    const validated = { ...cmd };
    if (validated.pan !== undefined) {
      // Wrap pan to [-180, 180] for 360° range
      while (validated.pan > PTZ_LIMITS.PAN_MAX) validated.pan -= 360;
      while (validated.pan < PTZ_LIMITS.PAN_MIN) validated.pan += 360;
    }
    if (validated.tilt !== undefined) {
      validated.tilt = Math.max(PTZ_LIMITS.TILT_MIN, Math.min(PTZ_LIMITS.TILT_MAX, validated.tilt));
    }
    if (validated.zoom !== undefined) {
      validated.zoom = Math.max(PTZ_LIMITS.ZOOM_MIN, Math.min(PTZ_LIMITS.ZOOM_MAX, validated.zoom));
    }
    if (validated.speed !== undefined) {
      validated.speed = Math.max(0, Math.min(1, validated.speed));
    }

    if (this._demoMode) {
      await delay(200);
      if (validated.pan !== undefined) this._demoCameraStatus.ptz_position.pan = validated.pan;
      if (validated.tilt !== undefined) this._demoCameraStatus.ptz_position.tilt = validated.tilt;
      if (validated.zoom !== undefined) this._demoCameraStatus.ptz_position.zoom = validated.zoom;
      return { status: "ok", position: this._demoCameraStatus.ptz_position };
    }
    return this.request("/camera/ptz", {
      method: "POST",
      body: JSON.stringify(validated),
    });
  }

  async toggleNightMode(enabled: boolean) {
    if (this._demoMode) {
      await delay(200);
      this._demoCameraStatus.night_mode = enabled;
      this._demoCameraStatus.ir_enabled = enabled;
      return { night_mode: enabled, ir_enabled: enabled };
    }
    return this.request(`/camera/night-mode/${enabled}`, { method: "POST" });
  }

  async triggerCapture() {
    if (this._demoMode) {
      await delay(100);
      return { status: "captured", message: "Demo frame captured" };
    }
    return this.request("/camera/capture", { method: "POST" });
  }

  // ─── System ───

  async getSystemInfo() {
    if (this._demoMode) return DEMO_SYSTEM_INFO;
    return this.request("/system/info");
  }

  async getSystemStats() {
    if (this._demoMode) {
      return {
        cpu_percent: 35 + Math.random() * 20,
        memory_used_mb: 3600 + Math.random() * 400,
        memory_total_mb: 8192,
        disk_used_gb: 124,
        disk_total_gb: 953,
        gpu_temp_c: 48 + Math.random() * 10,
        gpu_utilization: 60 + Math.random() * 20,
      };
    }
    return this.request("/system/stats");
  }
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

export const api = new ApiClient();
