"""
Comprehensive MiniAgent Demo

This example demonstrates the full capabilities of the enhanced MiniAgent framework:
- Multi-step reasoning and planning
- Tool usage (file operations, web search, calculations, code execution)
- Memory system (semantic, episodic, working memory)
- Safety guardrails and validation
- Evaluation framework
- Configuration management
"""

import asyncio
import os
import json
from pathlib import Path
import logging

# Import miniagent components
from miniagent.core.runtime import run_agent
from miniagent.config import AgentConfig, get_config, set_config
from miniagent.eval.harness import (
    AgentEvaluator, 
    create_basic_eval_suite, 
    create_advanced_eval_suite,
    EvalSuite,
    EvalTask
)
from miniagent.tools.registry import tools
from miniagent.exec.sandbox import get_sandbox_stats, cleanup_sandbox

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def demo_basic_agent():
    """Demonstrate basic agent capabilities"""
    print("\n" + "="*60)
    print("DEMO 1: Basic Agent Capabilities")
    print("="*60)
    
    goals = [
        "Calculate the area of a circle with radius 5",
        "Create a file called 'demo.txt' with a hello message",
        "Explain what machine learning is in simple terms"
    ]
    
    for goal in goals:
        print(f"\nGOAL: {goal}")
        print("-" * 40)
        
        result = await run_agent(goal, max_steps=5)
        print(f"RESULT: {result.get('result', 'No result')}")
        
        if 'memory_summary' in result:
            memory_count = sum(len(memories) for memories in result['memory_summary'].values())
            print(f"MEMORIES CREATED: {memory_count}")

async def demo_complex_task():
    """Demonstrate complex multi-step task"""
    print("\n" + "="*60)
    print("DEMO 2: Complex Multi-Step Task")
    print("="*60)
    
    goal = """Create a simple data analysis report:
    1. Generate some sample data (name, age, score) for 5 people
    2. Save it to a CSV file
    3. Calculate the average age and score
    4. Write a summary report with findings"""
    
    print(f"GOAL: {goal}")
    print("-" * 40)
    
    result = await run_agent(goal, max_steps=12)
    print(f"RESULT: {result.get('result', 'No result')}")
    
    # Show execution history
    if 'history' in result:
        print(f"\nEXECUTION STEPS: {len(result['history'])}")
        for i, step in enumerate(result['history'][:10]):  # Show first 10 steps
            if 'action' in step:
                action = step['action']
                print(f"  Step {i}: {action.get('type', 'unknown')} - {action.get('name', '')}")

async def demo_evaluation():
    """Demonstrate evaluation framework"""
    print("\n" + "="*60)
    print("DEMO 3: Agent Evaluation")
    print("="*60)
    
    evaluator = AgentEvaluator()
    
    # Run basic evaluation suite
    print("Running basic evaluation suite...")
    basic_suite = create_basic_eval_suite()
    basic_results = await evaluator.run_suite(basic_suite, run_agent)
    
    print(f"\nBasic Evaluation Results:")
    print(f"  Success Rate: {basic_results['success_rate']:.1%}")
    print(f"  Average Score: {basic_results['average_score']:.2f}")
    print(f"  Total Time: {basic_results['total_execution_time']:.1f}s")
    
    # Show individual task results
    for task_result in basic_results['results']:
        status = "✓" if task_result['success'] else "✗"
        print(f"  {status} {task_result['task_id']}: {task_result['execution_time']:.1f}s")

async def demo_custom_evaluation():
    """Demonstrate custom evaluation tasks"""
    print("\n" + "="*60)
    print("DEMO 4: Custom Evaluation Tasks")
    print("="*60)
    
    # Create custom evaluation suite
    custom_suite = EvalSuite(
        name="custom_demo",
        description="Custom tasks for demo"
    )
    
    def check_file_creation(result):
        """Check if agent successfully created a file"""
        return "created" in str(result).lower() or "written" in str(result).lower()
    
    def check_calculation(result):
        """Check if agent performed calculation correctly"""
        result_str = str(result).lower()
        return any(num in result_str for num in ["42", "42.0", "forty-two"])
    
    custom_suite.add_task(EvalTask(
        id="file_task",
        description="File creation task",
        goal="Create a file named 'custom_test.txt' with the content 'This is a test'",
        success_criteria=check_file_creation,
        max_steps=3
    ))
    
    custom_suite.add_task(EvalTask(
        id="math_task", 
        description="Mathematical calculation",
        goal="What is 6 times 7?",
        success_criteria=check_calculation,
        max_steps=3
    ))
    
    evaluator = AgentEvaluator()
    results = await evaluator.run_suite(custom_suite, run_agent)
    
    print(f"Custom Evaluation Results:")
    print(f"  Success Rate: {results['success_rate']:.1%}")
    print(f"  Tasks Completed: {results['successful_tasks']}/{results['total_tasks']}")

