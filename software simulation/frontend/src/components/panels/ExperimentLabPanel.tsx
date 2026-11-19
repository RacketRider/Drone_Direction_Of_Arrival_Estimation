"use client";

import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  BarChart,
  Bar,
  ReferenceLine,
  AreaChart,
  Area
} from "recharts";
import { ExperimentPreset, ExperimentReport, PaperBenchmarksData } from "@/types/telemetry";
import {
  FlaskConical,
  Play,
  Download,
  CheckCircle,
  AlertTriangle,
  Layers,
  FileSpreadsheet,
  BookOpen,
  TrendingUp,
  Radio,
  Compass,
  ShieldCheck,
  ShieldAlert,
  Activity
} from "lucide-react";

type SubViewMode = "PAPER_BENCHMARKS" | "LIVE_BATCHES";

export function ExperimentLabPanel() {
  const [subView, setSubView] = useState<SubViewMode>("PAPER_BENCHMARKS");
  const [presets, setPresets] = useState<ExperimentPreset[]>([]);
  const [selectedPresetId, setSelectedPresetId] = useState<string>("PRESET_A_FREQUENCY_HOPPING");
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [isExportingExcel, setIsExportingExcel] = useState<boolean>(false);
  const [report, setReport] = useState<ExperimentReport | null>(null);
  const [paperData, setPaperData] = useState<PaperBenchmarksData | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Fetch presets list and paper benchmarks
  useEffect(() => {
    fetch("/api/experiments/presets")
      .then((res) => res.json())
      .then((data) => {
        setPresets(data);
        if (data.length > 0) setSelectedPresetId(data[0].id);
      })
      .catch((err) => {
        console.error("Failed to load experiment presets:", err);
      });

    fetch("/api/experiments/paper-benchmarks")
      .then((res) => res.json())
      .then((data: PaperBenchmarksData) => {
        setPaperData(data);
      })
      .catch((err) => {
        console.error("Failed to load paper benchmarks:", err);
      });
  }, []);

  const handleRunExperiment = async () => {
    setIsRunning(true);
    setError(null);
    setReport(null);

    try {
      const res = await fetch("/api/experiments/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ preset_id: selectedPresetId, seed: 42 }),
      });

      if (!res.ok) {
        throw new Error(`Server returned status ${res.status}`);
      }

      const data: ExperimentReport = await res.json();
      setReport(data);
    } catch (err: any) {
      setError(err?.message || "Experiment run failed");
    } finally {
      setIsRunning(false);
    }
  };

  const handleExportJSON = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.preset_id}_report.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportCSV = () => {
    if (!report || !report.results.length) return;
    const headers = Object.keys(report.results[0]).join(",");
    const rows = report.results.map((r) => Object.values(r).join(",")).join("\n");
    const csvContent = `${headers}\n${rows}`;
    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${report.preset_id}_report.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportXLSX = async (exportFullTelemetry: boolean = false) => {
    setIsExportingExcel(true);
    try {
      const payload = (!exportFullTelemetry && report && report.results.length > 0)
        ? { rows: report.results }
        : {};

      const res = await fetch("/api/export.xlsx", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        throw new Error(`Export failed with HTTP ${res.status}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = exportFullTelemetry
        ? `ec261_telemetry_master_${Date.now()}.xlsx`
        : `${report ? report.preset_id : "ec261"}_report_${Date.now()}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.message || "Excel export failed");
    } finally {
      setIsExportingExcel(false);
    }
  };

  const selectedPreset = presets.find((p) => p.id === selectedPresetId);

  // Formatted data for Figure 3a (Freq vs Static Steering Bias)
  const fig3aData = paperData?.figure3_manifold_bias.freq_sweep.frequencies_mhz.map((f, i) => ({
    freq: f,
    worst_case: Number(paperData.figure3_manifold_bias.freq_sweep.worst_case_bias_deg[i]?.toFixed(3) || 0),
    rms: Number(paperData.figure3_manifold_bias.freq_sweep.rms_bias_deg[i]?.toFixed(3) || 0),
  })) || [];

  // Formatted data for Figure 3b (Radius vs 95th-pct Bias)
  const fig3bData = paperData?.figure3_manifold_bias.radius_sweep.radius_cm.map((r, i) => ({
    radius: Number(r.toFixed(1)),
    bias_915: Number(Math.max(paperData.figure3_manifold_bias.radius_sweep.bias_915mhz_deg[i] || 0, 0.05).toFixed(2)),
    bias_868: Number(Math.max(paperData.figure3_manifold_bias.radius_sweep.bias_868mhz_deg[i] || 0, 0.05).toFixed(2)),
  })) || [];

  // Formatted data for Figure 4a (DoA RMSE vs SNR)
  const fig4aData = paperData?.figure4_snr_benchmarks.snr_db.map((snr, i) => ({
    snr,
    proposed: Number(paperData.figure4_snr_benchmarks.doa_rmse.proposed_fine_lambda_k[i]?.toFixed(2) || 0),
    switched: Number(paperData.figure4_snr_benchmarks.doa_rmse.switched_no_derotation[i]?.toFixed(2) || 0),
    fft_only: Number(paperData.figure4_snr_benchmarks.doa_rmse.fft_only_derotation[i]?.toFixed(2) || 0),
    static_base: Number(paperData.figure4_snr_benchmarks.doa_rmse.static_lambda0_baseline[i]?.toFixed(2) || 0),
    ideal: Number(paperData.figure4_snr_benchmarks.doa_rmse.ideal_4ch_coherent[i]?.toFixed(2) || 0),
    crb: Number(paperData.figure4_snr_benchmarks.doa_rmse.cramer_rao_bound[i]?.toFixed(2) || 0),
  })) || [];

  // Formatted data for Figure 4b (Frequency Offset RMSE vs SNR)
  const fig4bData = paperData?.figure4_snr_benchmarks.snr_db.map((snr, i) => ({
    snr,
    coarse_fft: Math.round(paperData.figure4_snr_benchmarks.frequency_offset_rmse_hz.coarse_fft_peak[i] || 0),
    lag_m_refined: Math.round(paperData.figure4_snr_benchmarks.frequency_offset_rmse_hz.lag_m_refined[i] || 0),
  })) || [];

  // Formatted data for Figure 5a (Gamma vs SNR)
  const fig5aData = paperData?.figure5_multipath_gate.eigenvalue_ratio_vs_snr.snr_db.map((snr, i) => ({
    snr,
    med: Number(paperData.figure5_multipath_gate.eigenvalue_ratio_vs_snr.gamma_median[i]?.toFixed(1) || 0),
    p10: Number(paperData.figure5_multipath_gate.eigenvalue_ratio_vs_snr.gamma_p10[i]?.toFixed(1) || 0),
    p90: Number(paperData.figure5_multipath_gate.eigenvalue_ratio_vs_snr.gamma_p90[i]?.toFixed(1) || 0),
    threshold: 8.0,
  })) || [];

  // Formatted data for Figure 5b (Rejection Prob vs Correlation c)
  const fig5bData = paperData?.figure5_multipath_gate.rejection_prob_vs_correlation.correlation_c.map((c, i) => ({
    c: Number(c.toFixed(2)),
    rho_0_3: Math.round((paperData.figure5_multipath_gate.rejection_prob_vs_correlation.rho_0_3_weak[i] || 0) * 100),
    rho_0_6: Math.round((paperData.figure5_multipath_gate.rejection_prob_vs_correlation.rho_0_6_moderate[i] || 0) * 100),
    rho_0_9: Math.round((paperData.figure5_multipath_gate.rejection_prob_vs_correlation.rho_0_9_strong[i] || 0) * 100),
  })) || [];

  return (
    <div className="space-y-4 p-2 text-xs font-mono text-slate-300">
      {/* Top Header & Sub-View Switcher */}
      <div className="p-4 bg-slate-900/90 rounded-xl border border-slate-800 shadow-lg">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div className="flex items-center space-x-3">
            <span className="flex items-center font-bold text-sm text-cyan-400">
              <FlaskConical className="w-4 h-4 mr-2" />
              Automated Research Experiment Laboratory
            </span>
            <span className="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/30 text-cyan-300 text-[10px]">
              IEEE Trans. Aerospace & Electronic Systems
            </span>
          </div>

          {/* Mode Switcher Tabs */}
          <div className="flex items-center space-x-1.5 bg-slate-950 p-1 rounded-lg border border-slate-800">
            <button
              onClick={() => setSubView("PAPER_BENCHMARKS")}
              className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all text-xs ${
                subView === "PAPER_BENCHMARKS"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <BookOpen className="w-3.5 h-3.5 mr-1 text-cyan-400" />
              <span>Paper Publication Benchmarks (IEEE)</span>
            </button>

            <button
              onClick={() => setSubView("LIVE_BATCHES")}
              className={`px-3 py-1.5 rounded-md flex items-center space-x-1.5 transition-all text-xs ${
                subView === "LIVE_BATCHES"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Play className="w-3.5 h-3.5 mr-1 text-emerald-400" />
              <span>Live Batch Simulator (Presets A–K)</span>
            </button>
          </div>

          {/* Export Actions */}
          <div className="flex items-center space-x-2">
            {report && (
              <>
                <button
                  onClick={handleExportCSV}
                  className="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center space-x-1"
                  title="Export results as CSV"
                >
                  <Download className="w-3 h-3 mr-1 text-emerald-400" />
                  <span>CSV</span>
                </button>
                <button
                  onClick={handleExportJSON}
                  className="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center space-x-1"
                  title="Export results as JSON"
                >
                  <Download className="w-3 h-3 mr-1 text-cyan-400" />
                  <span>JSON</span>
                </button>
                <button
                  onClick={() => handleExportXLSX(false)}
                  disabled={isExportingExcel}
                  className="px-2.5 py-1.5 rounded bg-emerald-950/70 hover:bg-emerald-900 text-emerald-300 border border-emerald-600/50 flex items-center space-x-1 shadow"
                  title="Export styled Excel workbook (.xlsx)"
                >
                  <FileSpreadsheet className="w-3 h-3 mr-1 text-emerald-400" />
                  <span>{isExportingExcel ? "Generating..." : "Report (.xlsx)"}</span>
                </button>
              </>
            )}

            <button
              onClick={() => handleExportXLSX(true)}
              disabled={isExportingExcel}
              className="px-2.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center space-x-1"
              title="Export all live telemetry history to multi-sheet Excel (.xlsx)"
            >
              <FileSpreadsheet className="w-3 h-3 mr-1 text-green-400" />
              <span>Full Telemetry (.xlsx)</span>
            </button>
          </div>
        </div>

        <div className="text-[11px] text-slate-400 leading-relaxed border-t border-slate-800/80 pt-2 flex items-center justify-between">
          <span>
            {subView === "PAPER_BENCHMARKS"
              ? "Displaying the rigorous theoretical sweeps and empirical benchmark curves published in our IEEE paper: array manifold mismatch, multi-receiver SNR sweeps, and eigenvalue gate bounds."
              : "Execute automated Monte Carlo parametric sweeps across SNR, array radius, carrier frequency offsets, and multipath coherence using the authoritative digital twin engine."}
          </span>
          <span className="text-slate-500 font-mono text-[10px]">
            4-Element UCA (r=7.2 cm) | HMC241 SP4T | RTL-SDR 2.0 MS/s
          </span>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-950/40 border border-red-500/40 rounded-xl text-red-300 flex items-center">
          <AlertTriangle className="w-4 h-4 mr-2" />
          <span>{error}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBVIEW 1: RESEARCH PAPER PUBLICATION BENCHMARKS                          */}
      {/* ========================================================================= */}
      {subView === "PAPER_BENCHMARKS" && (
        <div className="space-y-4">
          {/* Card 1: Array Manifold Mismatch & Spatial Ambiguity Analysis (Paper Fig. 3) */}
          <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 shadow-md">
            <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2">
                <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-400 font-bold text-xs border border-blue-800/60">
                  Paper Fig. 3
                </span>
                <span className="font-bold text-sm text-slate-100">
                  Array Manifold Mismatch & Spatial Ambiguity Breakdown
                </span>
              </div>
              <span className="text-[11px] text-slate-400">
                Analytical proof of Eq. (7) & spatial aliasing boundary
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Fig 3(a): Static-Steering Bias vs Hop Frequency */}
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <div className="text-xs font-bold text-cyan-400 mb-1 flex items-center justify-between">
                  <span>(a) Static-Steering Bias vs Hop Frequency (MHz)</span>
                  <span className="text-[10px] text-slate-500">f₀ = 433 MHz, r = 7.2 cm</span>
                </div>
                <div className="text-[10px] text-slate-400 mb-2">
                  Uncompensated static steering creates progressive bias up to 0.85° across 868–928 MHz ISM bands.
                </div>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={fig3aData} margin={{ top: 10, right: 15, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                      <XAxis dataKey="freq" stroke="#64748B" fontSize={10} unit=" MHz" domain={[430, 930]} />
                      <YAxis stroke="#64748B" fontSize={10} unit="°" domain={[0, 1.0]} />
                      <Tooltip contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <ReferenceLine x={433} stroke="#64748B" strokeDasharray="3 3" label={{ value: "433 MHz", fill: "#64748B", fontSize: 9 }} />
                      <ReferenceLine x={868} stroke="#64748B" strokeDasharray="3 3" label={{ value: "868 MHz", fill: "#64748B", fontSize: 9 }} />
                      <ReferenceLine x={915} stroke="#64748B" strokeDasharray="3 3" label={{ value: "915 MHz", fill: "#64748B", fontSize: 9 }} />
                      <Line type="monotone" dataKey="worst_case" stroke="#F59E0B" strokeWidth={2} dot={false} name="Worst-case |bias(θ)| (deg)" />
                      <Line type="monotone" dataKey="rms" stroke="#00E5FF" strokeWidth={2} strokeDasharray="4 2" dot={false} name="RMS Bias over Azimuth θ (deg)" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Fig 3(b): 95th-Percentile Bias vs UCA Radius */}
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <div className="text-xs font-bold text-cyan-400 mb-1 flex items-center justify-between">
                  <span>(b) 95th-Pct. Bias vs UCA Radius r (cm)</span>
                  <span className="text-[10px] text-emerald-400">Prototype: r = 7.2 cm</span>
                </div>
                <div className="text-[10px] text-slate-400 mb-2">
                  Spatial ambiguity breakdown: catastrophic phase wrapping occurs above r ≥ 12 cm (d/λ ≥ 0.52).
                </div>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={fig3bData} margin={{ top: 10, right: 15, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                      <XAxis dataKey="radius" stroke="#64748B" fontSize={10} unit=" cm" domain={[4, 40]} />
                      <YAxis stroke="#64748B" fontSize={10} unit="°" domain={[0, 90]} />
                      <Tooltip contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <ReferenceLine x={7.2} stroke="#10B981" strokeWidth={2} strokeDasharray="3 3" label={{ value: "Prototype r=7.2 cm", fill: "#10B981", fontSize: 9, position: "insideTopLeft" }} />
                      <ReferenceLine x={12.0} stroke="#EF4444" strokeWidth={1.5} strokeDasharray="4 2" label={{ value: "Ambiguity Collapse (≥12 cm)", fill: "#EF4444", fontSize: 9, position: "insideTopRight" }} />
                      <Line type="monotone" dataKey="bias_915" stroke="#EF4444" strokeWidth={2} dot={{ r: 2 }} name="f_k = 915 MHz (95th-pct)" />
                      <Line type="monotone" dataKey="bias_868" stroke="#10B981" strokeWidth={2} strokeDasharray="3 3" dot={{ r: 2 }} name="f_k = 868 MHz (95th-pct)" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>

          {/* Card 2: DoA Estimation Accuracy & Frequency Recovery vs SNR (Paper Fig. 4) */}
          <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 shadow-md">
            <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2">
                <span className="px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 font-bold text-xs border border-cyan-800/60">
                  Paper Fig. 4
                </span>
                <span className="font-bold text-sm text-slate-100">
                  DoA Estimation Accuracy & Frequency-Offset Recovery across SNR
                </span>
              </div>
              <span className="text-[11px] text-slate-400">
                Multi-receiver Monte Carlo benchmark (400 bursts/point @ 915 MHz)
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Fig 4(a): 6-Receiver DoA RMSE vs SNR */}
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <div className="text-xs font-bold text-cyan-400 mb-1 flex items-center justify-between">
                  <span>(a) DoA RMSE (deg) vs SNR per Element (dB)</span>
                  <span className="text-[10px] text-slate-500">N_snap = 32 snapshots</span>
                </div>
                <div className="text-[10px] text-slate-400 mb-2">
                  Proposed fine de-rotation + λ_k reaches 0.18° at 30 dB, closely tracking the Cramér-Rao Bound (CRB).
                </div>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={fig4aData} margin={{ top: 10, right: 15, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                      <XAxis dataKey="snr" stroke="#64748B" fontSize={10} unit=" dB" domain={[-10, 30]} />
                      <YAxis stroke="#64748B" fontSize={10} unit="°" domain={[0, 30]} />
                      <Tooltip contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 10 }} />
                      <Line type="monotone" dataKey="proposed" stroke="#00E5FF" strokeWidth={2.5} dot={{ r: 3 }} name="Proposed (Fine De-rot + λ_k)" />
                      <Line type="monotone" dataKey="ideal" stroke="#10B981" strokeWidth={1.5} strokeDasharray="3 3" dot={{ r: 2 }} name="Ideal 4-Ch Coherent" />
                      <Line type="monotone" dataKey="crb" stroke="#94A3B8" strokeWidth={1.5} strokeDasharray="2 2" dot={false} name="Cramér-Rao Bound (CRB)" />
                      <Line type="monotone" dataKey="static_base" stroke="#3B82F6" strokeWidth={1.5} dot={{ r: 2 }} name="Static λ₀ (433 MHz) Baseline" />
                      <Line type="monotone" dataKey="fft_only" stroke="#D946EF" strokeWidth={1.5} dot={{ r: 2 }} name="FFT-Only De-rotation" />
                      <Line type="monotone" dataKey="switched" stroke="#EF4444" strokeWidth={1.5} dot={{ r: 2 }} name="Switched (No De-rotation)" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Fig 4(b): Frequency Offset Estimation Error vs SNR */}
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <div className="text-xs font-bold text-cyan-400 mb-1 flex items-center justify-between">
                  <span>(b) Carrier Frequency Error RMSE (Hz) vs SNR</span>
                  <span className="text-[10px] text-cyan-400">Lag-M vs FFT Resolution</span>
                </div>
                <div className="text-[10px] text-slate-400 mb-2">
                  Lag-M differential phase refinement resolves sub-100 Hz accuracy (down to 34 Hz at +30 dB).
                </div>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={fig4bData} margin={{ top: 10, right: 15, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                      <XAxis dataKey="snr" stroke="#64748B" fontSize={10} unit=" dB" domain={[-10, 30]} />
                      <YAxis stroke="#64748B" fontSize={10} unit=" Hz" domain={[0, 5000]} />
                      <Tooltip contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="coarse_fft" stroke="#D946EF" strokeWidth={2} dot={{ r: 3 }} name="Coarse FFT Peak (N_fft=512, ~3.9 kHz bin)" />
                      <Line type="monotone" dataKey="lag_m_refined" stroke="#00E5FF" strokeWidth={2.5} dot={{ r: 3 }} name="Lag-M Differential Refinement (Eq. 5)" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>

          {/* Card 3: Multipath Eigenvalue Gate Dynamics & Coherence Breakdown (Paper Fig. 5) */}
          <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 shadow-md">
            <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2">
                <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-400 font-bold text-xs border border-amber-800/60">
                  Paper Fig. 5
                </span>
                <span className="font-bold text-sm text-slate-100">
                  Multipath Eigenvalue Ratio Gate & Coherence Collapse
                </span>
              </div>
              <span className="text-[11px] text-slate-400">
                Evaluation of γ = λ₁/λ₂ across SNR and reflection correlation |c|
              </span>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Fig 5(a): Gamma vs SNR */}
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <div className="text-xs font-bold text-cyan-400 mb-1 flex items-center justify-between">
                  <span>(a) Eigenvalue Ratio γ = λ₁/λ₂ vs SNR under LoS</span>
                  <span className="text-[10px] text-red-400">γ_th = 8.0</span>
                </div>
                <div className="text-[10px] text-slate-400 mb-2">
                  At SNR ≥ 10 dB, median γ exceeds 80, ensuring clean LoS false rejection rate &lt; 0.5%.
                </div>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={fig5aData} margin={{ top: 10, right: 15, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                      <XAxis dataKey="snr" stroke="#64748B" fontSize={10} unit=" dB" domain={[-10, 30]} />
                      <YAxis stroke="#64748B" fontSize={10} domain={[0, 250]} />
                      <Tooltip contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <ReferenceLine y={8.0} stroke="#EF4444" strokeWidth={2} strokeDasharray="4 2" label={{ value: "Gate Threshold γ_th = 8.0", fill: "#EF4444", fontSize: 9 }} />
                      <Line type="monotone" dataKey="p90" stroke="#64748B" strokeWidth={1} strokeDasharray="2 2" dot={false} name="90th-Percentile γ" />
                      <Line type="monotone" dataKey="med" stroke="#00E5FF" strokeWidth={2.5} dot={{ r: 2 }} name="Median γ = λ₁/λ₂" />
                      <Line type="monotone" dataKey="p10" stroke="#64748B" strokeWidth={1} strokeDasharray="2 2" dot={false} name="10th-Percentile γ" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Fig 5(b): Rejection Probability vs Correlation |c| */}
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
                <div className="text-xs font-bold text-cyan-400 mb-1 flex items-center justify-between">
                  <span>(b) Rejection Probability vs Path Correlation |c|</span>
                  <span className="text-[10px] text-amber-400">SNR = 15 dB @ 915 MHz</span>
                </div>
                <div className="text-[10px] text-slate-400 mb-2">
                  Partially correlated multipath (|c| &le; 0.8) is rejected with &gt; 95% probability. Fully coherent multipath (|c| &rarr; 1.0) collapses to rank-1.
                </div>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={fig5bData} margin={{ top: 10, right: 15, left: -20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                      <XAxis dataKey="c" stroke="#64748B" fontSize={10} domain={[0, 1.0]} />
                      <YAxis stroke="#64748B" fontSize={10} unit="%" domain={[0, 100]} />
                      <Tooltip contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Line type="monotone" dataKey="rho_0_9" stroke="#EF4444" strokeWidth={2.5} dot={{ r: 3 }} name="Strong Reflection (ρ = 0.9, -0.9 dB)" />
                      <Line type="monotone" dataKey="rho_0_6" stroke="#F59E0B" strokeWidth={2} dot={{ r: 3 }} name="Moderate Reflection (ρ = 0.6, -4.4 dB)" />
                      <Line type="monotone" dataKey="rho_0_3" stroke="#3B82F6" strokeWidth={1.5} dot={{ r: 3 }} name="Weak Reflection (ρ = 0.3, -10.5 dB)" />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          </div>

          {/* Academic Table I & II: Comprehensive Performance Breakdown */}
          {paperData?.figure5_multipath_gate.gate_table && (
            <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 shadow-md">
              <div className="flex items-center justify-between mb-3 border-b border-slate-800 pb-2">
                <span className="font-bold text-sm text-cyan-400">
                  Paper Table II: Empirical Direction Finding Performance across 6 Multipath Regimes
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  1,000 Monte Carlo Bursts per Regime @ 915 MHz, SNR = 15 dB
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-[11px] font-mono border-collapse">
                  <thead>
                    <tr className="border-b border-slate-700 bg-slate-800/60 text-slate-300">
                      <th className="p-2">Propagation Regime</th>
                      <th className="p-2 text-cyan-400">Median γ</th>
                      <th className="p-2 text-amber-400">Gate Rejection (%)</th>
                      <th className="p-2 text-red-400">Raw MUSIC RMSE</th>
                      <th className="p-2 text-emerald-400 font-bold">Gated MUSIC RMSE</th>
                      <th className="p-2">Bartlett RMSE</th>
                      <th className="p-2">Capon RMSE</th>
                      <th className="p-2">Interferometry LS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {paperData.figure5_multipath_gate.gate_table.map((row, idx) => (
                      <tr key={idx} className="border-b border-slate-800/80 hover:bg-slate-800/30">
                        <td className="p-2 font-bold text-slate-200">{row.name}</td>
                        <td className="p-2 text-cyan-300">{row.gam_med.toFixed(1)}</td>
                        <td className="p-2 text-amber-300 font-bold">{(row.rej * 100).toFixed(1)}%</td>
                        <td className="p-2 text-red-300">{row.MUSIC ? `${row.MUSIC.toFixed(2)}°` : "—"}</td>
                        <td className="p-2 text-emerald-400 font-bold">
                          {row.MUSIC_gated ? `${row.MUSIC_gated.toFixed(2)}°` : "N/A (All Gated)"}
                        </td>
                        <td className="p-2 text-slate-400">{row.Bartlett ? `${row.Bartlett.toFixed(2)}°` : "—"}</td>
                        <td className="p-2 text-slate-400">{row.Capon ? `${row.Capon.toFixed(2)}°` : "—"}</td>
                        <td className="p-2 text-slate-400">{row["Interf-LS"] ? `${row["Interf-LS"].toFixed(2)}°` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* SUBVIEW 2: LIVE INTERACTIVE BATCH SIMULATOR                               */}
      {/* ========================================================================= */}
      {subView === "LIVE_BATCHES" && (
        <div className="space-y-4">
          {/* Top Configuration & Preset Selector */}
          <div className="p-4 bg-slate-900/80 rounded-xl border border-slate-800 shadow-md">
            <div className="flex items-center justify-between mb-3">
              <span className="flex items-center font-bold text-sm text-cyan-400">
                <FlaskConical className="w-4 h-4 mr-2" />
                Live Monte Carlo Batch Preset Execution
              </span>

              <button
                onClick={handleRunExperiment}
                disabled={isRunning}
                className={`px-4 py-2 rounded-lg flex items-center space-x-2 font-bold transition-all shadow-md ${
                  isRunning
                    ? "bg-slate-800 text-slate-500 cursor-not-allowed"
                    : "bg-cyan-500 text-slate-950 hover:bg-cyan-400"
                }`}
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>{isRunning ? "Simulating Batches..." : "Execute Experiment"}</span>
              </button>
            </div>

            {/* Preset Selector Dropdown & Description */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
              <div>
                <label htmlFor="experiment-preset-select" className="text-slate-400 block mb-1">
                  Select Experiment Preset:
                </label>
                <select
                  id="experiment-preset-select"
                  name="experiment_preset"
                  value={selectedPresetId}
                  onChange={(e) => setSelectedPresetId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-200 rounded p-2 outline-none focus:border-cyan-500"
                >
                  {presets.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.id}: {p.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="col-span-2 p-2.5 bg-slate-950/60 rounded border border-slate-800/80">
                <div className="text-[11px] text-cyan-400 font-bold mb-1">
                  Research Objective & Parameter Sweep:
                </div>
                <div className="text-[11px] text-slate-300 leading-relaxed">
                  {selectedPreset?.description || "Select a preset to view research objectives."}
                </div>
              </div>
            </div>
          </div>

          {/* Results Viewport */}
          {report && (
            <div className="space-y-4">
              {/* Chart Row */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* RMSE Comparison Chart */}
                <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800">
                  <div className="text-sm font-bold text-cyan-400 mb-2">
                    Direction Finding RMSE (Degrees) vs {report.parameter_name}
                  </div>
                  <div className="h-56 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={report.results} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                        <XAxis dataKey="param_value" stroke="#64748B" fontSize={10} />
                        <YAxis stroke="#64748B" fontSize={10} unit="°" />
                        <Tooltip contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Bar dataKey="compensated_rmse_deg" fill="#00E5FF" name="Proposed A2 Compensated RMSE" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="static_rmse_deg" fill="#EF4444" name="Static 433 Baseline RMSE" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="tracked_rmse_deg" fill="#10B981" name="Gated Track RMSE" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Availability & Rejection Chart */}
                <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800">
                  <div className="text-sm font-bold text-cyan-400 mb-2">
                    Gate Reliability & Track Availability (%)
                  </div>
                  <div className="h-56 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={report.results} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
                        <XAxis dataKey="param_value" stroke="#64748B" fontSize={10} />
                        <YAxis stroke="#64748B" fontSize={10} domain={[0, 100]} unit="%" />
                        <Tooltip contentStyle={{ backgroundColor: "#0F172A", borderColor: "#334155", fontSize: 11 }} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Line type="monotone" dataKey="track_availability_pct" stroke="#10B981" strokeWidth={2} name="Track Availability (%)" />
                        <Line type="monotone" dataKey="multipath_rejection_rate" stroke="#F59E0B" strokeWidth={2} name="Multipath Rejection (%)" />
                        <Line type="monotone" dataKey="false_rejection_rate" stroke="#EF4444" strokeWidth={1.5} strokeDasharray="4 2" name="False Rejection (%)" />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Full Metrics Table */}
              <div className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 overflow-x-auto">
                <div className="text-sm font-bold text-cyan-400 mb-2">
                  Comprehensive Benchmark Dataset ({report.results.length} Batches)
                </div>
                <table className="w-full text-left text-[11px] font-mono border-collapse">
                  <thead>
                    <tr className="border-b border-slate-700 bg-slate-800/60 text-slate-300">
                      <th className="p-2">Parameter ({report.parameter_name})</th>
                      <th className="p-2 text-cyan-400">Comp. RMSE</th>
                      <th className="p-2 text-red-400">Static RMSE</th>
                      <th className="p-2 text-emerald-400">Track RMSE</th>
                      <th className="p-2">Comp. MAE</th>
                      <th className="p-2">Median Err</th>
                      <th className="p-2 text-amber-400">MP Rejection</th>
                      <th className="p-2 text-red-400">False Reject</th>
                      <th className="p-2 text-emerald-400">Availability</th>
                      <th className="p-2">Latency</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.results.map((row, idx) => (
                      <tr key={idx} className="border-b border-slate-800/80 hover:bg-slate-800/30">
                        <td className="p-2 font-bold text-slate-200">{row.param_value}</td>
                        <td className="p-2 text-cyan-300 font-bold">{row.compensated_rmse_deg.toFixed(2)}°</td>
                        <td className="p-2 text-red-300">{row.static_rmse_deg.toFixed(2)}°</td>
                        <td className="p-2 text-emerald-300">{row.tracked_rmse_deg.toFixed(2)}°</td>
                        <td className="p-2">{row.compensated_mae_deg.toFixed(2)}°</td>
                        <td className="p-2">{row.compensated_median_deg.toFixed(2)}°</td>
                        <td className="p-2 text-amber-300 font-bold">{(row.multipath_rejection_rate * 100).toFixed(1)}%</td>
                        <td className="p-2 text-red-300 font-bold">{(row.false_rejection_rate * 100).toFixed(1)}%</td>
                        <td className="p-2 text-emerald-300 font-bold">{row.track_availability_pct.toFixed(1)}%</td>
                        <td className="p-2">{row.mean_latency_ms.toFixed(1)} ms</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
