"""
Developer Logs service.

Provides a directory tree of the rotating Excel transaction logs (see
``app.utils.excel_log_rotator``) and a path-traversal-safe way to resolve a
relative path to an absolute file for download.
"""
import os
from typing import Any, Dict

from app.core.config import settings
from app.core.exceptions import AuthorizationError, NotFoundError


class DeveloperLogsService:
    """Builds a tree view of ``EXCEL_LOG_DIR`` and resolves safe download paths."""

    def __init__(self) -> None:
        self._root = os.path.abspath(settings.EXCEL_LOG_DIR)

    def build_tree(self) -> Dict[str, Any]:
        """Return a nested dict describing every Month_Year folder and its log files."""
        os.makedirs(self._root, exist_ok=True)
        return self._build_node(self._root, name="Logs")

    def _build_node(self, path: str, name: str) -> Dict[str, Any]:
        if os.path.isdir(path):
            children = []
            for entry in sorted(os.listdir(path)):
                children.append(self._build_node(os.path.join(path, entry), entry))
            return {"type": "folder", "name": name, "children": children}
        return {"type": "file", "name": name, "size_bytes": os.path.getsize(path), "relative_path": os.path.relpath(path, self._root)}

    def resolve_download_path(self, relative_path: str) -> str:
        """
        Resolve a relative path (as returned by ``build_tree``) to an
        absolute file path, rejecting any attempt to escape the log root.

        Raises:
            AuthorizationError: if the resolved path escapes ``EXCEL_LOG_DIR``.
            NotFoundError: if no such file exists.
        """
        candidate = os.path.abspath(os.path.join(self._root, relative_path))
        if not candidate.startswith(self._root + os.sep):
            raise AuthorizationError("Invalid log file path.")
        if not os.path.isfile(candidate):
            raise NotFoundError("Log file not found.")
        return candidate
