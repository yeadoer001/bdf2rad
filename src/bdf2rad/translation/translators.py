from .core import nf,ni
from collections import defaultdict

# Conservative IDs kept outside most Nastran IDs to avoid collisions.
NODE_GROUP_BASE=8000000
SURF_BASE=9000000
FUNCT_BASE=6000000


def elements(src, preserve_high_order=True):
    out=[]; warnings=[]
    for eid,e in src.elements.items():
        typ=e['type']; n=e['nodes'];
        if typ=='CTETRA' and len(n) in (4,10):
            if len(n)==10 and not preserve_high_order:
                n=n[:4]; warnings.append(f'CTETRA10 {eid} downgraded to TETRA4 by policy')
            out.append(dict(eid=eid,pid=e['pid'],type='TETRA10' if len(n)==10 else 'TETRA4',nodes=n))
        elif typ=='CHEXA' and len(n) in (8,20):
            if len(n)==20 and not preserve_high_order:
                n=n[:8]; warnings.append(f'CHEXA20 {eid} downgraded to BRICK by policy')
            out.append(dict(eid=eid,pid=e['pid'],type='BRIC20' if len(n)==20 else 'BRICK',nodes=n))
        elif typ=='CPENTA' and len(n) in (6,15):
            # OpenRadioss Nastran converter maps CPENTA15 to /BRICK after first-order conversion.
            # Degenerate brick preserves the six corner nodes but necessarily drops midside nodes.
            if len(n)==15:
                n=[n[0],n[1],n[2],n[2],n[3],n[4],n[5],n[5]]
                warnings.append(f'CPENTA15 {eid} converted to degenerate BRICK; midside nodes not represented')
            else:
                n=[n[0],n[1],n[2],n[2],n[3],n[4],n[5],n[5]]
            out.append(dict(eid=eid,pid=e['pid'],type='BRICK',nodes=n))
        else: warnings.append(f'Unsupported solid topology eid={eid} {typ}{len(n)}')
    return out,warnings

def materials(src, use_mats1=True):
    out=[]; functs=[]; warnings=[]
    for mid,m in src.mats.items():
        p=src.mats1.get(mid)
        if use_mats1 and p and p['type']=='PLASTIC':
            # LAW36 expects a stress-strain function. MATS1 gives initial yield and a hardening slope,
            # so create a two-point bilinear plastic curve. This is an engineering approximation,
            # not an exact nonlinear table when TID is present.
            if p['H']>0 and p['limit1']>=0:
                y=p['limit1']; h=p['H']; e0=y/m['E'] if m['E'] else 0.0; f=FUNCT_BASE+mid
                functs.append((f,[(e0,y),(e0+max(1e-6,0.01),y+h*max(1e-6,0.01))]))
                out.append(dict(mid=mid,law='LAW36',rho=m['rho'],E=m['E'],nu=m['nu'],funct=f))
                warnings.append(f'MAT1/MATS1 {mid}: bilinear LAW36 curve synthesized from yield={y}, H={h}')
                continue
            warnings.append(f'MAT1/MATS1 {mid}: unsupported/degenerate hardening definition; using ELASTIC')
        out.append(dict(mid=mid,law='ELASTIC',rho=m['rho'],E=m['E'],nu=m['nu']))
    return out,functs,warnings

def properties(src):
    return [dict(pid=pid,mid=d['mid']) for pid,d in sorted(src.props.items())]

def groups_and_bcs(src, selected_spc=None):
    groups=[]; bcs=[]; gid=NODE_GROUP_BASE
    by=defaultdict(list)
    cards=[c for c in src.spc if selected_spc is None or ni(c.fields[0])==selected_spc]
    for c in cards:
        f=c.fields
        if c.name=='SPC' and len(f)>=3: by[str(f[2]).replace(' ','')].append(ni(f[1]))
        elif c.name=='SPC1' and len(f)>=3: by[str(f[1]).replace(' ','')].extend(ni(x) for x in f[2:] if x)
    for dof,nodes in sorted(by.items()):
        gid+=1; nodes=sorted(set(nodes)); groups.append((gid,f'SPC_{gid}',nodes)); bcs.append((gid,gid,dof))
    return groups,bcs

def initial_velocity(src, selected_ic=None):
    v=defaultdict(lambda:[0.0,0.0,0.0]); warnings=[]
    for c in src.tic:
        if selected_ic is not None and ni(c.fields[0])!=selected_ic: continue
        f=c.fields; nid=ni(f[1]); dof=ni(f[2]); val=nf(f[4] if len(f)>4 else f[3],0.0)
        if dof in (1,2,3): v[nid][dof-1]=val
        else: warnings.append(f'TIC node {nid}: unsupported DOF {dof}')
    clusters=defaultdict(list)
    for nid,vec in v.items(): clusters[tuple(vec)].append(nid)
    groups=[]; entries=[]; gid=NODE_GROUP_BASE+100000
    for vec,nodes in sorted(clusters.items()):
        gid+=1; groups.append((gid,'TIC_'+str(gid),sorted(nodes))); entries.append((gid,vec))
    return groups,entries,warnings

