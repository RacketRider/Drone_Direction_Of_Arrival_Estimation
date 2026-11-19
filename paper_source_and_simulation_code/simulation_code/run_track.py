import numpy as np, json
from sim_core import *
rng = np.random.default_rng(11)
f = 915e6; dt = 0.1; K = 600; t = np.arange(K)*dt
true = (30+2.5*t) % 360
urban = ((t > 15) & (t < 25)) | ((t > 40) & (t < 48))
def burst(thd, mp_on):
    T = len(thd); th = np.deg2rad(thd); foff = rng.uniform(-20e3, 20e3, T)
    rho = np.where(mp_on, rng.uniform(0.4, 0.9, T), 0.0); c = np.where(mp_on, rng.uniform(0.0, 0.9, T), 0.0)
    thr = th+np.deg2rad(rng.uniform(25, 335, T))
    y = make_switched(rng, T, 12, f, th, foff, (rho, c, thr)); fc, fr = freq_estimate(y)
    R = cov(snapshots(y, fr)); w, v = eig(R)
    return music(R, f+fr), w[:, 0]/w[:, 1]
def run(seed_mp):
    mp_on = urban & (rng.random(K) < 0.6)
    est, gam = burst(true, mp_on)
    return est, gam, mp_on
def ckf(z, accept, sig=1.0, q=0.05):
    x = np.array([z[0], 0.0]); P = np.diag([4.0, 4.0]); out = []
    F = np.array([[1, dt], [0, 1]]); Q = q*np.array([[dt**3/3, dt**2/2], [dt**2/2, dt]]); H = np.array([[1.0, 0.0]])
    for k in range(len(z)):
        x = F@x; x[0] %= 360; P = F@P@F.T+Q
        if accept[k]:
            nu = wrap(z[k]-x[0]); S = H@P@H.T+sig**2; Kg = P@H.T/S
            x = x+(Kg*nu).ravel(); x[0] %= 360; P = (np.eye(2)-Kg@H)@P
        out.append(x[0])
    return np.array(out)
rm = lambda a: float(np.sqrt(np.mean(wrap(a-true)**2)))
agg = {k: [] for k in ['raw', 'gated_hold', 'kf_all', 'kf_gate', 'kf_innov']}
for rep in range(40):
    est, gam, mp_on = run(rep); acc = gam >= 8.0
    # gate-hold: hold last accepted estimate
    hold = est.copy(); last = est[0]
    for k in range(K):
        if acc[k]: last = est[k]
        hold[k] = last
    # KF with innovation (chi-square-like 3-sigma) gating only
    kf_in = []; x = est[0]
    agg['raw'].append(rm(est)); agg['gated_hold'].append(rm(hold))
    agg['kf_all'].append(rm(ckf(est, np.ones(K, bool)))); agg['kf_gate'].append(rm(ckf(est, acc)))
    if rep == 0: ex = dict(t=t.tolist(), true=true.tolist(), est=est.tolist(), acc=acc.tolist(), kf_gate=ckf(est, acc).tolist(), kf_all=ckf(est, np.ones(K, bool)).tolist(), mp=mp_on.tolist())
summ = {k: [float(np.mean(v)), float(np.std(v))] for k, v in agg.items() if v}
print(summ)
res = dict(summary=summ, example=ex)
# --- triangulation / GDOP
st = np.array([[0, 0], [120, 0], [60, 110.]]); tgt = np.array([75., 45.]); sig = np.deg2rad(1.0)
def jac(p):
    d = p[None]-st; r2 = np.sum(d**2, axis=1)+1e-9
    return np.stack([-d[:, 1]/r2, d[:, 0]/r2], axis=1)
def wls(b, p0, w=None):
    p = p0.copy()
    for _ in range(10):
        d = p[None]-st; pred = np.arctan2(d[:, 1], d[:, 0]); res_ = np.arctan2(np.sin(b-pred), np.cos(b-pred))
        H = jac(p); dp = np.linalg.lstsq(H, res_, rcond=None)[0]; p = p+dp
    return p
bt = np.arctan2(tgt[1]-st[:, 1], tgt[0]-st[:, 0])
pts = np.array([wls(bt+rng.normal(0, sig, 3), np.array([60., 60.])) for _ in range(2000)])
H = jac(tgt); Cp = np.linalg.inv(H.T@H)*sig**2
rmse_mc = float(np.sqrt(np.mean(np.sum((pts-tgt)**2, axis=1)))); gd_t = float(np.sqrt(np.trace(np.linalg.inv(H.T@H))))
xs = np.linspace(1, 119, 60); ys = np.linspace(1, 119, 60); G = np.zeros((len(ys), len(xs)))
for i, y_ in enumerate(ys):
    for j, x_ in enumerate(xs):
        Hh = jac(np.array([x_, y_])); G[i, j] = min(np.sqrt(np.trace(np.linalg.inv(Hh.T@Hh+1e-12*np.eye(2)))), 400)
res['tri'] = dict(stations=st.tolist(), target=tgt.tolist(), pts=pts[:400].tolist(), cov=Cp.tolist(), rmse_mc=rmse_mc, gdop_target=gd_t,
                  rms_theory=float(np.sqrt(np.trace(Cp))), xs=xs.tolist(), ys=ys.tolist(), G=G.tolist())
print('tri rmse mc', rmse_mc, 'theory', res['tri']['rms_theory'], 'gdop@tgt (m/rad)', gd_t, 'median GDOP map', float(np.median(G)))
json.dump(res, open('res_track.json', 'w'))
