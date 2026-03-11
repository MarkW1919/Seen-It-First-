import { useEffect, useState, useCallback } from "react";
import type { RankedVehicle } from "../types/navigation";
import { VehicleDetectionCard } from "./VehicleDetectionCard";

const REFRESH_INTERVAL_MS = 3000;
const MAX_TARGETS = 10;

interface TargetsResponse {
  targets: RankedVehicle[];
  error?: string;
}

interface Props {
  /** When true (ARRIVED event received) the panel is visible and polling starts. */
  scanning: boolean;
  /** Optional static targets used for UI previews/demo mode. */
  previewTargets?: RankedVehicle[];
}

export function TargetList({ scanning, previewTargets }: Props) {
  const [vehicles, setVehicles] = useState<RankedVehicle[]>([]);
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  const fetchTargets = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    try {
      const res = await fetch("/navigation/targets", { signal });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TargetsResponse = await res.json();
      if (data.error) throw new Error(data.error);
      setVehicles(data.targets.slice(0, MAX_TARGETS));
      setError(null);
      const res = await fetch("/navigation/targets");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: TargetsResponse = await res.json();
      setVehicles((data.targets ?? []).slice(0, MAX_TARGETS));
      setError(data.error ?? null);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Fetch failed");
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll every 3 seconds while scanning
  useEffect(() => {
    if (!scanning) {
      setVehicles([]);
      setError(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    fetchTargets(controller.signal);

    const interval = setInterval(() => fetchTargets(controller.signal), REFRESH_INTERVAL_MS);
    return () => {
      controller.abort();
      clearInterval(interval);
    };
  }, [scanning, fetchTargets]);
    if (previewTargets && previewTargets.length > 0) {
      setVehicles(previewTargets.slice(0, MAX_TARGETS));
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    fetchTargets();

    const interval = setInterval(fetchTargets, REFRESH_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [scanning, fetchTargets, previewTargets]);

  if (!scanning) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
      {/* Scanning header */}
      <div style={{
        textAlign: "center",
        padding: "0.75rem",
        background: "rgba(30, 58, 138, 0.4)",
        border: "1px solid #1d4ed8",
        borderRadius: "12px",
      }}>
        <p style={{
          color: "#93c5fd",
          fontWeight: 600,
          fontSize: "0.8rem",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          margin: 0,
        }}>
          Scanning Vehicles at Destination
        </p>
      </div>

      {/* Section title */}
      <h2 style={{ color: "#fff", fontWeight: 700, fontSize: "1rem", margin: 0 }}>
        Potential Target Vehicles
      </h2>

      {/* Loading state */}
      {loading && vehicles.length === 0 && (
        <p style={{ color: "#94a3b8", fontSize: "0.8rem", textAlign: "center", padding: "1rem 0", margin: 0 }}>
          Searching for vehicles…
        </p>
      )}

      {/* Error */}
      {error && (
        <p style={{ color: "#f87171", fontSize: "0.8rem", textAlign: "center", padding: "0.5rem 0", margin: 0 }}>
          Error: {error}
        </p>
      )}

      {/* No results */}
      {!loading && !error && vehicles.length === 0 && (
        <p style={{ color: "#64748b", fontSize: "0.8rem", textAlign: "center", padding: "1rem 0", margin: 0 }}>
          No vehicles detected within range.
        </p>
      )}

      {/* Vehicle cards — top vehicle highlighted in red */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
        {vehicles.map((v, idx) => (
          <VehicleDetectionCard
            key={v.vehicle_id}
            vehicle={v}
            isTopTarget={idx === 0}
          />
        ))}
      </div>

      {vehicles.length > 0 && (
        <p style={{ color: "#475569", fontSize: "0.7rem", textAlign: "center", margin: 0 }}>
          Showing {vehicles.length} vehicle{vehicles.length !== 1 ? "s" : ""} · refreshes every 3 s
        </p>
      )}
    </div>
  );
}
