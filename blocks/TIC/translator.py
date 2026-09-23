from collections import defaultdict
from bdf2rad.core.plugin_helpers import emit,rb,fs,fi,bdf_velocity_to_rad_mm_ms

def translate(model,ctx,plugin):
    sid=int(model.case.get('IC','0') or 0);groups=defaultdict(list)
    for t in model.tics:
        if t.sid==sid and t.velocity is not None and t.dof in (1,2,3):groups[(t.dof,t.velocity)].append(t.nid)
    blocks=[];audit=[];gid=410000
    for (dof,v),ids in sorted(groups.items()):
        vv=bdf_velocity_to_rad_mm_ms(v);vx=vv if dof==1 else 0.0;vy=vv if dof==2 else 0.0;vz=vv if dof==3 else 0.0
        lines=emit(plugin,{'GRID':gid,'DOF':dof,'GROUP_TITLE':f'IC_VELOCITY_{dof}','NODE_ROWS':'\n'.join(f'{x:>10d}' for x in sorted(set(ids))), 'ID':gid,'TITLE':f'Initial velocity DOF {dof}','VX':fs(vx),'VY':fs(vy),'VZ':fs(vz),'GRND':fi(gid),'SKEW':fi(0),'TSTART':fs(0.0),'SENS':fi(0)})
        blocks.append(rb(plugin,f'/INIVEL/TRA/{gid}',lines,source_cards=('TIC',)))
        audit.append({'card':'TIC','status':'translated','target':f'/INIVEL/TRA/{gid}','count':len(set(ids)),'velocity_source':v,'velocity_target_mm_ms':vv})
        gid+=1
    return blocks,audit
