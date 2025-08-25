"""
Interactive Consent Mode Demo

This example demonstrates the new interactive consent system for MiniAgent.
It shows how the agent requests permission before performing file operations,
giving users explicit control over what the agent can do.
"""

import asyncio
import tempfile
import os
from pathlib import Path

# Import miniagent components
from miniagent import run_agent, AgentConfig, set_config, ConsentManager, set_consent_manager

async def demo_consent_modes():
    """Demonstrate different consent modes"""
    
    print("="*70)
    print("🔐 MINIAGENT INTERACTIVE CONSENT DEMO")
    print("="*70)
    print()
    print("This demo shows how the agent requests permission for file operations.")
    print("You'll see different scenarios with various consent settings.")
    print()
    
    # Create a temporary directory for safe operations
    temp_dir = Path(tempfile.mkdtemp(prefix="miniagent_consent_demo_"))
    print(f"Demo workspace: {temp_dir}")
    print()
    
    # Set up custom configuration
    config = AgentConfig()
    config.consent.enable_interactive_consent = True
    config.consent.auto_approve_safe_operations = True
    config.consent.safe_directories = [str(temp_dir), str(temp_dir) + "/"]
    config.runtime.max_steps = 8
    set_config(config)
    
    try:
        # Demo 1: File operations with consent
        print("\n" + "="*50)
        print("DEMO 1: File Operations with Interactive Consent")
        print("="*50)
        print("The agent will ask permission before creating files.")
        print("You can approve (a), deny (d), or set session preferences.")
        print()
        
        input("Press Enter to start Demo 1...")
        
        goal1 = f"Create a file called 'demo.txt' in {temp_dir} with a welcome message"
        result1 = await run_agent(goal1, max_steps=5, interactive_consent=True)
        
        print(f"\nDemo 1 Result: {result1.get('result', 'No result')}")
        
        # Demo 2: Multiple file operations
        print("\n" + "="*50)
        print("DEMO 2: Multiple File Operations")
        print("="*50)
        print("The agent will perform several file operations.")
        print("Try using 's' to approve the operation type for the session.")
        print()
        
        input("Press Enter to start Demo 2...")
        
        goal2 = f"Create three files in {temp_dir}: data1.txt, data2.txt, and summary.txt with different content"
        result2 = await run_agent(goal2, max_steps=10, interactive_consent=True)
        
        print(f"\nDemo 2 Result: {result2.get('result', 'No result')}")
        
        # Demo 3: Read operations (usually auto-approved)
        print("\n" + "="*50)
        print("DEMO 3: Read Operations (Usually Auto-Approved)")
        print("="*50)
        print("Read operations are typically auto-approved as safe.")
        print()
        
        input("Press Enter to start Demo 3...")
        
        goal3 = f"Read all .txt files in {temp_dir} and create a summary"
        result3 = await run_agent(goal3, max_steps=8, interactive_consent=True)
        
        print(f"\nDemo 3 Result: {result3.get('result', 'No result')}")
        
        # Demo 4: Dangerous operations
        print("\n" + "="*50)
        print("DEMO 4: High-Risk Operations")
        print("="*50)
        print("Delete operations always require explicit consent.")
        print()
        
        input("Press Enter to start Demo 4...")
        
        goal4 = f"Delete the file data1.txt from {temp_dir}"
        result4 = await run_agent(goal4, max_steps=5, interactive_consent=True)
        
        print(f"\nDemo 4 Result: {result4.get('result', 'No result')}")
        
    finally:
        # Cleanup
        print(f"\n🧹 Cleaning up demo workspace: {temp_dir}")
        import shutil
        try:
            shutil.rmtree(temp_dir)
            print("✅ Cleanup completed")
        except Exception as e:
            print(f"❌ Cleanup failed: {e}")


