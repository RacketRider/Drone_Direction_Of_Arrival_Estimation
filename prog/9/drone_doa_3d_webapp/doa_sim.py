"""
doa_sim.py - simulation library for low-cost drone Direction-of-Arrival (DoA) estimation.

System under study (azimuth only)
---------------------------------
* SwitchedBeamArray : N directional antennas, boresights spaced 360/N deg, ONE receiver behind an
                      RF switch. Only the received POWER of each beam is available (no phase).
* CircularArray     : N omni elements on a ring (half-wavelength spacing) with N coherent channels.
                      Needed by MUSIC / ESPRIT, which use phase. Costs N receive chains, so it is the
                      "expensive" comparison method, not a like-for-like hardware option.

Estimators
----------
Switched-beam (power only): strongest beam, power centroid, power-vector ML (pattern fit, with an
                            uncertainty estimate and a goodness-of-fit statistic).
Circular array (phase)    : MUSIC (grid + parabolic refinement), UCA-ESPRIT (phase-mode / beamspace).
Tracking                  : AngleTracker - Kalman filter on [angle, rate] with adaptive measurement
                            noise (from the estimator's own uncertainty), innovation gating, adaptive
                            process noise, re-acquisition, and a confidence score.

Conventions
-----------
Angles in degrees. Noise power is normalised to 1 (sigma2 = 1). "SNR" everywhere means the SNR at an
ISOTROPIC (0 dBi) element: switched-beam antennas then add their own directional gain on top, which is
physically what makes them competitive with a coherent array. Time budget is matched: the switched
array dwells L samples on each of N beams, the circular array takes K = N*L snapshots in parallel.

Simplifications (state these in the report):
* Gaussian signal model (drone video/telemetry is noise-like over a dwell).
* Per-dwell independent Rician fading on the switched array (worst case: the channel changes between
  dwells). Circular array: fading is a common scale factor per snapshot and does not affect MUSIC.
* Ideal 3GPP-style beam pattern with a flat sidelobe floor; hardware errors are added separately.
* Noise floor is assumed calibrated (known).
"""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np
from scipy.special import jv
from scipy.stats import chi2

# --------------------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------------------

def wrap180(x):
    return (np.asarray(x, dtype=float) + 180.0) % 360.0 - 180.0


def wrap360(x):
    return np.asarray(x, dtype=float) % 360.0


def undb(x):
    return 10.0 ** (np.asarray(x, dtype=float) / 10.0)


def db(x):
    return 10.0 * np.log10(x)


def cn(rng, shape):
    """Circular complex Gaussian, unit variance."""
    return (rng.standard_normal(shape) + 1j * rng.standard_normal(shape)) / np.sqrt(2.0)


def _b(x, B):
    x = np.asarray(x, dtype=float)
    return np.broadcast_to(x, (B,)) if x.ndim == 0 else x


def _parab(y0, y1, y2):
    """Parabolic interpolation around a grid minimum. Returns (offset in grid steps, 2nd difference)."""
    den = y0 - 2.0 * y1 + y2
    safe = np.where(den > 1e-12, den, np.inf)
    delta = np.clip(0.5 * (y0 - y2) / safe, -1.0, 1.0)
    return delta, den


def metrics(err_deg, fail_thr=15.0):
    e = np.abs(np.asarray(err_deg, dtype=float))
    e = e[np.isfinite(e)]
    return dict(mae=float(e.mean()), rmse=float(np.sqrt((e ** 2).mean())), median=float(np.median(e)),
                p95=float(np.percentile(e, 95)), fail=float((e > fail_thr).mean()), n=int(e.size))


def conf_from_sigma(sig_deg, scale=10.0):
    """Map an angular standard deviation to a 0..1 confidence (0.88 @5deg, 0.61 @10deg, 0.14 @20deg)."""
    return np.exp(-0.5 * (np.asarray(sig_deg, dtype=float) / scale) ** 2)


# --------------------------------------------------------------------------------------------------
# array models
# --------------------------------------------------------------------------------------------------

