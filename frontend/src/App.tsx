import { useState } from "react";
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
import { login } from "./services/auth";

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
      </div>
    </div>
  );
}

function AppContent() {
  const activeView = useAppStore((s) => s.activeView);

  // Connect WebSocket for real-time alerts
  useWebSocket();

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
