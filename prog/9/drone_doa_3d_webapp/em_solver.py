"""Bounded 2-D TMz FDTD and geometric propagation helpers for Drone DoA Lab.

This is a 2-D cross-section solver, not a 3-D Maxwell solution. The FDTD patch is
intentionally local because a scene tens of metres wide at 2.4 GHz needs millions
of cells to resolve a wavelength accurately.
"""
from __future__ import annotations
import math
import numpy as np
C0=299_792_458.0
EPS0=8.8541878128e-12
MU0=4e-7*np.pi

def segment_triangle_intersection(p0,p1,tri,eps=1e-9):
    """Möller–Trumbore segment/triangle intersection; tri is 3x3 (x,y,z)."""
    v0,v1,v2=np.asarray(tri,float); d=np.asarray(p1,float)-np.asarray(p0,float)
    e1=v1-v0; e2=v2-v0; h=np.cross(d,e2); a=float(np.dot(e1,h))
    if abs(a)<eps:return None
    f=1.0/a; s=np.asarray(p0,float)-v0; u=f*float(np.dot(s,h))
    if u < -eps or u > 1+eps:return None
    q=np.cross(s,e1); v=f*float(np.dot(d,q))
    if v < -eps or u+v > 1+eps:return None
    t=f*float(np.dot(e2,q))
    if eps<t<1-eps:return t
    return None

def trace_geometry(source,target,objects):
    """Exact against supplied triangle facets; circles/boxes are analytic primitives.
    Scene object proxies are approximations unless triangle vertices are supplied.
    """
    s=np.asarray(source,float); t=np.asarray(target,float); d=t-s; hits=[]; direct=[]
    for i,o in enumerate(objects if isinstance(objects,list) else []):
        if not isinstance(o,dict):continue
        name=str(o.get('id',o.get('label',f'object_{i+1}')))
        if isinstance(o.get('triangles'),list):
            for tri in o['triangles']:
                try:
                    hit=segment_triangle_intersection(s,t,tri)
                    if hit is not None:hits.append({'object':name,'kind':o.get('kind','mesh'),'t':hit,'point':(s+hit*d).tolist(),'method':'triangle facet'})
                except (ValueError,TypeError):continue
        elif 'bounds' in o:
            b=o['bounds']; lo=np.asarray(b.get('min',[0,0,0]),float); hi=np.asarray(b.get('max',[0,0,0]),float)
            inv=np.where(np.abs(d)>1e-12,1/d,np.inf); a=(lo-s)*inv; z=(hi-s)*inv
            near=np.max(np.minimum(a,z)); far=np.min(np.maximum(a,z))
            if far>=max(near,0) and near<1 and far>0:hits.append({'object':name,'kind':o.get('kind','box'),'t':float(max(0,near)),'point':(s+max(0,near)*d).tolist(),'method':'axis-aligned box'})
        else:
            # Analytic X/Z cylinder/circle proxy for scene objects that expose radius.
            try: center=np.array([float(o.get('x',0)),float(o.get('z',0))]); r=float(o.get('radius',1.0))
            except (TypeError,ValueError):continue
            u=d[[0,2]]; q=s[[0,2]]-center; aa=float(u@u); bb=2*float(q@u); cc=float(q@q-r*r); disc=bb*bb-4*aa*cc
            if aa>1e-12 and disc>=0:
                roots=[v for v in ((-bb-math.sqrt(disc))/(2*aa),(-bb+math.sqrt(disc))/(2*aa)) if 1e-6<v<1-1e-6]
                if roots:hits.append({'object':name,'kind':o.get('kind','primitive'),'t':min(roots),'point':(s+min(roots)*d).tolist(),'method':'analytic circle proxy'})
    hits.sort(key=lambda h:h['t'])
    return {'blocked':bool(hits),'hits':hits,'direct_path':[s.tolist(),t.tolist()], 'geometry_note':'Triangle tests are exact only for supplied triangle facets; scene proxies use analytic primitives.'}

