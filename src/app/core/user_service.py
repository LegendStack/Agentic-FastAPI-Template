from typing import Any, cast

from sqlalchemy.ext.asyncio import AsyncSession

from ..crud.crud_users import crud_users
from .config import settings
from .identity import UserIdentity
from .logger import logging

logger = logging.getLogger(__name__)


class IdentityService:
    @staticmethod
    async def get_or_create_user(db: AsyncSession, identity: UserIdentity) -> dict[str, Any]:
        """
        Synchronizes a UserIdentity with the local database.
        Implements JIT (Just-In-Time) provisioning and role mapping.
        """
        # 1. Search for existing user by subject or email
        user: dict[str, Any] | None = None
        if identity.email:
            user = cast(dict[str, Any], await crud_users.get(db=db, email=identity.email, is_deleted=False))

        if not user and identity.username:
            user = cast(dict[str, Any], await crud_users.get(db=db, username=identity.username, is_deleted=False))

        if user:
            # Update existing user if needed (e.g., name changed in Entra)
            # This is where we could update roles as well
            logger.info(f"Identity synced for user: {identity.email}")
            return user

        # 2. Map Entra roles/groups to local tiers/superuser
        is_superuser = False
        tier_id = 1  # Default tier (usually 'free')

        # Simple role mapping example (can be expanded via settings.ENTRA_ROLE_MAPPING)
        roles = identity.raw_claims.get("roles", [])
        groups = identity.raw_claims.get("groups", [])

        # Checking if any role matches a superuser group defined in config
        # For now, let's look for a generic "Admin" role if it exists in claims
        admin_group = settings.ENTRA_ROLE_MAPPING.get("admin_group")
        if "Admin" in roles or any(g == admin_group for g in groups):
            is_superuser = True

        # 3. Create new user record (JIT Provisioning)
        logger.info(f"Provisioning new user from identity: {identity.email} ({identity.provider})")

        email = identity.email or f"{identity.subject}@{identity.provider}.local"
        username = identity.username or email.split("@")[0]
        name = identity.full_name or username

        new_user_data = {
            "name": name,
            "email": email,
            "username": username,
            "hashed_password": "SSO_USER",  # Indicator that this user doesn't use local pass
        }

        try:
            from ..schemas.user import UserCreateInternal

            user_create = UserCreateInternal(**new_user_data)
            user = cast(dict[str, Any], await crud_users.create(db=db, object=user_create))

            # Update roles if needed (superuser/tier)
            if is_superuser or tier_id != 1:
                await crud_users.update(db=db, id=user["id"], object={"is_superuser": is_superuser, "tier_id": tier_id})
                user = cast(dict[str, Any], await crud_users.get(db=db, id=user["id"]))

            logger.info(f"Audit: User created via SSO - {identity.email}")
            return user
        except Exception as e:
            logger.error(f"Failed to provision user {identity.email}: {e}")
            raise
