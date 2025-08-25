import logging
from typing import Dict, Any
from .state import AgentState
from ..policy.planner import plan_next
from ..tools.registry import tools
from ..tools import builtin  # Import to register built-in tools
from ..exec.sandbox import run_tool
from ..guard.schema import validate_action, sanitize_output, input_validator
from ..guard.consent import get_consent_manager, set_consent_manager, ConsentManager, request_operation_consent
from ..config import get_config

# Logger will be configured by config system
logger = logging.getLogger(__name__)

async def run_agent(goal: str, max_steps: int = 4, show_thinking: bool = False, quiet_mode: bool = False, interactive_consent: bool = None) -> Dict[str, Any]:
    # Validate user input
    if not input_validator.validate_user_input(goal):
        return {"error": "Goal failed safety validation", "trace_id": None}
    
    # Initialize consent manager based on configuration and parameters
    config = get_config()
    
    # Determine if we should use interactive consent
    if interactive_consent is None:
        interactive_consent = config.consent.enable_interactive_consent
    
    # Set up consent manager
    consent_manager = ConsentManager(
        interactive=interactive_consent,
        auto_approve_safe=config.consent.auto_approve_safe_operations
    )
    
    # Configure safe directories from config
    consent_manager.safe_directories = set(config.consent.safe_directories)
    
    # Set the global consent manager
    set_consent_manager(consent_manager)
    
    if interactive_consent and not quiet_mode:
        print("🔐 Interactive consent mode is ENABLED")
        print("   The agent will ask for permission before file operations")
        print("   You can approve/deny each operation or set session-wide preferences")
        print()
    
    state = AgentState(goal=goal)
    
    # Store the goal in memory
    state.remember(f"Agent goal: {goal}", "episodic", {"type": "goal", "step": -1})
    
    logger.info(f"Starting agent with goal: {goal}")
    
    # Show goal unless in quiet mode
    if not quiet_mode:
        print("=" * 60)
        print(f"🎯 GOAL: {goal}")
        print("=" * 60)
        
        if show_thinking:
            print("🧠 AGENT THINKING IN REAL-TIME...")
            print("-" * 40)
    
    for step in range(max_steps):
        try:
            # Get relevant context from memory for planning
            context = state.get_context(goal, max_items=5)
            
            if show_thinking:
                print(f"\n🤔 Step {step + 1}: Planning next action...")
            
            action = plan_next(state, tools.list())
            
            # Validate action for safety
            try:
                action = validate_action(action)
            except ValueError as e:
                error_msg = f"Action validation failed: {e}"
                logger.error(error_msg)
                state.history.append({"step": step, "error": error_msg})
                continue
            
            state.history.append({"step": step, "action": action})
            
            # Store action in memory
            action_desc = f"Step {step}: {action.get('type', 'unknown')} action"
            if action.get('type') == 'tool':
                action_desc += f" using {action.get('name')} with args {action.get('args', {})}"
            elif action.get('type') == 'think':
                action_desc += f": {action.get('reasoning', 'thinking...')}"
            
            state.remember(action_desc, "episodic", {"type": "action", "step": step})
            
            if action.get("type") == "tool":
                tool_name = action.get("name", "unknown")
                tool_args = action.get("args", {})
                
                # Show tool usage unless in quiet mode
                if not quiet_mode:
                    print(f"\n🔧 Step {step + 1}: Using {tool_name}")
                
                if show_thinking:
                    args_preview = str(tool_args)
                    if len(args_preview) > 60:
                        args_preview = args_preview[:57] + "..."
                    print(f"   Args: {args_preview}")
                
                spec = tools.get(action["name"])
                if spec is None:
                    error_msg = f"Tool '{action['name']}' not found"
                    logger.error(error_msg)
                    state.history.append({"step": step, "error": error_msg})
                    if not quiet_mode:
                        print(f"   ❌ Error: {error_msg}")
                    continue
                
                # Check for user consent if this is a potentially risky operation
                needs_consent = await _check_if_consent_needed(tool_name, tool_args, config, interactive_consent)
                
                if needs_consent:
                    # Prepare consent request details
                    consent_details = {"args": tool_args}
                    target = _extract_operation_target(tool_name, tool_args)
                    
                    # Request consent
                    consent_granted = await request_operation_consent(
                        operation=tool_name,
                        target=target,
                        details=consent_details
                    )
                    
                    if not consent_granted:
                        error_msg = f"Operation '{tool_name}' denied by user"
                        logger.info(error_msg)
                        state.history.append({"step": step, "consent_denied": True, "operation": tool_name})
                        
                        if not quiet_mode:
                            print(f"   🚫 Operation denied by user")
                        
                        # Store consent denial in memory
                        state.remember(f"User denied operation: {tool_name} on {target}", "episodic", 
                                     {"type": "consent_denied", "step": step, "operation": tool_name})
                        
                        # Check for repeated denials to prevent infinite loops
                        denial_count = sum(1 for entry in state.history[-5:] 
                                         if entry.get("consent_denied") and entry.get("operation") == tool_name)
                        
                        if denial_count >= 2:
                            # Force finish after 2 denials of the same operation
                            logger.warning(f"Stopping after {denial_count} denials of {tool_name}")
                            if not quiet_mode:
                                print(f"   ⚠️  Stopping: repeated denials of {tool_name}")
                            
                            # Directly execute finish logic
                            final_result = f"I cannot complete this task because the user has denied permission for '{tool_name}' operations. Please manually perform this operation or grant permission if you'd like me to proceed."
                            
                            if not quiet_mode:
                                print(f"\n✅ Step {step + 1}: Task completed!")
                            
                            # Show final result
                            print("=" * 60)
                            print(f"🎉 FINAL RESULT:")
                            print(f"   {final_result}")
                            print("=" * 60)
                            
                            state.history.append({"step": step, "final_result": final_result})
                            state.remember(f"Task completed: {final_result}", "episodic", 
                                         {"type": "completion", "step": step})
                            
                            return {
                                "trace_id": state.trace_id,
                                "result": final_result,
                                "history": state.history,
                                "context": state.get_context(goal, max_items=3)
                            }
                        
                        continue
                
                result = await run_tool(spec, action.get("args", {}))
                
                # Sanitize tool output
                result = sanitize_output(result)
                
                state.history.append({"step": step, "observation": result})
                
                if not quiet_mode:
                    if isinstance(result, dict) and 'error' in result:
                        print(f"   ❌ Failed: {result['error']}")
                    else:
                        print(f"   ✅ Completed")
                    
                    if show_thinking:
                        # Show brief result preview
                        if isinstance(result, dict):
                            for key in ['result', 'output', 'content', 'success']:
                                if key in result:
                                    val = str(result[key])
                                    if len(val) > 80:
                                        val = val[:77] + "..."
                                    print(f"   📋 {key}: {val}")
                                    break
                
                # Store tool result in memory
                result_str = str(result)[:500]  # Truncate long results
                state.remember(f"Tool {action['name']} result: {result_str}", "semantic", 
                             {"type": "tool_result", "step": step, "tool": action['name']})
                
                logger.info(f"Step {step}: Used tool {action['name']}")
                
            elif action.get("type") == "think":
                reasoning = action.get("reasoning", "thinking...")
                
                if not quiet_mode:
                    print(f"\n💭 Step {step + 1}: Thinking...")
                if show_thinking and not quiet_mode:
                    lines = reasoning.split('\n')
                    for line in lines:
                        if line.strip():
                            print(f"   {line.strip()}")
                
                state.history.append({"step": step, "thought": reasoning})
                state.mem.notes[f"thought_{step}"] = reasoning
                
                # Store reasoning in memory
                state.remember(f"Reasoning at step {step}: {reasoning}", "semantic", 
                             {"type": "reasoning", "step": step})
                
                logger.info(f"Step {step}: Thinking - {reasoning[:100]}...")
                
            elif action.get("type") == "finish":
                final_result = action.get("output", "")
                
                if not quiet_mode:
                    print(f"\n✅ Step {step + 1}: Task completed!")
                
                # Always show final result (even in quiet mode)
                print("=" * 60)
                print(f"🎉 FINAL RESULT:")
                print(f"   {final_result}")
                print("=" * 60)
                
                # Store final result in memory
                state.remember(f"Final result: {final_result}", "episodic", 
                             {"type": "result", "step": step, "goal": goal})
                
                logger.info(f"Agent finished at step {step}")
                
                return {
                    "trace_id": state.trace_id, 
                    "result": final_result, 
                    "history": state.history,
                    "memory_summary": state.get_context(goal, max_items=3)
                }
                
        except Exception as e:
            error_msg = f"Error at step {step}: {str(e)}"
            logger.error(error_msg)
            state.history.append({"step": step, "error": error_msg})
            
            # Store error in memory
            state.remember(error_msg, "episodic", {"type": "error", "step": step})
    
    logger.info(f"Agent reached max steps ({max_steps})")
    
    # Show clean max steps message (always shown, even in quiet mode)
    if not quiet_mode:
        print("\n⏰ Reached maximum steps limit")
    print("=" * 60)
    print(f"🎉 FINAL RESULT:")
    print(f"   Task partially completed after {max_steps} steps")
    print("=" * 60)
    
    return {
        "trace_id": state.trace_id, 
        "result": f"Task partially completed after {max_steps} steps", 
        "history": state.history,
        "memory_summary": state.get_context(goal, max_items=3)
    }


