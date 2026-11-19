import numpy as np, json
import sim_core as sc
from sim_core import *
rng = np.random.default_rng(7)
res = {}
ths = np.arange(0, 360, 3.0)
# ---- bias vs radius (noiseless, static cal at 433 MHz)
radii = np.arange(0.04, 0.401, 0.01); out = {}
for f in [868e6, 915e6]:
    mx = []
    for r in radii:
        sc.R_ARR = r; b = []
        for t in ths:
            a = sc.steer(f, np.deg2rad(t)); R = np.outer(a, a.conj())[None]
            est = sc.music(R+1e-9*np.eye(4)[None], np.array([433e6]))[0]; b.append(abs(sc.wrap(est-t)))
        mx.append(float(np.percentile(b, 95)))
    out[str(int(f/1e6))] = mx
sc.R_ARR = 0.072
res['bias_radius'] = dict(r_cm=(radii*100).tolist(), **out)
# ---- bias vs frequency (noiseless), rms over theta, r=7.2
fsw = np.arange(430, 931, 10)*1e6; rms = []; p95 = []
for f in fsw:
    b = []
    for t in ths:
        a = steer(f, np.deg2rad(t)); R = np.outer(a, a.conj())[None]
        b.append(wrap(music(R+1e-9*np.eye(4)[None], np.array([433e6]))[0]-t))
    b = np.array(b); rms.append(float(np.sqrt(np.mean(b**2)))); p95.append(float(np.max(np.abs(b))))
res['bias_freq'] = dict(f=(fsw/1e6).tolist(), rms=rms, maxabs=p95)
# ---- pseudospectra at 915, 15 dB (single burst)
f = 915e6; t0 = 35.0
y = make_switched(rng, 1, 15, f, np.array([np.deg2rad(t0)]), np.array([8e3]))
fc, fr = freq_estimate(y); print('freq err', fr-8e3)
def spec(R, fst):
    w, v = eig(R); En = v[0][:, 1:]
    A = steer(np.full(len(GRID), fst), GRID); return 1/np.sum(np.abs(A.conj()@En)**2, axis=1)
Rp = cov(snapshots(y, fr)); Rn = cov(snapshots(y, fr, derotate=False))
np.savez('spectra.npz', th=np.rad2deg(GRID), prop=spec(Rp, f+fr[0]), stat=spec(Rp, F0_STATIC), nod=spec(Rn, f+fr[0]))
# ---- gate: gamma vs SNR (LoS)
snrs = np.arange(-10, 31, 2.5); g = {'med': [], 'p10': [], 'p90': [], 'frej': []}; T = 600
for s in snrs:
    th = rng.uniform(0, 2*np.pi, T); foff = rng.uniform(-20e3, 20e3, T)
    y = make_switched(rng, T, s, f, th, foff); fc, fr = freq_estimate(y)
    w, v = eig(cov(snapshots(y, fr))); gam = w[:, 0]/w[:, 1]
    g['med'].append(float(np.median(gam))); g['p10'].append(float(np.percentile(gam, 10))); g['p90'].append(float(np.percentile(gam, 90)))
    g['frej'].append(float(np.mean(gam < 8.0)))
res['gamma_snr'] = dict(snr=snrs.tolist(), **g)
print('false reject by SNR', dict(zip(snrs.tolist(), g['frej'])))
# ---- gate: reject prob vs coherence c for rho values at 15 dB
cs = np.array([0, .2, .4, .6, .8, .9, .95, .98, 1.0]); rhos = [0.3, 0.6, 0.9]; pr = {}
def mp_run(T, s, rho, c, algs=True):
    th = rng.uniform(0, 2*np.pi, T); thd = np.rad2deg(th)
    thr = th+np.deg2rad(rng.uniform(25, 335, T))
    foff = rng.uniform(-20e3, 20e3, T)
    mp = (np.full(T, rho), np.full(T, c), thr)
    y = make_switched(rng, T, s, f, th, foff, mp); fc, fr = freq_estimate(y)
    R = cov(snapshots(y, fr)); w, v = eig(R); gam = w[:, 0]/w[:, 1]
    return thd, R, fr, gam
for rho in rhos:
    pr[str(rho)] = []
    for c in cs:
        thd, R, fr, gam = mp_run(600, 15, rho, c); pr[str(rho)].append(float(np.mean(gam < 8.0)))
res['rej_vs_c'] = dict(c=cs.tolist(), **pr)
print(res['rej_vs_c'])
# ---- table: algorithms under conditions
conds = [('LoS only', 0.0, 0.0), ('Weak reflection (-10.5 dB), partially coh.', 0.3, 0.5), ('Moderate refl. (-4.4 dB), decorrelated', 0.6, 0.0),
         ('Moderate refl. (-4.4 dB), partially coh.', 0.6, 0.6), ('Strong refl. (-0.9 dB), partially coh.', 0.9, 0.6), ('Moderate refl. (-4.4 dB), fully coherent', 0.6, 1.0)]
tab = []
for name, rho, c in conds:
    T = 1000
    if rho == 0:
        th = rng.uniform(0, 2*np.pi, T); thd = np.rad2deg(th); foff = rng.uniform(-20e3, 20e3, T)
        y = make_switched(rng, T, 15, f, th, foff); fc, fr = freq_estimate(y)
        R = cov(snapshots(y, fr)); w, v = eig(R); gam = w[:, 0]/w[:, 1]
    else:
        thd, R, fr, gam = mp_run(T, 15, rho, c)
    acc = gam >= 8.0; fs_ = f+fr
    rm = lambda est, m=slice(None): float(np.sqrt(np.mean(wrap(est-thd)[m]**2))) if np.any(np.arange(T)[m] >= 0) else float('nan')
    ests = {k: fn(R, fs_) for k, fn in {'MUSIC': music, 'Bartlett': bartlett, 'Capon': capon, 'Interf-LS': interf}.items()}
    row = dict(name=name, rej=float(np.mean(~acc)), gam_med=float(np.median(gam)))
    for k, e in ests.items(): row[k] = rm(e)
    row['MUSIC_gated'] = float(np.sqrt(np.mean(wrap(ests['MUSIC']-thd)[acc]**2))) if acc.any() else float('nan')
    big = np.abs(wrap(ests['MUSIC']-thd)) > 5.0
    row['out_all'] = float(np.mean(big)); row['out_acc'] = float(np.mean(big[acc])) if acc.any() else float('nan')
    row['det_big'] = float(np.mean(~acc[big])) if big.any() else float('nan')
    tab.append(row); print(row)
res['gate_table'] = tab
json.dump(res, open('res_more.json', 'w'), indent=1)
