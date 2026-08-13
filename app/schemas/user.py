"""Pydantic schemas for the User resource, registration, and approval workflow."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, validator

from app.core.constants import RoleName, UserStatus


class UserRegisterRequest(BaseModel):
    """Payload for self-service registration (``POST /auth/register``)."""

    username: str = Field(..., min_length=3, max_length=50, regex=r"^[a-zA-Z0-9_.\-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=150)
    group_id: Optional[int] = None
    # Every Group the user should belong to (in addition to/including their
    # primary ``group_id``). When provided, this is the full membership set
    # -- omit it (leave as None) to make no change to group membership.
    group_ids: Optional[List[int]] = None

    @validator("password")
    def _validate_password_strength(cls, value: str) -> str:  # noqa: N805
        """Enforce a minimum password complexity policy."""
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit.")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter.")
        return value


class UserCreateRequest(BaseModel):
    """Payload for an admin directly creating an already-approved user."""

    username: str = Field(..., min_length=3, max_length=50, regex=r"^[a-zA-Z0-9_.\-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=150)
    role_name: str = Field(default=RoleName.USER)
    group_id: Optional[int] = None
    group_ids: Optional[List[int]] = None

    @validator("role_name")
    def _validate_role(cls, value: str) -> str:  # noqa: N805
        if value not in RoleName.ALL:
            raise ValueError("role_name must be one of: {0}".format(", ".join(RoleName.ALL)))
        return value


class UserUpdateRequest(BaseModel):
    """Payload for updating a user's profile/role/group. All fields optional."""

    full_name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    role_name: Optional[str] = None
    group_id: Optional[int] = None
    group_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None

    @validator("role_name")
    def _validate_role(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in RoleName.ALL:
            raise ValueError("role_name must be one of: {0}".format(", ".join(RoleName.ALL)))
        return value


class UserApprovalRequest(BaseModel):
    """Payload for approving or rejecting a pending registration."""

    approve: bool
    role_name: Optional[str] = Field(
        default=None, description="Role to assign on approval; defaults to USER if omitted."
    )
    rejection_reason: Optional[str] = Field(default=None, max_length=500)

    @validator("role_name")
    def _validate_role(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in RoleName.ALL:
            raise ValueError("role_name must be one of: {0}".format(", ".join(RoleName.ALL)))
        return value


class ChangePasswordRequest(BaseModel):
    """Payload for a user changing their own password."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class PasswordResetRequestRequest(BaseModel):
    """Payload for requesting a password-reset email ("forgot password")."""

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Payload for completing a password reset with the emailed token."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class RoleResponse(BaseModel):
    """Read model for a Role."""

    id: int
    name: str
    description: Optional[str] = None

    class Config:
        orm_mode = True


class GroupSummaryResponse(BaseModel):
    """Minimal Group read model, nested inside UserResponse."""

    id: int
    name: str

    class Config:
        orm_mode = True


class UserResponse(BaseModel):
    """Read model for a User."""

    id: int
    username: str
    email: EmailStr
    full_name: str
    status: str
    is_active: bool
    role: RoleResponse
    group: Optional[GroupSummaryResponse] = None
    groups: List[GroupSummaryResponse] = []
    approved_by_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class UserFilter(BaseModel):
    """Query-parameter filter set for listing users."""

    status: Optional[str] = None
    role_name: Optional[str] = None
    group_id: Optional[int] = None
    search: Optional[str] = None

    @validator("status")
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in UserStatus.ALL:
            raise ValueError("status must be one of: {0}".format(", ".join(UserStatus.ALL)))
        return value
