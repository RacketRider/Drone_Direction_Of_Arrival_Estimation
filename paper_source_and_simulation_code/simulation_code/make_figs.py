import numpy as np, json, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['Liberation Serif', 'DejaVu Serif'], 'mathtext.fontset': 'stix',
    'font.size': 7.5, 'axes.linewidth': 0.6, 'axes.labelsize': 7.5, 'legend.fontsize': 6.3, 'xtick.labelsize': 7, 'ytick.labelsize': 7,
    'lines.linewidth': 1.0, 'lines.markersize': 3.2, 'grid.linewidth': 0.35, 'grid.alpha': 0.5, 'legend.frameon': True,
    'legend.framealpha': 0.9, 'legend.edgecolor': '0.6', 'legend.fancybox': False, 'pdf.fonttype': 42})
A = json.load(open('res_main.json')); B = json.load(open('res_more.json')); T = json.load(open('res_track.json')); S = np.load('spectra.npz')
W2 = 7.16; W1 = 3.45
def lab(ax, s): ax.text(0.5, -0.33, s, transform=ax.transAxes, ha='center', va='top', fontsize=7.5)
# ---- Fig 2: bias analysis (3 panels, full width)
fig, ax = plt.subplots(1, 3, figsize=(W2, 1.9), gridspec_kw={'wspace': 0.34})
a = ax[0]; a.plot(B['bias_freq']['f'], B['bias_freq']['maxabs'], 'k-', label='Worst-case $|\\mathrm{bias}|$'); a.plot(B['bias_freq']['f'], B['bias_freq']['rms'], 'b--', label='RMS over $\\theta$')
for f_ in [433, 868, 915]: a.axvline(f_, color='0.7', lw=0.5, ls=':')
a.set_xlabel('Hop frequency $f_k$ (MHz)'); a.set_ylabel('Static-steering bias (deg)'); a.grid(True); a.legend(loc='upper left'); a.set_ylim(0, 1.0); lab(a, '(a)')
a = ax[1]; a.semilogy(B['bias_radius']['r_cm'], np.maximum(B['bias_radius']['915'], 0.05), 'r-s', label='$f_k$ = 915 MHz'); a.semilogy(B['bias_radius']['r_cm'], np.maximum(B['bias_radius']['868'], 0.05), 'g--o', label='$f_k$ = 868 MHz')
a.axvline(7.2, color='k', ls=':', lw=0.7); a.text(7.9, 6.0, 'prototype\n$r$=7.2 cm', fontsize=6.3); a.set_xlabel('UCA radius $r$ (cm)'); a.set_ylabel('95th-pct. bias (deg)'); a.grid(True, which='both'); a.legend(loc='center right'); lab(a, '(b)')
a = ax[2]; th = S['th']
for k, st, l in [('prop', 'k-', 'Proposed (de-rotated, $\\lambda_k$)'), ('stat', 'b--', 'Static $\\lambda_0$ (433 MHz)'), ('nod', 'r-.', 'No de-rotation')]:
    p = S[k]; a.plot(th, 10*np.log10(p/p.max()), st, label=l)
