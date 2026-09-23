from collections import defaultdict
from bdf2rad.core.plugin_helpers import emit,rb,fi

def _family(e):
    if e.typ=='CHEXA' and len(e.nodes)==8:return 'BRICK'
    if e.typ=='CHEXA' and len(e.nodes)==20:return 'BRICK'
    if e.typ=='CTETRA' and len(e.nodes)==10:return 'TETRA10'
    if e.typ=='CTETRA' and len(e.nodes)==4:return 'TETRA4'
    if e.typ=='CPENTA':return 'BRIC20_DEGENERATED'
    return 'UNSUPPORTED'

def translate(model,ctx,plugin):
    fams=defaultdict(list)
    for e in model.elements.values(): fams[(e.pid,_family(e))].append(e)
    part_map={};blocks=[];audit=[];next_id=100000
    for (pid,fam),els in sorted(fams.items()):
        if fam=='UNSUPPORTED': continue
        same_pid_families={k for k in fams if k[0]==pid}
        part_id=pid if len(same_pid_families)==1 else next_id
        if len(same_pid_families)>1: next_id+=1
        part_map[(pid,fam)]=part_id
        prop=model.props.get(pid);mid=prop.mid if prop else 0
        vals={'ID':part_id,'TITLE':f'BDF_PART_{pid}_{fam}','PROP':fi(pid),'MAT':fi(mid),'SUBSET':fi(0),'THICK':fi(0)}
        blocks.append(rb(plugin,f'/PART/{part_id}',emit(plugin,vals),order=35))
        audit.append({'card':'PSOLID','source_pid':pid,'family':fam,'status':'translated','target':f'/PART/{part_id}'})
    ctx.metadata['part_map']=part_map
    return blocks,audit
