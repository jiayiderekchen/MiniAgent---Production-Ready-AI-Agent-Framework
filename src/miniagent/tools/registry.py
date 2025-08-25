from dataclasses import dataclass
from typing import Dict, Any, Callable, List, Optional
from pydantic import BaseModel, ValidationError

@dataclass
class ToolSpec:
    name: str
    schema: Dict[str, Any]  # Informational / doc; can be enforced by validator
    fn: Callable[[Dict[str, Any]], Any]
    timeout_s: float = 15.0
    validator: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None  # optional

class ToolRegistry:
    def __init__(self): self._t: Dict[str, ToolSpec] = {}
    def register(self, spec: ToolSpec): self._t[spec.name] = spec
    def get(self, name: str) -> ToolSpec: return self._t[name]
    def list(self) -> List[ToolSpec]: return list(self._t.values())

tools = ToolRegistry()
