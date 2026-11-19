import json, numpy as np
A = json.load(open('res_main.json')); B = json.load(open('res_more.json')); T = json.load(open('res_track.json'))
c = 3e8; r = 0.072
out = []
# Table: hop benchmark
rows = ''
for h in A['hops']:
    f = float(h['f'])*1e6; kap = 2*np.pi*f*r/c
    rows += f"{h['f']} & {kap:.2f} & {h['stat_err']:+.2f} & {h['stat_rmse']:.2f} & {h['prop_bias']:+.2f} & {h['prop_rmse']:.2f} \\\\\n"
open('tab_hops.tex', 'w').write(rows)
# Table: gate / multipath
lab = ['LoS only', r'$\rho{=}0.3,\ |c|{=}0.5$', r'$\rho{=}0.6,\ |c|{=}0$', r'$\rho{=}0.6,\ |c|{=}0.6$', r'$\rho{=}0.9,\ |c|{=}0.6$', r'$\rho{=}0.6,\ |c|{=}1$']
rows = ''
for l, d in zip(lab, B['gate_table']):
    rows += f"{l} & {100*d['rej']:.0f}\\% & {d['MUSIC']:.1f} & {d['Bartlett']:.1f} & {d['Capon']:.1f} & {d['MUSIC_gated']:.1f} & {d['out_all']:.2f}/{d['out_acc']:.2f} \\\\\n"
open('tab_gate.tex', 'w').write(rows)
# tracking
s = T['summary']; names = [('raw', 'Raw MUSIC (no filter)'), ('gated_hold', 'Gate + hold last bearing'), ('kf_all', 'Circular KF, no gate'), ('kf_gate', 'Circular KF + gate')]
rows = ''.join(f"{n} & {s[k][0]:.2f} $\\pm$ {s[k][1]:.2f} \\\\\n" for k, n in names)
open('tab_track.tex', 'w').write(rows)
# single-source algorithm RMSE
snr = A['snrs']; i5, i15, i25 = snr.index(5), snr.index(15), snr.index(25)
al = A['alg']; cu = A['curves']; fe = A['fe']
m = {}
m['rmseFifteen'] = f"{cu['proposed'][i15]:.2f}"; m['rmseIdealFifteen'] = f"{cu['ideal'][i15]:.2f}"; m['crbFifteen'] = f"{A['crb'][i15]:.2f}"
m['rmseFive'] = f"{cu['proposed'][i5]:.2f}"; m['rmseThirty'] = f"{cu['proposed'][snr.index(30)]:.2f}"
m['nodFifteen'] = f"{cu['noderot'][i15]:.1f}"; m['fftFifteen'] = f"{cu['fftonly'][i15]:.1f}"; m['statFifteen'] = f"{cu['static'][i15]:.2f}"
m['capFifteen'] = f"{al['Capon'][i15]:.2f}"
m['feFineFive'] = f"{fe['fine'][i5]:.0f}"; m['feFineFifteen'] = f"{fe['fine'][i15]:.0f}"; m['feFineThirty'] = f"{fe['fine'][snr.index(30)]:.0f}"
m['feCoarseFifteen'] = f"{fe['coarse'][i15]/1e3:.1f}"
m['trk'] = f"{T['tri']['rmse_mc']:.2f}"; m['gdopT'] = f"{T['tri']['gdop_target']:.0f}"; m['gdopMed'] = f"{float(np.median(np.array(T['tri']['G']))):.0f}"
m['triTheory'] = f"{T['tri']['rms_theory']:.2f}"
open('nums.tex', 'w').write(''.join(f"\\newcommand{{\\{k}}}{{{v}}}\n" for k, v in m.items()))
print(m)
