def validate(ir):
    issues=[]
    node_ids=set(ir.nodes)
    for eid,e in ir.solid_elements.items():
        if e.data['pid'] not in ir.properties: issues.append(f'element {eid} missing property {e.data["pid"]}')
        missing=[n for n in e.data['nodes'] if n not in node_ids]
        if missing: issues.append(f'element {eid} missing nodes {missing[:5]}')
    for pid,p in ir.properties.items():
        if p.data['mid'] not in ir.materials: issues.append(f'property {pid} missing material {p.data["mid"]}')
    for n,e in ir.nodes.items():
        if e.data['cp'] or e.data['cd']: issues.append(f'coordinate system on GRID {n} requires transform')
    for mid,e in ir.plasticity.items():
        if str(e.data.get('type','')).upper() not in ('PLASTIC',''): issues.append(f'unsupported MATS1 type on {mid}')
    return issues
