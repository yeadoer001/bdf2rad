from pathlib import Path
from .translators import NODE_GROUP_BASE,SURF_BASE

def _chunks(xs,n):
    for i in range(0,len(xs),n): yield xs[i:i+n]

def write_group(lines,gid,title,nodes):
    lines += [f'/GRNOD/NODE/{gid}/1',title]
    for c in _chunks(nodes,10): lines.append(' '.join(str(x) for x in c))

def write_starter(path, name, model, data, preserve_high_order=True, version='2026'):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True); L=['#RADIOSS STARTER',f'/BEGIN/{name}','1 0']
    L += ['/UNIT/1','kg mm s mN']
    for mat in data['materials']:
        mid=mat['mid'];
        if mat['law']=='ELASTIC': L += [f'/MAT/ELASTIC/{mid}',f'MAT1_{mid}',f'{mat["rho"]:.12E}',f'{mat["E"]:.12E} {mat["nu"]:.12E}']
        else:
            L += [f'/MAT/LAW36/{mid}',f'MAT1_MATS1_{mid}',f'{mat["rho"]:.12E}',f'{mat["E"]:.12E}',f'{mat["nu"]:.12E}', '0.0 0.0 0.0 0.0', str(mat['funct'])]
    for fid,pts in data['functions']:
        L += [f'/FUNCT/{fid}',f'MATS1_BILINEAR_{fid}']
        L += [f'{x:.12E} {y:.12E}' for x,y in pts]
    for prop in data['properties']:
        pid=prop['pid']; L += [f'/PROP/SOLID/{pid}',f'PSOLID_{pid}','14 0 0 0 2 0 0 0 0','0.0 0.0 0.0 0.0 0.0',f'/PART/{pid}',f'PART_{pid}',f'{pid} {prop["mid"]}']
    L.append('/NODE')
    for nid,d in sorted(model.nodes.items()): L.append(f'{nid} {d["x"][0]:.12E} {d["x"][1]:.12E} {d["x"][2]:.12E}')
    groups={}; grouped={}
    for e in data['elements']: grouped.setdefault((e['pid'],e['type']),[]).append(e)
    for (pid,typ),es in sorted(grouped.items()):
        kw=typ; L += [f'/{kw}/{pid}']
        for e in es: L.append(' '.join(str(x) for x in (e['eid'],*e['nodes'])))
    for gid,title,nodes in data['node_groups']: write_group(L,gid,title,nodes)
    for gid,bid,dof in data['bcs']:
        L += [f'/BCS/{bid}',f'SPC_{gid}',f'{dof} 0 {gid}']
    for gid,vec in data['velocity']:
        L += [f'/INIVEL/TRA/{gid}/1',f'TIC_{gid}',f'{vec[0]:.12E} {vec[1]:.12E} {vec[2]:.12E} {gid} 0']
    for rid,scale,x,y,z in data['gravity']:
        L += [f'/GRAV/{rid}/1',f'GRAV_{rid}',f'{scale:.12E} 0 0',f'{x:.12E} {y:.12E} {z:.12E}']
    for rid,nid,mass,off,inert in data['masses']:
        if any(abs(x)>0 for x in off+inert): data['warnings'].append(f'CONM2 {rid}: inertia/offset cannot be represented by ADMAS/5 exactly')
        L += [f'/ADMAS/5/{rid}',f'CONM2_{rid}',f'{mass:.12E} {nid}']
    for rid,indep,cm,gid in data['rbe2']:
        L += [f'/RBE2/{rid}',f'RBE2_{rid}',f'{indep} {cm} {gid}']
    for rid,ref,entries,gid in data['rbe3']:
        L += [f'/RBE3/{rid}',f'RBE3_{rid}',f'{ref} 123456 {gid} 0']
        for wt,comp,nodes in entries: L += [f'{wt:.12E} {comp}'] + [str(n) for n in nodes]
    # Contacts: each BCTSET main/sec is translated as TYPE7 only when the corresponding BSURFS exist.
    face_map={sid:faces for sid,faces in data['surfaces']}
    for sid,faces in data['surfaces']:
        # Explicit /SURF/SEG requires segment nodes; aggregate unique triangles/quads from BDF faces.
        L += [f'/SURF/SEG/{SURF_BASE+sid}',f'BSURFS_{sid}']
        for _,nodes in faces: L.append(' '.join(str(n) for n in nodes))
    for cid,main,sec,fric,raw in data['contacts']:
        if main in face_map and sec in face_map:
            # Secondary node group from secondary surface nodes.
            nodes=sorted({n for _,face in face_map[sec] for n in face})
            gid=NODE_GROUP_BASE+500000+cid; write_group(L,gid,f'CONTACT_SEC_{cid}',nodes)
            L += [f'/INTER/TYPE7/{cid}',f'BCTSET_{cid}',f'{gid} {SURF_BASE+main} 1',f'1.0 {fric:.12E} 0.01']
        else:
            data['warnings'].append(f'BCTSET {cid}: missing referenced BSURFS main={main} sec={sec}; omitted')
    for c in data['glue']:
        gid=ni(c.fields[0]); L.append(f'# BGSET {gid} retained as source metadata; direct TYPE2 mapping requires verified patch/surface semantics')
    if data['not_transferred']:
        L.append('# NOT TRANSFERRED SOURCE CONTROLS')
        for x in data['not_transferred']: L.append('# '+x)
    L.append('/END'); p.write_text('\n'.join(L)+'\n',encoding='ascii'); return p

def write_engine(path,name,end_time,dtout):
    p=Path(path); p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text('\n'.join(['#RADIOSS ENGINE','/RUN',name,'1',f'/CYCLE/STOP/{end_time:.12E}',f'/ANIM/DT/{dtout:.12E}','/ANIM/ELEM/STRAIN','/ANIM/BRICK/STRAIN','/ANIM/NODA/VEL','/END'])+'\n',encoding='ascii'); return p
