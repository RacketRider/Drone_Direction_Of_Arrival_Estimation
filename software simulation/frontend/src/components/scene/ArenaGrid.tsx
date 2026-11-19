"use client";

import React, { useMemo } from "react";
import * as THREE from "three";
import { createTerrainTexture } from "./proceduralTextures";

export type GroundType = "grass" | "soil" | "pavement";

interface ArenaGridProps {
  groundType?: GroundType;
  showGrid?: boolean;
}

export function ArenaGrid({ groundType = "grass", showGrid = true }: ArenaGridProps) {
  // Terrain Texture
  const terrainTex = useMemo(() => {
    return createTerrainTexture(groundType);
  }, [groundType]);

  const groundMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        map: terrainTex,
        roughness: groundType === "pavement" ? 0.75 : 0.9,
        metalness: groundType === "pavement" ? 0.15 : 0.02,
      }),
    [terrainTex, groundType]
  );

  return (
    <group name="TerrainAndArenaGrid">
      {/* 1. Solid Ground Terrain Mesh (180m x 180m) */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.05, 0]} receiveShadow material={groundMat}>
        <planeGeometry args={[180, 180]} />
      </mesh>

      {/* 2. Precision Engineering Grid on top */}
      {showGrid && (
        <gridHelper
          args={[120, 60, "#00E5FF", groundType === "grass" ? "#1E3A24" : "#1E2B42"]}
          position={[0, 0.01, 0]}
        />
      )}

      {/* 3. Central Antenna Site Tactical Circular Platform */}
      <mesh position={[0, 0.06, 0]} receiveShadow castShadow>
        <cylinderGeometry args={[3.2, 3.5, 0.12, 48]} />
        <meshStandardMaterial color="#1E293B" metalness={0.7} roughness={0.3} />
      </mesh>

      {/* Outer Tactical Border Ring */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.13, 0]}>
        <ringGeometry args={[3.0, 3.15, 64]} />
        <meshBasicMaterial color="#00E5FF" side={THREE.DoubleSide} />
      </mesh>

      {/* Central Mast */}
      <mesh position={[0, 1.0, 0]} castShadow>
        <cylinderGeometry args={[0.08, 0.12, 2.0, 16]} />
        <meshStandardMaterial color="#94A3B8" metalness={0.9} roughness={0.15} />
      </mesh>

      {/* 4. Compass Range Rings at 10m, 25m, 45m */}
      {[10, 25, 45].map((rad) => (
        <mesh key={rad} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.03, 0]}>
          <ringGeometry args={[rad - 0.08, rad + 0.08, 96]} />
          <meshBasicMaterial
            color={groundType === "grass" ? "#52B788" : "#38BDF8"}
            transparent
            opacity={0.35}
            side={THREE.DoubleSide}
          />
        </mesh>
      ))}

      {/* 5. Compass Cardinal Direction Lines (N, S, E, W) */}
      <group position={[0, 0.04, 0]}>
        {/* +X (East, Red/Amber) */}
        <mesh position={[30, 0, 0]}>
          <boxGeometry args={[60, 0.02, 0.1]} />
          <meshBasicMaterial color="#F59E0B" transparent opacity={0.3} />
        </mesh>
        {/* +Z (South/North, Cyan) */}
        <mesh position={[0, 0, 30]}>
          <boxGeometry args={[0.1, 0.02, 60]} />
          <meshBasicMaterial color="#00E5FF" transparent opacity={0.3} />
        </mesh>
      </group>
    </group>
  );
}
