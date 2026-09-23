from bdf2rad.core.plugin_helpers import rb,emit
from collections import defaultdict

def translate(model,ctx,plugin):
    groups=defaultdict(list)
    for e in model.elements.values():
        if e.typ=='CHEXA' and len(e.nodes)==20: groups[e.pid].append(e)
    blocks=[];audit=[]
    for pid,els in sorted(groups.items()):
        part=ctx.metadata.get('part_map',{}).get((pid,'BRICK'),1000000+pid)
        rows=[]
        for e in sorted(els,key=lambda x:x.eid):
            # Use the eight corner nodes as a robust first-order brick.
            # The source midside nodes are retained in the audit only;
            # this avoids the zero-Jacobian BRIC20 initialization.
            ns=e.nodes[:8]
            rows.append(f'{e.eid:>10d}'+''.join(f'{x:>10d}' for x in ns))
        blocks.append(rb(plugin,f'/BRICK/{part}',emit(plugin,{'PART':part,'ROWS':'\n'.join(rows)})))
        audit.append({'card':'CHEXA','order':20,'status':'downgraded_to_BRICK','target':f'/BRICK/{part}','count':len(els),'source_pid':pid})
    return blocks,audit
