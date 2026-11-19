// Run with:  node tests/test_physics.js
'use strict';
const RF = require('../rf_physics.js');
let pass = 0, fail = 0;
function check(name, cond, info) {
  if (cond) { pass++; console.log('  PASS  ' + name + (info ? '  (' + info + ')' : '')); }
  else { fail++; console.log('  FAIL  ' + name + (info ? '  (' + info + ')' : '')); }
}
const near = (a, b, tol) => Math.abs(a - b) <= tol;
const f = 2.4e9, lam = RF.C0 / f;

console.log('\n[1] Fresnel coefficients');
{
  const m = RF.makeMaterial('air', { er: 4, sigma: 0 });
  const fr0 = RF.fresnelAirTo(m, f, 0);
  check('normal incidence  G = (1-n)/(1+n) = -1/3', near(fr0.gs.re, -1 / 3, 1e-9) && near(fr0.gp.re, -1 / 3, 1e-9), fr0.gs.re.toFixed(6));
  const thB = Math.atan(2) * RF.R2D;
  const frB = RF.fresnelAirTo(m, f, thB);
  check('Brewster angle (63.43 deg): |G_TM| = 0', RF.cabs(frB.gp) < 1e-9, RF.cabs(frB.gp).toExponential(2));
  const frG = RF.fresnelAirTo(m, f, 89.999);
  check('grazing incidence |G_TE| -> 1', near(RF.cabs(frG.gs), 1, 1e-3));
  const fr45 = RF.fresnelAirTo(m, f, 45);
  // n=2 at 45 deg: rs = (cos45 - 2cos20.7)/(cos45 + 2cos20.7) = -0.4514, rp = 0.2038
  check('45 deg: |G_TE| = 0.4514, |G_TM| = 0.2038', near(RF.cabs(fr45.gs), 0.4514, 2e-4) && near(RF.cabs(fr45.gp), 0.2038, 2e-4),
    RF.cabs(fr45.gs).toFixed(4) + ', ' + RF.cabs(fr45.gp).toFixed(4));
  check('Snell refraction angle at 45 deg = asin(sin45/2) = 20.70 deg', near(fr45.thetaT, 20.7048, 1e-3), fr45.thetaT.toFixed(4));
  const pec = RF.makeMaterial('pec');
  const fp = RF.fresnelAirTo(pec, f, 30);
  check('metal: |G| ~ 1 for both polarisations', near(RF.cabs(fp.gs), 1, 1e-3) && near(RF.cabs(fp.gp), 1, 1e-3));
}

console.log('\n[2] Lossy material properties');
{
  const w = RF.makeMaterial('water');
  const p = RF.matProps(w, f);
  check('water: n ~ 8.8, strongly lossy (alpha > 20 Np/m)', near(p.n.re, 8.8, 0.15) && p.alpha > 20, 'n=' + p.n.re.toFixed(3) + ' alpha=' + p.alpha.toFixed(1));
  const fol = RF.makeMaterial('foliage');
  const pf = RF.matProps(fol, f);
  check('foliage attenuation 0.5..3 dB/m (ITU-R P.833 order of magnitude)', pf.dbPerM > 0.5 && pf.dbPerM < 3, pf.dbPerM.toFixed(2) + ' dB/m');
  const wood = RF.makeMaterial('wood_live');
  const pw = RF.matProps(wood, f);
  check('live wood is strongly attenuating (> 20 dB/m)', pw.dbPerM > 20, pw.dbPerM.toFixed(1) + ' dB/m');
}

