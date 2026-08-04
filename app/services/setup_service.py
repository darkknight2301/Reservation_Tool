"""Setup service: business logic for Setup CRUD and status transitions."""
from typing import List, Optional, Tuple

from app.core.constants import AuditAction, SetupStatus
from app.core.exceptions import ConflictError, InvalidStateTransitionError, NotFoundError
from app.models.setup import Setup
from app.models.user import User
from app.repositories.interfaces.i_setup_repository import ISetupRepository
from app.schemas.setup import SetupCreateRequest, SetupFilter, SetupUpdateRequest
from app.services.audit_service import AuditService

# Explicit allow-list of legal status transitions. Any transition not listed
# here is rejected, keeping setup lifecycle changes deliberate and auditable.
_ALLOWED_STATUS_TRANSITIONS = {
    SetupStatus.AVAILABLE: {SetupStatus.RESERVED, SetupStatus.MAINTENANCE, SetupStatus.RETIRED},
    SetupStatus.RESERVED: {SetupStatus.AVAILABLE, SetupStatus.MAINTENANCE},
    SetupStatus.MAINTENANCE: {SetupStatus.AVAILABLE, SetupStatus.RETIRED},
    SetupStatus.RETIRED: set(),
}


class SetupService:
    """Business logic for Setup CRUD and status lifecycle management."""

    def __init__(self, setup_repository: ISetupRepository, audit_service: AuditService) -> None:
        self._setup_repository = setup_repository
        self._audit_service = audit_service

    def get_by_id(self, setup_id: int) -> Setup:
        setup = self._setup_repository.get_by_id(setup_id)
        if setup is None:
            raise NotFoundError("Setup with id {0} was not found.".format(setup_id))
        return setup

    def list(self, filters: SetupFilter, page: int, page_size: int) -> Tuple[List[Setup], int]:
        return self._setup_repository.list(filters, page, page_size)

    def list_all(self, filters: SetupFilter) -> List[Setup]:
        return self._setup_repository.list_all(filters)

    def create(self, payload: SetupCreateRequest, acting_user: User) -> Setup:
        existing = self._setup_repository.get_by_ip_or_hostname(payload.ip_address, payload.hostname)
        if existing is not None:
            conflicting_field = "ip_address" if existing.ip_address == payload.ip_address else "hostname"
            raise ConflictError(
                "A setup with this {0} already exists.".format(conflicting_field),
                details={"field": conflicting_field},
            )

        setup = Setup(**payload.dict(), status=SetupStatus.AVAILABLE)
        created = self._setup_repository.create(setup)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="Setup",
            entity_id=created.id,
            new_value={"hostname": created.hostname, "ip_address": created.ip_address},
        )
        return created

    def update(self, setup_id: int, payload: SetupUpdateRequest, acting_user: User) -> Setup:
        setup = self.get_by_id(setup_id)
        old_value = {"hostname": setup.hostname, "ip_address": setup.ip_address, "status": setup.status}

        update_data = payload.dict(exclude_unset=True, exclude={"status"})
        if "ip_address" in update_data or "hostname" in update_data:
            candidate_ip = update_data.get("ip_address", setup.ip_address)
            candidate_hostname = update_data.get("hostname", setup.hostname)
            existing = self._setup_repository.get_by_ip_or_hostname(candidate_ip, candidate_hostname)
            if existing is not None and existing.id != setup_id:
                conflicting_field = "ip_address" if existing.ip_address == candidate_ip else "hostname"
                raise ConflictError(
                    "A setup with this {0} already exists.".format(conflicting_field),
                    details={"field": conflicting_field},
                )

        for field_name, field_value in update_data.items():
            setattr(setup, field_name, field_value)

        if payload.status is not None and payload.status != setup.status:
            self._transition_status(setup, payload.status)

        updated = self._setup_repository.update(setup)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="Setup",
            entity_id=updated.id,
            old_value=old_value,
            new_value={"hostname": updated.hostname, "ip_address": updated.ip_address, "status": updated.status},
        )
        return updated

    def _transition_status(self, setup: Setup, new_status: str) -> None:
        """Validate and apply a status transition per the allowed state machine."""
        allowed_targets = _ALLOWED_STATUS_TRANSITIONS.get(setup.status, set())
        if new_status not in allowed_targets:
            raise InvalidStateTransitionError(
                "Setup cannot transition from {0} to {1}.".format(setup.status, new_status)
            )
        setup.status = new_status

    def delete(self, setup_id: int, acting_user: User) -> None:
        setup = self.get_by_id(setup_id)
        if setup.status == SetupStatus.RESERVED:
            raise ConflictError("Setup cannot be deleted while it is reserved.")
        self._setup_repository.delete(setup_id)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.DELETE,
            entity_type="Setup",
            entity_id=setup_id,
        )
