"""Pagination helper utilities shared by repositories and API routers."""
import math
from typing import Any, List, Tuple, TypeVar

from sqlalchemy.orm import Query

T = TypeVar("T")


def paginate_query(query: "Query[Any]", page: int, page_size: int) -> Tuple[List[Any], int]:
    """
    Apply LIMIT/OFFSET pagination to a SQLAlchemy query.

    Returns:
        A tuple of (items for the requested page, total matching row count).
    """
    total_items = query.order_by(None).count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total_items


def total_pages(total_items: int, page_size: int) -> int:
    """Compute the total number of pages for a given item count and page size."""
    if page_size <= 0:
        return 0
    return math.ceil(total_items / page_size)