console.log('\n[3] Exact segment / mesh intersection and penetration loss');
{
  const mat = RF.makeMaterial('granite');
  const box = RF.makeObject({ id: 'b', kind: 'rock', mat, tris: RF.boxTris(0, 1, 0, 2, 2, 2) });
  const ch = RF.segmentChords([box], [-5, 1, 0.1], [5, 1, 0.1]);
  check('one chord of length 2 m through a 2 m cube', ch.length === 1 && near(ch[0].len, 2, 1e-9), ch.length && ch[0].len.toFixed(6));
  const ch2 = RF.segmentChords([box], [0, 1, 0], [5, 1, 0]);
  check('segment starting inside -> chord of 1 m with no entry face', ch2.length === 1 && near(ch2[0].len, 1, 1e-9) && ch2[0].n0 === null);
  check('pointInside', RF.pointInside(box, [0.3, 1.2, -0.4]) && !RF.pointInside(box, [3, 1, 0]));
  const env = RF.makeEnv({ f, objects: [box] });
  const E0 = RF.launchField(1, 'V', [1, 0, 0]);
  const seg = RF.propagateSegment(env, [-5, 1, 0.1], [5, 1, 0.1], E0, null);
  const p = RF.matProps(mat, f);
  const fr = RF.fresnelAirTo(mat, f, 0);
  const expected = 2 * -10 * Math.log10(1 - RF.cabs2(fr.gs)) + 8.6859 * p.alpha * 2;
  check('penetration loss = 2 x interface + alpha L', near(seg.lossDb, expected, 1e-3), seg.lossDb.toFixed(3) + ' dB vs ' + expected.toFixed(3));
}

console.log('\n[4] Two-ray ground reflection versus the analytical formula');
{
  const g = RF.makeMaterial('soil_moist');
  const env = RF.makeEnv({ f, objects: [], groundMat: g, groundRough: 0, en: { direct: true, ground: true, penetration: true } });
  for (const pol of ['H', 'V']) {
    const tx = { pos: [0, 10, 0], ptW: 1, pol }, rx = { pos: [40, 2, 0], pol };
    const paths = RF.tracePaths(env, tx, rx);
    const d = paths.find(x => x.type === 'direct'), gr = paths.find(x => x.type === 'ground');
    const r1 = Math.hypot(40, 8), r2 = Math.hypot(40, 12);
    const th = Math.atan2(40, 12) * RF.R2D;
    const fr = RF.fresnelAirTo(g, f, th);
    const G = pol === 'H' ? fr.gs : fr.gp;
    check(`${pol}-pol: ground path length = image distance`, near(gr.length, r2, 1e-9));
    const ratio = RF.cabs(gr.amp) / RF.cabs(d.amp);
    check(`${pol}-pol: reflection magnitude in (0,1)`, ratio > 0 && ratio < 1, ratio.toFixed(3));
  }
  // H-pol with dipole along Z (perpendicular to the X-Y plane of incidence) -> pure TE: exact check
  {
    const tx = { pos: [0, 10, 0], ptW: 1, pol: 'V' }, rx = { pos: [40, 2, 0], pol: 'V' };
    // rotate geometry so that the propagation plane is X-Y and the 'H' dipole (X axis) is replaced: use path along Z
    const txz = { pos: [0, 10, 0], ptW: 1, pol: 'H' }, rxz = { pos: [0, 2, 40], pol: 'H' };
    const paths = RF.tracePaths(env, txz, rxz);
    const d = paths.find(x => x.type === 'direct'), gr = paths.find(x => x.type === 'ground');
    const r1 = Math.hypot(40, 8), r2 = Math.hypot(40, 12);
    const th = Math.atan2(40, 12) * RF.R2D;
    const fr = RF.fresnelAirTo(g, f, th);
    const expected = RF.cabs(fr.gs) * r1 / r2;
    const ratio = RF.cabs(gr.amp) / RF.cabs(d.amp);
    check('pure TE geometry: |A_ground|/|A_direct| = |G_TE| r1/r2', near(ratio, expected, 1e-6), ratio.toFixed(5) + ' vs ' + expected.toFixed(5));
    const dphi = RF.carg(RF.cdiv(gr.amp, d.amp));
    const exph = RF.carg(RF.cmul(fr.gs, RF.cexpj(-2 * Math.PI / lam * (r2 - r1))));
    check('pure TE geometry: phase difference = arg(G) - k (r2 - r1)', near(Math.cos(dphi - exph), 1, 1e-6));
    void tx; void rx;
  }
}

