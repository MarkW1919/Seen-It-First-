import { useAppStore } from "../store";
import { logout } from "../services/auth";
import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";

function Toggle({
  label,
  description,
  enabled,
  onChange,
}: {
  label: string;
  description?: string;
  enabled: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="text-sm font-medium text-slate-200">{label}</p>
        {description && (
          <p className="text-xs text-slate-500">{description}</p>
        )}
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={`relative w-12 h-7 rounded-full transition-colors ${
          enabled ? "bg-primary-600" : "bg-slate-600"
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-6 h-6 rounded-full bg-white transition-transform ${
            enabled ? "translate-x-5" : ""
          }`}
        />
      </button>
    </div>
  );
}

export default function SettingsPanel() {
  const user = useAppStore((s) => s.user);
  const alertSoundEnabled = useAppStore((s) => s.alertSoundEnabled);
  const setAlertSoundEnabled = useAppStore((s) => s.setAlertSoundEnabled);
  const alertVibrationEnabled = useAppStore((s) => s.alertVibrationEnabled);
  const setAlertVibrationEnabled = useAppStore((s) => s.setAlertVibrationEnabled);
  const mapFollowGps = useAppStore((s) => s.mapFollowGps);
  const setMapFollowGps = useAppStore((s) => s.setMapFollowGps);

  const { data: systemInfo } = useQuery({
    queryKey: ["system", "info"],
    queryFn: () => api.getSystemInfo(),
  });

  return (
    <div className="h-full overflow-y-auto">
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-bold">Settings</h2>
      </div>

      <div className="p-4 space-y-6">
        {/* Profile */}
        <section>
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-2">
            Profile
          </h3>
          <div className="card">
            <p className="text-lg font-medium">{user?.full_name}</p>
            <p className="text-sm text-slate-400">{user?.email}</p>
            <p className="text-xs text-slate-500 mt-1">
              Role: {user?.role?.toUpperCase()}
            </p>
          </div>
        </section>

        {/* Alerts */}
        <section>
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-2">
            Alerts
          </h3>
          <div className="card divide-y divide-slate-700">
            <Toggle
              label="Alert Sound"
              description="Play sound when hot list match detected"
              enabled={alertSoundEnabled}
              onChange={setAlertSoundEnabled}
            />
            <Toggle
              label="Vibration"
              description="Vibrate device on hot list match"
              enabled={alertVibrationEnabled}
              onChange={setAlertVibrationEnabled}
            />
          </div>
        </section>

        {/* Map */}
        <section>
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-2">
            Map
          </h3>
          <div className="card divide-y divide-slate-700">
            <Toggle
              label="Follow GPS"
              description="Auto-center map on your location"
              enabled={mapFollowGps}
              onChange={setMapFollowGps}
            />
          </div>
        </section>

        {/* System Info */}
        <section>
          <h3 className="text-sm font-medium text-slate-400 uppercase tracking-wider mb-2">
            System
          </h3>
          <div className="card text-sm space-y-2">
            <div className="flex justify-between">
              <span className="text-slate-400">Version</span>
              <span>
                {(systemInfo as { version?: string })?.version || "1.0.0"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Platform</span>
              <span className="text-xs">
                {(systemInfo as { platform?: string })?.platform || "---"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Hostname</span>
              <span>
                {(systemInfo as { hostname?: string })?.hostname || "---"}
              </span>
            </div>
          </div>
        </section>

        {/* Logout */}
        <button
          onClick={() => {
            if (confirm("Sign out of RepoScan Pro?")) {
              logout();
            }
          }}
          className="btn-danger w-full"
        >
          Sign Out
        </button>

        <p className="text-center text-xs text-slate-600 pb-4">
          RepoScan Pro v1.0.0
        </p>
      </div>
    </div>
  );
}