def gravity(src, selected_load=None):
    cands=[c for c in src.grav if selected_load is None or ni(c.fields[0])==selected_load]
    if not cands: return []
    out=[]
    for c in cands:
        f=c.fields; out.append((ni(f[0]),nf(f[2],1.0),nf(f[3]),nf(f[4]),nf(f[5])))
    return out

def masses(src):
    out=[]; warnings=[]
    for c in src.conm2:
        f=c.fields; nid=ni(f[1]); mass=nf(f[3]); off=[nf(x) for x in f[4:7]]; inert=[nf(x) for x in f[7:13]]
        out.append((ni(f[0]),nid,mass,off,inert))
        if any(abs(x)>0 for x in off+inert): warnings.append(f'CONM2 {ni(f[0])} has nonzero offset/inertia; /ADMAS/5 cannot preserve inertia tensor')
    return out,warnings

def rbe2(src):
    out=[]; groups=[]; gid=NODE_GROUP_BASE+200000
    for c in src.rbe2:
        f=c.fields; rid=ni(f[0]); indep=ni(f[1]); cm=str(f[2]).replace(' ',''); dep=[ni(x) for x in f[3:] if x]; gid+=1
        groups.append((gid,f'RBE2_{rid}',dep)); out.append((rid,indep,cm,gid))
    return out,groups

def rbe3(src):
    out=[]; groups=[]; gid=NODE_GROUP_BASE+300000
    for c in src.rbe3:
        f=c.fields; rid=ni(f[0]); ref=ni(f[2]);
        vals=[x for x in f[3:] if x]
        # Parse repeating weight, component, node list groups conservatively.
        i=0; entries=[]; current=[]
        while i<len(vals):
            try: wt=nf(vals[i]);
            except: i+=1; continue
            if i+1>=len(vals): break
            comp=str(vals[i+1]).replace(' ',''); i+=2; nodes=[]
            while i<len(vals):
                s=vals[i]
                if s.replace('.','',1).replace('-','',1).isdigit() and ('.' in s or 'E' in s.upper() or (i+1<len(vals) and len(s)<=4 and vals[i+1].replace('.','',1).replace('-','',1).isdigit())): pass
                try:
                    n=ni(s)
                except: break
                # A component field is typically 1-6 digits; if the next token looks like one, keep consuming nodes only after comp.
                if len(s)<=6 and all(ch in '0123456' for ch in s) and s!='0' and len(nodes)==0 and i<len(vals)-1:
                    # first node can legitimately be small; do not special-case.
                    pass
                nodes.append(n); i+=1
                if i>=len(vals): break
            if nodes: entries.append((wt,comp,nodes))
            else: break
        flat=[n for _,_,ns in entries for n in ns]; gid+=1; groups.append((gid,f'RBE3_{rid}',sorted(set(flat))))
        out.append((rid,ref,entries,gid))
    return out,groups

def surface_faces(src):
    # BSURFS is encoded as repeated (element id + face nodes). Infer face arity from the referenced element.
    out=[]; warnings=[]
    for c in src.bsurfs:
        f=c.fields; sid=ni(f[0]); vals=[x for x in f[4:] if x]; i=0; faces=[]
        while i<len(vals):
            eid=ni(vals[i]); i+=1; e=src.elements.get(eid)
            if not e: warnings.append(f'BSURFS {sid}: unknown element {eid}'); break
            nface=3 if e['type']=='CTETRA' else 4 if e['type'] in ('CHEXA','CPENTA') else 0
            if not nface or i+nface>len(vals): warnings.append(f'BSURFS {sid}: invalid face record at element {eid}'); break
            nodes=[ni(x) for x in vals[i:i+nface]]; i+=nface; faces.append((eid,nodes))
        if faces: out.append((sid,faces))
    return out,warnings

def contact_sets(src):
    params={ni(c.fields[0]):c.fields for c in src.bcrpara}
    pairs=[]
    for c in src.bctset:
        f=c.fields; sid=ni(f[0]); main=ni(f[1]); sec=ni(f[2]); fric=nf(f[3],0.0); pairs.append((sid,main,sec,fric,params.get(sid,[])))
    adds={ni(c.fields[0]):[ni(x) for x in c.fields[1:] if x] for c in src.bctadd}
    selected=[]
    for root,children in adds.items():
        selected.extend(children)
    if not selected: selected=[x[0] for x in pairs]
    pm={x[0]:x for x in pairs}
    return [pm[x] for x in selected if x in pm]

def glue_sets(src):
    adds={ni(c.fields[0]):[ni(x) for x in c.fields[1:] if x] for c in src.bgadd}
    selected=[]
    for ch in adds.values(): selected.extend(ch)
    if not selected: selected=[ni(c.fields[0]) for c in src.bgset]
    return [c for c in src.bgset if ni(c.fields[0]) in set(selected)]
