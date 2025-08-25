import asyncio
import argparse
import sys
import json
from pathlib import Path
from .core.runtime import run_agent
from .config import get_config, create_default_config, AgentConfig
from .eval.harness import AgentEvaluator, create_basic_eval_suite, create_advanced_eval_suite
import logging

logger = logging.getLogger(__name__)

def cmd_run(args):
    """Run the agent with a goal"""
    config = get_config()
    
    # Set cleaner logging for better user experience
    import logging
    if not getattr(args, 'verbose', False):
        # Suppress verbose logs for clean output
        logging.getLogger('sentence_transformers').setLevel(logging.WARNING)
        logging.getLogger('miniagent.policy.planner_llm').setLevel(logging.WARNING)
        logging.getLogger('miniagent.policy.complexity_analyzer').setLevel(logging.WARNING)
        logging.getLogger('miniagent.policy.model_selector').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('miniagent.core.runtime').setLevel(logging.WARNING)
        # Suppress tokenizer warnings
        import os
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    
    if not config.llm.get_active_api_key():
        provider = config.llm.provider
        print(f"Error: {provider.title()} API key not configured.")
        if provider == "openai":
            print("Please set OPENAI_API_KEY environment variable or create a config file with 'miniagent config'")
        elif provider == "deepseek":
            print("Please set DEEPSEEK_API_KEY environment variable or create a config file with 'miniagent config'")
        return 1
    
    try:
        # Enable real-time thinking if verbose or if thinking flag is set
        show_thinking = args.verbose or getattr(args, 'thinking', False)
        quiet_mode = getattr(args, 'quiet', False)
        
        # Determine consent mode
        interactive_consent = None
        if getattr(args, 'interactive', False):
            interactive_consent = True
        elif getattr(args, 'no_consent', False):
            interactive_consent = False
        # If neither flag is set, use config default (handled in run_agent)
        
        result = asyncio.run(run_agent(
            args.goal, 
            max_steps=args.steps, 
            show_thinking=show_thinking, 
            quiet_mode=quiet_mode,
            interactive_consent=interactive_consent
        ))
        
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            # If we already showed thinking in real-time, just show a summary
            if show_thinking:
                print(f"\n🎉 TASK COMPLETED!")
                print(f"📋 Final Answer: {result.get('result', 'No result')}")
            else:
                # Show full post-execution analysis
                print("=" * 60)
                print(f"🎯 GOAL: {args.goal}")
                print("=" * 60)
            
            # Show thought process and execution steps (only if not already shown)
            if 'history' in result and not show_thinking:
                print("\n🧠 AGENT THOUGHT PROCESS:")
                print("-" * 40)
                
                step_count = 0
                for entry in result['history']:
                    if 'action' in entry:
                        action = entry['action']
                        step_count += 1
                        
                        if action.get('type') == 'think':
                            print(f"\n💭 Step {step_count}: THINKING")
                            reasoning = action.get('reasoning', 'Processing...')
                            # Format reasoning nicely
                            lines = reasoning.split('\n')
                            for line in lines:
                                if line.strip():
                                    print(f"   {line.strip()}")
                        
                        elif action.get('type') == 'tool':
                            print(f"\n🔧 Step {step_count}: USING TOOL")
                            print(f"   Tool: {action.get('name', 'unknown')}")
                            args_str = str(action.get('args', {}))
                            if len(args_str) > 80:
                                args_str = args_str[:77] + "..."
                            print(f"   Args: {args_str}")
                        
                        elif action.get('type') == 'finish':
                            print(f"\n✅ Step {step_count}: COMPLETING TASK")
                            print(f"   Final answer ready")
                    
                    elif 'thought' in entry:
                        print(f"\n💭 REFLECTION:")
                        thought = entry['thought']
                        lines = thought.split('\n')
                        for line in lines:
                            if line.strip():
                                print(f"   {line.strip()}")
                    
                    elif 'observation' in entry:
                        obs = entry['observation']
                        print(f"   📋 Result: ", end="")
                        
                        # Format observation nicely
                        if isinstance(obs, dict):
                            if 'error' in obs:
                                print(f"❌ {obs['error']}")
                            elif 'success' in obs:
                                print(f"✅ {obs.get('success', 'Success')}")
                            else:
                                # Show key results - handle different result types
                                key_results = []
                                
                                # Handle web search results (enhanced display)
                                if 'results' in obs and 'summary' in obs:
                                    count = obs.get('count', 0)
                                    summary = obs.get('summary', 'No summary')[:120]
                                    key_results.append(f"Found {count} results: {summary}")
                                    
                                    if count > 0:
                                        # Show top results with sources
                                        top_results = obs.get('results', [])[:2]
                                        for i, result in enumerate(top_results):
                                            title = result.get('title', 'No title')[:60]
                                            source = result.get('source', 'Web')
                                            key_results.append(f"{i+1}. {title} ({source})")
                                
                                # Handle stock/weather info tool results
                                elif 'guidance' in obs and 'message' in obs:
                                    message = obs.get('message', '')[:60]
                                    suggestion = obs.get('suggestion', '')[:80]
                                    key_results.append(f"{message}")
                                    if suggestion:
                                        key_results.append(f"Suggestion: {suggestion}")
                                
                                # Handle other standard result types
                                if not key_results:
                                    for key in ['result', 'output', 'content', 'answer']:
                                        if key in obs:
                                            val = str(obs[key])
                                            if len(val) > 60:
                                                val = val[:57] + "..."
                                            key_results.append(f"{key}: {val}")
                                
                                # Check if it's a boolean success indicator that needs better display
                                if not key_results and isinstance(obs, bool) and obs:
                                    key_results.append("Operation completed successfully")
                                elif not key_results and isinstance(obs, dict):
                                    # Fallback for complex dictionaries
                                    keys = list(obs.keys())[:3]
                                    key_results.append(f"Data available: {', '.join(keys)}")
                                
                                if key_results:
                                    print(" | ".join(key_results))
                                else:
                                    print("Operation completed")
                        else:
                            obs_str = str(obs)
                            if len(obs_str) > 80:
                                obs_str = obs_str[:77] + "..."
                            print(obs_str)
                    
                    elif 'error' in entry:
                        print(f"   ❌ Error: {entry['error']}")
                
                print("\n" + "-" * 40)
            
            # Show final result (only if runtime didn't already show it)
            # The runtime shows final result when agent finishes successfully
            # We only need to show it here if the task was incomplete
            result_text = result.get('result', '')
            if result_text and result_text.strip() and not result_text.startswith('Task partially completed'):
                # Only show if it's a meaningful result and not already displayed by runtime
                history = result.get('history', [])
                agent_finished_successfully = any(
                    entry.get('action', {}).get('type') == 'finish' 
                    for entry in history 
                    if 'action' in entry
                )
                
                if not agent_finished_successfully:
                    print(f"\n🎉 FINAL RESULT:")
                    print(f"   {result_text}")
                    print("=" * 60)
            
            # Show memory summary if available
            if 'memory_summary' in result and not args.json:
                memory_summary = result['memory_summary']
                total_memories = sum(len(memories) for memories in memory_summary.values() if memories)
                if total_memories > 0:
                    print(f"\n🧠 MEMORIES CREATED: {total_memories} items")
                    for memory_type, memories in memory_summary.items():
                        if memories:
                            print(f"   {memory_type.title()}: {len(memories)} items")
            
            # Show verbose details if requested
            if args.verbose:
                print(f"\n📊 EXECUTION DETAILS:")
                print(f"   Trace ID: {result.get('trace_id', 'N/A')}")
                print(f"   Total Steps: {len([e for e in result.get('history', []) if 'action' in e])}")
                print(f"   History Entries: {len(result.get('history', []))}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Agent execution failed: {e}")
        print(f"Error: {e}")
        return 1

