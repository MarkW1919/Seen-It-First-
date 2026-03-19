import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { OperatorProfile } from "../types/navigation";

type SettingField = {
  key: keyof OperatorProfile;
  label: string;
  description: string;
  kind: "select";
  options: Array<{ value: number; label: string }>;
};

const ACTIVE_FIELDS: SettingField[] = [
  {
    key: "arrival_distance_ft",
    label: "Arrival trigger distance",
    description: "Default geofence distance used when a new navigation mission starts.",
    kind: "select",
    options: [
      { value: 100, label: "100 ft" },
      { value: 200, label: "200 ft" },
      { value: 300, label: "300 ft" },
      { value: 500, label: "500 ft" },
      { value: 1000, label: "1000 ft" },
    ],
  },
  {
    key: "hotlist_refresh_sec",
    label: "Hotlist refresh interval",
    description: "How often the hotlist board refreshes recent alert history from the edge runtime.",
    kind: "select",
    options: [
      { value: 15, label: "15 sec" },
      { value: 30, label: "30 sec" },
      { value: 60, label: "60 sec" },
      { value: 120, label: "2 min" },
      { value: 300, label: "5 min" },
    ],
  },
  {
    key: "max_tracked_vehicles",
    label: "Max tracked vehicles",
    description: "Upper bound for how many candidate vehicles are shown once scanning is active.",
    kind: "select",
    options: [
      { value: 5, label: "5" },
      { value: 10, label: "10" },
      { value: 15, label: "15" },
      { value: 20, label: "20" },
      { value: 30, label: "30" },
    ],
  },
];

const DEFAULT_PROFILE: OperatorProfile = {
  hotlist_refresh_sec: 60,
  arrival_distance_ft: 300,
  show_traffic_overlays: true,
  ocr_confidence_threshold: 0.8,
  max_tracked_vehicles: 10,
  auto_checkin_on_arrival: true,
  silent_shift_mode: false,
  low_storage_warning: true,
};

async function getOperatorProfile(): Promise<OperatorProfile> {
  const res = await fetch("/navigation/operator-profile");
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  return res.json() as Promise<OperatorProfile>;
}

async function putOperatorProfile(profile: OperatorProfile): Promise<OperatorProfile> {
  const res = await fetch("/navigation/operator-profile", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((detail as { detail?: string }).detail ?? res.statusText);
  }
  return res.json() as Promise<OperatorProfile>;
}

