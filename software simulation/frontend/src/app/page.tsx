"use client";

import React, { useState } from "react";
import { useSimulationWebSocket } from "@/hooks/useSimulationWebSocket";
import { SceneViewport } from "@/components/scene/SceneViewport";
import { TelemetryPanel } from "@/components/telemetry/TelemetryPanel";
import { SimulationControls } from "@/components/controls/SimulationControls";
import { SignalAnalysisPanel } from "@/components/panels/SignalAnalysisPanel";
import { ExperimentLabPanel } from "@/components/panels/ExperimentLabPanel";
import { EMMaxwellLabPanel } from "@/components/panels/EMMaxwellLabPanel";

import {
  Compass,
  Activity,
  FlaskConical,
  Waves,
  Radio,
  Wifi,
  ShieldCheck,
  ShieldAlert,
  Sliders,
  Layers,
  Cpu
} from "lucide-react";

type ActiveTab = "MISSION_CONTROL" | "SIGNAL_ANALYSIS" | "EXPERIMENT_LAB" | "EM_MAXWELL_LAB";

export default function Home() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("MISSION_CONTROL");
  const { telemetry, diagnostics, isConnected, error, sendCommand } = useSimulationWebSocket();

  return (
    <div className="flex flex-col h-screen w-screen bg-[#070B12] text-slate-100 overflow-hidden font-sans">
      {/* Top Aerospace Telemetry Banner */}
      <header className="h-14 bg-slate-900/90 border-b border-slate-800 flex items-center justify-between px-5 z-20 shrink-0">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-cyan-950/60 rounded-lg border border-cyan-500/40 text-cyan-400">
            <Radio className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-bold text-sm text-cyan-400 tracking-wider font-mono">EC261</span>
              <span className="text-slate-400 text-xs font-mono">/</span>
              <span className="font-bold text-sm text-slate-200">UAV RF Direction Finding Digital Twin</span>
            </div>
            <div className="text-[10px] text-slate-400 font-mono">
              IIIT Vadodara – International Campus Diu | Switched-Interferometric SDR Array
            </div>
          </div>
        </div>

        {/* Tab Navigation Navigation */}
        <div className="flex items-center space-x-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs font-mono">
          <button
            onClick={() => setActiveTab("MISSION_CONTROL")}
            className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all ${
              activeTab === "MISSION_CONTROL"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Compass className="w-3.5 h-3.5 mr-1" />
            <span>3D Mission Control</span>
          </button>

          <button
            onClick={() => setActiveTab("SIGNAL_ANALYSIS")}
            className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all ${
              activeTab === "SIGNAL_ANALYSIS"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Activity className="w-3.5 h-3.5 mr-1" />
            <span>Signal Analysis</span>
          </button>

          <button
            onClick={() => setActiveTab("EXPERIMENT_LAB")}
            className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all ${
              activeTab === "EXPERIMENT_LAB"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <FlaskConical className="w-3.5 h-3.5 mr-1" />
            <span>Experiment Lab</span>
          </button>

          <button
            onClick={() => setActiveTab("EM_MAXWELL_LAB")}
            className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all ${
              activeTab === "EM_MAXWELL_LAB"
                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Waves className="w-3.5 h-3.5 mr-1" />
            <span>EM & Multi-Radar Lab</span>
          </button>
        </div>

        {/* Live System Diagnostics / Connection Status */}
        <div className="flex items-center space-x-4 text-xs font-mono">
          {telemetry && (
            <div className="flex items-center space-x-2 text-[11px]">
              <span className="text-slate-400">Hop:</span>
              <span className="text-cyan-400 font-bold">{telemetry.rf.active_freq_mhz.toFixed(1)} MHz</span>
              <span className="text-slate-500">|</span>
              <span className="text-slate-400">SNR:</span>
              <span className="text-emerald-400 font-bold">{telemetry.rf.snr_db.toFixed(0)} dB</span>
            </div>
          )}

          <div className="flex items-center space-x-2 pl-3 border-l border-slate-800">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                isConnected ? "bg-emerald-400 shadow-[0_0_8px_#10B981]" : "bg-red-400 animate-pulse"
              }`}
            />
            <span className={isConnected ? "text-emerald-400 text-xs" : "text-red-400 text-xs"}>
              {isConnected ? "WEBSOCKET LIVE" : "DISCONNECTED"}
            </span>
          </div>
        </div>
      </header>

      {/* Main Interactive Workspace */}
      <main className="flex-1 overflow-hidden p-3">
        {activeTab === "MISSION_CONTROL" && (
          <div className="flex h-full w-full gap-3">
            {/* LEFT: 65% Interactive 3D Viewport */}
            <div className="w-[65%] h-full">
              <SceneViewport telemetry={telemetry} onCommand={sendCommand} />
            </div>

            {/* RIGHT: 35% Telemetry, Compass Rose & Controls */}
            <div className="w-[35%] h-full flex flex-col justify-between space-y-3">
              <div className="flex-1 overflow-y-auto">
                <TelemetryPanel telemetry={telemetry} />
              </div>
              <div className="shrink-0">
                <SimulationControls telemetry={telemetry} onCommand={sendCommand} />
              </div>
            </div>
          </div>
        )}

        {activeTab === "SIGNAL_ANALYSIS" && (
          <div className="h-full w-full overflow-y-auto">
            <SignalAnalysisPanel diagnostics={diagnostics} telemetry={telemetry} />
          </div>
        )}

        {activeTab === "EXPERIMENT_LAB" && (
          <div className="h-full w-full overflow-y-auto">
            <ExperimentLabPanel />
          </div>
        )}

        {activeTab === "EM_MAXWELL_LAB" && (
          <div className="h-full w-full overflow-y-auto">
            <EMMaxwellLabPanel />
          </div>
        )}
      </main>

      {/* Bottom Status Bar */}
      <footer className="h-7 bg-slate-950 border-t border-slate-800/80 flex items-center justify-between px-4 text-[10px] font-mono text-slate-500 shrink-0">
        <div>
          <span>Antenna: 4-Element UCA (r=7.2 cm)</span>
          <span className="mx-2">|</span>
          <span>Switch: HMC241 SP4T (GaAs)</span>
          <span className="mx-2">|</span>
          <span>ADC: RTL-SDR 2.0 MS/s</span>
        </div>
        <div>
          <span>DSP: Radix-2 FFT → Covariance R_xx → Jacobi EVD → Multipath Gate (γ=8.0) → MUSIC</span>
        </div>
      </footer>
    </div>
  );
}

