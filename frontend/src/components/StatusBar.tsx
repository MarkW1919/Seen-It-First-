import { useAppStore } from "../store";
import { useGeolocation } from "../hooks/useGeolocation";

export default function StatusBar() {
  const cameraStatus = useAppStore((s) => s.cameraStatus);
  const isScanning = useAppStore((s) => s.isScanning);
  const { position } = useGeolocation();

  return (
    <div className="bg-slate-800 border-b border-slate-700 px-4 py-2 flex items-center justify-between text-xs safe-area-top">
      {/* Left: scanning status */}
      <div className="flex items-center gap-2">
        <span
          className={`w-2 h-2 rounded-full ${isScanning ? "bg-success-400 animate-pulse" : "bg-slate-500"}`}
        />
        <span className="text-slate-300">
          {isScanning ? "SCANNING" : "IDLE"}
        </span>
      </div>

      {/* Center: camera info */}
      <div className="flex items-center gap-3 text-slate-400">
        <span
          className={
            cameraStatus.is_connected ? "text-success-400" : "text-danger-400"
          }
        >
          CAM {cameraStatus.is_connected ? "OK" : "OFF"}
        </span>
        {cameraStatus.is_connected && (
          <span>{cameraStatus.fps.toFixed(0)} FPS</span>
        )}
        {cameraStatus.night_mode && (
          <span className="text-purple-400">IR</span>
        )}
      </div>

      {/* Right: GPS */}
      <div className="flex items-center gap-1 text-slate-400">
        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
          <path
            fillRule="evenodd"
            d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
            clipRule="evenodd"
          />
        </svg>
        {position ? (
          <span className="text-success-400">GPS</span>
        ) : (
          <span className="text-danger-400">NO GPS</span>
        )}
      </div>
    </div>
  );
}
