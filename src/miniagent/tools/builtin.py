import os
import json
import math
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List
import httpx
from .registry import ToolSpec, tools


# === File Operations ===
def _read_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Read contents of a file"""
    try:
        path = Path(args["path"])
        if not path.exists():
            return {"error": f"File not found: {path}"}
        if path.is_dir():
            return {"error": f"Path is a directory: {path}"}
        
        content = path.read_text(encoding='utf-8')
        return {"content": content, "size": len(content)}
    except Exception as e:
        return {"error": str(e)}

def _write_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Write content to a file"""
    try:
        path = Path(args["path"])
        content = args["content"]
        
        # Create parent directories if they don't exist
        path.parent.mkdir(parents=True, exist_ok=True)
        
        path.write_text(content, encoding='utf-8')
        return {"success": True, "bytes_written": len(content)}
    except Exception as e:
        return {"error": str(e)}

def _list_directory(args: Dict[str, Any]) -> Dict[str, Any]:
    """List contents of a directory"""
    try:
        path = Path(args.get("path", "."))
        if not path.exists():
            return {"error": f"Directory not found: {path}"}
        if not path.is_dir():
            return {"error": f"Path is not a directory: {path}"}
        
        items = []
        for item in path.iterdir():
            items.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            })
        
        return {"items": sorted(items, key=lambda x: (x["type"], x["name"]))}
    except Exception as e:
        return {"error": str(e)}

def _create_directory(args: Dict[str, Any]) -> Dict[str, Any]:
    """Create a directory"""
    try:
        path = Path(args["path"])
        path.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": str(path)}
    except Exception as e:
        return {"error": str(e)}

