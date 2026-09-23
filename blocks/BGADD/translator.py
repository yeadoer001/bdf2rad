
def translate(model,ctx,plugin):
    n=model.card_counts.get('BGADD',0)
    return [],([{'card':'BGADD','status':'audit-only','count':n,'reason':'No invented target syntax. Add a dedicated plugin when a documented target Block mapping is established.'}] if n else [])
