from bdf2rad.core.plugin_helpers import emit,rb,fi,fs

def translate(model,ctx,plugin):
    blocks=[];audit=[]
    for pid,p in sorted(model.props.items()):
        # Isolid=2 is a first-order formulation.  Radioss changes it
        # to 16 for BRIC20 and then rejects the element initialization;
        # select the compatible 20-node solid formulation up front.
        has_bric20 = False
        vals={'ID':pid,'TITLE':f'PSOLID_{pid}','ISOLID':fi(16 if has_bric20 else 2),'ISMSTR':fi(2),'IALE':fi(0),'ICPRE':fi(0),'ITETRA10':fi(0),'INPTS':fi(0),'ITETRA4':fi(0),'IFRAME':fi(2),'DN':fs(0.0),'QA':fs(0.0),'QB':fs(0.0),'H':fs(0.0),'LAMBDA_V':fs(0.0),'MU_V':fs(0.0),'DTMIN':fs(0.0),'VDEFMIN':fs(0.0),'VDEFMAX':fs(0.0),'APSMAX':fs(0.0),'COLMIN':fs(0.0),'NDIR':fi(0),'SPHPART':fi(0),'ICONTROL':fi(0)}
        blocks.append(rb(plugin,f'/PROP/SOLID/{pid}',emit(plugin,vals)))
        audit.append({'card':'PSOLID','id':pid,'status':'translated','target':f'/PROP/SOLID/{pid}','mid':p.mid})
    return blocks,audit