a.axvline(35, color='0.5', ls=':', lw=0.7); a.set_xlim(0, 90); a.set_ylim(-30, 1); a.set_xlabel('Azimuth $\\theta$ (deg)'); a.set_ylabel('Pseudospectrum (dB)'); a.grid(True); a.legend(loc='lower right'); lab(a, '(c)')
fig.savefig('figs/fig_bias.pdf', bbox_inches='tight'); plt.close()
# ---- Fig 3: RMSE vs SNR + frequency error
snr = A['snrs']; C = A['curves']
fig, ax = plt.subplots(1, 2, figsize=(W2, 2.0), gridspec_kw={'wspace': 0.22})
a = ax[0]
a.semilogy(snr, C['noderot'], 'r-v', label='Switched, no de-rotation'); a.semilogy(snr, C['fftonly'], 'm-^', label='FFT-only de-rotation'); a.semilogy(snr, C['static'], 'b-s', label='Static $\\lambda_0$ (433 MHz)')
a.semilogy(snr, C['proposed'], 'k-o', label='Proposed (fine de-rotation + $\\lambda_k$)'); a.semilogy(snr, C['ideal'], 'g--x', label='Ideal 4-channel coherent'); a.semilogy(snr, A['crb'], 'k:', label='CRB')
a.set_xlabel('SNR per element (dB)'); a.set_ylabel('DoA RMSE (deg)'); a.grid(True, which='both'); a.legend(loc='lower left'); a.set_ylim(0.05, 100); lab(a, '(a)')
a = ax[1]; a.semilogy(snr, A['fe']['coarse'], 'm-^', label='Coarse FFT peak'); a.semilogy(snr, A['fe']['fine'], 'k-o', label='After lag-$M$ refinement')
a.set_xlabel('SNR per element (dB)'); a.set_ylabel('Frequency-offset RMSE (Hz)'); a.grid(True, which='both'); a.legend(loc='upper right'); lab(a, '(b)')
fig.savefig('figs/fig_rmse.pdf', bbox_inches='tight'); plt.close()
# ---- Fig 4: gate
G = B['gamma_snr']; R = B['rej_vs_c']
fig, ax = plt.subplots(1, 2, figsize=(W2, 1.95), gridspec_kw={'wspace': 0.22})
a = ax[0]; a.semilogy(G['snr'], G['med'], 'k-o', label='Median $\\gamma$'); a.fill_between(G['snr'], G['p10'], G['p90'], color='0.8', label='10th–90th pct.')
a.axhline(8, color='r', ls='--', label='$\\gamma_{\\rm th}=8$'); a.set_xlabel('SNR per element (dB)'); a.set_ylabel('Eigenvalue ratio $\\gamma=\\lambda_1/\\lambda_2$'); a.grid(True, which='both'); a.legend(loc='upper left'); lab(a, '(a)')
a = ax[1]
for rho, st in zip(['0.3', '0.6', '0.9'], ['b-s', 'k-o', 'r-^']): a.plot(R['c'], R[rho], st, label='$\\rho$ = %s'%rho)
a.set_xlabel('Direct/reflected correlation $|c|$'); a.set_ylabel('Rejection probability'); a.set_ylim(-0.03, 1.03); a.grid(True); a.legend(loc='upper right'); lab(a, '(b)')
fig.savefig('figs/fig_gate.pdf', bbox_inches='tight'); plt.close()
# ---- Fig 5: tracking
ex = T['example']; t = np.array(ex['t']); true = np.array(ex['true']); est = np.array(ex['est']); kf = np.array(ex['kf_all']); kg = np.array(ex['kf_gate']); acc = np.array(ex['acc'])
wr = lambda d: (d+180) % 360-180
fig, ax = plt.subplots(2, 1, figsize=(W1, 2.5), sharex=True, gridspec_kw={'hspace': 0.12})
for a in ax:
    for (t0, t1) in [(15, 25), (40, 48)]: a.axvspan(t0, t1, color='0.9', zorder=0)
a = ax[0]; a.plot(t, true, 'k-', lw=0.8, label='Truth'); a.plot(t[acc], est[acc], 'g.', ms=1.5, label='MUSIC (accepted)'); a.plot(t[~acc], est[~acc], 'r.', ms=2.2, label='MUSIC (gate-rejected)')
a.plot(t, kg, 'b-', lw=0.8, label='Circular KF'); a.set_ylabel('Bearing (deg)'); a.legend(loc='upper left', ncol=2, columnspacing=0.8, handlelength=1.4); a.grid(True); a.set_ylim(20, 220)
a = ax[1]; a.plot(t, wr(est-true), color='0.55', lw=0.5, label='Raw MUSIC'); a.plot(t, wr(kg-true), 'b-', lw=0.8, label='Gated + circular KF'); a.set_ylim(-40, 40)
a.set_xlabel('Time (s)'); a.set_ylabel('Error (deg)'); a.grid(True); a.legend(loc='upper left', ncol=2)
fig.savefig('figs/fig_track.pdf', bbox_inches='tight'); plt.close()
# ---- Fig 6: GDOP
tr = T['tri']; st = np.array(tr['stations']); tg = np.array(tr['target']); pts = np.array(tr['pts']); Cp = np.array(tr['cov'])
fig, a = plt.subplots(figsize=(W1, 2.95))
Gm = np.array(tr['G']); cs = a.contourf(tr['xs'], tr['ys'], Gm, levels=[85, 95, 105, 120, 150, 200, 400], cmap='YlGnBu', alpha=0.9, extend='both')
cb = fig.colorbar(cs, ax=a, fraction=0.046, pad=0.02); cb.set_label('GDOP (m/rad)', fontsize=7); cb.ax.tick_params(labelsize=6.5)
a.plot(pts[:, 0], pts[:, 1], '.', color='tab:blue', ms=1.2, alpha=0.5, label='WLS fixes (1$^\\circ$ bearing noise)')
w, v = np.linalg.eigh(Cp); ang = np.degrees(np.arctan2(v[1, 1], v[0, 1])); k = np.sqrt(5.991)
a.add_patch(Ellipse(tg, 2*k*np.sqrt(w[1]), 2*k*np.sqrt(w[0]), angle=ang, fill=False, ec='r', lw=1.0, label='95% confidence ellipse'))
a.plot(*tg, 'r*', ms=6, label='UAV (true)'); a.plot(st[:, 0], st[:, 1], 'k^', ms=6, label='DF stations')
for i, s_ in enumerate(st): a.annotate('S%d'%(i+1), s_, textcoords='offset points', xytext=(4, 4), fontsize=7)
a.set_xlim(0, 120); a.set_ylim(0, 120); a.set_aspect('equal'); a.set_xlabel('x (m)'); a.set_ylabel('y (m)'); a.legend(loc='upper center', bbox_to_anchor=(0.5, -0.19), ncol=2, fontsize=6.0)
fig.savefig('figs/fig_gdop.pdf', bbox_inches='tight'); plt.close()
print('ok')
# ---- Fig 5 combined: tracking (a,b) + GDOP (c)
fig = plt.figure(figsize=(W2, 2.75))
gs = fig.add_gridspec(2, 2, width_ratios=[1.25, 1], hspace=0.12, wspace=0.28, left=0.07, right=0.97, top=0.97, bottom=0.17)
a1 = fig.add_subplot(gs[0, 0]); a2 = fig.add_subplot(gs[1, 0], sharex=a1); a3 = fig.add_subplot(gs[:, 1])
for a in (a1, a2):
    for (t0, t1) in [(15, 25), (40, 48)]: a.axvspan(t0, t1, color='0.9', zorder=0)
