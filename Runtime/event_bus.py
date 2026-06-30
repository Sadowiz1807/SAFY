from Core.contracts import UIEvent
class EventBus:
    def __init__(self): self.events=[]
    def emit(self, type, payload=None, request_id=None):
        e=UIEvent(type=type,payload=payload or {},request_id=request_id or UIEvent(type=type).request_id); self.events.append(e); return e
    def drain(self): ev,self.events=self.events,[]; return ev
