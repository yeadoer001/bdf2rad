from collections import defaultdict
class DependencyGraph:
    def __init__(self): self.edges=defaultdict(set); self.nodes=set()
    def add(self, kind, ident): self.nodes.add((kind,ident)); return (kind,ident)
    def link(self, source, target): self.edges[source].add(target); self.nodes.update((source,target))
    def dangling(self, known): return [(s,t) for s,ts in self.edges.items() for t in ts if t not in known]