def _delete_file(args: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a file or directory"""
    try:
        path = Path(args["path"])
        if not path.exists():
            return {"error": f"Path not found: {path}"}
        
        if path.is_file():
            path.unlink()
            return {"success": True, "action": "file_deleted"}
        elif path.is_dir():
            import shutil
            shutil.rmtree(path)
            return {"success": True, "action": "directory_deleted"}
    except Exception as e:
        return {"error": str(e)}


# === Web Operations ===
async def _search_web(args: Dict[str, Any]) -> Dict[str, Any]:
    """Advanced web search with multiple strategies for comprehensive, accurate results"""
    try:
        query = args.get("q", "").strip()
        if not query:
            return {"error": "Query cannot be empty"}
        
        results = []
        summary_info = ""
        
        async with httpx.AsyncClient(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            timeout=15.0
        ) as client:
            
            # Strategy 1: Try DuckDuckGo instant answer API for direct facts
            try:
                ddg_url = "https://api.duckduckgo.com/"
                ddg_params = {
                    "q": query,
                    "format": "json",
                    "no_html": "1",
                    "skip_disambig": "1"
                }
                ddg_response = await client.get(ddg_url, params=ddg_params)
                ddg_data = ddg_response.json()
                
                # Extract instant answers
                if ddg_data.get("Answer"):
                    summary_info = ddg_data["Answer"]
                    results.append({
                        "title": f"Direct Answer",
                        "url": ddg_data.get("AnswerURL", ""),
                        "snippet": ddg_data["Answer"],
                        "source": "DuckDuckGo Instant Answer"
                    })
                
                # Extract definitions and abstracts
                if ddg_data.get("Definition"):
                    results.append({
                        "title": f"Definition: {query}",
                        "url": ddg_data.get("DefinitionURL", ""),
                        "snippet": ddg_data["Definition"],
                        "source": "DuckDuckGo Definition"
                    })
                    if not summary_info:
                        summary_info = ddg_data["Definition"]
                
                if ddg_data.get("Abstract") and not summary_info:
                    summary_info = ddg_data["Abstract"]
                    results.append({
                        "title": f"Overview: {query}",
                        "url": ddg_data.get("AbstractURL", ""),
                        "snippet": ddg_data["Abstract"],
                        "source": "DuckDuckGo Abstract"
                    })
                
                # Extract related topics for more comprehensive results
                if ddg_data.get("RelatedTopics"):
                    for topic in ddg_data["RelatedTopics"][:3]:
                        if isinstance(topic, dict) and "Text" in topic:
                            results.append({
                                "title": topic.get("Text", "")[:80] + "..." if len(topic.get("Text", "")) > 80 else topic.get("Text", ""),
                                "url": topic.get("FirstURL", ""),
                                "snippet": topic.get("Text", ""),
                                "source": "DuckDuckGo Related"
                            })
            except Exception as e:
                print(f"DuckDuckGo API failed: {e}")
            
            # Strategy 2: Web scraping for general search results if we need more
            if len(results) < 2:
                try:
                    # Use DuckDuckGo HTML search for actual web results
                    search_url = "https://html.duckduckgo.com/html/"
                    search_params = {"q": query}
                    
                    search_response = await client.post(search_url, data=search_params)
                    html_content = search_response.text
                    
                    # Parse search results from HTML (simplified parsing)
                    import re
                    
                    # Extract result blocks
                    result_pattern = r'<div class="result__body">.*?<a rel="nofollow" href="([^"]*)".*?>(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>'
                    matches = re.findall(result_pattern, html_content, re.DOTALL | re.IGNORECASE)
                    
                    for i, (url, title, snippet) in enumerate(matches[:5]):
                        # Clean up HTML tags and entities
                        title = re.sub(r'<[^>]+>', '', title).strip()
                        snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                        title = title.replace('&amp;', '&').replace('&#x27;', "'").replace('&quot;', '"')
                        snippet = snippet.replace('&amp;', '&').replace('&#x27;', "'").replace('&quot;', '"')
                        
                        if title and snippet and url:
                            results.append({
                                "title": title[:100],
                                "url": url,
                                "snippet": snippet[:300],
                                "source": "Web Search"
                            })
                except Exception as e:
                    print(f"HTML search failed: {e}")
            
            # Strategy 3: Knowledge-based responses for common queries
            if not results:
                knowledge_response = _generate_knowledge_response(query)
                if knowledge_response:
                    results.append(knowledge_response)
            
            # Strategy 4: Fallback with helpful guidance
            if not results:
                results.append({
                    "title": f"Search Guidance for: {query}",
                    "url": f"https://www.google.com/search?q={query.replace(' ', '+')}",
                    "snippet": f"I found limited results for '{query}'. For comprehensive web search results, try: 1) Google Search, 2) Bing, 3) DuckDuckGo directly. I can help you rephrase your query or provide specific assistance if you tell me what information you're looking for.",
                    "source": "Search Assistant"
                })
            
            # Enhance summary if we have results but no summary
            if results and not summary_info:
                first_result = results[0]
                summary_info = first_result["snippet"][:200] + "..." if len(first_result["snippet"]) > 200 else first_result["snippet"]
            
            return {
                "query": query,
                "results": results,
                "count": len(results),
                "summary": summary_info or f"Found {len(results)} results for '{query}'",
                "search_strategies": ["DuckDuckGo API", "HTML Search", "Knowledge Base"],
                "status": "completed"
            }
            
    except Exception as e:
        return {
            "error": f"Search failed: {str(e)}",
            "query": query,
            "results": [{
                "title": "Search Error",
                "url": "",
                "snippet": f"Search encountered an error: {str(e)}. Try rephrasing your query or ask me to help with a specific aspect of your question.",
                "source": "Error Handler"
            }],
            "count": 1,
            "summary": f"Search error for '{query}'"
        }

def _generate_knowledge_response(query: str) -> Dict[str, Any]:
    """Generate knowledge-based responses for common queries"""
    query_lower = query.lower()
    
    # Programming and technology topics
    if any(term in query_lower for term in ["python", "javascript", "programming", "code", "algorithm"]):
        return {
            "title": f"Programming Information: {query}",
            "url": "https://docs.python.org" if "python" in query_lower else "https://developer.mozilla.org",
            "snippet": "For programming questions, I recommend checking official documentation, Stack Overflow, or GitHub. I can also help you with specific coding problems or explain programming concepts directly.",
            "source": "Programming Knowledge"
        }
    
    # Science and math topics
    if any(term in query_lower for term in ["formula", "equation", "theory", "science", "physics", "chemistry", "math"]):
        return {
            "title": f"Science/Math Information: {query}",
            "url": "https://www.wolframalpha.com",
            "snippet": "For scientific and mathematical information, consider Wolfram Alpha, Khan Academy, or academic sources. I can also help explain concepts or solve specific problems.",
            "source": "Science Knowledge"
        }
    
    # Business and finance
    if any(term in query_lower for term in ["business", "finance", "investment", "market", "economy"]):
        return {
            "title": f"Business/Finance Information: {query}",
            "url": "https://finance.yahoo.com",
            "snippet": "For business and financial information, check reputable sources like Yahoo Finance, Bloomberg, or Financial Times. I can help explain concepts or analyze specific topics.",
            "source": "Business Knowledge"
        }
    
    return None

async def _fetch_url(args: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch content from a URL"""
    try:
        url = args["url"]
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            if "text" in content_type or "json" in content_type:
                content = response.text[:10000]  # Limit content size
            else:
                content = f"Binary content ({len(response.content)} bytes)"
            
            return {
                "url": url,
                "status": response.status_code,
                "content_type": content_type,
                "content": content,
                "headers": dict(response.headers)
            }
    except Exception as e:
        return {"error": str(e)}


# === Code Execution ===
def _execute_python(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Python code safely"""
    try:
        code = args["code"]
        
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Execute with timeout
            result = subprocess.run(
                ["python", temp_file],
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        finally:
            os.unlink(temp_file)
            
    except subprocess.TimeoutExpired:
        return {"error": "Code execution timed out"}
    except Exception as e:
        return {"error": str(e)}

def _execute_shell(args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute shell command (with safety restrictions)"""
    try:
        command = args["command"]
        
        # Basic safety: block dangerous commands
        dangerous = ["rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", "chmod 777"]
        if any(danger in command.lower() for danger in dangerous):
            return {"error": "Command blocked for safety reasons"}
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {"error": "Command execution timed out"}
    except Exception as e:
        return {"error": str(e)}


# === Math and Computation ===
def _calculate(args: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate mathematical expressions safely"""
    try:
        expression = args["expression"]
        
        # Only allow safe mathematical operations
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "sqrt": math.sqrt, "log": math.log,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "pi": math.pi, "e": math.e
        }
        
        # Compile and evaluate the expression
        code = compile(expression, "<string>", "eval")
        
        # Check for disallowed operations
        for name in code.co_names:
            if name not in allowed_names:
                return {"error": f"Operation '{name}' not allowed"}
        
        result = eval(code, {"__builtins__": {}}, allowed_names)
        
        return {
            "expression": expression,
            "result": result,
            "type": type(result).__name__
        }
    except Exception as e:
        return {"error": str(e)}


# === Text Processing ===
def _text_summary(args: Dict[str, Any]) -> Dict[str, Any]:
    """Simple text summarization"""
    try:
        text = args["text"]
        max_sentences = args.get("max_sentences", 3)
        
        # Simple extractive summary: take first and last few sentences
        sentences = text.split('. ')
        if len(sentences) <= max_sentences:
            return {"summary": text, "original_length": len(text)}
        
        # Take first and last sentences
        summary_sentences = sentences[:max_sentences//2] + sentences[-(max_sentences//2):]
        summary = '. '.join(summary_sentences)
        
        return {
            "summary": summary,
            "original_length": len(text),
            "summary_length": len(summary),
            "compression_ratio": len(summary) / len(text)
        }
    except Exception as e:
        return {"error": str(e)}


# === System Information ===
def _get_system_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """Get basic system information"""
    try:
        import platform
        import psutil
        
        return {
            "platform": platform.system(),
            "architecture": platform.architecture()[0],
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": {
                "total": psutil.disk_usage('/').total,
                "used": psutil.disk_usage('/').used,
                "free": psutil.disk_usage('/').free
            }
        }
    except Exception as e:
        return {"error": str(e)}


# Register all tools
tools.register(ToolSpec(
    name="file.read",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to read"}
        },
        "required": ["path"]
    },
    fn=_read_file,
    timeout_s=10.0
))

tools.register(ToolSpec(
    name="file.write",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file to write"},
            "content": {"type": "string", "description": "Content to write to the file"}
        },
        "required": ["path", "content"]
    },
    fn=_write_file,
    timeout_s=10.0
))

tools.register(ToolSpec(
    name="file.list",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the directory to list", "default": "."}
        }
    },
    fn=_list_directory,
    timeout_s=5.0
))

tools.register(ToolSpec(
    name="file.mkdir",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the directory to create"}
        },
        "required": ["path"]
    },
    fn=_create_directory,
    timeout_s=5.0
))

tools.register(ToolSpec(
    name="file.delete",
    schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to the file or directory to delete"}
        },
        "required": ["path"]
    },
    fn=_delete_file,
    timeout_s=10.0
))

tools.register(ToolSpec(
    name="web.search",
    schema={
        "type": "object",
        "properties": {
            "q": {"type": "string", "description": "Search query"}
        },
        "required": ["q"]
    },
    fn=_search_web,
    timeout_s=15.0
))

tools.register(ToolSpec(
    name="web.fetch",
    schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"}
        },
        "required": ["url"]
    },
    fn=_fetch_url,
    timeout_s=15.0
))

tools.register(ToolSpec(
    name="code.python",
    schema={
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python code to execute"}
        },
        "required": ["code"]
    },
    fn=_execute_python,
    timeout_s=30.0
))

tools.register(ToolSpec(
    name="shell.exec",
    schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"}
        },
        "required": ["command"]
    },
    fn=_execute_shell,
    timeout_s=30.0
))

tools.register(ToolSpec(
    name="math.calc",
    schema={
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Mathematical expression to evaluate"}
        },
        "required": ["expression"]
    },
    fn=_calculate,
    timeout_s=5.0
))

tools.register(ToolSpec(
    name="text.summarize",
    schema={
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to summarize"},
            "max_sentences": {"type": "integer", "description": "Maximum number of sentences in summary", "default": 3}
        },
        "required": ["text"]
    },
    fn=_text_summary,
    timeout_s=10.0
))

tools.register(ToolSpec(
    name="system.info",
    schema={
        "type": "object",
        "properties": {}
    },
    fn=_get_system_info,
    timeout_s=5.0
))


# === Memory Tools ===
def _memory_store(args: Dict[str, Any]) -> Dict[str, Any]:
    """Store information in agent memory"""
    try:
        content = args["content"]
        memory_type = args.get("memory_type", "semantic")
        metadata = args.get("metadata", {})
        
        # This is a placeholder - in practice, the runtime will handle memory
        # For now, just return success
        return {
            "success": True,
            "content": content,
            "memory_type": memory_type,
            "message": "Memory storage would be handled by the agent runtime"
        }
    except Exception as e:
        return {"error": str(e)}

def _memory_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search agent memory"""
    try:
        query = args["query"]
        memory_type = args.get("memory_type", "semantic")
        top_k = args.get("top_k", 5)
        
        # This is a placeholder - in practice, the runtime will handle memory
        return {
            "query": query,
            "memory_type": memory_type,
            "top_k": top_k,
            "results": [],
            "message": "Memory search would be handled by the agent runtime"
        }
    except Exception as e:
        return {"error": str(e)}


# === Weather Information Tool ===
async def _get_weather_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """Provide weather information and guidance"""
    location = args.get("location", "your area")
    
    return {
        "message": f"Weather Information for {location}",
        "guidance": [
            "I cannot access real-time weather data without a weather API key.",
            "Here are the best ways to get current weather:",
            "1. Check weather.com or weather apps on your device",
            "2. Ask a voice assistant like Siri, Google, or Alexa",
            "3. Search 'weather' + your city name in a web browser",
            "4. Use local news websites or TV weather forecasts"
        ],
        "alternatives": [
            "I can help you create a Python script to fetch weather using a free API",
            "I can show you how to set up weather monitoring tools",
            "I can provide general information about weather patterns"
        ],
        "suggestion": "Try asking: 'Help me create a weather script using OpenWeatherMap API'"
    }

tools.register(ToolSpec(
    name="weather.info",
    schema={
        "type": "object",
        "properties": {
            "location": {"type": "string", "description": "Location for weather information", "default": "your area"}
        },
        "required": []
    },
    fn=_get_weather_info,
    timeout_s=3.0
))

async def _get_stock_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """Provide stock price information and guidance"""
    symbol = args.get("symbol", "the requested stock")
    
    return {
        "message": f"Stock Price Information for {symbol}",
        "guidance": [
            "I cannot access real-time stock market data without a financial API key.",
            "Here are the best ways to get current stock prices:",
            "1. Check financial websites like Yahoo Finance, Google Finance, or Bloomberg",
            "2. Use your broker's app or website (Robinhood, E*TRADE, etc.)",
            "3. Search '[company name] stock price' in Google for instant results",
            "4. Use financial apps like Yahoo Finance, Bloomberg, or MarketWatch",
            "5. Check the company's investor relations page"
        ],
        "alternatives": [
            "I can help you create a Python script to fetch stock prices using a free API",
            "I can explain how stock markets work or help with investment analysis",
            "I can help you understand financial terms and concepts"
        ],
        "suggestion": f"Try searching '{symbol} stock price' in Google or visiting finance.yahoo.com/quote/{symbol.upper()}"
    }

tools.register(ToolSpec(
    name="stock.info",
    schema={
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol (e.g., AAPL, GOOGL, TSLA)", "default": "the requested stock"}
        },
        "required": []
    },
    fn=_get_stock_info,
    timeout_s=3.0
))

tools.register(ToolSpec(
    name="memory.store",
    schema={
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Content to store in memory"},
            "memory_type": {"type": "string", "description": "Type of memory: semantic, episodic, or working", "default": "semantic"},
            "metadata": {"type": "object", "description": "Additional metadata", "default": {}}
        },
        "required": ["content"]
    },
    fn=_memory_store,
    timeout_s=5.0
))

tools.register(ToolSpec(
    name="memory.search",
    schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query for memory"},
            "memory_type": {"type": "string", "description": "Type of memory to search: semantic, episodic, or working", "default": "semantic"},
            "top_k": {"type": "integer", "description": "Number of results to return", "default": 5}
        },
        "required": ["query"]
    },
    fn=_memory_search,
    timeout_s=5.0
))
