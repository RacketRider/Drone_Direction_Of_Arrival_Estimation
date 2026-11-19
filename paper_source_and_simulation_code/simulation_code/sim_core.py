import numpy as np
C = 3e8; M = 4; R_ARR = 0.072; FS = 250e3; TS = 1/FS
NS = 256; NSNAP = NS//M; F0_STATIC = 433e6
PHI = 2*np.pi*np.arange(M)/M
GRID = np.deg2rad(np.arange(0, 360, 0.1))
def wrap(d): return (d+180)%360-180
def steer(f, theta):
    """f, theta broadcastable -> (...,M)"""
    f = np.asarray(f)[..., None]; th = np.asarray(theta)[..., None]
    return np.exp(1j*2*np.pi*f/C*R_ARR*np.cos(th-PHI))
def bpsk(rng, T, L=16):
    sym = rng.choice([-1.0, 1.0], size=(T, NS//L))
    return np.repeat(sym, L, axis=1)
def noise(rng, shape): return (rng.standard_normal(shape)+1j*rng.standard_normal(shape))/np.sqrt(2)
def make_switched(rng, T, snr_db, f_ch, theta, f_off, mp=None):
    """mp=(rho, c, theta_r) arrays (T,) or None. Returns y (T,NS)."""
    n = np.arange(NS); el = n % M
    ftrue = f_ch + f_off
    amp = 10**(snr_db/20)
    s = bpsk(rng, T)*np.exp(1j*rng.uniform(0, 2*np.pi, (T, 1)))
    a = steer(ftrue, theta)                      # (T,M)
    sig = a[:, el]*s
    if mp is not None:
        rho, c, th_r = mp
        sp = bpsk(rng, T)
        sr = c[:, None]*np.abs(s)*np.exp(1j*np.angle(s)) + np.sqrt(1-c**2)[:, None]*sp*np.exp(1j*np.angle(s))
        ar = steer(ftrue, th_r)
        psi = np.exp(1j*rng.uniform(0, 2*np.pi, (T, 1)))
        sig = sig + rho[:, None]*psi*ar[:, el]*sr
    y = amp*sig*np.exp(1j*2*np.pi*f_off[:, None]*n*TS) + noise(rng, (T, NS))
    return y
def freq_estimate(y, refine=True):
    T = y.shape[0]
    w = np.hanning(NS)
    Y = np.abs(np.fft.fftshift(np.fft.fft(y*w, axis=1), axes=1))
    fax = np.fft.fftshift(np.fft.fftfreq(NS, TS))
    band = np.abs(fax) < FS/(2*M)
    idx = np.argmax(np.where(band, Y, -1), axis=1)
    f_c = fax[idx]
    if not refine: return f_c, f_c
    n = np.arange(NS)
    yd = y*np.exp(-1j*2*np.pi*f_c[:, None]*n*TS)
    r = np.sum(yd[:, M:]*np.conj(yd[:, :-M]), axis=1)
    f_r = f_c + FS/(2*np.pi*M)*np.angle(r)
    return f_c, f_r
def snapshots(y, f_hat, derotate=True):
    n = np.arange(NS)
    x = y*np.exp(-1j*2*np.pi*f_hat[:, None]*n*TS) if derotate else y
    return x.reshape(y.shape[0], NSNAP, M).transpose(0, 2, 1)   # (T,M,NSNAP)
def cov(X): return X@np.conj(X.transpose(0, 2, 1))/X.shape[2]
def eig(R):
    w, v = np.linalg.eigh(R); return w[:, ::-1], v[:, :, ::-1]
def _refine(P, grid_deg=0.1):
    i = np.argmax(P, axis=1); G = P.shape[1]
    im, ip = (i-1) % G, (i+1) % G
    r = np.arange(P.shape[0])
    ym, y0, yp = P[r, im], P[r, i], P[r, ip]
    den = ym-2*y0+yp
    d = np.where(np.abs(den) > 1e-30, 0.5*(ym-yp)/den, 0)
    return (i+np.clip(d, -1, 1))*grid_deg % 360
def music(R, f_steer):
    w, v = eig(R); En = v[:, :, 1:]
    A = steer(f_steer[:, None]*np.ones(len(GRID)), GRID[None, :]*np.ones((R.shape[0], 1)))  # (T,G,M)
    proj = np.einsum('tgm,tmk->tgk', np.conj(A), En)
    den = np.sum(np.abs(proj)**2, axis=2)
    P = 1/np.maximum(den, 1e-12)
    return _refine(P)
def bartlett(R, f_steer):
    A = steer(f_steer[:, None]*np.ones(len(GRID)), GRID[None, :]*np.ones((R.shape[0], 1)))
    P = np.real(np.einsum('tgm,tmn,tgn->tg', np.conj(A), R, A))
    return _refine(P)
def capon(R, f_steer):
    T = R.shape[0]
    Rl = R+1e-2*np.trace(R, axis1=1, axis2=2).real[:, None, None]/M*np.eye(M)
    Ri = np.linalg.inv(Rl)
    A = steer(f_steer[:, None]*np.ones(len(GRID)), GRID[None, :]*np.ones((T, 1)))
    P = 1/np.maximum(np.real(np.einsum('tgm,tmn,tgn->tg', np.conj(A), Ri, A)), 1e-12)
    return _refine(P)
PAIRS = [(i, j) for i in range(M) for j in range(i+1, M)]
def interf(R, f_steer):
    T = R.shape[0]
    A = steer(f_steer[:, None]*np.ones(len(GRID)), GRID[None, :]*np.ones((T, 1)))
    cost = 0
    for (i, j) in PAIRS:
        pred = A[:, :, i]*np.conj(A[:, :, j])
        m = R[:, i, j][:, None]
        cost = cost + np.abs(m)*(1-np.cos(np.angle(m)-np.angle(pred)))
    return _refine(-cost)
def crb_deg(snr_db, theta_rad, f, nsnap=NSNAP):
    """deterministic CRB (deg) for single source, per-element SNR, nsnap snapshots"""
    h = 1e-5
    a = steer(f, theta_rad); da = (steer(f, theta_rad+h)-steer(f, theta_rad-h))/(2*h)
    q = np.real(np.sum(np.conj(da)*da, -1) - np.abs(np.sum(np.conj(a)*da, -1))**2/np.sum(np.abs(a)**2, -1))
    snr = 10**(snr_db/10)
    return np.rad2deg(np.sqrt(1/(2*nsnap*snr*q)))
