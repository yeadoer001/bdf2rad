
def translate(model,ctx,plugin):
    n=model.card_counts.get('NLCNTLG',0)
    return [],([{'card':'NLCNTLG','status':'audit-only','count':n,'reason':'No invented target syntax. Add a dedicated plugin when a documented target Block mapping is established.'}] if n else [])
