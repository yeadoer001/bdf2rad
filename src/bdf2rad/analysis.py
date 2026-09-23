"""Full streaming inventory and case-control inheritance; no implied mapping."""
from collections import Counter, defaultdict
from dataclasses import asdict
import json
import re
from .parser import BDFParser, nastran_float
from .paths import writable_path
from .audit import REASONS

SELECTIONS = {'SPC':('SPC','SPC1','SPCADD'), 'LOAD':('LOAD','FORCE','GRAV','MOMENT','PLOAD','PLOAD2','PLOAD4'),
              'IC':('TIC',), 'BCSET':('BCTSET','BCTADD'), 'BGSET':('BGSET','BGADD'),
              'TSTEP':('TSTEP','TSTEP1'), 'NLCNTL':('NLCNTL','NLCNTL2'), 'TEMP(INIT)':('TEMPD','TEMP')}
UNIONS = {'BCTADD': ('BCTSET','BCTADD'), 'BGADD':('BGSET','BGADD'), 'SPCADD':('SPC','SPC1','SPCADD')}


def case_control(lines):
    global_values, subcases, diagnostics = {}, {}, []
    scope = global_values
    solution = None
    for loc, raw in lines:
        text = raw.split('$',1)[0].strip()
        match = re.match(r'SOL\s+(\d+)', text, re.I)
        if match:
            solution = int(match[1])
        match = re.fullmatch(r'SUBCASE\s+(\d+)', text, re.I)
        if match:
            key = match[1]
            if key in subcases:
                diagnostics.append({'code':'DUPLICATE_SUBCASE', 'source':asdict(loc), 'id':key})
            scope = subcases.setdefault(key,{})
        elif '=' in text and not text.upper().startswith('NASTRAN '):
            key,value = text.split('=',1)
            key = re.sub(r'\s+', '', key.upper())
            scope[key] = {'value':value.strip(), 'source':asdict(loc)}
    effective = {key:{**global_values,**values} for key,values in subcases.items()}
    return {'solution':solution, 'global':global_values, 'subcases':subcases,
            'effective_subcases':effective or {'GLOBAL':dict(global_values)}, 'diagnostics':diagnostics}


