from starlette.requests import Request
from starlette.responses import JSONResponse


async def heartbeat(request: Request):
    return JSONResponse({"ok": True})
