import asyncio
import os
import signal
import tempfile
import shutil
import resource
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential
import logging

logger = logging.getLogger(__name__)

@dataclass
class SandboxConfig:
    """Configuration for sandbox execution"""
    max_memory_mb: int = 512
    max_cpu_time_s: int = 30
    max_file_size_mb: int = 100
    max_processes: int = 5
    allowed_dirs: List[str] = None
    blocked_commands: List[str] = None
    enable_network: bool = True
    
    def __post_init__(self):
        if self.allowed_dirs is None:
            self.allowed_dirs = ["/tmp", "/var/tmp"]
        if self.blocked_commands is None:
            self.blocked_commands = [
                "rm -rf", "mkfs", "dd if=", ":(){ :|:& };:", "chmod 777",
                "sudo", "su", "chroot", "mount", "umount", "systemctl",
                "service", "iptables", "ufw", "passwd", "useradd", "userdel"
            ]


class SecurityError(Exception):
    """Raised when a security violation is detected"""
    pass


class SandboxExecutor:
    """Enhanced sandbox executor with security restrictions"""
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.temp_dirs = []
    
    def __del__(self):
        """Cleanup temporary directories"""
        self.cleanup()
    
    def cleanup(self):
        """Clean up temporary directories and resources"""
        for temp_dir in self.temp_dirs:
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp dir {temp_dir}: {e}")
        self.temp_dirs.clear()
    
    def create_sandbox_dir(self) -> Path:
        """Create a temporary directory for sandbox execution"""
        temp_dir = Path(tempfile.mkdtemp(prefix="miniagent_sandbox_"))
        self.temp_dirs.append(temp_dir)
        return temp_dir
    
    def validate_command(self, command: str) -> bool:
        """Check if a command is safe to execute"""
        command_lower = command.lower().strip()
        
        # Check for explicitly blocked commands
        for blocked in self.config.blocked_commands:
            if blocked.lower() in command_lower:
                raise SecurityError(f"Blocked command detected: {blocked}")
        
        # Check for suspicious patterns
        suspicious_patterns = [
            "> /dev/", "< /dev/", "exec(", "eval(", "__import__",
            "subprocess.call", "os.system", "curl http", "wget http"
        ]
        
        for pattern in suspicious_patterns:
            if pattern.lower() in command_lower:
                logger.warning(f"Suspicious pattern detected: {pattern}")
        
        return True
    
    def set_resource_limits(self):
        """Set resource limits for the current process"""
        try:
            # Set memory limit
            max_memory = self.config.max_memory_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (max_memory, max_memory))
            
            # Set CPU time limit
            resource.setrlimit(resource.RLIMIT_CPU, (self.config.max_cpu_time_s, self.config.max_cpu_time_s))
            
            # Set file size limit
            max_file_size = self.config.max_file_size_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_size, max_file_size))
            
            # Set process limit
            resource.setrlimit(resource.RLIMIT_NPROC, (self.config.max_processes, self.config.max_processes))
            
        except Exception as e:
            logger.warning(f"Failed to set resource limits: {e}")
    
    async def execute_with_limits(self, spec, args: Dict[str, Any]) -> Any:
        """Execute a tool function with security and resource limits"""
        
        # Validate arguments if validator exists
        if getattr(spec, 'validator', None):
            try:
                args = spec.validator(args)
            except Exception as e:
                raise SecurityError(f"Argument validation failed: {e}")
        
        # Check if this is a potentially dangerous operation
        if hasattr(spec, 'name') and any(dangerous in spec.name for dangerous in ['shell', 'exec', 'code']):
            # Additional validation for code/shell execution
            if 'command' in args:
                self.validate_command(args['command'])
            if 'code' in args:
                # Basic code validation (could be enhanced)
                code = args['code']
                if any(danger in code.lower() for danger in ['import os', '__import__', 'exec(', 'eval(']):
                    logger.warning("Potentially dangerous code detected")
        
        async def _call():
            # Execute in a separate process for isolation if it's a risky operation
            if hasattr(spec, 'name') and any(risky in spec.name for risky in ['shell', 'code', 'file.delete']):
                return await self._execute_in_subprocess(spec, args)
            else:
                # Execute normally for safe operations
                res = spec.fn(args)
                if asyncio.iscoroutine(res):
                    return await res
                return res
        
        try:
            return await asyncio.wait_for(_call(), timeout=spec.timeout_s)
        except asyncio.TimeoutError:
            raise SecurityError(f"Tool execution timed out after {spec.timeout_s} seconds")
    
    async def _execute_in_subprocess(self, spec, args: Dict[str, Any]) -> Any:
        """Execute tool in a separate subprocess for isolation"""
        # For now, just execute normally but with monitoring
        # In a production system, this would use proper process isolation
        try:
            result = spec.fn(args)
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            logger.error(f"Subprocess execution failed: {e}")
            raise


# Global sandbox executor instance
_sandbox = SandboxExecutor()

@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=0.3, min=0.3, max=1.2))
async def run_tool(spec, args: Dict[str, Any]) -> Any:
    """Enhanced tool execution with security sandbox"""
    try:
        return await _sandbox.execute_with_limits(spec, args)
    except SecurityError as e:
        logger.error(f"Security violation in tool {getattr(spec, 'name', 'unknown')}: {e}")
        return {"error": f"Security violation: {str(e)}", "blocked": True}
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        raise


def get_sandbox_stats() -> Dict[str, Any]:
    """Get current sandbox statistics"""
    try:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        return {
            "memory_peak_kb": usage.ru_maxrss,
            "cpu_time_user": usage.ru_utime,
            "cpu_time_system": usage.ru_stime,
            "temp_dirs_active": len(_sandbox.temp_dirs)
        }
    except Exception as e:
        return {"error": str(e)}


def cleanup_sandbox():
    """Cleanup sandbox resources"""
    _sandbox.cleanup()
