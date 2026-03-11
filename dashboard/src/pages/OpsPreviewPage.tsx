import { useMemo, useState, type CSSProperties } from "react";
import { PREVIEW_ALERTS } from "../mock/previewAlerts";

type OpsScreen = "hotlist" | "cameras" | "settings";

const HOTLIST_ALERTS = [
  { plate: "8ABC123", level: "HIGH", reason: "Stolen Vehicle", time: "2 min ago", camera: "Gate North" },
  { plate: "4KJX998", level: "MED", reason: "BOLO Match", time: "11 min ago", camera: "Lot East" },
  { plate: "7TQF201", level: "HIGH", reason: "Felony Warrant", time: "18 min ago", camera: "Main Entry" },
];

const CAMERAS = [
  { id: "cam-front-1", name: "Main Entry", status: "Online", fps: 30, temp: "61°C" },
  { id: "cam-side-2", name: "Gate North", status: "Online", fps: 28, temp: "59°C" },
  { id: "cam-rear-3", name: "Lot East", status: "Online", fps: 27, temp: "60°C" },
  { id: "cam-west-4", name: "Street Cam 2", status: "Offline", fps: 0, temp: "--" },
];


const PTZ_PRESETS = [
  "Front Gate",
  "License Lane",
  "Perimeter West",
  "Staging Lot",
];

function badge(bg: string): CSSProperties {
  return {
    background: bg,
    color: "#fff",
    borderRadius: 999,
    padding: "0.2rem 0.6rem",
    fontSize: "0.72rem",
    fontWeight: 700,
  };
}

function getScreen(): OpsScreen {
  const screen = new URLSearchParams(window.location.search).get("screen");
  if (screen === "hotlist" || screen === "cameras" || screen === "settings") return screen;
  return "hotlist";
}

