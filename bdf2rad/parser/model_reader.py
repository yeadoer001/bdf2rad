from __future__ import annotations
from ..model import *
from .cards import iter_cards, read_case_control, nastran_float

SUPPORTED = {
    'GRID','CTETRA','CHEXA','CPENTA','PSOLID','MAT1','MATS1','CONM2','RBE2','RBE3',
    'SPC','SPC1','SPCADD','TIC','GRAV','BSURFS','BCRPARA','BCTSET','BCTADD',
    'BGSET','BGADD','NLCNTLG','NLCNTL2','TSTEP1','TEMPD','TEMP','PARAM','BCSET','IC',
    'LOAD','TSTEP','SUBCASE'
}

def _i(x, d=0):
    try: return int(float(x.strip())) if x.strip() else d
    except Exception: return d

def _f(x, d=None):
    try: return nastran_float(x) if x.strip() else d
    except Exception: return d

def F(f, i, d=''): return f[i] if i < len(f) else d

def read_model(path, encoding='gb18030') -> Model:
    m=Model(); c,e=read_case_control(path,encoding);m.control_lines=c;m.executive=e
    for card in iter_cards(path,encoding):
        f=card.fields;n=card.name;m.card_counts[n]=m.card_counts.get(n,0)+1
        try:
            if n=='GRID':
                nid=_i(F(f,1));m.nodes[nid]=Node(nid,(_f(F(f,3),0.0) or 0.0,_f(F(f,4),0.0) or 0.0,_f(F(f,5),0.0) or 0.0),_i(F(f,2)),_i(F(f,6)))
            elif n in ('CTETRA','CHEXA','CPENTA'):
                eid=_i(F(f,1));pid=_i(F(f,2));m.elements[eid]=Element(eid,n,pid,[_i(x) for x in f[3:] if x.strip()])
            elif n=='PSOLID':
                pid=_i(F(f,1));m.props[pid]=Property(pid,_i(F(f,2)),f)
            elif n=='MAT1':
                mid=_i(F(f,1));E=_f(F(f,2),0.0) or 0.0;G=_f(F(f,3),0.0) or 0.0;nu=_f(F(f,4),0.0) or 0.0;rho=_f(F(f,5),0.0) or 0.0;alpha=_f(F(f,6),0.0) or 0.0
                if G==0 and E and nu:G=E/(2*(1+nu))
                if nu==0 and E and G:nu=E/(2*G)-1
                m.mats[mid]=Material(mid,E,nu,rho,G,alpha)
            elif n=='MATS1':m.plastics[_i(F(f,1))]=Plastic(_i(F(f,1)),_i(F(f,2)),F(f,3).upper(),_f(F(f,4),0.0) or 0.0,_i(F(f,5),1),_i(F(f,6),1),_f(F(f,7),0.0) or 0.0)
            elif n=='CONM2':
                eid=_i(F(f,1));m.masses[eid]=Mass(eid,_i(F(f,2)),_f(F(f,4),0.0) or 0.0,(_f(F(f,5),0.0) or 0.0,_f(F(f,6),0.0) or 0.0,_f(F(f,7),0.0) or 0.0),_i(F(f,3)))
            elif n=='RBE2':m.rbe2[_i(F(f,1))]=RBE2(_i(F(f,1)),_i(F(f,2)),F(f,3) or '123456',[_i(x) for x in f[4:] if x.strip()])
            elif n=='RBE3':m.rbe3[_i(F(f,1))]=RBE3(_i(F(f,1)),_i(F(f,3)),F(f,4) or '123456',_f(F(f,5),1.0) or 1.0,F(f,6) or '123',[_i(x) for x in f[7:] if x.strip()])
            elif n=='SPC':m.spcs.append(SPC(_i(F(f,1)),_i(F(f,2)),F(f,3),_f(F(f,4),0.0) or 0.0))
            elif n=='SPC1':
                sid=_i(F(f,1));comp=F(f,2);m.spcs.extend(SPC(sid,_i(x),comp,0.0) for x in f[3:] if x.strip())
            elif n=='TIC':m.tics.append(TIC(_i(F(f,1)),_i(F(f,2)),_i(F(f,3)),_f(F(f,4),None),_f(F(f,5),None)))
            elif n=='GRAV':m.gravs[_i(F(f,1))]=Gravity(_i(F(f,1)),_i(F(f,2)),_f(F(f,3),1.0) or 1.0,(_f(F(f,4),0.0) or 0.0,_f(F(f,5),0.0) or 0.0,_f(F(f,6),0.0) or 0.0))
            elif n=='TSTEP1':m.tsteps[_i(F(f,1))]=TStep(_i(F(f,1)),_f(F(f,2),0.0) or 0.0,_i(F(f,3)),F(f,4))
            elif n=='BCRPARA':m.bcrpara[_i(F(f,1))]=BCRPara(_i(F(f,1)),_f(F(f,3),0.0) or 0.0,F(f,4) or 'FLEX')
            elif n=='BCTSET':m.bctsets[_i(F(f,1))]=BCTSet(_i(F(f,1)),_i(F(f,2)),_i(F(f,3)),_f(F(f,4),0.0) or 0.0,_i(F(f,5)),_f(F(f,6),0.0) or 0.0,_i(F(f,7),1))
            elif n=='BGSET':m.bgsets[_i(F(f,1))]=BGSet(_i(F(f,1)),_i(F(f,2)),_i(F(f,3)),_f(F(f,4),1.0) or 1.0,_f(F(f,5),0.0) or 0.0)
            elif n=='BCTADD':m.bctadds[_i(F(f,1))]=[_i(x) for x in f[2:] if x.strip()]
            elif n=='BGADD':m.bgadds[_i(F(f,1))]=[_i(x) for x in f[2:] if x.strip()]
            elif n=='BSURFS':
                # Nastran BSURFS has blank fields 3-5, then repeating EID,G1,G2,G3 groups.
                vals=[_i(x) for x in f[5:] if x.strip()]
                faces=[]
                for k in range(0,len(vals),4):
                    chunk=vals[k:k+4]
                    if len(chunk)==4: faces.append(tuple(chunk))
                m.bsurfs[_i(F(f,1))]=BsurfS(_i(F(f,1)),faces)
            elif n not in SUPPORTED:
                m.diagnostics.append({'severity':'UNSUPPORTED_CARD','card':n,'line':card.line,'fields':f[:12]})
        except Exception as ex:
            m.diagnostics.append({'severity':'PARSE_ERROR','card':n,'line':card.line,'error':str(ex),'fields':f[:12]})
    for ln in c:
        s=ln.strip()
        if '=' in s:
            k,v=s.split('=',1);m.case[k.strip().upper()]=v.strip()
        elif s.upper().startswith('SUBCASE'):
            parts=s.split();m.case['_SUBCASE']=parts[1] if len(parts)>1 else '1'
    return m
