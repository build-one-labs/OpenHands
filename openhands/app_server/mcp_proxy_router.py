"""Sandbox endpoint resolution for MCP tools.

Resolves a conversation_id to the sandbox's internal MCP base URL and
session API key. Used by the centralized MCP server tools (list_tools,
call_tool) in openhands/server/routes/mcp.py.
"""

import logging
from dataclasses import dataclass
from uuid import UUID

from fastapi import Request

from openhands.app_server.app_conversation.app_conversation_info_service import (
    AppConversationInfoService,
)
from openhands.app_server.sandbox.sandbox_models import AGENT_SERVER, SandboxStatus
from openhands.app_server.sandbox.sandbox_service import SandboxService

_logger = logging.getLogger(__name__)


@dataclass
class SandboxEndpoint:
    base_url: str
    session_api_key: str | None


async def resolve_sandbox_endpoint(
    conversation_id: str, request: Request
) -> SandboxEndpoint | None:
    """Resolve a conversation_id to the sandbox's internal URL and API key.

    Reuses the same resolution pattern as http_proxy_router.py:
    UUID parse -> AppConversationInfoService -> SandboxService -> SandboxInfo.
    """
    from openhands.app_server.config import (
        get_app_conversation_info_service,
        get_sandbox_service,
    )

    try:
        conv_uuid = UUID(hex=conversation_id)
    except ValueError:
        _logger.warning(f'MCP: invalid conversation_id format: {conversation_id}')
        return None

    state = request.state
    try:
        async with (
            get_app_conversation_info_service(state, request) as info_service,
            get_sandbox_service(state, request) as sandbox_service,
        ):
            return await _resolve_endpoint(
                info_service, sandbox_service, conversation_id, conv_uuid
            )
    except Exception as exc:
        _logger.error(f'MCP: failed to resolve sandbox for {conversation_id}: {exc}')
        return None


async def _resolve_endpoint(
    info_service: AppConversationInfoService,
    sandbox_service: SandboxService,
    conversation_id: str,
    conv_uuid: UUID,
) -> SandboxEndpoint | None:
    """Resolve the sandbox endpoint (URL + API key) for a conversation."""
    info = await info_service.get_app_conversation_info(conv_uuid)
    if info is None:
        _logger.warning(f'MCP: conversation not found: {conversation_id}')
        return None

    sandbox = await sandbox_service.get_sandbox(info.sandbox_id)
    if sandbox is None:
        _logger.warning(f'MCP: sandbox not found: {info.sandbox_id}')
        return None

    # Record activity for idle-timeout tracking
    from openhands.app_server.idle_timeout_manager import get_idle_timeout_manager

    manager = get_idle_timeout_manager()
    if manager:
        manager.touch(info.sandbox_id)

    if sandbox.status != SandboxStatus.RUNNING:
        _logger.warning(
            f'MCP: sandbox not running: {info.sandbox_id} ({sandbox.status})'
        )
        return None

    if not sandbox.exposed_urls:
        _logger.warning(f'MCP: no exposed URLs for sandbox: {info.sandbox_id}')
        return None

    agent_server_eu = next(
        (eu for eu in sandbox.exposed_urls if eu.name == AGENT_SERVER),
        None,
    )
    if not agent_server_eu or not agent_server_eu.internal_url:
        _logger.warning(f'MCP: no internal URL for sandbox: {info.sandbox_id}')
        return None

    return SandboxEndpoint(
        base_url=agent_server_eu.internal_url,
        session_api_key=sandbox.session_api_key,
    )
