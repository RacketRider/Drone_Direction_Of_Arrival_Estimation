"use client";

import React from "react";
import { TelemetryFrame } from "@/types/telemetry";
import { CompassBearingDial } from "./CompassBearingDial";
import { Radio, ShieldAlert, ShieldCheck, Activity, Cpu, Wifi, AlertTriangle, Navigation, Crosshair } from "lucide-react";

interface TelemetryPanelProps {
  telemetry: TelemetryFrame | null;
}

export function TelemetryPanel({ telemetry }: TelemetryPanelProps) {
  if (!telemetry) {
    return (
      <div className="flex items-center justify-center h-full p-6 text-slate-500 font-mono text-xs">
        Connecting to RF telemetry stream...
      </div>
    );
  }

  const { uav, rf, hardware, dsp, multiradar } = telemetry;
  const isAccepted = dsp.is_accepted;
  const eigRatio = dsp.eigenvalue_ratio;

  return (
    <div className="flex flex-col space-y-3.5 h-full overflow-y-auto pr-1">
      {/* Top Status Header: Reliability Gate Status */}
      <div
        className={`p-3 rounded-xl border flex items-center justify-between ${
          isAccepted
            ? "bg-emerald-950/30 border-emerald-500/40 text-emerald-300"
            : "bg-red-950/30 border-red-500/40 text-red-300"
        }`}
      >
        <div className="flex items-center space-x-2.5">
          {isAccepted ? (
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
          ) : (
            <ShieldAlert className="w-5 h-5 text-red-400" />
          )}
          <div>
            <div className="text-[11px] font-mono tracking-wider uppercase opacity-75">
              Reliability Gate
            </div>
            <div className="text-sm font-bold font-mono">
              {dsp.gate_status}
            </div>
          </div>
        </div>

        <div className="text-right font-mono">
          <div className="text-[10px] text-slate-400">Ratio (λ₁/λ₂)</div>
          <div className="text-sm font-bold text-cyan-400">
            {eigRatio.toFixed(1)} <span className="text-[11px] text-slate-400">/ 8.0</span>
          </div>
        </div>
      </div>

      {/* 360 Azimuth Compass Rose */}
      <CompassBearingDial telemetry={telemetry} />

      {/* Primary RF & DoA Readout Grid */}
      <div className="grid grid-cols-2 gap-2 text-xs font-mono">
        {/* Hop Frequency */}
        <div className="p-2.5 bg-slate-900/60 rounded-lg border border-slate-800">
          <div className="flex items-center text-slate-400 text-[10px] mb-1">
            <Radio className="w-3.5 h-3.5 mr-1 text-cyan-400" />
            <span>Active Hop</span>
          </div>
          <div className="text-sm font-bold text-cyan-300">
            {rf.active_freq_mhz.toFixed(1)} <span className="text-[10px] text-slate-400">MHz</span>
          </div>
          <div className="text-[10px] text-slate-500">
            λ = {(rf.wavelength_m * 100).toFixed(1)} cm
          </div>
        </div>

        {/* SNR Readout */}
        <div className="p-2.5 bg-slate-900/60 rounded-lg border border-slate-800">
          <div className="flex items-center text-slate-400 text-[10px] mb-1">
            <Wifi className="w-3.5 h-3.5 mr-1 text-emerald-400" />
            <span>Channel SNR</span>
          </div>
          <div className="text-sm font-bold text-emerald-400">
            {rf.snr_db.toFixed(1)} <span className="text-[10px] text-slate-400">dB</span>
          </div>
          <div className="text-[10px] text-slate-500">
            {rf.is_occluded ? "LOS Occluded" : "Clean Line-of-Sight"}
          </div>
        </div>

        {/* Proposed Compensated DoA */}
        <div className="p-2.5 bg-cyan-950/20 rounded-lg border border-cyan-800/40">
          <div className="text-[10px] text-cyan-400 mb-0.5">Proposed A2 DoA</div>
          <div className="text-base font-bold text-cyan-300">
            {dsp.est_compensated_deg.toFixed(1)}°
          </div>
          <div className="text-[10px] text-cyan-500">
            Err: {dsp.error_comp_deg >= 0 ? `+${dsp.error_comp_deg.toFixed(1)}°` : `${dsp.error_comp_deg.toFixed(1)}°`}
          </div>
        </div>

        {/* Static Uncompensated Baseline DoA */}
        <div className="p-2.5 bg-slate-900/40 rounded-lg border border-slate-800">
          <div className="text-[10px] text-slate-400 mb-0.5">Static 433 Baseline</div>
          <div className="text-base font-bold text-slate-300">
            {dsp.est_static_deg.toFixed(1)}°
          </div>
          <div className="text-[10px] text-red-400">
            Err: {dsp.error_static_deg >= 0 ? `+${dsp.error_static_deg.toFixed(1)}°` : `${dsp.error_static_deg.toFixed(1)}°`}
          </div>
        </div>
      </div>

      {/* Multi-Algorithm Benchmark Comparison */}
      <div className="p-2.5 bg-slate-900/60 rounded-xl border border-slate-800 text-xs font-mono">
        <div className="text-[10px] text-slate-400 uppercase tracking-wider mb-2 flex items-center justify-between border-b border-slate-800 pb-1">
          <span className="flex items-center">
            <Activity className="w-3.5 h-3.5 mr-1 text-cyan-400" />
            Benchmark Estimators
          </span>
          <span className="text-[9px] text-slate-500">Live Comparative Error</span>
        </div>
        <div className="grid grid-cols-3 gap-1.5 text-center text-[10px]">
          <div className="p-1.5 bg-slate-800/40 rounded border border-slate-700/50">
            <div className="text-slate-400">UCA-ESPRIT</div>
            <div className="font-bold text-slate-200">{dsp.est_esprit_deg !== undefined ? `${dsp.est_esprit_deg.toFixed(1)}°` : "--"}</div>
            <div className="text-cyan-400 text-[9px]">
              {dsp.error_esprit_deg !== undefined ? `±${Math.abs(dsp.error_esprit_deg).toFixed(1)}°` : ""}
            </div>
          </div>
          <div className="p-1.5 bg-slate-800/40 rounded border border-slate-700/50">
            <div className="text-slate-400">Power ML</div>
            <div className="font-bold text-slate-200">{dsp.est_pv_deg !== undefined ? `${dsp.est_pv_deg.toFixed(1)}°` : "--"}</div>
            <div className="text-cyan-400 text-[9px]">
              {dsp.error_pv_deg !== undefined ? `±${Math.abs(dsp.error_pv_deg).toFixed(1)}°` : ""}
            </div>
          </div>
          <div className="p-1.5 bg-slate-800/40 rounded border border-slate-700/50">
            <div className="text-slate-400">Centroid</div>
            <div className="font-bold text-slate-200">{dsp.est_centroid_deg !== undefined ? `${dsp.est_centroid_deg.toFixed(1)}°` : "--"}</div>
            <div className="text-cyan-400 text-[9px]">
              {dsp.error_centroid_deg !== undefined ? `±${Math.abs(dsp.error_centroid_deg).toFixed(1)}°` : ""}
            </div>
          </div>
        </div>
      </div>

      {/* Autonomous Obstacle Avoidance & Flight Safety */}
      <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 text-xs font-mono space-y-2">
        <div className="flex items-center justify-between text-slate-400 text-[11px] pb-1.5 border-b border-slate-800">
          <span className="flex items-center">
            <Navigation className="w-3.5 h-3.5 mr-1 text-cyan-400" />
            Obstacle Avoidance
          </span>
          <span
            className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
              uav.avoidance_status === "AVOIDING"
                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                : uav.avoidance_status === "OBSTRUCTED_PAUSED"
                ? "bg-red-500/20 text-red-300 border border-red-500/40"
                : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
            }`}
          >
            {uav.avoidance_status ?? "NOMINAL"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div>
            <span className="text-slate-500">Min Clearance: </span>
            <span
              className={`font-bold ${
                (uav.min_clearance_m ?? 99) < 4.0
                  ? "text-amber-400"
                  : "text-slate-200"
              }`}
            >
              {(uav.min_clearance_m ?? 99.0).toFixed(1)} m
            </span>
          </div>

          <div>
            <span className="text-slate-500">Avoidance Events: </span>
            <span className="text-cyan-400 font-bold">
              {uav.avoidance_event_count ?? 0}
            </span>
          </div>

          {uav.active_building_name && (
            <div className="col-span-2 text-slate-400 text-[10px] flex items-center space-x-1">
              <span className="text-amber-400">Target Obstacle:</span>
              <span className="text-slate-300">{uav.active_building_name}</span>
            </div>
          )}

          {uav.avoidance_status === "OBSTRUCTED_PAUSED" && (
            <div className="col-span-2 p-1.5 rounded bg-red-950/40 border border-red-500/40 text-red-300 text-[10px] flex items-center space-x-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0" />
              <span>Direct path obstructed by building envelope; safely holding position.</span>
            </div>
          )}
        </div>
      </div>

      {/* Multi-Station Radar Network & 2D Localization */}
      {multiradar && (
        <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 text-xs font-mono space-y-2">
          <div className="flex items-center justify-between text-slate-400 text-[11px] pb-1.5 border-b border-slate-800">
            <span className="flex items-center text-cyan-400">
              <Crosshair className="w-3.5 h-3.5 mr-1" />
              Multi-Station 2D Localization
            </span>
            <span className="text-[10px] bg-cyan-950/40 text-cyan-300 px-1.5 py-0.5 rounded border border-cyan-800/40">
              {multiradar.num_active_stations} Active DF Stations
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div>
              <span className="text-slate-500">Est UAV (X, Z): </span>
              <span className="text-emerald-400 font-bold">
                {multiradar.estimated_pos_xz
                  ? `(${multiradar.estimated_pos_xz[0].toFixed(1)}, ${multiradar.estimated_pos_xz[1].toFixed(1)}) m`
                  : "--"}
              </span>
            </div>

            <div>
              <span className="text-slate-500">2D Position Err: </span>
              <span
                className={`font-bold ${
                  (multiradar.position_error_m ?? 99) < 5.0
                    ? "text-emerald-400"
                    : "text-amber-400"
                }`}
              >
                {multiradar.position_error_m !== null && multiradar.position_error_m !== undefined
                  ? `${multiradar.position_error_m.toFixed(2)} m`
                  : "--"}
              </span>
            </div>
          </div>

          {/* Per-Station Bearing Breakdown */}
          <div className="space-y-1 pt-1 border-t border-slate-800/60">
            <div className="text-[10px] text-slate-500 flex justify-between">
              <span>Station</span>
              <span>Range / True Az</span>
              <span>Tracked DoA (Err)</span>
            </div>
            {multiradar.stations.map((st) => (
              <div key={st.id} className="flex justify-between items-center text-[10px] bg-slate-800/30 px-1.5 py-1 rounded">
                <span className="text-slate-300 font-bold truncate max-w-[90px]">{st.name.replace("Station ", "")}</span>
                <span className="text-slate-400">{st.distance_m.toFixed(0)}m / {st.true_azimuth_deg.toFixed(1)}°</span>
                <span className="text-cyan-300">
                  {st.tracked_bearing_deg.toFixed(1)}°
                  <span className={`text-[9px] ml-1 ${Math.abs(st.tracked_error_deg) < 2.0 ? "text-emerald-400" : "text-amber-400"}`}>
                    (±{Math.abs(st.tracked_error_deg).toFixed(1)}°)
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Receiver Hardware & Tracking State */}
      <div className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 text-xs font-mono space-y-2">
        <div className="flex items-center justify-between text-slate-400 text-[11px] pb-1.5 border-b border-slate-800">
          <span className="flex items-center">
            <Cpu className="w-3.5 h-3.5 mr-1 text-cyan-400" />
            Hardware & Subsystems
          </span>
          <span className="text-cyan-400 uppercase text-[10px] font-bold">
            {hardware.mode === "MODE_A_SIMULTANEOUS" ? "Mode A (Simultaneous)" : "Mode B (Switched HMC241)"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div>
            <span className="text-slate-500">Tracker State: </span>
            <span className={dsp.tracker_state === "ACQUIRED" ? "text-emerald-400 font-bold" : "text-amber-400 font-bold"}>
              {dsp.tracker_state}
            </span>
          </div>

          <div>
            <span className="text-slate-500">Phase Coherence: </span>
            <span className={hardware.phase_coherence_ok ? "text-emerald-400" : "text-red-400"}>
              {hardware.phase_coherence_ok ? "OK" : "DRIFT"}
            </span>
          </div>

          <div>
            <span className="text-slate-500">Rejections: </span>
            <span className="text-amber-400 font-bold">{dsp.total_rejections}</span>
            <span className="text-slate-500"> / {dsp.total_bursts}</span>
          </div>

          <div>
            <span className="text-slate-500">UAV Speed: </span>
            <span className="text-slate-300">{uav.speed.toFixed(1)} m/s</span>
          </div>
        </div>
      </div>
    </div>
  );
}

