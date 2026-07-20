"""
Transport and at-rest encryption using AES-256-GCM and X25519 ECDH.
Generates self-signed TLS certificates on first boot.
"""

import os
import secrets
import hashlib
from typing import Tuple, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509.oid import NameOID
import cryptography.x509 as x509_module
from cryptography.x509 import CertificateBuilder, Name
from datetime import datetime, timedelta
import base64
import json


class EncryptionManager:
    """Handles AES-256-GCM encryption/decryption with ECDH key exchange"""
    
    @staticmethod
    def generate_x25519_keypair() -> Tuple[x25519.X25519PrivateKey, bytes]:
        """
        Generate X25519 key pair for ECDH.
        
        Returns:
            Tuple of (private_key, public_key_bytes)
        """
        private_key = x25519.X25519PrivateKey.generate()
        public_key = private_key.public_key()
        public_key_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return private_key, public_key_bytes
    
    @staticmethod
    def derive_shared_secret(
        private_key: x25519.X25519PrivateKey,
        peer_public_key_bytes: bytes
    ) -> bytes:
        """
        Derive shared secret using X25519 ECDH.
        
        Args:
            private_key: Our X25519 private key
            peer_public_key_bytes: Peer's public key (32 bytes)
            
        Returns:
            32-byte shared secret
        """
        peer_public_key = x25519.X25519PublicKey(peer_public_key_bytes)
        shared_secret = private_key.exchange(peer_public_key)
        return shared_secret
    
    @staticmethod
    def derive_session_key(shared_secret: bytes, salt: bytes = b"edge-drishti-session") -> bytes:
        """
        Derive AES-256-GCM session key from shared secret using HKDF.
        
        Args:
            shared_secret: 32-byte shared secret from ECDH
            salt: Optional salt for KDF
            
        Returns:
            32-byte AES-256 key
        """
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"edge-drishti-aes256-gcm"
        )
        return hkdf.derive(shared_secret)
    
    @staticmethod
    def encrypt_aes_gcm(plaintext: bytes, key: bytes, additional_data: Optional[bytes] = None) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt data with AES-256-GCM.
        
        Args:
            plaintext: Data to encrypt
            key: 32-byte AES-256 key
            additional_data: Optional authenticated data (AAD)
            
        Returns:
            Tuple of (ciphertext, nonce, tag)
        """
        nonce = secrets.token_bytes(12)  # 96-bit nonce for GCM
        cipher = AESGCM(key)
        ciphertext = cipher.encrypt(nonce, plaintext, additional_data)
        return ciphertext, nonce, b"tag_included_in_ciphertext"
    
    @staticmethod
    def decrypt_aes_gcm(
        ciphertext: bytes,
        key: bytes,
        nonce: bytes,
        additional_data: Optional[bytes] = None
    ) -> bytes:
        """
        Decrypt AES-256-GCM encrypted data.
        
        Args:
            ciphertext: Encrypted data (includes tag)
            key: 32-byte AES-256 key
            nonce: 12-byte nonce used for encryption
            additional_data: Optional authenticated data (AAD)
            
        Returns:
            Decrypted plaintext
        """
        cipher = AESGCM(key)
        plaintext = cipher.decrypt(nonce, ciphertext, additional_data)
        return plaintext
    
    @staticmethod
    def encrypt_payload(data: dict, key: bytes) -> str:
        """
        Encrypt a JSON payload with AES-256-GCM and return base64 string.
        
        Args:
            data: Dict to encrypt
            key: 32-byte AES-256 key
            
        Returns:
            Base64-encoded {nonce}:{ciphertext} string
        """
        plaintext = json.dumps(data).encode()
        nonce = secrets.token_bytes(12)
        cipher = AESGCM(key)
        ciphertext = cipher.encrypt(nonce, plaintext, None)
        
        # Return base64(nonce + ciphertext)
        encrypted = nonce + ciphertext
        return base64.b64encode(encrypted).decode()
    
    @staticmethod
    def decrypt_payload(encrypted_str: str, key: bytes) -> dict:
        """
        Decrypt a base64 AES-256-GCM encrypted payload.
        
        Args:
            encrypted_str: Base64-encoded {nonce}:{ciphertext} string
            key: 32-byte AES-256 key
            
        Returns:
            Decrypted dict
        """
        encrypted = base64.b64decode(encrypted_str)
        nonce = encrypted[:12]
        ciphertext = encrypted[12:]
        
        cipher = AESGCM(key)
        plaintext = cipher.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())


class TLSCertificateManager:
    """Generates self-signed TLS certificates"""
    
    @staticmethod
    def generate_self_signed_certificate(
        cert_path: str,
        key_path: str,
        hostname: str = "localhost",
        days_valid: int = 365
    ) -> None:
        """
        Generate self-signed TLS certificate and key.
        
        Args:
            cert_path: Path to save certificate
            key_path: Path to save private key
            hostname: Certificate common name (default: localhost)
            days_valid: Certificate validity in days
        """
        from cryptography.hazmat.primitives.asymmetric import rsa
        
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        
        subject = issuer = Name([
            x509_module.NameAttribute(NameOID.COMMON_NAME, hostname),
        ])
        
        cert = CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509_module.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=days_valid)
        ).add_extension(
            x509_module.SubjectAlternativeName([
                x509_module.DNSName(hostname),
                x509_module.DNSName("edgedrishti.local"),
                x509_module.DNSName("localhost"),
                x509_module.DNSName("127.0.0.1"),
                x509_module.DNSName("::1"),
            ]),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        
        os.chmod(cert_path, 0o600)
        os.chmod(key_path, 0o600)
    
    @staticmethod
    def ensure_tls_certificate(cert_path: str, key_path: str) -> None:
        """
        Ensure TLS certificate exists; generate if not.
        
        Args:
            cert_path: Path to certificate
            key_path: Path to private key
        """
        if not os.path.exists(cert_path) or not os.path.exists(key_path):
            TLSCertificateManager.generate_self_signed_certificate(cert_path, key_path)



encryption_manager = EncryptionManager()
tls_manager = TLSCertificateManager()
