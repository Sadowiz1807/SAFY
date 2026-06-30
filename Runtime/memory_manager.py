class MemoryManager:
    def __init__(self): self.long_term=[]; self.artifacts=[]
    def recent_chat(self, turns, limit=10): return turns[-limit:]
    def relevant(self, query):
        q=query.lower(); return [m for m in self.long_term if any(t in m.lower() for t in q.split())]
    def build(self, query='', turns=None, working=None):
        return {"short_term": self.recent_chat(turns or []), "working": working or {}, "long_term": self.relevant(query), "artifacts": self.artifacts}
