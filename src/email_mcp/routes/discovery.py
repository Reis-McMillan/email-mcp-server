from starlette.responses import JSONResponse
from starlette.routing import Route

from ..config import config

async def get_prm_doc(request):
    return JSONResponse({
        'resource': f'{config.HOST}/mcp',
        'authorization_servers': [config.AUTH_URL],
        'bearer_methods_supported': ['header'],
        'scopes_supported': ['mcp'],
        'resource_name': 'email-mcp-server'
    })

dicovery_routes = [Route('/oauth-res    ource-metadata', get_prm_doc)]