def demo_configuration():
    """Demonstrate configuration management"""
    print("\n" + "="*60)
    print("DEMO 5: Configuration Management")
    print("="*60)
    
    # Show current configuration
    config = get_config()
    print("Current Configuration:")
    print(f"  OpenAI Model: {config.openai.model}")
    print(f"  Max Memory: {config.sandbox.max_memory_mb}MB")
    print(f"  Memory Directory: {config.memory.persist_dir}")
    print(f"  Safety Enabled: {config.safety.enable_content_filtering}")
    print(f"  Max Steps: {config.runtime.max_steps}")
    
    # Create a custom configuration
    custom_config = AgentConfig()
    custom_config.runtime.max_steps = 8
    custom_config.sandbox.max_memory_mb = 256
    custom_config.safety.max_output_length = 5000
    
    print(f"\nCustom Configuration Example:")
    print(f"  Max Steps: {custom_config.runtime.max_steps}")
    print(f"  Max Memory: {custom_config.sandbox.max_memory_mb}MB")
    print(f"  Max Output Length: {custom_config.safety.max_output_length}")

def demo_tools():
    """Demonstrate available tools"""
    print("\n" + "="*60)
    print("DEMO 6: Available Tools")
    print("="*60)
    
    tool_list = tools.list()
    print(f"Total Available Tools: {len(tool_list)}")
    
    # Group tools by category
    categories = {}
    for tool in tool_list:
        category = tool.name.split('.')[0] if '.' in tool.name else 'other'
        if category not in categories:
            categories[category] = []
        categories[category].append(tool.name)
    
    for category, tool_names in categories.items():
        print(f"\n{category.title()} Tools ({len(tool_names)}):")
        for tool_name in sorted(tool_names):
            print(f"  - {tool_name}")

def demo_sandbox_stats():
    """Demonstrate sandbox statistics"""
    print("\n" + "="*60)
    print("DEMO 7: Sandbox Statistics")
    print("="*60)
    
    stats = get_sandbox_stats()
    if 'error' not in stats:
        print("Sandbox Resource Usage:")
        print(f"  Peak Memory: {stats.get('memory_peak_kb', 0)/1024:.1f} MB")
        print(f"  CPU Time (User): {stats.get('cpu_time_user', 0):.2f}s")
        print(f"  CPU Time (System): {stats.get('cpu_time_system', 0):.2f}s")
        print(f"  Active Temp Dirs: {stats.get('temp_dirs_active', 0)}")
    else:
        print(f"Could not get sandbox stats: {stats['error']}")

async def main():
    """Run all demonstrations"""
    print("MiniAgent Comprehensive Demo")
    print("This demo showcases the full capabilities of the enhanced MiniAgent framework.")
    
    # Check if OpenAI API key is available
    if not os.getenv('OPENAI_API_KEY'):
        print("\n⚠️  WARNING: OPENAI_API_KEY not set.")
        print("Some demonstrations may not work without an API key.")
        print("Set the environment variable to see full functionality.\n")
    
    try:
        # Run all demonstrations
        await demo_basic_agent()
        await demo_complex_task()
        await demo_evaluation()
        await demo_custom_evaluation()
        
        demo_configuration()
        demo_tools()
        demo_sandbox_stats()
        
        print("\n" + "="*60)
        print("DEMO COMPLETE")
        print("="*60)
        print("All demonstrations completed successfully!")
        print("Check the generated files and logs for more details.")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        print(f"\nDemo failed with error: {e}")
    
    finally:
        # Cleanup
        cleanup_sandbox()
        print("\nCleaned up sandbox resources.")

if __name__ == "__main__":
    asyncio.run(main())
