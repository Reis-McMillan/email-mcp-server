from starlette.responses import JSONResponse
from starlette.requests import Request

from ..config import config

async def get_prm(request: Request):
    return JSONResponse({
        'resource': config.MCP_URI,
        'authorization_servers': [config.AUTH_URL],
        'bearer_methods_supported': ['header'],
        'scopes_supported': ['mcp'],
        'resource_name': 'email-mcp-server'
    })