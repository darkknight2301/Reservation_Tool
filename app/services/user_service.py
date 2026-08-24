"""
User service.

Handles user CRUD (by admins/leads), the registration approval workflow,
and profile updates. Record-level RBAC nuance (e.g. "a LEAD may only
approve/manage users in their own Group") is enforced here, since route-level
permission checks can only express "does this role have this permission",
not "for which records".
"""
from datetime import datetime
from typing import List, Optional, Tuple

from app.core.constants import AuditAction, RoleName, UserStatus
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import User
from app.repositories.interfaces.i_user_repository import IUserRepository
from app.schemas.user import UserApprovalRequest, UserCreateRequest, UserFilter, UserUpdateRequest
from app.services.audit_service import AuditService
from app.services.role_lookup_service import RoleLookupService


def _scope_role_names(acting_user: User) -> Optional[List[str]]:
    """
    LEAD-level approvers may only manage BOT/USER accounts within their own
    group; MANAGER and OWNER manage globally. Returns None for
    unrestricted (global) scope.
    """
    if acting_user.role.name in (RoleName.OWNER, RoleName.MANAGER):
        return None
    return [RoleName.BOT, RoleName.USER]


class UserService:
    """Business logic for user management and the approval workflow."""

    def __init__(
        self,
        user_repository: IUserRepository,
        role_lookup_service: RoleLookupService,
        audit_service: AuditService,
    ) -> None:
        self._user_repository = user_repository
        self._role_lookup_service = role_lookup_service
        self._audit_service = audit_service

    def get_by_id(self, user_id: int) -> User:
        """Fetch a user by id, raising NotFoundError if absent."""
        user = self._user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User with id {0} was not found.".format(user_id))
        return user

    def list(self, filters: UserFilter, page: int, page_size: int) -> Tuple[List[User], int]:
        """List users matching the given filters, paginated."""
        return self._user_repository.list(filters, page, page_size)

    def create(self, payload: UserCreateRequest, acting_user: User) -> User:
        """Directly create an already-approved user (admin/lead action)."""
        if self._user_repository.get_by_username(payload.username) is not None:
            raise ConflictError("Username is already taken.", details={"field": "username"})
        if self._user_repository.get_by_email(payload.email) is not None:
            raise ConflictError("Email is already registered.", details={"field": "email"})

        role = self._role_lookup_service.get_role_by_name(payload.role_name)
        primary_group_id = payload.group_id
        if primary_group_id is None and payload.group_ids:
            primary_group_id = payload.group_ids[0]
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            role_id=role.id,
            group_id=primary_group_id,
            status=UserStatus.APPROVED,
            is_active=True,
            approved_by_id=acting_user.id,
            approved_at=datetime.utcnow(),
        )
        created_user = self._user_repository.create(user)
        if payload.group_ids is not None:
            self._user_repository.set_groups(created_user, payload.group_ids)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.CREATE,
            entity_type="User",
            entity_id=created_user.id,
            new_value={"username": created_user.username, "role": role.name},
        )
        return created_user

    def update(self, user_id: int, payload: UserUpdateRequest, acting_user: User) -> User:
        """Update a user's profile, role, group, or active flag."""
        user = self.get_by_id(user_id)
        old_value = {"full_name": user.full_name, "role": user.role.name, "is_active": user.is_active}

        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.role_name is not None:
            role = self._role_lookup_service.get_role_by_name(payload.role_name)
            user.role_id = role.id
        if payload.group_id is not None:
            user.group_id = payload.group_id
        elif payload.group_ids:
            user.group_id = payload.group_ids[0]
        if payload.is_active is not None:
            user.is_active = payload.is_active
            if payload.is_active and user.status == UserStatus.DISABLED:
                # Re-enabling a disabled account must also lift the DISABLED
                # status -- otherwise login stays blocked by
                # AuthService.authenticate()'s status check even though
                # is_active looks correct in the admin UI.
                user.status = UserStatus.APPROVED

        updated_user = self._user_repository.update(user)
        if payload.group_ids is not None:
            self._user_repository.set_groups(updated_user, payload.group_ids)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=updated_user.id,
            old_value=old_value,
            new_value={"full_name": updated_user.full_name, "role": updated_user.role.name, "is_active": updated_user.is_active},
        )
        return updated_user

    def delete(self, user_id: int, acting_user: User) -> None:
        """Soft-delete a user by deactivating the account."""
        user = self.get_by_id(user_id)
        user.is_active = False
        user.status = UserStatus.DISABLED
        self._user_repository.update(user)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.DELETE,
            entity_type="User",
            entity_id=user.id,
        )

    def reactivate(self, user_id: int, acting_user: User) -> User:
        """
        Reactivate a DISABLED or REJECTED user: restores ``is_active`` and
        resets ``status`` back to APPROVED so the account can log in again.
        """
        user = self.get_by_id(user_id)
        old_value = {"status": user.status, "is_active": user.is_active}

        user.is_active = True
        user.status = UserStatus.APPROVED

        updated_user = self._user_repository.update(user)
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.UPDATE,
            entity_type="User",
            entity_id=updated_user.id,
            old_value=old_value,
            new_value={"status": updated_user.status, "is_active": updated_user.is_active},
        )
        return updated_user

    def hard_delete(self, user_id: int, acting_user: User) -> None:
        """
        Permanently remove a user record.

        Raises:
            ConflictError: if the user still has dependent records
                (reservations, swap requests, announcements, export logs,
                etc.) that reference them -- use ``delete()`` (deactivate)
                instead in that case.
        """
        user = self.get_by_id(user_id)
        username = user.username
        deleted = self._user_repository.delete(user_id)
        if not deleted:
            raise ConflictError(
                "User '{0}' cannot be permanently deleted because other records (reservations, swaps, "
                "announcements, or exports) still reference them. Deactivate the account instead.".format(username)
            )
        self._audit_service.record(
            user_id=acting_user.id,
            action=AuditAction.DELETE,
            entity_type="User",
            entity_id=user_id,
            old_value={"username": username},
        )

    def process_approval(self, user_id: int, payload: UserApprovalRequest, acting_user: User) -> User:
        """
        Approve or reject a pending registration.

        Raises:
            AuthorizationError: if a LEAD attempts to approve a user outside
                their own group.
            ConflictError: if the target user is not in PENDING status.
        """
        user = self.get_by_id(user_id)
        if user.status != UserStatus.PENDING:
            raise ConflictError("User {0} is not pending approval.".format(user_id))

        allowed_role_names = _scope_role_names(acting_user)
        if allowed_role_names is not None and (
            user.group_id != acting_user.group_id or user.group_id is None
        ):
            raise AuthorizationError("You may only approve users within your own group.")

        if payload.approve:
            role_name = payload.role_name or RoleName.BOT
            role = self._role_lookup_service.get_role_by_name(role_name)
            user.status = UserStatus.APPROVED
            user.role_id = role.id
            user.approved_by_id = acting_user.id
            user.approved_at = datetime.utcnow()
            action = AuditAction.APPROVE
        else:
            user.status = UserStatus.REJECTED
            user.is_active = False
            action = AuditAction.REJECT

        updated_user = self._user_repository.update(user)
        self._audit_service.record(
            user_id=acting_user.id,
            action=action,
            entity_type="User",
            entity_id=updated_user.id,
            new_value={"status": updated_user.status, "rejection_reason": payload.rejection_reason},
        )
        return updated_user
