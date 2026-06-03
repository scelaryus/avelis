"""Dependency injection — uses real JWT auth from core.rbac."""
from fastapi import Depends, Query
from app.core.rbac import get_current_user, CurrentUser, require_role
from app.db import get_db

# Re-export so existing imports work
__all__ = ["get_current_user", "CurrentUser", "require_role", "get_db", "Pagination"]

class Pagination:
    def __init__(self, limit: int = Query(50, le=200), offset: int = Query(0, ge=0)):
        self.limit = limit
        self.offset = offset
