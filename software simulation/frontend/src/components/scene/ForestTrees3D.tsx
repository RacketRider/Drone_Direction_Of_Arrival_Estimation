"use client";

import React, { useMemo } from "react";
import * as THREE from "three";

interface ForestTrees3DProps {
  foliageDensity: number; // 0.0 to 1.0
  visible?: boolean;
  onSelectObject?: (obj: any) => void;
  selectedId?: string | null;
}

interface TreeData {
  id: number;
  x: number;
  z: number;
  height: number;
  radius: number;
  isPine: boolean;
  rotation: number;
}

interface RockData {
  x: number;
  z: number;
  scale: [number, number, number];
  rotation: [number, number, number];
}

export function ForestTrees3D({
  foliageDensity,
  visible = true,
  onSelectObject,
  selectedId = null,
}: ForestTrees3DProps) {
  // 1. Deterministic tree locations avoiding buildings and ground station
  const allTrees: TreeData[] = useMemo(() => {
    const list: TreeData[] = [];
    let id = 0;

    // Grid sweep with jitter
    for (let ix = -5; ix <= 5; ix++) {
      for (let iz = -5; iz <= 5; iz++) {
        const x = ix * 11.5 + ((iz * 7) % 5) * 0.8;
        const z = iz * 11.5 + ((ix * 9) % 5) * 0.8;

        // Skip ground station central zone (radius < 9m)
        if (Math.hypot(x, z) < 9.0) continue;

        // Skip Building Alpha zone (x: -38 to -18, z: -35 to -15) + 3m margin
        if (x >= -41 && x <= -15 && z >= -38 && z <= -12) continue;

        // Skip Building Beta zone (x: 18 to 38, z: -32 to -12) + 3m margin
        if (x >= 15 && x <= 41 && z >= -35 && z <= -9) continue;

        // Bounds of arena
        if (Math.abs(x) > 54 || Math.abs(z) > 54) continue;

        const isPine = (ix + iz) % 2 === 0;
        const height = 5.5 + ((id * 3) % 5) * 1.2; // 5.5m to 10.3m
        const radius = 1.4 + ((id * 7) % 4) * 0.3; // 1.4m to 2.3m

        list.push({
          id: id++,
          x,
          z,
          height,
          radius,
          isPine,
          rotation: (id * 1.37) % (Math.PI * 2),
        });
      }
    }
    return list;
  }, []);

  // Filter visible trees according to foliage density
  const visibleTrees = useMemo(() => {
    if (!visible || foliageDensity <= 0.02) return [];
    const count = Math.round(allTrees.length * Math.min(1.0, foliageDensity));
    return allTrees.slice(0, count);
  }, [allTrees, foliageDensity, visible]);

  // Terrain Rocks
  const rocks: RockData[] = useMemo(() => [
    { x: -14, z: 12, scale: [1.8, 0.9, 1.4], rotation: [0.2, 0.5, 0.1] },
    { x: 18, z: 15, scale: [2.2, 1.1, 1.8], rotation: [0.1, 1.2, 0.3] },
    { x: -32, z: 18, scale: [1.6, 0.8, 1.5], rotation: [0.4, 0.7, 0.2] },
    { x: 26, z: -42, scale: [2.5, 1.3, 2.0], rotation: [0.3, 0.2, 0.5] },
    { x: -44, z: -2, scale: [2.1, 1.0, 1.7], rotation: [0.2, 0.9, 0.1] },
    { x: 5, z: 36, scale: [1.9, 0.9, 1.5], rotation: [0.5, 1.1, 0.3] },
    { x: 38, z: 12, scale: [2.4, 1.2, 1.9], rotation: [0.1, 0.4, 0.2] },
    { x: -22, z: 38, scale: [1.7, 0.8, 1.4], rotation: [0.3, 0.8, 0.4] },
  ], []);

  // Shared Materials
  const trunkMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#4A3324",
        roughness: 0.9,
        metalness: 0.05,
      }),
    []
  );

  const pineCanopyMat1 = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#1E4B27", roughness: 0.82 }),
    []
  );
  const pineCanopyMat2 = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#2B5E33", roughness: 0.85 }),
    []
  );
  const pineCanopyMat3 = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#3B7545", roughness: 0.88 }),
    []
  );

  const oakCanopyMat = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#3B6E33", roughness: 0.84 }),
    []
  );

  const rockMat = useMemo(
    () => new THREE.MeshStandardMaterial({ color: "#545C66", roughness: 0.88, metalness: 0.1 }),
    []
  );

  const puddleMat = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        color: "#4A7080",
        roughness: 0.15,
        metalness: 0.1,
        transparent: true,
        opacity: 0.65,
      }),
    []
  );

  if (!visible || visibleTrees.length === 0) {
    return null;
  }

  return (
    <group name="ForestEnvironment">
      {/* 1. Dynamic Trees */}
      {visibleTrees.map((tree) => {
        const trunkH = tree.height * 0.4;
        const trunkR = tree.radius * 0.16;
        const isSelected = selectedId === `tree_${tree.id}`;

        const handleTreeClick = (e: any) => {
          e.stopPropagation();
          onSelectObject?.({
            id: `tree_${tree.id}`,
            name: `${tree.isPine ? "Evergreen Pine" : "Deciduous Oak"} #${tree.id + 1}`,
            type: "tree",
            position: [tree.x, tree.height * 0.5, tree.z],
            materialName: "Wood Core & Layered Dielectric Foliage",
            epsilon_r: tree.isPine ? 12.5 : 14.2,
            conductivity_s_m: 0.018,
            tan_delta_e: 0.045,
            fresnel_refl_pct: 28.5,
            impedance_ohm: 106.6,
            skin_depth_m: 0.54,
          });
        };

        return (
          <group
            key={tree.id}
            position={[tree.x, 0, tree.z]}
            rotation={[0, tree.rotation, 0]}
            onClick={handleTreeClick}
            onPointerOver={(e) => {
              e.stopPropagation();
              document.body.style.cursor = "pointer";
            }}
            onPointerOut={() => {
              document.body.style.cursor = "default";
            }}
          >
            {/* Selection Base Reticle if selected */}
            {isSelected && (
              <mesh position={[0, 0.05, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                <ringGeometry args={[tree.radius * 0.9, tree.radius * 1.15, 32]} />
                <meshBasicMaterial color="#FFB300" side={THREE.DoubleSide} />
              </mesh>
            )}

            {/* Wooden Trunk */}
            <mesh position={[0, trunkH / 2, 0]} material={trunkMat} castShadow receiveShadow>
              <cylinderGeometry args={[trunkR * 0.8, trunkR * 1.2, trunkH, 7]} />
            </mesh>

            {/* Tree Foliage Canopy */}
            {tree.isPine ? (
              // Evergreen Conifer (3 layered needle cones)
              <group position={[0, trunkH * 0.8, 0]}>
                <mesh position={[0, 0, 0]} material={pineCanopyMat1} castShadow receiveShadow>
                  <coneGeometry args={[tree.radius * 1.1, tree.height * 0.32, 8]} />
                </mesh>
                <mesh
                  position={[0, tree.height * 0.18, 0]}
                  material={pineCanopyMat2}
                  castShadow
                  receiveShadow
                >
                  <coneGeometry args={[tree.radius * 0.85, tree.height * 0.28, 8]} />
                </mesh>
                <mesh
                  position={[0, tree.height * 0.34, 0]}
                  material={pineCanopyMat3}
                  castShadow
                  receiveShadow
                >
                  <coneGeometry args={[tree.radius * 0.6, tree.height * 0.24, 7]} />
                </mesh>
              </group>
            ) : (
              // Deciduous Broadleaf (Lush clustered spherical canopy)
              <group position={[0, trunkH + tree.height * 0.22, 0]}>
                <mesh position={[0, 0, 0]} material={oakCanopyMat} castShadow receiveShadow>
                  <dodecahedronGeometry args={[tree.radius * 0.95, 1]} />
                </mesh>
                <mesh
                  position={[tree.radius * 0.3, tree.height * 0.12, tree.radius * 0.2]}
                  material={oakCanopyMat}
                  castShadow
                  receiveShadow
                >
                  <dodecahedronGeometry args={[tree.radius * 0.72, 1]} />
                </mesh>
                <mesh
                  position={[-tree.radius * 0.25, tree.height * 0.1, -tree.radius * 0.25]}
                  material={oakCanopyMat}
                  castShadow
                  receiveShadow
                >
                  <dodecahedronGeometry args={[tree.radius * 0.68, 1]} />
                </mesh>
              </group>
            )}
          </group>
        );
      })}

      {/* 2. Terrain Granite Boulders / Rocks */}
      {rocks.map((rock, idx) => {
        const isRockSelected = selectedId === `rock_${idx}`;
        return (
          <group
            key={idx}
            position={[rock.x, rock.scale[1] * 0.45, rock.z]}
            rotation={rock.rotation as any}
            scale={rock.scale as any}
            onClick={(e) => {
              e.stopPropagation();
              onSelectObject?.({
                id: `rock_${idx}`,
                name: `Granite Boulder #${idx + 1}`,
                type: "rock",
                position: [rock.x, rock.scale[1] * 0.45, rock.z],
                materialName: "Dense Granite Rock",
                epsilon_r: 7.0,
                conductivity_s_m: 0.008,
                tan_delta_e: 0.035,
                fresnel_refl_pct: 32.4,
                impedance_ohm: 142.5,
                skin_depth_m: 0.68,
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
            <mesh material={rockMat} castShadow receiveShadow>
              <dodecahedronGeometry args={[1.0, 0]} />
            </mesh>
            {isRockSelected && (
              <lineSegments>
                <edgesGeometry args={[new THREE.DodecahedronGeometry(1.08, 0)]} />
                <lineBasicMaterial color="#FFB300" linewidth={3} />
              </lineSegments>
            )}
          </group>
        );
      })}

      {/* 3. Forest Ground Water Patches / Puddles */}
      {[
        [-18, 14, 3.2],
        [22, -18, 2.6],
        [-34, -22, 2.9],
        [32, 24, 3.5],
      ].map(([px, pz, pr], idx) => (
        <mesh
          key={idx}
          position={[px, 0.02, pz]}
          rotation={[-Math.PI / 2, 0, 0]}
          material={puddleMat}
        >
          <circleGeometry args={[pr, 24]} />
        </mesh>
      ))}
    </group>
  );
}

