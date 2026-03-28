import React from "react";

interface Props {
  gpsLocked:       boolean;
  wsConnected:     boolean;
  pipelineActive:  boolean;
  fps:             number;
  cameraCount:     number;
  detectionCount:  number;
  alertCount:      number;
  navigating:      boolean;
  gpuTempC?:       number;
}

function Dot({ on, color }: { on: boolean; color: string }) {
  return (
    <span style={{
      display: "inline-block",
      width: 7,
      height: 7,
      borderRadius: "50%",
      background: on ? color : "#1e3a5f",
      flexShrink: 0,
    }} />
  );
}

function Item({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "5px",
      padding: "0 10px",
      borderRight: "1px solid #1e3a5f",
    }}>
      {children}
    </div>
  );
}

const label: React.CSSProperties = {
  fontSize: "0.6rem",
  color: "#475569",
  letterSpacing: "0.06em",
  fontFamily: "monospace",
};

const val: React.CSSProperties = {
  fontSize: "0.65rem",
  fontWeight: 700,
  color: "#94a3b8",
  fontFamily: "monospace",
};

export function StatusBar(p: Props) {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      height: 28,
      background: "#060c1a",
      borderTop: "1px solid #1e3a5f",
      flexShrink: 0,
      overflowX: "auto" as const,
    }}>
      <Item>
        <Dot on={p.gpsLocked} color="#22c55e" />
        <span style={label}>GPS</span>
        <span style={val}>{p.gpsLocked ? "LOCKED" : "SEARCHING"}</span>
      </Item>

      <Item>
        <Dot on={p.wsConnected} color="#22c55e" />
        <span style={label}>SERVER</span>
        <span style={val}>{p.wsConnected ? "CONNECTED" : "OFFLINE"}</span>
      </Item>

      <Item>
        <Dot on={p.pipelineActive} color={p.pipelineActive ? "#22c55e" : "#f59e0b"} />
        <span style={label}>LPR</span>
        <span style={{ ...val, color: p.pipelineActive ? "#22c55e" : "#f59e0b" }}>
          {p.pipelineActive ? "ACTIVE" : "IDLE"}
        </span>
      </Item>

      <Item>
        <Dot on={true} color="#3b82f6" />
        <span style={label}>FPS</span>
        <span style={val}>{p.fps}</span>
      </Item>

      <Item>
        <Dot on={p.cameraCount > 0} color="#3b82f6" />
        <span style={label}>CAMS</span>
        <span style={val}>{p.cameraCount} active</span>
      </Item>

      <Item>
        <Dot on={p.detectionCount > 0} color="#3b82f6" />
        <span style={label}>READS</span>
        <span style={val}>{p.detectionCount}</span>
      </Item>

      {p.alertCount > 0 && (
        <Item>
          <Dot on={true} color="#ef4444" />
          <span style={{ ...label, color: "#f87171" }}>ALERTS</span>
          <span style={{ ...val, color: "#f87171" }}>{p.alertCount}</span>
        </Item>
      )}

      {p.navigating && (
        <Item>
          <Dot on={true} color="#f59e0b" />
          <span style={{ ...label, color: "#fbbf24" }}>NAVIGATING</span>
        </Item>
      )}

      {p.gpuTempC !== undefined && (
        <Item>
          <Dot on={true} color={p.gpuTempC > 80 ? "#ef4444" : p.gpuTempC > 70 ? "#f59e0b" : "#22c55e"} />
          <span style={label}>GPU</span>
          <span style={val}>{p.gpuTempC}°C</span>
        </Item>
      )}

      <div style={{ flex: 1 }} />
      <div style={{ ...label, padding: "0 10px", color: "#1e3a5f" }}>
        SEEN-IT-FIRST v1.0 · Jetson Orin Nano Super
      </div>
    </div>
  );
}
