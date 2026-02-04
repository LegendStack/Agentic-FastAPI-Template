"""
Zero-Trust Encryption Utility.
==============================
Provides tenant-aware symmetric encryption for sensitive RAG data.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet

from .config import settings

logger = logging.getLogger(__name__)


class TenantEncryption:
    """
    Handles encryption/decryption using keys derived from tenant_id.
    """

    @staticmethod
    def _get_tenant_key(tenant_id: str) -> bytes:
        """
        Derives a symmetric key for a specific tenant.
        In production, this would fetch from a KMS (Azure Key Vault, AWS KMS).
        """
        # Derive a 32-byte key from tenant_id + master secret
        combined = f"{tenant_id}:{settings.SECRET_KEY.get_secret_value()}".encode()
        key_hash = hashlib.sha256(combined).digest()
        return base64.urlsafe_b64encode(key_hash)

    @classmethod
    def encrypt(cls, data: str, tenant_id: str) -> str:
        """Encrypts data for a specific tenant."""
        if not data or not tenant_id:
            return data

        try:
            key = cls._get_tenant_key(tenant_id)
            f = Fernet(key)
            return f.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption failed for tenant {tenant_id}: {e}")
            return data

    @classmethod
    def decrypt(cls, encrypted_data: str, tenant_id: str) -> str:
        """Decrypts data for a specific tenant."""
        if not encrypted_data or not tenant_id:
            return encrypted_data

        try:
            key = cls._get_tenant_key(tenant_id)
            f = Fernet(key)
            return f.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption failed for tenant {tenant_id}: {e}")
            return encrypted_data
