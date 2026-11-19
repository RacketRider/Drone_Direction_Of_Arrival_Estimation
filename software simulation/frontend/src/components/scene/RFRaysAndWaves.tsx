"use client";

import React, { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";
import { TelemetryFrame } from "@/types/telemetry";

interface RFRaysAndWavesProps {
  telemetry: TelemetryFrame | null;
  showBuildings?: boolean;
  showMultiStation?: boolean;
}

export function RFRaysAndWaves({
  telemetry,
  showBuildings = true,
  showMultiStation = false,
}: RFRaysAndWavesProps) {
  const ringsRef = useRef<THREE.Group>(null);
  const trailPointsRef = useRef<[number, number, number][]>([]);

  // Wavelength / Frequency color mapping:
  // 433 MHz -> Cyan (#00E5FF)
  // 868 MHz -> Amber (#FFB300)
  // 902-928 MHz -> Emerald (#00E676)
  const waveColor = useMemo(() => {
    if (!telemetry) return "#00E5FF";
    const f = telemetry.rf.active_freq_mhz;
    if (f < 500) return "#00E5FF";       // 433 MHz
    if (f < 900) return "#FFB300";       // 868 MHz
    return "#00E676";                    // 915-928 MHz
  }, [telemetry?.rf?.active_freq_mhz]);

  // Expanding wave animation
  useFrame((_, delta) => {
    if (ringsRef.current) {
      ringsRef.current.children.forEach((child) => {
        const mesh = child as THREE.Mesh;
        const scale = mesh.scale.x + delta * 2.5;
        if (scale > 15.0) {
          mesh.scale.set(0.2, 0.2, 0.2);
          if (mesh.material instanceof THREE.Material) {
            mesh.material.opacity = 0.8;
          }
        } else {
          mesh.scale.set(scale, scale, scale);
          if (mesh.material instanceof THREE.Material) {
            mesh.material.opacity = Math.max(0.0, 0.8 * (1.0 - scale / 15.0));
          }
        }
      });
    }
  });

  // Track UAV trail points
  useMemo(() => {
    if (telemetry?.uav) {
      trailPointsRef.current.push([telemetry.uav.x, telemetry.uav.y, telemetry.uav.z]);
      if (trailPointsRef.current.length > 200) {
        trailPointsRef.current.shift();
      }
    }
  }, [telemetry?.uav?.x, telemetry?.uav?.y, telemetry?.uav?.z]);

  if (!telemetry) return null;

  const { uav, rf, dsp } = telemetry;
  const gsPos: [number, number, number] = [0, 2.0, 0];
  const uavPos: [number, number, number] = [uav.x, uav.y, uav.z];

  // Ground DoA Bearing vectors constrained to array pedestal radius (r=4.8m)
  const trueBearingRad = (uav.true_azimuth_deg * Math.PI) / 180.0;
  const estBearingRad = (dsp.accepted_track_deg * Math.PI) / 180.0;
  const needleLen = 4.8;

  const trueVectorEnd: [number, number, number] = [
    needleLen * Math.cos(trueBearingRad),
    0.2,
    needleLen * Math.sin(trueBearingRad)
  ];
  const estVectorEnd: [number, number, number] = [
    needleLen * Math.cos(estBearingRad),
    0.25,
    needleLen * Math.sin(estBearingRad)
  ];

  return (
    <group>
      {/* 1. Direct LOS Ray */}
      <Line
        points={[gsPos, uavPos]}
        color={rf.is_occluded ? "#EF4444" : "#00E676"}
        lineWidth={rf.is_occluded ? 1.5 : 2.5}
        dashed={rf.is_occluded}
        dashSize={1}
        gapSize={0.5}
      />

      {/* 2. Reflected NLOS Rays (Only if buildings are enabled) */}
      {showBuildings && rf.nlos_paths.map((p, idx) => {
        const reflPt: [number, number, number] = [p.refl_point[0], p.refl_point[1], p.refl_point[2]];
        return (
          <group key={idx}>
            <Line
              points={[uavPos, reflPt]}
              color="#FFB300"
              lineWidth={1.5}
            />
            <Line
              points={[reflPt, gsPos]}
              color="#FFB300"
              lineWidth={1.5}
            />
          </group>
        );
      })}

      {/* 3. Expanding Spherical Wavefront Rings */}
      <group position={[uav.x, uav.y, uav.z]} ref={ringsRef}>
        {[0, 1, 2, 3].map((idx) => (
          <mesh key={idx} scale={[idx * 3 + 0.5, idx * 3 + 0.5, idx * 3 + 0.5]}>
            <sphereGeometry args={[1, 24, 16]} />
            <meshBasicMaterial
              color={waveColor}
              wireframe
              transparent
              opacity={0.3}
            />
          </mesh>
        ))}
      </group>

      {/* 4. UAV Flight Path Trail */}
      {trailPointsRef.current.length >= 2 && (
        <Line
          points={trailPointsRef.current}
          color={uav.is_avoiding ? "#F59E0B" : "#00E5FF"}
          lineWidth={uav.is_avoiding ? 2.5 : 1.5}
          transparent
          opacity={uav.is_avoiding ? 0.85 : 0.55}
        />
      )}

      {/* 4b. Avoidance Divergence Offset Vector (when avoiding obstacle) */}
      {uav.is_avoiding && uav.nominal_x !== undefined && (
        <group>
          <Line
            points={[
              [uav.nominal_x, uav.nominal_y ?? uav.y, uav.nominal_z ?? uav.z],
              [uav.x, uav.y, uav.z],
            ]}
            color="#F59E0B"
            lineWidth={1.5}
            dashed
            dashSize={0.4}
            gapSize={0.3}
          />
          <mesh position={[uav.nominal_x, uav.nominal_y ?? uav.y, uav.nominal_z ?? uav.z]}>
            <sphereGeometry args={[0.35, 12, 12]} />
            <meshBasicMaterial color="#94A3B8" transparent opacity={0.6} />
          </mesh>
        </group>
      )}

      {/* 4c. Obstructed Pause Warning Beacon */}
      {uav.is_paused && (
        <mesh position={[uav.x, uav.y + 1.2, uav.z]}>
          <sphereGeometry args={[0.5, 16, 16]} />
          <meshBasicMaterial color="#EF4444" wireframe />
        </mesh>
      )}

      {/* 5. Ground Truth Bearing Vector Needle (Pedestal Radial Marker) */}
      <Line
        points={[[0, 0.2, 0], trueVectorEnd]}
        color="#10B981"
        lineWidth={1.5}
        dashed
        dashSize={0.4}
        gapSize={0.3}
      />

      {/* 6. Estimated Bearing Vector Needle & Arrowhead (Pedestal Radar Rose Pointer) */}
      <Line
        points={[[0, 0.25, 0], estVectorEnd]}
        color={dsp.tracker_state === "HOLDING" ? "#FFB300" : "#00E5FF"}
        lineWidth={3.5}
      />
      <mesh
        position={estVectorEnd}
        rotation={[-Math.PI / 2, 0, -estBearingRad + Math.PI / 2]}
      >
        <coneGeometry args={[0.3, 0.7, 12]} />
        <meshBasicMaterial color={dsp.tracker_state === "HOLDING" ? "#FFB300" : "#00E5FF"} />
      </mesh>

      {/* 7. Multi-Station Radar Network Bearing Rays & Triangulation Target (Only when multi-station mode enabled) */}
      {showMultiStation && telemetry.multiradar && (
        <group>
          {telemetry.multiradar.stations.map((st) => {
            if (!st.active || st.id === 1) return null; // Station 1 is rendered at origin
            const stOrigin: [number, number, number] = [st.x, 0.15, st.z];
            const aRad = (st.tracked_bearing_deg * Math.PI) / 180.0;
            const rayLen = Math.min(st.distance_m * 1.1, 40.0);
            const stRayEnd: [number, number, number] = [
              st.x + rayLen * Math.cos(aRad),
              0.15,
              st.z + rayLen * Math.sin(aRad)
            ];

            return (
              <group key={st.id}>
                {/* Station Pedestal Marker */}
                <mesh position={[st.x, 0.4, st.z]}>
                  <cylinderGeometry args={[0.6, 0.8, 0.8, 16]} />
                  <meshStandardMaterial color="#0F172A" metalness={0.8} roughness={0.2} />
                </mesh>
                <mesh position={[st.x, 0.9, st.z]}>
                  <sphereGeometry args={[0.25, 12, 12]} />
                  <meshBasicMaterial color="#00E5FF" />
                </mesh>

                {/* Station Bearing Line toward Drone */}
                <Line
                  points={[stOrigin, stRayEnd]}
                  color="#38BDF8"
                  lineWidth={1.5}
                  dashed
                  dashSize={0.8}
                  gapSize={0.4}
                />
              </group>
            );
          })}

          {/* Triangulated 2D Estimated UAV Location Reticle */}
          {telemetry.multiradar.estimated_pos_xz && (
            <group position={[telemetry.multiradar.estimated_pos_xz[0], 0.12, telemetry.multiradar.estimated_pos_xz[1]]}>
              <mesh rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry args={[0.8, 1.1, 24]} />
                <meshBasicMaterial color="#10B981" transparent opacity={0.7} />
              </mesh>
              <mesh rotation={[-Math.PI / 2, 0, 0]}>
                <circleGeometry args={[0.3, 16]} />
                <meshBasicMaterial color="#10B981" />
              </mesh>
            </group>
          )}
        </group>
      )}
    </group>
  );
}
