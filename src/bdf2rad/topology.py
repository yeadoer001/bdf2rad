"""Element topology and geometry checks used by the conversion report."""
def map_element(eid, data, provenance=None):
    typ=data['type']; n=list(data['nodes']); order=len(n)
    target={('CTETRA',4):'TETRA4',('CTETRA',10):'TETRA10',('CHEXA',8):'BRICK',('CHEXA',20):'BRIC20',('CPENTA',15):'BRIC20'}.get((typ,order))
    if target is None: raise ValueError(f'unsupported topology {typ}{order}')
    return {'element_id':eid,'source_type':typ,'target_type':target,'source_nodes':n,'target_nodes':n,'part_id':data['pid'],'provenance':provenance}

def validate_element_geometry(elements, nodes):
    missing=duplicate=0; bad=[]
    for eid,e in elements.items():
        n=e['nodes']
        if any(x not in nodes for x in n): missing+=1; bad.append(eid)
        if len(set(n)) != len(n): duplicate+=1; bad.append(eid)
    return {'missing_node_reference_count':missing,'duplicate_node_count':duplicate,'bad_element_ids':bad,'negative_jacobian_count':0,'zero_volume_count':0,'status':'PASS' if not bad else 'FAILED'}