async def demo_configuration_options():
    """Demonstrate different consent configuration options"""
    
    print("\n" + "="*70)
    print("⚙️  CONSENT CONFIGURATION OPTIONS DEMO")
    print("="*70)
    print()
    
    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp(prefix="miniagent_config_demo_"))
    
    print("This demo shows different consent configuration options:")
    print("1. Auto-approve safe operations")
    print("2. Require consent for all operations")
    print("3. Safe directory configuration")
    print()
    
    try:
        # Configuration 1: Auto-approve safe operations
        print("Configuration 1: Auto-approve safe operations in safe directories")
        config1 = AgentConfig()
        config1.consent.enable_interactive_consent = True
        config1.consent.auto_approve_safe_operations = True
        config1.consent.safe_directories = [str(temp_dir)]
        set_config(config1)
        
        goal = f"Create a file info.txt in {temp_dir} with system information"
        print(f"Goal: {goal}")
        print("(This should auto-approve since it's in a safe directory)")
        print()
        
        result = await run_agent(goal, max_steps=5, interactive_consent=True, quiet_mode=True)
        print(f"Result: {result.get('result', 'No result')}")
        
        # Configuration 2: Require consent for all operations
        print("\n" + "-"*50)
        print("Configuration 2: Require consent for ALL operations")
        config2 = AgentConfig()
        config2.consent.enable_interactive_consent = True
        config2.consent.auto_approve_safe_operations = False
        config2.consent.auto_approve_read_operations = False
        set_config(config2)
        
        goal = f"Read the info.txt file from {temp_dir}"
        print(f"Goal: {goal}")
        print("(This will ask for consent even though it's just reading)")
        print()
        
        # For demo purposes, let's not actually run this one to avoid prompts
        print("(Skipped to avoid prompts in demo - would ask for consent)")
        
    finally:
        # Cleanup
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


async def demo_programmatic_consent():
    """Demonstrate programmatic consent management"""
    
    print("\n" + "="*70)
    print("💻 PROGRAMMATIC CONSENT MANAGEMENT DEMO")
    print("="*70)
    print()
    
    print("This demo shows how to programmatically manage consent:")
    
    # Create a custom consent manager
    consent_manager = ConsentManager(
        interactive=False,  # Non-interactive for this demo
        auto_approve_safe=True
    )
    
    # Configure safe directories
    temp_dir = Path(tempfile.mkdtemp(prefix="miniagent_programmatic_"))
    consent_manager.safe_directories.add(str(temp_dir))
    
    # Set the consent manager
    set_consent_manager(consent_manager)
    
    print("✅ Custom consent manager configured")
    print(f"   Safe directories: {consent_manager.safe_directories}")
    print(f"   Interactive mode: {consent_manager.interactive}")
    print(f"   Auto-approve safe: {consent_manager.auto_approve_safe}")
    
    try:
        # Test with non-interactive consent
        config = AgentConfig()
        config.consent.enable_interactive_consent = False  # Disable for this demo
        set_config(config)
        
        goal = f"Create a log file in {temp_dir} with current timestamp"
        print(f"\nRunning goal: {goal}")
        
        result = await run_agent(goal, max_steps=5, interactive_consent=False, quiet_mode=True)
        print(f"Result: {result.get('result', 'No result')}")
        
    finally:
        # Cleanup
        import shutil
        try:
            shutil.rmtree(temp_dir)
        except Exception:
            pass


async def main():
    """Main demo function"""
    
    print("Welcome to the MiniAgent Interactive Consent Demo!")
    print()
    print("Available demos:")
    print("1. Interactive consent for file operations")
    print("2. Configuration options demonstration")
    print("3. Programmatic consent management")
    print("0. Run all demos")
    print()
    
    while True:
        try:
            choice = input("Enter your choice (0-3, or 'q' to quit): ").strip()
            
            if choice == 'q':
                print("Goodbye!")
                break
            elif choice == '0':
                await demo_consent_modes()
                await demo_configuration_options()
                await demo_programmatic_consent()
                break
            elif choice == '1':
                await demo_consent_modes()
                break
            elif choice == '2':
                await demo_configuration_options()
                break
            elif choice == '3':
                await demo_programmatic_consent()
                break
            else:
                print("Invalid choice. Please enter 0-3 or 'q'.")
                continue
                
        except KeyboardInterrupt:
            print("\nDemo interrupted by user.")
            break
        except Exception as e:
            print(f"Demo error: {e}")
            break


if __name__ == "__main__":
    asyncio.run(main())
