import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { useWebSocket } from "../hooks/useWebSocket";
import type {
  AlertEvent,
  DetectionEvent,
  RecentEventsResponse,
  RuntimeStatusResponse,
  WsEvent,
} from "../types/navigation";

type OpsEvent = {
  id: string;
  type: "ALERT" | "DETECTION";
  plate: string;
  vehicle: string;
  camera: string;
  confidenceText: string;
  timestamp: number;
  detailLines: Array<{ label: string; value: string }>;
};

function isOpsEvent(event: WsEvent): event is AlertEvent | DetectionEvent {
  return event.event === "ALERT" || event.event === "DETECTION";
}

function formatClock(timestamp: number): string {
  return new Date(timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function normalizeEvent(event: AlertEvent | DetectionEvent): OpsEvent {
  if (event.event === "ALERT") {
    return {
      id: `alert:${event.track_id}:${event.camera_id}:${event.timestamp}:${event.plate}`,
      type: "ALERT",
      plate: event.plate,
      vehicle: event.vehicle_class ?? "Unknown vehicle",
      camera: event.camera_id,
      confidenceText: `${(event.confidence * 100).toFixed(0)}%`,
      timestamp: event.timestamp,
      detailLines: [
        { label: "Priority", value: event.priority.toUpperCase() },
        { label: "Reason", value: event.reason },
        { label: "Track", value: String(event.track_id) },
        { label: "Camera", value: event.camera_id },
      ],
    };
  }

  const vehicleBits = [event.color, event.make, event.model].filter(Boolean).join(" ") || (event.vehicle_class ?? "Unknown vehicle");
  return {
    id: `detection:${event.track_id}:${event.camera_id}:${event.timestamp}`,
    type: "DETECTION",
    plate: event.plate_text ?? "No plate",
    vehicle: vehicleBits,
    camera: event.camera_id,
    confidenceText: `${Math.round((event.plate_conf ?? event.vehicle_conf ?? 0) * 100)}%`,
    timestamp: event.timestamp,
    detailLines: [
      { label: "Track", value: String(event.track_id) },
      { label: "Vehicle class", value: event.vehicle_class ?? "Unknown" },
      { label: "Year range", value: event.year_range ?? "Unknown" },
      { label: "Fingerprint", value: event.fingerprint ?? "Unavailable" },
      { label: "Composite path", value: event.composite_path ?? "Unavailable" },
      { label: "Plate crop", value: event.plate_path ?? "Unavailable" },
    ],
  };
}

export default function CameraViews() {
  const [events, setEvents] = useState<OpsEvent[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const runtimeQuery = useQuery<RuntimeStatusResponse>({
    queryKey: ["runtime-status"],
    queryFn: async () => {
      const res = await fetch("/navigation/runtime");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<RuntimeStatusResponse>;
    },
    refetchInterval: 5_000,
  });

  const eventsQuery = useQuery<RecentEventsResponse>({
    queryKey: ["recent-ops-events"],
    queryFn: async () => {
      const res = await fetch("/navigation/events/recent?limit=25");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json() as Promise<RecentEventsResponse>;
    },
    refetchInterval: 15_000,
  });

  useEffect(() => {
    const incoming = (eventsQuery.data?.events ?? []).map(normalizeEvent);
    if (incoming.length === 0) return;
    setEvents((prev) => {
      const merged = [...incoming, ...prev];
      const seen = new Set<string>();
      return merged.filter((item) => {
        if (seen.has(item.id)) return false;
        seen.add(item.id);
        return true;
      }).slice(0, 25);
    });
  }, [eventsQuery.data]);

  useWebSocket(
    useCallback((event: WsEvent) => {
      if (!isOpsEvent(event)) return;
      const normalized = normalizeEvent(event);
      setEvents((prev) => {
        const merged = [normalized, ...prev];
        const seen = new Set<string>();
        return merged.filter((item) => {
          if (seen.has(item.id)) return false;
          seen.add(item.id);
          return true;
        }).slice(0, 25);
      });
      setSelectedId((prev) => prev ?? normalized.id);
    }, []),
  );

  useEffect(() => {
    if (events.length > 0 && !selectedId) {
      setSelectedId(events[0].id);
    }
  }, [events, selectedId]);

  const selectedEvent = useMemo(
    () => events.find((event) => event.id === selectedId) ?? null,
    [events, selectedId],
  );

  const cameras = runtimeQuery.data?.cameras ?? [];

  return (
    <div style={S.page}>
      <section style={S.section}>
        <div style={S.sectionHeader}>
          <h2 style={S.sectionTitle}>Camera Runtime</h2>
          <span style={S.statusLine}>
            Pipeline: {runtimeQuery.data?.pipeline_active ? "ACTIVE" : "IDLE"} | WS clients: {runtimeQuery.data?.ws_clients ?? 0}
          </span>
        </div>

        {runtimeQuery.isLoading && cameras.length === 0 && <p style={S.infoText}>Loading camera runtime...</p>}
        {runtimeQuery.error instanceof Error && <p style={S.errorText}>Unable to load camera runtime: {runtimeQuery.error.message}</p>}

        <div style={S.camGrid}>
          {cameras.map((camera) => (
            <div key={camera.camera_id} style={S.camCard}>
              <div style={S.camHeader}>
                <strong style={S.camName}>{camera.name}</strong>
                <StatusBadge online={camera.status === "Online"} />
              </div>
              <div style={S.camMetrics}>
                <Metric label="Camera ID" value={camera.camera_id} />
                <Metric label="FPS" value={camera.fps.toFixed(1)} />
                <Metric label="Queue" value={String(camera.queue_depth)} />
                <Metric label="Last frame" value={camera.last_frame_age_s === null ? "n/a" : `${camera.last_frame_age_s.toFixed(1)}s`} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <section style={S.section}>
        <h3 style={S.subTitle}>Recent Operations Events</h3>
        {eventsQuery.isLoading && events.length === 0 && <p style={S.infoText}>Loading recent event history...</p>}
        {!eventsQuery.isLoading && events.length === 0 && <p style={S.infoText}>No recent detection or alert events are available yet.</p>}
        <div style={S.tableWrap}>
          <table style={S.table}>
            <thead>
              <tr>
                <th>Time</th>
                <th>Type</th>
                <th>Plate</th>
                <th>Vehicle</th>
                <th>Camera</th>
                <th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr
                  key={event.id}
                  style={{
                    cursor: "pointer",
                    background: event.id === selectedId ? "rgba(37,99,235,0.15)" : undefined,
                  }}
                  onClick={() => setSelectedId(event.id)}
                >
                  <td>{formatClock(event.timestamp)}</td>
                  <td>{event.type}</td>
                  <td style={S.plateCell}>{event.plate}</td>
                  <td>{event.vehicle}</td>
                  <td>{event.camera}</td>
                  <td>{event.confidenceText}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section style={S.detailPanel}>
        <h3 style={S.subTitle}>Selected Event Detail</h3>
        {selectedEvent ? (
          <div style={S.detailGrid}>
            {selectedEvent.detailLines.map((line) => (
              <DetailItem key={`${selectedEvent.id}:${line.label}`} label={line.label} value={line.value} />
            ))}
          </div>
        ) : (
          <p style={S.infoText}>Select an event to inspect recent runtime detail.</p>
        )}
      </section>
    </div>
  );
}

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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div style={S.metric}>
      <span style={S.metricLabel}>{label}</span>
      <strong style={S.metricValue}>{value}</strong>
    </div>
  );
}

function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div style={S.detailItem}>
      <span style={S.detailLabel}>{label}</span>
      <strong style={{ color: "#e8edf5", wordBreak: "break-word" }}>{value}</strong>
    </div>
  );
}

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
  sectionHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "1rem",
    marginBottom: "0.6rem",
  },
  sectionTitle: {
    margin: 0,
    fontSize: "1rem",
    fontWeight: 700,
    color: "#e8edf5",
  },
  statusLine: {
    color: "#94a3b8",
    fontSize: "0.78rem",
  },
  subTitle: {
    margin: "0 0 0.5rem",
    fontSize: "0.9rem",
    fontWeight: 600,
    color: "#cbd5e1",
  },
  infoText: {
    color: "#94a3b8",
    fontSize: "0.84rem",
  },
  errorText: {
    color: "#f87171",
    fontSize: "0.84rem",
  },
  camGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "8px",
  },
  camCard: {
    border: "1px solid #1e293b",
    borderRadius: "10px",
    padding: "0.85rem",
    background: "#0c1220",
  },
  camHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: "0.75rem",
    marginBottom: "0.65rem",
  },
  camName: {
    color: "#e8edf5",
  },
  camMetrics: {
    display: "grid",
    gridTemplateColumns: "repeat(2, 1fr)",
    gap: "0.5rem",
  },
  metric: {
    border: "1px solid #1e293b",
    borderRadius: "8px",
    padding: "0.5rem 0.65rem",
    background: "#111827",
    display: "flex",
    flexDirection: "column",
    gap: "2px",
  },
  metricLabel: {
    color: "#64748b",
    fontSize: "0.65rem",
    textTransform: "uppercase",
    letterSpacing: "0.08em",
    fontWeight: 600,
  },
  metricValue: {
    color: "#e8edf5",
  },
  tableWrap: {
    overflowX: "auto",
    border: "1px solid #1e293b",
    borderRadius: "10px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    minWidth: 720,
  },
  plateCell: {
    fontFamily: "'SF Mono', 'Fira Code', monospace",
    fontWeight: 700,
    color: "#e8edf5",
  },
  detailPanel: {
    background: "#0c1220",
    border: "1px solid #1e293b",
    borderRadius: "12px",
    padding: "0.85rem",
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
};
