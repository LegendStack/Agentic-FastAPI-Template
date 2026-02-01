from typing import Any

from pydantic import BaseModel, EmailStr


class UserIdentity(BaseModel):
    subject: str  # Unique identifier (sub in JWT, oid in Entra)
    email: EmailStr | None = None
    full_name: str | None = None
    username: str | None = None
    raw_claims: dict[str, Any] = {}
    provider: str