console.log('\n[5] Facet specular reflection (image method)');
{
  const mat = RF.makeMaterial('granite');
  // big vertical wall at x = 10 (thin box), facing -X
  const wall = RF.makeObject({ id: 'w', kind: 'building', mat, tris: RF.boxTris(10.25, 5, 0, 0.5, 10, 30) });
  const env = RF.makeEnv({ f, objects: [wall], en: { direct: true, ground: false, specular: true, penetration: true } });
  const tx = { pos: [0, 4, -5], ptW: 1, pol: 'V' }, rx = { pos: [2, 4, 5], pol: 'V' };
  const paths = RF.tracePaths(env, tx, rx);
  const sp = paths.find(p => p.type === 'specular');
  const img = [20, 4, -5];
  check('specular path found on wall face', !!sp);
  if (sp) {
    check('path length = |image - rx|', near(sp.length, RF.vdist(img, rx.pos), 1e-9), sp.length.toFixed(4));
    check('reflection point on the x = 10 face', near(sp.points[1][0], 10, 1e-9));
    check('angle of incidence equals angle of reflection', (() => {
      const P = sp.points[1], n = [-1, 0, 0];
      const a1 = Math.acos(RF.vdot(RF.vnorm(RF.vsub(tx.pos, P)), n)), a2 = Math.acos(RF.vdot(RF.vnorm(RF.vsub(rx.pos, P)), n));
      return near(a1, a2, 1e-9);
    })());
  }
}

console.log('\n[6] Knife-edge diffraction (ITU-R P.526)');
check('J(0) = 6.03 dB', near(RF.knifeEdgeDb(0), 6.03, 0.02), RF.knifeEdgeDb(0).toFixed(3));
check('J(-1) = 0 dB', RF.knifeEdgeDb(-1) === 0);
check('J(2.4) ~ 20.6 dB', near(RF.knifeEdgeDb(2.4), 20.6, 0.3), RF.knifeEdgeDb(2.4).toFixed(2));

console.log('\n[7] PV-ML estimator (switched-beam power vector)');
{
  const arr = new RF.SwitchedBeamArray(6);
  const rng = RF.mulberry32(3);
  let errs = [];
  for (let t = 0; t < 200; t++) {
    const th = rng() * 360;
    const g = arr.gain(th);
    const m = Array.from(g, gi => RF.undb(15) * gi + 1);
    const p = RF.measureBeams(m, 64, rng);
    const e = RF.pvmlEstimate(arr, p, 64);
    errs.push(RF.wrap180(e.theta - th));
  }
  const rmse = Math.sqrt(errs.reduce((s, e) => s + e * e, 0) / errs.length);
  check('PV-ML RMSE < 3 deg at 15 dB SNR, 6 beams, L=64', rmse < 3, rmse.toFixed(2) + ' deg');
  const g = arr.gain(123.4);
  const e = RF.pvmlEstimate(arr, Array.from(g, gi => 1000 * gi + 1), 64);
  check('PV-ML noiseless estimate exact', near(e.theta, 123.4, 0.05), e.theta.toFixed(3));
}

console.log('\n[8] MUSIC / Bartlett on the coherent UCA');
{
  const rng = RF.mulberry32(5);
  const path = { coherent: true, amp: RF.C(Math.sqrt(1e-9 * 10)), powerW: 1e-8, az: 77, el: 0 };
  const R = RF.ucaCovariance(8, [path], [], 1e-9, 400, rng);
  const sp = RF.arraySpectra(R, 1);
  check('MUSIC peak within 1 deg', Math.abs(RF.wrap180(sp.musicPeak - 77)) < 1, sp.musicPeak.toFixed(2));
  check('Bartlett peak within 2 deg', Math.abs(RF.wrap180(sp.bartlettPeak - 77)) < 2, sp.bartlettPeak.toFixed(2));
  const ev = RF.jacobiEig([4, 1, 1, 3], 2).vals.sort();
  check('Jacobi eigenvalues of [[4,1],[1,3]]', near(ev[0], 3.5 - Math.sqrt(1.25), 1e-9) && near(ev[1], 3.5 + Math.sqrt(1.25), 1e-9));
}

console.log('\n[9] Multi-receiver localisation');
{
  const drone = [12, -7];
  const st = [[-30, 0], [30, 10], [0, 35]].map(([x, z]) => ({ x, z, az: RF.azOf([drone[0] - x, 0, drone[1] - z]), sigma: 2 }));
  const L = RF.localize(st);
  check('noise-free bearings intersect at the true position', L.valid && near(L.x, 12, 1e-6) && near(L.z, -7, 1e-6), L.x.toFixed(4) + ', ' + L.z.toFixed(4));
  const one = RF.localize(st.slice(0, 1));
  check('one receiver gives a bearing only (no position)', !one.valid);
}

