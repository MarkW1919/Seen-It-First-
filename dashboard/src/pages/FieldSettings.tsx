import { useState, type CSSProperties } from "react";

// ---------------------------------------------------------------------------
// Settings data
// ---------------------------------------------------------------------------
interface Setting {
  key: string;
  label: string;
  description: string;
  type: "select" | "checkbox";
  options?: string[];
  defaultValue: string | boolean;
}

const ALERT_NAV: Setting[] = [
  { key: "hotlist_refresh", label: "Hotlist refresh interval", description: "How often incoming hotlist alerts refresh.", type: "select", options: ["30 sec", "60 sec", "2 min", "5 min"], defaultValue: "60 sec" },
  { key: "arrival_distance", label: "Arrival trigger distance", description: "Distance to auto-mark on-scene status.", type: "select", options: ["100 ft", "200 ft", "300 ft", "500 ft", "1000 ft"], defaultValue: "300 ft" },
  { key: "traffic_overlays", label: "Show route traffic overlays", description: "Display congestion and ETA impact while driving.", type: "checkbox", defaultValue: true },
];

const DETECTION: Setting[] = [
  { key: "ocr_threshold", label: "OCR confidence threshold", description: "Minimum confidence before plate hit is surfaced.", type: "select", options: ["0.70", "0.75", "0.80", "0.85", "0.90"], defaultValue: "0.80" },
  { key: "max_tracked", label: "Max tracked vehicles", description: "Limit active tracking cards to reduce visual load.", type: "select", options: ["5", "10", "15", "20"], defaultValue: "10" },
  { key: "auto_checkin", label: "Auto check-in on arrival", description: "Automatically transition workflow state when on scene.", type: "checkbox", defaultValue: true },
];

const NOTIFICATIONS: Setting[] = [
  { key: "silent_mode", label: "Silent shift mode", description: "Suppress alert sounds and vibration cues.", type: "checkbox", defaultValue: false },
  { key: "low_storage", label: "Low storage warning", description: "Warn before evidence exports are impacted.", type: "checkbox", defaultValue: true },
];

