from bdf2rad.core.plugin_helpers import emit,rb,fs,fi

def translate(model,ctx,plugin):
    # Type 0 represents a nodal mass group; one group per CONM2 avoids inventing a mass aggregation rule.
    blocks=[];audit=[];gid=440000
    for eid,m in sorted(model.masses.items()):
        lines=emit(plugin,{'ID':eid,'TITLE':f'CONM2_{eid}','MASS':fs(m.mass),'GRND':fi(gid)})
        lines += [f'/GRNOD/NODE/{gid}',f'CONM2_{eid}_NODE',fi(m.nid)]
        blocks.append(rb(plugin,f'/ADMAS/0/{eid}',lines,source_cards=('CONM2',)));audit.append({'card':'CONM2','id':eid,'status':'translated','target':f'/ADMAS/0/{eid}'})
        gid+=1
    return blocks,audit
