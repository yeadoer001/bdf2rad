"""Full-model preflight and evidence report. No success without solver evidence."""
import json
from collections import Counter
from pathlib import Path
from .semantic import scan
from .validator import validate
from .active_case import resolve
from .paths import writable_path
from .radioss_writer import build_ir, write as write_radioss
from .topology import validate_element_geometry
from .radioss_schema import validate_keywords
from .mass import structural_mass
from .radioss_parser import parse_generated_rad


def convert(source, output, encoding='gb18030', termination_time=3e-3, output_interval=3e-5, *, output_policy=None):
    output=writable_path(output, output_policy)
    report_path=writable_path(output.parent/'conversion_report.json', output_policy)
    output.parent.mkdir(parents=True,exist_ok=True)
    report={'status':'INCOMPLETE','source':str(source),'units':{'mass':'kg','length':'mm','time':'s','force':'mN'},
            'card_counts':{},'mappings':{},'approximations':[],'not_transferred':[],'unsupported_active':[],
            'node_check':{},'element_check':{},'material_check':{},'mass_check':{},'constraint_check':{},
            'initial_condition_check':{},'contact_check':{},'reference_check':{},'model_counts':{},'target_entity_counts':{},
            'starter':{'status':'NOT_RUN','reason':'No validated target model'},'engine':{'status':'NOT_RUN','reason':'Starter not passed'},'warnings':[]}
    try:
        ir=scan(source,encoding); issues=validate(ir); active=resolve(ir)
        issues.extend(active['errors'])
        report['card_counts']=ir.card_counts; report['active_case']=active
        report['model_counts']={k:len(getattr(ir,k)) for k in ('nodes','solid_elements','properties','materials','plasticity','masses','rbe2','rbe3','boundary_conditions','initial_conditions')}
        report['reference_check']={'issues':issues,'scope':'basic mesh references and selected TIC; remaining checks incomplete'}
        report['unsupported_active']=list(ir.unsupported)
        metadata={'NLCNTLG','NLCNTL2','DESC'}
        for name,count in ir.card_counts.items():
            active_count=active['counts'].get(name,count)
            status='NOT_TRANSFERRED' if name in metadata else 'SEMANTIC_MAPPING_PENDING'
            report['mappings'][name]={'source_count':count,'active_count':active_count,'status':status}
            if name not in metadata and active_count:
                report['unsupported_active'].append({'card':name,'count':active_count,'reason':'Target mapping and serialization not verified'})
        for name in ('NLCNTLG','NLCNTL2'):
            if name in ir.card_counts: report['not_transferred'].append({'card':name,'reason':'SOURCE_SOL402_CONTROL_NOT_DIRECTLY_EQUIVALENT','definitions':[e.data for e in ir.analysis_controls.get(name,[])]})
        orders=Counter(e.data['type']+str(len(e.data['nodes'])) for e in ir.solid_elements.values())
        report['element_check']={'source_orders':dict(orders),'target_orders':{},'jacobian':'NOT_VERIFIED','volume':'NOT_VERIFIED', **validate_element_geometry({i:e.data for i,e in ir.solid_elements.items()},{i:e.data for i,e in ir.nodes.items()})}
        if orders['CPENTA15']: report['approximations'].append({'source':'CPENTA15','target':'PENTA6','count':orders['CPENTA15'],'status':'PROPOSED_NOT_APPLIED'})
        report['node_check']={'source_count':len(ir.nodes),'target_count':0,'bounds':[[min(e.data['xyz'][i] for e in ir.nodes.values()),max(e.data['xyz'][i] for e in ir.nodes.values())] for i in range(3)] if ir.nodes else []}
        report['initial_condition_check']={'status':'MAPPED','clusters':active['initial_velocity_clusters'],'source_node_count':active['counts']['TIC']}
        report['contact_check']={'status':'NOT_VERIFIED','active_sliding_sets':active['contacts'],'active_glue_sets':active['glue']}
        nd={i:e.data for i,e in ir.nodes.items()}; ed={i:e.data for i,e in ir.solid_elements.items()}; md={i:e.data for i,e in ir.materials.items()}; pd={i:e.data for i,e in ir.properties.items()}
        sm,invalid=structural_mass(ed,nd,md,pd); cm=sum(e.data['mass'] for e in ir.masses.values())
        report['mass_check']={'status':'NOT_VERIFIED','source_structural_mass':sm if not invalid else None,'source_concentrated_mass':cm,'source_total_mass':sm+cm if not invalid else None,'target_structural_mass':None,'target_concentrated_mass':None,'target_total_mass':None,'absolute_error':None,'relative_error':None,'invalid_elements':invalid,'source_provenance':'SOURCE_BDF_REPARSE','target_provenance':'TARGET_RAD_REPARSE'}
        report['material_check']={'source_count':len(ir.materials),'plastic_count':len(ir.plasticity),'target_count':0}
        report['constraint_check']={'status':'MAPPED','source_rbe2':len(ir.rbe2),'target_rbe2':len(ir.rbe2),'source_rbe3':len(ir.rbe3),'target_rbe3':len(ir.rbe3),'active_spc_records':active['counts']['SPC']}
        report['controls']={'source_end_time':active['termination_time'],'requested_end_time':termination_time,'output_interval':output_interval,'fixed_explicit_dt':None}
        # Serialize only when lexical/semantic parsing itself succeeded. Unknown or
        # malformed cards remain a fail-closed publication gate.
        # Unsupported physics remains fail-closed in the report; it is never silently dropped.
        starter_path = output
        engine_path = output.with_name(output.stem.replace('_0000','_0001') + '.rad')
        target = None
        rir = build_ir(ir, active)
        if not ir.unsupported:
            write_radioss(starter_path, engine_path, rir, active, termination_time, output_interval, source.name, output_policy)
        if starter_path.exists():
            schema=validate_keywords(starter_path.read_text(encoding='ascii'))
            report['target_schema']=schema
            (starter_path.parent/'generated_keyword_inventory.json').write_text(json.dumps(schema,indent=2),encoding='utf-8')
            target=parse_generated_rad(starter_path)
            tc=Counter(e['family'] for e in target.elements.values()); parse_ok=bool(target.nodes and target.elements)
            report['target_reparse']={'status':'PASS' if parse_ok else 'FAIL','node_count':len(target.nodes),'element_count':len(target.elements),'element_families':dict(tc),'group_count':len(target.groups),'provenance':'TARGET_RAD_REPARSE'}
            report['element_check']['target_orders']=dict(tc)
        report['starter_file']=str(starter_path); report['engine_file']=str(engine_path)
        report['target_entity_counts']={'nodes':len(target.nodes) if target else 0,'elements':len(target.elements) if target else 0,'materials':len(target.materials) if target else 0,'properties':len(target.properties) if target else 0,'groups':len(target.groups) if target else 0}
        report['node_check']['target_count']=len(target.nodes) if target else 0
        # target_orders above is populated exclusively from the reparsed RAD.
        report['element_check']['equivalence_map']={'CHEXA20':'BRIC20','CHEXA8':'BRICK','CPENTA15':'DEGENERATED_BRICK','CTETRA10':'TETRA10'}
        target_ok=report.get('target_reparse',{}).get('status')=='PASS'
        report['element_check']['reference_integrity']='PASS' if target_ok and not issues else 'NOT_VERIFIED'
        report['element_check']['geometry_validity']='NOT_VERIFIED'
        report['element_check']['topology_equivalence']='NOT_VERIFIED'
        report['element_check']['serialization_validity']='PASS' if target_ok and report.get('target_schema',{}).get('status')=='PASS' else 'NOT_VERIFIED'
        report['element_check']['semantic_equivalence']='NOT_VERIFIED'
        report['material_check']['target_count']=len(rir.materials)
        report['warnings']=issues + rir.warnings
        report['mapping_report']={
            'GRID':{'source_count':len(ir.nodes),'target_keyword':'/NODE','target_count':len(target.nodes) if target else 0,'status':'PASS' if target and len(target.nodes)==len(ir.nodes) else 'INCOMPLETE'},
            'CHEXA20':{'source_count':sum(1 for e in ir.solid_elements.values() if e.data['type']=='CHEXA' and len(e.data['nodes'])==20),'target_keyword':'/BRIC20','target_count':(target and sum(1 for e in target.elements.values() if e['family']=='BRIC20')) or 0,'status':'SERIALIZED'},
            'CHEXA8':{'source_count':sum(1 for e in ir.solid_elements.values() if e.data['type']=='CHEXA' and len(e.data['nodes'])==8),'target_keyword':'/BRICK','target_count':(target and sum(1 for e in target.elements.values() if e['family']=='BRICK')) or 0,'status':'SERIALIZED'},
            'CTETRA10':{'source_count':sum(1 for e in ir.solid_elements.values() if e.data['type']=='CTETRA' and len(e.data['nodes'])==10),'target_keyword':'/TETRA10','target_count':(target and sum(1 for e in target.elements.values() if e['family']=='TETRA10')) or 0,'status':'SERIALIZED'},
            'MATS1':{'source_count':len(ir.plasticity),'target_keyword':'FAILED_MAPPING','target_count':0,'status':'FAILED_MAPPING'},
            'CONM2':{'source_count':len(ir.masses),'target_keyword':'/ADMAS/5','target_count':0,'status':'FAILED_MAPPING'},
            'CONTACT':{'source_count':len(active['contacts']),'target_keyword':'/INTER/TYPE7','target_count':0,'status':'FAILED_MAPPING'},
            'GLUE':{'source_count':len(active['glue']),'target_keyword':'/INTER/TYPE2','target_count':0,'status':'FAILED_MAPPING'}}
        (output.parent/'mapping_report.json').write_text(json.dumps(report['mapping_report'],indent=2),encoding='utf-8')
        report['element_check']['status']='PASS' if all(report['element_check'].get(k)=='PASS' for k in ('reference_integrity','geometry_validity','topology_equivalence','serialization_validity','semantic_equivalence')) else 'INCOMPLETE'
        report['target_entity_counts'].update({'materials':len(target.materials) if target else 0,'properties':len(target.properties) if target else 0,'parts':len(target.parts) if target else 0,'masses':len(target.masses) if target else 0})
        report['blockers']=[f'{x["card"]}: {x.get("reason",x.get("error","unresolved"))}' for x in report['unsupported_active']]
        report['blockers'].extend(['Starter solver verification absent','Engine smoke evidence absent','Structural and target mass comparison absent','Active nonlinear/contact mappings require validation'])
    except (OSError,ValueError,UnicodeError) as exc:
        report['warnings'].append(str(exc)); report['blockers']=['Source scan or validation failed: '+str(exc)]
    report_path.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    return report