// ---------------------------------------------------------------------------
// Field Settings Tab
// ---------------------------------------------------------------------------
export default function FieldSettings() {
  const [profile, setProfile] = useState("default");
  const [values, setValues] = useState<Record<string, string | boolean>>(() => {
    const v: Record<string, string | boolean> = {};
    [...ALERT_NAV, ...DETECTION, ...NOTIFICATIONS].forEach((s) => { v[s.key] = s.defaultValue; });
    return v;
  });

  const updateValue = (key: string, value: string | boolean) => {
    setValues((prev) => ({ ...prev, [key]: value }));
  };

  const resetDefaults = () => {
    const v: Record<string, string | boolean> = {};
    [...ALERT_NAV, ...DETECTION, ...NOTIFICATIONS].forEach((s) => { v[s.key] = s.defaultValue; });
    setValues(v);
  };

  return (
    <div style={S.page}>
      <div style={S.panel}>
        {/* Header */}
        <div style={S.panelHeader}>
          <div>
            <h2 style={S.title}>Field Settings</h2>
            <p style={S.subtitle}>Core controls only: tune what agents most commonly adjust during recovery operations.</p>
          </div>
        </div>

        {/* Profile bar */}
        <div style={S.profileBar}>
          <div style={S.profileBadge}>
            Using {profile === "default" ? "default field" : "saved preview"} profile
          </div>
          <div style={S.profileActions}>
            <button style={S.btnSecondary} onClick={resetDefaults}>Reset defaults</button>
            <button style={S.btnPrimary} onClick={() => setProfile("saved")}>Apply locally</button>
          </div>
        </div>

        {/* Settings columns */}
        <div style={S.columnsGrid}>
          <SettingsColumn title="Alert & Navigation" color="#3b82f6" settings={ALERT_NAV} values={values} onChange={updateValue} />
          <SettingsColumn title="Detection & Workflow" color="#06b6d4" settings={DETECTION} values={values} onChange={updateValue} />
          <SettingsColumn title="Notifications" color="#f59e0b" settings={NOTIFICATIONS} values={values} onChange={updateValue} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings Column
// ---------------------------------------------------------------------------
function SettingsColumn({
  title, color, settings, values, onChange,
}: {
  title: string;
  color: string;
  settings: Setting[];
  values: Record<string, string | boolean>;
  onChange: (key: string, value: string | boolean) => void;
}) {
  return (
    <div style={{ ...S.column, borderTop: `3px solid ${color}` }}>
      <h3 style={{ ...S.colTitle, color }}>{title}</h3>
      <div style={S.settingsList}>
        {settings.map((s) => (
          <div key={s.key} style={S.settingRow}>
            <div style={S.settingInfo}>
              <span style={S.settingLabel}>{s.label}</span>
              <span style={S.settingDesc}>{s.description}</span>
            </div>
            {s.type === "select" && s.options && (
              <select
                style={S.select}
                value={values[s.key] as string}
                onChange={(e) => onChange(s.key, e.target.value)}
              >
                {s.options.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            )}
            {s.type === "checkbox" && (
              <label style={S.checkLabel}>
                <input
                  type="checkbox"
                  checked={values[s.key] as boolean}
                  onChange={(e) => onChange(s.key, e.target.checked)}
                  style={S.checkbox}
                />
                <span style={{
                  ...S.checkBox,
                  background: values[s.key] ? "#3b82f6" : "transparent",
                  borderColor: values[s.key] ? "#3b82f6" : "#475569",
                }}>
                  {values[s.key] && "✓"}
                </span>
              </label>
            )}
          </div>
        ))}
      </div>
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
    padding: "1rem 1.25rem",
  },
  panel: {
    background: "#111827",
    border: "1px solid #1e293b",
    borderRadius: "14px",
    padding: "1.25rem",
  },
  panelHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: "0.75rem",
  },
  title: {
    margin: 0,
    fontSize: "1.15rem",
    fontWeight: 700,
    color: "#e8edf5",
  },
  subtitle: {
    margin: "4px 0 0",
    fontSize: "0.82rem",
    color: "#64748b",
  },
  profileBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "1rem",
    padding: "8px 0",
    borderBottom: "1px solid #1e293b",
  },
  profileBadge: {
    fontSize: "0.78rem",
    color: "#94a3b8",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "6px 14px",
  },
  profileActions: {
    display: "flex",
    gap: "8px",
  },
  btnPrimary: {
    background: "linear-gradient(180deg, #2563eb, #1d4ed8)",
    color: "#fff",
    border: "1px solid #3b82f6",
    borderRadius: "8px",
    padding: "8px 18px",
    fontWeight: 700,
    fontSize: "0.82rem",
    cursor: "pointer",
    minHeight: "40px",
  },
  btnSecondary: {
    background: "#1a2332",
    color: "#e8edf5",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "8px 18px",
    fontWeight: 600,
    fontSize: "0.82rem",
    cursor: "pointer",
    minHeight: "40px",
  },

  // Columns
  columnsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: "12px",
  },
  column: {
    border: "1px solid #1e293b",
    borderRadius: "12px",
    padding: "1rem",
    background: "#0c1220",
  },
  colTitle: {
    margin: "0 0 0.75rem",
    fontSize: "0.9rem",
    fontWeight: 700,
  },
  settingsList: {
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  settingRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "12px",
    paddingBottom: "0.65rem",
    borderBottom: "1px solid #1e293b",
  },
  settingInfo: {
    display: "flex",
    flexDirection: "column",
    gap: "2px",
    flex: 1,
  },
  settingLabel: {
    fontSize: "0.85rem",
    fontWeight: 600,
    color: "#e8edf5",
  },
  settingDesc: {
    fontSize: "0.72rem",
    color: "#64748b",
    lineHeight: 1.3,
  },
  select: {
    background: "#1a2332",
    color: "#e8edf5",
    border: "1px solid #334155",
    borderRadius: "8px",
    padding: "8px 12px",
    fontSize: "0.82rem",
    cursor: "pointer",
    minHeight: "40px",
    minWidth: "90px",
    outline: "none",
  },
  checkLabel: {
    position: "relative",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
  },
  checkbox: {
    position: "absolute",
    opacity: 0,
    width: 0,
    height: 0,
  },
  checkBox: {
    width: "24px",
    height: "24px",
    borderRadius: "6px",
    border: "2px solid #475569",
    display: "grid",
    placeItems: "center",
    fontSize: "0.75rem",
    color: "#fff",
    fontWeight: 700,
    transition: "all 0.15s",
  },
};
