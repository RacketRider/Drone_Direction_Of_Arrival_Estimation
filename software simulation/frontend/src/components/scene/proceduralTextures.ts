"use client";

import * as THREE from "three";

/**
 * Generates an architectural building facade texture with concrete spandrels,
 * metallic mullions, and reflective tinted office window grids.
 */
export function createBuildingFacadeTexture(): THREE.CanvasTexture {
  if (typeof document === "undefined") {
    // SSR fallback dummy
    return new THREE.CanvasTexture({} as any);
  }

  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");
  if (!ctx) return new THREE.CanvasTexture(canvas);

  // 1. Concrete Panel Background
  ctx.fillStyle = "#2A3644";
  ctx.fillRect(0, 0, 512, 512);

  // Concrete subtle texture noise
  for (let i = 0; i < 2000; i++) {
    const nx = Math.random() * 512;
    const ny = Math.random() * 512;
    const alpha = Math.random() * 0.08;
    ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.fillRect(nx, ny, 2, 2);
  }

  // 2. Horizontal Floor Spandrel Bands (6 floors)
  const numFloors = 6;
  const floorH = 512 / numFloors;
  const numWindows = 8;
  const winW = (512 / numWindows) * 0.72;
  const gapX = (512 / numWindows) * 0.28;

  for (let f = 0; f < numFloors; f++) {
    const y0 = f * floorH;

    // Dark architectural floor divide line
    ctx.strokeStyle = "#16202C";
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(0, y0);
    ctx.lineTo(512, y0);
    ctx.stroke();

    // Spandrel beam panel
    ctx.fillStyle = "#1E2938";
    ctx.fillRect(0, y0, 512, 10);

    // Windows for this floor
    for (let w = 0; w < numWindows; w++) {
      const wx = w * (winW + gapX) + gapX / 2;
      const wy = y0 + 14;
      const wh = floorH - 22;

      // Window Frame (Mullion)
      ctx.fillStyle = "#0F172A";
      ctx.fillRect(wx - 2, wy - 2, winW + 4, wh + 4);

      // Glass Tint: Gradient from deep cyan-blue to reflective sky-blue
      const grad = ctx.createLinearGradient(wx, wy, wx + winW, wy + wh);
      const isNightLight = (f + w) % 5 === 0;
      if (isNightLight) {
        // Subtle warm interior room light
        grad.addColorStop(0, "#1E3A5F");
        grad.addColorStop(0.5, "#254B77");
        grad.addColorStop(1, "#38BDF8");
      } else {
        grad.addColorStop(0, "#0E243A");
        grad.addColorStop(0.6, "#1A3D5E");
        grad.addColorStop(1, "#2C5282");
      }
      ctx.fillStyle = grad;
      ctx.fillRect(wx, wy, winW, wh);

      // Glass specular reflection slash
      ctx.fillStyle = "rgba(255, 255, 255, 0.12)";
      ctx.beginPath();
      ctx.moveTo(wx, wy + wh * 0.4);
      ctx.lineTo(wx + winW * 0.6, wy);
      ctx.lineTo(wx + winW * 0.85, wy);
      ctx.lineTo(wx + winW * 0.25, wy + wh * 0.4);
      ctx.fill();

      // Window cross divider
      ctx.strokeStyle = "rgba(15, 23, 42, 0.85)";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(wx + winW / 2, wy);
      ctx.lineTo(wx + winW / 2, wy + wh);
      ctx.moveTo(wx, wy + wh * 0.65);
      ctx.lineTo(wx + winW, wy + wh * 0.65);
      ctx.stroke();
    }
  }

  // Ground Floor Lobby Glass Wall
  ctx.fillStyle = "#162232";
  ctx.fillRect(0, 512 - floorH, 512, floorH);
  for (let w = 0; w < 4; w++) {
    const lx = w * 128 + 12;
    const ly = 512 - floorH + 8;
    const lw = 104;
    const lh = floorH - 12;
    ctx.fillStyle = "#1E3247";
    ctx.fillRect(lx, ly, lw, lh);
    ctx.strokeStyle = "#38BDF8";
    ctx.lineWidth = 1;
    ctx.strokeRect(lx, ly, lw, lh);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.generateMipmaps = true;
  return texture;
}

/**
 * Generates an architectural rooftop gravel / concrete slab texture.
 */
export function createConcreteRoofTexture(): THREE.CanvasTexture {
  if (typeof document === "undefined") {
    return new THREE.CanvasTexture({} as any);
  }

  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  if (!ctx) return new THREE.CanvasTexture(canvas);

  // Roof concrete base
  ctx.fillStyle = "#334155";
  ctx.fillRect(0, 0, 256, 256);

  // Gravel flecks
  for (let i = 0; i < 1500; i++) {
    const x = Math.random() * 256;
    const y = Math.random() * 256;
    const col = Math.random() > 0.5 ? "rgba(200, 215, 230, 0.15)" : "rgba(15, 23, 42, 0.25)";
    ctx.fillStyle = col;
    ctx.fillRect(x, y, 2, 2);
  }

  // Roof expansion joint grid
  ctx.strokeStyle = "#1E293B";
  ctx.lineWidth = 2;
  ctx.strokeRect(4, 4, 248, 248);
  ctx.strokeRect(64, 64, 128, 128);

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  return texture;
}

/**
 * Generates ground terrain texture: tactical forest moss/earth, dark graphite loam, or military tarmac.
 */
export function createTerrainTexture(type: "grass" | "soil" | "pavement"): THREE.CanvasTexture {
  if (typeof document === "undefined") {
    return new THREE.CanvasTexture({} as any);
  }

  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");
  if (!ctx) return new THREE.CanvasTexture(canvas);

  if (type === "grass") {
    // Dark Tactical Forest Floor
    ctx.fillStyle = "#0D1F13";
    ctx.fillRect(0, 0, 512, 512);

    // Deep evergreen moss patches
    for (let p = 0; p < 35; p++) {
      const cx = Math.random() * 512;
      const cy = Math.random() * 512;
      const cr = 20 + Math.random() * 70;
      const grad = ctx.createRadialGradient(cx, cy, 2, cx, cy, cr);
      grad.addColorStop(0, "rgba(20, 48, 28, 0.7)");
      grad.addColorStop(1, "rgba(13, 31, 19, 0)");
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.arc(cx, cy, cr, 0, Math.PI * 2);
      ctx.fill();
    }

    // Pine needle / grass flecks
    for (let i = 0; i < 4000; i++) {
      const x = Math.random() * 512;
      const y = Math.random() * 512;
      const green = 35 + Math.floor(Math.random() * 40);
      ctx.fillStyle = `rgba(20, ${green}, 25, 0.4)`;
      ctx.fillRect(x, y, 1, 2);
    }
  } else if (type === "soil") {
    // Dark Graphite Earth / Loam
    ctx.fillStyle = "#111822";
    ctx.fillRect(0, 0, 512, 512);
    for (let i = 0; i < 3000; i++) {
      const x = Math.random() * 512;
      const y = Math.random() * 512;
      ctx.fillStyle = Math.random() > 0.5 ? "rgba(35, 48, 65, 0.3)" : "rgba(10, 15, 22, 0.4)";
      ctx.fillRect(x, y, 2, 2);
    }
  } else {
    // Polished Military Tarmac / Dark Apron
    ctx.fillStyle = "#0B121D";
    ctx.fillRect(0, 0, 512, 512);

    // Subtle dark tarmac speckle
    for (let i = 0; i < 3000; i++) {
      const x = Math.random() * 512;
      const y = Math.random() * 512;
      ctx.fillStyle = Math.random() > 0.5 ? "rgba(0, 229, 255, 0.03)" : "rgba(30, 43, 66, 0.3)";
      ctx.fillRect(x, y, 1, 1);
    }
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(8, 8);
  return texture;
}