export default function OpsPreviewPage() {
  const screen = getScreen();
  const [selectedAlertId, setSelectedAlertId] = useState<string>(PREVIEW_ALERTS[0]?.id ?? "");
  const [ptzOpen, setPtzOpen] = useState(false);

  const selectedAlert = useMemo(
    () => PREVIEW_ALERTS.find((a) => a.id === selectedAlertId) ?? PREVIEW_ALERTS[0] ?? null,
    [selectedAlertId],
  );

  return (
    <div style={styles.page}>
      <header style={styles.header}>
        <div style={styles.brand}>Seen-It-First Ops Preview</div>
        <nav style={styles.nav}>
          <a href="/?screen=hotlist" style={screen === "hotlist" ? styles.activeLink : styles.link}>Hotlist Alerts</a>
          <a href="/?screen=cameras" style={screen === "cameras" ? styles.activeLink : styles.link}>Camera Views</a>
          <a href="/?screen=settings" style={screen === "settings" ? styles.activeLink : styles.link}>Settings</a>
        </nav>
      </header>

      <main style={styles.main}>
        {screen === "hotlist" && (
          <section style={styles.panel}>
            <h2 style={styles.title}>Active Hotlist Alerts</h2>
            <div style={styles.stack}>
              {HOTLIST_ALERTS.map((a) => (
                <div key={a.plate} style={styles.rowCard}>
                  <div>
                    <div style={styles.plate}>{a.plate}</div>
                    <div style={styles.sub}>{a.reason} · {a.camera}</div>
                  </div>
                  <div style={styles.rightGroup}>
                    <span style={badge(a.level === "HIGH" ? "#dc2626" : "#d97706")}>{a.level}</span>
                    <span style={styles.time}>{a.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {screen === "cameras" && (
          <section style={styles.panel}>
            <h2 style={styles.title}>Camera Views</h2>
            <div style={styles.grid}>
              {CAMERAS.map((cam) => (
                <div key={cam.id} style={styles.cameraCard}>
                  <div style={styles.cameraFeed}>Live Feed: {cam.name}</div>
                  <div style={styles.cameraMeta}>
                    <span>{cam.id}</span>
                    <span style={badge(cam.status === "Online" ? "#16a34a" : "#64748b")}>{cam.status}</span>
                    <span>{cam.fps} FPS</span>
                    <span>{cam.temp}</span>
                  </div>
                </div>
              ))}
            </div>

            <h3 style={styles.subTitle}>Recent Alerts</h3>
            <div style={styles.tableWrap}>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th>Time</th><th>Plate</th><th>Vehicle</th><th>Camera</th><th>Confidence</th><th>GPS</th><th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {PREVIEW_ALERTS.map((h) => {
                    const rowStyle = h.id === selectedAlert?.id ? styles.tableRowActive : styles.tableRow;
                    return (
                      <tr key={`${h.plate}-${h.ts}`} style={rowStyle} onClick={() => setSelectedAlertId(h.id)}>
                        <td>{h.ts}</td>
                        <td style={{ fontFamily: "monospace", fontWeight: 700 }}>{h.plate}</td>
                        <td>{h.vehicle}</td>
                        <td>{h.camera}</td>
                        <td>{(h.confidence * 100).toFixed(0)}%</td>
                        <td>
                          <a
                            href={`/?preview=route&alert=${h.id}`}
                            style={styles.coordLink}
                            title="Open in navigation preview"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {h.latitude.toFixed(5)}, {h.longitude.toFixed(5)}
                          </a>
                        </td>
                        <td>
                          <a
                            href={`/?preview=route&alert=${h.id}`}
                            style={styles.routeBtn}
                            onClick={(e) => e.stopPropagation()}
                          >
                            View Directions
                          </a>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {selectedAlert && (
              <section style={styles.detailPanel}>
                <h3 style={styles.subTitle}>Selected Alert Details</h3>
                <div style={styles.detailLayout}>
                  <img src={selectedAlert.photoUrl} alt={`Scan ${selectedAlert.plate}`} style={styles.scanPhoto} />
                  <div style={styles.detailGrid}>
                    <div style={styles.detailItem}><span style={styles.detailLabel}>Plate</span><strong>{selectedAlert.plate}</strong></div>
                    <div style={styles.detailItem}><span style={styles.detailLabel}>Vehicle</span><strong>{selectedAlert.vehicle}</strong></div>
                    <div style={styles.detailItem}><span style={styles.detailLabel}>Make / Model</span><strong>{selectedAlert.make} {selectedAlert.model}</strong></div>
                    <div style={styles.detailItem}><span style={styles.detailLabel}>Color / Year</span><strong>{selectedAlert.color} / {selectedAlert.yearRange}</strong></div>
                    <div style={styles.detailItem}><span style={styles.detailLabel}>Camera</span><strong>{selectedAlert.camera}</strong></div>
                    <div style={styles.detailItem}><span style={styles.detailLabel}>Time</span><strong>{selectedAlert.ts}</strong></div>
                    <div style={styles.detailItem}><span style={styles.detailLabel}>Coordinates</span><strong>{selectedAlert.latitude.toFixed(5)}, {selectedAlert.longitude.toFixed(5)}</strong></div>
                    <div style={styles.detailItem}><span style={styles.detailLabel}>Confidence</span><strong>{(selectedAlert.confidence * 100).toFixed(0)}%</strong></div>
                  </div>
                </div>

                <div style={styles.quickActions}>
                  <a href={`/?preview=route&alert=${selectedAlert.id}`} style={styles.quickBtnPrimary}>License Plate Search</a>
                  <a href="/?screen=settings" style={styles.quickBtn}>Settings</a>
                  <button type="button" style={styles.quickBtn} onClick={() => setPtzOpen(true)}>Manual PTZ Control</button>
                </div>
              </section>
            )}
          </section>
        )}

        {screen === "settings" && (
          <section style={styles.panel}>
            <h2 style={styles.title}>System Settings</h2>
            <div style={styles.settingRow}><span>Hotlist refresh interval</span><strong>60 sec</strong></div>
            <div style={styles.settingRow}><span>Arrival trigger distance</span><strong>300 ft</strong></div>
            <div style={styles.settingRow}><span>Alert sound</span><strong>Enabled</strong></div>
            <div style={styles.settingRow}><span>Default OCR confidence threshold</span><strong>0.80</strong></div>
            <div style={styles.settingRow}><span>Max tracked vehicles</span><strong>10</strong></div>
          </section>
        )}
      </main>

      {ptzOpen && (
        <div style={styles.modalBackdrop} onClick={() => setPtzOpen(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <div>
                <h3 style={styles.modalTitle}>Manual PTZ Control</h3>
                <p style={styles.modalHint}>Premium cinematic controls for rapid visual reacquisition.</p>
              </div>
              <button type="button" style={styles.modalClose} onClick={() => setPtzOpen(false)}>✕</button>
            </div>

            <div style={styles.presetRow}>
              {PTZ_PRESETS.map((preset) => (
                <button key={preset} type="button" style={styles.presetBtn}>{preset}</button>
              ))}
            </div>

            <div style={styles.ptzLayout}>
              <div style={styles.joystickShell}>
                <div style={styles.joystickRing}>
                  <div style={styles.joystickPad}>
                    <button type="button" style={{ ...styles.ptzBtn, gridArea: "up" }}>▲</button>
                    <button type="button" style={{ ...styles.ptzBtn, gridArea: "left" }}>◀</button>
                    <div style={styles.joystickCore}>●</div>
                    <button type="button" style={{ ...styles.ptzBtn, gridArea: "right" }}>▶</button>
                    <button type="button" style={{ ...styles.ptzBtn, gridArea: "down" }}>▼</button>
                  </div>
                </div>
                <div style={styles.joystickLabel}>Pan · Tilt Joystick</div>
              </div>

              <div style={styles.ptzRightPane}>
                <div style={styles.telemetryCard}>
                  <span>Selected Camera</span>
                  <strong>{selectedAlert?.camera ?? "Main Entry"}</strong>
                  <span>Active Preset</span>
                  <strong>License Lane</strong>
                  <span>Tracking Quality</span>
                  <strong style={{ color: "#22c55e" }}>High</strong>
                </div>

                <div style={styles.ptzSliders}>
                  <label style={styles.sliderRow}>Zoom
                    <input type="range" min="1" max="20" defaultValue="8" />
                  </label>
                  <label style={styles.sliderRow}>Focus
                    <input type="range" min="1" max="20" defaultValue="10" />
                  </label>
                  <label style={styles.sliderRow}>Speed
                    <input type="range" min="1" max="10" defaultValue="5" />
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { minHeight: "100vh", background: "#0f172a", color: "#e2e8f0", fontFamily: "Inter, system-ui, sans-serif" },
  header: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1rem 1.25rem", background: "#111827", borderBottom: "1px solid #334155" },
  brand: { fontWeight: 700, color: "#60a5fa" },
  nav: { display: "flex", gap: "0.75rem" },
  link: { color: "#94a3b8", textDecoration: "none", border: "1px solid #334155", borderRadius: 8, padding: "0.45rem 0.7rem" },
  activeLink: { color: "#e2e8f0", textDecoration: "none", border: "1px solid #3b82f6", background: "#1e3a8a", borderRadius: 8, padding: "0.45rem 0.7rem" },
  main: { padding: "1rem 1.25rem" },
  panel: { background: "#111827", border: "1px solid #334155", borderRadius: 12, padding: "1rem" },
  title: { marginTop: 0 },
  subTitle: { marginTop: "1rem", marginBottom: "0.6rem", color: "#cbd5e1" },
  stack: { display: "flex", flexDirection: "column", gap: "0.7rem" },
  rowCard: { display: "flex", justifyContent: "space-between", alignItems: "center", background: "#0b1220", border: "1px solid #374151", borderRadius: 10, padding: "0.8rem" },
  plate: { fontFamily: "monospace", fontWeight: 800, fontSize: "1.1rem" },
  sub: { color: "#94a3b8", fontSize: "0.85rem" },
  rightGroup: { display: "flex", gap: "0.65rem", alignItems: "center" },
  time: { color: "#cbd5e1", fontSize: "0.82rem" },
  tableWrap: { overflowX: "auto", border: "1px solid #334155", borderRadius: 10 },
  table: { width: "100%", borderCollapse: "collapse", minWidth: 920 },
  tableRow: { cursor: "pointer" },
  tableRowActive: { cursor: "pointer", background: "rgba(37, 99, 235, 0.18)" },
  grid: { display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: "0.85rem" },
  cameraCard: { border: "1px solid #334155", borderRadius: 10, overflow: "hidden" },
  cameraFeed: { height: 180, display: "grid", placeItems: "center", background: "linear-gradient(145deg,#1e293b,#334155)", color: "#bfdbfe", fontWeight: 600 },
  cameraMeta: { display: "flex", justifyContent: "space-between", padding: "0.65rem", fontSize: "0.82rem" },
  coordLink: { color: "#93c5fd", textDecoration: "none", fontFamily: "monospace", fontWeight: 700 },
  routeBtn: { color: "#fff", background: "#2563eb", textDecoration: "none", padding: "0.28rem 0.55rem", borderRadius: 6, fontSize: "0.78rem" },
  detailPanel: { marginTop: "1rem", border: "1px solid #334155", borderRadius: 10, padding: "0.85rem", background: "#0b1220" },
  detailLayout: { display: "grid", gridTemplateColumns: "260px 1fr", gap: "0.85rem", alignItems: "start" },
  scanPhoto: { width: "100%", height: 170, objectFit: "cover", borderRadius: 8, border: "1px solid #334155" },
  detailGrid: { display: "grid", gridTemplateColumns: "repeat(2, minmax(0,1fr))", gap: "0.6rem" },
  detailItem: { border: "1px solid #1f2937", borderRadius: 8, padding: "0.55rem", display: "flex", flexDirection: "column", gap: "0.2rem" },
  detailLabel: { color: "#94a3b8", fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.06em" },
  quickActions: { marginTop: "0.85rem", display: "flex", flexWrap: "wrap", gap: "0.55rem" },
  quickBtnPrimary: { color: "#fff", background: "#2563eb", textDecoration: "none", border: "1px solid #3b82f6", borderRadius: 8, padding: "0.45rem 0.7rem", fontWeight: 700 },
  quickBtn: { color: "#e2e8f0", background: "#1f2937", border: "1px solid #334155", borderRadius: 8, padding: "0.45rem 0.7rem", fontWeight: 600, cursor: "pointer", textDecoration: "none" },
  settingRow: { display: "flex", justifyContent: "space-between", borderBottom: "1px solid #1f2937", padding: "0.8rem 0" },
  modalBackdrop: { position: "fixed", inset: 0, background: "rgba(2,6,23,0.75)", display: "grid", placeItems: "center", zIndex: 80 },
  modal: { width: "min(900px, 95vw)", borderRadius: 18, background: "linear-gradient(155deg, rgba(10,14,25,0.98), rgba(15,23,42,0.94))", border: "1px solid rgba(96,165,250,0.35)", boxShadow: "0 24px 60px rgba(2,6,23,0.65)", padding: "1rem 1.1rem" },
  modalHeader: { display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "0.8rem" },
  modalClose: { border: "1px solid #475569", background: "#1e293b", color: "#e2e8f0", borderRadius: 8, padding: "0.3rem 0.55rem", cursor: "pointer" },
  modalTitle: { margin: 0, fontSize: "1.15rem", letterSpacing: "0.02em" },
  modalHint: { color: "#93c5fd", marginTop: "0.2rem", marginBottom: 0 },
  presetRow: { display: "flex", flexWrap: "wrap", gap: "0.45rem", marginTop: "0.85rem", marginBottom: "0.95rem" },
  presetBtn: { color: "#dbeafe", background: "linear-gradient(180deg,#1e3a8a,#1d4ed8)", border: "1px solid #60a5fa", borderRadius: 999, padding: "0.35rem 0.75rem", fontSize: "0.78rem", cursor: "pointer" },
  ptzLayout: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", alignItems: "stretch" },
  joystickShell: { border: "1px solid rgba(148,163,184,0.25)", borderRadius: 14, padding: "0.8rem", background: "linear-gradient(170deg, rgba(30,41,59,0.62), rgba(15,23,42,0.25))", display: "flex", flexDirection: "column", gap: "0.6rem", alignItems: "center", justifyContent: "center" },
  joystickRing: { borderRadius: "50%", padding: "0.7rem", border: "1px solid rgba(125,211,252,0.3)", background: "radial-gradient(circle at 35% 25%, rgba(96,165,250,0.28), rgba(15,23,42,0.05))" },
  joystickPad: { display: "grid", gridTemplateAreas: '". up ." "left center right" ". down ."', gap: "0.5rem", justifyItems: "center", alignItems: "center" },
  joystickLabel: { fontSize: "0.75rem", color: "#94a3b8", letterSpacing: "0.07em", textTransform: "uppercase" },
  joystickCore: { gridArea: "center", width: 72, height: 72, borderRadius: "50%", background: "radial-gradient(circle at 30% 30%, #93c5fd, #2563eb)", boxShadow: "inset 0 0 18px rgba(255,255,255,0.25), 0 8px 20px rgba(37,99,235,0.35)", display: "grid", placeItems: "center", fontSize: "1.3rem" },
  ptzBtn: { width: 50, height: 50, borderRadius: 13, border: "1px solid #475569", background: "linear-gradient(180deg,#0f172a,#111827)", color: "#cbd5e1", cursor: "pointer", fontWeight: 700 },
  ptzRightPane: { display: "grid", gridTemplateRows: "auto 1fr", gap: "0.75rem" },
  telemetryCard: { border: "1px solid rgba(148,163,184,0.25)", borderRadius: 12, padding: "0.65rem", background: "rgba(15,23,42,0.55)", display: "grid", gridTemplateColumns: "1fr auto", rowGap: "0.35rem", columnGap: "0.8rem", fontSize: "0.78rem", color: "#94a3b8" },
  ptzSliders: { display: "flex", flexDirection: "column", gap: "0.7rem", border: "1px solid rgba(148,163,184,0.2)", borderRadius: 12, padding: "0.7rem", background: "rgba(15,23,42,0.45)" },
  sliderRow: { display: "flex", flexDirection: "column", gap: "0.3rem", color: "#cbd5e1", fontSize: "0.85rem" },
};