a1.plot(t, true, 'k-', lw=0.8, label='Truth'); a1.plot(t[acc], est[acc], 'g.', ms=1.5, label='MUSIC (accepted)'); a1.plot(t[~acc], est[~acc], 'r.', ms=2.2, label='MUSIC (gate-rejected)')
a1.plot(t, kg, 'b-', lw=0.8, label='Circular KF'); a1.set_ylabel('Bearing (deg)'); a1.legend(loc='upper left', ncol=2, columnspacing=0.8, handlelength=1.4); a1.grid(True); a1.set_ylim(20, 230)
plt.setp(a1.get_xticklabels(), visible=False)
a2.plot(t, wr(est-true), color='0.55', lw=0.5, label='Raw MUSIC'); a2.plot(t, wr(kg-true), 'b-', lw=0.8, label='Gated + circular KF'); a2.set_ylim(-40, 40)
a2.set_xlabel('Time (s)'); a2.set_ylabel('Error (deg)'); a2.grid(True); a2.legend(loc='upper left', ncol=2)
a1.text(0.5, 1.0, '', transform=a1.transAxes)
cs = a3.contourf(tr['xs'], tr['ys'], Gm, levels=[85, 95, 105, 120, 150, 200, 400], cmap='YlGnBu', alpha=0.9, extend='both')
cb = fig.colorbar(cs, ax=a3, fraction=0.046, pad=0.02); cb.set_label('GDOP (m/rad)', fontsize=7); cb.ax.tick_params(labelsize=6.5)
a3.plot(pts[:, 0], pts[:, 1], '.', color='tab:blue', ms=1.2, alpha=0.5, label='WLS fixes (1$^\\circ$ noise)')
a3.add_patch(Ellipse(tg, 2*k*np.sqrt(w[1]), 2*k*np.sqrt(w[0]), angle=ang, fill=False, ec='r', lw=1.0, label='95% ellipse'))
a3.plot(*tg, 'r*', ms=6, label='UAV (true)'); a3.plot(st[:, 0], st[:, 1], 'k^', ms=6, label='DF stations')
for i, s_ in enumerate(st): a3.annotate('S%d'%(i+1), s_, textcoords='offset points', xytext=(4, 4), fontsize=7)
a3.set_xlim(0, 120); a3.set_ylim(0, 120); a3.set_aspect('equal'); a3.set_xlabel('x (m)'); a3.set_ylabel('y (m)'); a3.legend(loc='upper right', fontsize=5.4, borderpad=0.3, labelspacing=0.25)
fig.text(0.30, 0.0, '(a)', ha='center', fontsize=7.5); fig.text(0.78, 0.0, '(b)', ha='center', fontsize=7.5)
fig.savefig('figs/fig_trkgdop.pdf'); plt.close(); print('ok2')