@dataclass
class SwitchedBeamArray:
    """N directional antennas. Pattern: 3GPP-style parabolic main lobe, flat sidelobe floor.

    bw_scale sets the 3 dB beamwidth as a multiple of the beam spacing (1.15 -> ~2.3 dB crossover loss).
    Peak gain follows the beamwidth (square-beam approximation, 65 % efficiency)."""
    n: int = 6
    bw_scale: float = 1.15
    sidelobe_db: float = 20.0
    efficiency: float = 0.65
    bw_deg: float = field(init=False)
    boresights: np.ndarray = field(init=False)
    g0: float = field(init=False)

    def __post_init__(self):
        spacing = 360.0 / self.n
        self.bw_deg = self.bw_scale * spacing
        self.boresights = spacing * np.arange(self.n)
        self.g0 = max(1.0, self.efficiency * 41253.0 / self.bw_deg ** 2)

    def gain(self, theta, boresights=None):
        """Linear gain (relative to isotropic) of every beam toward theta. theta: (B,) or (B,N) -> (B,N)."""
        b = self.boresights if boresights is None else boresights
        th = np.asarray(theta, dtype=float)
        if th.ndim == 1:
            th = th[:, None]
        d = wrap180(th - b)
        a_db = -np.minimum(12.0 * (d / self.bw_deg) ** 2, self.sidelobe_db)
        return self.g0 * undb(a_db)

    def perturbed(self, B, rng, gain_err_db=0.0, point_err_deg=0.0):
        """Draw per-trial hardware errors (true boresights, true gain multipliers)."""
        bs = self.boresights + point_err_deg * rng.standard_normal((B, self.n))
        gm = undb(gain_err_db * rng.standard_normal((B, self.n)))
        return bs, gm


@dataclass
class CircularArray:
    """Uniform circular array of omni elements, spacing `spacing_wl` wavelengths between neighbours."""
    n: int = 6
    spacing_wl: float = 0.5
    kr: float = field(init=False)
    gam: np.ndarray = field(init=False)

    def __post_init__(self):
        radius_wl = self.spacing_wl / (2.0 * np.sin(np.pi / self.n))
        self.kr = 2.0 * np.pi * radius_wl
        self.gam = 2.0 * np.pi * np.arange(self.n) / self.n

    def steering(self, phi_deg):
        phi = np.deg2rad(np.asarray(phi_deg, dtype=float))[..., None]
        return np.exp(1j * self.kr * np.cos(phi - self.gam))


# --------------------------------------------------------------------------------------------------
# signal simulation
# --------------------------------------------------------------------------------------------------

def _rician(rng, shape, k_db):
    """Complex channel gain with unit mean power. k_db=+inf: no fading, -inf: Rayleigh."""
    if k_db is None or k_db == np.inf:
        return np.ones(shape, dtype=complex)
    if k_db == -np.inf:
        return cn(rng, shape)
    K = undb(k_db)
    return np.sqrt(K / (K + 1.0)) + cn(rng, shape) / np.sqrt(K + 1.0)


def expected_power(arr: SwitchedBeamArray, theta, snr_db, sigma2=1.0):
    """Noise-free, fading-free expected per-beam power."""
    th = np.asarray(theta, dtype=float)
    B = th.shape[0]
    return undb(_b(snr_db, B))[:, None] * sigma2 * arr.gain(th) + sigma2


