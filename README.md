# MiniAgent - Production-Ready AI Agent Framework

A sophisticated, enterprise-grade AI agent framework designed for building intelligent agents with advanced reasoning, comprehensive tooling, and robust safety measures.

## 🌟 Overview

MiniAgent is a complete AI agent framework that transforms the traditional approach to building intelligent systems. Unlike simple chatbots or basic automation tools, MiniAgent provides a comprehensive infrastructure for creating agents that can:

- **Think and Plan**: Multi-step reasoning with OpenAI function-calling integration
- **Remember and Learn**: Advanced memory systems with vector storage and episodic recall
- **Execute Safely**: Sandbox execution with comprehensive security guardrails
- **Evaluate Performance**: Built-in evaluation framework for continuous improvement
- **Scale and Configure**: Flexible configuration management for production deployments

## 🚀 Key Features

### 🧠 Advanced AI Planning System
- **OpenAI Function Calling Integration**: Leverages GPT-4's native function calling for structured reasoning
- **Multi-Step Planning**: Breaks down complex goals into executable sub-tasks
- **Context-Aware Decisions**: Uses memory and current state for intelligent planning
- **Error Recovery**: Automatic fallback and retry mechanisms
- **Complexity Routing**: Intelligent model selection based on task complexity (DeepSeek integration)

### 🛠️ Comprehensive Tool Ecosystem

#### File Operations (5 tools)
- `file.read` - Read file contents with encoding detection
- `file.write` - Write files with automatic directory creation
- `file.list` - Directory listing with metadata
- `file.mkdir` - Recursive directory creation
- `file.delete` - Safe file/directory deletion

#### Web & Network (2 tools)
- `web.search` - Real-time DuckDuckGo search with result ranking
- `web.fetch` - URL content fetching with content type detection

#### Code Execution (2 tools)
- `code.python` - Sandboxed Python execution with output capture
- `shell.exec` - Secure shell command execution with validation

#### Mathematics & Analysis (3 tools)
- `math.calc` - Safe mathematical expression evaluation
- `text.summarize` - Advanced text summarization
- `system.info` - System resource monitoring

#### Memory Management (2 tools)
- `memory.store` - Explicit knowledge storage
- `memory.search` - Semantic memory retrieval

### 🧠 Advanced Memory Architecture

#### Vector-Based Semantic Memory
- **ChromaDB Integration**: Production-grade vector database
- **Sentence Transformers**: High-quality embeddings (all-MiniLM-L6-v2)
- **Similarity Search**: Intelligent retrieval of relevant information
- **Persistent Storage**: Automatic persistence across sessions

#### Episodic Memory System
- **Sequential Experience Storage**: Time-ordered memory of agent actions
- **Context Retrieval**: Historical context for decision-making
- **Session Persistence**: Continuous learning across interactions

#### Working Memory Management
- **LRU Eviction**: Intelligent short-term memory management
- **Fast Access**: Optimized for current task context
- **Resource Efficient**: Configurable memory limits

### 🛡️ Enterprise-Grade Security

#### Multi-Layer Safety Framework
- **Command Validation**: Real-time dangerous command detection
- **Code Safety Analysis**: Static analysis for Python code execution
- **Content Filtering**: Automatic removal of sensitive data (API keys, passwords)
- **Input Validation**: Comprehensive input sanitization and validation

#### Sandbox Execution Environment
- **Resource Limits**: Memory (512MB), CPU (30s), file size (100MB) constraints
- **Process Isolation**: Secure execution of untrusted code
- **Network Controls**: Configurable network access policies
- **Path Validation**: Prevention of unauthorized file system access

#### Security Configurations
```json
{
  "safety": {
    "enable_content_filtering": true,
    "enable_command_validation": true,
    "enable_file_path_validation": true,
    "max_output_length": 10000,
    "blocked_file_paths": ["/etc/", "/usr/", "/bin/", "/sbin/"]
  }
}
```

### 📊 Comprehensive Evaluation Framework

#### Built-in Evaluation Suites
- **Basic Suite**: Math, file operations, reasoning, web search
- **Advanced Suite**: Problem solving, code generation, multi-step tasks, research

#### Custom Evaluation Capabilities
```python
from miniagent.eval.harness import EvalSuite, EvalTask

suite = EvalSuite("custom_eval", "Custom evaluation suite")
suite.add_task(EvalTask(
    id="complex_reasoning",
    description="Test multi-step reasoning",
    goal="Analyze data and provide insights",
    success_criteria=lambda result: "analysis" in str(result).lower(),
    max_steps=8
))
```

### ⚙️ Flexible Configuration System

#### Multi-Source Configuration
- **JSON Files**: Structured configuration files
- **Environment Variables**: Runtime configuration override
- **Programmatic**: Dynamic configuration in code
- **CLI Arguments**: Command-line configuration options

#### LLM Provider Support
- **DeepSeek**: Primary provider with complexity routing
- **OpenAI**: Full GPT-4 integration
- **Extensible**: Easy integration of new providers

## 🏗️ Installation & Setup

### Requirements
- Python 3.9+
- 512MB RAM minimum (2GB recommended)
- Internet connection for LLM APIs and web search

### Installation
```bash
# Clone the repository
git clone <repository-url>
cd miniagent-starter

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .

# Verify installation
miniagent --help
```

### Quick Configuration
```bash
# Generate default configuration
miniagent config create

# Set API key (choose one)
export DEEPSEEK_API_KEY="sk-your-deepseek-key"
export OPENAI_API_KEY="sk-your-openai-key"

# Test installation
miniagent run "Calculate 15 * 23 + 7"
```

## 🚀 Usage Examples

### Basic Usage
```bash
# Simple calculations
miniagent run "What is the area of a circle with radius 10?"

# File operations
miniagent run "Create a file with today's date and current time"

# Web research
miniagent run "Search for the latest developments in AI safety"

# Code generation and execution
miniagent run "Write and run a Python script to generate the first 10 Fibonacci numbers"
```

### Advanced Multi-Step Tasks
```bash
# Complex data analysis
miniagent run "Create sample sales data, analyze trends, and generate a summary report" --steps 12 --verbose

# Research and documentation
miniagent run "Research quantum computing basics and create a beginner's guide" --steps 15

# System analysis
miniagent run "Analyze system performance and create optimization recommendations" --thinking
```

### CLI Options
```bash
# Verbose output with step-by-step details
miniagent run "Complex task" --verbose

# Show real-time thinking process
miniagent run "Problem to solve" --thinking

# Quiet mode (results only)
miniagent run "Quick task" --quiet

# JSON output for programmatic use
miniagent run "Data task" --json

# Custom step limit
miniagent run "Long task" --steps 20
```

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI**: Function calling and GPT-4 integration
- **ChromaDB**: Vector database infrastructure
- **Sentence Transformers**: High-quality embeddings
- **Pydantic**: Data validation and serialization
- **DuckDuckGo**: Privacy-focused web search

---

**MiniAgent** - From concept to production, the complete AI agent framework for building intelligent systems that think, remember, and execute safely.

