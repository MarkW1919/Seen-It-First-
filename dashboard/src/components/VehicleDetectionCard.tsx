import React from "react";
import { RankedVehicle } from "../types/navigation";

interface Props {
  vehicle: RankedVehicle;
  isTopTarget?: boolean;
}

function confidenceColor(conf: number): string {
  if (conf >= 0.85) return "text-green-400";
  if (conf >= 0.70) return "text-yellow-400";
  return "text-red-400";
}

export function VehicleDetectionCard({ vehicle, isTopTarget = false }: Props) {
  const borderClass = isTopTarget
    ? "border-red-500 shadow-red-500/30 shadow-lg"
    : "border-gray-700";

  return (
    <div
      className={`rounded-xl bg-gray-900 text-white p-4 border ${borderClass} space-y-1`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-gray-300 uppercase tracking-wide">
          Vehicle Detected
        </span>
        {vehicle.hotlist_match && (
          <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded-full font-bold">
            HOTLIST
          </span>
        )}
        {isTopTarget && !vehicle.hotlist_match && (
          <span className="text-xs bg-orange-600 text-white px-2 py-0.5 rounded-full font-bold">
            TOP TARGET
          </span>
        )}
      </div>

      {/* Classification fields */}
      <Row label="Type"   value={capitalize(vehicle.vehicle_type)} />
      <Row label="Make"   value={capitalize(vehicle.make)}  />
      <Row label="Model"  value={capitalize(vehicle.model)} />
      <Row label="Color"  value={capitalize(vehicle.color)} />
      <Row label="Year"   value={vehicle.year_range}        />

      {/* Plate */}
      <Row
        label="Plate"
        value={vehicle.plate ?? "Not Detected"}
        valueClass={vehicle.plate ? "text-white font-mono font-bold" : "text-gray-500 italic"}
      />

      {/* Scores */}
      <div className="pt-2 border-t border-gray-700 space-y-1">
        <Row
          label="Confidence"
          value={vehicle.confidence.toFixed(2)}
          valueClass={confidenceColor(vehicle.confidence)}
        />
        <Row label="Distance" value={`${Math.round(vehicle.distance_ft)} ft`} />
        <Row label="Score"    value={vehicle.score.toFixed(1)}            />
      </div>
    </div>
  );
}

function Row({
  label,
  value,
  valueClass = "text-white",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-400">{label}:</span>
      <span className={valueClass}>{value}</span>
    </div>
  );
}

function capitalize(s: string): string {
  if (!s || s === "unknown") return "Unknown";
  return s.charAt(0).toUpperCase() + s.slice(1);
}
