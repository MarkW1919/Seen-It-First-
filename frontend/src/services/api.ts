import type {
  Detection,
  DetectionList,
  HotListEntry,
  HotListAlert,
  CameraStatus,
  Token,
  User,
} from "../types";

const BASE_URL = "/api";

class ApiClient {
  private token: string | null = null;

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
    return this.request("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name }),
    });
  }

  async refreshToken(refresh_token: string): Promise<Token> {
    return this.request("/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token }),
    });
  }

  async getMe(): Promise<User> {
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
    const query = new URLSearchParams();
    if (params?.page) query.set("page", String(params.page));
    if (params?.page_size) query.set("page_size", String(params.page_size));
    if (params?.session_id) query.set("session_id", params.session_id);
    if (params?.start_date) query.set("start_date", params.start_date);
    if (params?.end_date) query.set("end_date", params.end_date);
    return this.request(`/detections?${query}`);
  }

  async getDetection(id: string): Promise<Detection> {
    return this.request(`/detections/${id}`);
  }

  // ─── Search ───

  async searchPlate(
    q: string,
    exact?: boolean,
    page?: number
  ): Promise<DetectionList> {
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
    const query = new URLSearchParams({
      lat: String(lat),
      lng: String(lng),
    });
    if (radius) query.set("radius", String(radius));
    return this.request(`/search/nearby?${query}`);
  }

  // ─── Hot List ───

  async getHotListEntries(active_only?: boolean): Promise<HotListEntry[]> {
    const query = new URLSearchParams();
    if (active_only !== undefined) query.set("active_only", String(active_only));
    return this.request(`/hotlist/entries?${query}`);
  }

  async createHotListEntry(
    data: Partial<HotListEntry>
  ): Promise<HotListEntry> {
    return this.request("/hotlist/entries", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateHotListEntry(
    id: string,
    data: Partial<HotListEntry>
  ): Promise<HotListEntry> {
    return this.request(`/hotlist/entries/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  async deleteHotListEntry(id: string): Promise<void> {
    return this.request(`/hotlist/entries/${id}`, { method: "DELETE" });
  }

  async getAlerts(status?: string): Promise<HotListAlert[]> {
    const query = new URLSearchParams();
    if (status) query.set("status", status);
    return this.request(`/hotlist/alerts?${query}`);
  }

  async updateAlert(
    id: string,
    data: { status?: string; notes?: string }
  ): Promise<HotListAlert> {
    return this.request(`/hotlist/alerts/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  // ─── Plates ───

  async getRecentPlates(limit?: number) {
    const query = new URLSearchParams();
    if (limit) query.set("limit", String(limit));
    return this.request(`/plates/recent?${query}`);
  }

  async getPlateStats() {
    return this.request("/plates/stats");
  }

  // ─── Camera ───

  async getCameraStatus(): Promise<CameraStatus> {
    return this.request("/camera/status");
  }

  async sendPTZCommand(cmd: {
    pan?: number;
    tilt?: number;
    zoom?: number;
  }) {
    return this.request("/camera/ptz", {
      method: "POST",
      body: JSON.stringify(cmd),
    });
  }

  async toggleNightMode(enabled: boolean) {
    return this.request(`/camera/night-mode/${enabled}`, { method: "POST" });
  }

  async triggerCapture() {
    return this.request("/camera/capture", { method: "POST" });
  }

  // ─── System ───

  async getSystemInfo() {
    return this.request("/system/info");
  }

  async getSystemStats() {
    return this.request("/system/stats");
  }
}

export const api = new ApiClient();
