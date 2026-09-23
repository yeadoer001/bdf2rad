from collections import defaultdict
from bdf2rad.core.plugin_helpers import emit,rb,dof6

def translate(model,ctx,plugin):
    sid=int(model.case.get('SPC','0') or 0);groups=defaultdict(list)
    for s in model.spcs:
        if s.sid==sid:groups[dof6(s.comp)].append(s.nid)
    blocks=[];audit=[];gid=400000
    for code,ids in sorted(groups.items()):
        block_lines=emit(plugin,{'GRID':gid,'CODE':code,'GROUP_TITLE':f'SPC_{code}','NODE_ROWS':'\n'.join(f'{x:>10d}' for x in sorted(set(ids))), 'NODE':'','ID':gid,'TITLE':f'SPC_{code}','TRAROT':code,'SKEW':f'{0:>10d}','GRND':f'{gid:>10d}'})
        blocks.append(rb(plugin,f'/BCS/{gid}',block_lines,source_cards=('SPC',)))
        audit.append({'card':'SPC','status':'translated','target':f'/BCS/{gid}','count':len(set(ids))})
        gid+=1
    return blocks,audit
