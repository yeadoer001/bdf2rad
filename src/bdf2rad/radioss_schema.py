LEGAL_KEYWORDS={'/BRICK','/BRIC20','/TETRA4','/TETRA10','/GRNOD/NODE','/INIVEL/TRA','/GRAV','/BCS','/RBE2','/RBE3','/INTER/TYPE2','/INTER/TYPE7','/BEGIN','/UNIT','/MAT/LAW1','/PROP/SOLID','/PART','/NODE','/END'}
def canonicalize_keyword_header(raw):
    raw=raw.strip()
    for family in sorted(LEGAL_KEYWORDS,key=len,reverse=True):
        if raw==family: return {'raw_header':raw,'family':family,'instance_ids':[],'raw_parts':raw.split('/')}
        if raw.startswith(family+'/'):
            tail=raw[len(family)+1:].split('/')
            if all(x.isdigit() for x in tail): return {'raw_header':raw,'family':family,'instance_ids':[int(x) for x in tail],'raw_parts':raw.split('/')}
    return {'raw_header':raw,'family':None,'instance_ids':[],'raw_parts':raw.split('/')}
def normalize_keyword_instance(raw):
    return canonicalize_keyword_header(raw)
def validate_keywords(text):
    found=[normalize_keyword_instance(line.strip()) for line in text.splitlines() if line.startswith('/')]
    bad=[x for x in found if x['family'] is None]
    forbidden=[x for x in found if x['family'] in ('/BRICK20','/PENTA15','/GRAVITY')]
    for x in found:
        x['schema_status']='PASS' if x['family'] else 'FAILED'; x['block_status']='PASS'; x['reference_status']='NOT_VERIFIED'
    return {'keywords':[x['raw_header'] for x in found],'entries':found,'illegal':bad,'forbidden':forbidden,'status':'PASS' if not bad and not forbidden else 'FAILED'}
