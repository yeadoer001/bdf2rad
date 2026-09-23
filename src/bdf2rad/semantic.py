"""Full-card semantic scan. Unknown cards are retained and classified."""
from .parser import BDFParser, nastran_float
from .nastran_ir import NastranIR, Entity, Provenance

ELEMENTS = {'CTETRA':'CTETRA','CHEXA':'CHEXA','CPENTA':'CPENTA'}
SUPPORTED = {'GRID','CTETRA','CHEXA','CPENTA','PSOLID','MAT1','MATS1','CONM2','RBE2','RBE3','SPC','SPC1','SPCADD','TIC','GRAV','BSURFS','BCRPARA','BCTSET','BCTADD','BGSET','BGADD','NLCNTLG','NLCNTL2','TSTEP1','TEMPD','TEMP'}

def _num(x, default=0.0):
    return default if x in ('', None) else nastran_float(x)
def _id(x): return int(x)
def _ent(card, data, sid=None, confidence='EXACT', warnings=None):
    return Entity(data, Provenance(card.name, card.source.file, card.source.line, sid, confidence, warnings or []))

def scan(source, encoding='gb18030'):
    ir=NastranIR(); parser=BDFParser(encoding=encoding); seen=set()
    for card in parser.parse(source):
        name=card.name; f=card.fields; ir.card_counts[name]=ir.card_counts.get(name,0)+1
        try:
            f=f+('',)*max(0,8-len(f))
            sid=_id(f[0]) if f[0].isdigit() else None
            if name in ('GRID','CTETRA','CHEXA','CPENTA','PSOLID','MAT1','MATS1','CONM2','RBE2','RBE3','BSURFS'):
                namespace='ELEMENT' if name in ('CTETRA','CHEXA','CPENTA','CONM2','RBE2','RBE3') else name
                key=(namespace,sid)
                if sid is None or sid <= 0 or key in seen:
                    raise ValueError(f'Invalid or duplicate ID {namespace}:{sid}')
                seen.add(key)
            if name=='GRID':
                ir.nodes[sid]=_ent(card, {'xyz':[_num(x) for x in f[2:5]],'cp':_id(f[1]) if f[1] else 0,'cd':_id(f[5]) if len(f)>5 and f[5] else 0},sid)
            elif name in ELEMENTS:
                ir.solid_elements[sid]=_ent(card, {'type':name,'pid':_id(f[1]),'nodes':[_id(x) for x in f[2:] if x]},sid)
            elif name=='PSOLID': ir.properties[sid]=_ent(card, {'mid':_id(f[1]),'raw':list(f)},sid)
            elif name=='MAT1': ir.materials[sid]=_ent(card, {'E':_num(f[1]),'G':_num(f[2]),'nu':_num(f[3]),'rho':_num(f[4]),'alpha':_num(f[5])},sid)
            elif name=='MATS1': ir.plasticity[sid]=_ent(card, {'mid':_id(f[0]),'tid':f[1] if len(f)>1 else '', 'type':f[2] if len(f)>2 else '', 'h':_num(f[3]) if len(f)>3 else 0.0,'yf':int(f[4] or 1),'hr':int(f[5] or 1),'limit1':_num(f[6])},sid)
            elif name=='CONM2': ir.masses[sid]=_ent(card, {'node':_id(f[1]),'mass':_num(f[3]),'offset':[_num(x) for x in f[4:7]],'raw':list(f)},sid)
            elif name=='RBE2': ir.rbe2[sid]=_ent(card, {'independent':_id(f[1]),'cm':f[2] if len(f)>2 else '', 'dependent':[_id(x) for x in f[3:] if x]},sid)
            elif name=='RBE3': ir.rbe3[sid]=_ent(card, {'raw':list(f)},sid,'REQUIRES_VALIDATION')
            elif name in ('SPC','SPC1'): ir.boundary_conditions[(sid,card.source.file,card.source.line)]=_ent(card, {'type':name,'raw':list(f)},sid)
            elif name=='TIC': ir.initial_conditions[(sid,card.source.file,card.source.line)]=_ent(card, {'node':_id(f[1]),'dof':f[2] if len(f)>2 else '', 'displacement':_num(f[3]),'velocity':_num(f[4]),'raw':list(f)},sid)
            elif name=='GRAV': ir.gravity[sid]=_ent(card, {'cid':_id(f[1]) if len(f)>1 and f[1] else 0,'scale':_num(f[2]),'vector':[_num(x) for x in f[3:6]]},sid)
            elif name=='BSURFS': ir.contact_surfaces[sid]=_ent(card, {'raw':list(f)},sid,'REQUIRES_VALIDATION')
            elif name in ('BCTSET','BCTADD'): ir.contacts[sid]=_ent(card, {'type':name,'raw':list(f)},sid)
            elif name in ('BGSET','BGADD'): ir.glue_interfaces[sid]=_ent(card, {'type':name,'raw':list(f)},sid)
            elif name in ('NLCNTLG','NLCNTL2','TSTEP1','TEMPD','TEMP','BCRPARA','SPCADD','DESC','PARAM'):
                ir.analysis_controls.setdefault(name,[]).append(_ent(card, {'raw':list(f)},sid,'SOURCE_METADATA_ONLY'))
            elif name not in ('ENDDATA',): ir.unsupported.append({'card':name,'source':card.source.file,'line':card.source.line,'fields':list(f)})
        except (ValueError, IndexError) as exc:
            ir.unsupported.append({'card':name,'source':card.source.file,'line':card.source.line,'error':str(exc),'fields':list(f)})
    from .analysis import case_control
    ir.metadata['case_control']=case_control(parser.control_lines)
    ir.metadata['control_lines']=[raw for _,raw in parser.control_lines]
    ir.metadata['source_file']=str(source); ir.metadata['encoding']=encoding
    return ir
