"use client";

import React from "react";
import { TelemetryFrame } from "@/types/telemetry";

interface CompassBearingDialProps {
  telemetry: TelemetryFrame | null;
}

export function CompassBearingDial({ telemetry }: CompassBearingDialProps) {
  const trueAz = telemetry?.uav?.true_azimuth_deg ?? 0;
  const compAz = telemetry?.dsp?.est_compensated_deg ?? 0;
  const staticAz = telemetry?.dsp?.est_static_deg ?? 0;
  const trackAz = telemetry?.dsp?.accepted_track_deg ?? 0;
  const errComp = telemetry?.dsp?.error_comp_deg ?? 0;
  const isHolding = telemetry?.dsp?.tracker_state === "HOLDING";

  // Dial radius
  const size = 180;
  const center = size / 2;
  const radius = center - 18;

  // Convert degrees to dial radians (0 deg = East, 90 deg = North)
  const toCoords = (deg: number, r: number) => {
    const rad = (deg * Math.PI) / 180.0;
    return {
      x: center + r * Math.cos(rad),
      y: center - r * Math.sin(rad),
    };
  };

  const truePt = toCoords(trueAz, radius - 4);
  const compPt = toCoords(compAz, radius - 4);
  const staticPt = toCoords(staticAz, radius - 14);
  const trackPt = toCoords(trackAz, radius - 4);

  return (
    <div className="flex flex-col items-center justify-center p-3 bg-slate-900/60 rounded-xl border border-slate-800">
      <div className="text-[11px] font-mono uppercase tracking-wider text-slate-400 mb-1">
        360° Azimuth Radar Rose
      </div>

      <div className="relative">
        <svg width={size} height={size} className="select-none">
          {/* Dial Background Circles */}
          <circle cx={center} cy={center} r={radius} fill="#0B132B" stroke="#1E293B" strokeWidth="2" />
          <circle cx={center} cy={center} r={radius * 0.65} fill="none" stroke="#1E2B42" strokeDasharray="3 3" />
          <circle cx={center} cy={center} r={radius * 0.3} fill="none" stroke="#1E2B42" />

          {/* Cardinal Directions */}
          <text x={center + radius - 10} y={center + 4} fill="#64748B" fontSize="9" fontFamily="monospace" textAnchor="middle">E (0°)</text>
          <text x={center} y={center - radius + 12} fill="#64748B" fontSize="9" fontFamily="monospace" textAnchor="middle">N (90°)</text>
          <text x={center - radius + 12} y={center + 4} fill="#64748B" fontSize="9" fontFamily="monospace" textAnchor="middle">W (180°)</text>
          <text x={center} y={center + radius - 6} fill="#64748B" fontSize="9" fontFamily="monospace" textAnchor="middle">S (-90°)</text>

          {/* Static Uncompensated Needle (Dashed Crimson) */}
          <line
            x1={center}
            y1={center}
            x2={staticPt.x}
            y2={staticPt.y}
            stroke="#EF4444"
            strokeWidth="1.5"
            strokeDasharray="4 2"
            opacity="0.7"
          />

          {/* True Azimuth Ground-Truth Needle (Dotted Emerald) */}
          <line
            x1={center}
            y1={center}
            x2={truePt.x}
            y2={truePt.y}
            stroke="#10B981"
            strokeWidth="1.8"
            strokeDasharray="2 2"
          />

          {/* Frequency-Compensated Proposed Needle (Solid Cyan or Amber if holding) */}
          <line
            x1={center}
            y1={center}
            x2={compPt.x}
            y2={compPt.y}
            stroke={isHolding ? "#FFB300" : "#00E5FF"}
            strokeWidth="2.5"
          />

          {/* Center Hub */}
          <circle cx={center} cy={center} r="4" fill="#00E5FF" />
        </svg>

        {/* Needle Labels Overlay */}
        <div className="absolute bottom-1 right-1 text-[10px] font-mono text-slate-400 flex flex-col items-end">
          <span className="text-emerald-400">● True: {trueAz.toFixed(1)}°</span>
          <span className="text-cyan-400">━ Comp: {compAz.toFixed(1)}°</span>
          <span className="text-red-400">┄ Static: {staticAz.toFixed(1)}°</span>
        </div>
      </div>

      <div className="mt-2 flex items-center justify-between w-full px-2 text-xs font-mono">
        <span className="text-slate-400">Tracking Error:</span>
        <span className={`font-bold ${Math.abs(errComp) < 2.0 ? "text-emerald-400" : "text-amber-400"}`}>
          {errComp >= 0 ? `+${errComp.toFixed(2)}°` : `${errComp.toFixed(2)}°`}
        </span>
      </div>
    </div>
  );
}