export default function FieldSettings() {
  const queryClient = useQueryClient();
  const profileQuery = useQuery<OperatorProfile>({
    queryKey: ["operator-profile"],
    queryFn: getOperatorProfile,
  });

  const persistedProfile = profileQuery.data ?? DEFAULT_PROFILE;
  const [draft, setDraft] = useState<OperatorProfile>(persistedProfile);
  const [statusNote, setStatusNote] = useState<string>("Loading operator profile...");

  useEffect(() => {
    if (!profileQuery.data) {
      return;
    }
    setDraft(profileQuery.data);
    setStatusNote("Profile synced from the edge runtime.");
  }, [profileQuery.data]);

  const hasUnsavedChanges = useMemo(
    () => JSON.stringify(draft) !== JSON.stringify(persistedProfile),
    [draft, persistedProfile],
  );

  const saveMutation = useMutation<OperatorProfile, Error, OperatorProfile>({
    mutationFn: putOperatorProfile,
    onSuccess: (profile) => {
      queryClient.setQueryData(["operator-profile"], profile);
      setDraft(profile);
      setStatusNote("Operator profile saved to the runtime.");
    },
    onError: (error) => {
      setStatusNote(`Unable to save operator profile: ${error.message}`);
    },
  });

  const updateNumericField = (key: keyof OperatorProfile, value: number) => {
    setDraft((prev) => ({ ...prev, [key]: value }));
    setStatusNote("Unsaved changes in this operator profile.");
  };

  const resetToSaved = () => {
    setDraft(persistedProfile);
    setStatusNote("Reverted to the last saved operator profile.");
  };

  const resetToDefaults = () => {
    setDraft(DEFAULT_PROFILE);
    setStatusNote("Loaded the default operator profile values. Save to persist them.");
  };

  const handleSave = () => {
    saveMutation.mutate({
      ...persistedProfile,
      ...draft,
    });
  };

  return (
    <div style={S.page}>
      <div style={S.panel}>
        <div style={S.panelHeader}>
          <div>
            <h2 style={S.title}>Field Settings</h2>
            <p style={S.subtitle}>
              These controls are wired to the persisted operator profile used by the runtime-backed dashboard.
            </p>
          </div>
          <div style={S.headerStatus}>
            <span style={S.statusLabel}>Runtime profile</span>
            <strong style={S.statusValue}>{profileQuery.isLoading ? "Loading" : "Connected"}</strong>
          </div>
        </div>

        <div style={S.noticeRow}>
          <span style={{ ...S.noticeDot, background: saveMutation.isError ? "#ef4444" : hasUnsavedChanges ? "#f59e0b" : "#22c55e" }} />
          <span style={S.noticeText}>{statusNote}</span>
        </div>

        {profileQuery.error instanceof Error && (
          <div style={S.errorBox}>Unable to load the operator profile: {profileQuery.error.message}</div>
        )}

        <div style={S.profileMeta}>
          <div style={S.metaCard}>
            <span style={S.metaLabel}>Stored profile</span>
            <strong style={S.metaValue}>operator_profile.json</strong>
          </div>
          <div style={S.metaCard}>
            <span style={S.metaLabel}>Save state</span>
            <strong style={S.metaValue}>{hasUnsavedChanges ? "Unsaved edits" : "In sync"}</strong>
          </div>
          <div style={S.metaCard}>
            <span style={S.metaLabel}>Applies to</span>
            <strong style={S.metaValue}>Nav HUD, Hotlist, Target List</strong>
          </div>
        </div>

        <div style={S.settingsGrid}>
          {ACTIVE_FIELDS.map((field) => (
            <div key={field.key} style={S.settingCard}>
              <div style={S.settingHeader}>
                <h3 style={S.settingTitle}>{field.label}</h3>
                <span style={S.settingKey}>{field.key}</span>
              </div>
              <p style={S.settingDescription}>{field.description}</p>
              <select
                style={S.select}
                value={String(draft[field.key])}
                onChange={(event) => updateNumericField(field.key, Number(event.target.value))}
                disabled={profileQuery.isLoading || saveMutation.isPending}
              >
                {field.options.map((option) => (
                  <option key={`${field.key}-${option.value}`} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
              <div style={S.savedLine}>
                Saved value: <strong>{field.options.find((option) => option.value === persistedProfile[field.key])?.label ?? String(persistedProfile[field.key])}</strong>
              </div>
            </div>
          ))}
        </div>

        <div style={S.actionRow}>
          <button style={S.btnSecondary} onClick={resetToSaved} disabled={saveMutation.isPending || !hasUnsavedChanges}>
            Discard edits
          </button>
          <button style={S.btnSecondary} onClick={resetToDefaults} disabled={saveMutation.isPending}>
            Load defaults
          </button>
          <button style={S.btnPrimary} onClick={handleSave} disabled={saveMutation.isPending || profileQuery.isLoading || !hasUnsavedChanges}>
            {saveMutation.isPending ? "Saving profile..." : "Save profile"}
          </button>
        </div>
      </div>
    </div>
  );
}

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
    display: "flex",
    flexDirection: "column",
    gap: "1rem",
  },
  panelHeader: {
    display: "flex",
    justifyContent: "space-between",
    gap: "1rem",
    alignItems: "flex-start",
  },
  title: {
    margin: 0,
    fontSize: "1.15rem",
    fontWeight: 700,
    color: "#e8edf5",
  },
  subtitle: {
    margin: "6px 0 0",
    fontSize: "0.84rem",
    color: "#94a3b8",
    maxWidth: "48rem",
    lineHeight: 1.5,
  },
  headerStatus: {
    background: "#0c1220",
    border: "1px solid #334155",
    borderRadius: "10px",
    padding: "10px 14px",
    display: "flex",
    flexDirection: "column",
    gap: "4px",
    minWidth: "160px",
  },
  statusLabel: {
    fontSize: "0.72rem",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#64748b",
  },
  statusValue: {
    fontSize: "0.9rem",
    color: "#e8edf5",
  },
  noticeRow: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    background: "#0c1220",
    border: "1px solid #1e293b",
    borderRadius: "10px",
    padding: "10px 12px",
  },
  noticeDot: {
    width: "10px",
    height: "10px",
    borderRadius: "999px",
    flexShrink: 0,
  },
  noticeText: {
    color: "#cbd5e1",
    fontSize: "0.85rem",
  },
  errorBox: {
    background: "#450a0a",
    color: "#fecaca",
    border: "1px solid #7f1d1d",
    borderRadius: "10px",
    padding: "10px 12px",
    fontSize: "0.85rem",
  },
  profileMeta: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: "12px",
  },
  metaCard: {
    background: "#0c1220",
    border: "1px solid #1e293b",
    borderRadius: "12px",
    padding: "12px 14px",
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  },
  metaLabel: {
    fontSize: "0.72rem",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    color: "#64748b",
  },
  metaValue: {
    fontSize: "0.9rem",
    color: "#e8edf5",
  },
  settingsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: "12px",
  },
  settingCard: {
    background: "#0c1220",
    border: "1px solid #1e293b",
    borderRadius: "12px",
    padding: "1rem",
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem",
  },
  settingHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "baseline",
    gap: "12px",
  },
  settingTitle: {
    margin: 0,
    fontSize: "0.95rem",
    fontWeight: 700,
    color: "#e8edf5",
  },
  settingKey: {
    fontSize: "0.68rem",
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
  },
  settingDescription: {
    margin: 0,
    color: "#94a3b8",
    fontSize: "0.8rem",
    lineHeight: 1.45,
  },
  select: {
    background: "#111827",
    color: "#e8edf5",
    border: "1px solid #334155",
    borderRadius: "10px",
    padding: "10px 12px",
    minHeight: "42px",
    fontSize: "0.9rem",
    outline: "none",
  },
  savedLine: {
    color: "#64748b",
    fontSize: "0.78rem",
  },
  actionRow: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "10px",
  },
  btnPrimary: {
    background: "linear-gradient(180deg, #2563eb, #1d4ed8)",
    color: "#fff",
    border: "1px solid #3b82f6",
    borderRadius: "10px",
    padding: "10px 18px",
    fontWeight: 700,
    minHeight: "42px",
    cursor: "pointer",
  },
  btnSecondary: {
    background: "#111827",
    color: "#e8edf5",
    border: "1px solid #334155",
    borderRadius: "10px",
    padding: "10px 18px",
    fontWeight: 600,
    minHeight: "42px",
    cursor: "pointer",
  },
};
