from bdf2rad.core.plugin_helpers import rb,emit
from collections import defaultdict

def translate(model,ctx,plugin):
    return _emit(model,ctx,plugin,8,'BRICK')

def _emit(model,ctx,plugin,n,typ):
    groups=defaultdict(list)
    for e in model.elements.values():
        if e.typ=='CHEXA' and len(e.nodes)==n: groups[e.pid].append(e)
    blocks=[]; audit=[]
    for pid,els in sorted(groups.items()):
        part=ctx.metadata.get('part_map',{}).get((pid,'BRICK'),pid)
        rows=[f'{e.eid:>10d}'+''.join(f'{x:>10d}' for x in e.nodes[:8]) for e in sorted(els,key=lambda x:x.eid)]
        blocks.append(rb(plugin,f'/BRICK/{part}',emit(plugin,{'PART':part,'ROWS':'\n'.join(rows)})))
        audit.append({'card':'CHEXA','order':8,'status':'translated','target':f'/BRICK/{part}','count':len(els),'source_pid':pid})
    return blocks,audit
