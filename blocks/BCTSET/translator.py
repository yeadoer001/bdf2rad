from bdf2rad.core.plugin_helpers import emit,rb,fi,fs

def translate(model,ctx,plugin):
    blocks=[];audit=[];sg=ctx.metadata.get('surface_group',{})
    for sid,c in sorted(model.bctsets.items()):
        sec=sg.get(c.source);main=c.target
        if sec is None:
            audit.append({'card':'BCTSET','id':sid,'status':'blocked','reason':'source BSURFS was not translated'});continue
        # The fixed six-row body follows the structure shown by the user-supplied TYPE7 examples; only field values are substituted.
        lines=emit(plugin,{'ID':sid,'TITLE':f'BCTSET_{sid}',
            'R1':f'{fi(sec)}{fi(main)}{fi(c.form)}{fi(0)}{fi(0)}{fi(0)}{fi(0)}{fi(0)}{fi(0)}',
            'R2':f'{fs(0.0)}{fs(max(c.maxd,0.0))}{fs(0.0)}{fi(0)}',
            'R3':f'{fs(0.0)}{fs(0.0)}{fs(0.0)}{fs(0.0)}{fi(0)}{fi(0)}',
            'R4':f'{fs(1.0)}{fs(c.friction)}{fs(max(c.mind,0.0))}{fs(0.0)}{fs(0.0)}',
            'R5':'       000                             5                   0                   0                   0',
            'R6':f'{fi(0)}{fi(0)}{fs(0.0)}{fi(2)}{fi(0)}{fi(0)}{fs(1.0)}{fi(0)}'})
        blocks.append(rb(plugin,f'/INTER/TYPE7/{sid}',lines,source_cards=('BCTSET','BCRPARA')))
        audit.append({'card':'BCTSET','id':sid,'status':'translated','target':f'/INTER/TYPE7/{sid}','secondary_group':sec,'main_surface':main,'friction':c.friction})
    return blocks,audit
