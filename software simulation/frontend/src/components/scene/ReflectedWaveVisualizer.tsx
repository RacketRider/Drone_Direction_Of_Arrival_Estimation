"use client";

import React, { useRef, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import { Line } from "@react-three/drei";
import * as THREE from "three";

export interface SelectedObjectInfo {
  id: string;
  name: string;
  type: "building" | "tree" | "rock" | "ground";
  position: [number, number, number];
  size?: [number, number, number];
  materialName: string;
  epsilon_r: number;
  conductivity_s_m: number;
  tan_delta_e: number;
  fresnel_refl_pct: number;
  impedance_ohm: number;
  skin_depth_m: number;
}

interface ReflectedWaveVisualizerProps {
  selectedObject: SelectedObjectInfo | null;
  uavPos: [number, number, number];
  arrayPos?: [number, number, number];
}

export function ReflectedWaveVisualizer({
  selectedObject,
  uavPos,
  arrayPos = [0, 2.0, 0],
}: ReflectedWaveVisualizerProps) {
  const waveRing1Ref = useRef<THREE.Mesh>(null);
  const waveRing2Ref = useRef<THREE.Mesh>(null);
  const waveRing3Ref = useRef<THREE.Mesh>(null);
  const packet1Ref = useRef<THREE.Mesh>(null);
  const packet2Ref = useRef<THREE.Mesh>(null);
  const packet3Ref = useRef<THREE.Mesh>(null);

  // Compute multi-ray probe physics: incident, specular, refracted, normal, exiting, and diffuse scatter
  const probePhysics = useMemo(() => {
    if (!selectedObject) return null;
    const [ox, oy, oz] = selectedObject.position;
    const [ux, uy, uz] = uavPos;
    const [ax, ay, az] = arrayPos;

    let reflX = ox;
    let reflY = Math.max(1.0, oy);
    let reflZ = oz;
    let normX = 0;
    let normY = 0;
    let normZ = 1;
    let objectRadius = 1.0;

    if (selectedObject.type === "building" && selectedObject.size) {
      const halfX = selectedObject.size[0] / 2;
      const halfY = selectedObject.size[1] / 2;
      const halfZ = selectedObject.size[2] / 2;
      objectRadius = Math.max(halfX, halfZ);

      // 4 vertical walls of the building box
      const faces = [
        // East face: x = ox + halfX, normal [1, 0, 0]
        { nx: 1.0, nz: 0.0, px: ox + halfX, pz: oz, isX: true, sMin: oz - halfZ, sMax: oz + halfZ },
        // West face: x = ox - halfX, normal [-1, 0, 0]
        { nx: -1.0, nz: 0.0, px: ox - halfX, pz: oz, isX: true, sMin: oz - halfZ, sMax: oz + halfZ },
        // South face: z = oz + halfZ, normal [0, 0, 1]
        { nx: 0.0, nz: 1.0, px: ox, pz: oz + halfZ, isX: false, sMin: ox - halfX, sMax: ox + halfX },
        // North face: z = oz - halfZ, normal [0, 0, -1]
        { nx: 0.0, nz: -1.0, px: ox, pz: oz - halfZ, isX: false, sMin: ox - halfX, sMax: ox + halfX },
      ];

      let bestPt: [number, number, number] | null = null;
      let bestNorm: [number, number, number] = [0, 0, 1];
      let minDeviation = Infinity;

      for (const f of faces) {
        const dT = f.nx * (ux - f.px) + f.nz * (uz - f.pz);
        const dR = f.nx * (ax - f.px) + f.nz * (az - f.pz);

        if (dT > 1e-4 && dR > 1e-4) {
          const s = dT / (dT + dR);
          const Ti_x = ux - 2.0 * dT * f.nx;
          const Ti_z = uz - 2.0 * dT * f.nz;
          const Ti_y = uy;

          const rx = Ti_x + s * (ax - Ti_x);
          const rz = Ti_z + s * (az - Ti_z);
          const ry = Ti_y + s * (ay - Ti_y);

          const spanCoord = f.isX ? rz : rx;
          const isInsideSpan = spanCoord >= f.sMin && spanCoord <= f.sMax;
          const isInsideH = ry >= 0 && ry <= selectedObject.size[1];

          if (isInsideSpan && isInsideH) {
            bestPt = [rx, ry, rz];
            bestNorm = [f.nx, 0, f.nz];
            break;
          }

          const clampedSpan = Math.max(f.sMin, Math.min(f.sMax, spanCoord));
          const clampedH = Math.max(0.5, Math.min(selectedObject.size[1] - 0.5, ry));
          const dev = Math.hypot(spanCoord - clampedSpan, ry - clampedH);
          if (dev < minDeviation) {
            minDeviation = dev;
            bestPt = f.isX ? [f.px, clampedH, clampedSpan] : [clampedSpan, clampedH, f.pz];
            bestNorm = [f.nx, 0, f.nz];
          }
        }
      }

      if (bestPt) {
        reflX = bestPt[0];
        reflY = bestPt[1];
        reflZ = bestPt[2];
        normX = bestNorm[0];
        normY = bestNorm[1];
        normZ = bestNorm[2];
      }
    } else if (selectedObject.type === "tree" || selectedObject.type === "rock") {
      // Convex cylinder/sphere scatterer: surface normal is bisector between incident and reflection
      const dxT = ux - ox;
      const dzT = uz - oz;
      const lenT = Math.hypot(dxT, dzT) || 1.0;
      const uTx = dxT / lenT;
      const uTz = dzT / lenT;

      const dxR = ax - ox;
      const dzR = az - oz;
      const lenR = Math.hypot(dxR, dzR) || 1.0;
      const uRx = dxR / lenR;
      const uRz = dzR / lenR;

      const bX = uTx + uRx;
      const bZ = uTz + uRz;
      const lenB = Math.hypot(bX, bZ) || 1.0;
      normX = bX / lenB;
      normZ = bZ / lenB;
      normY = 0;

      objectRadius = selectedObject.type === "tree" ? 0.8 : (selectedObject.size ? selectedObject.size[0] / 2 : 1.4);
      reflX = ox + objectRadius * normX;
      reflZ = oz + objectRadius * normZ;
      const sH = lenR / (lenR + lenT);
      reflY = Math.max(0.8, Math.min(oy + (selectedObject.size?.[1] || 3.0), ay + sH * (uy - ay)));
    }

    const P: [number, number, number] = [reflX, reflY, reflZ];
    const N: [number, number, number] = [normX, normY, normZ];

    // 1. Incident direction vector (UAV -> P)
    const incVec = new THREE.Vector3(reflX - ux, reflY - uy, reflZ - uz).normalize();
    const normVec = new THREE.Vector3(normX, normY, normZ).normalize();

    // Angle of incidence theta_i
    const cosThetaI = Math.min(1.0, Math.max(0.01, -incVec.dot(normVec)));
    const sinThetaI = Math.sqrt(Math.max(0, 1.0 - cosThetaI * cosThetaI));

    // 2. Snell's Law Refraction inside material: n = sqrt(eps_r)
    const nMat = Math.sqrt(Math.max(1.1, selectedObject.epsilon_r || 4.0));
    const sinThetaT = Math.min(0.99, sinThetaI / nMat);
    const cosThetaT = Math.sqrt(Math.max(0.01, 1.0 - sinThetaT * sinThetaT));

    // Refracted direction unit vector inside
    const refractVec = incVec.clone().multiplyScalar(1.0 / nMat)
      .add(normVec.clone().multiplyScalar(cosThetaI / nMat - cosThetaT))
      .normalize();

    // In-material penetration depth
    const penLen = Math.min(objectRadius * 1.8, 3.5);
    const P_inside: [number, number, number] = [
      reflX + refractVec.x * penLen,
      reflY + refractVec.y * penLen,
      reflZ + refractVec.z * penLen,
    ];

    // 3. Exiting / Transmitted wave emerging from rear
    const exitLen = 6.0;
    const P_exit: [number, number, number] = [
      P_inside[0] + incVec.x * exitLen,
      P_inside[1] + incVec.y * exitLen,
      P_inside[2] + incVec.z * exitLen,
    ];

    // 4. Surface normal display segment
    const normalEnd: [number, number, number] = [
      reflX + normX * 1.8,
      reflY + normY * 1.8,
      reflZ + normZ * 1.8,
    ];

    // 5. Specular reflection direction from P towards free space / receiver
    const reflDir = incVec.clone().reflect(normVec).negate().normalize();
    const specularBounceEnd: [number, number, number] = [
      reflX + reflDir.x * 12.0,
      reflY + reflDir.y * 12.0,
      reflZ + reflDir.z * 12.0,
    ];

    // 6. Multi-ray diffuse scattering fan (4 raylets)
    const tangent1 = new THREE.Vector3(-normZ, 0, normX).normalize();
    const tangent2 = new THREE.Vector3(0, 1, 0);
    const scatterRays: [number, number, number][][] = [
      [-0.45, 0.25],
      [0.45, 0.25],
      [-0.3, -0.35],
      [0.3, -0.35],
    ].map(([u, v]) => {
      const sDir = normVec.clone().multiplyScalar(0.7)
        .add(tangent1.clone().multiplyScalar(u))
        .add(tangent2.clone().multiplyScalar(v))
        .normalize()
        .multiplyScalar(4.5);
      return [P, [reflX + sDir.x, reflY + sDir.y, reflZ + sDir.z]];
    });

    // 7. Auxiliary probe bundle incident rays (offset across beam footprint)
    const probeBundleRays: [number, number, number][][] = [
      [-0.5, 0.3],
      [0.5, -0.3],
    ].map(([du, dv]) => {
      const pOff: [number, number, number] = [
        reflX + tangent1.x * du + normX * 0.15,
        reflY + dv,
        reflZ + tangent1.z * du + normZ * 0.15,
      ];
      return [uavPos, pOff];
    });

    return {
      P,
      N,
      P_inside,
      P_exit,
      normalEnd,
      specularBounceEnd,
      scatterRays,
      probeBundleRays,
      thetaI_deg: Math.acos(cosThetaI) * (180.0 / Math.PI),
      thetaT_deg: Math.asin(sinThetaT) * (180.0 / Math.PI),
    };
  }, [selectedObject, uavPos, arrayPos]);

  // Animate expanding wave rings and traveling energy packets
  useFrame((state) => {
    if (!probePhysics) return;
    const t = state.clock.getElapsedTime();

    // 1. Concentric expanding wavefront rings
    if (waveRing1Ref.current) {
      const r1 = (t * 5.0) % 8.0;
      waveRing1Ref.current.scale.set(r1, r1, r1);
      (waveRing1Ref.current.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 0.75 - (r1 / 8.0) * 0.75);
    }
    if (waveRing2Ref.current) {
      const r2 = (t * 5.0 + 2.6) % 8.0;
      waveRing2Ref.current.scale.set(r2, r2, r2);
      (waveRing2Ref.current.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 0.75 - (r2 / 8.0) * 0.75);
    }
    if (waveRing3Ref.current) {
      const r3 = (t * 5.0 + 5.2) % 8.0;
      waveRing3Ref.current.scale.set(r3, r3, r3);
      (waveRing3Ref.current.material as THREE.MeshBasicMaterial).opacity = Math.max(0, 0.75 - (r3 / 8.0) * 0.75);
    }

    // 2. Traveling energy packets:
    // Packet 1: UAV -> Surface
    const prog1 = (t * 1.5) % 1.0;
    if (packet1Ref.current) {
      packet1Ref.current.position.set(
        uavPos[0] + prog1 * (probePhysics.P[0] - uavPos[0]),
        uavPos[1] + prog1 * (probePhysics.P[1] - uavPos[1]),
        uavPos[2] + prog1 * (probePhysics.P[2] - uavPos[2])
      );
    }

    // Packet 2: Surface -> Array
    const prog2 = (t * 1.5 + 0.5) % 1.0;
    if (packet2Ref.current) {
      packet2Ref.current.position.set(
        probePhysics.P[0] + prog2 * (arrayPos[0] - probePhysics.P[0]),
        probePhysics.P[1] + prog2 * (arrayPos[1] - probePhysics.P[1]),
        probePhysics.P[2] + prog2 * (arrayPos[2] - probePhysics.P[2])
      );
    }

    // Packet 3: Penetrating Refracted pulse inside material
    const prog3 = (t * 2.0) % 1.0;
    if (packet3Ref.current) {
      packet3Ref.current.position.set(
        probePhysics.P[0] + prog3 * (probePhysics.P_inside[0] - probePhysics.P[0]),
        probePhysics.P[1] + prog3 * (probePhysics.P_inside[1] - probePhysics.P[1]),
        probePhysics.P[2] + prog3 * (probePhysics.P_inside[2] - probePhysics.P[2])
      );
    }
  });

  if (!selectedObject || !probePhysics) return null;

  return (
    <group name="ReflectedWaveVisualizer">
      {/* 1. Primary Incident Ray (UAV -> Object Surface) [Gold] */}
      <Line points={[uavPos, probePhysics.P]} color="#F59E0B" lineWidth={2.5} />

      {/* 1b. Surrounding Auxiliary Incident Probe Bundle Rays [Subtle Gold] */}
      {probePhysics.probeBundleRays.map((pts, i) => (
        <Line
          key={`bundle-${i}`}
          points={pts}
          color="#F59E0B"
          lineWidth={1.2}
          transparent
          opacity={0.45}
          dashed
          dashSize={0.8}
          gapSize={0.4}
        />
      ))}

      {/* 2. Specular Reflected Ray (Object Surface -> UCA Array) [Orange] */}
      <Line points={[probePhysics.P, arrayPos]} color="#FF9F43" lineWidth={2.8} />

      {/* 2b. Specular Free-Space Bounce Ray [Orange dashed] */}
      <Line
        points={[probePhysics.P, probePhysics.specularBounceEnd]}
        color="#FF9F43"
        lineWidth={1.5}
        dashed
        dashSize={1.0}
        gapSize={0.5}
        transparent
        opacity={0.5}
      />

      {/* 3. Surface Normal Vector Arrow at Reflection Point [White/Slate] */}
      <Line points={[probePhysics.P, probePhysics.normalEnd]} color="#E2E8F0" lineWidth={2.0} />

      {/* 4. Refracted Ray Bending Inside Material (Snell's Law) [Emerald Green] */}
      <Line points={[probePhysics.P, probePhysics.P_inside]} color="#10B981" lineWidth={3.0} />

      {/* 5. Transmitted Wave Exiting Rear of Object [Sky Blue] */}
      <Line
        points={[probePhysics.P_inside, probePhysics.P_exit]}
        color="#38BDF8"
        lineWidth={1.6}
        dashed
        dashSize={0.8}
        gapSize={0.4}
        transparent
        opacity={0.65}
      />

      {/* 6. Diffuse Scattering Raylet Fan [Subtle Amber/Gray] */}
      {probePhysics.scatterRays.map((pts, i) => (
        <Line
          key={`scatter-${i}`}
          points={pts}
          color="#94A3B8"
          lineWidth={1.2}
          transparent
          opacity={0.55}
          dashed
          dashSize={0.6}
          gapSize={0.3}
        />
      ))}

      {/* 7. Traveling RF Energy Packets (Photons along rays) */}
      <mesh ref={packet1Ref}>
        <sphereGeometry args={[0.26, 12, 12]} />
        <meshBasicMaterial color="#00E5FF" />
      </mesh>
      <mesh ref={packet2Ref}>
        <sphereGeometry args={[0.26, 12, 12]} />
        <meshBasicMaterial color="#FFB300" />
      </mesh>
      <mesh ref={packet3Ref}>
        <sphereGeometry args={[0.18, 10, 10]} />
        <meshBasicMaterial color="#10B981" />
      </mesh>

      {/* 8. Reflection Point Contact Reticle & Concentric Wave Ripples */}
      <group position={probePhysics.P}>
        {/* Glowing Reflection Center Node */}
        <mesh>
          <sphereGeometry args={[0.38, 16, 16]} />
          <meshBasicMaterial color="#FFB300" />
        </mesh>
        <pointLight color="#FFB300" intensity={2.5} distance={12} />

        {/* Outer Highlight Reticle Ring */}
        <mesh rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.8, 0.98, 32]} />
          <meshBasicMaterial color="#FF9F43" side={THREE.DoubleSide} />
        </mesh>

        {/* 3 Concentric Expanding Wave Rings */}
        <mesh ref={waveRing1Ref} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.85, 0.98, 48]} />
          <meshBasicMaterial color="#FF9F43" transparent opacity={0.6} side={THREE.DoubleSide} />
        </mesh>
        <mesh ref={waveRing2Ref} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.85, 0.98, 48]} />
          <meshBasicMaterial color="#FFB300" transparent opacity={0.6} side={THREE.DoubleSide} />
        </mesh>
        <mesh ref={waveRing3Ref} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.85, 0.98, 48]} />
          <meshBasicMaterial color="#FFA726" transparent opacity={0.6} side={THREE.DoubleSide} />
        </mesh>
      </group>
    </group>
  );
}
