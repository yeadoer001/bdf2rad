from bdf2rad.core.plugin_helpers import emit,rb,fi,fs,bdf_accel_to_rad_mm_ms2

def translate(model,ctx,plugin):
    blocks=[];audit=[]
    for sid,g in sorted(model.gravs.items()):
        mags=[bdf_accel_to_rad_mm_ms2(x) for x in g.vector]
        mag=(sum(x*x for x in mags))**0.5
        axis=max(range(3),key=lambda i:abs(mags[i])) if mag else 0
        direction='XYZ'[axis]
        signed=mags[axis]
        lines=emit(plugin,{'ID':sid,'TITLE':f'GRAV_{sid}','FCT':fi(0),'DIR':f'{direction:>10s}','SKEW':fi(0),'SENS':fi(0),'GRND':fi(0),'ASCALE':fs(1.0),'FSCALE':fs(signed)})
        blocks.append(rb(plugin,f'/GRAV/{sid}',lines));audit.append({'card':'GRAV','status':'translated','target':f'/GRAV/{sid}','vector_target_mm_ms2':mags})
    return blocks,audit
