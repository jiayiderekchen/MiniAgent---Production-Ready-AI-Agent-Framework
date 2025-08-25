"""
MiniAgent - A comprehensive AI agent framework

A production-ready framework for building intelligent agents with:
- Advanced planning and reasoning
- Comprehensive tool suite
- Vector-based memory systems
- Security and safety guardrails
- Evaluation framework
- Configuration management

Example usage:
    import asyncio
    from miniagent import run_agent
    
    async def main():
        result = await run_agent("Calculate the area of a circle with radius 5")
        print(result['result'])
    
    asyncio.run(main())
"""

from .core.runtime import run_agent
from .core.state import AgentState
from .config import AgentConfig, get_config, set_config
from .tools.registry import tools, ToolSpec
from .memory.store import IntegratedMemorySystem, VectorMemoryStore, EpisodicMemory, WorkingMemory
from .eval.harness import AgentEvaluator, EvalSuite, EvalTask, create_basic_eval_suite, create_advanced_eval_suite
from .guard.schema import validate_action, sanitize_output
from .guard.consent import ConsentManager, get_consent_manager, set_consent_manager

__version__ = "1.0.0"

__all__ = [
    # Core functionality
    "run_agent",
    "AgentState",
    
    # Configuration
    "AgentConfig", 
    "get_config", 
    "set_config",
    
    # Tools
    "tools",
    "ToolSpec", 
    
    # Memory
    "IntegratedMemorySystem",
    "VectorMemoryStore",
    "EpisodicMemory", 
    "WorkingMemory",
    
    # Evaluation
    "AgentEvaluator",
    "EvalSuite",
    "EvalTask",
    "create_basic_eval_suite",
    "create_advanced_eval_suite",
    
    # Safety & Consent
    "validate_action",
    "sanitize_output",
    "ConsentManager",
    "get_consent_manager", 
    "set_consent_manager",
    
    # Version
    "__version__",
]