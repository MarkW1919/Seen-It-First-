import { useAppStore } from "../store";
import { useCameraStatus, useCapture, useNightMode } from "../hooks/useCamera";
import DetectionCard from "./DetectionCard";

export default function LiveScanView() {
  const isScanning = useAppStore((s) => s.isScanning);
  const setScanning = useAppStore((s) => s.setScanning);
  const liveFeed = useAppStore((s) => s.liveFeed);
  const cameraStatus = useAppStore((s) => s.cameraStatus);
  const { data: camStatus } = useCameraStatus();
  const capture = useCapture();
  const nightMode = useNightMode();

  // Prefer API data when available, fall back to store (populated by demo mode)
  const currentStatus = camStatus ?? cameraStatus;

  return (
    <div className="flex flex-col h-full">
      {/* Camera feed area */}
      <div className="relative bg-black aspect-video max-h-[45vh] flex items-center justify-center">
        {currentStatus.is_connected ? (
          <div className="w-full h-full flex items-center justify-center text-slate-500">
            {/* In production, this would be an RTSP/MJPEG stream via <img> or <video> */}
            <div className="text-center">
              <svg
                className="w-16 h-16 mx-auto mb-2 text-slate-600"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
              <p className="text-sm">
                {currentStatus.resolution} @ {currentStatus.fps} FPS
              </p>
              {currentStatus.night_mode && (
                <p className="text-purple-400 text-xs mt-1">IR Night Vision Active</p>
              )}
            </div>
          </div>
        ) : (
          <div className="text-center text-slate-500">
            <svg
              className="w-16 h-16 mx-auto mb-2"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1}
                d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"
              />
            </svg>
            <p>Camera Not Connected</p>
          </div>
        )}

        {/* Overlay controls */}
        <div className="absolute bottom-3 left-3 right-3 flex items-center justify-between">
          <button
            onClick={() => nightMode.mutate(!currentStatus.night_mode)}
            className={`p-2 rounded-lg backdrop-blur ${
              currentStatus.night_mode
                ? "bg-purple-500/50 text-white"
                : "bg-black/50 text-slate-300"
            }`}
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
              <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
            </svg>
          </button>

          <button
            onClick={() => capture.mutate()}
            className="p-3 rounded-full bg-white/20 backdrop-blur border-2 border-white/50"
          >
            <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
              <path
                fillRule="evenodd"
                d="M4 5a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V7a2 2 0 00-2-2h-1.586a1 1 0 01-.707-.293l-1.121-1.121A2 2 0 0011.172 3H8.828a2 2 0 00-1.414.586L6.293 4.707A1 1 0 015.586 5H4zm6 9a3 3 0 100-6 3 3 0 000 6z"
                clipRule="evenodd"
              />
            </svg>
          </button>

          <div className="text-white bg-black/50 backdrop-blur rounded-lg px-2 py-1 text-xs">
            {currentStatus.fps.toFixed(0)} FPS
          </div>
        </div>
      </div>

      {/* Scan toggle */}
      <div className="p-4">
        <button
          onClick={() => setScanning(!isScanning)}
          className={`w-full py-4 rounded-xl font-bold text-lg transition-all ${
            isScanning
              ? "bg-danger-600 hover:bg-danger-500 text-white"
              : "bg-success-600 hover:bg-success-500 text-white"
          }`}
        >
          {isScanning ? "STOP SCANNING" : "START SCANNING"}
        </button>
      </div>

      {/* Live detection feed */}
      <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-2">
        <h3 className="text-sm font-medium text-slate-400 sticky top-0 bg-slate-900 py-1">
          Live Detections ({liveFeed.length})
        </h3>
        {liveFeed.length === 0 ? (
          <div className="text-center text-slate-600 py-8">
            {isScanning
              ? "Waiting for detections..."
              : "Start scanning to detect plates"}
          </div>
        ) : (
          liveFeed.map((detection) => (
            <DetectionCard key={detection.id} detection={detection} compact />
          ))
        )}
      </div>
    </div>
  );
}
