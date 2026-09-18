"""Tests for resolving user secrets from the Better Auth server."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from openhands.server.user_auth import default_user_auth as module
from openhands.server.user_auth.default_user_auth import DefaultUserAuth

AUTH_URL = 'https://auth.test.build.one/build-one'


def _response(payload: object, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = json.dumps(payload)
    return resp


def _patch_client(resp: MagicMock | Exception):
    client = MagicMock()
    if isinstance(resp, Exception):
        client.get = AsyncMock(side_effect=resp)
    else:
        client.get = AsyncMock(return_value=resp)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return patch.object(module.httpx, 'AsyncClient', return_value=ctx), client


def _user_auth() -> DefaultUserAuth:
    user_auth = DefaultUserAuth()
    user_auth._session_cookie = ('b1.session_token', 'tok')
    user_auth._forwarded_host = 'app.example.com'
    user_auth._forwarded_proto = 'https'
    return user_auth


async def _fetch(resp: MagicMock | Exception, auth_url: str = AUTH_URL):
    patcher, client = _patch_client(resp)
    with patch.dict(module.os.environ, {'BETTER_AUTH_URL': auth_url}), patcher:
        secrets = await _user_auth()._fetch_auth_server_secrets()
    return secrets, client


def _values(secrets) -> dict[str, str]:
    return {
        key: value.secret.get_secret_value()
        for key, value in secrets.custom_secrets.items()
    }


async def test_resolves_all_secrets_in_one_call():
    secrets, client = await _fetch(
        _response(
            {
                'secrets': [
                    {
                        'key': 'anthropic-api-key',
                        'secret': 'sk-ant',
                        'level': 'organization',
                        'scope': '',
                    },
                    {
                        'key': 'github-token',
                        'secret': 'ghp',
                        'level': 'user',
                        'scope': '',
                    },
                ],
                'scope': '',
            }
        )
    )

    client.get.assert_awaited_once()
    call = client.get.await_args
    assert call.args[0] == f'{AUTH_URL}/api/secrets/resolve-all'
    assert call.kwargs['cookies'] == {'b1.session_token': 'tok'}
    assert call.kwargs['headers'] == {
        'x-forwarded-host': 'app.example.com',
        'x-forwarded-proto': 'https',
    }
    assert _values(secrets) == {'anthropic-api-key': 'sk-ant', 'github-token': 'ghp'}


async def test_unwraps_json_stringified_token():
    secrets, _ = await _fetch(
        _response({'secrets': [{'key': 'github-token', 'secret': '{"token": "ghp"}'}]})
    )
    assert _values(secrets) == {'github-token': 'ghp'}


async def test_unwraps_json_value_wrapper():
    credentials = '{"claudeAiOauth": {"accessToken": "x"}}'
    secrets, _ = await _fetch(
        _response(
            {
                'secrets': [
                    {
                        'key': 'linear-api-key',
                        'secret': json.dumps({'value': 'lin_api_123'}),
                    },
                    {
                        'key': 'claude-code-credentials',
                        'secret': json.dumps({'value': credentials}),
                    },
                ]
            }
        )
    )
    assert _values(secrets) == {
        'linear-api-key': 'lin_api_123',
        'claude-code-credentials': credentials,
    }


async def test_skips_malformed_and_empty_entries():
    secrets, _ = await _fetch(
        _response(
            {
                'secrets': [
                    {'key': 'ok', 'secret': 'value'},
                    {'key': 'empty', 'secret': ''},
                    {'key': '', 'secret': 'no-key'},
                    {'secret': 'missing-key'},
                    'not-a-dict',
                ]
            }
        )
    )
    assert _values(secrets) == {'ok': 'value'}


async def test_returns_none_when_no_secrets():
    secrets, _ = await _fetch(_response({'secrets': [], 'scope': ''}))
    assert secrets is None


async def test_returns_none_on_error_status():
    secrets, _ = await _fetch(_response({'error': 'Unauthorized'}, status_code=401))
    assert secrets is None


async def test_returns_none_on_network_error():
    secrets, _ = await _fetch(RuntimeError('network down'))
    assert secrets is None


async def test_returns_none_on_unexpected_payload():
    secrets, _ = await _fetch(_response(['not', 'a', 'dict']))
    assert secrets is None


async def test_skips_request_without_session():
    patcher, client = _patch_client(_response({'secrets': []}))
    with patch.dict(module.os.environ, {'BETTER_AUTH_URL': AUTH_URL}), patcher:
        assert await DefaultUserAuth()._fetch_auth_server_secrets() is None
    client.get.assert_not_called()
