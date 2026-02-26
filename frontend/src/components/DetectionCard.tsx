import type { Detection } from "../types";
import { formatVehicleDescription } from "../utils/format";
import PlateDisplay from "./PlateDisplay";

interface DetectionCardProps {
  detection: Detection;
  compact?: boolean;
  isAlert?: boolean;
  onClick?: () => void;
}

export default function DetectionCard({
  detection,
  compact = false,
  isAlert = false,
  onClick,
}: DetectionCardProps) {
  const plate = detection.plate_reads[0];
  const vehicleDesc = formatVehicleDescription(detection);

  const timeStr = new Date(detection.created_at).toLocaleTimeString();
  const dateStr = new Date(detection.created_at).toLocaleDateString();

  if (compact) {
    return (
      <button
        onClick={onClick}
        className={`card w-full text-left flex items-center gap-3 ${isAlert ? "border-danger-500 bg-danger-500/10" : ""}`}
      >
        {plate && (
          <PlateDisplay
            plateText={plate.plate_text}
            state={plate.plate_state}
            confidence={plate.confidence}
            isAlert={isAlert}
            size="sm"
          />
        )}
        <div className="flex-1 min-w-0">
          {vehicleDesc && (
            <p className="text-sm text-slate-300 truncate">{vehicleDesc}</p>
          )}
          <p className="text-xs text-slate-500">{timeStr}</p>
        </div>
        {detection.latitude && (
          <svg
            className="w-4 h-4 text-slate-500 shrink-0"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
              clipRule="evenodd"
            />
          </svg>
        )}
      </button>
    );
  }

  return (
    <div
      className={`card ${isAlert ? "border-danger-500 bg-danger-500/10" : ""}`}
    >
      <div className="flex items-start justify-between gap-4">
        <div>
          {plate && (
            <PlateDisplay
              plateText={plate.plate_text}
              state={plate.plate_state}
              confidence={plate.confidence}
              isAlert={isAlert}
              size="md"
            />
          )}
        </div>
        <div className="text-right text-xs text-slate-500">
          <div>{dateStr}</div>
          <div>{timeStr}</div>
        </div>
      </div>

      {vehicleDesc && (
        <p className="mt-3 text-sm text-slate-300">{vehicleDesc}</p>
      )}

      {detection.address && (
        <p className="mt-1 text-xs text-slate-500 flex items-center gap-1">
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path
              fillRule="evenodd"
              d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z"
              clipRule="evenodd"
            />
          </svg>
          {detection.address}
        </p>
      )}

      {detection.speed !== null && (
        <p className="mt-1 text-xs text-slate-500">
          {detection.speed.toFixed(0)} mph
          {detection.heading !== null && ` · heading ${detection.heading.toFixed(0)}°`}
        </p>
      )}

      {/* Additional plate reads */}
      {detection.plate_reads.length > 1 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {detection.plate_reads.slice(1).map((pr) => (
            <PlateDisplay
              key={pr.id}
              plateText={pr.plate_text}
              state={pr.plate_state}
              confidence={pr.confidence}
              size="sm"
            />
          ))}
        </div>
      )}
    </div>
  );
}
