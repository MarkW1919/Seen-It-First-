import { useEffect, useState, useCallback } from "react";
import type { RankedVehicle } from "../types/navigation";
import { VehicleDetectionCard } from "./VehicleDetectionCard";

const TARGETS_ENDPOINT = "/navigation/targets";
const REFRESH_INTERVAL_MS = 3000;
const DEFAULT_MAX_TARGETS = 10;

interface TargetsResponse {
  targets: RankedVehicle[];
  error?: string;
}

interface Props {
  scanning: boolean;
  previewTargets?: RankedVehicle[];
  maxTargets?: number;
}

export function TargetList({ scanning, previewTargets, maxTargets = DEFAULT_MAX_TARGETS }: Props) {
  const [vehicles, setVehicles] = useState<RankedVehicle[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchTargets = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const res = await fetch(TARGETS_ENDPOINT, { signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TargetsResponse = await res.json();
      if (data.error) throw new Error(data.error);
      setVehicles(data.targets.slice(0, maxTargets));
      setError(null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Fetch failed");
    } finally {
      setLoading(false);
    }
  }, [maxTargets]);

  useEffect(() => {
    if (!scanning) {
      setVehicles([]);
      setError(null);
      setLoading(false);
      return;
    }

    if (previewTargets && previewTargets.length > 0) {
      setVehicles(previewTargets.slice(0, maxTargets));
      setLoading(false);
      setError(null);
      return;
    }

    const controller = new AbortController();
    fetchTargets(controller.signal);
    const interval = setInterval(() => fetchTargets(controller.signal), REFRESH_INTERVAL_MS);

    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [scanning, fetchTargets, previewTargets, maxTargets]);

  if (!scanning) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
      <div
        style={{
          textAlign: "center",
          padding: "10px",
          background: "rgba(30, 58, 138, 0.35)",
          border: "1px solid #1d4ed8",
          borderRadius: "10px",
        }}
      >
        <p
          style={{
            color: "#93c5fd",
            fontWeight: 700,
            fontSize: "0.78rem",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            margin: 0,
          }}
        >
          Scanning vehicles at destination
        </p>
      </div>

      <h3 style={{ color: "#e8edf5", fontWeight: 700, fontSize: "0.9rem", margin: 0 }}>
        Potential target vehicles
      </h3>

      {loading && vehicles.length === 0 && (
        <p style={{ color: "#94a3b8", fontSize: "0.8rem", textAlign: "center", padding: "0.75rem 0", margin: 0 }}>
          Searching for vehicles...
        </p>
      )}

      {error && (
        <p style={{ color: "#f87171", fontSize: "0.8rem", textAlign: "center", padding: "0.5rem 0", margin: 0 }}>
          Error: {error}
        </p>
      )}

      {!loading && !error && vehicles.length === 0 && (
        <p style={{ color: "#64748b", fontSize: "0.8rem", textAlign: "center", padding: "0.75rem 0", margin: 0 }}>
          No vehicles detected within range.
        </p>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {vehicles.map((vehicle, idx) => (
          <VehicleDetectionCard key={vehicle.vehicle_id} vehicle={vehicle} isTopTarget={idx === 0} />
        ))}
      </div>

      {vehicles.length > 0 && (
        <p style={{ color: "#475569", fontSize: "0.68rem", textAlign: "center", margin: 0 }}>
          Showing {vehicles.length} vehicle{vehicles.length !== 1 ? "s" : ""} | refreshes every 3s
        </p>
      )}
    </div>
  );
}
