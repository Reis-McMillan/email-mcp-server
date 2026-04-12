from abc import ABC, abstractmethod
from datetime import datetime, timezone

from email_mcp.db.auth_cache import AuthCache
from email_mcp.modules.tokens import get_external_token
from email_mcp.utils.external_tokens import find_token


class Service(ABC):
    provider_id: str
    auth_cache: AuthCache
    _registry: dict[str, type['Service']] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, 'provider_id') and isinstance(cls.provider_id, str):
            Service._registry[cls.provider_id] = cls

    def __init__(self, user_id: int, subject: str):
        self.user_id = user_id
        self.subject = subject

    @classmethod
    def for_provider(cls, provider_id: str) -> type['Service'] | None:
        return cls._registry.get(provider_id)

    @classmethod
    def set_auth_cache(cls, auth_cache: AuthCache):
        cls.auth_cache = auth_cache

    async def get_token(self) -> str:
        auth = await self.auth_cache.get(self.user_id)
        if not auth:
            raise ValueError(f"No cached auth for user {self.user_id}")

        token = find_token(
            auth.get('external_tokens') or [],
            self.provider_id, self.subject
        )

        if token:
            expires_at = token.get('expires_at')
            if expires_at:
                exp_dt = datetime.fromisoformat(expires_at)
                if exp_dt > datetime.now(timezone.utc):
                    return token['access_token']
            else:
                return token['access_token']

        refreshed = await get_external_token(
            self.user_id, self.auth_cache, self.provider_id, self.subject
        )
        return refreshed['access_token']

    @abstractmethod
    async def send_email(self, recipient_id: str, subject: str, message: str) -> dict:
        """Creates and sends an email message."""
        ...

    @abstractmethod
    async def open_email(self, email_id: str) -> str:
        """Opens email in browser given ID."""
        ...

    @abstractmethod
    async def get_unread_emails(self) -> list[dict[str, str]] | str:
        """Retrieves unread messages from mailbox."""
        ...

    @abstractmethod
    async def read_email(self, email_id: str) -> dict[str, str] | str:
        """Retrieves email contents including to, from, subject, and contents."""
        ...

    @abstractmethod
    async def trash_email(self, email_id: str) -> str:
        """Moves email to trash given ID."""
        ...

    @abstractmethod
    async def mark_email_as_read(self, email_id: str) -> str:
        """Marks email as read given ID."""
        ...
