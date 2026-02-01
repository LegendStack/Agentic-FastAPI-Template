import time
from abc import ABC, abstractmethod
from typing import Any, cast

import httpx
from fastapi import HTTPException
from jose import JWTError, jwt

from .config import settings
from .identity import UserIdentity
from .logger import logging

logger = logging.getLogger(__name__)


class AuthProviderBase(ABC):
    @abstractmethod
    async def verify_token(self, token: str) -> UserIdentity | None:
        pass


class LocalJWTProvider(AuthProviderBase):
    async def verify_token(self, token: str) -> UserIdentity | None:
        try:
            payload: dict[str, Any] = jwt.decode(
                token, settings.SECRET_KEY.get_secret_value(), algorithms=[settings.ALGORITHM]
            )
            username_or_email = payload.get("sub")
            if not username_or_email:
                raise HTTPException(status_code=401, detail="Invalid token: missing sub")

            return UserIdentity(
                subject=username_or_email,
                username=username_or_email if "@" not in username_or_email else None,
                email=username_or_email if "@" in username_or_email else None,
                raw_claims=payload,
                provider="local",
            )
        except JWTError as e:
            logger.error(f"Local JWT validation failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid or expired token")


class EntraIDProvider(AuthProviderBase):
    def __init__(self) -> None:
        self.jwks_cache: dict[str, Any] | None = None
        self.cache_expires: float = 0
        self.tenant_id: str = settings.AZURE_TENANT_ID or ""
        self.client_id: str = settings.AZURE_CLIENT_ID or ""

        if not self.tenant_id or not self.client_id:
            logger.error("Entra ID configuration missing (AZURE_TENANT_ID or AZURE_CLIENT_ID)")

        self.jwks_url: str = settings.ENTRA_JWKS_URL.format(tenant_id=self.tenant_id)
        self.issuer: str = settings.ENTRA_ISSUER.format(tenant_id=self.tenant_id)

    async def _get_jwks(self) -> dict[str, Any]:
        if self.jwks_cache and time.time() < self.cache_expires:
            return self.jwks_cache

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.jwks_url)
                response.raise_for_status()
                self.jwks_cache = cast(dict[str, Any], response.json())
                self.cache_expires = time.time() + 3600  # Cache for 1 hour
                return self.jwks_cache
        except Exception as e:
            logger.error(f"Failed to fetch JWKS from Entra ID: {e}")
            if self.jwks_cache:
                return self.jwks_cache  # Return stale cache on failure
            raise HTTPException(status_code=503, detail="Authentication service unavailable")

    async def verify_token(self, token: str) -> UserIdentity | None:
        jwks = await self._get_jwks()
        try:
            # We use the algorithms supported by Entra ID (typically RS256)
            payload: dict[str, Any] = jwt.decode(
                token, jwks, algorithms=["RS256"], audience=self.client_id, issuer=self.issuer
            )

            oid = payload.get("oid") or payload.get("sub")
            email = payload.get("email") or payload.get("preferred_username")
            name = payload.get("name")

            if not oid:
                raise HTTPException(status_code=401, detail="Invalid Entra ID token: missing oid/sub")

            return UserIdentity(
                subject=oid,
                email=email,
                full_name=name,
                username=email,  # Often used as username in enterprise apps
                raw_claims=payload,
                provider="entra",
            )
        except JWTError as e:
            logger.warn(f"Entra ID token validation failed: {e}")
            raise HTTPException(status_code=401, detail=f"Invalid Entra ID token: {str(e)}")


def get_auth_provider() -> AuthProviderBase:
    if settings.AUTH_PROVIDER == "entra":
        return EntraIDProvider()
    return LocalJWTProvider()
