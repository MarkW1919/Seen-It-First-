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
  const borderColor = isTopTarget ? "#ef4444" : "#334155";
  const shadowStyle = isTopTarget ? "0 0 12px rgba(239,68,68,0.3)" : "none";

  return (
    <div
      style={{
        background: "#111827",
        border: `1px solid ${borderColor}`,
        borderRadius: "12px",
        padding: "0.875rem",
        color: "#e2e8f0",
        boxShadow: shadowStyle,
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
        <span style={{ fontSize: "0.7rem", fontWeight: 600, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          Vehicle Detected
        </span>
        {vehicle.hotlist_match && (
          <span style={badgeStyle("#dc2626")}>HOTLIST</span>
        )}
        {isTopTarget && !vehicle.hotlist_match && (
          <span style={badgeStyle("#ea580c")}>TOP TARGET</span>
        )}
      </div>

      {/* Classification */}
      <Row label="Type"  value={capitalize(vehicle.vehicle_type)} />
      <Row label="Make"  value={capitalize(vehicle.make)} />
      <Row label="Model" value={capitalize(vehicle.model)} />
      <Row label="Color" value={capitalize(vehicle.color)} />
      <Row label="Year"  value={vehicle.year_range === "unknown" ? "Unknown" : vehicle.year_range} />

      {/* Plate */}
      <Row
        label="Plate"
        value={vehicle.plate ?? "Not Detected"}
        valueColor={vehicle.plate ? "#fff" : "#64748b"}
        valueExtra={vehicle.plate ? { fontFamily: "monospace", fontWeight: 700 } : { fontStyle: "italic" as const }}
      />

      {/* Fingerprint (last 12 chars) */}
      {vehicle.fingerprint && (
        <Row
          label="ID"
          value={vehicle.fingerprint.length > 28 ? vehicle.fingerprint.slice(-12) : vehicle.fingerprint}
          valueColor="#64748b"
          valueExtra={{ fontFamily: "monospace", fontSize: "0.7rem" }}
        />
      )}

      {/* Divider */}
      <div style={{ borderTop: "1px solid #1f2937", margin: "0.4rem 0" }} />

      {/* Scores */}
      <Row label="Confidence" value={vehicle.confidence.toFixed(2)} valueColor={confidenceColor(vehicle.confidence)} />
      <Row label="Distance"   value={`${Math.round(vehicle.distance_ft)} ft`} />
      <Row label="Score"       value={vehicle.score.toFixed(1)} valueColor="#60a5fa" valueExtra={{ fontWeight: 700 }} />
    </div>
  );
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */

function Row({
  label,
  value,
  valueColor = "#e2e8f0",
  valueExtra = {},
}: {
  label: string;
  value: string;
  valueColor?: string;
  valueExtra?: React.CSSProperties;
}) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.8rem", lineHeight: "1.6" }}>
      <span style={{ color: "#94a3b8" }}>{label}:</span>
      <span style={{ color: valueColor, ...valueExtra }}>{value}</span>
    </div>
  );
}

function badgeStyle(bg: string): React.CSSProperties {
  return {
    fontSize: "0.65rem",
    background: bg,
    color: "#fff",
    padding: "0.15rem 0.5rem",
    borderRadius: "999px",
    fontWeight: 700,
    letterSpacing: "0.04em",
  };
}
