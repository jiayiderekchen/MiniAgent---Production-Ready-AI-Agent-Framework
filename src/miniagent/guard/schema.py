from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Literal, Optional, List
import re
import logging

logger = logging.getLogger(__name__)

class Action(BaseModel):
    type: Literal['tool', 'think', 'finish']
    name: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)
    output: Optional[str] = None
    reasoning: Optional[str] = None  # Added missing reasoning field for think actions
    
    @validator('name')
    def validate_tool_name(cls, v, values):
        if values.get('type') == 'tool' and not v:
            raise ValueError("Tool name is required for tool actions")
        return v
    
    @validator('args')
    def validate_args(cls, v, values):
        if values.get('type') == 'tool':
            # Basic validation for tool arguments
            if not isinstance(v, dict):
                raise ValueError("Tool args must be a dictionary")
        return v


class SafetyChecker:
    """Safety checker for agent actions and content"""
    
    def __init__(self):
        self.blocked_patterns = [
            r'rm\s+-rf\s+/',
            r'sudo\s+rm',
            r'mkfs',
            r'dd\s+if=',
            r'chmod\s+777',
            r'passwd\s+',
            r'useradd\s+',
            r'userdel\s+',
            r'mount\s+',
            r'umount\s+',
            r'systemctl\s+',
            r'service\s+',
            r'iptables\s+',
            r'ufw\s+',
        ]
        
        self.suspicious_patterns = [
            r'eval\s*\(',
            r'exec\s*\(',
            r'__import__\s*\(',
            r'subprocess\.call',
            r'os\.system',
            r'base64\.decode',
            r'pickle\.loads',
        ]
        
        self.max_output_length = 10000
        self.max_file_size_mb = 100
    
    def check_command_safety(self, command: str) -> bool:
        """Check if a command is safe to execute"""
        command_lower = command.lower().strip()
        
        # Check for blocked patterns
        for pattern in self.blocked_patterns:
            if re.search(pattern, command_lower):
                logger.warning(f"Blocked command pattern detected: {pattern}")
                return False
        
        # Check for suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.search(pattern, command_lower):
                logger.warning(f"Suspicious command pattern detected: {pattern}")
        
        return True
    
    def check_code_safety(self, code: str) -> bool:
        """Check if code is safe to execute"""
        code_lower = code.lower()
        
        # Check for dangerous imports/functions
        dangerous_imports = [
            'import os', 'import subprocess', 'import sys',
            'from os import', 'from subprocess import',
            '__import__', 'eval(', 'exec('
        ]
        
        for danger in dangerous_imports:
            if danger in code_lower:
                logger.warning(f"Potentially dangerous code detected: {danger}")
        
        return True
    
    def check_output_safety(self, output: Any) -> Any:
        """Check and sanitize output"""
        if isinstance(output, str):
            # Truncate very long outputs
            if len(output) > self.max_output_length:
                logger.warning(f"Output truncated from {len(output)} to {self.max_output_length} characters")
                return output[:self.max_output_length] + "... [truncated]"
        
        return output
    
    def check_file_operation_safety(self, file_path: str, operation: str) -> bool:
        """Check if file operation is safe"""
        import os
        from pathlib import Path
        
        path = Path(file_path).resolve()
        
        # Check for dangerous paths
        dangerous_paths = [
            '/etc/', '/usr/', '/bin/', '/sbin/', '/boot/',
            '/dev/', '/proc/', '/sys/', '/root/'
        ]
        
        for dangerous in dangerous_paths:
            if str(path).startswith(dangerous):
                logger.warning(f"Blocked file operation on dangerous path: {path}")
                return False
        
        # Check file size for write operations
        if operation in ['write', 'create'] and path.exists():
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
                if size_mb > self.max_file_size_mb:
                    logger.warning(f"File too large: {size_mb}MB > {self.max_file_size_mb}MB")
                    return False
            except:
                pass
        
        return True


