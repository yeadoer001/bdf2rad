from bdf2rad.core.plugin_helpers import emit,rb,fi,fs

def translate(model,ctx,plugin):
    blocks=[];audit=[]
    for mid,m in sorted(model.mats.items()):
        lines=emit(plugin,{'ID':mid,'TITLE':f'MAT1_{mid}','RHO':fs(m.rho),'E':fs(m.E),'NU':fs(m.nu)})
        blocks.append(rb(plugin,f'/MAT/LAW1/{mid}',lines))
        audit.append({'card':'MAT1','id':mid,'status':'translated','target':f'/MAT/LAW1/{mid}'})
    return blocks,audit
