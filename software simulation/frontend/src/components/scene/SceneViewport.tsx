"use client";

import React, { useRef, useState, useEffect, useMemo } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, PerspectiveCamera } from "@react-three/drei";
import * as THREE from "three";

import { TelemetryFrame } from "@/types/telemetry";
import { ArenaGrid, GroundType } from "./ArenaGrid";
import { AntennaArray3D } from "./AntennaArray3D";
import { Buildings3D } from "./Buildings3D";
import { Quadcopter3D } from "./Quadcopter3D";
import { RFRaysAndWaves } from "./RFRaysAndWaves";
import { ForestTrees3D } from "./ForestTrees3D";
import { ReflectedWaveVisualizer, SelectedObjectInfo } from "./ReflectedWaveVisualizer";
import {
  Camera,
  Compass,
  Eye,
  Crosshair,
  Trees,
  Building2,
  SlidersHorizontal,
  Sun,
  Sunset,
  Moon,
  Zap,
  X,
  Shield,
  Radio,
} from "lucide-react";

interface SceneViewportProps {
  telemetry: TelemetryFrame | null;
  onCommand?: (cmd: any) => void;
}

type CameraPreset = "ISOMETRIC" | "TOP_DOWN" | "ARRAY_ZOOM" | "FOLLOW_UAV";
type SkyMode = "DAYLIGHT" | "SUNSET" | "NIGHT_HUD";
type EnvPreset = "FOREST" | "WOODLAND_URBAN" | "URBAN_RANGE";

function CameraController({
  preset,
  uavPos,
}: {
  preset: CameraPreset;
  uavPos: [number, number, number];
}) {
  const controlsRef = useRef<any>(null);

  useEffect(() => {
    if (!controlsRef.current) return;
    const controls = controlsRef.current;

    if (preset === "ISOMETRIC") {
      controls.object.position.set(45, 40, 55);
      controls.target.set(0, 10, 0);
    } else if (preset === "TOP_DOWN") {
      controls.object.position.set(0, 95, 0.01);
      controls.target.set(0, 0, 0);
    } else if (preset === "ARRAY_ZOOM") {
      controls.object.position.set(0.6, 2.6, 0.8);
      controls.target.set(0, 2.0, 0);
    }
    controls.update();
  }, [preset]);

  useFrame(() => {
    if (preset === "FOLLOW_UAV" && controlsRef.current) {
      const controls = controlsRef.current;
      controls.target.lerp(new THREE.Vector3(...uavPos), 0.1);
      controls.update();
    }
  });

  return (
    <OrbitControls
      ref={controlsRef}
      enableDamping
      dampingFactor={0.05}
      maxPolarAngle={Math.PI / 2 - 0.02}
      minDistance={0.2}
      maxDistance={220}
    />
  );
}

