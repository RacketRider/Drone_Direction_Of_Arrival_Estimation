"use client";

import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  BarChart,
  Bar,
  Cell
} from "recharts";
import { SignalDiagnosticsFrame, TelemetryFrame } from "@/types/telemetry";
import { Activity, BarChart2, Radio, Waves } from "lucide-react";

interface SignalAnalysisPanelProps {
  diagnostics: SignalDiagnosticsFrame | null;
  telemetry: TelemetryFrame | null;
}

export function SignalAnalysisPanel({ diagnostics, telemetry }: SignalAnalysisPanelProps) {
  // 1. Complex IQ samples formatted for LineChart
  const iqData = useMemo(() => {
    if (!diagnostics?.raw_iq_burst) return [];
    const { time_us, i_ch0, q_ch0 } = diagnostics.raw_iq_burst;
    return time_us.map((t, idx) => ({
      time: t,
      I: i_ch0[idx] ?? 0,
      Q: q_ch0[idx] ?? 0,
    }));
  }, [diagnostics?.raw_iq_burst]);

  // 2. Power Envelope samples formatted
  const powerData = useMemo(() => {
    if (!diagnostics?.power_envelope) return [];
    const { time_us, power_linear } = diagnostics.power_envelope;
    return time_us.map((t, idx) => ({
      time: t,
      power: power_linear[idx] ?? 0,
    }));
  }, [diagnostics?.power_envelope]);

  // 3. FFT Spectrum formatted
  const fftData = useMemo(() => {
    if (!diagnostics?.fft_spectrum) return [];
    const { freqs_khz, mag_db } = diagnostics.fft_spectrum;
    // Decimate for chart performance
    const step = 2;
    const res = [];
    for (let i = 0; i < freqs_khz.length; i += step) {
      res.push({
        freq_khz: freqs_khz[i],
        mag_db: mag_db[i] ?? -60,
      });
    }
    return res;
  }, [diagnostics?.fft_spectrum]);

  // 4. MUSIC Pseudospectrum formatted
  const musicData = useMemo(() => {
    if (!diagnostics?.music_spectrum) return [];
    const { angles_deg, comp_db, static_db } = diagnostics.music_spectrum;
    const step = 2; // Decimate 0.5 deg grid to 1.0 deg for fast SVG
    const res = [];
    for (let i = 0; i < angles_deg.length; i += step) {
      res.push({
        angle: angles_deg[i],
        comp_db: comp_db[i] ?? -40,
        static_db: static_db[i] ?? -40,
      });
    }
    return res;
  }, [diagnostics?.music_spectrum]);

  // 5. Eigenvalues formatted for BarChart
  const eigData = useMemo(() => {
    if (!telemetry?.dsp?.eigenvalues) return [];
    const vals = telemetry.dsp.eigenvalues;
    return [
      { name: "λ₁ (Signal)", value: vals[0], isSignal: true },
      { name: "λ₂ (Noise/Refl)", value: vals[1], isSignal: false },
      { name: "λ₃ (Noise)", value: vals[2], isSignal: false },
      { name: "λ₄ (Noise)", value: vals[3], isSignal: false },
    ];
  }, [telemetry?.dsp?.eigenvalues]);

  if (!diagnostics) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-500 font-mono text-xs">
        Collecting live baseband burst samples from DSP engine...
      </div>
    );
  }

  const pTh = diagnostics.power_envelope?.threshold ?? 0;
  const trueAz = diagnostics.music_spectrum?.true_bearing_deg ?? 0;
  const compAz = diagnostics.music_spectrum?.est_comp_deg ?? 0;
  const staticAz = diagnostics.music_spectrum?.est_static_deg ?? 0;
  const peakF_khz = diagnostics.fft_spectrum?.peak_freq_khz ?? 150;

  return (
    <div className="space-y-4 p-2 text-xs font-mono text-slate-300">
      {/* Grid: Row 1 - Power Envelope and FFT Spectrum */}
      <div className="grid grid-cols-2 gap-4">
        {/* Panel 1: Power Envelope & Burst Trigger */}
        <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="flex items-center font-bold text-cyan-400">
              <Activity className="w-4 h-4 mr-1.5" />
              1. Power Envelope Trigger P[n] = I² + Q²
            </span>
            <span className="text-[10px] text-slate-400">
              Threshold η: <span className="text-red-400 font-bold">{pTh.toFixed(4)}</span>
            </span>
          </div>

          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={powerData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="time" stroke="#64748B" fontSize={10} unit="µs" />
                <YAxis stroke="#64748B" fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }}
                />
                <ReferenceLine y={pTh} stroke="#EF4444" strokeDasharray="4 4" label={{ value: "Trigger η", fill: "#EF4444", fontSize: 10 }} />
                <Line type="monotone" dataKey="power" stroke="#00E5FF" dot={false} strokeWidth={1.6} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Panel 2: FFT Peak Identification */}
        <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="flex items-center font-bold text-cyan-400">
              <Radio className="w-4 h-4 mr-1.5" />
              2. Baseband FFT Spectrum (N=256)
            </span>
            <span className="text-[10px] text-emerald-400 font-bold">
              Peak: {peakF_khz.toFixed(1)} kHz
            </span>
          </div>

          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={fftData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="freq_khz" stroke="#64748B" fontSize={10} unit="kHz" />
                <YAxis stroke="#64748B" fontSize={10} domain={[-50, 2]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }}
                />
                <ReferenceLine x={peakF_khz} stroke="#10B981" strokeDasharray="3 3" />
                <Line type="monotone" dataKey="mag_db" stroke="#38BDF8" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Grid: Row 2 - MUSIC Pseudospectrum & Eigenvalue Distribution */}
      <div className="grid grid-cols-3 gap-4">
        {/* Panel 3: MUSIC Spatial Pseudospectrum Overlay (Span 2 cols) */}
        <div className="col-span-2 p-3 bg-slate-900/80 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between mb-2">
            <span className="flex items-center font-bold text-cyan-400">
              <Waves className="w-4 h-4 mr-1.5" />
              3. Circular MUSIC Pseudospectrum P_MUSIC(θ)
            </span>
            <div className="flex items-center space-x-3 text-[10px]">
              <span className="text-cyan-400 font-bold">━ Proposed A2 ({compAz.toFixed(1)}°)</span>
              <span className="text-red-400 font-bold">┄ Static 433 ({staticAz.toFixed(1)}°)</span>
              <span className="text-emerald-400 font-bold">┊ True ({trueAz.toFixed(1)}°)</span>
            </div>
          </div>

          <div className="h-48 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={musicData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                <XAxis dataKey="angle" stroke="#64748B" fontSize={10} domain={[-180, 180]} unit="°" />
                <YAxis stroke="#64748B" fontSize={10} domain={[-35, 2]} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }}
                />
                <ReferenceLine x={trueAz} stroke="#10B981" strokeWidth={1.8} strokeDasharray="3 3" label={{ value: "True Bearing", fill: "#10B981", fontSize: 10 }} />
                <Line type="monotone" dataKey="comp_db" stroke="#00E5FF" dot={false} strokeWidth={2.2} name="Proposed Compensated" />
                <Line type="monotone" dataKey="static_db" stroke="#EF4444" dot={false} strokeWidth={1.5} strokeDasharray="4 2" name="Static Uncompensated" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Panel 4: Eigenvalues & Gate Diagnostics */}
        <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="flex items-center font-bold text-cyan-400">
                <BarChart2 className="w-4 h-4 mr-1.5" />
                4. Eigenvalues (EVD)
              </span>
              <span className="text-[10px] text-slate-400">M = 4</span>
            </div>

            <div className="h-32 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={eigData} margin={{ top: 5, right: 5, left: -25, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                  <XAxis dataKey="name" stroke="#64748B" fontSize={9} />
                  <YAxis stroke="#64748B" fontSize={9} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 10 }}
                  />
                  <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                    {eigData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={entry.isSignal ? "#00E5FF" : index === 1 && telemetry?.dsp?.is_accepted === false ? "#EF4444" : "#475569"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Ratio Gauge Card */}
          <div className="mt-2 p-2 bg-slate-950/60 rounded-lg border border-slate-800 text-[11px]">
            <div className="flex justify-between items-center mb-1">
              <span className="text-slate-400">Spread Ratio γ = λ₁/λ₂:</span>
              <span className={`font-bold ${telemetry?.dsp?.is_accepted ? "text-cyan-400" : "text-red-400"}`}>
                {telemetry?.dsp?.eigenvalue_ratio?.toFixed(2) ?? "0.00"}
              </span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  telemetry?.dsp?.is_accepted ? "bg-cyan-400" : "bg-red-400"
                }`}
                style={{
                  width: `${Math.min(100, ((telemetry?.dsp?.eigenvalue_ratio ?? 0) / 25.0) * 100)}%`,
                }}
              />
            </div>
            <div className="flex justify-between text-[9px] text-slate-500 mt-1">
              <span>0 (Multipath)</span>
              <span>Threshold: 8.0</span>
              <span>25+ (Pure LoS)</span>
            </div>
          </div>
        </div>
      </div>

      {/* Row 3: Complex IQ Baseband Samples (Channel 0) */}
      <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800">
        <div className="flex items-center justify-between mb-2">
          <span className="font-bold text-cyan-400">
            5. In-Phase (I) and Quadrature (Q) Baseband Waveform (Antenna 0)
          </span>
          <span className="text-[10px] text-slate-400">
            Duration: 128 µs (2 MS/s)
          </span>
        </div>

        <div className="h-32 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={iqData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
              <XAxis dataKey="time" stroke="#64748B" fontSize={9} unit="µs" />
              <YAxis stroke="#64748B" fontSize={9} domain={[-2, 2]} />
              <Tooltip
                contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 10 }}
              />
              <Line type="monotone" dataKey="I" stroke="#00E5FF" dot={false} strokeWidth={1.2} name="I Channel" />
              <Line type="monotone" dataKey="Q" stroke="#F59E0B" dot={false} strokeWidth={1.2} name="Q Channel" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

