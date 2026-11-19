/* =====================================================================================================
 * rf_physics.js  -  RF propagation + DoA estimation engine for the Drone DoA 3D simulation
 * -----------------------------------------------------------------------------------------------------
 * Pure JavaScript, no dependencies. Loaded by index.html as a classic script (window.RF) and by
 * Node for the unit tests (module.exports).
 *
 * Coordinate system : metres, Y is up, ground plane is y = 0.
 * Azimuth convention: degrees, measured counter-clockwise from +X when the scene is viewed from above
 *                     (so az = atan2(-dz, dx)).  Elevation positive upward.
 * Time convention   : e^{+j w t}; a travelling wave is e^{-j k r}.  Lossy media have
 *                     eps_c = eps' - j sigma/(w eps0) and refractive index n = n' - j n'' (n'' >= 0).
 *
 * Propagation mechanisms (all computed against the actual triangle meshes of the scene objects):
 *   direct            straight segment drone -> receiver, with exact segment/triangle intersection;
 *                     every crossed object adds Fresnel interface loss (entry + exit) and
 *                     in-material attenuation exp(-alpha L) and extra phase (beta - k0) L
 *   ground            image-method specular reflection on y = 0 (soil or puddle material, Fresnel,
 *                     Rayleigh roughness)
 *   specular          image-method reflection on every flat facet of rocks / tree trunks with a
 *                     finite-facet (physical-optics) size correction
 *   ground+facet      second-order image paths (ground -> facet and facet -> ground)
 *   diffraction       ITU-R P.526 single knife-edge around top / left / right of a blocking obstacle
 *   diffuse scatter   Lambertian effective-roughness model for rocks/trunks, isotropic volume
 *                     scattering for foliage canopies (incoherent power)
 * Polarisation is tracked as a complex 3-vector through every interaction (TE/TM decomposition).
 * ===================================================================================================*/
