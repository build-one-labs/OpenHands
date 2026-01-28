"""
Patch the agent server to serve the frontend SPA at root instead of /static/.
This is applied at container startup before the server starts.
"""
import importlib
import os
from pathlib import Path

AGENT_SERVER_API_PATH = None

def find_api_module():
    """Find the installed agent_server api.py path."""
    mod = importlib.import_module('openhands.agent_server.api')
    return mod.__file__

def patch():
    api_path = find_api_module()
    if not api_path:
        print("PATCH: Could not find agent_server api.py")
        return

    with open(api_path, 'r') as f:
        content = f.read()

    # Check if already patched
    if 'SPAStaticFiles' in content:
        print("PATCH: Already patched")
        return

    # Replace the _setup_static_files function to mount SPA at root
    old = '''def _setup_static_files(app: FastAPI, config: Config) -> None:
    """Set up static file serving and root redirect if configured.

    Args:
        app: FastAPI application instance.
        config: Configuration object containing static files settings.
    """
    # Only proceed if static files are configured and directory exists
    if not (
        config.static_files_path
        and config.static_files_path.exists()
        and config.static_files_path.is_dir()
    ):
        # Map the root path to server info if there are no static files
        app.get("/")(get_server_info)
        return

    # Mount static files directory
    app.mount(
        "/static",
        StaticFiles(directory=str(config.static_files_path)),
        name="static",
    )

    # Add root redirect to static files
    @app.get("/", tags=["Server Details"])
    async def root_redirect():
        """Redirect root endpoint to static files directory."""
        # Check if index.html exists in the static directory
        # We know static_files_path is not None here due to the outer condition
        assert config.static_files_path is not None
        index_path = config.static_files_path / "index.html"
        if index_path.exists():
            return RedirectResponse(url="/static/index.html", status_code=302)
        else:
            return RedirectResponse(url="/static/", status_code=302)'''

    new = '''def _setup_static_files(app: FastAPI, config: Config) -> None:
    """Set up static file serving as SPA at root."""
    # Only proceed if static files are configured and directory exists
    if not (
        config.static_files_path
        and config.static_files_path.exists()
        and config.static_files_path.is_dir()
    ):
        # Map the root path to server info if there are no static files
        app.get("/")(get_server_info)
        return

    class SPAStaticFiles(StaticFiles):
        async def get_response(self, path: str, scope) -> Response:
            try:
                return await super().get_response(path, scope)
            except Exception:
                return await super().get_response('index.html', scope)

    from starlette.responses import Response
    app.mount(
        '/',
        SPAStaticFiles(directory=str(config.static_files_path), html=True),
        name='spa',
    )'''

    if old in content:
        content = content.replace(old, new)
        with open(api_path, 'w') as f:
            f.write(content)
        print("PATCH: Successfully patched _setup_static_files for SPA serving")
    else:
        print("PATCH: Could not find exact match for _setup_static_files")
        print("PATCH: Attempting to find the function...")
        if '_setup_static_files' in content:
            print("PATCH: Function exists but signature differs - manual review needed")
        else:
            print("PATCH: Function not found at all")

if __name__ == '__main__':
    patch()
