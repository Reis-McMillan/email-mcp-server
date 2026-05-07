import logging
from datetime import datetime

import httpx
import jwt

import email_mcp.config.config as config
from email_mcp.db.auth_cache import AuthCache


def _parse_expires_at(token: dict) -> dict:
    raw = token.get('expires_at')
    if isinstance(raw, str):
        token['expires_at'] = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    return token

logger = logging.getLogger(__name__)


class ReauthRequired(Exception):
    """Raised when an external provider requires the end user to reauthorize."""
    def __init__(self, provider_id: str, moneypenny_url: str):
        super().__init__(f"Reauthorization required for provider {provider_id!r}")
        self.provider_id = provider_id
        self.moneypenny_url = moneypenny_url


class VerysClient:
    def __init__(self, auth_cache: AuthCache):
        self.auth_cache: AuthCache = auth_cache
        self.token_url = f"{config.AUTH_URL}/token"
        self.federation_url = f"{config.AUTH_URL}/federation/"
        self.moneypenny_actions_url = f"{config.MONEYPENNY_URL}/actions"

    @staticmethod
    def find_token(tokens: list[dict], token_id: int) -> dict | None:
        for t in tokens:
            if t['token_id'] == token_id:
                return t
        return None
    
    def token_expired(self, token: str | bytes) -> bool:
        try:
            jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True}
            )
            return False
        except jwt.ExpiredSignatureError:
            return True
    
    async def refresh_access_token(
        self,
        auth: dict
    ) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": config.CLIENT_ID,
                    "client_secret": config.CLIENT_SECRET,
                    "refresh_token": auth['refresh_token']
                }
            )

        if not response.is_success:
            raise RuntimeError(f"Token refresh failed: {response.status_code} {response.text}")

        data = response.json()
        auth['access_token'] = data['access_token']
        auth['refresh_token'] = data['refresh_token']

        await self.auth_cache.upsert(auth)

        return auth
    
    async def check_token(
        self,
        auth: dict
    ) -> dict:
        if self.token_expired(auth['access_token']):
            logger.info("Access token expired for %s, refreshing", auth['email'])
            auth = await self.refresh_access_token(auth)

        return auth
    
    async def check_moneypenny_token(self, auth: dict) -> dict:
        moneypenny_token = auth.get('moneypenny_token')
        if not moneypenny_token or self.token_expired(moneypenny_token):
            logger.info("Moneypenny token expired or missing for %s, exchanging", auth['email'])
            auth = await self.moneypenny_token_exchange(auth)
        return auth

    async def moneypenny_token_exchange(
        self,
        auth: dict
    ) -> dict:
        auth = await self.check_token(auth)
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
                    "client_id": config.CLIENT_ID,
                    "client_secret": config.CLIENT_SECRET,
                    "subject_token": auth['access_token'],
                    "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
                    "audience": config.MONEYPENNY_CLIENT_ID,
                }
            )

        if not response.is_success:
            logger.warning(
                f"Moneypenny token exchange failed: {response.status_code} {response.text}"
            )
            return auth

        data = response.json()
        auth['moneypenny_token'] = data['access_token']
        
        await self.auth_cache.upsert(auth)

        return auth
    
    @staticmethod
    def _insert_external_tokens(
        auth: dict,
        ext_token: dict | list[dict]
    ):
        # if ext_tokens is list, overwrite
        if isinstance(ext_token, list):
            auth['external_tokens'] = ext_token
            return auth
        
        elif isinstance(ext_token, dict):
            if auth['external_tokens'] is None:
                auth['external_tokens'] = [ext_token]
                return auth
            token_ids: list = list(map(lambda t: t['token_id'], auth['external_tokens']))
            try:
                idx = token_ids.index(ext_token['token_id'])
                auth['external_tokens'][idx] = ext_token
            except ValueError:
                auth['external_tokens'].append(ext_token)
            
            return auth
        
    async def get_external_tokens(
        self,
        auth: dict,
        token_id: int | None = None
    ) -> dict:
        auth = await self.check_token(auth)

        async with httpx.AsyncClient() as client:
            if token_id:
                federation_url = f"{self.federation_url}{token_id}"
            else:
                federation_url = f"{self.federation_url}tokens"
            response = await client.get(
                federation_url,
                headers={
                    "Authorization": f"Bearer {auth['access_token']}"
                },
            )

        if not response.is_success:
            error_payload = {}
            try:
                error_payload = response.json()
            except Exception:
                pass

            needs_reauth = (
                token_id is not None
                and response.status_code == 401
                and error_payload.get('error') == 'reauthorization_required'
            )

            if needs_reauth:
                token = self.find_token(auth.get('external_tokens') or [], token_id)
                moneypenny_token = auth.get('moneypenny_token')
                if moneypenny_token:
                    try:
                        async with httpx.AsyncClient() as client:
                            mp_response = await client.post(
                                self.moneypenny_actions_url,
                                headers={
                                    "Authorization": f"Bearer {moneypenny_token}",
                                    "Content-Type": "application/json",
                                },
                                json={"provider_id": token['provider_id']},
                            )
                        if mp_response.status_code != 201:
                            logger.warning(
                                "Moneypenny action create returned %s for provider %s: %s",
                                mp_response.status_code, token['provider_id'], mp_response.text,
                            )
                    except httpx.HTTPError as e:
                        logger.warning(
                            "Moneypenny action create network error for provider %s: %s",
                            token['provider_id'], e,
                        )
                else:
                    logger.warning(
                        "No moneypenny_token in auth; cannot create action for provider %s",
                        token['provider_id'],
                    )

                raise ReauthRequired(
                    provider_id=token['provider_id'],
                    moneypenny_url=config.MONEYPENNY_URL,
                )

            raise RuntimeError(f"External token fetch failed: {response.status_code} {response.text}")

        data: list[dict] | dict = response.json()
        if isinstance(data, list):
            data = [_parse_expires_at(t) for t in data]
        elif isinstance(data, dict):
            data = _parse_expires_at(data)
        auth = self._insert_external_tokens(auth, data)
        await self.auth_cache.upsert(auth)

        return auth
