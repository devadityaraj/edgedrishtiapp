"""
Secure password, PIN, and recovery-key hashing using Argon2id.
Per-record salting using cryptographically secure random generation.
"""

import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
from typing import Tuple

# Use Argon2id with strict security parameters
hasher = PasswordHasher(
    time_cost=2,  
    memory_cost=65536,  
    parallelism=4,  
    hash_len=32,  
    salt_len=16,  
)


def hash_password(password: str) -> Tuple[str, str]:
    """
    Hash a password with Argon2id and return (hash, salt).
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Tuple of (hashed_password, salt) - salt extracted from hash
    """
    if not password or len(password) < 6:
        raise ValueError("Password must be at least 6 characters")
    
    hash_result = hasher.hash(password)
    # Argon2 hash includes the salt; extract it for storage if needed
    
    return hash_result, secrets.token_hex(16)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its Argon2id hash.
    
    Args:
        password: Plain text password to verify
        password_hash: Stored Argon2id hash
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHash):
        return False


def hash_pin(pin: str) -> Tuple[str, str]:
    """
    Hash an admin PIN with Argon2id.
    
    Args:
        pin: 4-8 digit PIN
        
    Returns:
        Tuple of (hashed_pin, salt)
    """
    if not pin or len(pin) < 4 or len(pin) > 8 or not pin.isdigit():
        raise ValueError("PIN must be 4-8 digits")
    
    hash_result = hasher.hash(pin)
    return hash_result, secrets.token_hex(16)


def verify_pin(pin: str, pin_hash: str) -> bool:
    """
    Verify a PIN against its Argon2id hash.
    
    Args:
        pin: Plain text PIN
        pin_hash: Stored Argon2id hash
        
    Returns:
        True if PIN matches, False otherwise
    """
    try:
        hasher.verify(pin_hash, pin)
        return True
    except (VerifyMismatchError, InvalidHash):
        return False


def hash_recovery_key(recovery_key: str) -> Tuple[str, str]:
    """
    Hash a recovery key with Argon2id.
    
    Args:
        recovery_key: 128-bit alphanumeric recovery key
        
    Returns:
        Tuple of (hashed_key, salt)
    """
    if not recovery_key or len(recovery_key) < 32:
        raise ValueError("Recovery key must be at least 32 characters")
    
    hash_result = hasher.hash(recovery_key)
    return hash_result, secrets.token_hex(16)


def verify_recovery_key(recovery_key: str, recovery_key_hash: str) -> bool:
    """
    Verify a recovery key against its Argon2id hash.
    
    Args:
        recovery_key: Plain text recovery key
        recovery_key_hash: Stored Argon2id hash
        
    Returns:
        True if recovery key matches, False otherwise
    """
    try:
        hasher.verify(recovery_key_hash, recovery_key)
        return True
    except (VerifyMismatchError, InvalidHash):
        return False


def generate_recovery_key() -> str:
    """
    Generate a cryptographically secure 128-bit alphanumeric recovery key.
    
    Returns:
        128-bit alphanumeric recovery key (base64-style, no padding)
    """
    # Generate 32 random bytes (256 bits) for 128-bit entropy with alphanumeric
    random_bytes = secrets.token_bytes(32)
    
    import base64
    key = base64.urlsafe_b64encode(random_bytes).decode().replace("-", "").replace("_", "").upper()[:43]
    return key


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.
    
    Args:
        length: Length of token in bytes (default 32)
        
    Returns:
        Hex-encoded random token
    """
    return secrets.token_hex(length)
