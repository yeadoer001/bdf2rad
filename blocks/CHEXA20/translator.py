from bdf2rad.core.plugin_helpers import rb,emit
from collections import defaultdict

def translate(model,ctx,plugin):
    groups=defaultdict(list)
    for e in model.elements.values():
        if e.typ=='CHEXA' and len(e.nodes)==20: groups[e.pid].append(e)
    blocks=[];audit=[]
    for pid,els in sorted(groups.items()):
        part=ctx.metadata.get('part_map',{}).get((pid,'BRIC20'),1000000+pid)
        rows=[]
        for e in sorted(els,key=lambda x:x.eid):
            ns=e.nodes[:20]
            rows.append(f'{e.eid:>10d}'+''.join(f'{x:>10d}' for x in ns[:8]))
            rows.append(''.join(f'{x:>10d}' for x in ns[8:16]))
            rows.append(''.join(f'{x:>10d}' for x in ns[16:20]))
        blocks.append(rb(plugin,f'/BRIC20/{part}',emit(plugin,{'PART':part,'ROWS':'\n'.join(rows)})))
        audit.append({'card':'CHEXA','order':20,'status':'translated','target':f'/BRIC20/{part}','count':len(els),'source_pid':pid})
    return blocks,audit
