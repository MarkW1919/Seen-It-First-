import { useCallback, useEffect, useRef } from "react";
import type { WsEvent } from "../types/navigation";

const WS_URL = "/ws";
const RECONNECT_DELAY_MS = 3000;

export function useWebSocket(onEvent: (ev: WsEvent) => void, enabled = true) {
  const wsRef = useRef<WebSocket | null>(null);
  const onEventRef = useRef(onEvent);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  onEventRef.current = onEvent;

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${window.location.host}${WS_URL}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.info("[WS] Connected");
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };

    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as WsEvent;
        onEventRef.current(data);
      } catch {
        // Ignore malformed frames.
      }
    };

    ws.onclose = () => {
      console.info("[WS] Disconnected - reconnecting in %dms", RECONNECT_DELAY_MS);
      if (mountedRef.current) {
        reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect, enabled]);
}
