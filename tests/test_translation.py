from bdf2rad.translation.translators import elements

def test_cpenta15_degenerate():
    class S: elements={1:{'type':'CPENTA','pid':1,'nodes':list(range(1,16))}}
    o,w=elements(S())
    assert o[0]['type']=='BRICK' and len(o[0]['nodes'])==8
    assert w