def fdtd_tmz(frequency_hz=2.4e9, size_m=1.5, cells_per_wavelength=10, steps=450, objects=None, seed=7):
    """Small 2-D TMz Yee-grid simulation with conductive dielectric and lossy sponge edges.
    E_z is updated from H_x/H_y; output is a normalized field magnitude map.
    """
    f=float(np.clip(frequency_hz,1e8,6e9)); lam=C0/f
    cpw=int(np.clip(cells_per_wavelength,8,16)); dx=lam/cpw; dy=dx
    nx=int(np.clip(round(size_m/dx),64,240)); ny=nx; dx=size_m/nx; dy=dx
    dt=0.99/(C0*math.sqrt(dx**-2+dy**-2)); steps=int(np.clip(steps,100,900))
    epsr=np.ones((ny,nx),float); sigma=np.zeros_like(epsr); mur=np.ones_like(epsr)
    # Small local cross-section around source: scene coordinates are mapped into this patch.
    for i,o in enumerate(objects if isinstance(objects,list) else []):
        if not isinstance(o,dict):continue
        try:
            x=float(o.get('x',0)); z=float(o.get('z',0)); r=float(np.clip(o.get('radius',.08),.02,.35))
            m=o.get('material',{}) or {}; er=float(np.clip(m.get('epsilon_r',4 if o.get('kind') in ('rock','stone','soil') else 2.5),1,80)); cond=float(np.clip(m.get('conductivity_s_m',.002),0,5))
        except (TypeError,ValueError):continue
        # Map scene object offsets relative to the midpoint between source and target.
        cx=int(nx/2+x/max(size_m,1e-9)*nx*.35); cy=int(ny/2+z/max(size_m,1e-9)*ny*.35); rr=max(1,int(r/dx))
        yy,xx=np.ogrid[:ny,:nx]; mask=(xx-cx)**2+(yy-cy)**2<=rr**2
        epsr[mask]=er; sigma[mask]=cond
    # Conductive-medium update coefficients.
    ca=(1-sigma*dt/(2*EPS0*epsr))/(1+sigma*dt/(2*EPS0*epsr))
    cb=(dt/(EPS0*epsr*dx))/(1+sigma*dt/(2*EPS0*epsr))
    ch=dt/(MU0*dx)
    ez=np.zeros((ny,nx)); hx=np.zeros((ny,nx)); hy=np.zeros((ny,nx))
    # Raised-cosine lossy sponge prevents strong edge returns; not a full PML.
    yy_idx, xx_idx = np.indices((ny, nx)); edge=np.minimum(np.minimum(yy_idx, xx_idx), np.minimum(ny-1-yy_idx, nx-1-xx_idx))
    sponge=np.exp(-0.018*np.maximum(0,10-edge)**2)
    sx,sy=nx//4,ny//2; omega=2*np.pi*f; pulse_center=45; pulse_width=16
    max_hist=[]
    for n in range(steps):
        hx[:-1,:]-=ch*(ez[1:,:]-ez[:-1,:]); hy[:,:-1]+=ch*(ez[:,1:]-ez[:,:-1])
        curl=(hy[1:-1,1:-1]-hy[1:-1,:-2])-(hx[1:-1,1:-1]-hx[:-2,1:-1])
        ez[1:-1,1:-1]=ca[1:-1,1:-1]*ez[1:-1,1:-1]+cb[1:-1,1:-1]*curl
        env=np.exp(-((n-pulse_center)/pulse_width)**2); ez[sy,sx]+=env*np.sin(omega*n*dt)
        ez*=sponge
        if n%50==0:max_hist.append(float(np.max(np.abs(ez))))
    field=np.abs(ez); peak=float(field.max()) or 1.0; norm=np.clip(field/peak,0,1)
    # Downsample for a compact API response.
    stride=max(1,nx//100); grid=np.round(norm[::stride,::stride],4).tolist()
    return {'solver':'2D TMz Yee-grid FDTD','frequency_hz':f,'wavelength_m':lam,'cells_per_wavelength':cpw,'dx_m':dx,'dt_s':dt,'steps':steps,'grid_nx':nx,'grid_ny':ny,'domain_size_m':size_m,'peak_field_amplitude_arbitrary_units':peak,'field_normalized':grid,'sample_stride':stride,'source_cell':[sx,sy],'max_field_history':max_hist,'stability':'Courant factor 0.99 in homogeneous 2D free space; verify material-specific cases before research use','boundary':'lossy sponge approximation, not CPML','scope':'2D local cross-section only; not a 3D Maxwell solve','objects_mapped':len(objects or [])}

def trace_reflected_scattered_paths(source, target, objects, max_paths=24):
    """Generate single-bounce specular candidates from supplied triangle facets and
    illustrative diffuse-scatter candidates toward selected facet centroids.
    Candidate paths are geometric, not an amplitude-calibrated EM solution.
    """
    s=np.asarray(source,float); t=np.asarray(target,float); reflected=[]; scattered=[]
    for oi,o in enumerate(objects if isinstance(objects,list) else []):
        if not isinstance(o,dict):continue
        name=str(o.get('id',o.get('label',f'object_{oi+1}')))
        tris=o.get('triangles') if isinstance(o.get('triangles'),list) else []
        if not tris:
            # Primitive proxies are not faceted, so mark a centroid-scatter candidate only.
            try: c=np.array([float(o.get('x',0)), float(o.get('y',0)), float(o.get('z',0))])
            except (TypeError,ValueError): continue
            if np.linalg.norm(c-s)+np.linalg.norm(t-c) < 1e5:
                scattered.append({'object':name,'path':[s.tolist(),c.tolist(),t.tolist()],'method':'primitive-centre scatter proxy','path_length_m':float(np.linalg.norm(c-s)+np.linalg.norm(t-c))})
            continue
        # Sample facets to bound work and avoid an enormous response for dense meshes.
        stride=max(1,len(tris)//120)
        for tri_raw in tris[::stride]:
            try: tri=np.asarray(tri_raw,float); a,b,c=tri
            except (ValueError,TypeError):continue
            n=np.cross(b-a,c-a); nn=float(np.linalg.norm(n))
            if nn<1e-10:continue
            n=n/nn
            image=s-2*np.dot(s-a,n)*n
            u=t-image
            denom=float(np.dot(n,u))
            if abs(denom)>1e-10:
                tau=float(np.dot(n,a-image)/denom)
                if 0<tau<1:
                    p=image+tau*u
                    # Barycentric point-in-triangle check.
                    v0=b-a; v1=c-a; v2=p-a; d00=v0@v0; d01=v0@v1; d11=v1@v1; d20=v2@v0; d21=v2@v1
                    den=d00*d11-d01*d01
                    if abs(den)>1e-12:
                        vv=(d11*d20-d01*d21)/den; ww=(d00*d21-d01*d20)/den; uu=1-vv-ww
                        if min(uu,vv,ww)>=-1e-6:
                            length=float(np.linalg.norm(p-s)+np.linalg.norm(t-p))
                            reflected.append({'object':name,'path':[s.tolist(),p.tolist(),t.tolist()],'reflection_point':p.tolist(),'method':'single-bounce specular triangle reflection','path_length_m':length})
            # A centroid candidate illustrates diffuse scattering; it is not a solved scattering lobe.
            center=tri.mean(axis=0); length=float(np.linalg.norm(center-s)+np.linalg.norm(t-center))
            scattered.append({'object':name,'path':[s.tolist(),center.tolist(),t.tolist()],'method':'facet-centroid diffuse-scatter proxy','path_length_m':length})
    reflected.sort(key=lambda p:p['path_length_m']); scattered.sort(key=lambda p:p['path_length_m'])
    return {'reflected_paths':reflected[:max_paths], 'scattered_paths':scattered[:max_paths],
            'note':'Specular candidates use triangle planes and point-in-triangle checks. Diffuse paths are centroid proxies; amplitudes and polarization are not solved.'}
