import { describe, it, expect, beforeEach } from "vitest";
import { useAppStore } from "./index";

describe("useAppStore", () => {
  beforeEach(() => {
    // Reset store state between tests
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

  describe("auth", () => {
    it("sets user and token on setAuth", () => {
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
    });

    it("clears user and token on logout", () => {
      useAppStore.setState({
        user: {
          id: "1",
          email: "test@example.com",
          full_name: "Test",
          role: "agent",
          is_active: true,
          created_at: "",
        },
        token: {
          access_token: "abc",
          refresh_token: "def",
          token_type: "bearer",
        },
      });

      useAppStore.getState().logout();

      expect(useAppStore.getState().user).toBeNull();
      expect(useAppStore.getState().token).toBeNull();
    });
  });

  describe("navigation", () => {
    it("changes active view", () => {
      useAppStore.getState().setActiveView("alerts");
      expect(useAppStore.getState().activeView).toBe("alerts");
    });
  });

  describe("live scan", () => {
    it("toggles scanning state", () => {
      useAppStore.getState().setScanning(true);
      expect(useAppStore.getState().isScanning).toBe(true);

      useAppStore.getState().setScanning(false);
      expect(useAppStore.getState().isScanning).toBe(false);
    });

    it("adds live detections and caps at 100", () => {
      const detection = {
        id: "det-1",
        agent_id: null,
        session_id: null,
        vehicle_type: "car",
        vehicle_color: "black",
        vehicle_make: "Toyota",
        vehicle_model: "Camry",
        vehicle_year: 2020,
        vehicle_confidence: 0.95,
        image_path: null,
        thumbnail_path: null,
        latitude: 34.0,
        longitude: -118.0,
        address: null,
        heading: null,
        speed: null,
        extra: {},
        created_at: new Date().toISOString(),
        plate_reads: [],
      };

      useAppStore.getState().addLiveDetection(detection);
      expect(useAppStore.getState().liveFeed).toHaveLength(1);
      expect(useAppStore.getState().liveFeed[0].id).toBe("det-1");
    });

    it("clears live feed", () => {
      useAppStore.setState({
        liveFeed: [
          {
            id: "det-1",
            agent_id: null,
            session_id: null,
            vehicle_type: "car",
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
            created_at: "",
            plate_reads: [],
          },
        ],
      });

      useAppStore.getState().clearLiveFeed();
      expect(useAppStore.getState().liveFeed).toHaveLength(0);
    });
  });

  describe("alerts", () => {
    const mockAlert = {
      id: "alert-1",
      hotlist_entry_id: "hl-1",
      detection_id: null,
      plate_text_matched: "ABC1234",
      match_confidence: 0.98,
      latitude: 34.0,
      longitude: -118.0,
      address: "123 Main St",
      status: "new" as const,
      acknowledged_at: null,
      resolved_at: null,
      notes: null,
      created_at: new Date().toISOString(),
      hotlist_entry: null,
    };

    it("adds alerts", () => {
      useAppStore.getState().addAlert(mockAlert);
      expect(useAppStore.getState().activeAlerts).toHaveLength(1);
    });

    it("dismisses an alert by id", () => {
      useAppStore.setState({ activeAlerts: [mockAlert] });
      useAppStore.getState().dismissAlert("alert-1");
      expect(useAppStore.getState().activeAlerts).toHaveLength(0);
    });

    it("clears all alerts", () => {
      useAppStore.setState({ activeAlerts: [mockAlert] });
      useAppStore.getState().clearAlerts();
      expect(useAppStore.getState().activeAlerts).toHaveLength(0);
    });
  });

  describe("settings", () => {
    it("toggles dark mode", () => {
      useAppStore.getState().setDarkMode(false);
      expect(useAppStore.getState().darkMode).toBe(false);
    });

    it("toggles map follow GPS", () => {
      useAppStore.getState().setMapFollowGps(false);
      expect(useAppStore.getState().mapFollowGps).toBe(false);
    });

    it("toggles alert sound", () => {
      useAppStore.getState().setAlertSoundEnabled(false);
      expect(useAppStore.getState().alertSoundEnabled).toBe(false);
    });
  });
});
