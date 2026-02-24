import { useEffect, useRef, useCallback } from "react";
import { useAppStore } from "../store";
import type { WSMessage, WSAlert, HotListAlert } from "../types";

const WS_RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 15000];

// Reuse a single AudioContext across the lifetime of the app to avoid
// creating a new heavyweight context on every alert (blocks UI thread)
let sharedAudioCtx: AudioContext | null = null;

function getAudioContext(): AudioContext | null {
  try {
    if (!sharedAudioCtx || sharedAudioCtx.state === "closed") {
      sharedAudioCtx = new AudioContext();
    }
    // Resume if suspended (browser autoplay policy)
    if (sharedAudioCtx.state === "suspended") {
      sharedAudioCtx.resume();
    }
    return sharedAudioCtx;
  } catch {
    return null;
  }
}

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<number>();
  const connectRef = useRef<() => void>();
  const token = useAppStore((s) => s.token);
  const addAlert = useAppStore((s) => s.addAlert);
  const alertSoundEnabled = useAppStore((s) => s.alertSoundEnabled);
  const alertVibrationEnabled = useAppStore((s) => s.alertVibrationEnabled);

  // Track recently seen alert IDs to deduplicate at the WS layer
  const recentAlertIds = useRef<Set<string>>(new Set());

  const playAlertSound = useCallback(() => {
    if (!alertSoundEnabled) return;
    const ctx = getAudioContext();
    if (!ctx) return;

    try {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      osc.type = "square";
      gain.gain.value = 0.3;
      osc.start();
      osc.stop(ctx.currentTime + 0.3);
      setTimeout(() => {
        try {
          const osc2 = ctx.createOscillator();
          const gain2 = ctx.createGain();
          osc2.connect(gain2);
          gain2.connect(ctx.destination);
          osc2.frequency.value = 1100;
          osc2.type = "square";
          gain2.gain.value = 0.3;
          osc2.start();
          osc2.stop(ctx.currentTime + 0.5);
        } catch {
          // Audio playback error on second tone
        }
      }, 300);
    } catch {
      // Audio not available
    }
  }, [alertSoundEnabled]);

  const vibrateAlert = useCallback(() => {
    if (!alertVibrationEnabled) return;
    if ("vibrate" in navigator) {
      navigator.vibrate([200, 100, 200, 100, 400]);
    }
  }, [alertVibrationEnabled]);

  const connect = useCallback(() => {
    if (!token?.access_token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws?token=${token.access_token}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      reconnectAttempt.current = 0;
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);

        if (msg.type === "hotlist_alert") {
          const alertMsg = msg as WSAlert;

          // Deduplicate at the WS message layer — skip if we already processed this alert ID
          if (recentAlertIds.current.has(alertMsg.alert_id)) {
            return;
          }
          recentAlertIds.current.add(alertMsg.alert_id);
          // Cap the set size to prevent unbounded growth
          if (recentAlertIds.current.size > 500) {
            const iter = recentAlertIds.current.values();
            for (let i = 0; i < 250; i++) {
              recentAlertIds.current.delete(iter.next().value as string);
            }
          }

          const alert: HotListAlert = {
            id: alertMsg.alert_id,
            hotlist_entry_id: alertMsg.hotlist_entry_id,
            detection_id: null,
            plate_text_matched: alertMsg.plate_text,
            match_confidence: alertMsg.confidence,
            latitude: alertMsg.location.lat ?? null,
            longitude: alertMsg.location.lng ?? null,
            address: alertMsg.location.address ?? null,
            status: "new",
            acknowledged_at: null,
            resolved_at: null,
            notes: null,
            created_at: alertMsg.timestamp,
            hotlist_entry: null,
          };

          // Update store first (synchronous, fast)
          addAlert(alert);

          // Defer audio/vibration/notification to next microtask so we don't
          // block the WebSocket message handler on the UI thread
          queueMicrotask(() => {
            playAlertSound();
            vibrateAlert();

            // Show system notification
            if (
              "Notification" in window &&
              Notification.permission === "granted"
            ) {
              new Notification("HOT LIST MATCH", {
                body: `Plate: ${alertMsg.plate_text}\nConfidence: ${(alertMsg.confidence * 100).toFixed(0)}%`,
                icon: "/icons/icon-192.png",
                tag: alertMsg.alert_id,
                requireInteraction: true,
              });
            }
          });
        }
      } catch {
        // Skip invalid messages
      }
    };

    ws.onclose = () => {
      const delay =
        WS_RECONNECT_DELAYS[
          Math.min(reconnectAttempt.current, WS_RECONNECT_DELAYS.length - 1)
        ];
      reconnectTimer.current = window.setTimeout(() => {
        reconnectAttempt.current++;
        connectRef.current?.();
      }, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [token, addAlert, playAlertSound, vibrateAlert]);

  // Keep connectRef in sync with the latest connect callback
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    // Request notification permission
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }

    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendMessage = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  return { sendMessage };
}
