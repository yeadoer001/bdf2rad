from dataclasses import dataclass, field

@dataclass
class GroupRegistry:
    groups: dict = field(default_factory=dict)
    next_id: int = 1
    def create_node_group(self, name, node_ids):
        ids=tuple(dict.fromkeys(int(x) for x in node_ids)); gid=self.next_id; self.next_id+=1
        self.groups[gid]={'name':name,'type':'NODE','nodes':ids}; return gid
    def validate(self):
        return all(g['nodes'] and len(g['nodes'])==len(set(g['nodes'])) for g in self.groups.values())
