from bdf2rad.core.plugin_helpers import rb,emit
from collections import defaultdict

def translate(model,ctx,plugin):
    groups=defaultdict(list)
    for e in model.elements.values():
        if e.typ=='CTETRA' and len(e.nodes)==10: groups[e.pid].append(e)
    blocks=[];audit=[]
    for pid,els in sorted(groups.items()):
        part=ctx.metadata.get('part_map',{}).get((pid,'TETRA10'),2000000+pid)
        rows=[]
        for e in sorted(els,key=lambda x:x.eid):
            rows.append(f'{e.eid:>10d}')
            rows.append(''.join(f'{x:>10d}' for x in e.nodes[:10]))
        blocks.append(rb(plugin,f'/TETRA10/{part}',emit(plugin,{'PART':part,'ROWS':'\n'.join(rows)})))
        audit.append({'card':'CTETRA','order':10,'status':'translated','target':f'/TETRA10/{part}','count':len(els),'source_pid':pid})
    return blocks,audit