def cmd_eval(args):
    """Run evaluation suites"""
    config = get_config()
    
    if not config.llm.get_active_api_key():
        provider = config.llm.provider
        print(f"Error: {provider.title()} API key not configured.")
        return 1
    
    evaluator = AgentEvaluator()
    
    try:
        if args.suite == "basic":
            suite = create_basic_eval_suite()
        elif args.suite == "advanced":
            suite = create_advanced_eval_suite()
        else:
            print(f"Unknown evaluation suite: {args.suite}")
            return 1
        
        print(f"Running evaluation suite: {suite.name}")
        result = asyncio.run(evaluator.run_suite(suite, run_agent))
        
        if args.json:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"\nEvaluation Results for {result['suite_name']}:")
            print(f"Success Rate: {result['success_rate']:.2%}")
            print(f"Average Score: {result['average_score']:.2f}")
            print(f"Total Time: {result['total_execution_time']:.2f}s")
            print(f"Successful Tasks: {result['successful_tasks']}/{result['total_tasks']}")
            
            if args.verbose:
                print("\nDetailed Results:")
                for task_result in result['results']:
                    status = "✓" if task_result['success'] else "✗"
                    print(f"  {status} {task_result['task_id']}: {task_result['execution_time']:.2f}s")
                    if task_result['error']:
                        print(f"    Error: {task_result['error']}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        print(f"Error: {e}")
        return 1

def cmd_config(args):
    """Manage configuration"""
    if args.action == "create":
        create_default_config(args.output)
        return 0
    elif args.action == "show":
        config = get_config()
        current_provider = config.llm.provider
        active_config = config.llm.get_active_config()
        
        print(f"Current LLM Provider: {current_provider.title()}")
        print(f"Active Model: {active_config.model}")
        print(f"API Key Set: {'✓' if active_config.api_key else '✗'}")
        print()
        
        config_dict = {
            'llm': {
                'provider': config.llm.provider,
                'openai': config.llm.openai.__dict__,
                'deepseek': config.llm.deepseek.__dict__
            },
            'sandbox': config.sandbox.__dict__,
            'memory': config.memory.__dict__,
            'safety': config.safety.__dict__,
            'runtime': config.runtime.__dict__
        }
        print(json.dumps(config_dict, indent=2))
        return 0
    else:
        print(f"Unknown config action: {args.action}")
        return 1

def cmd_provider(args):
    """Switch LLM provider"""
    if args.provider_name not in ["deepseek", "openai"]:
        print(f"Error: Unsupported provider '{args.provider_name}'")
        print("Supported providers: deepseek, openai")
        return 1
    
    config = get_config()
    config.llm.provider = args.provider_name
    
    # Save to config file
    config_file = "./agent_config.json"
    config.to_file(config_file)
    
    active_config = config.llm.get_active_config()
    print(f"✓ Switched to {args.provider_name.title()} provider")
    print(f"  Model: {active_config.model}")
    print(f"  API Key: {'✓ Set' if active_config.api_key else '✗ Not set'}")
    
    if not active_config.api_key:
        if args.provider_name == "openai":
            print("  Set OPENAI_API_KEY environment variable or update config file")
        elif args.provider_name == "deepseek":
            print("  Set DEEPSEEK_API_KEY environment variable or update config file")
    
    return 0

def cmd_tools(args):
    """List available tools"""
    from .tools.registry import tools
    
    tool_list = tools.list()
    
    if args.json:
        tool_data = []
        for tool in tool_list:
            tool_data.append({
                "name": tool.name,
                "schema": tool.schema,
                "timeout": tool.timeout_s
            })
        print(json.dumps(tool_data, indent=2))
    else:
        print(f"Available Tools ({len(tool_list)}):")
        print("=" * 50)
        for tool in tool_list:
            print(f"  {tool.name}")
            if 'description' in tool.schema:
                print(f"    {tool.schema['description']}")
            if 'properties' in tool.schema:
                params = list(tool.schema['properties'].keys())
                print(f"    Parameters: {', '.join(params)}")
            print()
    
    return 0

def main():
    parser = argparse.ArgumentParser(description="MiniAgent - A comprehensive AI agent framework")
    parser.add_argument("--config", type=str, help="Path to configuration file")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run the agent with a goal")
    run_parser.add_argument("goal", type=str, help="Agent goal, e.g., 'research X'")
    run_parser.add_argument("--steps", type=int, default=6, help="Max reasoning/tool steps")
    run_parser.add_argument("--thinking", action="store_true", help="Show real-time agent thinking process")
    run_parser.add_argument("--quiet", "-q", action="store_true", help="Minimal output - only show final result")
    run_parser.add_argument("--interactive", "--consent", action="store_true", help="Enable interactive consent mode for file operations")
    run_parser.add_argument("--no-consent", action="store_true", help="Disable interactive consent mode (override config)")
    run_parser.set_defaults(func=cmd_run)
    
    # Eval command
    eval_parser = subparsers.add_parser("eval", help="Run evaluation suites")
    eval_parser.add_argument("suite", choices=["basic", "advanced"], help="Evaluation suite to run")
    eval_parser.set_defaults(func=cmd_eval)
    
    # Config command
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_parser.add_argument("action", choices=["create", "show"], help="Configuration action")
    config_parser.add_argument("--output", type=str, default="./agent_config.json", help="Output file for create action")
    config_parser.set_defaults(func=cmd_config)
    
    # Tools command
    tools_parser = subparsers.add_parser("tools", help="List available tools")
    tools_parser.set_defaults(func=cmd_tools)
    
    # Provider command
    provider_parser = subparsers.add_parser("provider", help="Switch LLM provider")
    provider_parser.add_argument("provider_name", choices=["deepseek", "openai"], help="LLM provider to use")
    provider_parser.set_defaults(func=cmd_provider)
    
    args = parser.parse_args()
    
    # Load custom config if provided
    if args.config:
        from .config import set_config
        custom_config = AgentConfig.from_file(args.config)
        set_config(custom_config)
    
    # Handle legacy usage (direct goal argument)
    if not hasattr(args, 'func'):
        if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
            # Legacy mode: miniagent "goal"
            args.goal = sys.argv[1]
            args.steps = 6
            for arg in sys.argv[2:]:
                if arg.startswith('--steps='):
                    args.steps = int(arg.split('=')[1])
            return cmd_run(args)
        else:
            parser.print_help()
            return 0
    
    return args.func(args)

if __name__ == "__main__":
    sys.exit(main())
