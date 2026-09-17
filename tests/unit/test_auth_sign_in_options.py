"""Tests for the org-scoped sign-in options endpoint.

With an organization-scoped auth URL (``<origin>/<slug>``), the auth server
strips the prefix and answers with that organization's sign-in methods, so
OpenHands must ask rather than hardcode a provider list.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openhands.server.routes import auth as auth_routes


def _response(payload: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = json.dumps(payload)
    return resp


def _patch_get(resp: MagicMock | Exception):
    """Patch httpx.AsyncClient so the endpoint's GET returns resp (or raises)."""
    client = MagicMock()
    if isinstance(resp, Exception):
        client.get = AsyncMock(side_effect=resp)
    else:
        client.get = AsyncMock(return_value=resp)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return patch.object(auth_routes.httpx, 'AsyncClient', return_value=ctx), client


# Entries as returned by /api/auth/b1/authentication
_BASIC = {
    'id': 'basic',
    'type': 'basic',
    'label': 'E-mail and password',
    'icon': 'pi pi-envelope',
    'kind': 'local',
}
_MICROSOFT = {
    'id': 'b1-microsoft',
    'type': 'microsoft',
    'label': 'Microsoft',
    'icon': 'pi pi-microsoft',
    'kind': 'oauth',
}
_GITHUB = {
    'id': 'b1-github',
    'type': 'github',
    'label': 'GitHub',
    'icon': 'pi pi-github',
    'kind': 'oauth',
}


async def _call() -> dict:
    request = MagicMock()
    request.headers = {'origin': 'https://app.example.com'}
    response = await auth_routes.get_providers(request)
    return json.loads(response.body)


_MICROSOFT_BUTTON = {
    'provider': 'microsoft',
    'label': 'Microsoft',
    'icon': 'pi pi-microsoft',
}
_GITHUB_BUTTON = {'provider': 'github', 'label': 'GitHub', 'icon': 'pi pi-github'}


@pytest.mark.parametrize(
    'methods,expected_providers,expected_password',
    [
        (
            [_BASIC, _MICROSOFT, _GITHUB],
            [_MICROSOFT_BUTTON, _GITHUB_BUTTON],
            True,
        ),
        ([_BASIC], [], True),
        ([_MICROSOFT], [_MICROSOFT_BUTTON], False),
        # Duplicates collapse; unknown kinds and non-dict entries are skipped
        (
            [_GITHUB, _GITHUB, {'type': 'saml', 'kind': 'sso'}, 'github', None],
            [_GITHUB_BUTTON],
            False,
        ),
        # Missing label falls back to the provider name, missing icon to None
        (
            [{'type': 'gitlab', 'kind': 'oauth'}],
            [{'provider': 'gitlab', 'label': 'gitlab', 'icon': None}],
            False,
        ),
        ([], [], False),
        (None, [], False),
        ('github', [], False),
    ],
)
def test_split_sign_in_methods(methods, expected_providers, expected_password):
    providers, password_enabled = auth_routes._split_sign_in_methods(methods)
    assert providers == expected_providers
    assert password_enabled is expected_password


async def test_returns_defaults_when_auth_not_configured():
    with patch.object(auth_routes, 'BETTER_AUTH_URL', ''):
        body = await _call()
    assert body == {
        'providers': [],
        'passwordEnabled': True,
        'inviteOnly': False,
        'organization': None,
    }


async def test_scopes_request_to_the_configured_organization():
    org = {'id': 'o1', 'slug': 'acme', 'name': 'Acme', 'logo': None}
    resp = _response(
        {
            'methods': [_BASIC, _GITHUB],
            'inviteOnly': True,
            'organization': org,
        }
    )
    patcher, client = _patch_get(resp)
    with (
        patch.object(auth_routes, 'BETTER_AUTH_URL', 'https://auth.example.com/acme'),
        patcher,
    ):
        body = await _call()

    # The org slug rides along in the base URL; the path stays under /api/
    # so the auth server's prefix middleware matches and strips it.
    assert (
        client.get.await_args.args[0]
        == 'https://auth.example.com/acme/api/auth/b1/authentication'
    )
    assert body == {
        'providers': [_GITHUB_BUTTON],
        'passwordEnabled': True,
        'inviteOnly': True,
        'organization': org,
    }


async def test_password_only_org_reports_no_providers():
    patcher, _ = _patch_get(_response({'methods': [_BASIC], 'inviteOnly': False}))
    with (
        patch.object(auth_routes, 'BETTER_AUTH_URL', 'https://auth.example.com'),
        patcher,
    ):
        body = await _call()
    assert body['providers'] == []
    assert body['passwordEnabled'] is True
    assert body['organization'] is None


async def test_social_only_org_disables_password():
    patcher, _ = _patch_get(_response({'methods': [_MICROSOFT]}))
    with (
        patch.object(auth_routes, 'BETTER_AUTH_URL', 'https://auth.example.com'),
        patcher,
    ):
        body = await _call()
    assert body['providers'] == [_MICROSOFT_BUTTON]
    assert body['passwordEnabled'] is False


@pytest.mark.parametrize(
    'failure',
    [_response({'error': 'boom'}, status_code=500), RuntimeError('network down')],
)
async def test_degrades_to_password_when_auth_server_unreachable(failure):
    patcher, _ = _patch_get(failure)
    with (
        patch.object(auth_routes, 'BETTER_AUTH_URL', 'https://auth.example.com/acme'),
        patcher,
    ):
        body = await _call()
    # No social buttons that would fail, but email/password stays available.
    assert body == {
        'providers': [],
        'passwordEnabled': True,
        'inviteOnly': False,
        'organization': None,
    }
