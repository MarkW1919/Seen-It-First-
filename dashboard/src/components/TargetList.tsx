import React, { useEffect, useState, useCallback } from "react";
import { RankedVehicle } from "../types/navigation";
import { VehicleDetectionCard } from "./VehicleDetectionCard";

const API_BASE = "http://localhost:8080";
const REFRESH_INTERVAL_MS = 3000;
const MAX_TARGETS = 10;

interface TargetsResponse {
  targets: RankedVehicle[];
}

interface Props {
  /** When true (ARRIVED event received) the panel is visible and polling starts. */
  scanning: boolean;
}

export function TargetList({ scanning }: Props) {
  const [vehicles, setVehicles] = useState<RankedVehicle[]>([]);
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  const fetchTargets = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/navigation/targets`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TargetsResponse = await res.json();
      setVehicles(data.targets.slice(0, MAX_TARGETS));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fetch failed");
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll every 3 seconds while scanning
  useEffect(() => {
    if (!scanning) {
      setVehicles([]);
      return;
    }

    setLoading(true);
    fetchTargets();

    const interval = setInterval(fetchTargets, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [scanning, fetchTargets]);

  if (!scanning) return null;

  return (
    <div className="space-y-4">
      {/* Scanning header */}
      <div className="text-center py-3 bg-blue-900/40 border border-blue-700 rounded-xl">
        <p className="text-blue-300 font-semibold text-sm tracking-wide uppercase">
          Scanning Vehicles at Destination
        </p>
      </div>

      {/* Section title */}
      <h2 className="text-white font-bold text-lg">
        Potential Target Vehicles
      </h2>

      {/* Loading state */}
      {loading && vehicles.length === 0 && (
        <p className="text-gray-400 text-sm text-center py-4">
          Searching for vehicles…
        </p>
      )}

      {/* Error */}
      {error && (
        <p className="text-red-400 text-sm text-center py-2">
          Error: {error}
        </p>
      )}

      {/* No results */}
      {!loading && !error && vehicles.length === 0 && (
        <p className="text-gray-500 text-sm text-center py-4">
          No vehicles detected within range.
        </p>
      )}

      {/* Vehicle cards — top vehicle highlighted in red */}
      <div className="space-y-3">
        {vehicles.map((v, idx) => (
          <VehicleDetectionCard
            key={v.vehicle_id}
            vehicle={v}
            isTopTarget={idx === 0}
          />
        ))}
      </div>

      {vehicles.length > 0 && (
        <p className="text-gray-600 text-xs text-center">
          Showing {vehicles.length} vehicle{vehicles.length !== 1 ? "s" : ""} · refreshes every 3 s
        </p>
      )}
    </div>
  );
}
