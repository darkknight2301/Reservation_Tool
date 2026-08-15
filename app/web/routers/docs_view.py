"""
Serves the pre-built Sphinx documentation site (see docs/, built via
``sphinx-build -b html docs docs/_build/html``) to authenticated users.

This intentionally serves static, already-generated HTML files rather than
rendering Jinja templates: each Sphinx page is a complete standalone HTML
document (with its own navigation/search from the Sphinx theme), so it is
served as-is rather than embedded inside the app's own base.html layout.

Only files inside ``docs/_build/html`` are ever reachable -- every request
path is resolved and checked against that directory before anything is
read from disk, so this cannot be used to reach any other repository file
(source code, .git, .env, etc.).
"""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.models.user import User
from app.web.deps import base_context, get_current_web_user, templates

router = APIRouter(tags=["Web - Documentation"])

_DOCS_ROOT = Path("docs/_build/html").resolve()

_MEDIA_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css",
    ".js": "application/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".gif": "image/gif",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain",
    ".xml": "application/xml",
}


def _resolve_doc_file(relative_path: str) -> Path:
    """
    Resolve ``relative_path`` underneath ``_DOCS_ROOT``, rejecting anything
    that would escape it (``..`` traversal, absolute paths, symlink tricks).
    Raises 404 for any path outside the docs directory, and for any path
    that isn't a real file (so no directory listings either).
    """
    candidate = (_DOCS_ROOT / relative_path).resolve()
    if candidate != _DOCS_ROOT and _DOCS_ROOT not in candidate.parents:
        raise HTTPException(status_code=404, detail="Documentation page not found.")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="Documentation page not found.")
    return candidate


@router.get("/documentation")
def documentation_index(request: Request, current_user: User = Depends(get_current_web_user)):
    """Entry point for the Documentation nav item: redirect into the built Sphinx site."""
    if not (_DOCS_ROOT / "index.html").is_file():
        return templates.TemplateResponse(
            "docs/_not_built.html", base_context(request, current_user), status_code=503
        )
    return RedirectResponse("/documentation/index.html")


@router.get("/documentation/{path:path}")
def documentation_asset(request: Request, path: str, current_user: User = Depends(get_current_web_user)):
    """Serve one file from the pre-built Sphinx HTML site (read-only)."""
    if not path or path.endswith("/"):
        path = path + "index.html"
    if not _DOCS_ROOT.is_dir():
        return templates.TemplateResponse(
            "docs/_not_built.html", base_context(request, current_user), status_code=503
        )
    file_path = _resolve_doc_file(path)
    media_type = _MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=str(file_path), media_type=media_type)