export function SceneViewport({ telemetry, onCommand }: SceneViewportProps) {
  const [cameraPreset, setCameraPreset] = useState<CameraPreset>("ISOMETRIC");
  // Sky Time-of-Day Selection
  const [skyMode, setSkyMode] = useState<SkyMode>("DAYLIGHT");
  // Environment Preset
  const [envPreset, setEnvPreset] = useState<EnvPreset>("WOODLAND_URBAN");
  const [foliageDensity, setFoliageDensity] = useState<number>(0.45);
  const [showFoliageControl, setShowFoliageControl] = useState<boolean>(false);
  // Interactive Object Selection for Reflected Waves
  const [selectedObject, setSelectedObject] = useState<SelectedObjectInfo | null>(null);
  // Multi-Station Radar Network Display Toggle (auxiliary stations 2 & 3)
  const [showMultiStation, setShowMultiStation] = useState<boolean>(false);

  const uavPos: [number, number, number] = telemetry?.uav
    ? [telemetry.uav.x, telemetry.uav.y, telemetry.uav.z]
    : [0, 18, 0];

  // Environment mode logic:
  // FOREST: showTrees = true, showBuildings = false (No buildings in pure forest!)
  // URBAN: showTrees = false, showBuildings = true
  // MIXED: showTrees = true, showBuildings = true
  const showBuildings = envPreset !== "FOREST";
  const showTrees = envPreset !== "URBAN_RANGE";
  const groundType: GroundType =
    envPreset === "URBAN_RANGE" ? "pavement" : envPreset === "FOREST" ? "grass" : "soil";

  // Sky Lighting Configurations
  const skyConfig = {
    DAYLIGHT: {
      background: "#4A7C9F",
      fogColor: "#4A7C9F",
      fogNear: 85,
      fogFar: 260,
      sunColor: "#FFFEE8",
      sunIntensity: 2.1,
      sunPos: [45, 75, 40] as [number, number, number],
      hemiSky: "#A8D5F5",
      hemiGround: "#1E3520",
      hemiIntensity: 1.05,
      ambientIntensity: 0.5,
    },
    SUNSET: {
      background: "#321A1A",
      fogColor: "#321A1A",
      fogNear: 75,
      fogFar: 230,
      sunColor: "#F59E0B",
      sunIntensity: 2.4,
      sunPos: [-60, 26, 45] as [number, number, number],
      hemiSky: "#F97316",
      hemiGround: "#1E0F0A",
      hemiIntensity: 1.1,
      ambientIntensity: 0.35,
    },
    NIGHT_HUD: {
      background: "#070B12",
      fogColor: "#070B12",
      fogNear: 65,
      fogFar: 195,
      sunColor: "#38BDF8",
      sunIntensity: 0.8,
      sunPos: [35, 60, 40] as [number, number, number],
      hemiSky: "#1E293B",
      hemiGround: "#050B14",
      hemiIntensity: 0.5,
      ambientIntensity: 0.25,
    },
  }[skyMode];

  const handleEnvPresetChange = (preset: EnvPreset) => {
    setEnvPreset(preset);
    let newDensity = 0.0;
    if (preset === "FOREST") newDensity = 0.85;
    else if (preset === "WOODLAND_URBAN") newDensity = 0.45;
    setFoliageDensity(newDensity);

    const buildingsEnabled = preset !== "FOREST";
    onCommand?.({
      action: "SET_ENVIRONMENT",
      preset: preset,
      buildings_enabled: buildingsEnabled,
      foliage_density: newDensity,
    });
  };

  // Distance & propagation metrics for selected reflector
  const reflectionMetrics = useMemo(() => {
    if (!selectedObject) return null;
    const [ox, oy, oz] = selectedObject.position;
    const [ux, uy, uz] = uavPos;
    // Distance from UAV to object
    const d1 = Math.hypot(ox - ux, oy - uy, oz - uz);
    // Distance from object to array at [0, 2.0, 0]
    const d2 = Math.hypot(ox - 0, oy - 2.0, oz - 0);
    const totalDist = d1 + d2;
    // Direct LOS distance
    const losDist = Math.hypot(ux, uy, uz);
    const excessDist = totalDist - losDist;
    const excessDelayNs = (excessDist / 299792458) * 1e9;

    return {
      totalDistM: totalDist,
      excessDistM: Math.max(0, excessDist),
      excessDelayNs: Math.max(0, excessDelayNs),
    };
  }, [selectedObject, uavPos]);

  return (
    <div className="relative w-full h-full bg-[#070B12] select-none overflow-hidden rounded-xl border border-slate-800">
      {/* 3D WebGL Canvas */}
      <Canvas shadows gl={{ antialias: true, alpha: false }}>
        {/* Dynamic Sky Background & Depth Fog */}
        <color attach="background" args={[skyConfig.background]} />
        <fog attach="fog" args={[skyConfig.fogColor, skyConfig.fogNear, skyConfig.fogFar]} />

        <PerspectiveCamera makeDefault position={[45, 40, 55]} fov={45} />
        <CameraController preset={cameraPreset} uavPos={uavPos} />

        {/* Dynamic Multi-Source Sunlight & Hemisphere Sky Lighting */}
        <ambientLight intensity={skyConfig.ambientIntensity} />
        <hemisphereLight
          args={[skyConfig.hemiSky, skyConfig.hemiGround, skyConfig.hemiIntensity]}
        />
        <directionalLight
          position={skyConfig.sunPos}
          intensity={skyConfig.sunIntensity}
          color={skyConfig.sunColor}
          castShadow
          shadow-mapSize-width={2048}
          shadow-mapSize-height={2048}
          shadow-camera-left={-70}
          shadow-camera-right={70}
          shadow-camera-top={70}
          shadow-camera-bottom={-70}
        />
        <pointLight position={[0, 4.5, 0]} intensity={1.4} color="#00E5FF" distance={40} />

        {/* 1. Ground Terrain & Precision Grid */}
        <ArenaGrid groundType={groundType} />

        {/* 2. Procedural Forest Trees, Foliage & Rocks (Hidden in pure Urban mode) */}
        {showTrees && (
          <ForestTrees3D
            foliageDensity={foliageDensity}
            visible={foliageDensity > 0.02}
            onSelectObject={setSelectedObject}
            selectedId={selectedObject?.id}
          />
        )}

        {/* 3. High-Fidelity Buildings with Window Facades (Hidden in pure Forest mode) */}
        {showBuildings && (
          <Buildings3D
            nlosPaths={telemetry?.rf?.nlos_paths}
            isOccluded={telemetry?.rf?.is_occluded}
            occludingId={null}
            onSelectObject={setSelectedObject}
            selectedId={selectedObject?.id}
          />
        )}

        {/* 4. Interactive Reflected Waves & Multipath Ray Visualizer */}
        <ReflectedWaveVisualizer selectedObject={selectedObject} uavPos={uavPos} />

        {/* 5. Switched 4-Element UCA Receiving Array */}
        <AntennaArray3D />

        {/* 6. Transmitting UAV Quadcopter */}
        {telemetry?.uav && <Quadcopter3D uav={telemetry.uav} />}

        {/* 7. RF Rays, Waves & Multi-Station Bearings */}
        <RFRaysAndWaves
          telemetry={telemetry}
          showBuildings={showBuildings}
          showMultiStation={showMultiStation}
        />
      </Canvas>

      {/* TOP HEADER CONTROLS BAR: Camera, Environment & Time-of-Day */}
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between flex-wrap gap-2 pointer-events-none z-10 text-xs">
        {/* TOP LEFT: Camera Preset Controls */}
        <div className="pointer-events-auto flex items-center space-x-1.5 bg-slate-900/90 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/60 shadow-lg">
          <button
            onClick={() => setCameraPreset("ISOMETRIC")}
            className={`px-2.5 py-1 rounded flex items-center space-x-1 font-mono transition-colors ${
              cameraPreset === "ISOMETRIC"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="Isometric Tactical Perspective"
          >
            <Camera className="w-3.5 h-3.5 mr-1" />
            <span>Isometric</span>
          </button>

          <button
            onClick={() => setCameraPreset("TOP_DOWN")}
            className={`px-2.5 py-1 rounded flex items-center space-x-1 font-mono transition-colors ${
              cameraPreset === "TOP_DOWN"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="Top-Down Orthographic Radar View"
          >
            <Compass className="w-3.5 h-3.5 mr-1" />
            <span>Top-Down Radar</span>
          </button>

          <button
            onClick={() => setCameraPreset("ARRAY_ZOOM")}
            className={`px-2.5 py-1 rounded flex items-center space-x-1 font-mono transition-colors ${
              cameraPreset === "ARRAY_ZOOM"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="Zoom to 4-Element UCA Array (r=7.2cm)"
          >
            <Crosshair className="w-3.5 h-3.5 mr-1" />
            <span>Array Micro-Zoom</span>
          </button>

          <button
            onClick={() => setCameraPreset("FOLLOW_UAV")}
            className={`px-2.5 py-1 rounded flex items-center space-x-1 font-mono transition-colors ${
              cameraPreset === "FOLLOW_UAV"
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
            title="Follow UAV Trajectory"
          >
            <Eye className="w-3.5 h-3.5 mr-1" />
            <span>Follow UAV</span>
          </button>
        </div>

        {/* TOP RIGHT: Environment, Foliage Density & Time-of-Day Toolbars */}
        <div className="pointer-events-auto flex items-center space-x-2">
          {/* Environment Presets (Forest / Mixed / Urban) */}
          <div className="flex items-center space-x-1 bg-slate-900/90 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/60 shadow-lg">
            <button
              onClick={() => handleEnvPresetChange("FOREST")}
              className={`px-2.5 py-1 rounded flex items-center space-x-1 font-mono text-[11px] transition-colors ${
                envPreset === "FOREST"
                  ? "bg-emerald-600/30 text-emerald-300 border border-emerald-500/50"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Dense Pine & Deciduous Forest (No Buildings)"
            >
              <Trees className="w-3.5 h-3.5 mr-1 text-emerald-400" />
              <span>Forest</span>
            </button>

            <button
              onClick={() => handleEnvPresetChange("WOODLAND_URBAN")}
              className={`px-2.5 py-1 rounded flex items-center space-x-1 font-mono text-[11px] transition-colors ${
                envPreset === "WOODLAND_URBAN"
                  ? "bg-cyan-600/30 text-cyan-300 border border-cyan-500/50"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Mixed Woodland with Concrete Obstacles"
            >
              <span className="text-cyan-400 mr-1">🌲+🏛️</span>
              <span>Mixed</span>
            </button>

            <button
              onClick={() => handleEnvPresetChange("URBAN_RANGE")}
              className={`px-2.5 py-1 rounded flex items-center space-x-1 font-mono text-[11px] transition-colors ${
                envPreset === "URBAN_RANGE"
                  ? "bg-amber-600/30 text-amber-300 border border-amber-500/50"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Tactical Urban Obstacle Range (Buildings Only)"
            >
              <Building2 className="w-3.5 h-3.5 mr-1 text-amber-400" />
              <span>Urban</span>
            </button>

            {/* Foliage Slider Toggle */}
            <button
              onClick={() => setShowFoliageControl(!showFoliageControl)}
              className={`px-2 py-1 rounded ml-1 flex items-center space-x-1 font-mono text-[11px] border transition-colors ${
                showFoliageControl
                  ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40"
                  : "bg-slate-800/80 text-slate-300 border-slate-700 hover:bg-slate-700"
              }`}
              title="Adjust Foliage Density & Tree Count"
            >
              <SlidersHorizontal className="w-3 h-3 text-cyan-400" />
              <span>{Math.round(foliageDensity * 100)}%</span>
            </button>
          </div>

          {/* Time of Day / Sky Lighting Mode Toggle */}
          <div className="flex items-center space-x-1 bg-slate-900/90 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/60 shadow-lg">
            <button
              onClick={() => setSkyMode("DAYLIGHT")}
              className={`px-2 py-1 rounded flex items-center space-x-1 text-[11px] font-mono transition-colors ${
                skyMode === "DAYLIGHT"
                  ? "bg-sky-500/25 text-sky-300 border border-sky-400/50"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Daylight Tactical Testing"
            >
              <Sun className="w-3.5 h-3.5 text-yellow-400 mr-1" />
              <span>Day</span>
            </button>

            <button
              onClick={() => setSkyMode("SUNSET")}
              className={`px-2 py-1 rounded flex items-center space-x-1 text-[11px] font-mono transition-colors ${
                skyMode === "SUNSET"
                  ? "bg-amber-500/25 text-amber-300 border border-amber-400/50"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Golden Sunset Recon"
            >
              <Sunset className="w-3.5 h-3.5 text-amber-400 mr-1" />
              <span>Sunset</span>
            </button>

            <button
              onClick={() => setSkyMode("NIGHT_HUD")}
              className={`px-2 py-1 rounded flex items-center space-x-1 text-[11px] font-mono transition-colors ${
                skyMode === "NIGHT_HUD"
                  ? "bg-indigo-500/25 text-indigo-300 border border-indigo-400/50"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Night Aerospace HUD"
            >
              <Moon className="w-3.5 h-3.5 text-indigo-400 mr-1" />
              <span>Night</span>
            </button>
          </div>

          {/* Multi-Station Triangulation Radar Network Toggle */}
          <div className="flex items-center space-x-1 bg-slate-900/90 backdrop-blur-md p-1.5 rounded-lg border border-slate-700/60 shadow-lg">
            <button
              onClick={() => setShowMultiStation(!showMultiStation)}
              className={`px-2.5 py-1 rounded flex items-center space-x-1 font-mono text-[11px] transition-colors ${
                showMultiStation
                  ? "bg-purple-600/30 text-purple-300 border border-purple-500/50 font-bold"
                  : "text-slate-400 hover:text-slate-200"
              }`}
              title="Toggle Auxiliary DF Stations 2 & 3 for 2D Multi-Radar Triangulation"
            >
              <Radio className="w-3.5 h-3.5 mr-1 text-purple-400" />
              <span>Multi-Radar: {showMultiStation ? "ON" : "OFF"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Floating Foliage Density Popup Slider */}
      {showFoliageControl && (
        <div className="absolute top-14 right-28 bg-slate-900/95 backdrop-blur-md p-3.5 rounded-xl border border-slate-700 shadow-2xl z-20 w-64 space-y-2.5 text-xs font-mono">
          <label htmlFor="foliage-density-slider" className="flex justify-between items-center text-slate-300 cursor-pointer">
            <span className="flex items-center text-emerald-400 font-bold">
              <Trees className="w-3.5 h-3.5 mr-1.5" />
              Foliage Density
            </span>
            <span className="font-bold text-slate-100">{Math.round(foliageDensity * 100)}%</span>
          </label>

          <input
            id="foliage-density-slider"
            name="foliage-density"
            type="range"
            min="0.0"
            max="1.0"
            step="0.05"
            value={foliageDensity}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              setFoliageDensity(val);
              onCommand?.({ action: "SET_FOLIAGE_DENSITY", foliage_density: val });
            }}
            className="w-full accent-emerald-400 h-1.5 bg-slate-700 rounded-lg cursor-pointer"
          />

          <div className="flex justify-between text-[10px] text-slate-400 pt-0.5">
            <span>Clear (0%)</span>
            <span>Medium (50%)</span>
            <span>Dense Forest</span>
          </div>

          <div className="text-[10px] text-slate-400 border-t border-slate-800 pt-1.5 leading-relaxed">
            Vegetation attenuation: <span className="text-amber-400 font-bold">~{(foliageDensity * 1.55).toFixed(2)} dB/m</span> (ITU-R P.833).
          </div>
        </div>
      )}

      {/* BOTTOM RIGHT: Interactive Object Material & Reflected Waves Inspector Card */}
      {selectedObject ? (
        <div className="absolute bottom-3 right-3 bg-slate-900/95 backdrop-blur-md p-3.5 rounded-xl border border-amber-500/40 shadow-2xl z-20 w-80 space-y-2 text-xs font-mono text-slate-200 animate-in fade-in slide-in-from-bottom-2 duration-200">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center space-x-1.5">
              <Zap className="w-4 h-4 text-amber-400 animate-pulse" />
              <span className="font-bold text-slate-100 truncate text-[11px] max-w-[200px]">
                {selectedObject.name}
              </span>
            </div>
            <button
              onClick={() => setSelectedObject(null)}
              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-slate-100"
              title="Deselect Object"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Reflected Wave Status */}
          <div className="p-2 bg-amber-950/30 rounded border border-amber-500/30 text-[10px] space-y-1">
            <div className="flex justify-between text-amber-300 font-bold">
              <span>Reflected Ray Path:</span>
              <span>UAV → Object → UCA</span>
            </div>
            {reflectionMetrics && (
              <div className="flex justify-between text-slate-400">
                <span>Excess Path / Delay:</span>
                <span className="text-amber-400 font-bold">
                  +{reflectionMetrics.excessDistM.toFixed(1)} m ({reflectionMetrics.excessDelayNs.toFixed(1)} ns)
                </span>
              </div>
            )}
            <div className="text-[9px] text-slate-400 italic">
              Concentric wave ripples radiating from reflection surface.
            </div>
          </div>

          {/* Material Electromagnetic Parameters */}
          <div className="space-y-1.5 text-[10px]">
            <div className="flex justify-between text-slate-400">
              <span>Material Class:</span>
              <span className="text-slate-200 font-bold">{selectedObject.materialName}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Relative Permittivity (εr):</span>
              <span className="text-cyan-400 font-bold">{selectedObject.epsilon_r.toFixed(1)}</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Conductivity (σ):</span>
              <span className="text-slate-200 font-bold">{selectedObject.conductivity_s_m.toFixed(3)} S/m</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Fresnel Reflectivity (|Γ|):</span>
              <span className="text-amber-400 font-bold">{selectedObject.fresnel_refl_pct.toFixed(1)}%</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Wave Impedance (η):</span>
              <span className="text-slate-200 font-bold">{selectedObject.impedance_ohm.toFixed(1)} Ω</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Skin Depth (δ):</span>
              <span className="text-emerald-400 font-bold">{selectedObject.skin_depth_m.toFixed(2)} m</span>
            </div>
          </div>

          {/* Multi-Ray Electromagnetic Probe Legend */}
          <div className="pt-2 border-t border-slate-800 text-[9px] space-y-1">
            <div className="text-slate-400 font-bold flex items-center justify-between">
              <span>Ray Mechanism:</span>
              <span className="text-slate-500 italic">Snell + Fresnel</span>
            </div>
            <div className="grid grid-cols-2 gap-1 text-[9px]">
              <span className="flex items-center text-amber-300">
                <span className="w-2 h-2 rounded-full bg-[#F59E0B] mr-1 inline-block" /> Incident Bundle
              </span>
              <span className="flex items-center text-orange-400">
                <span className="w-2 h-2 rounded-full bg-[#FF9F43] mr-1 inline-block" /> Specular Bounce
              </span>
              <span className="flex items-center text-emerald-400">
                <span className="w-2 h-2 rounded-full bg-[#10B981] mr-1 inline-block" /> Refracted Inside
              </span>
              <span className="flex items-center text-sky-400">
                <span className="w-2 h-2 rounded-full bg-[#38BDF8] mr-1 inline-block" /> Rear Exit Wave
              </span>
              <span className="flex items-center text-slate-300">
                <span className="w-2 h-2 rounded-full bg-[#E2E8F0] mr-1 inline-block" /> Surface Normal
              </span>
              <span className="flex items-center text-slate-400">
                <span className="w-2 h-2 rounded-full bg-[#94A3B8] mr-1 inline-block" /> Diffuse Scatter
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="absolute bottom-3 right-3 bg-slate-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-800 text-[10px] font-mono text-slate-400 flex items-center space-x-1.5 shadow-md">
          <Zap className="w-3 h-3 text-amber-400" />
          <span>Click any building, tree, or rock to view reflected waves & material physics</span>
        </div>
      )}

      {/* BOTTOM LEFT: Arena Dimensions & Environment Badge */}
      <div className="absolute bottom-3 left-3 bg-slate-900/85 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-800 text-[11px] font-mono text-slate-300 flex items-center space-x-3 shadow-md">
        <span>Arena: 120m × 120m</span>
        <span className="text-slate-600">|</span>
        <span className="text-emerald-400 flex items-center">
          <Trees className="w-3 h-3 mr-1" />
          {envPreset === "FOREST" ? "Dense Forest (No Buildings)" : envPreset === "WOODLAND_URBAN" ? "Mixed Woodland" : "Urban Obstacle Range"}
        </span>
        <span className="text-slate-600">|</span>
        <span className="flex items-center text-sky-300">
          <Sun className="w-3 h-3 mr-1 text-yellow-400" />
          {skyMode}
        </span>
      </div>
    </div>
  );
}
