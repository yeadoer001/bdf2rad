from bdf2rad.core.plugin_helpers import emit,rb

def translate(model,ctx,plugin):
    rows=[]
    for n in sorted(model.nodes.values(),key=lambda x:x.nid):
        rows.append(f'{n.nid:>10d}{n.xyz[0]:>20.12E}{n.xyz[1]:>20.12E}{n.xyz[2]:>20.12E}')
    return [rb(plugin,'/NODE',emit(plugin,{'ROWS':'\n'.join(rows)}))],[{'card':'GRID','status':'translated','count':len(rows),'target':'/NODE'}]
