"use client";

import React, { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { UAVState } from "@/types/telemetry";

interface Quadcopter3DProps {
  uav: UAVState;
}

export function Quadcopter3D({ uav }: Quadcopter3DProps) {
  const rotorsRef = useRef<THREE.Group[]>([]);

  // Rotate propellers continuously
  useFrame((_, delta) => {
    rotorsRef.current.forEach((r, idx) => {
      if (r) {
        const dir = idx % 2 === 0 ? 1 : -1;
        r.rotation.y += dir * delta * 40.0;
      }
    });
  });

  const armLen = 0.6;
  const armAngles = [Math.PI / 4, (3 * Math.PI) / 4, (5 * Math.PI) / 4, (7 * Math.PI) / 4];

  // Heading is in degrees
  const headingRad = (uav.heading_deg * Math.PI) / 180.0;
  const pitchRad = ((uav.pitch_deg ?? 0) * Math.PI) / 180.0;

  return (
    <group
      position={[uav.x, uav.y, uav.z]}
      rotation={[pitchRad, -headingRad, 0]}
    >
      {/* Central Aerodynamic Fuselage */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[0.3, 0.1, 0.3]} />
        <meshStandardMaterial color="#0F172A" metalness={0.8} roughness={0.2} />
      </mesh>

      {/* Top Canopy / GNSS Dome */}
      <mesh position={[0, 0.08, 0]}>
        <sphereGeometry args={[0.1, 16, 12]} />
        <meshStandardMaterial color="#00E5FF" metalness={0.9} roughness={0.1} />
      </mesh>

      {/* 4 Carbon Arms & Motor Nacelles */}
      {armAngles.map((ang, i) => {
        const ax = armLen * Math.cos(ang);
        const az = armLen * Math.sin(ang);
        return (
          <group key={i}>
            {/* Carbon Tube Arm */}
            <mesh position={[ax / 2, 0, az / 2]} rotation={[0, -ang + Math.PI / 2, 0]}>
              <cylinderGeometry args={[0.02, 0.02, armLen, 12]} />
              <meshStandardMaterial color="#334155" metalness={0.6} />
            </mesh>

            {/* Motor Pod */}
            <mesh position={[ax, 0.03, az]}>
              <cylinderGeometry args={[0.045, 0.045, 0.06, 16]} />
              <meshStandardMaterial color="#1E293B" metalness={0.9} />
            </mesh>

            {/* Rotating Propeller */}
            <group
              position={[ax, 0.07, az]}
              ref={(el) => {
                if (el) rotorsRef.current[i] = el;
              }}
            >
              <mesh>
                <boxGeometry args={[0.45, 0.005, 0.035]} />
                <meshStandardMaterial color="#94A3B8" transparent opacity={0.8} />
              </mesh>
            </group>
          </group>
        );
      })}

      {/* Front Navigation Beacon (Cyan) */}
      <mesh position={[0.2, 0, 0]}>
        <sphereGeometry args={[0.025, 8, 8]} />
        <meshBasicMaterial color="#00E5FF" />
      </mesh>

      {/* Altitude Shadow on Ground Plane */}
      <mesh position={[0, -uav.y + 0.02, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[0.6, 24]} />
        <meshBasicMaterial color="#000000" transparent opacity={0.3} />
      </mesh>

      {/* Altitude Stanchion Line down to ground */}
      <mesh position={[0, -uav.y / 2, 0]}>
        <cylinderGeometry args={[0.01, 0.01, uav.y, 8]} />
        <meshBasicMaterial color="#334155" transparent opacity={0.6} />
      </mesh>
    </group>
  );
}