def simulate_switched(arr, theta, snr_db, rng, L=64, *, int_theta=None, sir_db=None,
                      mp_theta=None, mp_rel_db=None, k_db=10.0, gain_err_db=0.0, point_err_deg=0.0,
                      iq=False):
    """Per-beam measured power p (B,N) for B independent measurement cycles.

    theta      : (B,) true azimuth, or (B,N) if the target moves during the switching cycle
    snr_db     : per-element isotropic SNR of the drone signal
    int_theta, sir_db : optional co-channel interferer (independent signal) and signal-to-interference
                        ratio at an isotropic element (sir=+inf disables it)
    mp_theta, mp_rel_db: optional coherent reflection (same signal, random phase per dwell) and its
                        power relative to the direct path
    k_db       : Rician K-factor of the per-dwell fading
    iq=True    : generate actual complex IQ samples (B,N,L) and average |y|^2; otherwise sample the
                 identical distribution directly (Gamma) which is ~L times faster. Both return (p, y|None).
    """
    theta = np.asarray(theta, dtype=float)
    B, N = theta.shape[0], arr.n
    rho = undb(_b(snr_db, B))[:, None]
    bs, gm = arr.perturbed(B, rng, gain_err_db, point_err_deg)
    c = np.sqrt(rho * arr.gain(theta, bs) * gm) * _rician(rng, (B, N), k_db)
    if mp_theta is not None:
        Gm = arr.gain(_b(mp_theta, B), bs) * gm
        rel = undb(_b(mp_rel_db, B))[:, None]
        psi = rng.uniform(0.0, 2.0 * np.pi, (B, N))
        c = c + np.sqrt(rho * rel * Gm) * np.exp(1j * psi)
    m = np.abs(c) ** 2 + 1.0
    if int_theta is not None:
        Gi = arr.gain(_b(int_theta, B), bs) * gm
        sir = _b(sir_db, B)
        with np.errstate(over="ignore", invalid="ignore"):
            rho_i = undb(_b(snr_db, B) - sir)[:, None]
        m = m + rho_i * Gi * np.abs(_rician(rng, (B, N), k_db)) ** 2
    if iq:
        y = np.sqrt(m)[:, :, None] * cn(rng, (B, N, L))
        return np.mean(np.abs(y) ** 2, axis=-1), y
    return rng.gamma(L, m / L), None


def simulate_uca(uca: CircularArray, theta, snr_db, rng, K, *, int_theta=None, sir_db=None,
                 mp_theta=None, mp_rel_db=None, phase_err_deg=0.0, gain_err_db=0.0):
    """Snapshots x (B,N,K) at the circular array. Interferer independent, reflection coherent (fixed phase)."""
    theta = np.asarray(theta, dtype=float)
    B, N = theta.shape[0], uca.n
    rho = undb(_b(snr_db, B))
    err = np.exp(1j * np.deg2rad(phase_err_deg) * rng.standard_normal((B, N))) \
        * 10.0 ** (gain_err_db * rng.standard_normal((B, N)) / 20.0)
    a = uca.steering(theta) * err
    if mp_theta is not None:
        rel = undb(_b(mp_rel_db, B))
        psi = rng.uniform(0.0, 2.0 * np.pi, B)
        a = a + (np.sqrt(rel) * np.exp(1j * psi))[:, None] * uca.steering(_b(mp_theta, B)) * err
    x = np.sqrt(rho)[:, None, None] * a[:, :, None] * cn(rng, (B, 1, K)) + cn(rng, (B, N, K))
    if int_theta is not None:
        with np.errstate(over="ignore", invalid="ignore"):
            rho_i = undb(_b(snr_db, B) - _b(sir_db, B))
        ai = uca.steering(_b(int_theta, B)) * err
        x = x + np.sqrt(rho_i)[:, None, None] * ai[:, :, None] * cn(rng, (B, 1, K))
    return x


# --------------------------------------------------------------------------------------------------
# estimators: switched beam (power only)
# --------------------------------------------------------------------------------------------------

def est_strongest(p, arr):
    return arr.boresights[np.argmax(p, axis=-1)]


def est_centroid(p, arr, sigma2=1.0):
    """Power-weighted vector centroid of the beam boresights (noise floor removed)."""
    w = np.maximum(p - sigma2, 0.0)
    z = (w * np.exp(1j * np.deg2rad(arr.boresights))).sum(-1)
    return wrap360(np.rad2deg(np.angle(z)))


