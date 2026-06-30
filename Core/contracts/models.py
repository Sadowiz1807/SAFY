from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
import uuid, time

class Serializable:
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, data): return cls(**data)

@dataclass
class RequestEnvelope(Serializable):
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = "default"
    user_id: str = "local"
    payload: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ResourceRef(Serializable):
    kind: str
    id: str
    path: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RuntimeSnapshot(Serializable):
    session: Dict[str, Any]
    database: Dict[str, Any]
    sandbox: Dict[str, Any]
    rules: Dict[str, Any]
    memory: Dict[str, Any] = field(default_factory=dict)
    skills: List[Dict[str, Any]] = field(default_factory=list)
    model: Dict[str, Any] = field(default_factory=dict)
    safety_mode: str = "human_approved"

@dataclass
class ActionPlan(Serializable):
    intent: str
    risk_level: str = "low"
    table: Optional[str] = None
    columns: List[str] = field(default_factory=list)
    operations: List[Dict[str, Any]] = field(default_factory=list)
    requires_confirmation: bool = False
    clarification: Optional[str] = None

@dataclass
class ToolCall(Serializable):
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "low"
    requires_confirmation: bool = False

@dataclass
class UIEvent(Serializable):
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = field(default_factory=time.time)

@dataclass
class UIPatch(Serializable):
    op: str
    target: str
    value: Any = None

@dataclass
class SafetyResult(Serializable):
    status: str
    allowed: bool = False
    reasons: List[str] = field(default_factory=list)
    risk_level: str = "low"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))

@dataclass
class ErrorEnvelope(Serializable):
    code: str
    message: str
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    details: Dict[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        for k in list(self.details):
            if any(s in k.lower() for s in ['secret','password','token','key']): self.details[k]='[REDACTED]'

@dataclass
class TaskFrame(Serializable):
    request: RequestEnvelope
    snapshot: RuntimeSnapshot
    plan: Optional[ActionPlan] = None
    artifacts: List[ResourceRef] = field(default_factory=list)