console.log('\n[10] Kalman bearing tracker');
{
  const tr = new RF.AngleTracker(4);
  const rng = RF.mulberry32(9);
  let o;
  for (let k = 0; k < 80; k++) { const truth = 350 + 2 * k * 0.2; o = tr.step(RF.wrap360(truth + 3 * RF.randn(rng)), 3, 0.2); }
  const truth = RF.wrap360(350 + 2 * 79 * 0.2);
  check('tracks through the 360/0 wrap with error < 3 deg', Math.abs(RF.wrap180(o.angle - truth)) < 3, RF.wrap180(o.angle - truth).toFixed(2));
}

console.log('\n[11] 2-D FDTD');
{
  const N = 200, dx = lam / 15;
  const sim = new RF.FDTD2D({ N, dx, f, propDirXZ: [1, 0], npml: 16 });
  sim.step(900);
  let finite = true, mx = 0;
  for (const v of sim.Ez) { if (!isFinite(v)) finite = false; mx = Math.max(mx, Math.abs(v)); }
  check('stable (finite, bounded field after 900 steps)', finite && mx < 10, 'max |Ez| = ' + mx.toFixed(3));
  // wavelength from zero crossings along the centre row
  const row = 100 * N; let zc = [];
  for (let i = 60; i < 150; i++) if (Math.sign(sim.Ez[row + i]) !== Math.sign(sim.Ez[row + i + 1])) zc.push(i);
  const lamCells = zc.length > 2 ? 2 * (zc[zc.length - 1] - zc[0]) / (zc.length - 1) : 0;
  check('simulated wavelength = 15 cells (+/- 5 %)', near(lamCells, 15, 0.75), lamCells.toFixed(2) + ' cells');
  // dielectric slab: wavelength inside shortens by sqrt(er)
  const epsr = new Float32Array(N * N).fill(1);
  for (let j = 0; j < N; j++) for (let i = 110; i < 170; i++) epsr[j * N + i] = 4;
  const s2 = new RF.FDTD2D({ N, dx, f, propDirXZ: [1, 0], npml: 16, epsr });
  s2.step(1400);
  zc = [];
  for (let i = 115; i < 165; i++) if (Math.sign(s2.Ez[row + i]) !== Math.sign(s2.Ez[row + i + 1])) zc.push(i);
  const lamIn = zc.length > 2 ? 2 * (zc[zc.length - 1] - zc[0]) / (zc.length - 1) : 0;
  check('wavelength inside eps_r = 4 slab = 7.5 cells (refraction / slow wave)', near(lamIn, 7.5, 0.6), lamIn.toFixed(2) + ' cells');
}

console.log('\n[12] Full trace in a small forest scene');
{
  const wood = RF.makeMaterial('wood_live');
  const trunk = RF.makeObject({ id: 't', kind: 'trunk', mat: wood, tris: RF.boxTris(15, 3, 0, 0.5, 6, 0.5) });
  const rock = RF.makeObject({ id: 'r', kind: 'rock', mat: RF.makeMaterial('granite'), tris: RF.boxTris(25, 0.8, 6, 2, 1.6, 2) });
  const env = RF.makeEnv({ f, objects: [trunk, rock] });
  const t0 = Date.now();
  let paths;
  for (let k = 0; k < 20; k++) paths = RF.tracePaths(env, { pos: [0, 3, 0], ptW: 0.1, pol: 'V' }, { pos: [30, 3, 0], pol: 'V' });
  const ms = (Date.now() - t0) / 20;
  const types = [...new Set(paths.map(p => p.type))];
  const d = paths.find(p => p.type === 'direct');
  check('direct path blocked by the trunk is classified NLOS', d.hardBlocked && RF.channelSummary(paths).state === 'NLOS');
  check('diffraction paths exist around the trunk', types.includes('diffraction'), types.join(', '));
  check('ground reflection exists', types.includes('ground'));
  check('trace is fast enough for real time (< 20 ms)', ms < 20, ms.toFixed(2) + ' ms');
}

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
