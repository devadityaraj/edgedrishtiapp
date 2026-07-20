"""
Login lockout state machine implementation.
Enforces progressive lockout and account disabling per specification.
"""

from datetime import datetime, timedelta
from typing import Dict, Tuple, Optional
from enum import Enum


class LoginAttemptResult(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"
    LOCKED_TEMPORARY = "locked_temporary"
    ACCOUNT_DISABLED = "account_disabled"
    USERNAME_NOT_FOUND = "username_not_found"


class LockoutStateMachine:
    """
    Manages login attempt tracking and lockout state.
    
    Rules:
    - Attempts 1-2: generic error, no lockout
    - Attempt 3+: 30s lockout per attempt
    - 5 total failed attempts with valid username: account disabled
    - Invalid username: no account disable, but IP-based 30s lockout
    """
    
    LOCKOUT_THRESHOLD = 3  
    LOCKOUT_DURATION_SECONDS = 30
    MAX_FAILED_ATTEMPTS = 5  
    
    @staticmethod
    def check_lockout_status(
        failed_attempt_count: int,
        lockout_until: Optional[datetime],
        account_disabled: bool
    ) -> Tuple[LoginAttemptResult, Optional[str]]:
        """
        Check if account/IP is currently locked.
        
        Args:
            failed_attempt_count: Total failed attempts for this user
            lockout_until: Datetime of when lockout expires (if locked)
            account_disabled: Whether account is permanently disabled
            
        Returns:
            Tuple of (status, message)
        """
        if account_disabled:
            return LoginAttemptResult.ACCOUNT_DISABLED, "Account is disabled"
        
        if lockout_until and datetime.utcnow() < lockout_until:
            remaining = (lockout_until - datetime.utcnow()).seconds
            return LoginAttemptResult.LOCKED_TEMPORARY, f"Try again in {remaining}s"
        
        return LoginAttemptResult.SUCCESS, None
    
    @staticmethod
    def process_failed_login_attempt(
        failed_attempt_count: int,
        username_found: bool
    ) -> Tuple[LoginAttemptResult, int, Optional[datetime]]:
        """
        Process a failed login attempt and return new state.
        
        Args:
            failed_attempt_count: Current failed attempt count
            username_found: Whether username exists in system
            
        Returns:
            Tuple of (result, new_failed_count, lockout_until)
        """
        
        new_failed_count = failed_attempt_count + 1
        lockout_until = None
        
        
        
        if not username_found:
            if new_failed_count >= 3:
                # IP lockout for invalid usernames too
                lockout_until = datetime.utcnow() + timedelta(
                    seconds=LockoutStateMachine.LOCKOUT_DURATION_SECONDS
                )
                return LoginAttemptResult.LOCKED_TEMPORARY, new_failed_count, lockout_until
            return LoginAttemptResult.FAIL, new_failed_count, None
        
        
        if new_failed_count >= LockoutStateMachine.MAX_FAILED_ATTEMPTS:
            return LoginAttemptResult.ACCOUNT_DISABLED, new_failed_count, None
        
        # Check lockout threshold (attempt 3+)
        if new_failed_count >= LockoutStateMachine.LOCKOUT_THRESHOLD:
            lockout_until = datetime.utcnow() + timedelta(
                seconds=LockoutStateMachine.LOCKOUT_DURATION_SECONDS
            )
            return LoginAttemptResult.LOCKED_TEMPORARY, new_failed_count, lockout_until
        
        
        return LoginAttemptResult.FAIL, new_failed_count, None
    
    @staticmethod
    def process_successful_login(
        user_id: str,
        failed_attempt_count: int
    ) -> Tuple[int, Optional[datetime]]:
        """
        Reset lockout state on successful login.
        
        Args:
            user_id: User who successfully logged in
            failed_attempt_count: Current failed count to reset
            
        Returns:
            Tuple of (new_failed_count=0, lockout_until=None)
        """
        return 0, None
    
    @staticmethod
    def get_lockout_expiry(
        current_failed_count: int
    ) -> Optional[datetime]:
        """
        Get when the next lockout expires based on attempt count.
        
        Args:
            current_failed_count: Current failed attempt count
            
        Returns:
            Datetime when lockout expires, or None if no lockout
        """
        if current_failed_count >= LockoutStateMachine.LOCKOUT_THRESHOLD:
            return datetime.utcnow() + timedelta(
                seconds=LockoutStateMachine.LOCKOUT_DURATION_SECONDS
            )
        return None


class IPBasedLockout:
    """Track IP-based lockout for brute force protection"""
    
    # In production, use Redis or similar; for now, in-memory dict
    # Format: {"ip": {"locked_until": datetime, "attempt_count": int}}
    _ip_lockouts: Dict[str, Dict] = {}
    
    @staticmethod
    def is_ip_locked(ip_address: str) -> Tuple[bool, Optional[str]]:
        """
        Check if an IP address is currently locked.
        
        Args:
            ip_address: IP address to check
            
        Returns:
            Tuple of (is_locked, message)
        """
        if ip_address not in IPBasedLockout._ip_lockouts:
            return False, None
        
        lock_info = IPBasedLockout._ip_lockouts[ip_address]
        if lock_info["locked_until"] and datetime.utcnow() < lock_info["locked_until"]:
            remaining = (lock_info["locked_until"] - datetime.utcnow()).seconds
            return True, f"IP locked. Try again in {remaining}s"
        
        
        del IPBasedLockout._ip_lockouts[ip_address]
        return False, None
    
    @staticmethod
    def lock_ip(ip_address: str, duration_seconds: int = 30) -> None:
        """
        Lock an IP address temporarily.
        
        Args:
            ip_address: IP to lock
            duration_seconds: Lockout duration
        """
        IPBasedLockout._ip_lockouts[ip_address] = {
            "locked_until": datetime.utcnow() + timedelta(seconds=duration_seconds),
            "attempt_count": IPBasedLockout._ip_lockouts.get(ip_address, {}).get("attempt_count", 0) + 1
        }
    
    @staticmethod
    def clear_ip_lock(ip_address: str) -> None:
        """Clear lock on an IP address"""
        if ip_address in IPBasedLockout._ip_lockouts:
            del IPBasedLockout._ip_lockouts[ip_address]
