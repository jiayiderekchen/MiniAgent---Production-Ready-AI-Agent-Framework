"""
Interactive Consent System for MiniAgent

This module provides user consent mechanisms for potentially destructive operations,
particularly file operations, giving users explicit control over agent actions.
"""

import logging
from typing import Dict, Any, Optional, Set, List
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


class ConsentDecision(Enum):
    """Possible consent decisions"""
    ALLOW = "allow"
    DENY = "deny"
    ALLOW_ALL = "allow_all"
    DENY_ALL = "deny_all"
    ALLOW_SESSION = "allow_session"


@dataclass
class ConsentRequest:
    """Represents a consent request for an operation"""
    operation: str  # e.g., "file.write", "file.delete"
    target: str     # e.g., file path
    details: Dict[str, Any]  # Additional operation details
    risk_level: str = "medium"  # low, medium, high
    
    def __str__(self):
        return f"{self.operation} on {self.target}"


class ConsentManager:
    """Manages user consent for agent operations"""
    
    def __init__(self, interactive: bool = True, auto_approve_safe: bool = True):
        self.interactive = interactive
        self.auto_approve_safe = auto_approve_safe
        self.session_approvals: Set[str] = set()
        self.session_denials: Set[str] = set()
        self.global_allow_all = False
        self.global_deny_all = False
        
        # Safe operations that can be auto-approved
        self.safe_operations = {
            "file.read", "file.list", "web.search", "web.fetch", 
            "math.calc", "text.summarize", "system.info", 
            "memory.search"
        }
        
        # High-risk operations that always require explicit consent
        self.high_risk_operations = {
            "file.delete", "code.python"
        }
        
        # Safe shell commands that don't require consent
        self.safe_shell_commands = {
            "date", "pwd", "whoami", "id", "uname", "hostname", 
            "uptime", "df", "free", "ps", "top", "ls", "cat", 
            "head", "tail", "wc", "grep", "find", "which", "echo"
        }
        
        # Directory patterns that are considered safe for operations
        self.safe_directories = {
            "./", "./temp/", "./workspace/", "./output/", "./artifacts/"
        }
    
    def is_safe_directory(self, path: str) -> bool:
        """Check if a directory is considered safe for operations"""
        try:
            resolved_path = Path(path).resolve()
            path_str = str(resolved_path)
            
            # Check if path is in safe directories
            for safe_dir in self.safe_directories:
                safe_resolved = str(Path(safe_dir).resolve())
                if path_str.startswith(safe_resolved):
                    return True
            
            # Check if it's in current working directory
            cwd = str(Path.cwd())
            if path_str.startswith(cwd):
                return True
                
            return False
        except Exception:
            return False
    
    def assess_risk_level(self, request: ConsentRequest) -> str:
        """Assess the risk level of an operation"""
        if request.operation in self.high_risk_operations:
            return "high"
        
        # Special handling for shell commands
        if request.operation == "shell.exec":
            return self._assess_shell_command_risk(request)
        
        if request.operation in self.safe_operations:
            if request.operation.startswith("file.") and request.target:
                if self.is_safe_directory(request.target):
                    return "low"
                else:
                    return "medium"
            return "low"
        
        # Special handling for file operations in safe directories
        if request.operation.startswith("file.") and request.target:
            # Delete operations are ALWAYS high-risk, regardless of directory
            if request.operation == "file.delete":
                return "high"
            elif self.is_safe_directory(request.target):
                # Other file operations in safe directories are low risk
                return "low"
            else:
                return "medium"
        
        return "medium"
    
    def _assess_shell_command_risk(self, request: ConsentRequest) -> str:
        """Assess risk level for shell commands based on the actual command"""
        if 'command' not in request.details.get('args', {}):
            return "high"  # No command specified = high risk
        
        command = request.details['args']['command'].strip()
        
        # Extract the base command (first word)
        base_command = command.split()[0] if command else ""
        
        # Safe commands get low risk
        if base_command in self.safe_shell_commands:
            return "low"
        
        # Check for dangerous patterns
        dangerous_patterns = [
            'rm ', 'sudo', 'chmod 777', 'passwd', 'useradd', 'userdel',
            'mount', 'umount', 'systemctl', 'service', 'iptables', 'ufw',
            'mkfs', 'dd if=', '>/dev/', 'curl', 'wget', 'nc ', 'netcat'
        ]
        
        command_lower = command.lower()
        for pattern in dangerous_patterns:
            if pattern in command_lower:
                return "high"
        
        # Moderate risk for other commands
        return "medium"
    
    def get_consent_key(self, request: ConsentRequest) -> str:
        """Generate a unique key for the consent request"""
        return f"{request.operation}:{request.target}"
    
    async def request_consent(self, request: ConsentRequest) -> ConsentDecision:
        """Request user consent for an operation"""
        
        # Update risk level
        request.risk_level = self.assess_risk_level(request)
        
        # Check global decisions
        if self.global_allow_all:
            logger.info(f"Auto-approved (global): {request}")
            return ConsentDecision.ALLOW
        
        if self.global_deny_all:
            logger.info(f"Auto-denied (global): {request}")
            return ConsentDecision.DENY
        
        consent_key = self.get_consent_key(request)
        
        # Check session approvals/denials
        if consent_key in self.session_approvals:
            logger.info(f"Auto-approved (session): {request}")
            return ConsentDecision.ALLOW
        
        if consent_key in self.session_denials:
            logger.info(f"Auto-denied (session): {request}")
            return ConsentDecision.DENY
        
        # Non-interactive mode - check auto-approval first
        if not self.interactive:
            # Auto-approve safe operations if enabled
            if self.auto_approve_safe and request.risk_level == "low":
                logger.info(f"Auto-approved (safe, non-interactive): {request}")
                return ConsentDecision.ALLOW
            else:
                logger.warning(f"Non-interactive mode: denying {request}")
                return ConsentDecision.DENY
        
        # Interactive mode - auto-approve safe operations if enabled
        if self.auto_approve_safe and request.risk_level == "low":
            logger.info(f"Auto-approved (safe): {request}")
            return ConsentDecision.ALLOW
        
        # Interactive consent prompt
        return self._prompt_user_consent(request)
    
    def _prompt_user_consent(self, request: ConsentRequest) -> ConsentDecision:
        """Prompt user for consent interactively"""
        
        # Display consent request
        print("\n" + "="*60)
        print("🔐 AGENT CONSENT REQUEST")
        print("="*60)
        print(f"Operation: {request.operation}")
        print(f"Target: {request.target}")
        print(f"Risk Level: {request.risk_level.upper()}")
        
        if request.details:
            print("Details:")
            for key, value in request.details.items():
                print(f"  {key}: {value}")
        
        print("\nThe agent wants to perform this operation.")
        print("What would you like to do?")
        print()
        print("Options:")
        print("  [a] Allow this operation")
        print("  [d] Deny this operation") 
        print("  [A] Allow ALL operations (session)")
        print("  [D] Deny ALL operations (session)")
        print("  [s] Allow this operation type for this session")
        print("  [?] Show more details")
        print()
        
        while True:
            try:
                choice = input("Your choice [a/d/A/D/s/?]: ").strip().lower()
                
                if choice == 'a':
                    print("✅ Operation APPROVED")
                    return ConsentDecision.ALLOW
                
                elif choice == 'd':
                    print("❌ Operation DENIED")
                    return ConsentDecision.DENY
                
                elif choice == 'A':
                    print("✅ ALL operations APPROVED for this session")
                    self.global_allow_all = True
                    return ConsentDecision.ALLOW_ALL
                
                elif choice == 'D':
                    print("❌ ALL operations DENIED for this session")
                    self.global_deny_all = True
                    return ConsentDecision.DENY_ALL
                
                elif choice == 's':
                    print(f"✅ All '{request.operation}' operations APPROVED for this session")
                    consent_key = self.get_consent_key(request)
                    self.session_approvals.add(consent_key)
                    return ConsentDecision.ALLOW_SESSION
                
                elif choice == '?':
                    self._show_detailed_info(request)
                    continue
                
                else:
                    print("Invalid choice. Please enter a, d, A, D, s, or ?")
                    continue
                    
            except KeyboardInterrupt:
                print("\n❌ Operation CANCELLED by user")
                return ConsentDecision.DENY
            except EOFError:
                print("\n❌ Operation DENIED (no input)")
                return ConsentDecision.DENY
    
    def _show_detailed_info(self, request: ConsentRequest):
        """Show detailed information about the operation"""
        print("\n" + "-"*40)
        print("DETAILED INFORMATION")
        print("-"*40)
        
        if request.operation.startswith("file."):
            self._show_file_operation_details(request)
        elif request.operation == "shell.exec":
            self._show_shell_operation_details(request)
        elif request.operation == "code.python":
            self._show_code_operation_details(request)
        else:
            print(f"Operation: {request.operation}")
            print(f"Target: {request.target}")
            print(f"Risk Level: {request.risk_level}")
        
        print("-"*40)
    
    def _show_file_operation_details(self, request: ConsentRequest):
        """Show details for file operations"""
        operation = request.operation.split(".")[-1]
        target_path = Path(request.target)
        
        print(f"File Operation: {operation.upper()}")
        print(f"Target Path: {target_path}")
        print(f"Absolute Path: {target_path.resolve()}")
        print(f"Directory: {target_path.parent}")
        print(f"Safe Directory: {'Yes' if self.is_safe_directory(str(target_path)) else 'No'}")
        
        if target_path.exists():
            print(f"File Exists: Yes")
            if target_path.is_file():
                print(f"File Size: {target_path.stat().st_size} bytes")
        else:
            print(f"File Exists: No")
        
        if operation == "write" and "content" in request.details:
            content = request.details["content"]
            lines = content.count('\n') + 1
            print(f"Content Length: {len(content)} characters, {lines} lines")
            if len(content) < 200:
                print(f"Content Preview:\n{content[:200]}")
            else:
                print(f"Content Preview:\n{content[:200]}...")
    
    def _show_shell_operation_details(self, request: ConsentRequest):
        """Show details for shell operations"""
        print(f"Shell Command: {request.details.get('command', 'N/A')}")
        print("⚠️  WARNING: Shell commands can modify your system")
        print("⚠️  Only approve if you trust this command")
    
    def _show_code_operation_details(self, request: ConsentRequest):
        """Show details for code execution"""
        code = request.details.get('code', 'N/A')
        print(f"Python Code ({len(code)} characters):")
        print("-" * 20)
        print(code[:500] + ("..." if len(code) > 500 else ""))
        print("-" * 20)
        print("⚠️  WARNING: Code execution can modify your system")
        print("⚠️  Only approve if you trust this code")
    
    def record_decision(self, request: ConsentRequest, decision: ConsentDecision):
        """Record the user's decision for future reference"""
        consent_key = self.get_consent_key(request)
        
        if decision == ConsentDecision.ALLOW:
            logger.info(f"User approved: {request}")
        elif decision == ConsentDecision.DENY:
            logger.info(f"User denied: {request}")
        elif decision == ConsentDecision.ALLOW_SESSION:
            self.session_approvals.add(consent_key)
            logger.info(f"User approved for session: {request}")
        elif decision == ConsentDecision.ALLOW_ALL:
            self.global_allow_all = True
            logger.info("User approved all operations for session")
        elif decision == ConsentDecision.DENY_ALL:
            self.global_deny_all = True
            logger.info("User denied all operations for session")
    
    def reset_session_permissions(self):
        """Reset session-based permissions"""
        self.session_approvals.clear()
        self.session_denials.clear()
        self.global_allow_all = False
        self.global_deny_all = False
        logger.info("Session permissions reset")


# Global consent manager instance
_consent_manager: Optional[ConsentManager] = None


def get_consent_manager() -> ConsentManager:
    """Get the global consent manager instance"""
    global _consent_manager
    if _consent_manager is None:
        _consent_manager = ConsentManager()
    return _consent_manager


def set_consent_manager(manager: ConsentManager):
    """Set the global consent manager instance"""
    global _consent_manager
    _consent_manager = manager


async def request_operation_consent(
    operation: str, 
    target: str, 
    details: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Request consent for an operation.
    
    Returns True if approved, False if denied.
    """
    consent_manager = get_consent_manager()
    
    request = ConsentRequest(
        operation=operation,
        target=target,
        details=details or {}
    )
    
    decision = await consent_manager.request_consent(request)
    consent_manager.record_decision(request, decision)
    
    return decision in [
        ConsentDecision.ALLOW, 
        ConsentDecision.ALLOW_ALL, 
        ConsentDecision.ALLOW_SESSION
    ]
