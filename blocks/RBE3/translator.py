from bdf2rad.core.plugin_helpers import emit,rb,fi,fs,dof6

def translate(model,ctx,plugin):
    blocks=[];audit=[];gid=430000
    for rid,r in sorted(model.rbe3.items()):
        rows=f'{fs(r.weight)}{dof6(r.ind_comp)}{fi(0)}{fi(gid)}'
        lines=emit(plugin,{'GRID':gid,'ID':rid,'NODE_ROWS':'\n'.join(f'{x:>10d}' for x in sorted(set(r.independent))), 'TITLE':f'RBE3_{rid}','NODE':fi(r.ref),'TRAROT':dof6(r.ref_comp),'NSET':fi(1),'IMOD':fi(1),'IFORM':fi(1),'ROWS':rows})
        blocks.append(rb(plugin,f'/RBE3/{rid}',lines,source_cards=('RBE3',)))
        audit.append({'card':'RBE3','status':'translated','target':f'/RBE3/{rid}','set_count':1,'note':'Iform=1 follows official default; verify source kinematic semantics.'})
        gid+=1
    return blocks,audit
