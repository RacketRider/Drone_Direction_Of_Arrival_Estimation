"use client";

import React, { useMemo } from "react";
import * as THREE from "three";
import { NLOSPath } from "@/types/telemetry";
import { createBuildingFacadeTexture, createConcreteRoofTexture } from "./proceduralTextures";

interface Buildings3DProps {
  nlosPaths?: NLOSPath[];
  isOccluded?: boolean;
  occludingId?: number | null;
  onSelectObject?: (obj: any) => void;
  selectedId?: string | null;
}

export function Buildings3D({
  nlosPaths = [],
  isOccluded = false,
  occludingId = null,
  onSelectObject,
  selectedId = null,
}: Buildings3DProps) {
  // Building Alpha: x in [-38, -18], z in [-35, -15], height 16m
  // Center: x = -28, z = -25, size: dx = 20, dz = 20, dy = 16
  const bldgAlpha = {
    id: 0,
    name: "Concrete Structure Alpha (Northwest)",
    pos: [-28.0, 8.0, -25.0] as [number, number, number],
    size: [20.0, 16.0, 20.0] as [number, number, number],
    penthousePos: [4.0, 9.0, 4.0] as [number, number, number],
    chillerPos: [-4.0, 8.6, -4.0] as [number, number, number],
  };

  // Building Beta: x in [18, 38], z in [-32, -12], height 19m
  // Center: x = 28, z = -22, size: dx = 20, dz = 20, dy = 19
  const bldgBeta = {
    id: 1,
    name: "Concrete Structure Beta (Northeast)",
    pos: [28.0, 9.5, -22.0] as [number, number, number],
    size: [20.0, 19.0, 20.0] as [number, number, number],
    penthousePos: [-4.0, 10.5, 4.0] as [number, number, number],
    chillerPos: [4.0, 10.1, -4.0] as [number, number, number],
  };

  const buildings = [bldgAlpha, bldgBeta];

  // Procedural Textures
  const facadeTex = useMemo(() => {
    const tex = createBuildingFacadeTexture();
    tex.repeat.set(2, 2);
    return tex;
  }, []);

  const roofTex = useMemo(() => {
    const tex = createConcreteRoofTexture();
    tex.repeat.set(4, 4);
    return tex;
  }, []);

  // Multi-material cube: [right, left, top, bottom, front, back]
  const wallMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        map: facadeTex,
        roughness: 0.35,
        metalness: 0.25,
      }),
    [facadeTex]
  );

  const roofMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        map: roofTex,
        roughness: 0.9,
        metalness: 0.1,
      }),
    [roofTex]
  );

  const baseMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#1A222D",
        roughness: 0.95,
      }),
    []
  );

  const hvacMaterial = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#64748B",
        metalness: 0.7,
        roughness: 0.3,
      }),
    []
  );

  const materialsList = useMemo(
    () => [
      wallMaterial, // px
      wallMaterial, // nx
      roofMaterial, // py (Roof)
      baseMaterial, // ny (Base)
      wallMaterial, // pz
      wallMaterial, // nz
    ],
    [wallMaterial, roofMaterial, baseMaterial]
  );

  return (
    <group name="ArchitecturalBuildings">
      {buildings.map((bldg) => {
        const isCausingOcclusion = isOccluded && occludingId === bldg.id;
        const activeRefls = nlosPaths.filter((p) => p.building_id === bldg.id);
        const hasReflection = activeRefls.length > 0;
        const halfY = bldg.size[1] / 2;
        const halfX = bldg.size[0] / 2;
        const halfZ = bldg.size[2] / 2;

        const isSelected = selectedId === `bldg_${bldg.id}`;

        return (
          <group key={bldg.id} position={bldg.pos}>
            {/* 1. Main Architectural Building Box with Windows & Facade Textures */}
            <mesh
              material={materialsList}
              castShadow
              receiveShadow
              onClick={(e) => {
                e.stopPropagation();
                onSelectObject?.({
                  id: `bldg_${bldg.id}`,
                  name: bldg.name,
                  type: "building",
                  position: bldg.pos,
                  size: bldg.size,
                  materialName: "Reinforced Concrete Facade & Tinted Glass",
                  epsilon_r: 5.5,
                  conductivity_s_m: 0.025,
                  tan_delta_e: 0.03,
                  fresnel_refl_pct: 40.8,
                  impedance_ohm: 160.1,
                  skin_depth_m: 0.37,
                });
              }}
              onPointerOver={(e) => {
                e.stopPropagation();
                document.body.style.cursor = "pointer";
              }}
              onPointerOut={() => {
                document.body.style.cursor = "default";
              }}
            >
              <boxGeometry args={bldg.size} />
            </mesh>

            {/* Glowing Selection Frame if Selected */}
            {isSelected && (
              <lineSegments>
                <edgesGeometry args={[new THREE.BoxGeometry(bldg.size[0] + 0.4, bldg.size[1] + 0.4, bldg.size[2] + 0.4)]} />
                <lineBasicMaterial color="#FFB300" linewidth={3} />
              </lineSegments>
            )}

            {/* Subtle Edge Accent Outline */}
            <lineSegments>
              <edgesGeometry args={[new THREE.BoxGeometry(...bldg.size)]} />
              <lineBasicMaterial
                color={isSelected ? "#FFB300" : isCausingOcclusion ? "#EF4444" : hasReflection ? "#FFB300" : "#64748B"}
                linewidth={isSelected ? 2.5 : 1.5}
              />
            </lineSegments>

            {/* 2. Concrete Ground Foundation Plinth */}
            <mesh position={[0, -halfY + 0.3, 0]} receiveShadow>
              <boxGeometry args={[bldg.size[0] + 1.2, 0.6, bldg.size[2] + 1.2]} />
              <meshStandardMaterial color="#0F172A" roughness={0.9} />
            </mesh>

            {/* 3. Rooftop Parapet Perimeter Walls */}
            <group position={[0, halfY + 0.35, 0]}>
              {/* North Parapet */}
              <mesh position={[0, 0, -halfZ + 0.15]} castShadow>
                <boxGeometry args={[bldg.size[0], 0.7, 0.3]} />
                <meshStandardMaterial color="#334155" roughness={0.8} />
              </mesh>
              {/* South Parapet */}
              <mesh position={[0, 0, halfZ - 0.15]} castShadow>
                <boxGeometry args={[bldg.size[0], 0.7, 0.3]} />
                <meshStandardMaterial color="#334155" roughness={0.8} />
              </mesh>
              {/* West Parapet */}
              <mesh position={[-halfX + 0.15, 0, 0]} castShadow>
                <boxGeometry args={[0.3, 0.7, bldg.size[2] - 0.6]} />
                <meshStandardMaterial color="#334155" roughness={0.8} />
              </mesh>
              {/* East Parapet */}
              <mesh position={[halfX - 0.15, 0, 0]} castShadow>
                <boxGeometry args={[0.3, 0.7, bldg.size[2] - 0.6]} />
                <meshStandardMaterial color="#334155" roughness={0.8} />
              </mesh>
            </group>

            {/* 4. Rooftop Mechanical Penthouse (Elevator/Stairs) */}
            <mesh
              position={[bldg.penthousePos[0], halfY + 1.2, bldg.penthousePos[2]]}
              castShadow
              receiveShadow
            >
              <boxGeometry args={[5.0, 2.4, 5.0]} />
              <meshStandardMaterial color="#1E293B" roughness={0.6} metalness={0.3} />
            </mesh>

            {/* 5. Rooftop HVAC Chiller Equipment Unit with Fans */}
            <group position={[bldg.chillerPos[0], halfY + 0.8, bldg.chillerPos[2]]}>
              <mesh material={hvacMaterial} castShadow>
                <boxGeometry args={[4.2, 1.6, 2.8]} />
              </mesh>
              {/* Chiller Fan Discs */}
              <mesh position={[-1.0, 0.81, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                <circleGeometry args={[0.7, 16]} />
                <meshStandardMaterial color="#0F172A" metalness={0.9} />
              </mesh>
              <mesh position={[1.0, 0.81, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                <circleGeometry args={[0.7, 16]} />
                <meshStandardMaterial color="#0F172A" metalness={0.9} />
              </mesh>
            </group>

            {/* 6. Rooftop Communications Antenna Mast */}
            <group position={[0, halfY + 2.0, 0]}>
              <mesh castShadow>
                <cylinderGeometry args={[0.06, 0.08, 4.0, 8]} />
                <meshStandardMaterial color="#E2E8F0" metalness={0.9} roughness={0.2} />
              </mesh>
              {/* Top Whip Beacon */}
              <mesh position={[0, 2.05, 0]}>
                <sphereGeometry args={[0.15, 12, 12]} />
                <meshBasicMaterial color="#EF4444" />
              </mesh>
              <pointLight position={[0, 2.1, 0]} color="#EF4444" intensity={0.6} distance={15} />
            </group>

            {/* 7. Four Corner Red Aviation Obstruction Lights */}
            {[
              [-halfX + 0.2, halfZ - 0.2],
              [halfX - 0.2, halfZ - 0.2],
              [-halfX + 0.2, -halfZ + 0.2],
              [halfX - 0.2, -halfZ + 0.2],
            ].map(([cx, cz], i) => (
              <mesh key={i} position={[cx, halfY + 0.8, cz]}>
                <sphereGeometry args={[0.16, 10, 10]} />
                <meshBasicMaterial color="#FF1E38" />
              </mesh>
            ))}

            {/* 8. Collision Safety Boundary Envelope */}
            <group position={[0, 1.5, 0]}>
              <mesh>
                <boxGeometry args={[bldg.size[0] + 6.0, bldg.size[1] + 3.0, bldg.size[2] + 6.0]} />
                <meshBasicMaterial
                  color="#0284c7"
                  transparent
                  opacity={0.03}
                  depthWrite={false}
                />
              </mesh>
              <lineSegments>
                <edgesGeometry
                  args={[
                    new THREE.BoxGeometry(
                      bldg.size[0] + 6.0,
                      bldg.size[1] + 3.0,
                      bldg.size[2] + 6.0
                    ),
                  ]}
                />
                <lineBasicMaterial
                  color="#38bdf8"
                  transparent
                  opacity={0.22}
                  linewidth={1}
                />
              </lineSegments>
            </group>
          </group>
        );
      })}

      {/* 9. Specular Reflection Highlight Points */}
      {nlosPaths.map((path, idx) => (
        <group key={idx} position={path.refl_point}>
          <mesh>
            <sphereGeometry args={[0.6, 16, 16]} />
            <meshBasicMaterial color="#FFB300" />
          </mesh>
          <pointLight color="#FFB300" intensity={1.5} distance={6} />
        </group>
      ))}
    </group>
  );
}
