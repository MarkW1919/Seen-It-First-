import { describe, it, expect } from "vitest";
import { api } from "./api";

describe("ApiClient", () => {
  describe("demo mode", () => {
    it("starts with demo mode disabled", () => {
      expect(api.isDemoMode).toBe(false);
    });

    it("toggles demo mode", () => {
      api.setDemoMode(true);
      expect(api.isDemoMode).toBe(true);
      api.setDemoMode(false);
      expect(api.isDemoMode).toBe(false);
    });

    it("returns demo data for login in demo mode", async () => {
      api.setDemoMode(true);
      const token = await api.login("demo@test.com", "password");
      expect(token).toHaveProperty("access_token");
      expect(token).toHaveProperty("refresh_token");
      api.setDemoMode(false);
    });

    it("returns demo user for getMe in demo mode", async () => {
      api.setDemoMode(true);
      const user = await api.getMe();
      expect(user).toHaveProperty("id");
      expect(user).toHaveProperty("email");
      expect(user).toHaveProperty("role");
      api.setDemoMode(false);
    });

    it("returns demo detections in demo mode", async () => {
      api.setDemoMode(true);
      const list = await api.getDetections();
      expect(list).toHaveProperty("items");
      expect(list).toHaveProperty("total");
      expect(Array.isArray(list.items)).toBe(true);
      api.setDemoMode(false);
    });

    it("returns hot list entries in demo mode", async () => {
      api.setDemoMode(true);
      const entries = await api.getHotListEntries();
      expect(Array.isArray(entries)).toBe(true);
      api.setDemoMode(false);
    });

    it("returns camera status in demo mode", async () => {
      api.setDemoMode(true);
      const status = await api.getCameraStatus();
      expect(status).toHaveProperty("is_connected");
      expect(status).toHaveProperty("fps");
      api.setDemoMode(false);
    });
  });
});
