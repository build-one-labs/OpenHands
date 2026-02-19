"""MCP SSE reverse proxy that forwards MCP protocol traffic to per-conversation sandboxes.

Each conversation's sandbox exposes an MCP endpoint at /mcp/sse (SSE transport).
External MCP clients (Claude Desktop, ChatGPT, etc.) can't reach sandbox containers
directly. This proxy accepts MCP protocol requests at a single deployment endpoint
and forwards them to the correct sandbox.

Two-phase MCP SSE protocol:
1. GET /mcp-proxy/{conversation_id}/sse — SSE stream with an `endpoint` event
2. POST /mcp-proxy/{conversation_id}/messages/ — JSON-RPC messages

The proxy rewrites the `endpoint` event URL so the client POSTs back through the proxy.
"""

import logging
import re
from uuid import UUID

import httpx
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from openhands.app_server.app_conversation.app_conversation_info_service import (
    AppConversationInfoService,
)
from openhands.app_server.sandbox.sandbox_models import AGENT_SERVER, SandboxStatus
from openhands.app_server.sandbox.sandbox_service import SandboxService
from openhands.server.user_auth import get_user_id

_logger = logging.getLogger(__name__)

router = APIRouter()

# Pattern to match the endpoint URL in SSE data lines.
# The sandbox sends: data: /mcp/messages/?session_id=...
# We rewrite to: data: /mcp-proxy/{conversation_id}/messages/?session_id=...
_ENDPOINT_RE = re.compile(r'^data:\s*/mcp/messages/(.*)$')


def _rewrite_endpoint_url(line: str, conversation_id: str) -> str:
    """Rewrite sandbox MCP endpoint URLs to route through the proxy."""
    match = _ENDPOINT_RE.match(line)
    if match:
        rest = match.group(1)
        return f'data: /mcp-proxy/{conversation_id}/messages/{rest}'
    return line


def _forward_headers(request: Request) -> dict[str, str]:
    """Filter request headers for forwarding, removing hop-by-hop headers."""
    headers = dict(request.headers)
    for header in ('host', 'transfer-encoding', 'connection', 'upgrade'):
        headers.pop(header, None)
    return headers


async def _resolve_sandbox_mcp_url(
    conversation_id: str, request: Request
) -> str | None:
    """Resolve a conversation_id to the sandbox's internal MCP base URL.

    Reuses the same resolution pattern as http_proxy_router.py:
    UUID parse → AppConversationInfoService → SandboxService → AGENT_SERVER internal URL.
    """
    from openhands.app_server.config import (
        get_app_conversation_info_service,
        get_sandbox_service,
    )

    try:
        conv_uuid = UUID(hex=conversation_id)
    except ValueError:
        _logger.warning(f'MCP proxy: invalid conversation_id format: {conversation_id}')
        return None

    state = request.state
    try:
        async with (
            get_app_conversation_info_service(state, request) as info_service,
            get_sandbox_service(state, request) as sandbox_service,
        ):
            return await _resolve_upstream_base_url(
                info_service, sandbox_service, conversation_id, conv_uuid
            )
    except Exception as exc:
        _logger.error(
            f'MCP proxy: failed to resolve upstream for {conversation_id}: {exc}'
        )
        return None


async def _resolve_upstream_base_url(
    info_service: AppConversationInfoService,
    sandbox_service: SandboxService,
    conversation_id: str,
    conv_uuid: UUID,
) -> str | None:
    """Resolve the upstream HTTP base URL for a conversation's sandbox."""
    info = await info_service.get_app_conversation_info(conv_uuid)
    if info is None:
        _logger.warning(f'MCP proxy: conversation not found: {conversation_id}')
        return None

    sandbox = await sandbox_service.get_sandbox(info.sandbox_id)
    if sandbox is None:
        _logger.warning(f'MCP proxy: sandbox not found: {info.sandbox_id}')
        return None

    # Record activity for idle-timeout tracking
    from openhands.app_server.idle_timeout_manager import get_idle_timeout_manager

    manager = get_idle_timeout_manager()
    if manager:
        manager.touch(info.sandbox_id)

    if sandbox.status != SandboxStatus.RUNNING:
        _logger.warning(
            f'MCP proxy: sandbox not running: {info.sandbox_id} ({sandbox.status})'
        )
        return None

    if not sandbox.exposed_urls:
        _logger.warning(f'MCP proxy: no exposed URLs for sandbox: {info.sandbox_id}')
        return None

    agent_server_eu = next(
        (eu for eu in sandbox.exposed_urls if eu.name == AGENT_SERVER),
        None,
    )
    if not agent_server_eu or not agent_server_eu.internal_url:
        _logger.warning(f'MCP proxy: no internal URL for sandbox: {info.sandbox_id}')
        return None

    return agent_server_eu.internal_url


@router.get('/mcp-proxy/{conversation_id}/sse')
async def mcp_sse_proxy(request: Request, conversation_id: str):
    """Proxy the MCP SSE stream from a conversation's sandbox.

    Opens a streaming GET to the sandbox's /mcp/sse endpoint and forwards the
    SSE stream to the client, rewriting the endpoint URL so the client POSTs
    back through the proxy.
    """
    # Authenticate
    await get_user_id(request)

    upstream_base_url = await _resolve_sandbox_mcp_url(conversation_id, request)
    if not upstream_base_url:
        return Response(
            content='Could not resolve sandbox URL',
            status_code=502,
        )

    upstream_url = f'{upstream_base_url}/mcp/sse'
    headers = _forward_headers(request)

    async def stream_sse():
        async with httpx.AsyncClient() as client:
            async with client.stream(
                'GET', upstream_url, headers=headers, timeout=None
            ) as resp:
                async for line in resp.aiter_lines():
                    rewritten = _rewrite_endpoint_url(line, conversation_id)
                    yield rewritten + '\n'

    return StreamingResponse(
        stream_sse(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


@router.post('/mcp-proxy/{conversation_id}/messages/')
async def mcp_messages_proxy(request: Request, conversation_id: str):
    """Proxy MCP JSON-RPC messages to a conversation's sandbox.

    Forwards the POST body and query string (session_id) to the sandbox's
    /mcp/messages/ endpoint. The response may be JSON or an SSE stream
    (for streaming tool results).
    """
    # Authenticate
    await get_user_id(request)

    upstream_base_url = await _resolve_sandbox_mcp_url(conversation_id, request)
    if not upstream_base_url:
        return Response(
            content='Could not resolve sandbox URL',
            status_code=502,
        )

    upstream_url = f'{upstream_base_url}/mcp/messages/'
    if request.url.query:
        upstream_url = f'{upstream_url}?{request.url.query}'

    body = await request.body()
    headers = _forward_headers(request)

    try:
        async with httpx.AsyncClient() as client:
            upstream_response = await client.post(
                upstream_url,
                content=body,
                headers=headers,
                timeout=30.0,
            )
    except httpx.RequestError as exc:
        _logger.error(f'MCP proxy: upstream request failed: {exc}')
        return Response(content='Upstream request failed', status_code=502)

    # Check if upstream is returning an SSE stream
    content_type = upstream_response.headers.get('content-type', '')
    if 'text/event-stream' in content_type:
        # For SSE responses, stream them through
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            media_type='text/event-stream',
        )

    # Forward upstream response headers, excluding hop-by-hop headers
    response_headers = {}
    for key, value in upstream_response.headers.items():
        if key.lower() not in (
            'transfer-encoding',
            'content-encoding',
            'content-length',
        ):
            response_headers[key] = value

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
