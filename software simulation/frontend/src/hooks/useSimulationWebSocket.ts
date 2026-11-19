"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { TelemetryFrame, SignalDiagnosticsFrame } from "@/types/telemetry";

export function useSimulationWebSocket(serverUrl: string = "ws://localhost:8000/ws/telemetry") {
  const [telemetry, setTelemetry] = useState<TelemetryFrame | null>(null);
  const [diagnostics, setDiagnostics] = useState<SignalDiagnosticsFrame | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(serverUrl);
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
        setError("WebSocket connection failed. Is the Python backend running?");
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Automatic reconnection every 2.0 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, 2000);
      };
    } catch (err: any) {
      setError(err?.message || "Failed to establish WebSocket");
    }
  }, [serverUrl]);

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

