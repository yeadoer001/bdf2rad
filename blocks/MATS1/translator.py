def translate(model,ctx,plugin):
    audit=[]
    for mid,p in sorted(model.plastics.items()):
        audit.append({'card':'MATS1','id':mid,'status':'audit-only','reason':'No direct one-to-one mapping is asserted. Source yield/hardening/table semantics must select a documented Radioss material law + function.'})
    return [],audit
