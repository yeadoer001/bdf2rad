"""Resolve selected source sets without activating inactive definitions."""
from collections import Counter

def resolve(ir):
    cases=ir.metadata['case_control']['effective_subcases']
    errors=[]
    if len(cases)!=1:
        return {'errors':['Exactly one effective subcase is currently supported'],'selected':{},'counts':{}}
    case=next(iter(cases.values())); selected={}
    for key in ('SPC','IC','LOAD','BCSET','BGSET','TSTEP','TEMP(INIT)'):
        if key in case:
            try: selected[key]=int(case[key]['value'])
            except ValueError: errors.append(f'Unresolved selection {key}: {case[key]["value"]}')
    def leaves(table,sid,union,trail=()):
        if sid in trail:
            errors.append(f'{union} cycle at {sid}'); return []
        e=table.get(sid)
        if e is None:
            errors.append(f'Missing {union} set {sid}'); return []
        if e.data['type']!=union: return [sid]
        result=[]
        for value in e.data['raw'][1:]:
            if value: result.extend(leaves(table,int(value),union,(*trail,sid)))
        return list(dict.fromkeys(result))
    contacts=leaves(ir.contacts,selected['BCSET'],'BCTADD') if 'BCSET' in selected else []
    glue=leaves(ir.glue_interfaces,selected['BGSET'],'BGADD') if 'BGSET' in selected else []
    spc=[e for e in ir.boundary_conditions.values() if e.provenance.source_id==selected.get('SPC')]
    tic=[e for e in ir.initial_conditions.values() if e.provenance.source_id==selected.get('IC')]
    for key,values in (('SPC',spc),('IC',tic)):
        if key in selected and not values: errors.append(f'Missing selected {key} {selected[key]}')
    velocity={}
    for e in tic:
        d=e.data; nid=d['node']
        if nid not in ir.nodes: errors.append(f'TIC missing node {nid}')
        if d['displacement']!=0: errors.append(f'TIC nonzero displacement at {nid}')
        if d['dof'] not in ('1','2','3'):
            errors.append(f'TIC unsupported DOF {d["dof"]}'); continue
        vector=velocity.setdefault(nid,{})
        component=int(d['dof'])-1
        if component in vector and vector[component]!=d['velocity']: errors.append(f'TIC conflicting velocity at {nid}')
        vector[component]=d['velocity']
    clusters=Counter(tuple(v.get(i,0.) for i in range(3)) for v in velocity.values())
    gravity=ir.gravity.get(selected.get('LOAD'))
    if 'LOAD' in selected and gravity is None: errors.append(f'Unresolved LOAD {selected["LOAD"]}; load combinations require mapping')
    timing=[e for e in ir.analysis_controls.get('TSTEP1',[]) if e.provenance.source_id==selected.get('TSTEP')]
    from .parser import nastran_float
    end=nastran_float(timing[0].data['raw'][1]) if len(timing)==1 else None
    if 'TSTEP' in selected and end is None: errors.append('Unresolved selected TSTEP1')
    return {'selected':selected,'errors':errors,'contacts':contacts,'glue':glue,'termination_time':end,
            'counts':{'SPC':len(spc),'TIC':len(tic),'BCTSET':len(contacts),'BGSET':len(glue),'GRAV':int(gravity is not None)},
            'initial_velocity_clusters':[{'vector':list(v),'node_count':n} for v,n in sorted(clusters.items())],
            'gravity_vector':[gravity.data['scale']*x for x in gravity.data['vector']] if gravity else None}
