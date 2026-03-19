import { useState, type CSSProperties } from "react";

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------
const HOTLIST_ALERTS = [
  {
    id: "hl-001",
    plate: "8ABC123",
    level: "HIGH" as const,
    reason: "Stolen Vehicle",
    time: "2 min ago",
    camera: "Gate North",
    make: "Ford",
    model: "Explorer",
    color: "Black",
    year: "2019-2022",
    notes: "Subject considered armed. Do not approach without backup.",
  },
  {
    id: "hl-002",
    plate: "4KJX998",
    level: "MED" as const,
    reason: "BOLO Match",
    time: "11 min ago",
    camera: "Lot East",
    make: "Toyota",
    model: "Camry",
    color: "Silver",
    year: "2018-2021",
    notes: "Skip trace confirmed. Owner cooperative on prior recovery.",
  },
  {
    id: "hl-003",
    plate: "7TQF201",
    level: "HIGH" as const,
    reason: "Felony Warrant",
    time: "18 min ago",
    camera: "Main Entry",
    make: "Chevrolet",
    model: "Tahoe",
    color: "White",
    year: "2020-2023",
    notes: "Lien holder: First National Bank. 90+ days delinquent.",
  },
  {
    id: "hl-004",
    plate: "2WNB847",
    level: "LOW" as const,
    reason: "Expired Registration",
    time: "42 min ago",
    camera: "Street Cam 1",
    make: "Honda",
    model: "Civic",
    color: "Blue",
    year: "2016-2018",
    notes: "Low priority. Flag and log only.",
  },
];

type AlertLevel = "HIGH" | "MED" | "LOW";

function levelColor(level: AlertLevel): string {
  if (level === "HIGH") return "#ef4444";
  if (level === "MED") return "#f59e0b";
  return "#64748b";
}

function levelBg(level: AlertLevel): string {
  if (level === "HIGH") return "rgba(239,68,68,0.12)";
  if (level === "MED") return "rgba(245,158,11,0.08)";
  return "rgba(100,116,139,0.08)";
}

