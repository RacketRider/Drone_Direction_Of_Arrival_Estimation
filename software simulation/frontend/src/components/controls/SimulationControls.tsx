"use client";

import React, { useState } from "react";
import { Play, Pause, StepForward, RotateCcw, Sliders, Zap, Download } from "lucide-react";
import { TelemetryFrame } from "@/types/telemetry";

interface SimulationControlsProps {
  telemetry: TelemetryFrame | null;
  onCommand: (cmd: object) => void;
}

export function SimulationControls({ telemetry, onCommand }: SimulationControlsProps) {
  const [speed, setSpeed] = useState<number>(1.0);
  const [snr, setSnr] = useState<number>(15.0);
  const [trajectory, setTrajectory] = useState<string>("FIGURE_EIGHT");
  const [receiverMode, setReceiverMode] = useState<string>("MODE_B_SWITCHED");
  const [trackerType, setTrackerType] = useState<string>("GATED_HOLD");
  const [gateTh, setGateTh] = useState<number>(8.0);
  const [isPlaying, setIsPlaying] = useState<boolean>(true);

  const handlePlayPause = () => {
    if (isPlaying) {
      onCommand({ action: "PAUSE" });
      setIsPlaying(false);
    } else {
      onCommand({ action: "PLAY" });
      setIsPlaying(true);
    }
  };

  const handleStep = () => {
    onCommand({ action: "STEP" });
    setIsPlaying(false);
  };

  const handleReset = () => {
    onCommand({ action: "RESET" });
    setIsPlaying(false);
  };

  const handleSpeedChange = (val: number) => {
    setSpeed(val);
    onCommand({ action: "SET_SPEED", speed_multiplier: val });
  };

  const handleSnrChange = (val: number) => {
    setSnr(val);
    onCommand({ action: "SET_SNR", snr_db: val });
  };

  const handleTrajectoryChange = (val: string) => {
    setTrajectory(val);
    onCommand({ action: "SET_TRAJECTORY", trajectory: val });
  };

  const handleReceiverModeChange = (val: "MODE_A_SIMULTANEOUS" | "MODE_B_SWITCHED") => {
    setReceiverMode(val);
    onCommand({ action: "SET_RECEIVER_MODE", receiver_mode: val });
  };

  const handleTrackerChange = (val: "GATED_HOLD" | "KALMAN_FILTER") => {
    setTrackerType(val);
    onCommand({ action: "SET_TRACKER_TYPE", tracker_type: val });
  };

  const handleGateThChange = (val: number) => {
    setGateTh(val);
    onCommand({ action: "SET_GATE_THRESHOLD", gate_threshold: val });
  };

  return (
    <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 text-xs font-mono">
      {/* Top Playback Control Row */}
      <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-slate-800">
        <div className="flex items-center space-x-2">
          <button
            onClick={handlePlayPause}
            className={`px-3 py-1.5 rounded-lg flex items-center space-x-1.5 font-bold transition-all shadow-md ${
              isPlaying
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40 hover:bg-amber-500/30"
                : "bg-cyan-500 text-slate-950 hover:bg-cyan-400 font-bold"
            }`}
          >
            {isPlaying ? <Pause className="w-4 h-4 mr-1" /> : <Play className="w-4 h-4 mr-1 fill-current" />}
            <span>{isPlaying ? "Pause" : "Run Live"}</span>
          </button>

          <button
            onClick={handleStep}
            className="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 flex items-center"
            title="Step One Burst (128 us)"
          >
            <StepForward className="w-3.5 h-3.5 mr-1 text-cyan-400" />
            <span>Step Burst</span>
          </button>

          <button
            onClick={handleReset}
            className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 border border-slate-700"
            title="Reset Simulation Clock"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>

          <a
            href="http://localhost:8000/api/export.xlsx"
            download="ec261_uav_telemetry.xlsx"
            className="px-2.5 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 flex items-center transition-colors"
            title="Export Excel flight dataset"
          >
            <Download className="w-3.5 h-3.5 mr-1 text-emerald-400" />
            <span>Export .xlsx</span>
          </a>
        </div>

        <div className="text-[11px] text-slate-400 font-mono">
          Sim Time: <span className="text-cyan-400 font-bold">{telemetry?.sim_time?.toFixed(2) ?? "0.00"}s</span>
        </div>
      </div>

      {/* Sliders & Parameter Selectors */}
      <div className="grid grid-cols-2 gap-3 text-[11px]">
        {/* Speed Slider */}
        <div>
          <label htmlFor="uav-speed-multiplier" className="flex justify-between text-slate-400 mb-1 cursor-pointer">
            <span>UAV Speed Multiplier:</span>
            <span className="text-cyan-400 font-bold">{speed.toFixed(2)}x</span>
          </label>
          <input
            id="uav-speed-multiplier"
            name="uav_speed_multiplier"
            type="range"
            min="0.25"
            max="4.0"
            step="0.25"
            value={speed}
            onChange={(e) => handleSpeedChange(parseFloat(e.target.value))}
            className="w-full accent-cyan-400 h-1.5 bg-slate-700 rounded-lg cursor-pointer"
          />
        </div>

        {/* SNR Slider */}
        <div>
          <label htmlFor="channel-snr-db" className="flex justify-between text-slate-400 mb-1 cursor-pointer">
            <span>Channel SNR:</span>
            <span className="text-emerald-400 font-bold">{snr.toFixed(0)} dB</span>
          </label>
          <input
            id="channel-snr-db"
            name="channel_snr_db"
            type="range"
            min="-5"
            max="30"
            step="1"
            value={snr}
            onChange={(e) => handleSnrChange(parseFloat(e.target.value))}
            className="w-full accent-emerald-400 h-1.5 bg-slate-700 rounded-lg cursor-pointer"
          />
        </div>

        {/* Trajectory Dropdown */}
        <div>
          <label htmlFor="flight-trajectory-select" className="text-slate-400 block mb-1">
            Flight Trajectory:
          </label>
          <select
            id="flight-trajectory-select"
            name="flight_trajectory"
            value={trajectory}
            onChange={(e) => handleTrajectoryChange(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded px-2 py-1 outline-none text-xs"
          >
            <option value="FIGURE_EIGHT">Figure-Eight (Gerono)</option>
            <option value="S_CURVE">S-Curve Slalom</option>
            <option value="CIRCULAR_ORBIT">Circular 360° Orbit</option>
            <option value="WAYPOINT_PATH">Tactical Waypoint Path</option>
          </select>
        </div>

        {/* Receiver Mode Dropdown */}
        <div>
          <label htmlFor="receiver-mode-select" className="text-slate-400 block mb-1">
            Receiver Mode:
          </label>
          <select
            id="receiver-mode-select"
            name="receiver_mode"
            value={receiverMode}
            onChange={(e) => handleReceiverModeChange(e.target.value as any)}
            className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded px-2 py-1 outline-none text-xs"
          >
            <option value="MODE_B_SWITCHED">Mode B: Switched HMC241 (1 SDR)</option>
            <option value="MODE_A_SIMULTANEOUS">Mode A: Simultaneous (4 SDRs)</option>
          </select>
        </div>

        {/* Tracker Type */}
        <div>
          <label htmlFor="tracking-engine-select" className="text-slate-400 block mb-1">
            Tracking Engine:
          </label>
          <select
            id="tracking-engine-select"
            name="tracking_engine"
            value={trackerType}
            onChange={(e) => handleTrackerChange(e.target.value as any)}
            className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded px-2 py-1 outline-none text-xs"
          >
            <option value="GATED_HOLD">Gated Hold (Baseline)</option>
            <option value="KALMAN_FILTER">Circular Kalman Filter</option>
          </select>
        </div>

        {/* Gate Threshold */}
        <div>
          <label htmlFor="gate-threshold-slider" className="flex justify-between text-slate-400 mb-1 cursor-pointer">
            <span>Gate Threshold γ_th:</span>
            <span className="text-amber-400 font-bold">{gateTh.toFixed(1)}</span>
          </label>
          <input
            id="gate-threshold-slider"
            name="gate_threshold"
            type="range"
            min="4.0"
            max="18.0"
            step="0.5"
            value={gateTh}
            onChange={(e) => handleGateThChange(parseFloat(e.target.value))}
            className="w-full accent-amber-400 h-1.5 bg-slate-700 rounded-lg cursor-pointer"
          />
        </div>
      </div>
    </div>
  );
}

