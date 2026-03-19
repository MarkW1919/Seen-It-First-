import { useState, useMemo, type CSSProperties } from "react";
import { PREVIEW_ALERTS } from "../mock/previewAlerts";
import PTZModal from "../components/PTZModal";

// ---------------------------------------------------------------------------
// Camera data
// ---------------------------------------------------------------------------
const CAMERAS = [
  { id: "cam-front-1", name: "Main Entry", status: "Online", fps: 30, temp: "61°C" },
  { id: "cam-side-2", name: "Gate North", status: "Online", fps: 28, temp: "59°C" },
  { id: "cam-rear-3", name: "Lot East", status: "Online", fps: 27, temp: "60°C" },
  { id: "cam-west-4", name: "Street Cam 2", status: "Offline", fps: 0, temp: "--" },
];

// ---------------------------------------------------------------------------
// Camera Views Tab
// ---------------------------------------------------------------------------
export default function CameraViews() {
  const [selectedAlertId, setSelectedAlertId] = useState<string>(PREVIEW_ALERTS[0]?.id ?? "");
  const [ptzOpen, setPtzOpen] = useState(false);

  const selectedAlert = useMemo(
    () => PREVIEW_ALERTS.find((a) => a.id === selectedAlertId) ?? PREVIEW_ALERTS[0] ?? null,
    [selectedAlertId],
  );

  return (
    <div style={S.page}>
      {/* Camera Grid */}
      <section style={S.section}>
        <h2 style={S.sectionTitle}>Camera Views</h2>
        <div style={S.camGrid}>
          {CAMERAS.map((cam) => (
            <div key={cam.id} style={S.camCard}>
              <div style={S.camFeed}>Live Feed: {cam.name}</div>
              <div style={S.camMeta}>
                <span style={S.camId}>{cam.id}</span>
                <StatusBadge online={cam.status === "Online"} />
                <span>{cam.fps} FPS</span>
                <span>{cam.temp}</span>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Recent Alerts Table */}
      <section style={S.section}>
        <h3 style={S.subTitle}>Recent Alerts</h3>
        <div style={S.tableWrap}>
          <table style={S.table}>
            <thead>
              <tr>
                <th>Time</th>
                <th>Plate</th>
                <th>Vehicle</th>
                <th>Camera</th>
                <th>Confidence</th>
                <th>GPS</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {PREVIEW_ALERTS.map((a) => (
                <tr
                  key={a.id}
                  style={{
                    cursor: "pointer",
                    background: a.id === selectedAlertId ? "rgba(37,99,235,0.15)" : undefined,
                  }}
                  onClick={() => setSelectedAlertId(a.id)}
                >
                  <td>{a.ts}</td>
                  <td style={{ fontFamily: "monospace", fontWeight: 700, color: "#e8edf5" }}>{a.plate}</td>
                  <td>{a.vehicle}</td>
                  <td>{a.camera}</td>
                  <td>{(a.confidence * 100).toFixed(0)}%</td>
                  <td>
                    <span style={S.coordText}>
                      {a.latitude.toFixed(5)},&nbsp;{a.longitude.toFixed(5)}
                    </span>
                  </td>
                  <td>
                    <button style={S.viewBtn} onClick={(e) => { e.stopPropagation(); setSelectedAlertId(a.id); }}>
                      View Directions
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Selected Alert Details */}
      {selectedAlert && (
        <section style={S.detailPanel}>
          <h3 style={S.subTitle}>Selected Alert Details</h3>
          <div style={S.detailLayout}>
            <img src={selectedAlert.photoUrl} alt={`Scan ${selectedAlert.plate}`} style={S.scanPhoto} />
            <div style={S.detailGrid}>
              <DetailItem label="PLATE" value={selectedAlert.plate} />
              <DetailItem label="VEHICLE" value={selectedAlert.vehicle} />
              <DetailItem label="MAKE / MODEL" value={`${selectedAlert.make} ${selectedAlert.model}`} />
              <DetailItem label="COLOR / YEAR" value={`${selectedAlert.color} / ${selectedAlert.yearRange}`} />
              <DetailItem label="CAMERA" value={selectedAlert.camera} />
              <DetailItem label="TIME" value={selectedAlert.ts} />
              <DetailItem label="COORDINATES" value={`${selectedAlert.latitude.toFixed(5)}, ${selectedAlert.longitude.toFixed(5)}`} />
              <DetailItem label="CONFIDENCE" value={`${(selectedAlert.confidence * 100).toFixed(0)}%`} />
            </div>
          </div>

          {/* Quick Actions */}
          <div style={S.quickActions}>
            <button style={S.quickBtnPrimary}>License Plate Search</button>
            <button style={S.quickBtn}>Dispatch Recovery Agent</button>
            <button style={S.quickBtn}>Mark Visual Confirmed</button>
            <button style={S.quickBtn}>Open Camera Playback</button>
            <button style={S.quickBtn}>Send Team Notification</button>
            <button style={S.quickBtn} onClick={() => setPtzOpen(true)}>Manual PTZ Control</button>
          </div>
        </section>
      )}

      {/* PTZ Modal */}
      {ptzOpen && (
        <PTZModal
          camera={selectedAlert?.camera ?? "Main Entry"}
          onClose={() => setPtzOpen(false)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function StatusBadge({ online }: { online: boolean }) {
  return (
    <span style={{
      background: online ? "#16a34a" : "#64748b",
      color: "#fff",
      borderRadius: 999,
      padding: "2px 8px",
      fontSize: "0.7rem",
      fontWeight: 700,
    }}>
      {online ? "Online" : "Offline"}
    </span>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={S.detailItem}>
      <span style={S.detailLabel}>{label}</span>
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
    overflowY: "auto",
    padding: "0.75rem 1rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  section: {
    background: "#111827",
    border: "1px solid #1e293b",
    borderRadius: "12px",
    padding: "0.85rem",
  },
  sectionTitle: {
    margin: "0 0 0.6rem",
    fontSize: "1rem",
    fontWeight: 700,
    color: "#e8edf5",
  },
  subTitle: {
    margin: "0 0 0.5rem",
    fontSize: "0.9rem",
    fontWeight: 600,
    color: "#cbd5e1",
  },

  // Camera grid
  camGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "8px",
  },
  camCard: {
    border: "1px solid #1e293b",
    borderRadius: "10px",
    overflow: "hidden",
  },
  camFeed: {
    height: 160,
    display: "grid",
    placeItems: "center",
    background: "linear-gradient(145deg, #1a2332, #263244)",
    color: "#7dd3fc",
    fontWeight: 600,
    fontSize: "0.9rem",
  },
  camMeta: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 12px",
    fontSize: "0.78rem",
    color: "#94a3b8",
    background: "#0c1220",
  },
  camId: {
    color: "#64748b",
    fontSize: "0.72rem",
  },

  // Table
  tableWrap: {
    overflowX: "auto",
    border: "1px solid #1e293b",
    borderRadius: "10px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    minWidth: 900,
  },
  coordText: {
    color: "#93c5fd",
    fontFamily: "monospace",
    fontWeight: 700,
    fontSize: "0.78rem",
  },
  viewBtn: {
    color: "#fff",
    background: "linear-gradient(180deg, #2563eb, #1d4ed8)",
    padding: "6px 12px",
    borderRadius: "6px",
    fontSize: "0.75rem",
    fontWeight: 600,
    border: "none",
    cursor: "pointer",
    whiteSpace: "nowrap",
    minHeight: "32px",
  },

  // Detail panel
  detailPanel: {
    background: "#0c1220",
    border: "1px solid #1e293b",
    borderRadius: "12px",
    padding: "0.85rem",
  },
  detailLayout: {
    display: "grid",
    gridTemplateColumns: "220px 1fr",
    gap: "0.85rem",
    alignItems: "start",
  },
  scanPhoto: {
    width: "100%",
    height: 170,
    objectFit: "cover",
    borderRadius: "10px",
    border: "1px solid #1e293b",
  },
  detailGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "0.5rem",
  },
  detailItem: {
    border: "1px solid #1e293b",
    borderRadius: "8px",
    padding: "0.5rem 0.65rem",
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    background: "#111827",
  },
  detailLabel: {
    color: "#64748b",
    fontSize: "0.65rem",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    fontWeight: 600,
  },

  // Quick actions
  quickActions: {
    marginTop: "0.75rem",
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
  },
  quickBtnPrimary: {
    color: "#fff",
    background: "linear-gradient(180deg, #2563eb, #1d4ed8)",
    border: "1px solid #3b82f6",
    borderRadius: "8px",
    padding: "10px 16px",
    fontWeight: 700,
    fontSize: "0.82rem",
    cursor: "pointer",
    minHeight: "42px",
  },
  quickBtn: {
    color: "#e8edf5",
    background: "#1a2332",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "10px 16px",
    fontWeight: 600,
    fontSize: "0.82rem",
    cursor: "pointer",
    minHeight: "42px",
  },
};
