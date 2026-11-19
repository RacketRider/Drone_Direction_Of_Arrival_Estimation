import numpy as np, json
from sim_core import *
rng = np.random.default_rng(2026)
res = {}
HOPS = {'433.0':433.0e6, '868.0':868.0e6, '902.0':902.0e6, '915.0':915.0e6, '928.0':928.0e6}
# ---------- Table I: hop benchmark at 15 dB, theta=35
T = 600; rows = []
for name, f in HOPS.items():
    th = np.full(T, np.deg2rad(35.0)); foff = rng.uniform(-20e3, 20e3, T)
    y = make_switched(rng, T, 15, f, th, foff)
    fc, fr = freq_estimate(y)
    X = snapshots(y, fr); R = cov(X)
    est_prop = music(R, f+fr)
    est_stat = music(R, np.full(T, F0_STATIC))
    e_p = wrap(est_prop-35); e_s = wrap(est_stat-35)
    rows.append(dict(f=name, stat_mean=float(np.mean(est_stat)), stat_err=float(np.mean(e_s)), stat_rmse=float(np.sqrt(np.mean(e_s**2))),
                     prop_mean=float(np.mean(est_prop)), prop_rmse=float(np.sqrt(np.mean(e_p**2))), prop_bias=float(np.mean(e_p))))
res['hops'] = rows
for r in rows: print(r)
# ---------- bias vs frequency sweep (high SNR) & spectra at 915
fs_sweep = np.arange(430, 931, 10)*1e6; bias = []
for f in fs_sweep:
    T = 100; th = np.full(T, np.deg2rad(35.0)); foff = rng.uniform(-20e3, 20e3, T)
    y = make_switched(rng, T, 25, f, th, foff); fc, fr = freq_estimate(y)
    R = cov(snapshots(y, fr))
    bias.append(float(np.mean(wrap(music(R, np.full(T, F0_STATIC))-35))))
res['bias_f'] = dict(f=(fs_sweep/1e6).tolist(), bias=bias)
# spectrum example at 915 MHz, 15 dB
T = 1; f = 915e6
y = make_switched(rng, T, 15, f, np.array([np.deg2rad(35.)]), np.array([8e3])); fc, fr = freq_estimate(y)
R = cov(snapshots(y, fr)); w, v = eig(R); En = v[:, :, 1:]
def spec(fst):
    A = steer(np.full(len(GRID), fst), GRID); pr = A.conj()@En[0]
    return 1/np.sum(np.abs(pr)**2, axis=1)
np.savez('spectra.npz', th=np.rad2deg(GRID), comp=spec(f+fr[0]), stat=spec(F0_STATIC))
# ---------- RMSE vs SNR
snrs = np.arange(-10, 31, 5); f = 915e6; T = 400
curves = {k: [] for k in ['proposed', 'fftonly', 'noderot', 'static', 'ideal']}
fe = {'coarse': [], 'fine': []}
algos = {'MUSIC': music, 'Bartlett': bartlett, 'Capon': capon, 'Interf-LS': interf}
alg_rmse = {k: [] for k in algos}; crb = []
for s in snrs:
    th = rng.uniform(0, 2*np.pi, T); foff = rng.uniform(-20e3, 20e3, T); thd = np.rad2deg(th)
    y = make_switched(rng, T, s, f, th, foff); fc, fr = freq_estimate(y)
    fe['coarse'].append(float(np.sqrt(np.mean((fc-foff)**2)))); fe['fine'].append(float(np.sqrt(np.mean((fr-foff)**2))))
    rm = lambda est: float(np.sqrt(np.mean(wrap(est-thd)**2)))
    Rp = cov(snapshots(y, fr))
    curves['proposed'].append(rm(music(Rp, f+fr)))
    curves['static'].append(rm(music(Rp, np.full(T, F0_STATIC))))
    Rc = cov(snapshots(y, fc)); curves['fftonly'].append(rm(music(Rc, f+fc)))
    Rn = cov(snapshots(y, fr, derotate=False)); curves['noderot'].append(rm(music(Rn, f+fr)))
    # ideal coherent 4-channel
    sk = bpsk(rng, T)[:, ::M]*np.exp(1j*rng.uniform(0, 2*np.pi, (T, 1)))
    Xi = 10**(s/20)*steer(f+foff, th)[:, :, None]*sk[:, None, :]+noise(rng, (T, M, NSNAP))
    curves['ideal'].append(rm(music(cov(Xi), f+foff)))
    for k, fn in algos.items(): alg_rmse[k].append(rm(fn(Rp, f+fr)))
    crb.append(float(np.sqrt(np.mean(crb_deg(s, th, f+foff)**2))))
    print(s, {k: round(v[-1], 2) for k, v in curves.items()}, round(crb[-1], 2), {k: round(v[-1], 2) for k, v in alg_rmse.items()})
res.update(snrs=snrs.tolist(), curves=curves, fe=fe, alg=alg_rmse, crb=crb)
json.dump(res, open('res_main.json', 'w'), indent=1)