class PowerVectorEstimator:
    """Maximum-likelihood fit of the measured power vector to the known beam patterns.

    Model: p_i ~ Gamma(L, m_i/L), m_i = a*G_i(theta) + sigma2  (a = unknown source strength, theta = angle).
    The strength `a` is profiled out per grid angle by Fisher scoring, the angle is refined by parabolic
    interpolation of the profile NLL. Also returned:
      sigma   : angular standard deviation from the profile curvature (Cramer-Rao style), inflated by
                sqrt(reduced deviance) when the data fit the model badly (fading, interference, mismatch)
      red_dev : Gamma deviance / (N-2)  (~1 for a good fit)
      snr_db  : estimated isotropic SNR of the source
    """

    def __init__(self, arr: SwitchedBeamArray, step=1.0):
        self.arr, self.step = arr, step
        self.grid = np.arange(0.0, 360.0, step)
        self.G = arr.gain(self.grid)  # (T,N) nominal model

    def _profile(self, p, G, sigma2, L):
        """Profile NLL over the source strength. G: (T,N) shared model or (B,T,N) per-trial model."""
        G = G[None, :, :] if G.ndim == 2 else G
        ph = np.maximum(p - sigma2, 0.0)[:, None, :]
        a = (ph * G).sum(-1) / (G * G).sum(-1)
        floor = 1e-3 * sigma2 / self.arr.g0
        a = np.maximum(a, floor)
        pp = p[:, None, :]
        for _ in range(5):
            m = a[..., None] * G + sigma2
            grad = (G * (m - pp) / m ** 2).sum(-1)
            fish = (G ** 2 / m ** 2).sum(-1)
            a = np.maximum(a - grad / fish, floor)
        m = a[..., None] * G + sigma2
        nll = L * (np.log(m) + pp / m).sum(-1)
        return nll, a

    def estimate(self, p, L, sigma2=1.0, chunk=256):
        p = np.atleast_2d(np.asarray(p, dtype=float))
        B, N = p.shape
        T = len(self.grid)
        th, sg, dv, sn = (np.empty(B) for _ in range(4))
        for s in range(0, B, chunk):
            pc = p[s:s + chunk]
            nll, a = self._profile(pc, self.G, sigma2, L)
            k = nll.argmin(1)
            ar = np.arange(len(pc))
            delta, den = _parab(nll[ar, (k - 1) % T], nll[ar, k], nll[ar, (k + 1) % T])
            th1 = self.grid[k] + delta * self.step
            # coarse-to-fine: re-fit a parabola on a 4x finer local grid (removes interpolation bias)
            d = self.step / 4.0
            cand = th1[:, None] + d * np.array([-1.0, 0.0, 1.0])
            Gf = self.arr.gain(cand.reshape(-1)).reshape(len(pc), 3, N)
            nll_f, _ = self._profile(pc, Gf, sigma2, L)
            delta2, _ = _parab(nll_f[:, 0], nll_f[:, 1], nll_f[:, 2])
            th[s:s + chunk] = wrap360(th1 + delta2 * d)
            curv = den / self.step ** 2
            sig_crb = np.where(curv > 1e-12, 1.0 / np.sqrt(np.maximum(curv, 1e-12)), 180.0)
            a_hat = a[ar, k]
            m = a_hat[:, None] * self.G[k] + sigma2
            r = pc / m
            red = 2.0 * L * (r - 1.0 - np.log(r)).sum(1) / max(N - 2, 1)
            sg[s:s + chunk] = np.clip(sig_crb * np.sqrt(np.maximum(1.0, red)), 0.05, 180.0)
            dv[s:s + chunk] = red
            sn[s:s + chunk] = db(np.maximum(a_hat / sigma2, 1e-3))
        return dict(theta=th, sigma=sg, red_dev=dv, snr_db=sn, rssi_db=db(np.maximum(p.max(1) / sigma2, 1e-3)))


# --------------------------------------------------------------------------------------------------
# estimators: circular array (phase)
# --------------------------------------------------------------------------------------------------

