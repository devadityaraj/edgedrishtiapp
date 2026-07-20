"""
Device and browser fingerprinting for login tracking.
Captures comprehensive browser/device data per specification.
"""

import hashlib
import json
from typing import Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


class BrowserFingerprint(BaseModel):
    """Browser and device fingerprint data"""
    
    
    ip_address: str
    
    
    user_agent: str
    browser_name: Optional[str] = None
    browser_version: Optional[str] = None
    os_name: Optional[str] = None
    os_version: Optional[str] = None
    
    
    device_type: str = "unknown"  
    screen_resolution: Optional[str] = None
    viewport_width: Optional[int] = None
    viewport_height: Optional[int] = None
    
    
    timezone: Optional[str] = None
    language: Optional[str] = None
    languages: Optional[str] = None  
    platform_string: Optional[str] = None
    referrer: Optional[str] = None
    
    
    hardware_concurrency: Optional[int] = None
    color_depth: Optional[int] = None
    pixel_depth: Optional[int] = None
    
    # Extra fingerprint JSON for extensibility
    extra: Dict[str, Any] = Field(default_factory=dict)
    
    
    captured_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    class Config:
        json_schema_extra = {
            "example": {
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0...",
                "browser_name": "Chrome",
                "browser_version": "120.0",
                "os_name": "Windows",
                "os_version": "11",
                "device_type": "desktop",
                "screen_resolution": "1920x1080",
                "timezone": "UTC",
                "language": "en-US",
                "hardware_concurrency": 8,
                "color_depth": 24
            }
        }


class FingerprintManager:
    """Manages device fingerprinting and hashing"""
    
    @staticmethod
    def create_fingerprint(
        ip_address: str,
        user_agent: str,
        browser_data: Dict[str, Any]
    ) -> BrowserFingerprint:
        """
        Create a fingerprint from browser/request data.
        
        Args:
            ip_address: Client IP address
            user_agent: User-Agent header
            browser_data: Dict with browser/device info from frontend
            
        Returns:
            BrowserFingerprint object
        """
        fingerprint = BrowserFingerprint(
            ip_address=ip_address,
            user_agent=user_agent,
            browser_name=browser_data.get("browserName"),
            browser_version=browser_data.get("browserVersion"),
            os_name=browser_data.get("osName"),
            os_version=browser_data.get("osVersion"),
            device_type=browser_data.get("deviceType", "unknown"),
            screen_resolution=browser_data.get("screenResolution"),
            viewport_width=browser_data.get("viewportWidth"),
            viewport_height=browser_data.get("viewportHeight"),
            timezone=browser_data.get("timezone"),
            language=browser_data.get("language"),
            languages=browser_data.get("languages"),
            platform_string=browser_data.get("platformString"),
            referrer=browser_data.get("referrer"),
            hardware_concurrency=browser_data.get("hardwareConcurrency"),
            color_depth=browser_data.get("colorDepth"),
            pixel_depth=browser_data.get("pixelDepth"),
            extra=browser_data.get("extra", {})
        )
        return fingerprint
    
    @staticmethod
    def hash_fingerprint(fingerprint: BrowserFingerprint) -> str:
        """
        Create a hash of the fingerprint for trusted device tokens.
        Hashes the subset of fingerprint that should be consistent:
        browser, OS, device type, screen resolution.
        
        Args:
            fingerprint: BrowserFingerprint object
            
        Returns:
            SHA-256 hash of fingerprint
        """
        # Hash these fields for trusted-device matching
        hashable_fields = {
            "browser_name": fingerprint.browser_name,
            "browser_version": fingerprint.browser_version,
            "os_name": fingerprint.os_name,
            "device_type": fingerprint.device_type,
            "screen_resolution": fingerprint.screen_resolution,
            "platform_string": fingerprint.platform_string,
        }
        
        fingerprint_str = json.dumps(hashable_fields, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
    
    @staticmethod
    def hash_ip_user_agent(ip_address: str, user_agent: str) -> str:
        """
        Quick hash of IP + User-Agent for IP-based lockout tracking.
        
        Args:
            ip_address: Client IP
            user_agent: User-Agent header
            
        Returns:
            SHA-256 hash
        """
        combined = f"{ip_address}:{user_agent}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    @staticmethod
    def fingerprints_match(
        fp1: BrowserFingerprint,
        fp2: BrowserFingerprint,
        strict: bool = True
    ) -> bool:
        """
        Check if two fingerprints match (for trusted device validation).
        
        Args:
            fp1: First fingerprint
            fp2: Second fingerprint
            strict: If True, require exact match; if False, allow minor variations
            
        Returns:
            True if fingerprints match
        """
        if strict:
            return (
                fp1.browser_name == fp2.browser_name and
                fp1.browser_version == fp2.browser_version and
                fp1.os_name == fp2.os_name and
                fp1.device_type == fp2.device_type and
                fp1.screen_resolution == fp2.screen_resolution
            )
        else:
            # Allow minor variations (e.g., browser version patch changes)
            return (
                fp1.browser_name == fp2.browser_name and
                fp1.os_name == fp2.os_name and
                fp1.device_type == fp2.device_type
            )
    
    @staticmethod
    def fingerprint_to_dict(fingerprint: BrowserFingerprint) -> Dict[str, Any]:
        """
        Convert fingerprint to dict for database storage.
        
        Args:
            fingerprint: BrowserFingerprint object
            
        Returns:
            Dict representation
        """
        return fingerprint.dict()
    
    @staticmethod
    def dict_to_fingerprint(data: Dict[str, Any]) -> BrowserFingerprint:
        """
        Create fingerprint from dict (from database).
        
        Args:
            data: Dict from database
            
        Returns:
            BrowserFingerprint object
        """
        return BrowserFingerprint(**data)



fingerprint_manager = FingerprintManager()
