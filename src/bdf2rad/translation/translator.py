from .core import parse,selected_case
from .translators import elements,materials,properties,groups_and_bcs,initial_velocity,gravity,masses,rbe2,rbe3,surface_faces,contact_sets,glue_sets
from .validate import validate
from .writer import write_starter,write_engine
from pathlib import Path
import json

def build(source,encoding='gb18030',preserve_high_order=True):
    src=parse(source,encoding=encoding); case=selected_case(src); warnings=[]
    els,w=elements(src,preserve_high_order); warnings+=w
    mats,functs,w=materials(src); warnings+=w
    props=properties(src)
    ng,bcs=groups_and_bcs(src,case.get('SPC'))
    vg,vel,vw=initial_velocity(src,case.get('IC')); ng += vg; warnings += vw
    grav=gravity(src,case.get('LOAD'))
    masses_,mw=masses(src); warnings+=mw
    rb2,rg2=rbe2(src); ng+=rg2; rb3,rg3=rbe3(src); ng+=rg3
    surfaces,sw=surface_faces(src); warnings+=sw
    contacts=contact_sets(src); glue=glue_sets(src)
    not_transferred=[f'{c.name} line {c.line_no}: source control retained without guessed explicit-equivalent mapping' for c in src.controls]
    data=dict(elements=els,materials=mats,functions=functs,properties=props,node_groups=ng,bcs=bcs,velocity=vel,gravity=grav,masses=masses_,rbe2=rb2,rbe3=rb3,surfaces=surfaces,contacts=contacts,glue=glue,warnings=warnings,not_transferred=not_transferred,case=case)
    errors,warnings=validate(src,data); data['warnings']=warnings; data['errors']=errors
    data['summary']={'source_nodes':len(src.nodes),'source_elements':len(src.elements),'target_elements':len(els),'materials':len(mats),'properties':len(props),'spc_records':len(src.spc),'tic_records':len(src.tic),'rbe2':len(rb2),'rbe3':len(rb3),'conm2':len(masses_),'bsurfs':len(surfaces),'contacts':len(contacts),'glue':len(glue),'termination_time':None}
    if src.tstep1:
        for c in src.tstep1:
            if len(c.fields)>1 and c.fields[1]:
                try: data['summary']['termination_time']=float(c.fields[1].replace('D','E')); break
                except: pass
    return src,data

def convert(source,outdir,encoding='gb18030',preserve_high_order=True,dtout=None):
    src,data=build(source,encoding,preserve_high_order); out=Path(outdir); out.mkdir(parents=True,exist_ok=True); name=Path(source).stem
    starter=out/f'{name}_0000.rad'; engine=out/f'{name}_0001.rad'; end=data['summary']['termination_time'] or 1.0; dtout=dtout or max(end/100.0,1e-9)
    write_starter(starter,name,src,data,preserve_high_order); write_engine(engine,name,end,dtout)
    report=out/'translation_report.json'; report.write_text(json.dumps({'status':'FAILED_VALIDATION' if data['errors'] else 'GENERATED','summary':data['summary'],'case':data['case'],'errors':data['errors'],'warnings':data['warnings'],'not_transferred':data['not_transferred']},indent=2,ensure_ascii=False),encoding='utf-8')
    return starter,engine,report