def analyze(source, output, encoding='gb18030'):
    output = writable_path(output)
    output.mkdir(parents=True,exist_ok=True)
    if (output/'analysis.json').exists() or (output/'unmapped_cards.jsonl').exists():
        raise FileExistsError('Use a fresh output directory; existing analysis is preserved')
    counts, orders = Counter(), Counter()
    first, ids, unions, controls = {}, defaultdict(set), {}, []
    selected_cards = {x for values in SELECTIONS.values() for x in values}
    reader = BDFParser(encoding=encoding)
    diagnostics = []
    parsed = False
    try:
        with (output/'unmapped_cards.jsonl').open('w',encoding='utf-8') as records:
            for card in reader.parse(source):
                name, fields = card.name, card.fields
                counts[name] += 1
                first.setdefault(name,asdict(card.source))
                records.write(json.dumps(asdict(card),ensure_ascii=False)+'\n')
                if name in ('CTETRA','CHEXA','CPENTA'):
                    orders[f'{name}{sum(bool(x) for x in fields[2:])}'] += 1
                if name in selected_cards:
                    try:
                        sid = int(fields[0]); ids[name].add(sid)
                        if name in UNIONS:
                            key = (name,sid)
                            if key in unions:
                                diagnostics.append({'code':'DUPLICATE_SET_UNION','card':name,'id':sid,'source':asdict(card.source)})
                            unions[key] = [int(x) for x in fields[1:] if x]
                    except (ValueError,IndexError) as exc:
                        diagnostics.append({'code':'INVALID_SET_ID','card':name,'source':asdict(card.source),'message':str(exc)})
                if name in ('NLCNTLG','NLCNTL2','TSTEP1'):
                    item = asdict(card)
                    item['mapping_status'] = 'REQUIRES_VALIDATION'
                    if name in ('NLCNTLG','NLCNTL2'):
                        tokens = [x for x in fields[(1 if name == 'NLCNTL2' else 0):] if x]
                        item['parameters'] = [{'name':tokens[i], 'raw_value':tokens[i+1] if i+1<len(tokens) else None}
                                              for i in range(0,len(tokens),2)]
                        if len(tokens)%2:
                            diagnostics.append({'code':'UNPAIRED_CONTROL_PARAMETER','source':asdict(card.source),'card':name})
                    if name == 'TSTEP1':
                        try:
                            item['end_time_candidate'] = nastran_float(fields[1])
                        except (ValueError,IndexError):
                            item['end_time_candidate'] = None
                    controls.append(item)
        parsed = True
    except (ValueError,OSError,UnicodeError) as exc:
        diagnostics.append({'code':'PARSE_FAILED','message':str(exc)})
    cases = case_control(reader.control_lines)
    diagnostics.extend(cases['diagnostics'])

    def resolve(names,sid,trail=()):
        matches = [(name,sid) for name in names if sid in ids[name]]
        if not matches:
            return {'id':sid,'status':'MISSING','expected':names}
        branches=[]
        for key in matches:
            if key in trail:
                branches.append({'card':key[0],'id':sid,'status':'CYCLE'})
            elif len(trail) >= 100:
                branches.append({'card':key[0],'id':sid,'status':'DEPTH_LIMIT'})
            elif key in unions:
                branches.append({'card':key[0],'id':sid,'children':[resolve(UNIONS[key[0]], child, (*trail,key)) for child in unions[key]]})
            else:
                branches.append({'card':key[0],'id':sid,'status':'FOUND_NOT_MAPPED'})
        return {'id':sid,'definitions':branches}

    selected={}
    for subcase, values in cases['effective_subcases'].items():
        selected[subcase]={}
        for key,names in SELECTIONS.items():
            if key in values:
                try:
                    selected[subcase][key] = resolve(names,int(values[key]['value']))
                except ValueError:
                    selected[subcase][key] = {'status':'UNRESOLVED_EXPRESSION','raw':values[key]}
    blockers = [{'card':name,'count':count,'first_source':first[name],
                 'status':'REQUIRES_VALIDATION' if name in ('NLCNTLG','NLCNTL2','TSTEP1','GRID') else 'UNSUPPORTED',
                 'reason':REASONS.get(name,'Full-model semantic mapping not implemented; original preserved.')}
                for name,count in counts.items()]
    def find_selection_issues(value, path):
        if isinstance(value,dict):
            if value.get('status') in ('MISSING','CYCLE','DEPTH_LIMIT','UNRESOLVED_EXPRESSION'):
                diagnostics.append({'code':'SELECTION_'+value['status'],'path':path,'details':value})
            for key,child in value.items():
                find_selection_issues(child,path+'/'+str(key))
        elif isinstance(value,list):
            for i,child in enumerate(value):
                find_selection_issues(child,path+'/'+str(i))
    find_selection_issues(selected,'subcases')
    report={'status':'ANALYZED_NOT_CONVERTED' if parsed else 'PARSE_FAILED',
            'source':str(source), 'encoding':encoding, 'counts':dict(counts), 'element_orders':dict(orders),
            'case_control':cases, 'selected_definitions':selected, 'nonlinear_and_time_controls':controls,
            'diagnostics':diagnostics, 'mapping_blockers':blockers,
            'conversion_success':False, 'solver_launch_allowed':False,
            'termination_time':None, 'note':'No explicit solver time selected automatically; no executable RAD emitted.'}
    (output/'analysis.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    md=['# Full-model analysis', '',f"Status: {report['status']}",f"SOL: {cases['solution']}",
        '', 'No runnable RAD published. Implicit controls are not explicit controls.', '',
        '| Card | Count | Status | First line |', '|---|---:|---|---:|']
    md += [f"| {b['card']} | {b['count']} | {b['status']} | {b['first_source']['line']} |" for b in blockers]
    md += ['', '## Effective subcase selections', '']
    for sid,values in cases['effective_subcases'].items():
        md += [f"Subcase {sid}: " + ', '.join(f"{key}={values[key]['value']}" for key in SELECTIONS if key in values)]
    md += ['', '## Required implementation order', '',
           '1. Verified high-order topology and solid formulation; retain all midside nodes.',
           '2. Joint MAT1/MATS1 mapping, thermal semantics, PSOLID and Part assignment.',
           '3. BSURFS face topology and distinct glue/contact mapping with selected sets.',
           '4. RBE weighting/DOFs, CONM2 inertia, selected SPC/TIC/GRAV and units.',
           '5. Explicit timing decision, Starter/Engine execution and independent physical checks.',
           '', 'These mappings remain unimplemented. This report does not convert or validate them.']
    (output/'ANALYSIS.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    return report
