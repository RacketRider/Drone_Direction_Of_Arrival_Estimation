"""Bounded 3-D vector Maxwell Yee-grid FDTD prototype.

This is a true 3-D Cartesian Yee-style time-domain update for Ex,Ey,Ez and
Hx,Hy,Hz on a small local voxel domain. It is deliberately not advertised as
solving the entire 45 m scene at 2.4 GHz. The output is a central Ez slice and
basic stability/finite-value diagnostics. Boundary absorption is a simple
lossy sponge, not a validated CPML.
"""
from __future__ import annotations
import math
import numpy as np
C0=299_792_458.0
EPS0=8.8541878128e-12
MU0=4e-7*np.pi

def fdtd_3d(frequency_hz=2.4e9, size_m=0.30, cells_per_wavelength=6, steps=80,
            shape=(28,28,28), seed=7):
    frequency_hz=float(frequency_hz); size_m=float(size_m)
    if not (1e8 <= frequency_hz <= 6e9): raise ValueError('frequency_hz must be between 0.1 and 6 GHz')
    if not (0.08 <= size_m <= 1.0): raise ValueError('3D local patch size must be 0.08–1.0 m')
    nx,ny,nz=(int(v) for v in shape)
    if min(nx,ny,nz)<12 or max(nx,ny,nz)>48: raise ValueError('each 3D grid dimension must be 12–48 cells')
    steps=int(np.clip(steps,20,160))
    dx=size_m/(max(nx,ny,nz)-1); dy=dx; dz=dx
    # 3-D Courant limit, with safety factor.
    dt=0.95/(C0*math.sqrt(dx**-2+dy**-2+dz**-2))
    epsr=np.ones((nx,ny,nz),dtype=np.float32); sigma=np.zeros_like(epsr)
    # Illustrative dielectric inclusions: lossy soil slab and two dielectric/rock voxels.
    epsr[:,:, :max(2,nz//7)]=4.0; sigma[:,:, :max(2,nz//7)]=0.015
    xx,yy,zz=np.indices((nx,ny,nz))
    rock=((xx-nx*.62)**2+(yy-ny*.48)**2+(zz-nz*.35)**2)<(min(nx,ny,nz)*.10)**2
    epsr[rock]=6.0; sigma[rock]=0.008
    tree=((xx-nx*.42)**2+(yy-ny*.58)**2)<(min(nx,ny)*.07)**2
    tree &= (zz>nz*.18)&(zz<nz*.85)
    epsr[tree]=2.2; sigma[tree]=0.025
    Ex=np.zeros_like(epsr); Ey=np.zeros_like(epsr); Ez=np.zeros_like(epsr)
    Hx=np.zeros_like(epsr); Hy=np.zeros_like(epsr); Hz=np.zeros_like(epsr)
    # Sponge damping increases smoothly near all six edges.
    edge=np.minimum.reduce(np.broadcast_arrays(xx, nx-1-xx, yy, ny-1-yy, zz, nz-1-zz)).astype(np.float32)
    sponge=np.exp(-0.10*np.maximum(0,4-edge)**2).astype(np.float32)
    ce=(1.0-sigma*dt/(2*EPS0*epsr))/(1.0+sigma*dt/(2*EPS0*epsr))
    ch=(dt/(EPS0*epsr))/(1.0+sigma*dt/(2*EPS0*epsr))
    ch=ch.astype(np.float32)
    # Soft Gaussian-modulated Ez source near one side of the domain.
    sx,sy,sz=nx//4,ny//2,nz//2
    t0=18.0; spread=6.0; omega=2*np.pi*frequency_hz
    for n in range(steps):
        # H <- H - dt/mu curl(E), forward differences via rolls; sponge suppresses wrap artefacts.
        dEz_dy=(np.roll(Ez,-1,axis=1)-Ez)/dy; dEy_dz=(np.roll(Ey,-1,axis=2)-Ey)/dz
        dEx_dz=(np.roll(Ex,-1,axis=2)-Ex)/dz; dEz_dx=(np.roll(Ez,-1,axis=0)-Ez)/dx
        dEy_dx=(np.roll(Ey,-1,axis=0)-Ey)/dx; dEx_dy=(np.roll(Ex,-1,axis=1)-Ex)/dy
        Hx=(Hx-(dt/MU0)*(dEz_dy-dEy_dz))*sponge
        Hy=(Hy-(dt/MU0)*(dEx_dz-dEz_dx))*sponge
        Hz=(Hz-(dt/MU0)*(dEy_dx-dEx_dy))*sponge
        # E <- E + dt/(eps) curl(H), backward differences.
        dHz_dy=(Hz-np.roll(Hz,1,axis=1))/dy; dHy_dz=(Hy-np.roll(Hy,1,axis=2))/dz
        dHx_dz=(Hx-np.roll(Hx,1,axis=2))/dz; dHz_dx=(Hz-np.roll(Hz,1,axis=0))/dx
        dHy_dx=(Hy-np.roll(Hy,1,axis=0))/dx; dHx_dy=(Hx-np.roll(Hx,1,axis=1))/dy
        Ex=ce*Ex+ch*(dHz_dy-dHy_dz); Ey=ce*Ey+ch*(dHx_dz-dHz_dx); Ez=ce*Ez+ch*(dHy_dx-dHx_dy)
        pulse=np.exp(-0.5*((n-t0)/spread)**2)*np.sin(omega*n*dt)
        Ez[sx,sy,sz]+=float(pulse)
        Ex*=sponge; Ey*=sponge; Ez*=sponge
        if not (np.isfinite(Ez).all() and np.isfinite(Hx).all()): raise FloatingPointError('non-finite field encountered')
    # central z slice, robust normalized for display
    sl=np.abs(Ez[:,:,nz//2]).astype(float); peak=float(sl.max())
    normalized=(sl/peak if peak>0 else sl).tolist()
    return {'solver':'3D vector Maxwell Yee-grid FDTD (local voxel patch)','dimensions':[nx,ny,nz],
      'steps':steps,'frequency_hz':frequency_hz,'wavelength_m':C0/frequency_hz,
      'dx_m':dx,'dt_s':dt,'courant_number':float(C0*dt*math.sqrt(dx**-2+dy**-2+dz**-2)),
      'field_component':'|Ez| central z slice','field_normalized':normalized,
      'peak_field_amplitude_arbitrary_units':peak,'finite_field':bool(np.isfinite(Ez).all()),
      'material_voxels':{'air_epsr':1.0,'soil_epsr':4.0,'rock_epsr':6.0,'vegetation_epsr':2.2},
      'notes':['True 3D field components are updated on a local Yee-style grid.','Displayed map is a 2D slice through the 3D field.','Material inclusions are illustrative voxel shapes, not imported scene meshes.','Boundary is a lossy sponge, not CPML; no experimental/reference validation is claimed.','A 45 m domain at 2.4 GHz needs far finer grids and is not represented by this local patch.']}
