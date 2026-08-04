"""Pydantic schemas for the Setup resource."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, validator

from app.core.constants import SetupStatus
from app.utils.validators import validate_ip_address, validate_hostname


class SetupCreateRequest(BaseModel):
    """Payload for creating a Setup. Mirrors every column in ``setups``."""

    product_id: int
    group_id: Optional[int] = None
    ip_address: str = Field(..., max_length=45)
    hostname: str = Field(..., max_length=255)
    ssd: Optional[str] = Field(default=None, max_length=100)
    hdd: Optional[str] = Field(default=None, max_length=100)
    hardware_info: Optional[str] = Field(default=None, max_length=500)
    capacity: Optional[str] = Field(default=None, max_length=100)
    form_factor: Optional[str] = Field(default=None, max_length=50)
    owner_id: Optional[int] = None
    adapter: Optional[str] = Field(default=None, max_length=100)
    aardvark: Optional[str] = Field(default=None, max_length=100)
    quarch: Optional[str] = Field(default=None, max_length=100)
    apc: Optional[str] = Field(default=None, max_length=100)
    remote_server: Optional[str] = Field(default=None, max_length=255)
    location: str = Field(..., max_length=255)
    remarks: Optional[str] = Field(default=None, max_length=1000)

    @validator("ip_address")
    def _validate_ip(cls, value: str) -> str:  # noqa: N805
        if not validate_ip_address(value):
            raise ValueError("ip_address must be a valid IPv4 or IPv6 address.")
        return value

    @validator("hostname")
    def _validate_hostname_field(cls, value: str) -> str:  # noqa: N805
        if not validate_hostname(value):
            raise ValueError("hostname must be a valid DNS hostname.")
        return value


class SetupUpdateRequest(BaseModel):
    """Payload for updating a Setup. All fields optional."""

    product_id: Optional[int] = None
    group_id: Optional[int] = None
    ip_address: Optional[str] = Field(default=None, max_length=45)
    hostname: Optional[str] = Field(default=None, max_length=255)
    ssd: Optional[str] = Field(default=None, max_length=100)
    hdd: Optional[str] = Field(default=None, max_length=100)
    hardware_info: Optional[str] = Field(default=None, max_length=500)
    capacity: Optional[str] = Field(default=None, max_length=100)
    form_factor: Optional[str] = Field(default=None, max_length=50)
    owner_id: Optional[int] = None
    adapter: Optional[str] = Field(default=None, max_length=100)
    aardvark: Optional[str] = Field(default=None, max_length=100)
    quarch: Optional[str] = Field(default=None, max_length=100)
    apc: Optional[str] = Field(default=None, max_length=100)
    remote_server: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    remarks: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = None

    @validator("ip_address")
    def _validate_ip(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and not validate_ip_address(value):
            raise ValueError("ip_address must be a valid IPv4 or IPv6 address.")
        return value

    @validator("hostname")
    def _validate_hostname_field(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and not validate_hostname(value):
            raise ValueError("hostname must be a valid DNS hostname.")
        return value

    @validator("status")
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in SetupStatus.ALL:
            raise ValueError("status must be one of: {0}".format(", ".join(SetupStatus.ALL)))
        return value


class SetupResponse(BaseModel):
    """Read model for a Setup."""

    id: int
    product_id: int
    group_id: Optional[int] = None
    ip_address: str
    hostname: str
    ssd: Optional[str] = None
    hdd: Optional[str] = None
    hardware_info: Optional[str] = None
    capacity: Optional[str] = None
    form_factor: Optional[str] = None
    owner_id: Optional[int] = None
    adapter: Optional[str] = None
    aardvark: Optional[str] = None
    quarch: Optional[str] = None
    apc: Optional[str] = None
    remote_server: Optional[str] = None
    location: str
    remarks: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class SetupFilter(BaseModel):
    """Query-parameter filter set for listing setups."""

    product_id: Optional[int] = None
    group_id: Optional[int] = None
    status: Optional[str] = None
    location: Optional[str] = None
    owner_id: Optional[int] = None
    search: Optional[str] = None

    @validator("status")
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:  # noqa: N805
        if value is not None and value not in SetupStatus.ALL:
            raise ValueError("status must be one of: {0}".format(", ".join(SetupStatus.ALL)))
        return value
