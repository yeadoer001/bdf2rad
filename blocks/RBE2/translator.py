from bdf2rad.core.plugin_helpers import emit,rb,fi,dof6

def translate(model,ctx,plugin):
    blocks=[];audit=[];gid=420000
    for rid,r in sorted(model.rbe2.items()):
        lines=emit(plugin,{'GRID':gid,'ID':rid,'NODE_ROWS':'\n'.join(f'{x:>10d}' for x in sorted(set(r.dependent))), 'TITLE':f'RBE2_{rid}','NODE':fi(r.independent),'TRAROT':dof6(r.cm),'SKEW':fi(0),'GRND':fi(gid),'FLAG':fi(0)})
        blocks.append(rb(plugin,f'/RBE2/{rid}',lines,source_cards=('RBE2',)))
        audit.append({'card':'RBE2','status':'translated','target':f'/RBE2/{rid}','dependent_count':len(set(r.dependent))})
        gid+=1
    return blocks,audit