async def _check_if_consent_needed(tool_name: str, tool_args: Dict[str, Any], config, interactive_consent: bool) -> bool:
    """Check if a tool operation requires user consent"""
    
    # If consent is disabled for this run, no consent needed
    if not interactive_consent:
        return False
    
    # File operations that typically require consent
    file_operations = {
        "file.write": config.consent.require_consent_for_write,
        "file.delete": config.consent.require_consent_for_delete,
        "file.mkdir": config.consent.require_consent_for_write,
    }
    
    # Execution operations that require consent
    execution_operations = {
        "shell.exec": config.consent.require_consent_for_execute,
        "code.python": config.consent.require_consent_for_execute,
    }
    
    # Read operations (may auto-approve if configured)
    read_operations = {
        "file.read": not config.consent.auto_approve_read_operations,
        "file.list": not config.consent.auto_approve_read_operations,
    }
    
    # Check specific operation requirements
    all_operations = {**file_operations, **execution_operations, **read_operations}
    
    return all_operations.get(tool_name, False)


def _extract_operation_target(tool_name: str, tool_args: Dict[str, Any]) -> str:
    """Extract the target of an operation for consent display"""
    
    # Common target fields
    target_fields = ["path", "command", "code", "q", "query", "url"]
    
    for field in target_fields:
        if field in tool_args:
            value = tool_args[field]
            if isinstance(value, str):
                # Truncate long values for display
                if len(value) > 100:
                    return value[:97] + "..."
                return value
            return str(value)
    
    # Fallback to tool name if no specific target found
    return f"<{tool_name} operation>"
