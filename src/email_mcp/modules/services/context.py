from contextvars import ContextVar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from email_mcp.middleware.authentication import User

current_user: ContextVar["User"] = ContextVar("current_user")
