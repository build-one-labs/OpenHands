"""
Custom server that wraps the V1 agent server API and adds SPA static file serving.
"""
import os

from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except Exception:
            return await super().get_response('index.html', scope)


class SPAFallbackMiddleware:
    """ASGI middleware: tries the inner app first; on 404 falls back to SPA."""

    def __init__(self, app: ASGIApp, spa: ASGIApp):
        self.app = app
        self.spa = spa

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            # WebSocket and lifespan go straight to the API
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # API and known backend paths go to the API app
        if (
            path.startswith("/api/")
            or path.startswith("/sockets/")
            or path.startswith("/alive")
            or path.startswith("/health")
            or path.startswith("/server_info")
            or path.startswith("/docs")
            or path.startswith("/redoc")
            or path.startswith("/openapi.json")
            or path.startswith("/mcp")
        ):
            await self.app(scope, receive, send)
            return

        # Everything else: try API first, fall back to SPA
        # For efficiency, send non-API paths directly to SPA
        await self.spa(scope, receive, send)


def create_app():
    # Import the V1 agent server API
    os.environ.setdefault('STATIC_FILES_PATH', '')  # Disable built-in static serving
    from openhands.agent_server.api import api as agent_api

    static_dir = os.environ.get('FRONTEND_DIR', '/app/frontend/build')
    if os.path.isdir(static_dir):
        spa = SPAStaticFiles(directory=static_dir, html=True)
        return SPAFallbackMiddleware(agent_api, spa)
    else:
        return agent_api


app = create_app()
