"""
Role lookup service.

A small, focused helper (kept separate from UserService to avoid a
circular/oversized dependency graph) that resolves role names to Role
entities and checks whether a role carries a given permission code.
"""
from app.core.exceptions import NotFoundError
from app.models.role import Role
from app.repositories.interfaces.i_role_repository import IRoleRepository


class RoleLookupService:
    """Resolves role names to entities and checks permission membership."""

    def __init__(self, role_repository: IRoleRepository) -> None:
        self._role_repository = role_repository

    def get_role_by_name(self, name: str) -> Role:
        """
        Fetch a Role by its canonical name.

        Raises:
            NotFoundError: if no such role has been seeded into the database.
        """
        role = self._role_repository.get_by_name(name)
        if role is None:
            raise NotFoundError("Role '{0}' is not configured.".format(name))
        return role

    def role_has_permission(self, role: Role, permission_code: str) -> bool:
        """Return True if the given role carries the given permission code."""
        return any(permission.code == permission_code for permission in role.permissions)
