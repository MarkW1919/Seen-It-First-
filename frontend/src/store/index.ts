import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  User,
  Token,
  AppView,
  HotListAlert,
  Detection,
  CameraStatus,
} from "../types";

interface AppState {
  // Auth
  user: User | null;
  token: Token | null;
  setAuth: (user: User, token: Token) => void;
  logout: () => void;

  // Navigation
  activeView: AppView;
  setActiveView: (view: AppView) => void;

  // Live scan
  isScanning: boolean;
  setScanning: (scanning: boolean) => void;
  liveFeed: Detection[];
  addLiveDetection: (detection: Detection) => void;
  clearLiveFeed: () => void;

  // Alerts
  activeAlerts: HotListAlert[];
  addAlert: (alert: HotListAlert) => void;
  dismissAlert: (alertId: string) => void;
  clearAlerts: () => void;
  alertSoundEnabled: boolean;
  setAlertSoundEnabled: (enabled: boolean) => void;
  alertVibrationEnabled: boolean;
  setAlertVibrationEnabled: (enabled: boolean) => void;

  // Camera
  cameraStatus: CameraStatus;
  setCameraStatus: (status: CameraStatus) => void;

  // Settings
  darkMode: boolean;
  setDarkMode: (dark: boolean) => void;
  mapFollowGps: boolean;
  setMapFollowGps: (follow: boolean) => void;
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      // Auth
      user: null,
      token: null,
      setAuth: (user, token) => set({ user, token }),
      logout: () => set({ user: null, token: null }),

      // Navigation
      activeView: "scan",
      setActiveView: (view) => set({ activeView: view }),

      // Live scan
      isScanning: false,
      setScanning: (scanning) => set({ isScanning: scanning }),
      liveFeed: [],
      addLiveDetection: (detection) =>
        set((state) => ({
          liveFeed: [detection, ...state.liveFeed].slice(0, 100),
        })),
      clearLiveFeed: () => set({ liveFeed: [] }),

      // Alerts (with deduplication by alert ID)
      activeAlerts: [],
      addAlert: (alert) =>
        set((state) => {
          // Deduplicate: skip if an alert with this ID already exists
          if (state.activeAlerts.some((a) => a.id === alert.id)) {
            return state;
          }
          return {
            activeAlerts: [alert, ...state.activeAlerts].slice(0, 50),
          };
        }),
      dismissAlert: (alertId) =>
        set((state) => ({
          activeAlerts: state.activeAlerts.filter((a) => a.id !== alertId),
        })),
      clearAlerts: () => set({ activeAlerts: [] }),
      alertSoundEnabled: true,
      setAlertSoundEnabled: (enabled) => set({ alertSoundEnabled: enabled }),
      alertVibrationEnabled: true,
      setAlertVibrationEnabled: (enabled) =>
        set({ alertVibrationEnabled: enabled }),

      // Camera
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
      setCameraStatus: (status) => set({ cameraStatus: status }),

      // Settings
      darkMode: true,
      setDarkMode: (dark) => set({ darkMode: dark }),
      mapFollowGps: true,
      setMapFollowGps: (follow) => set({ mapFollowGps: follow }),
    }),
    {
      name: "reposcan-storage",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        darkMode: state.darkMode,
        alertSoundEnabled: state.alertSoundEnabled,
        alertVibrationEnabled: state.alertVibrationEnabled,
        mapFollowGps: state.mapFollowGps,
      }),
    }
  )
);
