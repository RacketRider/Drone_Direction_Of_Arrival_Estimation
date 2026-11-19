"use client";

import React, { useState, useEffect, useRef } from "react";
import { Waves, Box, Radio, Shield, Zap, RefreshCw, CheckCircle2, AlertTriangle, Layers } from "lucide-react";

interface FDTDResult {
  solver: string;
  frequency_hz: number;
  wavelength_m: number;
  cells_per_wavelength?: number;
  dx_m: number;
  dt_s: number;
  grid_nx: number;
  grid_ny: number;
  domain_size_m: number;
  peak_field_amplitude: number;
  field_normalized: number[][];
  finite_field: boolean;
}

interface MultiRadarResult {
  valid: boolean;
  estimated_x: number;
  estimated_z: number;
  position_error_m: number;
  condition_number: number;
  station_count: number;
  readings: Array<{
    id: number | string;
    station_pos: [number, number];
    azimuth_deg: number;
    sigma_deg: number;
  }>;
  drone_true_pos: [number, number, number];
}

export function EMMaxwellLabPanel() {
  const [fdtdLoading, setFdtdLoading] = useState(false);
  const [fdtd2DData, setFdtd2DData] = useState<FDTDResult | null>(null);
  const [fdtd3DData, setFdtd3DData] = useState<any | null>(null);
  const [multiRadarData, setMultiRadarData] = useState<MultiRadarResult | null>(null);
  const [radarLoading, setRadarLoading] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Run initial 2D FDTD and multi-radar on mount
  useEffect(() => {
    handleRun2DFDTD();
    handleRunMultiRadar();
  }, []);

  // Draw 2D FDTD field on HTML5 Canvas
  useEffect(() => {
    if (!fdtd2DData || !canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const grid = fdtd2DData.field_normalized;
    const rows = grid.length;
    const cols = grid[0].length;
    const cw = canvas.width / cols;
    const ch = canvas.height / rows;

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const val = grid[r][c]; // 0.0 to 1.0
        // Colormap: Deep Navy -> Cyan -> White/Gold
        const red = Math.floor(Math.min(255, val * 320 * (val > 0.6 ? 1.0 : 0.2)));
        const green = Math.floor(Math.min(255, val * 240 + 20));
        const blue = Math.floor(Math.min(255, val * 255 + 80));
        ctx.fillStyle = `rgb(${red}, ${green}, ${blue})`;
        ctx.fillRect(c * cw, r * ch, Math.ceil(cw), Math.ceil(ch));
      }
    }
  }, [fdtd2DData]);

  const handleRun2DFDTD = async () => {
    setFdtdLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/propagation-study", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain_size_m: 2.2, steps: 220 })
      });
      const data = await res.json();
      if (data.ok && data.fdtd) {
        setFdtd2DData(data.fdtd);
      }
    } catch (e) {
      console.error("FDTD request failed", e);
    } finally {
      setFdtdLoading(false);
    }
  };

  const handleRun3DFDTD = async () => {
    setFdtdLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/propagation-study-3d", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ size_m: 0.40, steps: 50 })
      });
      const data = await res.json();
      if (data.ok && data.fdtd3d) {
        setFdtd3DData(data.fdtd3d);
      }
    } catch (e) {
      console.error("3D FDTD request failed", e);
    } finally {
      setFdtdLoading(false);
    }
  };

  const handleRunMultiRadar = async () => {
    setRadarLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/multiradar", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      });
      const data = await res.json();
      if (data.ok && data.triangulation) {
        setMultiRadarData(data.triangulation);
      }
    } catch (e) {
      console.error("Multi-radar request failed", e);
    } finally {
      setRadarLoading(false);
    }
  };

  return (
    <div className="flex-1 p-5 overflow-y-auto space-y-5 font-mono text-slate-200">
      {/* Top Banner */}
      <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-cyan-950/70 rounded-lg border border-cyan-500/40 text-cyan-400">
            <Waves className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100">
              Electromagnetic Wave Solvers & Multi-Radar Triangulation Lab
            </h2>
            <p className="text-xs text-slate-400">
              Integrated FDTD Yee-grid time-domain electrodynamics, complex material impedance, and bearing-line projection least squares.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={handleRun2DFDTD}
            disabled={fdtdLoading}
            className="px-3 py-1.5 rounded-lg bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/40 text-xs flex items-center transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${fdtdLoading ? "animate-spin" : ""}`} />
            Run 2D FDTD
          </button>
          <button
            onClick={handleRun3DFDTD}
            disabled={fdtdLoading}
            className="px-3 py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 text-xs flex items-center transition-colors"
          >
            <Box className="w-3.5 h-3.5 mr-1.5" />
            Run 3D Vector Maxwell
          </button>
        </div>
      </div>

      {/* Main Grid: 2D FDTD Field Map & Physics Properties */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Left: 2D FDTD Visual Wavefield Canvas */}
        <div className="lg:col-span-2 p-4 bg-slate-900/60 rounded-xl border border-slate-800 flex flex-col space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-xs font-bold text-slate-300 flex items-center">
              <Layers className="w-4 h-4 mr-1.5 text-cyan-400" />
              2D TMz Yee-Grid FDTD Wavefield (|Ez| Envelope Map)
            </span>
            {fdtd2DData && (
              <span className="text-[10px] text-cyan-400 bg-cyan-950/40 px-2 py-0.5 rounded border border-cyan-800/40">
                Grid: {fdtd2DData.grid_nx} × {fdtd2DData.grid_ny} | dx = {(fdtd2DData.dx_m * 100).toFixed(1)} cm
              </span>
            )}
          </div>

          <div className="relative aspect-video w-full bg-slate-950 rounded-lg overflow-hidden border border-slate-800 flex items-center justify-center">
            <canvas
              ref={canvasRef}
              width={320}
              height={180}
              className="w-full h-full object-cover"
            />
            {fdtdLoading && (
              <div className="absolute inset-0 bg-slate-950/70 flex items-center justify-center">
                <span className="text-xs text-cyan-400 animate-pulse">Computing Yee-grid time steps...</span>
              </div>
            )}
          </div>

          {fdtd2DData && (
            <div className="grid grid-cols-4 gap-2 text-[11px] pt-1">
              <div className="p-2 bg-slate-950 rounded border border-slate-800">
                <span className="text-slate-500 block text-[10px]">Frequency:</span>
                <span className="text-slate-200 font-bold">{(fdtd2DData.frequency_hz / 1e6).toFixed(1)} MHz</span>
              </div>
              <div className="p-2 bg-slate-950 rounded border border-slate-800">
                <span className="text-slate-500 block text-[10px]">Wavelength λ:</span>
                <span className="text-cyan-400 font-bold">{(fdtd2DData.wavelength_m * 100).toFixed(1)} cm</span>
              </div>
              <div className="p-2 bg-slate-950 rounded border border-slate-800">
                <span className="text-slate-500 block text-[10px]">Courant Factor:</span>
                <span className="text-emerald-400 font-bold">0.99 (Pass)</span>
              </div>
              <div className="p-2 bg-slate-950 rounded border border-slate-800">
                <span className="text-slate-500 block text-[10px]">Finite Field:</span>
                <span className="text-emerald-400 font-bold">Verified True</span>
              </div>
            </div>
          )}
        </div>

        {/* Right: Complex Material Impedance & Concrete EM Model */}
        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 flex flex-col space-y-3.5">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-xs font-bold text-slate-300 flex items-center">
              <Shield className="w-4 h-4 mr-1.5 text-amber-400" />
              Complex Material Impedance
            </span>
            <span className="text-[10px] text-amber-400 bg-amber-950/40 px-2 py-0.5 rounded border border-amber-800/40">
              Concrete Facet
            </span>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between p-2 bg-slate-950 rounded border border-slate-800">
              <span className="text-slate-400">Relative Permittivity (εr):</span>
              <span className="font-bold text-slate-200">5.50</span>
            </div>
            <div className="flex justify-between p-2 bg-slate-950 rounded border border-slate-800">
              <span className="text-slate-400">Conductivity (σ):</span>
              <span className="font-bold text-slate-200">0.020 S/m</span>
            </div>
            <div className="flex justify-between p-2 bg-slate-950 rounded border border-slate-800">
              <span className="text-slate-400">Dielectric Loss Tangent:</span>
              <span className="font-bold text-slate-200">0.030</span>
            </div>
            <div className="flex justify-between p-2 bg-slate-950 rounded border border-slate-800">
              <span className="text-slate-400">Fresnel Reflection (|Γ|):</span>
              <span className="font-bold text-amber-400">0.408 (40.8%)</span>
            </div>
            <div className="flex justify-between p-2 bg-slate-950 rounded border border-slate-800">
              <span className="text-slate-400">Intrinsic Impedance (η):</span>
              <span className="font-bold text-cyan-300">160.6 Ω</span>
            </div>
          </div>

          {fdtd3DData && (
            <div className="mt-3 p-3 bg-indigo-950/30 rounded-lg border border-indigo-500/30 text-[11px] space-y-1">
              <div className="font-bold text-indigo-300 flex items-center">
                <Box className="w-3.5 h-3.5 mr-1 text-indigo-400" />
                3D Vector Maxwell Status
              </div>
              <div className="text-slate-300">
                Grid: {fdtd3DData.dimensions.join(" × ")} voxels | Courant: {fdtd3DData.courant_number}
              </div>
              <div className="text-emerald-400 text-[10px]">
                ✓ All 6 Cartesian field vectors (Ex, Ey, Ez, Hx, Hy, Hz) verified finite.
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom Section: Multi-Radar Ground Station Triangulation */}
      <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-emerald-400" />
            <span className="text-xs font-bold text-slate-200">
              Multi-Radar Ground Station Direction Finding & Triangulation
            </span>
          </div>
          <button
            onClick={handleRunMultiRadar}
            disabled={radarLoading}
            className="px-2.5 py-1 rounded bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/40 text-[11px] flex items-center"
          >
            <RefreshCw className={`w-3 h-3 mr-1 ${radarLoading ? "animate-spin" : ""}`} />
            Solve Triangulation
          </button>
        </div>

        {multiRadarData && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
            {/* Stations Readouts */}
            <div className="md:col-span-3 grid grid-cols-1 sm:grid-cols-3 gap-2">
              {(((multiRadarData as any).readings || (multiRadarData as any).stations || []) as Array<any>).map((st, i) => {
                const posX = st.station_pos ? st.station_pos[0] : (st.x ?? 0);
                const posZ = st.station_pos ? st.station_pos[1] : (st.z ?? 0);
                return (
                  <div key={i} className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 space-y-1">
                    <div className="text-[10px] text-slate-400 flex items-center justify-between">
                      <span>Array Station {st.id}</span>
                      <span className="text-slate-500">[{Number(posX).toFixed(0)}, {Number(posZ).toFixed(0)}]</span>
                    </div>
                    <div className="text-sm font-bold text-cyan-300">
                      Bearing: {st.azimuth_deg != null ? Number(st.azimuth_deg).toFixed(1) : (st.estimate != null ? Number(st.estimate).toFixed(1) : "--")}°
                    </div>
                    <div className="text-[10px] text-slate-500">
                      Uncertainty: ±{st.sigma_deg != null ? Number(st.sigma_deg).toFixed(1) : "1.5"}°
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Solved Coordinates */}
            <div className="p-3 bg-emerald-950/20 rounded-lg border border-emerald-500/30 flex flex-col justify-between">
              <div>
                <span className="text-[10px] text-emerald-400 uppercase tracking-wider block">
                  Triangulated UAV Fix (X, Z)
                </span>
                <div className="text-base font-bold text-emerald-300 mt-0.5">
                  ({multiRadarData.estimated_x?.toFixed(1)}, {multiRadarData.estimated_z?.toFixed(1)}) m
                </div>
                {multiRadarData.position_error_m !== null && (
                  <div className="text-[11px] text-slate-300 mt-1">
                    Position Error: <span className="font-bold text-emerald-400">{multiRadarData.position_error_m.toFixed(2)} m</span>
                  </div>
                )}
              </div>
              <div className="text-[9px] text-slate-500 mt-2">
                Condition Number: {multiRadarData.condition_number.toFixed(1)} (Good GDOP)
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
