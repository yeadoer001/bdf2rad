from bdf2rad.core.plugin_helpers import emit,rb,fi,fs

def translate(model,ctx,plugin):
    blocks=[];audit=[];sg=ctx.metadata.get('surface_group',{})
    for sid,b in sorted(model.bgsets.items()):
        sec=sg.get(b.source);main=b.target
        if sec is None:
            audit.append({'card':'BGSET','id':sid,'status':'audit-only','reason':'source BSURFS not translated'});continue
        lines=emit(plugin,{'ID':sid,'TITLE':f'BGSET_{sid}','R1':f'{fi(sec)}{fi(main)}{fi(1000)}{fi(5)}{fi(0)}{fi(2)}{fi(1000)}{fs(b.clearance)}'})
        blocks.append(rb(plugin,f'/INTER/TYPE2/{sid}',lines,source_cards=('BGSET','BGADD')))
        audit.append({'card':'BGSET','id':sid,'status':'audit-only','target':f'/INTER/TYPE2/{sid}','note':'Candidate only; source Glue semantics are not asserted equivalent by this translator.'})
    return blocks,audit
