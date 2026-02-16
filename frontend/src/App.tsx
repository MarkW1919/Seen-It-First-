import { useState, useEffect, useRef } from "react";
import { useAppStore } from "./store";
import { useWebSocket } from "./hooks/useWebSocket";
import Layout from "./components/Layout";
import LiveScanView from "./components/LiveScanView";
import AlertPanel from "./components/AlertPanel";
import MapView from "./components/MapView";
import SearchPanel from "./components/SearchPanel";
import HistoryView from "./components/HistoryView";
import HotListManager from "./components/HotListManager";
import SettingsPanel from "./components/SettingsPanel";
import { login, loginDemo } from "./services/auth";
import { api } from "./services/api";
import { DEMO_DETECTIONS, DEMO_ALERTS, DEMO_CAMERA_STATUS } from "./services/mockData";

function LoginScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDemo = async () => {
    setLoading(true);
    setError("");
    try {
      await loginDemo();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo mode failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="card w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary-400">RepoScan Pro</h1>
          <p className="text-slate-400 mt-2">License Plate Recognition System</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="input"
            required
            autoComplete="email"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="input"
            required
            autoComplete="current-password"
          />

          {error && (
            <div className="text-danger-400 text-sm text-center">{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full text-lg"
          >
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-slate-700">
          <button
            onClick={handleDemo}
            disabled={loading}
            className="w-full py-3 rounded-xl font-medium text-sm
                       bg-slate-700 hover:bg-slate-600 text-slate-200
                       transition-colors border border-slate-600"
          >
            Enter Demo Mode
          </button>
          <p className="text-xs text-slate-500 text-center mt-2">
            Explore the full UI with sample data — no backend required
          </p>
        </div>
      </div>
    </div>
  );
}

/**
 * In demo mode, simulate a live scan feed by trickling in detections
 * and firing alerts with sound/vibration after a short delay.
 */
function useDemoSimulation() {
  const isScanning = useAppStore((s) => s.isScanning);
  const addLiveDetection = useAppStore((s) => s.addLiveDetection);
  const addAlert = useAppStore((s) => s.addAlert);
  const setCameraStatus = useAppStore((s) => s.setCameraStatus);
  const intervalRef = useRef<number>();

  useEffect(() => {
    if (!api.isDemoMode) return;

    // Set initial camera status for demo
    setCameraStatus(DEMO_CAMERA_STATUS);

    if (isScanning) {
      let idx = 0;
      intervalRef.current = window.setInterval(() => {
        if (idx < DEMO_DETECTIONS.length) {
          // Create a fresh detection with current timestamp
          const det = {
            ...DEMO_DETECTIONS[idx],
            id: `live-${Date.now()}-${idx}`,
            created_at: new Date().toISOString(),
          };
          addLiveDetection(det);

          // If this detection matches a hot list alert, fire it
          const matchingAlert = DEMO_ALERTS.find(
            (a) =>
              det.plate_reads.some((pr) => pr.plate_text === a.plate_text_matched)
          );
          if (matchingAlert) {
            addAlert({
              ...matchingAlert,
              id: `live-alert-${Date.now()}`,
              created_at: new Date().toISOString(),
            });
          }

          idx++;
        } else {
          idx = 0; // loop
        }
      }, 3000);
    }

    return () => {
      clearInterval(intervalRef.current);
    };
  }, [isScanning, addLiveDetection, addAlert, setCameraStatus]);
}

function AppContent() {
  const activeView = useAppStore((s) => s.activeView);

  // Connect WebSocket for real-time alerts (no-op in demo mode since no backend)
  useWebSocket();

  // Simulate live detections in demo mode
  useDemoSimulation();

  const renderView = () => {
    switch (activeView) {
      case "scan":
        return <LiveScanView />;
      case "alerts":
        return <AlertPanel />;
      case "map":
        return <MapView />;
      case "search":
        return <SearchPanel />;
      case "history":
        return <HistoryView />;
      case "hotlist":
        return <HotListManager />;
      case "settings":
        return <SettingsPanel />;
      default:
        return <LiveScanView />;
    }
  };

  return <Layout>{renderView()}</Layout>;
}

export default function App() {
  const user = useAppStore((s) => s.user);

  if (!user) {
    return <LoginScreen />;
  }

  return <AppContent />;
}
