from collections import Counter

def validate(src,data):
    errors=[]; warnings=list(data['warnings'])
    nids=set(src.nodes)
    for e in data['elements']:
        missing=[n for n in e['nodes'] if n not in nids]
        if missing: errors.append(f'element {e["eid"]} missing nodes {missing[:8]}')
    for p in data['properties']:
        if p['mid'] not in src.mats: errors.append(f'PSOLID {p["pid"]} references missing MAT1 {p["mid"]}')
    if len(data['elements']) != len(src.elements): errors.append(f'only {len(data["elements"])}/{len(src.elements)} elements translated')
    if any(d['cp'] or d['cd'] for d in src.nodes.values()): warnings.append('Nonzero GRID CP/CD present; coordinate transformation is not implemented in V1')
    return errors,warnings
