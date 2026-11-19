"use client";

import React from "react";
import * as THREE from "three";

interface AntennaArray3DProps {
  switchState?: number;
  highlightZoom?: boolean;
}

export function AntennaArray3D({ switchState = 0, highlightZoom = false }: AntennaArray3DProps) {
  // Radius r = 0.072 m (7.2 cm)
  const r = 0.072;
  const mastHeight = 2.0;

  // Elements at 0, 90, 180, 270 deg
  const elements = [
    { id: 0, x: r, z: 0, angle: "0° (E)" },
    { id: 1, x: 0, z: r, angle: "90° (N)" },
    { id: 2, x: -r, z: 0, angle: "180° (W)" },
    { id: 3, x: 0, z: -r, angle: "270° (S)" },
  ];

  return (
    <group position={[0, mastHeight, 0]}>
      {/* Circular Ground Plane / Hub */}
      <mesh position={[0, 0, 0]}>
        <cylinderGeometry args={[0.15, 0.15, 0.02, 32]} />
        <meshStandardMaterial color="#0F172A" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Circular Array Perimeter Ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[r - 0.003, r + 0.003, 32]} />
        <meshBasicMaterial color="#00E5FF" side={THREE.DoubleSide} />
      </mesh>

      {/* 4 Antenna Monopoles */}
      {elements.map((el) => {
        const isActive = switchState === el.id;
        return (
          <group key={el.id} position={[el.x, 0, el.z]}>
            {/* Monopole element rod */}
            <mesh position={[0, 0.08, 0]}>
              <cylinderGeometry args={[0.004, 0.004, 0.16, 12]} />
              <meshStandardMaterial
                color={isActive ? "#FFB300" : "#00E5FF"}
                emissive={isActive ? "#FFB300" : "#00E5FF"}
                emissiveIntensity={isActive ? 0.8 : 0.2}
              />
            </mesh>
            {/* Base feed connector */}
            <mesh position={[0, 0.005, 0]}>
              <cylinderGeometry args={[0.012, 0.012, 0.01, 16]} />
              <meshStandardMaterial color="#64748B" metalness={0.9} />
            </mesh>
          </group>
        );
      })}

      {/* Visual Indicator Halo for macroscopic visibility in 120m arena */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.01, 0]}>
        <ringGeometry args={[0.6, 0.65, 32]} />
        <meshBasicMaterial color="#00E5FF" transparent opacity={0.25} side={THREE.DoubleSide} />
      </mesh>
    </group>
  );
}