class MusicEstimator:
    """MUSIC on the sample covariance with a 1-degree grid and parabolic refinement.

    sigma  : single-source stochastic CRB evaluated at the eigenvalue-based SNR estimate, inflated when
             the 2nd eigenvalue exceeds the noise-only (Marchenko-Pastur) edge - i.e. when the single
             source model is violated (interferer / multipath)."""

    def __init__(self, uca: CircularArray, step=1.0):
        self.uca, self.step = uca, step
        self.grid = np.arange(0.0, 360.0, step)
        self.A = uca.steering(self.grid)  # (T,N)

    def estimate(self, x, d=1, chunk=500):
        B, N, K = x.shape
        T = len(self.grid)
        th, sg, sn = (np.empty(B) for _ in range(3))
        for s in range(0, B, chunk):
            xc = x[s:s + chunk]
            R = np.einsum("bnk,bmk->bnm", xc, xc.conj()) / K
            w, V = np.linalg.eigh(R)
            En = V[:, :, :N - d]
            proj = np.einsum("bnm,tn->bmt", En.conj(), self.A)
            den = (proj.real ** 2 + proj.imag ** 2).sum(1)
            k = den.argmin(1)
            ar = np.arange(len(xc))
            delta, _ = _parab(den[ar, (k - 1) % T], den[ar, k], den[ar, (k + 1) % T])
            th[s:s + chunk] = wrap360(self.grid[k] + delta * self.step)
            noise = np.maximum(w[:, :max(N - 2, 1)].mean(1), 1e-12)
            rho = np.maximum((w[:, -1] / noise - 1.0) / N, 1e-4)
            var = (1.0 + 1.0 / (N * rho)) / (K * N * rho * self.uca.kr ** 2)
            edge = (1.0 + np.sqrt(N / K)) ** 2
            infl = np.sqrt(np.maximum(1.0, (w[:, -2] / noise) / edge))
            sg[s:s + chunk] = np.clip(np.rad2deg(np.sqrt(var)) * infl, 0.05, 180.0)
            sn[s:s + chunk] = db(rho)
        return dict(theta=th, sigma=sg, snr_db=sn)


