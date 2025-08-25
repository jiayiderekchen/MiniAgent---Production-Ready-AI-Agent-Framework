import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class OpenAIConfig:
    """OpenAI API configuration"""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    max_tokens: int = 4000
    temperature: float = 0.1
    timeout: float = 30.0
    
    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.getenv("OPENAI_API_KEY", "")

@dataclass
class DeepSeekConfig:
    """DeepSeek API configuration"""
    api_key: str = ""
    model: str = "deepseek-chat"
    reasoner_model: str = "deepseek-reasoner"
    base_url: str = "https://api.deepseek.com/v1"
    max_tokens: int = 4000
    temperature: float = 0.1
    timeout: float = 30.0
    enable_complexity_routing: bool = True
    
    def __post_init__(self):
        if not self.api_key:
            # Try environment variable first, then fallback to hardcoded key
            self.api_key = os.getenv("DEEPSEEK_API_KEY")
    
    def get_model_for_complexity(self, is_complex: bool) -> str:
        """Get the appropriate model based on complexity."""
        if self.enable_complexity_routing and is_complex:
            return self.reasoner_model
        return self.model

@dataclass
class LLMConfig:
    """General LLM provider configuration"""
    provider: str = "deepseek"  # Default to DeepSeek
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)
    deepseek: DeepSeekConfig = field(default_factory=DeepSeekConfig)
    
    def get_active_config(self):
        """Get the configuration for the active provider"""
        if self.provider == "openai":
            return self.openai
        elif self.provider == "deepseek":
            return self.deepseek
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
    
    def get_active_api_key(self):
        """Get the API key for the active provider"""
        config = self.get_active_config()
        return config.api_key

@dataclass
class SandboxConfig:
    """Sandbox execution configuration"""
    max_memory_mb: int = 512
    max_cpu_time_s: int = 30
    max_file_size_mb: int = 100
    max_processes: int = 5
    enable_network: bool = True
    temp_dir: str = "/tmp"

@dataclass
class MemoryConfig:
    """Memory system configuration"""
    persist_dir: str = "./agent_memory"
    vector_store_collection: str = "semantic_memory"
    max_episodic_memories: int = 1000
    max_working_memory_items: int = 20
    embedding_model: str = "all-MiniLM-L6-v2"

@dataclass
class SafetyConfig:
    """Safety and security configuration"""
    enable_content_filtering: bool = True
    enable_command_validation: bool = True
    enable_file_path_validation: bool = True
    max_output_length: int = 10000
    max_input_length: int = 50000
    blocked_file_paths: list = field(default_factory=lambda: [
        "/etc/", "/usr/", "/bin/", "/sbin/", "/boot/",
        "/dev/", "/proc/", "/sys/", "/root/"
    ])

@dataclass
class ConsentConfig:
    """User consent configuration"""
    enable_interactive_consent: bool = False
    auto_approve_safe_operations: bool = True
    auto_approve_read_operations: bool = True
    require_consent_for_write: bool = True
    require_consent_for_delete: bool = True
    require_consent_for_execute: bool = True
    safe_directories: list = field(default_factory=lambda: [
        "./", "./temp/", "./workspace/", "./output/", "./artifacts/"
    ])

@dataclass
class RuntimeConfig:
    """Runtime execution configuration"""
    max_steps: int = 10
    default_timeout: float = 60.0
    enable_logging: bool = True
    log_level: str = "INFO"
    enable_memory_persistence: bool = True
    enable_guardrails: bool = True

@dataclass
class AgentConfig:
    """Main agent configuration"""
    llm: LLMConfig = field(default_factory=LLMConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    consent: ConsentConfig = field(default_factory=ConsentConfig)
    
    # Backward compatibility
    @property
    def openai(self):
        """Backward compatibility property"""
        return self.llm.openai
    
    @classmethod
    def from_file(cls, config_path: str) -> 'AgentConfig':
        """Load configuration from JSON file"""
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file {config_path} not found, using defaults")
            return cls()
        
        try:
            with open(config_file, 'r') as f:
                config_data = json.load(f)
            
            # Create config objects from nested dictionaries
            llm_data = config_data.get('llm', {})
            
            # Handle backward compatibility for old 'openai' key
            if 'openai' in config_data and 'llm' not in config_data:
                llm_data = {
                    'provider': 'openai',
                    'openai': config_data['openai'],
                    'deepseek': {}
                }
            
            # Create LLM config
            openai_config = OpenAIConfig(**llm_data.get('openai', {}))
            deepseek_config = DeepSeekConfig(**llm_data.get('deepseek', {}))
            llm_config = LLMConfig(
                provider=llm_data.get('provider', 'deepseek'),
                openai=openai_config,
                deepseek=deepseek_config
            )
            
            sandbox_config = SandboxConfig(**config_data.get('sandbox', {}))
            memory_config = MemoryConfig(**config_data.get('memory', {}))
            safety_config = SafetyConfig(**config_data.get('safety', {}))
            runtime_config = RuntimeConfig(**config_data.get('runtime', {}))
            consent_config = ConsentConfig(**config_data.get('consent', {}))
            
            return cls(
                llm=llm_config,
                sandbox=sandbox_config,
                memory=memory_config,
                safety=safety_config,
                runtime=runtime_config,
                consent=consent_config
            )
            
        except Exception as e:
            logger.error(f"Failed to load config from {config_path}: {e}")
            return cls()
    
    def to_file(self, config_path: str):
        """Save configuration to JSON file"""
        config_data = {
            'llm': {
                'provider': self.llm.provider,
                'openai': self.llm.openai.__dict__,
                'deepseek': self.llm.deepseek.__dict__
            },
            'sandbox': self.sandbox.__dict__,
            'memory': self.memory.__dict__,
            'safety': self.safety.__dict__,
            'runtime': self.runtime.__dict__,
            'consent': self.consent.__dict__
        }
        
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Saved configuration to {config_path}")
    
    def setup_logging(self):
        """Setup logging based on configuration"""
        if self.runtime.enable_logging:
            level = getattr(logging, self.runtime.log_level.upper(), logging.INFO)
            logging.basicConfig(
                level=level,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.StreamHandler(),
                    logging.FileHandler('agent.log')
                ]
            )


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """Load agent configuration"""
    if config_path is None:
        # Try common config locations
        possible_paths = [
            "./agent_config.json",
            "./config/agent.json",
            os.path.expanduser("~/.miniagent/config.json"),
            "/etc/miniagent/config.json"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                config_path = path
                break
    
    if config_path and Path(config_path).exists():
        return AgentConfig.from_file(config_path)
    else:
        logger.info("No config file found, using default configuration")
        return AgentConfig()


def create_default_config(output_path: str = "./agent_config.json"):
    """Create a default configuration file"""
    config = AgentConfig()
    config.to_file(output_path)
    print(f"Created default configuration at {output_path}")
    print("Please edit the configuration file to customize your agent settings.")


# Global configuration instance
_global_config: Optional[AgentConfig] = None

def get_config() -> AgentConfig:
    """Get the global configuration instance"""
    global _global_config
    if _global_config is None:
        _global_config = load_config()
        _global_config.setup_logging()
    return _global_config

def set_config(config: AgentConfig):
    """Set the global configuration instance"""
    global _global_config
    _global_config = config
    config.setup_logging()


if __name__ == "__main__":
    # Create default config when run as script
    create_default_config()
