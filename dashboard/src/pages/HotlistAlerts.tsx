import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { useWebSocket } from "../hooks/useWebSocket";
import type { AlertEvent, OperatorProfile, RecentEventsResponse, WsEvent } from "../types/navigation";

const EVENTS_ENDPOINT = "/navigation/events/recent?event_type=ALERT&limit=25";

function isAlertEvent(event: WsEvent | AlertEvent): event is AlertEvent {
  return event.event === "ALERT";
}

function alertId(alert: AlertEvent): string {
  return `${alert.track_id}:${alert.camera_id}:${alert.timestamp}:${alert.plate}`;
}

function dedupeAlerts(alerts: AlertEvent[]): AlertEvent[] {
  const seen = new Set<string>();
  const deduped: AlertEvent[] = [];
  for (const alert of alerts) {
    const key = alertId(alert);
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(alert);
  }
  return deduped;
}

function formatAlertTime(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function priorityColor(priority: string): string {
  const normalized = priority.trim().toUpperCase();
  if (normalized === "HIGH") return "#ef4444";
  if (normalized === "MED" || normalized === "MEDIUM") return "#f59e0b";
  return "#64748b";
}

export default function HotlistAlerts() {
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const profileQuery = useQuery<OperatorProfile>({
    queryKey: ["operator-profile"],
    queryFn: async () => {
      const res = await fetch("/navigation/operator-profile");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<OperatorProfile>;
    },
    staleTime: 30_000,
  });

  const { data, isLoading, error } = useQuery<RecentEventsResponse>({
    queryKey: ["hotlist-alerts"],
    queryFn: async () => {
      const res = await fetch(EVENTS_ENDPOINT);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<RecentEventsResponse>;
    },
    refetchInterval: (profileQuery.data?.hotlist_refresh_sec ?? 60) * 1000,
  });

  useEffect(() => {
    const incoming = (data?.events ?? []).filter(isAlertEvent);
    if (incoming.length === 0) return;
    setAlerts(dedupeAlerts(incoming));
  }, [data]);

  useWebSocket(
    useCallback((event: WsEvent) => {
      if (!isAlertEvent(event)) return;
      setAlerts((prev) => dedupeAlerts([event, ...prev]).slice(0, 25));
      setSelectedId((prev) => prev ?? alertId(event));
    }, []),
  );

  useEffect(() => {
    if (alerts.length > 0 && !selectedId) {
      setSelectedId(alertId(alerts[0]));
    }
  }, [alerts, selectedId]);

  const selected = useMemo(
    () => alerts.find((alert) => alertId(alert) === selectedId) ?? null,
    [alerts, selectedId],
  );

  return (
    <div style={S.page}>
      <div style={S.layout}>
        <div style={S.listPanel}>
          <div style={S.listHeader}>
            <h2 style={S.title}>Active Hotlist Alerts</h2>
            <span style={S.countBadge}>{alerts.length}</span>
          </div>

          {isLoading && alerts.length === 0 && <p style={S.infoText}>Loading recent alerts...</p>}
          {error instanceof Error && <p style={S.errorText}>Unable to load recent alerts: {error.message}</p>}
          {!isLoading && alerts.length === 0 && <p style={S.infoText}>No live hotlist alerts have been published yet.</p>}

          <div style={S.alertStack}>
            {alerts.map((alert) => {
              const id = alertId(alert);
              return (
                <button
                  key={id}
                  style={{
                    ...S.alertCard,
                    borderLeft: `4px solid ${priorityColor(alert.priority)}`,
                    background: id === selectedId ? "rgba(37,99,235,0.12)" : "rgba(15,23,42,0.9)",
                  }}
                  onClick={() => setSelectedId(id)}
                >
                  <div style={S.alertTop}>
                    <span style={S.plate}>{alert.plate}</span>
                    <div style={S.alertRight}>
                      <span style={{ ...S.levelBadge, background: priorityColor(alert.priority) }}>
                        {alert.priority.toUpperCase()}
                      </span>
                      <span style={S.timeAgo}>{formatAlertTime(alert.timestamp)}</span>
                    </div>
                  </div>
                  <div style={S.alertInfo}>
                    <span style={S.reason}>{alert.reason}</span>
                    <span style={S.dot}>|</span>
                    <span style={S.camera}>{alert.camera_id}</span>
                  </div>
                  <div style={S.vehicleDesc}>
                    Vehicle class: {alert.vehicle_class ?? "Unknown"} | Confidence: {(alert.confidence * 100).toFixed(0)}%
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div style={S.detailPanel}>
          {selected ? (
            <>
              <div style={S.detailHeader}>
                <span style={{ ...S.levelBadge, ...S.detailBadge, background: priorityColor(selected.priority) }}>
                  {selected.priority.toUpperCase()} PRIORITY
                </span>
                <span style={S.detailTime}>{formatAlertTime(selected.timestamp)}</span>
              </div>

              <div style={S.detailPlate}>{selected.plate}</div>
              <div style={S.detailReason}>{selected.reason}</div>

              <div style={S.detailGrid}>
                <DRow label="Camera" value={selected.camera_id} />
                <DRow label="Track" value={String(selected.track_id)} />
                <DRow label="Vehicle class" value={selected.vehicle_class ?? "Unknown"} />
                <DRow label="Confidence" value={`${(selected.confidence * 100).toFixed(0)}%`} />
              </div>

              <div style={S.notesBox}>
                <span style={S.notesLabel}>Operator Guidance</span>
                <p style={S.notesText}>
                  This panel reflects live hotlist alert events from the edge runtime. Use the Navigation HUD to route to the scene and the Camera Ops page to review recent event context.
                </p>
              </div>
            </>
          ) : (
            <div style={S.emptyDetail}>
              <div style={S.emptyIcon}>ALRT</div>
              <p style={S.emptyText}>Select an alert to inspect the live event details.</p>
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
  infoText: {
    color: "#94a3b8",
    fontSize: "0.85rem",
  },
  errorText: {
    color: "#f87171",
    fontSize: "0.85rem",
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
  emptyDetail: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
    gap: "12px",
  },
  emptyIcon: {
    fontSize: "1.4rem",
    fontWeight: 800,
    color: "#334155",
    letterSpacing: "0.12em",
  },
  emptyText: {
    color: "#475569",
    fontSize: "0.9rem",
    textAlign: "center",
  },
};
