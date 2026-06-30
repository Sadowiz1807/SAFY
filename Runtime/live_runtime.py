from Runtime.session_manager import SessionManager
from Runtime.memory_manager import MemoryManager
from Runtime.sandbox_manager import SandboxManager
from Runtime.rule_manager import RuleManager
from Runtime.skill_registry import SkillRegistry
from Runtime.context_builder import ContextBuilder
from Runtime.event_bus import EventBus

SESSION_MANAGER = SessionManager()
MEMORY_MANAGER = MemoryManager()
SANDBOX_MANAGER = SandboxManager()
RULE_MANAGER = RuleManager()
SKILL_REGISTRY = SkillRegistry()
EVENT_BUS = EventBus()
CONTEXT_BUILDER = ContextBuilder(SESSION_MANAGER, MEMORY_MANAGER, SANDBOX_MANAGER, RULE_MANAGER, SKILL_REGISTRY)
LIVE_PATH_CALLS = []

def mark(name):
    LIVE_PATH_CALLS.append(name)