class UcaEspritEstimator:
    """UCA-ESPRIT in phase-mode (beamspace) form, single source. Needs N >= 3."""

    def __init__(self, uca: CircularArray, M=None):
        self.uca = uca
        N = uca.n
        self._setup(M if M is not None else 1)
        if M is None:
            # pick the mode count with the smallest noiseless (aliasing) bias; small rings are not free of it
            th = np.linspace(0.25, 359.75, 360)
            best = None
            for Mi in range(1, (N - 1) // 2 + 1):
                self._setup(Mi)
                e = wrap180(self._from_vector(uca.steering(th) @ self.F.T) - th)
                rms = float(np.sqrt((e ** 2).mean()))
                if best is None or rms < best[0]:
                    best = (rms, Mi)
            self._setup(best[1])
            self.bias_rms = best[0]
        else:
            self.bias_rms = float("nan")

    def _setup(self, M):
        self.M = M
        m = np.arange(-M, M + 1)
        self.F = np.exp(-1j * np.outer(m, self.uca.gam)) / self.uca.n          # phase-mode transform
        self.gam_m = np.exp(1j * np.pi / 2.0 * m) * jv(m, self.uca.kr)        # j^m J_m(kr)

    def _from_vector(self, v):
        """ESPRIT shift-invariance step on a (B, 2M+1) signal-subspace vector."""
        U = v / np.linalg.norm(v, axis=1, keepdims=True) / self.gam_m[None, :]
        U1, U2 = U[:, :-1], U[:, 1:]
        z = (U1.conj() * U2).sum(1) / (np.abs(U1) ** 2).sum(1)
        return wrap360(-np.rad2deg(np.angle(z)))

    def estimate(self, x, chunk=500):
        B, N, K = x.shape
        out = np.empty(B)
        for s in range(0, B, chunk):
            xc = x[s:s + chunk]
            R = np.einsum("bnk,bmk->bnm", xc, xc.conj()) / K
            Rm = self.F @ R @ self.F.conj().T
            _, V = np.linalg.eigh(Rm)
            out[s:s + chunk] = self._from_vector(V[:, :, -1])   # Bessel weighting undone on the subspace
        return out


# --------------------------------------------------------------------------------------------------
# one-stop measurement + estimation
# --------------------------------------------------------------------------------------------------

class Systems:
    """Bundle of arrays and estimators for a given element count N, dwell L and snapshot count K."""

    def __init__(self, n=6, L=64, K=None, bw_scale=1.15, sidelobe_db=20.0, grid_step=1.0):
        self.n, self.L, self.K = n, L, (K if K is not None else n * L)
        self.arr = SwitchedBeamArray(n, bw_scale, sidelobe_db)
        self.uca = CircularArray(n)
        self.pv = PowerVectorEstimator(self.arr, grid_step)
        self.music = MusicEstimator(self.uca, grid_step)
        self.esprit = UcaEspritEstimator(self.uca)


_SWITCHED = {"strongest", "centroid", "pv"}
_COHERENT = {"music", "esprit"}


def _sl(x, s, B):
    if x is None:
        return None
    a = np.asarray(x)
    return a[s] if (a.ndim >= 1 and a.shape[0] == B) else x


def measure_all(S: Systems, rng, theta, snr_db, *, methods=("strongest", "centroid", "pv", "music", "esprit"),
                int_theta=None, sir_db=None, mp_theta=None, mp_rel_db=None, k_db=10.0,
                gain_err_db=0.0, point_err_deg=0.0, phase_err_deg=0.0, uca_gain_err_db=0.0,
                theta_cycle=None, chunk=500):
    """Simulate B trials and run the requested estimators. Returns {method: array or dict}.

    theta_cycle: optional (B,N) per-beam target angle (target moving during the switching cycle)."""
    methods = set(methods)
    theta = np.asarray(theta, dtype=float)
    B = theta.shape[0]
    res = {}
    parts = {k: [] for k in methods}
    for s0 in range(0, B, chunk):
        s = slice(s0, min(B, s0 + chunk))
        kw = dict(int_theta=_sl(int_theta, s, B), sir_db=_sl(sir_db, s, B),
                  mp_theta=_sl(mp_theta, s, B), mp_rel_db=_sl(mp_rel_db, s, B))
        th, sn = theta[s], _sl(snr_db, s, B)
        if methods & _SWITCHED:
            thc = th if theta_cycle is None else np.asarray(theta_cycle)[s]
            p, _ = simulate_switched(S.arr, thc, sn, rng, S.L, k_db=k_db, gain_err_db=gain_err_db,
                                     point_err_deg=point_err_deg, **kw)
            if "strongest" in methods:
                parts["strongest"].append(est_strongest(p, S.arr))
            if "centroid" in methods:
                parts["centroid"].append(est_centroid(p, S.arr))
            if "pv" in methods:
                parts["pv"].append(S.pv.estimate(p, S.L))
        if methods & _COHERENT:
            x = simulate_uca(S.uca, th, sn, rng, S.K, phase_err_deg=phase_err_deg,
                             gain_err_db=uca_gain_err_db, **kw)
            if "music" in methods:
                parts["music"].append(S.music.estimate(x))
            if "esprit" in methods:
                parts["esprit"].append(S.esprit.estimate(x))
    for k, lst in parts.items():
        if not lst:
            continue
        res[k] = ({key: np.concatenate([d[key] for d in lst]) for key in lst[0]} if isinstance(lst[0], dict)
                  else np.concatenate(lst))
    return res


# --------------------------------------------------------------------------------------------------
# adaptive tracker
# --------------------------------------------------------------------------------------------------

@dataclass
class TrackerConfig:
    dt: float = 0.05              # s between measurements
    q0: float = 300.0             # acceleration PSD, deg^2/s^3
    q_min: float = 30.0
    q_max: float = 2.0e4
    adaptive_q: bool = True       # raise q when the normalised innovations are persistently large
    adaptive_R: bool = True       # use the estimator's own sigma as measurement noise
    r_fixed: float = 8.0          # deg, measurement sigma when adaptive_R is False
    sigma_floor: float = 1.0      # deg, residual calibration/model error
    sigma_ceil: float = 90.0      # deg, measurement with sigma >= this is treated as 'no measurement'
    gating: bool = True
    gate_prob: float = 0.999
    soft_gate_nis: float = 36.0   # NIS below this but above the gate = 'possible manoeuvre', not a jump
    maneuver_q_gain: float = 4.0  # process-noise inflation applied to a possible manoeuvre
    nis_win: int = 10
    reacq_n: int = 15             # consecutive rejections before a re-acquisition is considered
    reacq_spread: float = 12.0    # deg, rejected measurements must agree within this to re-acquire
    sigma0: float = 40.0          # deg, initial angle uncertainty
    omega0: float = 60.0          # deg/s, initial rate uncertainty
    conf_scale: float = 10.0      # deg
    conf_thresh: float = 0.5      # below this the output is flagged unreliable


COAST, ACCEPT, REJECT, REACQ = 0, 1, 2, 3


class AngleTracker:
    """Kalman filter on [angle (unwrapped), angular rate] with gating and adaptive noise."""

    def __init__(self, cfg: TrackerConfig):
        self.cfg = cfg
        self.gate = chi2.ppf(cfg.gate_prob, 1)
        self.x0 = None
        self.q = cfg.q0
        self.nis = deque(maxlen=cfg.nis_win)
        self.rej = []
        self.last_status = COAST

    def _init(self, z, sig):
        c = self.cfg
        s0 = float(np.clip(sig, 4.0, c.sigma0)) if np.isfinite(sig) else c.sigma0
        self.x0, self.x1 = float(z), 0.0
        self.p00, self.p01, self.p11 = s0 ** 2, 0.0, c.omega0 ** 2
        self.rej = []

    def step(self, z, sig):
        """z: measured angle (deg), sig: its standard deviation (deg). Returns (theta, omega, sigma_post, status, conf)."""
        c = self.cfg
        if self.x0 is None:
            if not np.isfinite(z) or sig >= c.sigma_ceil:     # nothing usable yet: do not start on garbage
                return float("nan"), 0.0, c.sigma0, COAST, 0.0
            self._init(z, sig)
            self.last_status = ACCEPT
            return self._out(ACCEPT)
        dt, q = c.dt, self.q
        # predict
        self.x0 += dt * self.x1
        self.p00 += dt * 2.0 * self.p01 + dt * dt * self.p11 + q * dt ** 3 / 3.0
        self.p01 += dt * self.p11 + q * dt * dt / 2.0
        self.p11 += q * dt
        status = COAST
        if np.isfinite(z) and sig < c.sigma_ceil:
            R = (min(max(sig, c.sigma_floor), c.sigma_ceil) if c.adaptive_R else c.r_fixed) ** 2
            y = float(wrap180(z - self.x0))
            S = self.p00 + R
            nis = y * y / S
            if c.gating and c.adaptive_q and self.gate < nis < c.soft_gate_nis and self.q < c.q_max:
                # Moderately large innovation: more likely a real manoeuvre than a jump. Inflate the process
                # noise for this step and re-test; abrupt jumps (interferer capture) stay far outside.
                qn = min(self.q * c.maneuver_q_gain, c.q_max)
                dq = qn - self.q
                self.p00 += dq * dt ** 3 / 3.0
                self.p01 += dq * dt * dt / 2.0
                self.p11 += dq * dt
                self.q = qn
                S = self.p00 + R
                nis = y * y / S
            if c.gating and nis > self.gate:
                status = REJECT
                self.rej.append(z)
                if len(self.rej) > c.reacq_n:
                    self.rej.pop(0)
                if len(self.rej) >= c.reacq_n:
                    zz = np.exp(1j * np.deg2rad(np.asarray(self.rej)))
                    rbar = min(max(abs(zz.mean()), 1e-9), 1.0)
                    spread = np.rad2deg(np.sqrt(-2.0 * np.log(rbar)))
                    if spread < c.reacq_spread:
                        mean_ang = np.rad2deg(np.angle(zz.mean()))
                        self._init(self.x0 + float(wrap180(mean_ang - self.x0)), 10.0)
                        status = REACQ
            else:
                k0, k1 = self.p00 / S, self.p01 / S
                self.x0 += k0 * y
                self.x1 += k1 * y
                self.p11 -= k1 * self.p01
                self.p01 *= (1.0 - k0)
                self.p00 *= (1.0 - k0)
                status = ACCEPT
                self.rej = []
                self.nis.append(nis)
                if c.adaptive_q and len(self.nis) >= c.nis_win // 2:
                    mean_nis = float(np.mean(self.nis))
                    if mean_nis > 1.8:
                        self.q = min(self.q * 1.5, c.q_max)
                    elif mean_nis < 0.6:
                        self.q = max(self.q / 1.2, c.q_min)
        self.last_status = status
        return self._out(status)

    def _out(self, status):
        c = self.cfg
        sp = float(np.sqrt(max(self.p00, 0.0)))
        conf = float(conf_from_sigma(sp, c.conf_scale)) * (1.0 if status in (ACCEPT, REACQ) else 0.7)
        return float(wrap360(self.x0)), self.x1, sp, status, conf


def run_tracker(z, sig, cfg: TrackerConfig):
    """Run the tracker over a measurement sequence. Returns dict of arrays."""
    tr = AngleTracker(cfg)
    n = len(z)
    out = {k: np.empty(n) for k in ("theta", "omega", "sigma", "status", "conf")}
    for i in range(n):
        th, om, sp, st, cf = tr.step(z[i], sig[i])
        out["theta"][i], out["omega"][i], out["sigma"][i], out["status"][i], out["conf"][i] = th, om, sp, st, cf
    out["flag"] = out["conf"] < cfg.conf_thresh
    return out


def ema_circular(z, alpha=0.3):
    """Exponential moving average on the unit circle (the naive smoother used as a baseline)."""
    z = np.asarray(z, dtype=float)
    out = np.empty_like(z)
    v = np.exp(1j * np.deg2rad(z[0]))
    for i, zi in enumerate(z):
        v = alpha * np.exp(1j * np.deg2rad(zi)) + (1.0 - alpha) * v
        out[i] = wrap360(np.rad2deg(np.angle(v)))
    return out


# --------------------------------------------------------------------------------------------------
# moving-drone scenario
# --------------------------------------------------------------------------------------------------

def make_scenario(rng, T=60.0, rate=20.0, interference=True, fades=True, n_bursts=3):
    """Drone azimuth trajectory + time-varying link conditions.

    omega profile: slow turn, fast fly-by (60 deg/s), hard reversal (-80 deg/s), hover, oscillation.
    SNR: slow range variation 11..25 dB plus two ~1 s blockage fades (-25 dB).
    Interference: bursts of 0.5-1.5 s from a fixed ground transmitter >= 40 deg from the drone, SIR -3..+6 dB.
    """
    t = np.arange(0.0, T, 1.0 / rate)
    ct = np.array([0, 5, 12, 15, 22, 24, 30, 32, 40, 44, 50, 53, 60.0]) * (T / 60.0)
    cw = np.array([0, 15, 15, 60, 60, -80, -80, 0, 2, 40, 40, -20, 0.0]) * rng.uniform(0.8, 1.2)
    omega = np.interp(t, ct, cw)
    theta = wrap360(rng.uniform(0, 360) + np.cumsum(omega) / rate)
    snr = 18.0 + 7.0 * np.sin(2 * np.pi * t / 45.0 + rng.uniform(0, 2 * np.pi))
    if fades:
        for _ in range(2):
            i0 = int(rng.uniform(2.0, T - 3.0) * rate)
            snr[i0:i0 + int(rng.uniform(0.8, 1.2) * rate)] -= 25.0
    mask = np.zeros(len(t), dtype=bool)
    int_theta = np.zeros(len(t))
    sir = np.full(len(t), np.inf)
    if interference:
        for _ in range(n_bursts):
            i0 = int(rng.uniform(3.0, T - 3.0) * rate)
            n = int(rng.uniform(0.5, 1.5) * rate)
            mask[i0:i0 + n] = True
            int_theta[i0:i0 + n] = wrap360(theta[i0] + rng.uniform(40, 320))
            sir[i0:i0 + n] = rng.uniform(-3.0, 6.0)
    return dict(t=t, theta=theta, omega=omega, snr=snr, int_theta=int_theta, sir=sir, int_mask=mask, rate=rate)


# --------------------------------------------------------------------------------------------------
# timing
# --------------------------------------------------------------------------------------------------

def time_call(fn, reps=200, warm=20):
    """Wall-clock per call in microseconds."""
    for _ in range(warm):
        fn()
    t = np.empty(reps)
    for i in range(reps):
        t0 = time.perf_counter()
        fn()
        t[i] = time.perf_counter() - t0
    return t * 1e6
