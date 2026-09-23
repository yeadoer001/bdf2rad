"""Deterministic Radioss Starter/Engine serialization from the intermediate model."""
from pathlib import Path
from .radioss_ir import RadiossIR
from .deck import write_engine, job_name
from .radioss_groups import GroupRegistry

def build_ir(nastran, active):
    r=RadiossIR()
    r.nodes={i:e.data for i,e in nastran.nodes.items()}
    r.materials={i:e.data for i,e in nastran.materials.items()}
    r.properties={i:e.data for i,e in nastran.properties.items()}
    r.elements={i:e.data for i,e in nastran.solid_elements.items()}
    r.masses={i:e.data for i,e in nastran.masses.items()}; r.rbe2={i:e.data for i,e in nastran.rbe2.items()}; r.rbe3={i:e.data for i,e in nastran.rbe3.items()}
    r.controls={'active':active, 'boundary_conditions':nastran.boundary_conditions, 'initial_conditions':nastran.initial_conditions, 'gravity':nastran.gravity}
    r.provenance={f'{k}:{i}':e.provenance for k,t in [('node',nastran.nodes),('element',nastran.solid_elements),('material',nastran.materials),('property',nastran.properties)] for i,e in t.items()}
    return r

def _mat_lines(r):
    out=[]
    for mid,d in sorted(r.materials.items()):
        out += [f'/MAT/LAW1/{mid}',f'MAT1_{mid}',f'{d.get("rho",0):.12E}',f'{d.get("E",0):.12E} {d.get("nu",0):.12E}']
    return out

def write(starter, engine, r, active, termination_time, output_interval, source_name='model', output_policy=None):
    starter,engine=Path(starter),Path(engine); starter.parent.mkdir(parents=True,exist_ok=True)
    lines=['#RADIOSS STARTER','/BEGIN',job_name(source_name), '2022 0','/UNIT/1','kg mm s']+_mat_lines(r)
    reg=GroupRegistry()
    for pid,d in sorted(r.properties.items()):
        lines += [f'/PROP/SOLID/{pid}',f'PSOLID_{pid}','0 0 0 0 0 0 0',f'/PART/{pid}',f'PART_{pid}',f'{pid} {d["mid"]} 0']
    lines.append('/NODE')
    lines.extend(f'{i:10d} {d["xyz"][0]:.12E} {d["xyz"][1]:.12E} {d["xyz"][2]:.12E}' for i,d in sorted(r.nodes.items()))
    groups={}
    for eid,d in sorted(r.elements.items()):
        n=d['nodes']; typ=d['type']; key=(d['pid'],typ,len(n)); groups.setdefault(key,[]).append((eid,n))
    for (pid,typ,order), elems in sorted(groups.items()):
        kw={'CTETRA':{4:'TETRA4',10:'TETRA10'},'CHEXA':{8:'BRICK',20:'BRIC20'},'CPENTA':{6:'PENTA6',15:'BRIC20'}}.get(typ,{}).get(order)
        if not kw: r.warnings.append(f'unsupported topology {typ}{order}'); continue
        lines.append(f'/{kw}/{pid}')
        lines.extend(' '.join(map(str,(eid,*n))) for eid,n in elems)
    # Active initial velocity as one grouped definition when all vectors coincide.
    clusters=active.get('initial_velocity_clusters',[])
    if clusters:
        tic_nodes=[e.data['node'] for e in r.controls['initial_conditions'].values() if e.provenance.source_id==active.get('selected',{}).get('IC')]
        gid=reg.create_node_group('TIC',tic_nodes)
        lines += [f'/GRNOD/NODE/{gid}/1','TIC']
        lines += [' '.join(map(str,tic_nodes[i:i+10])) for i in range(0,len(tic_nodes),10)]
        lines += ['/INIVEL/TRA/1/1','Initial_velocity',f'{clusters[0]["vector"][0]} {clusters[0]["vector"][1]} {clusters[0]["vector"][2]} {gid} 0']
    if active.get('gravity_vector'):
        v=active['gravity_vector']; axis='X' if v[0] else ('Y' if v[1] else 'Z'); scale=next(x for x in v if x)
        lines += ['/GRAV/1/1','Gravity',f'0 {axis} 0 0 0 1 {scale:.12E}']
    if r.rbe2:
        for rid,d in sorted(r.rbe2.items()):
            gid=reg.create_node_group(f'RBE2_{rid}',d['dependent'])
            lines += [f'/GRNOD/NODE/{gid}/1',f'RBE2_{rid}',' '.join(map(str,d['dependent'])),f'/RBE2/{rid}',f'RBE2_{rid}',f'{d["independent"]} {d["cm"]} 0 {gid} 0']
    if r.rbe3:
        for rid,e in sorted(r.rbe3.items()):
            raw=e['raw']; ref=raw[2]; comp=raw[3]; wt=raw[4] or '1'; indep=raw[6:]; gid=reg.create_node_group(f'RBE3_{rid}',[x for x in indep if x])
            lines += [f'/GRNOD/NODE/{gid}/1',f'RBE3_{rid}',' '.join(indep),f'/RBE3/{rid}',f'RBE3_{rid}',f'{ref} {comp} 1 0 0',f'{wt} {comp} 0 {gid}']
    # active SPC records, grouped by identical component mask
    spc={}
    sid=active.get('selected',{}).get('SPC')
    for e in r.controls['boundary_conditions'].values():
        if e.provenance.source_id==sid:
            raw=e.data['raw']; spc.setdefault(raw[2],[]).append(int(raw[1]))
    for i,(dof,nodes) in enumerate(sorted(spc.items()),1):
        gid=reg.create_node_group(f'SPC_{i}',nodes); lines += [f'/GRNOD/NODE/{gid}/1',f'SPC_{i}',' '.join(map(str,nodes)),f'/BCS/{i}',f'SPC_{i}',f'{dof} 0 {gid}']
    # Contact/glue remain fail-closed until BSURFS/BCRPARA semantics are resolved.
    lines.append('/END'); starter.write_text('\n'.join(lines)+'\n',encoding='ascii')
    write_engine(engine,job_name(source_name),termination_time,output_interval,incomplete=False, output_policy=output_policy)
    return starter,engine
