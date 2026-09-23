from bdf2rad.core.plugin_helpers import emit,rb,fi
from bdf2rad.core.plugin_helpers import faces_for_element

def translate(model,ctx,plugin):
    blocks=[];audit=[];surface_group={};gid=450000
    for sid,s in sorted(model.bsurfs.items()):
        seg_rows=[];all_nodes=set();seg_id=1
        for eid,g1,g2,g3 in s.faces:
            face=resolve_face(model,eid,g1,g2,g3)
            if face is None:
                audit.append({'card':'BSURFS','id':sid,'status':'error','reason':'source element/face nodes could not be resolved','eid':eid,'nodes':[g1,g2,g3]});continue
            all_nodes.update(face)
            vals=[fi(seg_id),fi(face[0]),fi(face[1]),fi(face[2])]
            if len(face)==4: vals.append(fi(face[3]))
            seg_rows.append(''.join(vals));seg_id+=1
        if not seg_rows: continue
        lines=emit(plugin,{'ID':sid,'TITLE':f'BSURFS_{sid}','ROWS':'\n'.join(seg_rows),'GRID':gid,'GROUP_TITLE':f'BSURFS_{sid}_NODES','NODE_ROWS':'\n'.join(f'{x:>10d}' for x in sorted(all_nodes))})
        blocks.append(rb(plugin,f'/SURF/SEG/{sid}',lines,source_cards=('BSURFS',)))
        surface_group[sid]=gid;gid+=1
        audit.append({'card':'BSURFS','id':sid,'status':'translated','target':f'/SURF/SEG/{sid}','segments':len(seg_rows),'group':surface_group[sid]})
    ctx.metadata['surface_group']=surface_group
    return blocks,audit

def resolve_face(model,eid,g1,g2,g3):
    e=model.elements.get(eid)
    if e is None:return None
    wanted={g1,g2,g3}
    for f in faces_for_element(e):
        if wanted.issubset(set(f)): return f
    return None
