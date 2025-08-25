#!/usr/bin/env python3
"""
Thinking Process Demo

This script demonstrates the enhanced thought process visualization
capabilities of the MiniAgent framework.
"""

import asyncio
import os
from miniagent.core.runtime import run_agent

async def demo_thinking():
    """Demonstrate the thinking process with various task types"""
    
    print("🚀 MiniAgent Thinking Process Demo")
    print("=" * 50)
    
    # Test tasks that showcase different types of thinking
    test_tasks = [
        "Calculate the area of a circle with radius 7",
        "Think about the steps to make a sandwich, then list them",
        "What is 15 + 27 and explain your reasoning",
        "Create a simple poem about AI",
    ]
    
    for i, task in enumerate(test_tasks, 1):
        print(f"\n📝 Demo {i}: {task}")
        print("─" * 50)
        
        try:
            result = await run_agent(task, max_steps=5, show_thinking=True)
            
            # Small pause between demos
            print("\n⏳ (pausing 2 seconds before next demo...)")
            await asyncio.sleep(2)
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            break
    
    print("\n🎉 Demo completed!")
    print("Try the CLI commands:")
    print("  miniagent run 'your task here' --thinking")
    print("  miniagent run 'your task here' --verbose")

if __name__ == "__main__":
    # Check for API key
    if not os.getenv('OPENAI_API_KEY'):
        print("⚠️  Please set OPENAI_API_KEY environment variable first")
        print("Example: export OPENAI_API_KEY=your-key-here")
        exit(1)
    
    asyncio.run(demo_thinking())
