"""Group service: business logic for Group CRUD."""
from typing import List, Optional, Tuple

from app.core.constants import AuditAction
from app.core.exceptions import ConflictError, NotFoundError
from app.models.group import Group
from app.models.user import User
from app.repositories.interfaces.i_group_repository import IGroupRepository
from app.schemas.group import GroupCreateRequest, GroupUpdateRequest
from app.services.audit_service import AuditService


class GroupService:
    """Business logic for Group CRUD."""

    def __init__(self, group_repository: IGroupRepository, audit_service: AuditService) -> None:
        self._group_repository = group_repository
        self._audit_service = audit_service

    def get_by_id(self, group_id: int) -> Group:
        group = self._group_repository.get_by_id(group_id)
        if group is None:
            raise NotFoundError("Group with id {0} was not found.".format(group_id))
        return group

    def list(self, page: int, page_size: int, search: Optional[str] = None) -> Tuple[List[Group], int]:
        return self._group_repository.list(page, page_size, search)

    def create(self, payload: GroupCreateRequest, acting_user: User) -> Group:
        if self._group_repository.get_by_name(payload.name) is not None:
            raise ConflictError("A group named '{0}' already exists.".format(payload.name))
        group = Group(name=payload.name, description=payload.description)
        created = self._group_repository.create(group)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="Group",
            entity_id=created.id,
            new_value={"name": created.name},
        )
        return created

    def update(self, group_id: int, payload: GroupUpdateRequest, acting_user: User) -> Group:
        group = self.get_by_id(group_id)
        old_value = {"name": group.name, "description": group.description}

        if payload.name is not None and payload.name != group.name:
            if self._group_repository.get_by_name(payload.name) is not None:
                raise ConflictError("A group named '{0}' already exists.".format(payload.name))
            group.name = payload.name
        if payload.description is not None:
            group.description = payload.description

        updated = self._group_repository.update(group)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="Group",
            entity_id=updated.id,
            old_value=old_value,
            new_value={"name": updated.name, "description": updated.description},
        )
        return updated

    def delete(self, group_id: int, acting_user: User) -> None:
        group = self.get_by_id(group_id)
        if self._group_repository.has_members_or_setups(group_id):
            raise ConflictError(
                "Group '{0}' cannot be deleted while users or setups are assigned to it.".format(group.name)
            )
        self._group_repository.delete(group_id)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.DELETE,
            entity_type="Group",
            entity_id=group_id,
        )
