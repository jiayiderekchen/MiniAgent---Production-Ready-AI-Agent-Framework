#!/usr/bin/env python3
"""
Demo of complexity-based model routing in miniagent.

This example shows how the system automatically chooses between
deepseek-chat and deepseek-reasoner based on question complexity.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from miniagent.core.runtime import run_agent

async def demo_complexity_routing():
    """Demonstrate complexity routing with different types of questions."""
    
    print("🚀 Complexity Routing Demo")
    print("=" * 60)
    print("Watch how the system chooses models based on question complexity!")
    print("Look for 'Model selection:' messages in the logs.")
    print()
    
    # Simple questions that should use deepseek-chat
    simple_questions = [
        "What's the current time?",
        "Calculate 25 * 4",
        "What is the weather like?"
    ]
    
    # Complex questions that should use deepseek-reasoner
    complex_questions = [
        "Design a scalable microservices architecture for handling 1 million concurrent users with optimal performance and fault tolerance",
        "Analyze the philosophical and ethical implications of artificial general intelligence on society and human decision-making autonomy"
    ]
    
    print("📝 Testing Simple Questions (should use deepseek-chat):")
    print("-" * 50)
    
    for i, question in enumerate(simple_questions, 1):
        print(f"\n{i}. Simple Question: {question}")
        try:
            result = await run_agent(question, max_steps=2, quiet_mode=True)
            print(f"   ✅ Result: {result.get('result', 'No result')}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n\n🧠 Testing Complex Questions (should use deepseek-reasoner):")
    print("-" * 50)
    
    for i, question in enumerate(complex_questions, 1):
        print(f"\n{i}. Complex Question: {question[:60]}...")
        try:
            result = await run_agent(question, max_steps=3, quiet_mode=True)
            print(f"   ✅ Result: {result.get('result', 'No result')[:100]}...")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print(f"\n\n💡 Key Points:")
    print("- Simple questions automatically use 'deepseek-chat' (faster, cheaper)")
    print("- Complex questions automatically use 'deepseek-reasoner' (better reasoning)")
    print("- No manual configuration needed - it's all automatic!")
    print("- Check the logs above for 'Model selection:' messages to see the routing")

def main():
    """Run the demo."""
    try:
        asyncio.run(demo_complexity_routing())
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\nDemo failed: {e}")
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
