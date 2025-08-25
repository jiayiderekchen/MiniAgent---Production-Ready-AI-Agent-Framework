from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid
from ..memory.store import IntegratedMemorySystem

@dataclass
class Memory:
    """Basic, in-memory stores. Extend as needed (vector DB, TTL caches, etc.)."""
    episodic: List[Dict[str, Any]] = field(default_factory=list)
    notes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentState:
    goal: str
    history: List[Dict[str, Any]] = field(default_factory=list)
    mem: Memory = field(default_factory=Memory)
    budget_tokens: int = 8000
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    memory_system: Optional[IntegratedMemorySystem] = None
    
    def __post_init__(self):
        """Initialize memory system if not provided"""
        if self.memory_system is None:
            self.memory_system = IntegratedMemorySystem()
    
    def remember(self, content: str, memory_type: str = "semantic", metadata: Optional[Dict[str, Any]] = None):
        """Store information in the memory system"""
        if self.memory_system:
            return self.memory_system.remember(content, memory_type, metadata)
    
    def recall(self, query: str, memory_type: str = "semantic", top_k: int = 5):
        """Retrieve information from the memory system"""
        if self.memory_system:
            return self.memory_system.recall(query, memory_type, top_k)
        return []
    
    def get_context(self, query: str, max_items: int = 10):
        """Get relevant context from all memory types"""
        if self.memory_system:
            return self.memory_system.get_context(query, max_items)
        return {}
