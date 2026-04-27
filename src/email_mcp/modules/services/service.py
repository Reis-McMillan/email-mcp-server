from abc import ABC, abstractmethod
from datetime import datetime, timezone

from email_mcp.db.auth_cache import AuthCache
from email_mcp.modules.tokens import VerysClient


class Service(ABC):
    provider_id: str
    auth_cache: AuthCache
    verys_client: VerysClient
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

    @classmethod
    def set_verys_client(cls, client: VerysClient):
        cls.verys_client = client

    async def get_token(self) -> dict:
        auth = await self.auth_cache.get(self.user_id)
        if not auth:
            raise ValueError(f"No cached auth for user {self.user_id}")

        token = self._find_local_token(auth.get('external_tokens') or [])
        if token and not self._token_expired(token):
            return token

        auth = await self.verys_client.get_external_tokens(
            auth,
            token_id=token['token_id'] if token else None,
        )
        token = self._find_local_token(auth.get('external_tokens') or [])
        if not token:
            raise ValueError(
                f"No token for provider={self.provider_id} subject={self.subject}"
            )
        return token

    def _find_local_token(self, tokens: list[dict]) -> dict | None:
        for t in tokens:
            if (t.get('provider_id') == self.provider_id
                    and t.get('subject') == self.subject):
                return t
        return None

    @staticmethod
    def _token_expired(token: dict) -> bool:
        exp = token.get('expires_at')
        if not exp:
            return False
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp)
        return exp <= datetime.now(timezone.utc)

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
