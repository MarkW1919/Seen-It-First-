import { useState, useEffect, useRef, useCallback } from "react";

interface GeoPosition {
  latitude: number;
  longitude: number;
  accuracy: number;
  heading: number | null;
  speed: number | null;
  timestamp: number;
}

export function useGeolocation(enabled: boolean = true) {
  const [position, setPosition] = useState<GeoPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const watchId = useRef<number | null>(null);

  const startWatching = useCallback(() => {
    if (!navigator.geolocation) {
      setError("Geolocation not supported");
      return;
    }

    watchId.current = navigator.geolocation.watchPosition(
      (pos) => {
        setPosition({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          heading: pos.coords.heading,
          speed: pos.coords.speed,
          timestamp: pos.timestamp,
        });
        setError(null);
      },
      (err) => {
        setError(err.message);
      },
      {
        enableHighAccuracy: true,
        maximumAge: 5000,
        timeout: 10000,
      }
    );
  }, []);

  const stopWatching = useCallback(() => {
    if (watchId.current !== null) {
      navigator.geolocation.clearWatch(watchId.current);
      watchId.current = null;
    }
  }, []);

  useEffect(() => {
    if (enabled) {
      startWatching();
    } else {
      stopWatching();
    }
    return stopWatching;
  }, [enabled, startWatching, stopWatching]);

  return { position, error };
}