// ---------------------------------------------------------------------------
// Hotlist Alerts Tab
// ---------------------------------------------------------------------------
export default function HotlistAlerts() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = HOTLIST_ALERTS.find((a) => a.id === selectedId) ?? null;

  return (
    <div style={S.page}>
      <div style={S.layout}>
        {/* Alert List */}
        <div style={S.listPanel}>
          <div style={S.listHeader}>
            <h2 style={S.title}>Active Hotlist Alerts</h2>
            <span style={S.countBadge}>{HOTLIST_ALERTS.length}</span>
          </div>
          <div style={S.alertStack}>
            {HOTLIST_ALERTS.map((a) => (
              <button
                key={a.id}
                style={{
                  ...S.alertCard,
                  borderLeft: `4px solid ${levelColor(a.level)}`,
                  background: a.id === selectedId ? "rgba(37,99,235,0.12)" : levelBg(a.level),
                }}
                onClick={() => setSelectedId(a.id === selectedId ? null : a.id)}
              >
                <div style={S.alertTop}>
                  <span style={S.plate}>{a.plate}</span>
                  <div style={S.alertRight}>
                    <span style={{ ...S.levelBadge, background: levelColor(a.level) }}>{a.level}</span>
                    <span style={S.timeAgo}>{a.time}</span>
                  </div>
                </div>
                <div style={S.alertInfo}>
                  <span style={S.reason}>{a.reason}</span>
                  <span style={S.dot}>·</span>
                  <span style={S.camera}>{a.camera}</span>
                </div>
                <div style={S.vehicleDesc}>
                  {a.color} {a.make} {a.model} ({a.year})
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        <div style={S.detailPanel}>
          {selected ? (
            <>
              <div style={S.detailHeader}>
                <span style={{ ...S.levelBadge, ...S.detailBadge, background: levelColor(selected.level) }}>{selected.level} PRIORITY</span>
                <span style={S.detailTime}>{selected.time}</span>
              </div>

              <div style={S.detailPlate}>{selected.plate}</div>
              <div style={S.detailReason}>{selected.reason}</div>

              <div style={S.detailGrid}>
                <DRow label="Make" value={selected.make} />
                <DRow label="Model" value={selected.model} />
                <DRow label="Color" value={selected.color} />
                <DRow label="Year" value={selected.year} />
                <DRow label="Camera" value={selected.camera} />
              </div>

              <div style={S.notesBox}>
                <span style={S.notesLabel}>FIELD NOTES</span>
                <p style={S.notesText}>{selected.notes}</p>
              </div>

              <div style={S.detailActions}>
                <button style={S.actionPrimary}>Navigate to Alert</button>
                <button style={S.actionBtn}>Dispatch Recovery</button>
                <button style={S.actionBtn}>Acknowledge</button>
                <button style={S.actionBtnDismiss}>Dismiss</button>
              </div>
            </>
          ) : (
            <div style={S.emptyDetail}>
              <div style={S.emptyIcon}>◎</div>
              <p style={S.emptyText}>Select an alert to view full details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function DRow({ label, value }: { label: string; value: string }) {
  return (
    <div style={S.dRow}>
      <span style={S.dLabel}>{label}</span>
      <strong style={{ color: "#e8edf5" }}>{value}</strong>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------
const S: Record<string, CSSProperties> = {
  page: {
    height: "100%",
    overflow: "hidden",
    padding: "0.75rem 1rem",
  },
  layout: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "0.75rem",
    height: "100%",
  },
  listPanel: {
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  },
  listHeader: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "0.6rem",
  },
  title: {
    margin: 0,
    fontSize: "1rem",
    fontWeight: 700,
    color: "#e8edf5",
  },
  countBadge: {
    background: "#1e293b",
    color: "#94a3b8",
    borderRadius: "999px",
    padding: "2px 10px",
    fontSize: "0.75rem",
    fontWeight: 700,
  },
  alertStack: {
    display: "flex",
    flexDirection: "column",
    gap: "8px",
    overflowY: "auto",
    flex: 1,
  },
  alertCard: {
    width: "100%",
    textAlign: "left",
    border: "1px solid #1e293b",
    borderRadius: "10px",
    padding: "14px 16px",
    cursor: "pointer",
    transition: "background 0.12s",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    minHeight: "80px",
  },
  alertTop: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  plate: {
    fontFamily: "'SF Mono', 'Fira Code', monospace",
    fontWeight: 800,
    fontSize: "1.15rem",
    color: "#e8edf5",
    letterSpacing: "0.05em",
  },
  alertRight: {
    display: "flex",
    gap: "8px",
    alignItems: "center",
  },
  levelBadge: {
    color: "#fff",
    borderRadius: 999,
    padding: "3px 10px",
    fontSize: "0.68rem",
    fontWeight: 800,
    letterSpacing: "0.04em",
  },
  timeAgo: {
    color: "#64748b",
    fontSize: "0.78rem",
  },
  alertInfo: {
    display: "flex",
    gap: "6px",
    alignItems: "center",
    fontSize: "0.82rem",
  },
  reason: {
    color: "#94a3b8",
    fontWeight: 600,
  },
  dot: {
    color: "#475569",
  },
  camera: {
    color: "#64748b",
  },
  vehicleDesc: {
    fontSize: "0.78rem",
    color: "#64748b",
  },

  // Detail panel
  detailPanel: {
    background: "#111827",
    border: "1px solid #1e293b",
    borderRadius: "12px",
    padding: "1.25rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
    overflowY: "auto",
  },
  detailHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  detailBadge: {
    padding: "5px 14px",
    fontSize: "0.75rem",
  },
  detailTime: {
    color: "#64748b",
    fontSize: "0.82rem",
  },
  detailPlate: {
    fontFamily: "'SF Mono', 'Fira Code', monospace",
    fontWeight: 800,
    fontSize: "2rem",
    color: "#e8edf5",
    letterSpacing: "0.08em",
  },
  detailReason: {
    fontSize: "1rem",
    fontWeight: 600,
    color: "#f59e0b",
  },
  detailGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "0.5rem",
    marginTop: "0.25rem",
  },
  dRow: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    border: "1px solid #1e293b",
    borderRadius: "8px",
    padding: "8px 10px",
    background: "#0c1220",
  },
  dLabel: {
    fontSize: "0.65rem",
    fontWeight: 600,
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#64748b",
  },
  notesBox: {
    background: "#0c1220",
    border: "1px solid #1e293b",
    borderRadius: "8px",
    padding: "10px 12px",
  },
  notesLabel: {
    fontSize: "0.65rem",
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.1em",
    color: "#64748b",
  },
  notesText: {
    fontSize: "0.85rem",
    color: "#cbd5e1",
    margin: "4px 0 0",
    lineHeight: 1.5,
  },
  detailActions: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    marginTop: "auto",
    paddingTop: "0.5rem",
  },
  actionPrimary: {
    background: "linear-gradient(180deg, #16a34a, #15803d)",
    color: "#fff",
    border: "1px solid #22c55e",
    borderRadius: "8px",
    padding: "12px 18px",
    fontWeight: 700,
    fontSize: "0.85rem",
    cursor: "pointer",
    minHeight: "48px",
  },
  actionBtn: {
    background: "#1a2332",
    color: "#e8edf5",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "12px 16px",
    fontWeight: 600,
    fontSize: "0.82rem",
    cursor: "pointer",
    minHeight: "48px",
  },
  actionBtnDismiss: {
    background: "transparent",
    color: "#64748b",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "12px 16px",
    fontWeight: 600,
    fontSize: "0.82rem",
    cursor: "pointer",
    minHeight: "48px",
  },

  // Empty state
  emptyDetail: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    gap: "12px",
  },
  emptyIcon: {
    fontSize: "2.5rem",
    color: "#334155",
  },
  emptyText: {
    color: "#475569",
    fontSize: "0.9rem",
  },
};