(function (global) {
  'use strict';

  // ------------------------------------------------------------------------------------------------
  // constants
  // ------------------------------------------------------------------------------------------------
  const C0 = 299792458;
  const EPS0 = 8.8541878128e-12;
  const MU0 = 1.25663706212e-6;
  const ETA0 = 376.730313668;
  const KB = 1.380649e-23;
  const D2R = Math.PI / 180, R2D = 180 / Math.PI;
  const NP2DB = 8.685889638;

  // ------------------------------------------------------------------------------------------------
  // complex numbers  {re, im}
  // ------------------------------------------------------------------------------------------------
  const C = (re, im = 0) => ({ re, im });
  const cadd = (a, b) => C(a.re + b.re, a.im + b.im);
  const csub = (a, b) => C(a.re - b.re, a.im - b.im);
  const cmul = (a, b) => C(a.re * b.re - a.im * b.im, a.re * b.im + a.im * b.re);
  const cdiv = (a, b) => { const d = b.re * b.re + b.im * b.im; return C((a.re * b.re + a.im * b.im) / d, (a.im * b.re - a.re * b.im) / d); };
  const cscale = (a, s) => C(a.re * s, a.im * s);
  const cabs = a => Math.hypot(a.re, a.im);
  const cabs2 = a => a.re * a.re + a.im * a.im;
  const carg = a => Math.atan2(a.im, a.re);
  const cexpj = ph => C(Math.cos(ph), Math.sin(ph));
  const cconj = a => C(a.re, -a.im);
  function csqrt(a) {
    const r = cabs(a);
    const re = Math.sqrt(Math.max(0, (r + a.re) / 2));
    let im = Math.sqrt(Math.max(0, (r - a.re) / 2));
    if (a.im < 0) im = -im;
    return C(re, im);
  }

  // ------------------------------------------------------------------------------------------------
  // real 3-vectors  [x, y, z]
  // ------------------------------------------------------------------------------------------------
  const vadd = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
  const vsub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const vscale = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
  const vdot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const vcross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const vlen = a => Math.hypot(a[0], a[1], a[2]);
  const vnorm = a => { const l = vlen(a) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
  const vdist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
  const vlerp = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
  function anyPerp(k) {
    const t = Math.abs(k[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
    return vnorm(vcross(k, t));
  }
  const mirrorGround = p => [p[0], -p[1], p[2]];

  // complex 3-vectors (polarisation)  [C, C, C]
  const cvFromReal = (u, c) => [cscale(c, u[0]), cscale(c, u[1]), cscale(c, u[2])];
  const cvAdd = (a, b) => [cadd(a[0], b[0]), cadd(a[1], b[1]), cadd(a[2], b[2])];
  const cvScaleC = (a, c) => [cmul(a[0], c), cmul(a[1], c), cmul(a[2], c)];
  const cvScale = (a, s) => [cscale(a[0], s), cscale(a[1], s), cscale(a[2], s)];
  const cvDotReal = (a, u) => C(a[0].re * u[0] + a[1].re * u[1] + a[2].re * u[2], a[0].im * u[0] + a[1].im * u[1] + a[2].im * u[2]);
  const cvPow = a => cabs2(a[0]) + cabs2(a[1]) + cabs2(a[2]);
  /** remove the component of a complex field along the real unit vector k (keeps the field transverse) */
  function cvTransverse(a, k) {
    const d = cvDotReal(a, k);
    return [csub(a[0], cscale(d, k[0])), csub(a[1], cscale(d, k[1])), csub(a[2], cscale(d, k[2]))];
  }

  // ------------------------------------------------------------------------------------------------
  // helpers
  // ------------------------------------------------------------------------------------------------
  const wrap360 = a => ((a % 360) + 360) % 360;
  const wrap180 = a => ((((a + 180) % 360) + 360) % 360) - 180;
  const db10 = x => 10 * Math.log10(Math.max(x, 1e-300));
  const undb = x => Math.pow(10, x / 10);
  const wToDbm = w => db10(w) + 30;
  const dbmToW = d => Math.pow(10, (d - 30) / 10);
  const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
  /** azimuth (deg, CCW from +X seen from above) of the direction vector d */
  const azOf = d => wrap360(Math.atan2(-d[2], d[0]) * R2D);
  const elOf = d => Math.asin(clamp(d[1] / (vlen(d) || 1), -1, 1)) * R2D;
  const dirFromAz = az => [Math.cos(az * D2R), 0, -Math.sin(az * D2R)];

  /** deterministic PRNG (mulberry32) */
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function randn(rng) {
    let u = 0, v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }
  /** Gamma(k, theta) sampler (Marsaglia & Tsang), k >= 1 */
  function gammaSample(k, theta, rng) {
    const d = k - 1 / 3, c = 1 / Math.sqrt(9 * d);
    for (;;) {
      let x, v;
      do { x = randn(rng); v = 1 + c * x; } while (v <= 0);
      v = v * v * v;
      const u = rng();
      if (u < 1 - 0.0331 * x * x * x * x) return d * v * theta;
      if (Math.log(u) < 0.5 * x * x + d * (1 - v + Math.log(v))) return d * v * theta;
    }
  }
  function hashPhase(a, b) {   // deterministic pseudo-random phase for diffuse components
    let h = 2166136261 >>> 0;
    const s = String(a) + '|' + String(b);
    for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return ((h >>> 0) / 4294967296) * 2 * Math.PI;
  }

  // ------------------------------------------------------------------------------------------------
  // materials (representative values near 2.4 GHz; sigma is an EFFECTIVE conductivity that also
  // absorbs the dielectric loss, and is held constant when the frequency is changed)
  // ------------------------------------------------------------------------------------------------
  const MATERIALS = {
    air:         { name: 'Air',                                   er: 1.0,  sigma: 0.0,    mur: 1.0,  moisture: 0,   cls: 'air' },
    foliage:     { name: 'Foliage canopy (leaves + twigs + air)', er: 1.25, sigma: 0.0012, mur: 1.0,  moisture: 55,  cls: 'vegetation' },
    foliage_wet: { name: 'Wet / dense foliage canopy',            er: 1.45, sigma: 0.0028, mur: 1.0,  moisture: 72,  cls: 'vegetation' },
    wood_live:   { name: 'Live green wood (trunk)',               er: 12.0, sigma: 0.08,   mur: 1.0,  moisture: 45,  cls: 'wood' },
    wood_dry:    { name: 'Dry / dead wood',                       er: 3.5,  sigma: 0.008,  mur: 1.0,  moisture: 12,  cls: 'wood' },
    granite:     { name: 'Granite boulder',                       er: 5.5,  sigma: 0.004,  mur: 1.0,  moisture: 1,   cls: 'rock' },
    limestone:   { name: 'Limestone boulder',                     er: 7.5,  sigma: 0.02,   mur: 1.0,  moisture: 4,   cls: 'rock' },
    basalt:      { name: 'Basalt (iron-rich, slightly magnetic)', er: 8.5,  sigma: 0.012,  mur: 1.03, moisture: 2,   cls: 'rock' },
    sandstone:   { name: 'Wet sandstone',                         er: 10.0, sigma: 0.05,   mur: 1.0,  moisture: 9,   cls: 'rock' },
    soil_dry:    { name: 'Dry soil / forest floor',               er: 3.8,  sigma: 0.004,  mur: 1.0,  moisture: 5,   cls: 'soil' },
    soil_moist:  { name: 'Moist loam soil',                       er: 12.0, sigma: 0.03,   mur: 1.0,  moisture: 18,  cls: 'soil' },
    soil_wet:    { name: 'Wet / saturated soil',                  er: 24.0, sigma: 0.15,   mur: 1.0,  moisture: 35,  cls: 'soil' },
    ground_rocky:{ name: 'Rocky / gravel ground',                 er: 6.5,  sigma: 0.01,   mur: 1.0,  moisture: 6,   cls: 'soil' },
    water:       { name: 'Fresh water (puddle)',                  er: 77.0, sigma: 1.3,    mur: 1.0,  moisture: 100, cls: 'water' },
    pec:         { name: 'Metal (near-perfect conductor)',        er: 1.0,  sigma: 1e7,    mur: 1.0,  moisture: 0,   cls: 'metal' },
  };
  for (const k in MATERIALS) MATERIALS[k].key = k;

  function makeMaterial(key, over) {
    const base = MATERIALS[key] || MATERIALS.air;
    return Object.assign({}, base, over || {}, { key: base.key, _cache: null });
  }

  /** all derived electromagnetic quantities of a material at frequency f (Hz) */
  function matProps(m, f) {
    if (m._cache && m._cache.f === f && m._cache.er === m.er && m._cache.sigma === m.sigma && m._cache.mur === m.mur) return m._cache.p;
    const w = 2 * Math.PI * f, k0 = w / C0;
    const epsC = C(m.er, -m.sigma / (w * EPS0));
    const n = csqrt(cscale(epsC, m.mur));
    const alpha = k0 * Math.abs(n.im), beta = k0 * n.re;
    const eta = cscale(csqrt(cdiv(C(m.mur, 0), epsC)), ETA0);
    const lossTan = m.sigma / (w * EPS0 * m.er);
    const p = {
      epsC, n, alpha, beta, eta, lossTan,
      dbPerM: NP2DB * alpha,
      skinDepth: alpha > 0 ? 1 / alpha : Infinity,
      lambdaIn: beta > 0 ? 2 * Math.PI / beta : Infinity,
      velocityFactor: 1 / Math.max(n.re, 1e-9),
      brewsterDeg: Math.atan(Math.sqrt(m.er)) * R2D,      // lossless approximation
      criticalDeg: n.re > 1 ? Math.asin(1 / n.re) * R2D : 90, // for a wave leaving the material
      normalReflDb: 0,
    };
    const g = cdiv(csub(eta, C(ETA0)), cadd(eta, C(ETA0)));
    p.normalGamma = cabs(g);
    p.normalReflDb = db10(cabs2(g));
    m._cache = { f, er: m.er, sigma: m.sigma, mur: m.mur, p };
    return p;
  }

  /**
   * Fresnel coefficients between medium 1 and medium 2 (each {n, eta} complex) for an incidence cosine.
   * Returns TE (s, perpendicular) and TM (p, parallel) reflection/transmission coefficients.
   * TM sign convention matches the polarisation basis used in reflectField (p_r = s x k_r), so that
   * at normal incidence gp == gs.
   */
  function fresnel(m1, m2, cosi) {
    cosi = clamp(cosi, 0, 1);
    const sini = Math.sqrt(Math.max(0, 1 - cosi * cosi));
    const sint = cscale(cdiv(m1.n, m2.n), sini);
    const cost = csqrt(csub(C(1), cmul(sint, sint)));
    const ci = C(cosi);
    const e1 = m1.eta, e2 = m2.eta;
    const a = cmul(e2, ci), b = cmul(e1, cost);
    const gs = cdiv(csub(a, b), cadd(a, b));
    const ts = cdiv(cscale(cmul(e2, ci), 2), cadd(a, b));
    const c2 = cmul(e2, cost), d1 = cmul(e1, ci);
    const gp = cdiv(csub(c2, d1), cadd(c2, d1));
    const tp = cdiv(cscale(cmul(e2, ci), 2), cadd(c2, d1));
    const sinReal = m1.n.re * sini / m2.n.re;
    return { gs, gp, ts, tp, cost, tir: sinReal > 1, thetaT: sinReal >= 1 ? 90 : Math.asin(sinReal) * R2D };
  }
  const AIR_MEDIUM = { n: C(1), eta: C(ETA0) };
  function medium(m, f) { const p = matProps(m, f); return { n: p.n, eta: p.eta }; }
  /** air -> material Fresnel at incidence angle (deg) */
  function fresnelAirTo(m, f, thetaDeg) { return fresnel(AIR_MEDIUM, medium(m, f), Math.cos(thetaDeg * D2R)); }

  /** basis vectors for an interface interaction. k: propagation dir (unit), n: surface normal (any side) */
  function interfaceBasis(k, n) {
    if (vdot(k, n) > 0) n = vscale(n, -1);           // n now points back toward the incident side
    const cosi = clamp(-vdot(k, n), 0, 1);
    let s = vcross(k, n);
    if (vlen(s) < 1e-9) s = anyPerp(k); else s = vnorm(s);
    const pi = vcross(k, s);
    return { n, cosi, s, pi };
  }

  /** specular reflection of a complex field E (propagating along k) off a surface with normal nrm */
  function reflectField(E, k, nrm, mat, f, roughness, lambda) {
    const B = interfaceBasis(k, nrm);
    const fr = fresnel(AIR_MEDIUM, medium(mat, f), B.cosi);
    const kr = vnorm(vadd(k, vscale(B.n, 2 * B.cosi)));
    const pr = vcross(B.s, kr);
    const Es = cvDotReal(E, B.s), Ep = cvDotReal(E, B.pi);
    let rho = 1;
    if (roughness > 0) { const g = Math.PI * roughness * B.cosi / lambda; rho = Math.exp(-8 * g * g); }
    let Er = cvAdd(cvFromReal(B.s, cmul(fr.gs, Es)), cvFromReal(pr, cmul(fr.gp, Ep)));
    if (rho !== 1) Er = cvScale(Er, rho);
    return { E: Er, kr, cosi: B.cosi, thetaDeg: Math.acos(B.cosi) * R2D, gs: fr.gs, gp: fr.gp, rho, fr };
  }

  /**
   * transmission of E through an interface while keeping the straight-line direction k
   * (straight-line penetration model). Power transmittance 1-|G|^2 per polarisation component,
   * phase of the Fresnel T coefficient. Uses the air->material coefficients at the local angle
   * (reciprocity: |G| is identical for both directions of crossing).
   */
  function transmitStraight(E, k, nrm, mat, f) {
    const B = interfaceBasis(k, nrm);
    const fr = fresnel(AIR_MEDIUM, medium(mat, f), B.cosi);
    const Es = cvDotReal(E, B.s), Ep = cvDotReal(E, B.pi);
    const tsMag = Math.sqrt(Math.max(0, 1 - cabs2(fr.gs))), tpMag = Math.sqrt(Math.max(0, 1 - cabs2(fr.gp)));
    const ts = cscale(cexpj(carg(fr.ts)), tsMag), tp = cscale(cexpj(carg(fr.tp)), tpMag);
    return { E: cvAdd(cvFromReal(B.s, cmul(ts, Es)), cvFromReal(B.pi, cmul(tp, Ep))), cosi: B.cosi, fr };
  }

  /** Snell refraction of a real direction (used by the visual probe rays). n1,n2 real parts */
  function refractDir(k, nrm, n1, n2) {
    let n = nrm;
    if (vdot(k, n) > 0) n = vscale(n, -1);
    const cosi = -vdot(k, n);
    const eta = n1 / n2;
    const k2 = 1 - eta * eta * (1 - cosi * cosi);
    if (k2 < 0) return null; // total internal reflection
    return vnorm(vadd(vscale(k, eta), vscale(n, eta * cosi - Math.sqrt(k2))));
  }
  function reflectDir(k, nrm) { const d = vdot(k, nrm); return vnorm(vsub(k, vscale(nrm, 2 * d))); }

  // ------------------------------------------------------------------------------------------------
  // scene objects (closed triangle meshes in world coordinates)
  // ------------------------------------------------------------------------------------------------
  /**
   * spec: { id, kind:'rock'|'trunk'|'foliage'|'building', name, mat, tris:Float64Array|number[] (9 per tri),
   *         specular?:bool, scatter?:bool, roughness?:m }
   */
  function makeObject(spec) {
    // drop degenerate (zero-area) triangles, e.g. the collapsed apex ring of a cone
    const raw = spec.tris, keep = [];
    for (let o = 0; o + 8 < raw.length; o += 9) {
      const ux = raw[o + 3] - raw[o], uy = raw[o + 4] - raw[o + 1], uz = raw[o + 5] - raw[o + 2];
      const wx = raw[o + 6] - raw[o], wy = raw[o + 7] - raw[o + 1], wz = raw[o + 8] - raw[o + 2];
      const cx = uy * wz - uz * wy, cy = uz * wx - ux * wz, cz = ux * wy - uy * wx;
      if (cx * cx + cy * cy + cz * cz > 1e-16) for (let k = 0; k < 9; k++) keep.push(raw[o + k]);
    }
    const tris = Float64Array.from(keep);
    const nt = tris.length / 9;
    const nrm = new Float64Array(nt * 3), area = new Float64Array(nt);
    let mn = [Infinity, Infinity, Infinity], mx = [-Infinity, -Infinity, -Infinity];
    const verts = new Map();
    for (let i = 0; i < nt; i++) {
      const o = i * 9;
      const a = [tris[o], tris[o + 1], tris[o + 2]], b = [tris[o + 3], tris[o + 4], tris[o + 5]], c = [tris[o + 6], tris[o + 7], tris[o + 8]];
      const cr = vcross(vsub(b, a), vsub(c, a));
      const l = vlen(cr);
      area[i] = l / 2;
      const nn = l > 0 ? vscale(cr, 1 / l) : [0, 1, 0];
      nrm[i * 3] = nn[0]; nrm[i * 3 + 1] = nn[1]; nrm[i * 3 + 2] = nn[2];
      for (const p of [a, b, c]) {
        for (let d = 0; d < 3; d++) { if (p[d] < mn[d]) mn[d] = p[d]; if (p[d] > mx[d]) mx[d] = p[d]; }
        verts.set(p[0].toFixed(4) + ',' + p[1].toFixed(4) + ',' + p[2].toFixed(4), p);
      }
    }
    const center = vscale(vadd(mn, mx), 0.5);
    let radius = 0;
    const vlist = [...verts.values()];
    for (const v of vlist) radius = Math.max(radius, vdist(v, center));
    const kind = spec.kind;
    return {
      id: spec.id, kind, name: spec.name || spec.id, mat: spec.mat,
      tris, nrm, area, nt, verts: vlist, center, radius, bbMin: mn, bbMax: mx,
      specular: spec.specular !== undefined ? spec.specular : (kind === 'rock' || kind === 'trunk' || kind === 'building'),
      scatter: spec.scatter !== undefined ? spec.scatter : true,
      hard: kind === 'rock' || kind === 'trunk' || kind === 'building',
      roughness: spec.roughness !== undefined ? spec.roughness : (kind === 'rock' ? 0.006 : kind === 'trunk' ? 0.004 : 0),
      group: spec.group || spec.id,
    };
  }

  /** Moller-Trumbore. returns t in [0,1] along a->a+d or -1 */
  function segTri(ax, ay, az, dx, dy, dz, T, o) {
    const v0x = T[o], v0y = T[o + 1], v0z = T[o + 2];
    const e1x = T[o + 3] - v0x, e1y = T[o + 4] - v0y, e1z = T[o + 5] - v0z;
    const e2x = T[o + 6] - v0x, e2y = T[o + 7] - v0y, e2z = T[o + 8] - v0z;
    const px = dy * e2z - dz * e2y, py = dz * e2x - dx * e2z, pz = dx * e2y - dy * e2x;
    const det = e1x * px + e1y * py + e1z * pz;
    if (Math.abs(det) < 1e-12) return -1;
    const inv = 1 / det;
    const tx = ax - v0x, ty = ay - v0y, tz = az - v0z;
    const u = (tx * px + ty * py + tz * pz) * inv;
    if (u < -1e-9 || u > 1 + 1e-9) return -1;
    const qx = ty * e1z - tz * e1y, qy = tz * e1x - tx * e1z, qz = tx * e1y - ty * e1x;
    const v = (dx * qx + dy * qy + dz * qz) * inv;
    if (v < -1e-9 || u + v > 1 + 1e-9) return -1;
    const t = (e2x * qx + e2y * qy + e2z * qz) * inv;
    return t;
  }

  function segSphere(a, d, L2, c, r) {
    // shortest distance from sphere centre to the segment
    const w = vsub(c, a);
    let t = L2 > 0 ? vdot(w, d) / L2 : 0;
    t = clamp(t, 0, 1);
    const p = vadd(a, vscale(d, t));
    return vdist(p, c) <= r;
  }

  /**
   * all chords (inside intervals) of the segment a->b through every object.
   * returns [{obj, t0, t1, n0 (entry normal or null), n1 (exit normal or null), len}]
   */
  function segmentChords(objects, a, b, ignore) {
    const d = vsub(b, a), L2 = vdot(d, d), L = Math.sqrt(L2);
    const out = [];
    if (L < 1e-9) return out;
    for (const obj of objects) {
      if (ignore && (ignore === obj.id || ignore === obj.group || (ignore instanceof Set && (ignore.has(obj.id) || ignore.has(obj.group))))) continue;
      if (!segSphere(a, d, L2, obj.center, obj.radius + 1e-6)) continue;
      const ev = [];
      const T = obj.tris, N = obj.nrm;
      for (let i = 0; i < obj.nt; i++) {
        const t = segTri(a[0], a[1], a[2], d[0], d[1], d[2], T, i * 9);
        if (t > 1e-7 && t < 1 - 1e-7) {
          const dn = d[0] * N[i * 3] + d[1] * N[i * 3 + 1] + d[2] * N[i * 3 + 2];
          if (Math.abs(dn) < 1e-12) continue;
          ev.push({ t, enter: dn < 0, n: [N[i * 3], N[i * 3 + 1], N[i * 3 + 2]] });
        }
      }
      if (!ev.length) continue;
      ev.sort((x, y) => x.t - y.t);
      // dedupe hits on shared edges/vertices
      const evs = [];
      for (const e of ev) {
        const last = evs[evs.length - 1];
        if (last && last.enter === e.enter && Math.abs(last.t - e.t) * L < 1e-5) continue;
        evs.push(e);
      }
      let depth = 0, t0 = 0, n0 = null;
      for (const e of evs) {
        if (e.enter) {
          if (depth === 0) { t0 = e.t; n0 = e.n; }
          depth++;
        } else {
          if (depth === 0) { // segment started inside the object
            out.push({ obj, t0: 0, t1: e.t, n0: null, n1: e.n, len: e.t * L });
          } else {
            depth--;
            if (depth === 0) out.push({ obj, t0, t1: e.t, n0, n1: e.n, len: (e.t - t0) * L });
          }
        }
      }
      if (depth > 0) out.push({ obj, t0, t1: 1, n0, n1: null, len: (1 - t0) * L });
    }
    out.sort((x, y) => x.t0 - y.t0);
    return out;
  }

  /** first hit (any triangle of any object) along a ray, returns {t (metres), obj, tri, n, point} */
  function rayFirstHit(objects, o, dir, maxLen, ignoreId) {
    const d = vscale(dir, maxLen);
    let best = null;
    for (const obj of objects) {
      if (obj.id === ignoreId) continue;
      if (!segSphere(o, d, maxLen * maxLen, obj.center, obj.radius)) continue;
      for (let i = 0; i < obj.nt; i++) {
        const t = segTri(o[0], o[1], o[2], d[0], d[1], d[2], obj.tris, i * 9);
        if (t > 1e-6 && t <= 1 && (!best || t < best.t)) best = { t, obj, tri: i };
      }
    }
    if (!best) return null;
    const N = best.obj.nrm, i = best.tri;
    return { t: best.t * maxLen, obj: best.obj, tri: i, n: [N[i * 3], N[i * 3 + 1], N[i * 3 + 2]], point: vadd(o, vscale(d, best.t)) };
  }

  /** inside test for a point (ray parity against the closed mesh) */
  function pointInside(obj, p) {
    if (vdist(p, obj.center) > obj.radius) return false;
    const d = [0.5734, 0.3412, 0.7449];
    const far = vadd(p, vscale(d, obj.radius * 3 + 1));
    const ch = segmentChords([obj], p, far, null);
    return ch.some(c => c.t0 === 0);
  }

  // ------------------------------------------------------------------------------------------------
  // field propagation along a straight segment (with penetration through objects)
  // ------------------------------------------------------------------------------------------------
  /**
   * returns { E, lossDb, crossings:[{obj, len, lossDb, interfaceDb, p0, p1}], hardBlocked, opaqueBlocked }
   * env.en.penetration === false -> any crossed object stops the wave (opaque obstacle comparison mode)
   */
  function propagateSegment(env, a, b, E, ignore) {
    const chords = segmentChords(env.objects, a, b, ignore);
    const res = { E, lossDb: 0, crossings: [], hardBlocked: false, opaqueBlocked: false };
    if (!chords.length) return res;
    const k = vnorm(vsub(b, a));
    const p0 = cvPow(E);
    let cur = E;
    for (const ch of chords) {
      const obj = ch.obj;
      if (obj.hard) res.hardBlocked = true;
      if (env.en && env.en.penetration === false) { res.opaqueBlocked = true; cur = cvScale(cur, 0); res.crossings.push({ obj, len: ch.len, lossDb: Infinity, interfaceDb: Infinity, p0: vlerp(a, b, ch.t0), p1: vlerp(a, b, ch.t1) }); continue; }
      const mp = matProps(obj.mat, env.f);
      const before = cvPow(cur);
      if (ch.n0) cur = transmitStraight(cur, k, ch.n0, obj.mat, env.f).E;
      if (ch.n1) cur = transmitStraight(cur, k, ch.n1, obj.mat, env.f).E;
      const mid = cvPow(cur);
      const att = Math.exp(-mp.alpha * ch.len);
      const ph = -(mp.beta - env.k0) * ch.len;
      cur = cvScaleC(cur, cscale(cexpj(ph), att));
      const after = cvPow(cur);
      res.crossings.push({
        obj, len: ch.len,
        lossDb: before > 0 ? db10(before / Math.max(after, 1e-300)) : 0,
        interfaceDb: before > 0 ? db10(before / Math.max(mid, 1e-300)) : 0,
        bulkDb: NP2DB * mp.alpha * ch.len,
        p0: vlerp(a, b, ch.t0), p1: vlerp(a, b, ch.t1),
      });
    }
    res.E = cur;
    const p1 = cvPow(cur);
    res.lossDb = p0 > 0 ? db10(p0 / Math.max(p1, 1e-300)) : 0;
    return res;
  }

  // ------------------------------------------------------------------------------------------------
  // antennas
  // ------------------------------------------------------------------------------------------------
  /** dipole axis for a polarisation */
  const polAxis = pol => (pol === 'H' ? [1, 0, 0] : [0, 1, 0]);
  /** far-field launch vector of a half-wave-dipole-like source (gain 1.64 * sin^2) in sqrt(W) units */
  function launchField(ptW, pol, k) {
    const u = polAxis(pol);
    const perp = vsub(u, vscale(k, vdot(u, k)));   // |perp| = sin(psi)
    const g = Math.sqrt(ptW * 1.64);
    return cvFromReal(perp, C(g));
  }
  /** unit receive polarisation vector for a wave arriving along propagation direction k */
  function rxPolVector(pol, k) {
    const u = polAxis(pol);
    let perp = vsub(u, vscale(k, vdot(u, k)));
    const l = vlen(perp);
    if (l < 1e-6) perp = anyPerp(k); else perp = vscale(perp, 1 / l);
    return perp;
  }

  // ------------------------------------------------------------------------------------------------
  // ITU-R P.526 knife-edge
  // ------------------------------------------------------------------------------------------------
  function knifeEdgeDb(v) { return v <= -0.78 ? 0 : 6.9 + 20 * Math.log10(Math.sqrt((v - 0.1) * (v - 0.1) + 1) + v - 0.1); }

  // ------------------------------------------------------------------------------------------------
  // path tracer
  // ------------------------------------------------------------------------------------------------
  /**
   * env = { objects, f, lambda, k0, groundMat, groundRough, groundHalf, puddles:[{x,z,r,mat,id}],
   *         en:{direct, penetration, ground, specular, second, diffraction, diffuse},
   *         scatterS, foliageS, maxPaths }
   */
  function makeEnv(o) {
    const f = o.f || 2.4e9;
    return Object.assign({
      objects: [], groundMat: makeMaterial('soil_dry'), groundRough: 0.02, groundHalf: 80, puddles: [],
      en: { direct: true, penetration: true, ground: true, specular: true, second: true, diffraction: true, diffuse: true },
      scatterS: 0.35, foliageS: 0.45, maxPaths: 60, minRelDb: -60,
    }, o, { f, lambda: C0 / f, k0: 2 * Math.PI * f / C0 });
  }

  function groundMaterialAt(env, x, z) {
    for (const p of env.puddles) if ((x - p.x) * (x - p.x) + (z - p.z) * (z - p.z) <= p.r * p.r) return { mat: p.mat, id: p.id, puddle: true };
    return { mat: env.groundMat, id: 'ground', puddle: false };
  }

  function finalizePath(env, type, pts, Erx, rx, extra) {
    let L = 0;
    for (let i = 1; i < pts.length; i++) L += vdist(pts[i - 1], pts[i]);
    const kArr = vnorm(vsub(pts[pts.length - 1], pts[pts.length - 2]));
    const spread = env.lambda / (4 * Math.PI * L);
    const ph = cexpj(-env.k0 * L);
    const upol = rxPolVector(rx.pol, kArr);
    const s = cscale(cmul(cvDotReal(Erx, upol), ph), spread);
    const back = vscale(kArr, -1);
    const kDep = vnorm(vsub(pts[1], pts[0]));
    return Object.assign({
      type, points: pts, length: L, delay: L / C0, amp: s, powerW: cabs2(s), coherent: true,
      az: azOf(back), el: elOf(back), aodAz: azOf(kDep), aodEl: elOf(kDep),
      interactions: [], crossings: [],
    }, extra || {});
  }

  /** trace every propagation path from transmitter tx to receiver rx. */
  function tracePaths(env, tx, rx) {
    const paths = [];
    const T = tx.pos, R = rx.pos;
    const en = env.en;
    const objs = env.objects;

    // ---------- direct ----------
    let directSeg = null;
    if (en.direct) {
      const k = vnorm(vsub(R, T));
      const E0 = launchField(tx.ptW, tx.pol, k);
      directSeg = propagateSegment(env, T, R, E0, null);
      const p = finalizePath(env, 'direct', [T, R], directSeg.E, rx, {
        crossings: directSeg.crossings, obstructed: directSeg.crossings.length > 0, hardBlocked: directSeg.hardBlocked,
        penetrationDb: directSeg.lossDb,
      });
      p.interactions = directSeg.crossings.map(c => ({ obj: c.obj.id, kind: 'transmit', lossDb: c.lossDb, len: c.len }));
      paths.push(p);
    }

    // ---------- ground reflection ----------
    if (en.ground && T[1] > 0 && R[1] > 0) {
      const s = T[1] / (T[1] + R[1]);
      const P = vlerp(mirrorGround(T), R, s); P[1] = 0;
      if (Math.abs(P[0]) <= env.groundHalf && Math.abs(P[2]) <= env.groundHalf) {
        const gm = groundMaterialAt(env, P[0], P[2]);
        const k1 = vnorm(vsub(P, T));
        let seg1 = propagateSegment(env, T, P, launchField(tx.ptW, tx.pol, k1), null);
        const rf = reflectField(seg1.E, k1, [0, 1, 0], gm.mat, env.f, gm.puddle ? 0.001 : env.groundRough, env.lambda);
        const seg2 = propagateSegment(env, P, R, rf.E, null);
        const p = finalizePath(env, 'ground', [T, P, R], seg2.E, rx, {
          crossings: seg1.crossings.concat(seg2.crossings), hardBlocked: seg1.hardBlocked || seg2.hardBlocked,
        });
        p.interactions = [{ obj: gm.id, kind: 'reflect', thetaDeg: rf.thetaDeg, gs: cabs(rf.gs), gp: cabs(rf.gp), rough: rf.rho, point: P }];
        paths.push(p);
      }
    }

    // ---------- first-order specular on facets ----------
    if (en.specular) {
      for (const obj of objs) {
        if (!obj.specular) continue;
        // quick reject: Tx and Rx both far from object relative to its size still allowed (image method exact)
        const Tt = obj.tris, N = obj.nrm;
        for (let i = 0; i < obj.nt; i++) {
          const o = i * 9, n = [N[i * 3], N[i * 3 + 1], N[i * 3 + 2]];
          const a0 = [Tt[o], Tt[o + 1], Tt[o + 2]];
          const dT = vdot(n, vsub(T, a0)), dR = vdot(n, vsub(R, a0));
          if (dT <= 1e-6 || dR <= 1e-6) continue;
          const Ti = vsub(T, vscale(n, 2 * dT));
          const P = vlerp(Ti, R, dT / (dT + dR));
          if (P[1] < 0.01 || !inTri(P, Tt, o)) continue;   // facets of partly buried rocks below ground are invalid
          const pth = facetPath(env, tx, rx, obj, i, n, [T, P, R], [P]);
          if (pth) paths.push(pth);
        }
      }
    }

    // ---------- second order: ground -> facet, facet -> ground ----------
    if (en.second && en.specular && en.ground && T[1] > 0 && R[1] > 0) {
      const Tg = mirrorGround(T);
      for (const obj of objs) {
        if (!obj.specular) continue;
        const Tt = obj.tris, N = obj.nrm;
        for (let i = 0; i < obj.nt; i++) {
          const o = i * 9, n = [N[i * 3], N[i * 3 + 1], N[i * 3 + 2]];
          const a0 = [Tt[o], Tt[o + 1], Tt[o + 2]];
          const dR = vdot(n, vsub(R, a0));
          if (dR <= 1e-6) continue;
          // (a) ground first, then facet
          const dTg = vdot(n, vsub(Tg, a0));
          if (dTg > 1e-6) {
            const Tgf = vsub(Tg, vscale(n, 2 * dTg));
            const P2 = vlerp(Tgf, R, dTg / (dTg + dR));
            if (P2[1] > 0.01 && inTri(P2, Tt, o)) {
              const u = T[1] / (P2[1] + T[1]);
              const P1 = vlerp(Tg, P2, u); P1[1] = 0;
              if (u > 0 && u < 1 && Math.abs(P1[0]) <= env.groundHalf && Math.abs(P1[2]) <= env.groundHalf && vdot(n, vsub(P1, a0)) > 0) {
                const pth = facetPath(env, tx, rx, obj, i, n, [T, P1, P2, R], [P2], 'ground-specular');
                if (pth) paths.push(pth);
              }
            }
          }
          // (b) facet first, then ground
          const dT = vdot(n, vsub(T, a0));
          if (dT > 1e-6) {
            const Tf = vsub(T, vscale(n, 2 * dT));
            if (Tf[1] > 0) {
              const Tfg = mirrorGround(Tf);
              const s = Tf[1] / (R[1] + Tf[1]);
              const P2 = vlerp(Tfg, R, s); P2[1] = 0;
              if (vdot(n, vsub(P2, a0)) > 1e-6 && Math.abs(P2[0]) <= env.groundHalf && Math.abs(P2[2]) <= env.groundHalf) {
                const den = vdot(n, vsub(P2, Tf));
                if (Math.abs(den) > 1e-9) {
                  const w = vdot(n, vsub(a0, Tf)) / den;
                  if (w > 0 && w < 1) {
                    const P1 = vlerp(Tf, P2, w);
                    if (inTri(P1, Tt, o) && P1[1] > 0.01) {
                      const pth = facetPath(env, tx, rx, obj, i, n, [T, P1, P2, R], [P1], 'specular-ground');
                      if (pth) paths.push(pth);
                    }
                  }
                }
              }
            }
          }
        }
      }
    }

    // ---------- knife-edge diffraction around hard obstacles blocking the direct path ----------
    if (en.diffraction && directSeg && directSeg.crossings.length) {
      const blockers = [...new Set(directSeg.crossings.filter(c => c.obj.hard).map(c => c.obj))];
      for (const obj of blockers) for (const dp of diffractionPaths(env, tx, rx, obj)) paths.push(dp);
    }

    // ---------- diffuse scattering ----------
    if (en.diffuse) {
      for (const obj of objs) {
        if (!obj.scatter) continue;
        const dp = diffusePath(env, tx, rx, obj);
        if (dp) paths.push(dp);
      }
    }

    // prune
    let pmax = 0;
    for (const p of paths) if (p.powerW > pmax) pmax = p.powerW;
    const thr = pmax * undb(env.minRelDb);
    const kept = paths.filter(p => p.type === 'direct' || p.powerW >= thr);
    kept.sort((a, b) => b.powerW - a.powerW);
    if (kept.length > env.maxPaths) {
      const d = kept.find(p => p.type === 'direct');
      const top = kept.slice(0, env.maxPaths);
      if (d && !top.includes(d)) top.push(d);
      return top;
    }
    return kept;
  }

  function inTri(P, T, o) {
    const a = [T[o], T[o + 1], T[o + 2]], b = [T[o + 3], T[o + 4], T[o + 5]], c = [T[o + 6], T[o + 7], T[o + 8]];
    const v0 = vsub(c, a), v1 = vsub(b, a), v2 = vsub(P, a);
    const d00 = vdot(v0, v0), d01 = vdot(v0, v1), d02 = vdot(v0, v2), d11 = vdot(v1, v1), d12 = vdot(v1, v2);
    const den = d00 * d11 - d01 * d01;
    if (Math.abs(den) < 1e-18) return false;
    const u = (d11 * d02 - d01 * d12) / den, v = (d00 * d12 - d01 * d02) / den;
    return u >= -1e-6 && v >= -1e-6 && u + v <= 1 + 1e-6;
  }

  /** build a facet reflection path (orders 1 and 2). pts = full polyline, facetPts = [facet point] */
  function facetPath(env, tx, rx, obj, tri, n, pts, facetPts, type) {
    type = type || 'specular';
    const P = facetPts[0];
    let E = launchField(tx.ptW, tx.pol, vnorm(vsub(pts[1], pts[0])));
    const crossings = [];
    const inter = [];
    let hard = false;
    let dToFacet = 0, dFromFacet = 0, passed = false;
    for (let s = 0; s < pts.length - 1; s++) {
      const a = pts[s], b = pts[s + 1];
      const segLen = vdist(a, b);
      if (!passed) dToFacet += segLen; else dFromFacet += segLen;
      const seg = propagateSegment(env, a, b, E, obj.id);
      if (seg.opaqueBlocked) return null;
      crossings.push(...seg.crossings);
      hard = hard || seg.hardBlocked;
      E = seg.E;
      if (s === pts.length - 2) break;
      const k = vnorm(vsub(b, a));
      if (b === P) {
        const rf = reflectField(E, k, n, obj.mat, env.f, obj.roughness, env.lambda);
        E = rf.E; passed = true;
        inter.push({ obj: obj.id, kind: 'reflect', thetaDeg: rf.thetaDeg, gs: cabs(rf.gs), gp: cabs(rf.gp), rough: rf.rho, point: P, tri });
      } else { // ground bounce
        const gm = groundMaterialAt(env, b[0], b[2]);
        const rf = reflectField(E, k, [0, 1, 0], gm.mat, env.f, gm.puddle ? 0.001 : env.groundRough, env.lambda);
        E = rf.E;
        inter.push({ obj: gm.id, kind: 'reflect', thetaDeg: rf.thetaDeg, gs: cabs(rf.gs), gp: cabs(rf.gp), rough: rf.rho, point: b });
      }
    }
    // finite-facet (physical optics) correction: facet smaller than the first Fresnel zone
    const ri = inter.find(x => x.tri === tri);
    const cosi = Math.cos(ri.thetaDeg * D2R);
    const Fz = env.lambda * dToFacet * dFromFacet / (dToFacet + dFromFacet);
    const fac = Math.min(1, obj.area[tri] * cosi / Math.max(Fz, 1e-9));
    E = cvScale(E, fac);
    ri.facetFactorDb = 20 * Math.log10(Math.max(fac, 1e-12));
    return finalizePath(env, type, pts, E, rx, { interactions: inter, crossings, hardBlocked: hard, objId: obj.id });
  }

  /** knife-edge paths over the top and around the sides of obstacle obj */
  function diffractionPaths(env, tx, rx, obj) {
    const T = tx.pos, R = rx.pos;
    const H = [R[0] - T[0], 0, R[2] - T[2]];
    const Hl = vlen(H);
    if (Hl < 0.5) return [];
    const hd = vscale(H, 1 / Hl), pd = [-hd[2], 0, hd[0]];
    let top = null, left = null, right = null;
    for (const v of obj.verts) {
      const t = vdot(vsub(v, T), hd) / Hl;
      if (t <= 0.01 || t >= 0.99) continue;
      const yL = T[1] + t * (R[1] - T[1]);
      const h = v[1] - yL, lat = vdot(vsub(v, T), pd);
      if (!top || h > top.h) top = { h, t };
      if (!left || lat > left.h) left = { h: lat, t };
      if (!right || -lat > right.h) right = { h: -lat, t };
    }
    const out = [];
    const edges = [];
    if (top && top.h > -1) edges.push({ name: 'top', e: top, off: [0, top.h, 0] });
    if (left && left.h > -1) edges.push({ name: 'left', e: left, off: vscale(pd, left.h) });
    if (right && right.h > -1) edges.push({ name: 'right', e: right, off: vscale(pd, -right.h) });
    for (const ed of edges) {
      const base = vlerp(T, R, ed.e.t);
      const Ept = vadd(base, ed.off);
      if (Ept[1] < 0.05) continue;
      const d1 = vdist(T, Ept), d2 = vdist(Ept, R);
      const v = ed.e.h * Math.sqrt(2 * (d1 + d2) / (env.lambda * d1 * d2));
      const J = knifeEdgeDb(v);
      if (J > 45) continue;
      const k1 = vnorm(vsub(Ept, T)), k2 = vnorm(vsub(R, Ept));
      const s1 = propagateSegment(env, T, Ept, launchField(tx.ptW, tx.pol, k1), obj.id);
      if (s1.opaqueBlocked) continue;
      let E = cvTransverse(s1.E, k2);
      const s2 = propagateSegment(env, Ept, R, E, obj.id);
      if (s2.opaqueBlocked) continue;
      E = cvScaleC(s2.E, cscale(cexpj(-Math.PI / 4), Math.pow(10, -J / 20)));
      out.push(finalizePath(env, 'diffraction', [T, Ept, R], E, rx, {
        interactions: [{ obj: obj.id, kind: 'diffract', edge: ed.name, v, lossDb: J, point: Ept }],
        crossings: s1.crossings.concat(s2.crossings), hardBlocked: s1.hardBlocked || s2.hardBlocked, objId: obj.id,
      }));
    }
    return out;
  }

  /** incoherent diffuse scattering path via object obj (Lambertian / volume model) */
  function diffusePath(env, tx, rx, obj) {
    const T = tx.pos, R = rx.pos, c = obj.center;
    let S, nS, cosI = 1, cosS = 1, sigma;
    if (obj.kind === 'foliage') {
      S = c.slice();
      if (pointInside(obj, T) || pointInside(obj, R)) return null;
      const r = obj.radius * 0.8;
      const A = Math.PI * r * r;
      sigma = 4 * env.foliageS * env.foliageS * A * 0.25;
    } else if (obj.kind === 'trunk') {
      const hT = [T[0] - c[0], 0, T[2] - c[2]], hR = [R[0] - c[0], 0, R[2] - c[2]];
      const bis = vnorm(vadd(vnorm(hT), vnorm(hR)));
      const rTr = Math.max(0.05, (obj.bbMax[0] - obj.bbMin[0]) / 2);
      const y = clamp((T[1] + R[1]) / 2, obj.bbMin[1] + 0.2, obj.bbMax[1] - 0.2);
      S = [c[0] + bis[0] * rTr, y, c[2] + bis[2] * rTr];
      nS = bis;
      const vis = Math.min(3, obj.bbMax[1] - obj.bbMin[1]);
      sigma = 2 * rTr * vis;
    } else {
      const bis = vnorm(vadd(vnorm(vsub(T, c)), vnorm(vsub(R, c))));
      const r = obj.radius * 0.75;
      S = vadd(c, vscale(bis, r));
      if (S[1] < 0.05) S[1] = 0.05;
      nS = bis;
      sigma = Math.PI * r * r;
    }
    const kI = vnorm(vsub(S, T)), kS = vnorm(vsub(R, S));
    if (nS) {
      cosI = -vdot(kI, nS); cosS = vdot(kS, nS);
      if (cosI <= 0.02 || cosS <= 0.02) return null;
      const fr = fresnel(AIR_MEDIUM, medium(obj.mat, env.f), cosI);
      const g2 = (cabs2(fr.gs) + cabs2(fr.gp)) / 2;
      sigma = 4 * env.scatterS * env.scatterS * g2 * sigma * cosI * cosS;
    }
    const d1 = vdist(T, S), d2 = vdist(S, R);
    if (d1 < 0.3 || d2 < 0.3) return null;
    const ignore = obj.kind === 'foliage' ? null : obj.id;
    const E0 = launchField(tx.ptW, tx.pol, kI);
    const s1 = propagateSegment(env, T, S, E0, ignore);
    const s2 = propagateSegment(env, S, R, cvTransverse(s1.E, kS), ignore);
    if (s1.opaqueBlocked || s2.opaqueBlocked) return null;
    const gtLoss = cvPow(E0) > 0 ? cvPow(s2.E) / cvPow(E0) : 0;     // penetration losses on both legs
    const PtGt = cvPow(E0);                                        // Pt*Gt toward the scatterer
    const Pw = PtGt * env.lambda * env.lambda * sigma / (Math.pow(4 * Math.PI, 3) * d1 * d1 * d2 * d2) * gtLoss;
    if (!(Pw > 0)) return null;
    const back = vscale(kS, -1);
    return {
      type: 'scatter', points: [T, S, R], length: d1 + d2, delay: (d1 + d2) / C0,
      amp: cscale(cexpj(hashPhase(obj.id, tx.id || 'tx')), Math.sqrt(Pw)), powerW: Pw, coherent: false,
      az: azOf(back), el: elOf(back), aodAz: azOf(kI), aodEl: elOf(kI),
      interactions: [{ obj: obj.id, kind: 'scatter', sigma, cosI, cosS, point: S }],
      crossings: s1.crossings.concat(s2.crossings), objId: obj.id,
    };
  }

  /** summary of a receiver's channel */
  function channelSummary(paths) {
    const d = paths.find(p => p.type === 'direct');
    let coh = C(0), inc = 0, tot = 0, strongest = null;
    for (const p of paths) {
      tot += p.powerW;
      if (p.coherent) coh = cadd(coh, p.amp); else inc += p.powerW;
      if (!strongest || p.powerW > strongest.powerW) strongest = p;
    }
    let state = 'LOS';
    if (d && d.obstructed) state = d.hardBlocked ? 'NLOS' : 'OLOS';
    const dp = d ? d.powerW : 0;
    // RMS delay spread
    let m1 = 0, m2 = 0;
    for (const p of paths) { m1 += p.powerW * p.delay; m2 += p.powerW * p.delay * p.delay; }
    const mean = tot > 0 ? m1 / tot : 0;
    const rms = tot > 0 ? Math.sqrt(Math.max(0, m2 / tot - mean * mean)) : 0;
    return {
      state, directW: dp, totalW: tot, coherentW: cabs2(coh) + inc,
      kFactorDb: db10(dp / Math.max(tot - dp, 1e-300)), strongest,
      rmsDelayNs: rms * 1e9, nPaths: paths.length,
      directLossDb: d ? (d.penetrationDb || 0) : null,
    };
  }

  // ------------------------------------------------------------------------------------------------
  // switched-beam array + PV-ML (JavaScript port of doa_sim.py SwitchedBeamArray/PowerVectorEstimator)
  // ------------------------------------------------------------------------------------------------
  class SwitchedBeamArray {
    constructor(n = 6, bwScale = 1.15, sidelobeDb = 20, efficiency = 0.65, yawDeg = 0, elBwDeg = 65) {
      this.n = n; this.bwScale = bwScale; this.sidelobeDb = sidelobeDb; this.yaw = yawDeg; this.elBw = elBwDeg;
      const spacing = 360 / n;
      this.bw = bwScale * spacing;
      this.boresights = Array.from({ length: n }, (_, i) => wrap360(yawDeg + spacing * i));
      this.g0 = Math.max(1, efficiency * 41253 / (this.bw * this.bw));
      this.grid = Array.from({ length: 360 }, (_, i) => i);
      this.G = this.grid.map(t => this.gain(t));
    }
    gain(theta) {
      const out = new Float64Array(this.n);
      for (let i = 0; i < this.n; i++) {
        const d = wrap180(theta - this.boresights[i]);
        out[i] = this.g0 * undb(-Math.min(12 * (d / this.bw) * (d / this.bw), this.sidelobeDb));
      }
      return out;
    }
    elGain(el) { return undb(-Math.min(12 * (el / this.elBw) * (el / this.elBw), 25)); }
  }

  /**
   * expected (noise-normalised) per-beam power for a set of drone paths and interferer path sets.
   * decorrelate: random phase per dwell for every coherent path except the strongest (moving drone).
   */
  function beamPowers(arr, dronePaths, interfSets, noiseW, rng, decorrelate) {
    const n = arr.n;
    const m = new Float64Array(n);
    const gcache = new Map();
    const gk = p => { let g = gcache.get(p); if (!g) { g = { g: arr.gain(p.az), e: arr.elGain(p.el) }; gcache.set(p, g); } return g; };
    let strongest = null;
    for (const p of dronePaths) if (p.coherent && (!strongest || p.powerW > strongest.powerW)) strongest = p;
    const parts = { signal: new Float64Array(n), interf: new Float64Array(n) };
    for (let i = 0; i < n; i++) {
      let c = C(0), inc = 0;
      for (const p of dronePaths) {
        const g = gk(p);
        const amp = Math.sqrt(g.g[i] * g.e);
        if (p.coherent) {
          let a = p.amp;
          if (decorrelate && p !== strongest) a = cmul(a, cexpj(rng() * 2 * Math.PI));
          c = cadd(c, cscale(a, amp));
        } else inc += p.powerW * g.g[i] * g.e;
      }
      let I = 0;
      for (const set of interfSets) {
        let ci = C(0), ii = 0;
        for (const p of set.paths) {
          const g = gk(p);
          const amp = Math.sqrt(g.g[i] * g.e) * set.rejection;
          if (p.coherent) ci = cadd(ci, cscale(decorrelate ? cmul(p.amp, cexpj(rng() * 2 * Math.PI)) : p.amp, amp));
          else ii += p.powerW * g.g[i] * g.e * set.rejection * set.rejection;
        }
        I += cabs2(ci) + ii;
      }
      parts.signal[i] = (cabs2(c) + inc) / noiseW;
      parts.interf[i] = I / noiseW;
      m[i] = parts.signal[i] + parts.interf[i] + 1;
    }
    return { m, parts };
  }
  /** measured power per beam (average of L samples of a complex Gaussian with mean power m_i) */
  function measureBeams(m, L, rng) { return Array.from(m, mi => gammaSample(L, mi / L, rng)); }

  function parab(y0, y1, y2) {
    const den = y0 - 2 * y1 + y2;
    const delta = den > 1e-12 ? clamp(0.5 * (y0 - y2) / den, -1, 1) : 0;
    return { delta, den };
  }

  /** PV-ML: Gamma maximum-likelihood fit of the power vector to the known beam patterns */
  function pvmlEstimate(arr, p, L, sigma2 = 1) {
    const N = arr.n, Tn = arr.grid.length;
    const floor = 1e-3 * sigma2 / arr.g0;
    const profile = (G) => {
      let num = 0, den = 0;
      for (let i = 0; i < N; i++) { num += Math.max(p[i] - sigma2, 0) * G[i]; den += G[i] * G[i]; }
      let a = Math.max(num / den, floor);
      for (let it = 0; it < 5; it++) {
        let grad = 0, fish = 0;
        for (let i = 0; i < N; i++) { const mm = a * G[i] + sigma2; grad += G[i] * (mm - p[i]) / (mm * mm); fish += G[i] * G[i] / (mm * mm); }
        a = Math.max(a - grad / fish, floor);
      }
      let nll = 0;
      for (let i = 0; i < N; i++) { const mm = a * G[i] + sigma2; nll += L * (Math.log(mm) + p[i] / mm); }
      return { nll, a };
    };
    const nll = new Float64Array(Tn), aa = new Float64Array(Tn);
    let k = 0;
    for (let t = 0; t < Tn; t++) { const r = profile(arr.G[t]); nll[t] = r.nll; aa[t] = r.a; if (r.nll < nll[k]) k = t; }
    const pr = parab(nll[(k - 1 + Tn) % Tn], nll[k], nll[(k + 1) % Tn]);
    const th1 = arr.grid[k] + pr.delta;
    const d = 0.25;
    const nf = [-1, 0, 1].map(s => profile(arr.gain(th1 + s * d)).nll);
    const pr2 = parab(nf[0], nf[1], nf[2]);
    const theta = wrap360(th1 + pr2.delta * d);
    const curv = pr.den;
    const sigCrb = curv > 1e-12 ? 1 / Math.sqrt(curv) : 180;
    const G = arr.G[k], a = aa[k];
    let red = 0;
    for (let i = 0; i < N; i++) { const mm = a * G[i] + sigma2, r = p[i] / mm; red += r - 1 - Math.log(r); }
    red = 2 * L * red / Math.max(N - 2, 1);
    const sigma = clamp(sigCrb * Math.sqrt(Math.max(1, red)), 0.05, 180);
    let mn = Infinity;
    for (let t = 0; t < Tn; t++) mn = Math.min(mn, nll[t]);
    const spectrum = Array.from(nll, v => Math.max(-40, -(v - mn) * 10 / Math.LN10));   // likelihood ratio, dB
    return { theta, sigma, redDev: red, snrDb: db10(Math.max(a / sigma2, 1e-3)), spectrum };
  }

  // ------------------------------------------------------------------------------------------------
  // coherent UCA reference: Bartlett + MUSIC
  // ------------------------------------------------------------------------------------------------
  function ucaRadiusWl(n) { return 0.5 / (2 * Math.sin(Math.PI / n)); }
  function ucaSteer(n, azDeg, elDeg) {
    const r = ucaRadiusWl(n) * 2 * Math.PI, ce = Math.cos((elDeg || 0) * D2R);
    const re = new Float64Array(n), im = new Float64Array(n);
    for (let m = 0; m < n; m++) {
      const ph = r * ce * Math.cos((azDeg - 360 * m / n) * D2R);
      re[m] = Math.cos(ph); im[m] = Math.sin(ph);
    }
    return { re, im };
  }
  /** sample covariance from K simulated snapshots; returns {re, im} n*n row-major */
  function ucaCovariance(n, dronePaths, interfSets, noiseW, K, rng) {
    const srcs = [];  // each: vector (re,im) scaled by sqrt(power/noise)
    const coh = { re: new Float64Array(n), im: new Float64Array(n) };
    let any = false;
    for (const p of dronePaths) {
      const a = ucaSteer(n, p.az, p.el);
      if (p.coherent) {
        const s = cscale(p.amp, 1 / Math.sqrt(noiseW));
        for (let m = 0; m < n; m++) { coh.re[m] += s.re * a.re[m] - s.im * a.im[m]; coh.im[m] += s.re * a.im[m] + s.im * a.re[m]; }
        any = true;
      } else {
        const g = Math.sqrt(p.powerW / noiseW);
        srcs.push({ re: a.re.map(v => v * g), im: a.im.map(v => v * g) });
      }
    }
    if (any) srcs.push(coh);
    for (const set of interfSets) {
      const v = { re: new Float64Array(n), im: new Float64Array(n) };
      for (const p of set.paths) {
        const a = ucaSteer(n, p.az, p.el);
        const s = cscale(p.amp, set.rejection / Math.sqrt(noiseW));
        for (let m = 0; m < n; m++) { v.re[m] += s.re * a.re[m] - s.im * a.im[m]; v.im[m] += s.re * a.im[m] + s.im * a.re[m]; }
      }
      srcs.push(v);
    }
    const Rre = new Float64Array(n * n), Rim = new Float64Array(n * n);
    const xr = new Float64Array(n), xi = new Float64Array(n);
    const h = Math.SQRT1_2;
    for (let k = 0; k < K; k++) {
      for (let m = 0; m < n; m++) { xr[m] = randn(rng) * h; xi[m] = randn(rng) * h; }
      for (const s of srcs) {
        const sr = randn(rng) * h, si = randn(rng) * h;
        for (let m = 0; m < n; m++) { xr[m] += s.re[m] * sr - s.im[m] * si; xi[m] += s.re[m] * si + s.im[m] * sr; }
      }
      for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
        Rre[i * n + j] += xr[i] * xr[j] + xi[i] * xi[j];
        Rim[i * n + j] += xi[i] * xr[j] - xr[i] * xi[j];
      }
    }
    for (let i = 0; i < n * n; i++) { Rre[i] /= K; Rim[i] /= K; }
    return { re: Rre, im: Rim, n, nSources: srcs.length };
  }
  /** cyclic Jacobi eigen-decomposition of a real symmetric matrix (row-major, size m) */
  function jacobiEig(A, m) {
    const a = Float64Array.from(A), V = new Float64Array(m * m);
    for (let i = 0; i < m; i++) V[i * m + i] = 1;
    for (let sweep = 0; sweep < 60; sweep++) {
      let off = 0;
      for (let p = 0; p < m; p++) for (let q = p + 1; q < m; q++) off += a[p * m + q] * a[p * m + q];
      if (off < 1e-20) break;
      for (let p = 0; p < m; p++) for (let q = p + 1; q < m; q++) {
        const apq = a[p * m + q];
        if (Math.abs(apq) < 1e-30) continue;
        const app = a[p * m + p], aqq = a[q * m + q];
        const th = (aqq - app) / (2 * apq);
        const t = Math.sign(th || 1) / (Math.abs(th) + Math.sqrt(th * th + 1));
        const c = 1 / Math.sqrt(t * t + 1), s = t * c;
        for (let k = 0; k < m; k++) {
          const akp = a[k * m + p], akq = a[k * m + q];
          a[k * m + p] = c * akp - s * akq; a[k * m + q] = s * akp + c * akq;
        }
        for (let k = 0; k < m; k++) {
          const apk = a[p * m + k], aqk = a[q * m + k];
          a[p * m + k] = c * apk - s * aqk; a[q * m + k] = s * apk + c * aqk;
        }
        for (let k = 0; k < m; k++) {
          const vkp = V[k * m + p], vkq = V[k * m + q];
          V[k * m + p] = c * vkp - s * vkq; V[k * m + q] = s * vkp + c * vkq;
        }
      }
    }
    const vals = Array.from({ length: m }, (_, i) => a[i * m + i]);
    return { vals, V };
  }
  /** Bartlett and MUSIC spectra (dB, peak-normalised) on a 1 degree grid */
  function arraySpectra(R, dSources) {
    const n = R.n, m = 2 * n;
    const M = new Float64Array(m * m);
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const re = R.re[i * n + j], im = R.im[i * n + j];
      M[i * m + j] = re; M[(i + n) * m + (j + n)] = re;
      M[i * m + (j + n)] = -im; M[(i + n) * m + j] = im;
    }
    const { vals, V } = jacobiEig(M, m);
    const order = vals.map((v, i) => [v, i]).sort((x, y) => x[0] - y[0]);
    const d = clamp(dSources, 1, n - 1);
    const nn = 2 * (n - d);
    const P = new Float64Array(m * m);
    for (let q = 0; q < nn; q++) {
      const c = order[q][1];
      for (let i = 0; i < m; i++) { const vi = V[i * m + c]; if (vi === 0) continue; for (let j = 0; j < m; j++) P[i * m + j] += vi * V[j * m + c]; }
    }
    const bart = new Float64Array(360), mus = new Float64Array(360);
    const x = new Float64Array(m);
    const quad = (Mx) => { let s = 0; for (let i = 0; i < m; i++) { let r = 0; for (let j = 0; j < m; j++) r += Mx[i * m + j] * x[j]; s += x[i] * r; } return s; };
    for (let t = 0; t < 360; t++) {
      const a = ucaSteer(n, t, 0);
      for (let i = 0; i < n; i++) { x[i] = a.re[i]; x[i + n] = a.im[i]; }
      bart[t] = quad(M) / n;
      mus[t] = 1 / Math.max(quad(P), 1e-12);
    }
    const norm = arrv => { let mx = -Infinity; for (const v of arrv) mx = Math.max(mx, v); return Array.from(arrv, v => Math.max(-40, db10(v / mx))); };
    const peak = arrv => { let k = 0; for (let i = 1; i < 360; i++) if (arrv[i] > arrv[k]) k = i; const pr = parab(-arrv[(k + 359) % 360], -arrv[k], -arrv[(k + 1) % 360]); return wrap360(k + pr.delta); };
    const bdB = norm(bart), mdB = norm(mus);
    return { bartlett: bdB, music: mdB, bartlettPeak: peak(bdB), musicPeak: peak(mdB), eigenvalues: order.filter((_, i) => i % 2 === 0).map(o => o[0]).reverse() };
  }

  // ------------------------------------------------------------------------------------------------
  // Kalman bearing tracker [angle, rate] with circular innovation, adaptive R and gating
  // ------------------------------------------------------------------------------------------------
  class AngleTracker {
    constructor(qDegS2 = 6) { this.q = qDegS2 * qDegS2; this.reset(); }
    reset() { this.x = null; this.P = null; this.miss = 0; this.status = 'idle'; }
    step(z, sig, dt) {
      const R = sig * sig + 0.25;
      if (!this.x) { this.x = [z, 0]; this.P = [R, 0, 0, 100]; this.status = 'init'; return this.out(); }
      // predict
      const [th, w] = this.x;
      this.x = [wrap360(th + w * dt), w];
      const P = this.P, q = this.q;
      const p00 = P[0] + dt * (P[2] + P[1]) + dt * dt * P[3] + q * dt * dt * dt / 3;
      const p01 = P[1] + dt * P[3] + q * dt * dt / 2;
      const p10 = P[2] + dt * P[3] + q * dt * dt / 2;
      const p11 = P[3] + q * dt;
      const nu = wrap180(z - this.x[0]);
      const S = p00 + R;
      if (Math.abs(nu) > 4 * Math.sqrt(S) && Math.abs(nu) > 8) {
        this.miss++;
        this.P = [p00, p01, p10, p11];
        if (this.miss >= 3) { this.x = [z, 0]; this.P = [R, 0, 0, 100]; this.miss = 0; this.status = 'reacquire'; }
        else this.status = 'coast';
        return this.out();
      }
      this.miss = 0;
      const K0 = p00 / S, K1 = p10 / S;
      this.x = [wrap360(this.x[0] + K0 * nu), this.x[1] + K1 * nu];
      this.P = [(1 - K0) * p00, (1 - K0) * p01, p10 - K1 * p00, p11 - K1 * p01];
      this.status = 'track';
      return this.out();
    }
    out() { return { angle: this.x[0], rate: this.x[1], sigma: Math.sqrt(Math.max(this.P[0], 0)), status: this.status }; }
  }

  // ------------------------------------------------------------------------------------------------
  // multi-receiver localisation: weighted least-squares bearing-line intersection in the X-Z plane
  // ------------------------------------------------------------------------------------------------
  function localize(stations) {
    const st = stations.filter(s => isFinite(s.az));
    if (st.length < 2) return { valid: false };
    // 2-D coordinates u = x, v = -z  -> azimuth is the standard CCW angle
    let est = null;
    let A00, A01, A11, det;
    for (let it = 0; it < 4; it++) {
      A00 = 0; A01 = 0; A11 = 0; let b0 = 0, b1 = 0;
      for (const s of st) {
        const a = s.az * D2R, nu = -Math.sin(a), nv = Math.cos(a);
        const pu = s.x, pv = -s.z;
        const sg = Math.max(s.sigma || 3, 0.3) * D2R;
        const r = est ? Math.max(2, Math.hypot(est[0] - pu, est[1] - pv)) : 30;
        const w = 1 / (sg * sg * r * r);
        A00 += w * nu * nu; A01 += w * nu * nv; A11 += w * nv * nv;
        const c = nu * pu + nv * pv;
        b0 += w * nu * c; b1 += w * nv * c;
      }
      det = A00 * A11 - A01 * A01;
      if (det <= 1e-12 * (A00 + A11) * (A00 + A11)) return { valid: false, reason: 'parallel bearings' };
      est = [(A11 * b0 - A01 * b1) / det, (A00 * b1 - A01 * b0) / det];
    }
    // covariance in (u,v) -> (x,z): z = -v flips the sign of the cross term
    const cuu = A11 / det, cvv = A00 / det, cuv = -A01 / det;
    const cov = [cuu, -cuv, -cuv, cvv];
    const tr = cov[0] + cov[3], dd = cov[0] * cov[3] - cov[1] * cov[1];
    const l1 = tr / 2 + Math.sqrt(Math.max(0, tr * tr / 4 - dd)), l2 = tr / 2 - Math.sqrt(Math.max(0, tr * tr / 4 - dd));
    const ang = 0.5 * Math.atan2(2 * cov[1], cov[0] - cov[3]);
    // check estimate lies in front of the bearings (not behind receivers)
    let behind = 0;
    for (const s of st) { const a = s.az * D2R; if ((est[0] - s.x) * Math.cos(a) + (est[1] + s.z) * Math.sin(a) < 0) behind++; }
    return { valid: true, x: est[0], z: -est[1], cov, ellipse: { a: Math.sqrt(Math.max(l1, 0)), b: Math.sqrt(Math.max(l2, 0)), angle: ang }, behind };
  }

  // ------------------------------------------------------------------------------------------------
  // receiver noise
  // ------------------------------------------------------------------------------------------------
  function noisePowerW(bandwidthHz, nfDb) { return KB * 290 * bandwidthHz * undb(nfDb); }

  // ------------------------------------------------------------------------------------------------
  // horizontal slice of a mesh (for the 2-D FDTD material map)
  // ------------------------------------------------------------------------------------------------
  function sliceObject(obj, y) {
    const segs = [];
    const T = obj.tris;
    for (let i = 0; i < obj.nt; i++) {
      const o = i * 9;
      const P = [[T[o], T[o + 1], T[o + 2]], [T[o + 3], T[o + 4], T[o + 5]], [T[o + 6], T[o + 7], T[o + 8]]];
      const pts = [];
      for (let e = 0; e < 3; e++) {
        const a = P[e], b = P[(e + 1) % 3];
        const da = a[1] - y, dbb = b[1] - y;
        if ((da < 0 && dbb >= 0) || (da >= 0 && dbb < 0)) {
          const t = da / (da - dbb);
          pts.push([a[0] + (b[0] - a[0]) * t, a[2] + (b[2] - a[2]) * t]);
        }
      }
      if (pts.length === 2) segs.push([pts[0][0], pts[0][1], pts[1][0], pts[1][1]]);
    }
    return segs;
  }
  function pointInSegs(x, z, segs) {
    let inside = false;
    for (const s of segs) {
      const [x1, z1, x2, z2] = s;
      if ((z1 > z) !== (z2 > z)) {
        const xi = x1 + (z - z1) * (x2 - x1) / (z2 - z1);
        if (xi > x) inside = !inside;
      }
    }
    return inside;
  }

  // ------------------------------------------------------------------------------------------------
  // 2-D TMz FDTD (Ez, Hx, Hy) with graded absorbing layer and an oblique plane-wave line source
  // grid index i -> x, j -> z
  // ------------------------------------------------------------------------------------------------
  class FDTD2D {
    /**
     * opt: { N, dx, f, epsr:Float32Array, sigma:Float32Array, mur?:Float32Array, propDirXZ:[kx,kz], npml }
     */
    constructor(opt) {
      const N = this.N = opt.N, dx = this.dx = opt.dx;
      this.f = opt.f;
      this.dt = 0.99 * dx / (C0 * Math.SQRT2);
      this.t = 0; this.steps = 0;
      const npml = this.npml = opt.npml || 18;
      const n2 = N * N;
      this.Ez = new Float64Array(n2); this.Hx = new Float64Array(n2); this.Hy = new Float64Array(n2);   // Float64: avoids slow float32 denormals ahead of the wavefront
      this.Erms = new Float64Array(n2);
      this.ca = new Float64Array(n2); this.cb = new Float64Array(n2);
      this.da = new Float64Array(n2); this.db = new Float64Array(n2);
      const dt = this.dt;
      const smax = 0.8 * 4 / (ETA0 * dx);
      const prof = (i) => { const d = Math.max(npml - i, i - (N - 1 - npml), 0) / npml; return smax * d * d * d; };
      for (let j = 0; j < N; j++) for (let i = 0; i < N; i++) {
        const id = j * N + i;
        const er = opt.epsr ? opt.epsr[id] : 1, sg = opt.sigma ? opt.sigma[id] : 0, mr = opt.mur ? opt.mur[id] : 1;
        const sp = Math.max(prof(i), prof(j));
        const eps = er * EPS0, mu = mr * MU0;
        const s = sg + sp * er;
        const ae = s * dt / (2 * eps);
        this.ca[id] = (1 - ae) / (1 + ae);
        this.cb[id] = (dt / (eps * dx)) / (1 + ae);
        const sm = sp * mr * MU0 / EPS0;
        const am = sm * dt / (2 * mu);
        this.da[id] = (1 - am) / (1 + am);
        this.db[id] = (dt / (mu * dx)) / (1 + am);
      }
      // plane-wave source line: perpendicular to propagation direction, just inside the absorber
      const k = opt.propDirXZ; const kl = Math.hypot(k[0], k[1]) || 1;
      this.k = [k[0] / kl, k[1] / kl];
      const c = (N - 1) / 2;
      const r0 = (N / 2 - npml - 4);
      this.src = [];
      for (let j = npml; j < N - npml; j++) for (let i = npml; i < N - npml; i++) {
        const u = (i - c) * this.k[0] + (j - c) * this.k[1];       // along k
        if (Math.abs(u + r0) <= 0.5 * (Math.abs(this.k[0]) + Math.abs(this.k[1])) + 1e-9) {
          const v = -(i - c) * this.k[1] + (j - c) * this.k[0];    // along the line
          const half = N / 2 - npml - 2;
          const win = Math.abs(v) > half ? 0 : Math.pow(Math.cos(0.5 * Math.PI * Math.abs(v) / half), 0.5);
          this.src.push({ id: j * N + i, delay: (u + r0) * dx / C0, w: win });
        }
      }
      this.amp = 1;
    }
    step(nsteps) {
      const N = this.N, Ez = this.Ez, Hx = this.Hx, Hy = this.Hy, ca = this.ca, cb = this.cb, da = this.da, db = this.db;
      const w = 2 * Math.PI * this.f;
      const T = 1 / this.f;
      for (let s = 0; s < nsteps; s++) {
        for (let j = 0; j < N - 1; j++) {
          const row = j * N;
          for (let i = 0; i < N - 1; i++) {
            const id = row + i;
            Hx[id] = da[id] * Hx[id] - db[id] * (Ez[id + N] - Ez[id]);
            Hy[id] = da[id] * Hy[id] + db[id] * (Ez[id + 1] - Ez[id]);
          }
        }
        for (let j = 1; j < N - 1; j++) {
          const row = j * N;
          for (let i = 1; i < N - 1; i++) {
            const id = row + i;
            Ez[id] = ca[id] * Ez[id] + cb[id] * ((Hy[id] - Hy[id - 1]) - (Hx[id] - Hx[id - N]));
          }
        }
        this.t += this.dt; this.steps++;
        const ramp = Math.min(1, this.t / (3 * T));
        for (const sc of this.src) {
          const tt = this.t - sc.delay;
          if (tt > 0) Ez[sc.id] += this.amp * sc.w * ramp * Math.sin(w * tt) * 0.5;
        }
        // running mean-square after the transient (time constant ~ 2 periods)
        if (this.t > 4 * T) {
          const a = this.dt / (2 * T);
          const Er = this.Erms;
          for (let id = 0; id < Ez.length; id++) Er[id] += a * (Ez[id] * Ez[id] - Er[id]);
        }
      }
    }
  }

  // ------------------------------------------------------------------------------------------------
  // geometry helpers for tests / generic objects
  // ------------------------------------------------------------------------------------------------
  function boxTris(cx, cy, cz, sx, sy, sz) {
    const x0 = cx - sx / 2, x1 = cx + sx / 2, y0 = cy - sy / 2, y1 = cy + sy / 2, z0 = cz - sz / 2, z1 = cz + sz / 2;
    const v = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0], [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]];
    const f = [[0, 3, 2], [0, 2, 1], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [3, 7, 6], [3, 6, 2], [0, 4, 7], [0, 7, 3], [1, 2, 6], [1, 6, 5]];
    const out = [];
    for (const t of f) for (const k of t) out.push(...v[k]);
    return out;
  }

  const RF = {
    C0, EPS0, MU0, ETA0, KB, D2R, R2D,
    C, cadd, csub, cmul, cdiv, cabs, cabs2, carg, cexpj, csqrt, cscale, cconj,
    vadd, vsub, vscale, vdot, vcross, vlen, vnorm, vdist, vlerp,
    wrap360, wrap180, db10, undb, wToDbm, dbmToW, clamp, azOf, elOf, dirFromAz,
    mulberry32, randn, gammaSample,
    MATERIALS, makeMaterial, matProps, fresnel, fresnelAirTo, AIR_MEDIUM, medium,
    reflectField, transmitStraight, refractDir, reflectDir, interfaceBasis,
    makeObject, segmentChords, rayFirstHit, pointInside, propagateSegment,
    launchField, rxPolVector, knifeEdgeDb,
    makeEnv, tracePaths, channelSummary, groundMaterialAt,
    SwitchedBeamArray, beamPowers, measureBeams, pvmlEstimate,
    ucaSteer, ucaCovariance, arraySpectra, jacobiEig,
    AngleTracker, localize, noisePowerW,
    sliceObject, pointInSegs, FDTD2D, boxTris,
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = RF;
  else global.RF = RF;
})(typeof window !== 'undefined' ? window : globalThis);
