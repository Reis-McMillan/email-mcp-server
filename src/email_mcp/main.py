import logging
from contextlib import asynccontextmanager

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.datastructures import State
from starlette.routing import Mount, Route
from starlette.middleware import Middleware
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.cors import CORSMiddleware

from email_mcp.config import config
from email_mcp.db.auth_cache import AuthCache
from email_mcp.db.authorization import Authorization
from email_mcp.middleware.authentication import BearerToken, on_authenticated_error
from email_mcp.modules.services.service import Service
from email_mcp.modules.tokens import VerysClient
from email_mcp.routes.auth import initialize, callback
from email_mcp.routes.discovery import get_prm
from email_mcp.routes.heartbeat import heartbeat
from email_mcp.routes.mcp import create_server, handle_streamable_http


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    app.state.db = State()
    app.state.db.auth_cache = AuthCache()
    app.state.db.authorization = Authorization()

    await app.state.db.auth_cache.ensure_indexes()
    await app.state.db.authorization.ensure_indexes()

    app.state.verys_client = VerysClient(app.state.db.auth_cache)

    Service.set_auth_cache(app.state.db.auth_cache)
    Service.set_verys_client(app.state.verys_client)

    server = create_server()
    app.state.session_manager = StreamableHTTPSessionManager(app=server)
    async with app.state.session_manager.run():
        yield

routes = [
    Route('/auth/initialize', initialize),
    Route('/auth/callback', callback),
    Route('/heartbeat', heartbeat),
    Route('/.well-known/oauth-protected-resource', get_prm),
    Mount('/mcp', app=handle_streamable_http),
]

app = Starlette(
    lifespan=lifespan,
    routes=routes,
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=config.ALLOWED_ORIGINS,
            allow_credentials=True,
            allow_methods=['GET', 'PUT', 'POST', 'DELETE', 'OPTIONS'],
            allow_headers=['Authorization', 'Content-Type', 'Mcp-Session-Id', 'Last-Event-ID'],
            expose_headers=['Mcp-Session-Id']
        ),
        Middleware(
            AuthenticationMiddleware,
            backend=BearerToken(),
            on_error=on_authenticated_error
        )
    ]
)