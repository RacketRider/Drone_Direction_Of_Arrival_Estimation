"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { TelemetryFrame, SignalDiagnosticsFrame } from "@/types/telemetry";

/**
 * Dynamically resolves the WebSocket URL for local development or production.
 * In production (HTTPS), automatically upgrades to wss:// and uses same-origin host.
 */
function getDefaultWsUrl(): string {
  if (typeof window === "undefined") return "";
  const isHttps = window.location.protocol === "https:";
  const wsProtocol = isHttps ? "wss:" : "ws:";
  const host = process.env.NEXT_PUBLIC_WS_HOST || window.location.host;
  return `${wsProtocol}//${host}/ws/telemetry`;
}

export function useSimulationWebSocket(customServerUrl?: string) {
  const [telemetry, setTelemetry] = useState<TelemetryFrame | null>(null);
  const [diagnostics, setDiagnostics] = useState<SignalDiagnosticsFrame | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    try {
      const targetUrl = customServerUrl || getDefaultWsUrl();
      if (!targetUrl) return;

      const ws = new WebSocket(targetUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "telemetry") {
            setTelemetry(data);
          } else if (data.type === "signal_diagnostics") {
            setDiagnostics(data);
          }
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      ws.onerror = (evt) => {
        setError("WebSocket connection failed. Ensure backend service is reachable.");
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Automatic reconnection attempt every 2.0 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 2000);
      };
    } catch (err: any) {
      setError(err?.message || "Failed to establish WebSocket");
    }
  }, [customServerUrl]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const sendCommand = useCallback((command: object) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(command));
    }
  }, []);

  return {
    telemetry,
    diagnostics,
    isConnected,
    error,
    sendCommand
  };
}
