import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "./index";
import type { Detection, HotListAlert } from "../types";

function makeDetection(id: string): Detection {
  return {
    id,
    agent_id: null,
    session_id: null,
    vehicle_type: null,
    vehicle_color: null,
    vehicle_make: null,
    vehicle_model: null,
    vehicle_year: null,
    vehicle_confidence: null,
    image_path: null,
    thumbnail_path: null,
    latitude: null,
    longitude: null,
    address: null,
    heading: null,
    speed: null,
    extra: {},
    created_at: new Date().toISOString(),
    plate_reads: [],
  };
}

function makeAlert(id: string): HotListAlert {
  return {
    id,
    hotlist_entry_id: "entry-1",
    detection_id: null,
    plate_text_matched: "ABC1234",
    match_confidence: 0.95,
    latitude: null,
    longitude: null,
    address: null,
    status: "new",
    acknowledged_at: null,
    resolved_at: null,
    notes: null,
    created_at: new Date().toISOString(),
    hotlist_entry: null,
  };
}

describe("useAppStore", () => {
  beforeEach(() => {
    useAppStore.setState({
      user: null,
      token: null,
      activeView: "scan",
      isScanning: false,
      liveFeed: [],
      activeAlerts: [],
      alertSoundEnabled: true,
      alertVibrationEnabled: true,
      cameraStatus: {
        is_connected: false,
        resolution: "1920x1080",
        fps: 0,
        night_mode: false,
        ir_enabled: false,
        ptz_position: { pan: 0, tilt: 0, zoom: 1 },
        streaming: false,
        rtsp_url: null,
      },
      darkMode: true,
      mapFollowGps: true,
    });
  });

  describe("navigation", () => {
    it("sets active view", () => {
      useAppStore.getState().setActiveView("alerts");
      expect(useAppStore.getState().activeView).toBe("alerts");
    });
  });

  describe("scanning", () => {
    it("toggles scanning state", () => {
      useAppStore.getState().setScanning(true);
      expect(useAppStore.getState().isScanning).toBe(true);

      useAppStore.getState().setScanning(false);
      expect(useAppStore.getState().isScanning).toBe(false);
    });
  });

  describe("live feed", () => {
    it("adds detection to live feed", () => {
      const det = makeDetection("det-1");
      useAppStore.getState().addLiveDetection(det);
      expect(useAppStore.getState().liveFeed).toHaveLength(1);
      expect(useAppStore.getState().liveFeed[0].id).toBe("det-1");
    });

    it("prepends newest detection", () => {
      useAppStore.getState().addLiveDetection(makeDetection("det-1"));
      useAppStore.getState().addLiveDetection(makeDetection("det-2"));
      expect(useAppStore.getState().liveFeed[0].id).toBe("det-2");
      expect(useAppStore.getState().liveFeed[1].id).toBe("det-1");
    });

    it("caps feed at 100 items", () => {
      for (let i = 0; i < 105; i++) {
        useAppStore.getState().addLiveDetection(makeDetection(`det-${i}`));
      }
      expect(useAppStore.getState().liveFeed.length).toBeLessThanOrEqual(100);
    });

    it("clears live feed", () => {
      useAppStore.getState().addLiveDetection(makeDetection("det-1"));
      useAppStore.getState().clearLiveFeed();
      expect(useAppStore.getState().liveFeed).toHaveLength(0);
    });
  });

  describe("alerts", () => {
    it("adds alert", () => {
      useAppStore.getState().addAlert(makeAlert("alert-1"));
      expect(useAppStore.getState().activeAlerts).toHaveLength(1);
    });

    it("deduplicates alerts by ID", () => {
      useAppStore.getState().addAlert(makeAlert("alert-1"));
      useAppStore.getState().addAlert(makeAlert("alert-1"));
      expect(useAppStore.getState().activeAlerts).toHaveLength(1);
    });

    it("caps alerts at 50", () => {
      for (let i = 0; i < 55; i++) {
        useAppStore.getState().addAlert(makeAlert(`alert-${i}`));
      }
      expect(useAppStore.getState().activeAlerts.length).toBeLessThanOrEqual(50);
    });

    it("dismisses alert by ID", () => {
      useAppStore.getState().addAlert(makeAlert("alert-1"));
      useAppStore.getState().addAlert(makeAlert("alert-2"));
      useAppStore.getState().dismissAlert("alert-1");
      expect(useAppStore.getState().activeAlerts).toHaveLength(1);
      expect(useAppStore.getState().activeAlerts[0].id).toBe("alert-2");
    });

    it("clears all alerts", () => {
      useAppStore.getState().addAlert(makeAlert("alert-1"));
      useAppStore.getState().clearAlerts();
      expect(useAppStore.getState().activeAlerts).toHaveLength(0);
    });
  });

  describe("settings", () => {
    it("toggles alert sound", () => {
      useAppStore.getState().setAlertSoundEnabled(false);
      expect(useAppStore.getState().alertSoundEnabled).toBe(false);
    });

    it("toggles alert vibration", () => {
      useAppStore.getState().setAlertVibrationEnabled(false);
      expect(useAppStore.getState().alertVibrationEnabled).toBe(false);
    });

    it("toggles map follow GPS", () => {
      useAppStore.getState().setMapFollowGps(false);
      expect(useAppStore.getState().mapFollowGps).toBe(false);
    });

    it("toggles dark mode", () => {
      useAppStore.getState().setDarkMode(false);
      expect(useAppStore.getState().darkMode).toBe(false);
    });
  });

  describe("camera status", () => {
    it("updates camera status", () => {
      const newStatus = {
        is_connected: true,
        resolution: "1920x1080",
        fps: 30,
        night_mode: true,
        ir_enabled: true,
        ptz_position: { pan: 45, tilt: 10, zoom: 2 },
        streaming: true,
        rtsp_url: "rtsp://localhost:8554/stream",
      };
      useAppStore.getState().setCameraStatus(newStatus);
      expect(useAppStore.getState().cameraStatus.is_connected).toBe(true);
      expect(useAppStore.getState().cameraStatus.fps).toBe(30);
      expect(useAppStore.getState().cameraStatus.night_mode).toBe(true);
    });
  });

  describe("auth", () => {
    it("sets auth and clears on logout", () => {
      const user = {
        id: "1",
        email: "test@example.com",
        full_name: "Test User",
        role: "agent" as const,
        is_active: true,
        created_at: new Date().toISOString(),
      };
      const token = {
        access_token: "abc",
        refresh_token: "def",
        token_type: "bearer",
      };

      useAppStore.getState().setAuth(user, token);
      expect(useAppStore.getState().user).toEqual(user);
      expect(useAppStore.getState().token).toEqual(token);

      useAppStore.getState().logout();
      expect(useAppStore.getState().user).toBeNull();
      expect(useAppStore.getState().token).toBeNull();
    });
  });
});
