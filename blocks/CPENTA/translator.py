from bdf2rad.core.plugin_helpers import rb,emit

def cpenta15_to_bric20(n):
    if len(n)!=15: raise ValueError('CPENTA15 requires 15 nodes')
    a,b,c,d,e,f,m12,m23,m31,m45,m56,m64,m14,m25,m36=n
    return [a,b,c,c,d,e,f,f,m12,m23,c,m31,m45,m56,f,m64,m14,m25,m36,f]

def translate(model,ctx,plugin):
    groups={}
    for e in model.elements.values():
        if e.typ=='CPENTA': groups.setdefault(e.pid,[]).append(e)
    blocks=[];audit=[]
    for pid,els in sorted(groups.items()):
        part=ctx.metadata.get('part_map',{}).get((pid,'BRIC20_DEGENERATED'),3000000+pid);rows=[]
        for e in sorted(els,key=lambda x:x.eid):
            if len(e.nodes)==15:
                ns=cpenta15_to_bric20(e.nodes)
                rows += [f'{e.eid:>10d}'+''.join(f'{x:>10d}' for x in ns[:8]), ''.join(f'{x:>10d}' for x in ns[8:16]), ''.join(f'{x:>10d}' for x in ns[16:20])]
            elif len(e.nodes)==6:
                a,b,c,d,e1,f=e.nodes;ns=[a,b,c,c,d,e1,f,f];rows.append(f'{e.eid:>10d}'+''.join(f'{x:>10d}' for x in ns))
            else: raise ValueError(f'Unsupported CPENTA node count: {len(e.nodes)}')
        blocks.append(rb(plugin,f'/BRIC20/{part}',emit(plugin,{'PART':part,'ROWS':'\n'.join(rows)})))
        audit.append({'card':'CPENTA','status':'translated_degenerate_brick','target':f'/BRIC20/{part}','count':len(els),'note':'Topology transform implemented; solver-side orientation still needs engineering validation.'})
    return blocks,audit
