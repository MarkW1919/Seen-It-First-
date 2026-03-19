import { type CSSProperties } from "react";

const PTZ_PRESETS = ["Front Gate", "License Lane", "Perimeter West", "Staging Lot"];

interface Props {
  camera: string;
  onClose: () => void;
}

export default function PTZModal({ camera, onClose }: Props) {
  return (
    <div style={S.backdrop} onClick={onClose}>
      <div style={S.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div style={S.header}>
          <div>
            <h3 style={S.title}>Manual PTZ Control</h3>
            <p style={S.hint}>Premium cinematic controls for rapid visual reacquisition.</p>
          </div>
          <button style={S.closeBtn} onClick={onClose}>✕</button>
        </div>

        {/* Presets */}
        <div style={S.presetRow}>
          {PTZ_PRESETS.map((p) => (
            <button key={p} style={S.presetBtn}>{p}</button>
          ))}
        </div>

        {/* PTZ Layout */}
        <div style={S.ptzLayout}>
          {/* Joystick */}
          <div style={S.joystickShell}>
            <div style={S.joystickRing}>
              <div style={S.joystickPad}>
                <button style={{ ...S.dpadBtn, gridArea: "up" }}>▲</button>
                <button style={{ ...S.dpadBtn, gridArea: "left" }}>◀</button>
                <div style={S.joystickCore}>●</div>
                <button style={{ ...S.dpadBtn, gridArea: "right" }}>▶</button>
                <button style={{ ...S.dpadBtn, gridArea: "down" }}>▼</button>
              </div>
            </div>
            <div style={S.joystickLabel}>PAN · TILT JOYSTICK</div>
          </div>

          {/* Right pane */}
          <div style={S.rightPane}>
            {/* Telemetry */}
            <div style={S.telemetry}>
              <span style={S.telLabel}>Selected Camera</span>
              <strong style={S.telValue}>{camera}</strong>
              <span style={S.telLabel}>Active Preset</span>
              <strong style={S.telValue}>License Lane</strong>
              <span style={S.telLabel}>Tracking Quality</span>
              <strong style={{ color: "#22c55e" }}>High</strong>
            </div>

            {/* Sliders */}
            <div style={S.sliders}>
              <SliderRow label="Zoom" min={1} max={20} defaultVal={8} />
              <SliderRow label="Focus" min={1} max={20} defaultVal={10} />
              <SliderRow label="Speed" min={1} max={10} defaultVal={5} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SliderRow({ label, min, max, defaultVal }: { label: string; min: number; max: number; defaultVal: number }) {
  return (
    <label style={S.sliderRow}>
      <span style={S.sliderLabel}>{label}</span>
      <input type="range" min={min} max={max} defaultValue={defaultVal} style={{ width: "100%", accentColor: "#3b82f6" }} />
    </label>
  );
}

const S: Record<string, CSSProperties> = {
  backdrop: {
    position: "fixed",
    inset: 0,
    background: "rgba(2,6,23,0.8)",
    display: "grid",
    placeItems: "center",
    zIndex: 100,
  },
  modal: {
    width: "min(880px, 95vw)",
    borderRadius: "18px",
    background: "linear-gradient(155deg, rgba(10,14,25,0.98), rgba(15,23,42,0.96))",
    border: "1px solid rgba(96,165,250,0.3)",
    boxShadow: "0 24px 60px rgba(2,6,23,0.7)",
    padding: "1.25rem",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: "1rem",
  },
  title: {
    margin: 0,
    fontSize: "1.1rem",
    fontWeight: 700,
    color: "#e8edf5",
    letterSpacing: "0.02em",
  },
  hint: {
    color: "#93c5fd",
    margin: "4px 0 0",
    fontSize: "0.82rem",
  },
  closeBtn: {
    border: "1px solid #475569",
    background: "#1e293b",
    color: "#e8edf5",
    borderRadius: "8px",
    padding: "6px 12px",
    cursor: "pointer",
    fontSize: "0.9rem",
    minHeight: "36px",
  },
  presetRow: {
    display: "flex",
    flexWrap: "wrap",
    gap: "8px",
    margin: "1rem 0",
  },
  presetBtn: {
    color: "#dbeafe",
    background: "linear-gradient(180deg, #1e3a8a, #1d4ed8)",
    border: "1px solid #60a5fa",
    borderRadius: "999px",
    padding: "8px 16px",
    fontSize: "0.82rem",
    fontWeight: 600,
    cursor: "pointer",
    minHeight: "38px",
  },
  ptzLayout: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: "1rem",
    alignItems: "stretch",
  },
  joystickShell: {
    border: "1px solid rgba(148,163,184,0.2)",
    borderRadius: "14px",
    padding: "1.25rem",
    background: "linear-gradient(170deg, rgba(30,41,59,0.5), rgba(15,23,42,0.2))",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
    alignItems: "center",
    justifyContent: "center",
  },
  joystickRing: {
    borderRadius: "50%",
    padding: "14px",
    border: "1px solid rgba(125,211,252,0.25)",
    background: "radial-gradient(circle at 35% 25%, rgba(96,165,250,0.2), rgba(15,23,42,0.05))",
  },
  joystickPad: {
    display: "grid",
    gridTemplateAreas: '". up ." "left center right" ". down ."',
    gap: "8px",
    justifyItems: "center",
    alignItems: "center",
  },
  dpadBtn: {
    width: 54,
    height: 54,
    borderRadius: "14px",
    border: "1px solid #475569",
    background: "linear-gradient(180deg, #0f172a, #111827)",
    color: "#cbd5e1",
    fontSize: "1rem",
    fontWeight: 700,
    cursor: "pointer",
    display: "grid",
    placeItems: "center",
  },
  joystickCore: {
    gridArea: "center",
    width: 76,
    height: 76,
    borderRadius: "50%",
    background: "radial-gradient(circle at 30% 30%, #93c5fd, #2563eb)",
    boxShadow: "inset 0 0 18px rgba(255,255,255,0.2), 0 8px 20px rgba(37,99,235,0.35)",
    display: "grid",
    placeItems: "center",
    fontSize: "1.3rem",
    color: "#fff",
  },
  joystickLabel: {
    fontSize: "0.7rem",
    fontWeight: 700,
    color: "#64748b",
    letterSpacing: "0.1em",
    textTransform: "uppercase",
  },
  rightPane: {
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  telemetry: {
    border: "1px solid rgba(148,163,184,0.2)",
    borderRadius: "12px",
    padding: "0.75rem",
    background: "rgba(15,23,42,0.5)",
    display: "grid",
    gridTemplateColumns: "1fr auto",
    rowGap: "6px",
    columnGap: "1rem",
    fontSize: "0.82rem",
  },
  telLabel: {
    color: "#64748b",
  },
  telValue: {
    color: "#e8edf5",
    textAlign: "right",
  },
  sliders: {
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
    border: "1px solid rgba(148,163,184,0.15)",
    borderRadius: "12px",
    padding: "0.85rem",
    background: "rgba(15,23,42,0.4)",
    flex: 1,
  },
  sliderRow: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    cursor: "pointer",
  },
  sliderLabel: {
    color: "#cbd5e1",
    fontSize: "0.85rem",
    fontWeight: 600,
  },
};
