import React from "react";
import type { RankedVehicle } from "../types/navigation";

interface Props {
  vehicle: RankedVehicle;
  isTopTarget?: boolean;
}

function confidenceColor(conf: number): string {
  if (conf >= 0.85) return "#22c55e";
  if (conf >= 0.70) return "#eab308";
  return "#ef4444";
}

function capitalize(s: string): string {
  if (!s || s === "unknown") return "Unknown";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function VehicleDetectionCard({ vehicle, isTopTarget = false }: Props) {
  const borderStyle = isTopTarget
    ? "1px solid #ef4444"
    : "1px solid #1e293b";
  const shadow = isTopTarget
    ? "0 0 14px rgba(239,68,68,0.3)"
    : "none";

  return (
    <div
      style={{
        background: "#111827",
        border: borderStyle,
        borderRadius: "10px",
        padding: "0.75rem",
        color: "#e8edf5",
        boxShadow: shadow,
        animation: isTopTarget ? "border-pulse 2s ease-in-out infinite" : undefined,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
        <span style={{
          fontSize: "0.65rem",
          fontWeight: 700,
          color: "#64748b",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
        }}>
          Vehicle Detected
        </span>
        {vehicle.hotlist_match && <BadgeTag bg="#dc2626">HOTLIST</BadgeTag>}
        {isTopTarget && !vehicle.hotlist_match && <BadgeTag bg="#ea580c">TOP TARGET</BadgeTag>}
      </div>

      {/* Classification rows */}
      <Row label="Type" value={capitalize(vehicle.vehicle_type)} />
      <Row label="Make" value={capitalize(vehicle.make)} />
      <Row label="Model" value={capitalize(vehicle.model)} />
      <Row label="Color" value={capitalize(vehicle.color)} />
      <Row label="Year" value={vehicle.year_range === "unknown" ? "Unknown" : vehicle.year_range} />

      {/* Plate */}
      <Row
        label="Plate"
        value={vehicle.plate ?? "Not Detected"}
        valueColor={vehicle.plate ? "#fff" : "#64748b"}
        valueExtra={vehicle.plate
          ? { fontFamily: "'SF Mono', 'Fira Code', monospace", fontWeight: 800, letterSpacing: "0.05em" }
          : { fontStyle: "italic" as const }
        }
      />

      {/* Fingerprint */}
      {vehicle.fingerprint && (
        <Row
          label="ID"
          value={vehicle.fingerprint.length > 28 ? vehicle.fingerprint.slice(-12) : vehicle.fingerprint}
          valueColor="#64748b"
          valueExtra={{ fontFamily: "monospace", fontSize: "0.68rem" }}
        />
      )}

      {/* Divider */}
      <div style={{ borderTop: "1px solid #1e293b", margin: "6px 0" }} />

      {/* Scores */}
      <Row label="Confidence" value={vehicle.confidence.toFixed(2)} valueColor={confidenceColor(vehicle.confidence)} />
      <Row label="Distance" value={`${Math.round(vehicle.distance_ft)} ft`} />
      <Row label="Score" value={vehicle.score.toFixed(1)} valueColor="#60a5fa" valueExtra={{ fontWeight: 700 }} />
    </div>
  );
}

function Row({
  label, value, valueColor = "#e8edf5", valueExtra = {},
}: {
  label: string; value: string; valueColor?: string; valueExtra?: React.CSSProperties;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.78rem", lineHeight: "1.6" }}>
      <span style={{ color: "#94a3b8" }}>{label}:</span>
      <span style={{ color: valueColor, ...valueExtra }}>{value}</span>
    </div>
  );
}

function BadgeTag({ bg, children }: { bg: string; children: React.ReactNode }) {
  return (
    <span style={{
      fontSize: "0.6rem",
      background: bg,
      color: "#fff",
      padding: "2px 8px",
      borderRadius: "999px",
      fontWeight: 800,
      letterSpacing: "0.05em",
    }}>
      {children}
    </span>
  );
}
