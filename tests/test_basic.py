import asyncio
import pytest
import tempfile
import os
from pathlib import Path

from miniagent.core.runtime import run_agent
from miniagent.core.state import AgentState
from miniagent.config import AgentConfig, set_config
from miniagent.tools.registry import tools, ToolSpec
from miniagent.memory.store import IntegratedMemorySystem
from miniagent.guard.schema import validate_action, sanitize_output
from miniagent.eval.harness import AgentEvaluator, EvalSuite, EvalTask

@pytest.fixture
def test_config():
    """Create a test configuration"""
    config = AgentConfig()
    config.runtime.max_steps = 5
    config.runtime.enable_logging = False
    config.memory.persist_dir = tempfile.mkdtemp()
    config.safety.enable_content_filtering = True
    set_config(config)
    return config

def test_basic_agent_run():
    """Test basic agent execution"""
    res = asyncio.run(run_agent("hello world", max_steps=2))
    assert "result" in res
    assert "history" in res
    assert "trace_id" in res

def test_agent_state():
    """Test agent state functionality"""
    state = AgentState(goal="test goal")
    
    # Test basic properties
    assert state.goal == "test goal"
    assert isinstance(state.history, list)
    assert isinstance(state.mem.notes, dict)
    assert state.trace_id is not None
    
    # Test memory integration
    assert state.memory_system is not None
    
    # Test memory operations
    memory_id = state.remember("test content", "semantic")
    assert memory_id is not None
    
    memories = state.recall("test", "semantic")
    assert len(memories) >= 0

def test_memory_system():
    """Test integrated memory system"""
    with tempfile.TemporaryDirectory() as temp_dir:
        memory_system = IntegratedMemorySystem(temp_dir)
        
        # Test semantic memory
        memory_id = memory_system.remember("Python is a programming language", "semantic")
        assert memory_id is not None
        
        results = memory_system.recall("programming", "semantic")
        assert len(results) >= 0
        
        # Test episodic memory
        memory_system.remember("User asked about Python", "episodic")
        
        # Test working memory
        memory_system.remember("current task", "working", {"key": "task1"})
        
        # Test context retrieval
        context = memory_system.get_context("Python")
        assert "semantic" in context
        assert "episodic" in context
        assert "working" in context

def test_tools_registry():
    """Test tools registry functionality"""
    tool_list = tools.list()
    assert len(tool_list) > 0
    
    # Check for expected tools
    tool_names = [tool.name for tool in tool_list]
    expected_tools = ["file.read", "file.write", "math.calc", "web.search"]
    
    for expected in expected_tools:
        assert expected in tool_names
    
    # Test getting a specific tool
    math_tool = tools.get("math.calc")
    assert math_tool is not None
    assert math_tool.name == "math.calc"

def test_action_validation():
    """Test action validation and safety"""
    # Valid action
    valid_action = {
        "type": "tool",
        "name": "math.calc",
        "args": {"expression": "2 + 2"}
    }
    
    validated = validate_action(valid_action)
    assert validated["type"] == "tool"
    assert validated["name"] == "math.calc"
    
    # Invalid action (missing name for tool)
    invalid_action = {
        "type": "tool",
        "args": {"expression": "2 + 2"}
    }
    
    with pytest.raises(ValueError):
        validate_action(invalid_action)

def test_output_sanitization():
    """Test output sanitization"""
    # Test with normal content
    normal_output = "This is normal output"
    sanitized = sanitize_output(normal_output)
    assert sanitized == normal_output
    
    # Test with potentially sensitive content
    sensitive_output = "API key: sk-1234567890abcdef"
    sanitized = sanitize_output(sensitive_output)
    # Should be masked
    assert "sk-1234567890abcdef" not in sanitized

def test_evaluation_framework():
    """Test evaluation framework"""
    async def dummy_agent(goal, max_steps):
        """Dummy agent for testing"""
        return {"result": f"Completed: {goal}", "success": True}
    
    # Create a simple evaluation task
    suite = EvalSuite("test_suite", "Test evaluation suite")
    
    def check_success(result):
        return result.get("success", False)
    
    suite.add_task(EvalTask(
        id="test_task",
        description="Test task",
        goal="test goal",
        success_criteria=check_success,
        max_steps=3
    ))
    
    # Run evaluation
    evaluator = AgentEvaluator(output_dir=tempfile.mkdtemp())
    results = asyncio.run(evaluator.run_suite(suite, dummy_agent))
    
    assert results["suite_name"] == "test_suite"
    assert results["total_tasks"] == 1
    assert results["successful_tasks"] == 1
    assert results["success_rate"] == 1.0

@pytest.mark.asyncio
async def test_math_calculation():
    """Test mathematical calculation capability"""
    result = await run_agent("Calculate 5 + 7", max_steps=3)
    
    # Should contain the result somewhere
    result_str = str(result).lower()
    assert any(answer in result_str for answer in ["12", "twelve"])

@pytest.mark.asyncio
async def test_file_operations():
    """Test file operation capabilities"""
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = Path(temp_dir) / "test.txt"
        goal = f"Create a file at {test_file} with the content 'Hello World'"
        
        result = await run_agent(goal, max_steps=5)
        
        # Check if the task was completed successfully
        result_str = str(result).lower()
        success_indicators = ["created", "written", "success", "completed"]
        assert any(indicator in result_str for indicator in success_indicators)

def test_configuration():
    """Test configuration management"""
    config = AgentConfig()
    
    # Test default values
    assert config.openai.model == "gpt-4o-mini"
    assert config.runtime.max_steps == 10
    assert config.safety.enable_content_filtering == True
    
    # Test configuration modification
    config.runtime.max_steps = 15
    assert config.runtime.max_steps == 15
    
    # Test configuration serialization
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config.to_file(f.name)
        
        # Load configuration back
        loaded_config = AgentConfig.from_file(f.name)
        assert loaded_config.runtime.max_steps == 15
        
        # Cleanup
        os.unlink(f.name)

def test_custom_tool_registration():
    """Test custom tool registration"""
    def custom_test_tool(args):
        return {"result": "custom tool executed"}
    
    # Register custom tool
    tools.register(ToolSpec(
        name="test.custom",
        schema={
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Test input"}
            }
        },
        fn=custom_test_tool,
        timeout_s=5.0
    ))
    
    # Verify tool is registered
    custom_tool = tools.get("test.custom")
    assert custom_tool is not None
    assert custom_tool.name == "test.custom"
    
    # Test tool execution
    result = custom_tool.fn({"input": "test"})
    assert result["result"] == "custom tool executed"

# Integration test
@pytest.mark.asyncio
async def test_integration_workflow():
    """Test complete workflow integration"""
    # Test a more complex workflow that exercises multiple components
    goal = """Think about the task, then calculate 3 * 4, and explain the result"""
    
    result = await run_agent(goal, max_steps=8)
    
    # Verify basic structure
    assert "result" in result
    assert "history" in result
    assert "trace_id" in result
    
    # Verify execution occurred
    assert len(result["history"]) > 0
    
    # Check for calculation result
    result_str = str(result).lower()
    assert "12" in result_str or "twelve" in result_str

if __name__ == "__main__":
    pytest.main([__file__])
