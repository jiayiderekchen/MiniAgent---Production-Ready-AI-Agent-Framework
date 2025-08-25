from typing import Dict, Any, List
import os
import json
from ..tools.registry import ToolSpec
from ..config import get_config
from .model_selector import select_model_for_question
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

def plan_next(state, tools_available: List[ToolSpec]) -> Dict[str, Any]:
    """Universal LLM planner with dynamic model selection based on complexity"""
    config = get_config()
    
    # Build context for complexity analysis
    context = ""
    if state.history:
        context_parts = []
        for entry in state.history[-3:]:  # Last 3 steps for context
            if "action" in entry:
                action = entry["action"]
                if action.get('type') == 'tool':
                    context_parts.append(f"Used {action.get('name')} tool")
                elif action.get('type') == 'think':
                    context_parts.append("Performed thinking step")
        context = "; ".join(context_parts)
    
    # Select appropriate model based on complexity
    model_selection = select_model_for_question(state.goal, context)
    llm_config = model_selection['config']
    
    # Log model selection
    if model_selection['routing_enabled']:
        complexity_info = model_selection['complexity_analysis']
        logger.info(
            f"Selected model: {model_selection['model']} "
            f"(complex: {model_selection['is_complex']}) "
            f"for goal: '{state.goal[:50]}...'"
        )
        logger.debug(f"Complexity reasoning: {complexity_info['reasoning'] if complexity_info else 'N/A'}")
    else:
        logger.info(f"Using default model: {llm_config.model} (complexity routing disabled)")
    
    # Check if we have an API key
    if not llm_config.api_key:
        return {
            "type": "finish",
            "output": f"No API key configured for {config.llm.provider}. Please set the appropriate environment variable."
        }
    
    # Create OpenAI-compatible client (works with DeepSeek too)
    client = OpenAI(
        api_key=llm_config.api_key,
        base_url=llm_config.base_url
    )
    
    # Build context from history
    context = f"Goal: {state.goal}\n\n"
    if state.history:
        context += "Previous steps:\n"
        for entry in state.history[-10:]:  # Last 10 steps to avoid context overflow
            if "action" in entry:
                action = entry["action"]
                context += f"- Step {entry['step']}: {action.get('type', 'unknown')} action"
                if action.get('type') == 'tool':
                    context += f" using {action.get('name')} with args {action.get('args', {})}"
                elif action.get('type') == 'think':
                    context += f": {action.get('reasoning', 'thinking...')}"
                context += "\n"
            elif "consent_denied" in entry and entry["consent_denied"]:
                # Clearly show that user denied the operation
                operation = entry.get("operation", "unknown operation")
                context += f"- Step {entry['step']}: USER DENIED operation '{operation}' - DO NOT retry this operation\n"
            if "observation" in entry:
                obs = entry["observation"]
                # For weather/stock tools, include full response to avoid loops
                if isinstance(obs, dict) and any(key in obs for key in ['guidance', 'message', 'alternatives']):
                    context += f"  Result: {str(obs)}\n"
                # For web search results, include comprehensive information to help LLM understand what was found
                elif isinstance(obs, dict) and 'results' in obs and 'summary' in obs:
                    summary = obs.get('summary', 'No summary')
                    results_count = obs.get('count', 0)
                    sample_results = obs.get('results', [])[:3]  # Show first 3 results
                    
                    # Build comprehensive context with actual search content
                    result_text = f"Web search found {results_count} results with valuable information. "
                    if sample_results:
                        result_text += "Key findings: "
                        for i, result in enumerate(sample_results):
                            snippet = result.get('snippet', '')[:200]
                            title = result.get('title', '')
                            if snippet and snippet != title:
                                result_text += f" [{i+1}] {snippet}"
                    
                    result_text += " [IMPORTANT: Use this search information to provide a comprehensive answer with the 'finish' function. Do not search again.]"
                    context += f"  Result: {result_text}\n"
                else:
                    obs_str = str(obs)[:200]  # Truncate other long observations
                    context += f"  Result: {obs_str}\n"
    
    # Convert tools to OpenAI function format
    tool_functions = []
    for tool in tools_available:
        function_def = {
            "type": "function",
            "function": {
                "name": tool.name.replace(".", "_"),  # OpenAI doesn't like dots in function names
                "description": f"Tool: {tool.name}",
                "parameters": tool.schema
            }
        }
        tool_functions.append(function_def)
    
    # Debug logging for tools
    logger.info(f"Available tools: {[t.name for t in tools_available]}")
    logger.info(f"Tool functions created: {len(tool_functions)}")
    logger.info(f"Using {config.llm.provider} provider with model {llm_config.model}")
    
    # Add special thinking and finishing functions
    tool_functions.extend([
        {
            "type": "function", 
            "function": {
                "name": "think",
                "description": "Take a moment to think and reason about the current situation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reasoning": {"type": "string", "description": "Your reasoning and thoughts"}
                    },
                    "required": ["reasoning"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "finish",
                "description": "Complete the task and provide the final answer",
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "output": {"type": "string", "description": "The final answer or result"}
                    },
                    "required": ["output"]
                }
            }
        }
    ])

    system_prompt = f"""You are an AI agent that must use the appropriate tool for each task.

Available tools: {', '.join([t.name for t in tools_available])}

GOAL: {state.goal}

INSTRUCTIONS:
- FIRST DECIDE: Can you answer this question directly from your knowledge? If YES, use "finish" immediately with your answer
- If the question requires CURRENT/REAL-TIME data (weather, stock prices, breaking news, current date/time), then use appropriate tools
- If the goal asks to "calculate" or involves math (like "15 * 8"), use math_calc tool with the expression
- If you need to create/read files, use file tools
- For WEATHER queries, use weather.info tool ONCE, then immediately finish with the guidance provided
- For STOCK PRICE queries, use stock.info tool ONCE, then immediately finish with the guidance provided
- For DATE/TIME queries ("what is the date today?", "what time is it?"), use shell.exec tool with command "date" to get current information
- For topics requiring CURRENT information or research, use web.search tool which provides comprehensive results
- Use think only if you need to analyze a complex problem first
- Use finish when you have the complete answer
- PREFER direct answers over tool usage for basic facts, definitions, historical information, and general knowledge
- IMPORTANT: Current date/time is NOT basic knowledge - it changes daily and requires real-time data

CRITICAL: AVOID INFINITE LOOPS AND HANDLE USER DENIALS
- If a tool has been used and provided any response, don't call it again with the same or similar arguments
- If you see "USER DENIED operation" in the context, NEVER retry that same operation type
- When the user denies an operation, immediately use "finish" with an explanation of what you cannot do and suggest alternatives
- If weather.info provides guidance about weather, immediately finish with that guidance
- If stock.info provides guidance about stock prices, immediately finish with that guidance
- If web.search returns results with information, immediately finish with a comprehensive answer based on those results
- NEVER respond with "No result" when you have web search results - always synthesize the information into a useful answer
- The enhanced web.search tool provides comprehensive results - rarely need multiple searches
- If you've tried 2-3 tools without success, finish with an explanation
- Always provide a meaningful response rather than repeating failed attempts
- RESPECT USER DECISIONS: If user denies permission, accept it gracefully and finish the task

IMPORTANT WEATHER HANDLING:
- For weather questions, call weather.info tool exactly ONCE
- The weather.info tool ALWAYS provides useful guidance about how to get weather information  
- After calling weather.info, immediately use the "finish" function with the guidance provided
- DO NOT call weather.info multiple times - one call is sufficient
- DO NOT call web_search for weather - weather.info provides complete guidance

IMPORTANT STOCK PRICE HANDLING:
- For stock price questions, call stock.info tool exactly ONCE with the stock symbol (e.g., AAPL, GOOGL, TSLA)
- The stock.info tool ALWAYS provides complete guidance about how to get stock price information
- IMMEDIATELY after calling stock.info, use the "finish" function with the guidance provided
- NEVER call stock.info twice - the first call always contains complete information
- If you see guidance like "check financial websites" or "search [symbol] stock price", that IS the complete answer
- DO NOT call web.search for stock prices - stock.info provides everything needed

DECISION EXAMPLES:
- "What is the capital of France?" → FINISH directly with "Paris" (basic knowledge)
- "What is machine learning?" → FINISH directly with explanation (general knowledge)
- "What's the weather today?" → USE weather.info tool (current data needed)
- "What's Apple's stock price?" → USE stock.info tool (current data needed)
- "What is the date today?" → USE shell.exec tool with "date" command (current date/time needed)
- "What time is it?" → USE shell.exec tool with "date" command (current date/time needed)
- "Calculate 15 * 8" → USE math_calc tool (calculation required)
- "Who wrote Romeo and Juliet?" → FINISH directly with "Shakespeare" (historical fact)
- "What are the latest news about AI?" → USE web.search tool (current/recent information)

For math calculations, DO NOT think - immediately use math_calc tool.
Only use tools when you genuinely need current data, calculations, or file operations."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context}
    ]

    try:
        resp = client.chat.completions.create(
            model=llm_config.model,
            messages=messages,
            tools=tool_functions,
            tool_choice="auto",
            temperature=llm_config.temperature,
            max_tokens=llm_config.max_tokens,
            timeout=llm_config.timeout,
        )
        
        message = resp.choices[0].message
        
        # Debug logging
        logger.info(f"LLM Response - Tool calls: {message.tool_calls}")
        logger.info(f"LLM Response - Content: {message.content}")
        
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            function_name = tool_call.function.name
            
            try:
                args = json.loads(tool_call.function.arguments)
                logger.info(f"Function: {function_name}, Arguments: {args}")
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}, Raw arguments: {tool_call.function.arguments}")
                args = {}
            
            if function_name == "think":
                reasoning = args.get("reasoning", "")
                logger.info(f"Think function - reasoning: '{reasoning}'")
                if not reasoning and message.content:
                    # Fallback to message content if reasoning is empty
                    reasoning = message.content
                if not reasoning:
                    reasoning = "Processing the request..."
                return {"type": "think", "reasoning": reasoning}
            elif function_name == "finish":
                output = args.get("output", "")
                if not output and message.content:
                    output = message.content
                return {"type": "finish", "output": output}
            else:
                # Convert back from underscore to dot notation for tool names
                original_name = function_name.replace("_", ".")
                return {"type": "tool", "name": original_name, "args": args}
        else:
            # Fallback if no tool call - treat as thinking
            content = message.content or "Analyzing the problem..."
            return {"type": "think", "reasoning": content}
            
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        return {"type": "finish", "output": f"Error in planning: {str(e)}"}