class ContentFilter:
    """Filter for sensitive content in agent communications"""
    
    def __init__(self):
        self.sensitive_patterns = [
            r'[A-Za-z0-9+/]{40,}={0,2}',  # Base64 encoded data
            r'sk-[a-zA-Z0-9]{48}',  # OpenAI API keys
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub personal access tokens
            r'AIza[0-9A-Za-z-_]{35}',  # Google API keys
            r'AKIA[0-9A-Z]{16}',  # AWS access keys
            r'(?i)password\s*[:=]\s*["\']?[^\s"\']+',  # Passwords
            r'(?i)secret\s*[:=]\s*["\']?[^\s"\']+',  # Secrets
        ]
    
    def filter_sensitive_content(self, text: str) -> str:
        """Remove or mask sensitive content"""
        if not isinstance(text, str):
            return text
        
        filtered_text = text
        
        for pattern in self.sensitive_patterns:
            matches = re.finditer(pattern, filtered_text)
            for match in matches:
                # Replace with masked version
                masked = '*' * len(match.group())
                filtered_text = filtered_text.replace(match.group(), masked)
                logger.warning(f"Masked sensitive content: {pattern}")
        
        return filtered_text


class InputValidator:
    """Validator for user inputs and tool arguments"""
    
    def __init__(self):
        self.max_input_length = 50000
        self.max_args_count = 20
    
    def validate_user_input(self, user_input: str) -> bool:
        """Validate user input for safety"""
        if not isinstance(user_input, str):
            return False
        
        if len(user_input) > self.max_input_length:
            logger.warning(f"User input too long: {len(user_input)} > {self.max_input_length}")
            return False
        
        # Check for injection attempts
        injection_patterns = [
            r'<script.*?>',
            r'javascript:',
            r'data:text/html',
            r'eval\s*\(',
            r'exec\s*\(',
        ]
        
        for pattern in injection_patterns:
            if re.search(pattern, user_input, re.IGNORECASE):
                logger.warning(f"Potential injection detected: {pattern}")
                return False
        
        return True
    
    def validate_tool_args(self, args: Dict[str, Any]) -> bool:
        """Validate tool arguments"""
        if not isinstance(args, dict):
            return False
        
        if len(args) > self.max_args_count:
            logger.warning(f"Too many tool arguments: {len(args)} > {self.max_args_count}")
            return False
        
        # Validate individual arguments
        for key, value in args.items():
            if isinstance(value, str) and len(value) > self.max_input_length:
                logger.warning(f"Tool argument '{key}' too long: {len(value)}")
                return False
        
        return True


# Global instances
safety_checker = SafetyChecker()
content_filter = ContentFilter()
input_validator = InputValidator()


def validate_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize an action"""
    try:
        # Parse with Pydantic for basic validation
        action_obj = Action(**action)
        
        # Additional safety checks
        if action_obj.type == 'tool':
            # Validate tool arguments
            if not input_validator.validate_tool_args(action_obj.args):
                raise ValueError("Tool arguments failed validation")
            
            # Check for dangerous operations
            if action_obj.name in ['shell.exec', 'code.python']:
                if 'command' in action_obj.args:
                    if not safety_checker.check_command_safety(action_obj.args['command']):
                        raise ValueError("Command failed safety check")
                if 'code' in action_obj.args:
                    if not safety_checker.check_code_safety(action_obj.args['code']):
                        raise ValueError("Code failed safety check")
            
            if action_obj.name and 'file.' in action_obj.name:
                if 'path' in action_obj.args:
                    operation = action_obj.name.split('.')[-1]
                    if not safety_checker.check_file_operation_safety(action_obj.args['path'], operation):
                        raise ValueError("File operation failed safety check")
        
        # Filter sensitive content in output
        if action_obj.output:
            action_obj.output = content_filter.filter_sensitive_content(action_obj.output)
        
        return action_obj.dict()
        
    except Exception as e:
        logger.error(f"Action validation failed: {e}")
        raise ValueError(f"Action validation failed: {e}")


def sanitize_output(output: Any) -> Any:
    """Sanitize output from tools or agent"""
    # Apply safety checks
    output = safety_checker.check_output_safety(output)
    
    # Filter sensitive content if it's a string
    if isinstance(output, str):
        output = content_filter.filter_sensitive_content(output)
    elif isinstance(output, dict):
        # Recursively filter dictionary values
        for key, value in output.items():
            if isinstance(value, str):
                output[key] = content_filter.filter_sensitive_content(value)
    
    return output
