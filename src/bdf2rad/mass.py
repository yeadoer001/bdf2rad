def _det(a,b,c): return a[0]*(b[1]*c[2]-b[2]*c[1])-a[1]*(b[0]*c[2]-b[2]*c[0])+a[2]*(b[0]*c[1]-b[1]*c[0])
def tetra_volume(p):
    a,b,c,d=p; u=[b[i]-a[i] for i in range(3)]; v=[c[i]-a[i] for i in range(3)]; w=[d[i]-a[i] for i in range(3)]; return abs(_det(u,v,w))/6
def element_volume(e,nodes):
    p=[nodes[x]['xyz'] for x in e['nodes']]
    if e['type']=='CTETRA': return tetra_volume(p[:4])
    if e['type']=='CPENTA': return tetra_volume([p[i] for i in (0,1,2,3)])+tetra_volume([p[i] for i in (3,4,5,2)])
    if e['type']=='CHEXA': return sum(tetra_volume([p[i] for i in q]) for q in ((0,1,3,4),(1,2,3,6),(1,4,5,6),(3,4,6,7),(1,3,4,6)))
    return 0.0
def structural_mass(elements,nodes,materials,properties):
    total=0.0; invalid=0
    for e in elements.values():
        try: total += element_volume(e,nodes)*materials[properties[e['pid']]['mid']]['rho']
        except (KeyError,IndexError): invalid += 1
    return total, invalid
