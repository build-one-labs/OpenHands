from types import MappingProxyType

import pytest
from pydantic import SecretStr

from openhands.integrations.provider import CustomSecret, ProviderToken
from openhands.integrations.service_types import ProviderType
from openhands.server.user_auth.default_user_auth import (
    _is_kimi_model,
    _is_openai_model,
    _llm_api_key_secret_name,
    _resolve_github_token_from_custom_secret,
)
from openhands.storage.data_models.secrets import (
    WELL_KNOWN_SECRET_GITHUB_TOKEN,
    WELL_KNOWN_SECRET_LLM_API_KEY,
    WELL_KNOWN_SECRET_MOONSHOT_API_KEY,
    WELL_KNOWN_SECRET_OPENAI_API_KEY,
    Secrets,
)


def test_resolve_github_token_creates_provider_token():
    """When github-token custom secret exists and no GitHub provider token,
    a GitHub provider token should be created."""
    secrets = Secrets(
        provider_tokens=MappingProxyType({}),
        custom_secrets=MappingProxyType(
            {
                WELL_KNOWN_SECRET_GITHUB_TOKEN: CustomSecret(
                    secret=SecretStr('ghp_test123')
                ),
            }
        ),
    )

    result = _resolve_github_token_from_custom_secret(secrets)

    assert ProviderType.GITHUB in result.provider_tokens
    assert (
        result.provider_tokens[ProviderType.GITHUB].token.get_secret_value()
        == 'ghp_test123'
    )


def test_resolve_github_token_preserves_existing_token():
    """When a GitHub provider token already exists, the custom secret should
    NOT override it."""
    existing_token = ProviderToken(token=SecretStr('existing-token'))
    secrets = Secrets(
        provider_tokens=MappingProxyType({ProviderType.GITHUB: existing_token}),
        custom_secrets=MappingProxyType(
            {
                WELL_KNOWN_SECRET_GITHUB_TOKEN: CustomSecret(
                    secret=SecretStr('ghp_custom')
                ),
            }
        ),
    )

    result = _resolve_github_token_from_custom_secret(secrets)

    assert (
        result.provider_tokens[ProviderType.GITHUB].token.get_secret_value()
        == 'existing-token'
    )


def test_resolve_github_token_no_custom_secret():
    """When no github-token custom secret exists, secrets should pass through
    unchanged."""
    secrets = Secrets(
        provider_tokens=MappingProxyType({}),
        custom_secrets=MappingProxyType({}),
    )

    result = _resolve_github_token_from_custom_secret(secrets)

    assert ProviderType.GITHUB not in result.provider_tokens


def test_resolve_github_token_empty_existing_token():
    """When GitHub provider token exists but has empty value, the custom secret
    should be used."""
    empty_token = ProviderToken(token=SecretStr(''))
    secrets = Secrets(
        provider_tokens=MappingProxyType({ProviderType.GITHUB: empty_token}),
        custom_secrets=MappingProxyType(
            {
                WELL_KNOWN_SECRET_GITHUB_TOKEN: CustomSecret(
                    secret=SecretStr('ghp_replacement')
                ),
            }
        ),
    )

    result = _resolve_github_token_from_custom_secret(secrets)

    assert (
        result.provider_tokens[ProviderType.GITHUB].token.get_secret_value()
        == 'ghp_replacement'
    )


def test_resolve_github_token_preserves_other_providers():
    """Other provider tokens should be unaffected by GitHub token resolution."""
    gitlab_token = ProviderToken(token=SecretStr('glpat-test'))
    secrets = Secrets(
        provider_tokens=MappingProxyType({ProviderType.GITLAB: gitlab_token}),
        custom_secrets=MappingProxyType(
            {
                WELL_KNOWN_SECRET_GITHUB_TOKEN: CustomSecret(
                    secret=SecretStr('ghp_test')
                ),
            }
        ),
    )

    result = _resolve_github_token_from_custom_secret(secrets)

    assert ProviderType.GITHUB in result.provider_tokens
    assert ProviderType.GITLAB in result.provider_tokens
    assert (
        result.provider_tokens[ProviderType.GITLAB].token.get_secret_value()
        == 'glpat-test'
    )


@pytest.mark.parametrize(
    'model,expected',
    [
        ('gpt-4o', True),
        ('openai/gpt-4o', True),
        ('o1-preview', True),
        ('o3-mini', True),
        ('o4-mini', True),
        ('chatgpt-4o-latest', True),
        ('litellm_proxy/gpt-4o', True),
        ('claude-sonnet-4-6', False),
        ('anthropic/claude-3-5-sonnet', False),
        ('gemini-1.5-pro', False),
        (None, False),
        ('', False),
    ],
)
def test_is_openai_model(model, expected):
    assert _is_openai_model(model) is expected


@pytest.mark.parametrize(
    'model,expected',
    [
        ('moonshot/kimi-k2-0711-preview', True),
        ('moonshot/moonshot-v1-8k', True),
        ('moonshot/kimi-latest', True),
        ('kimi-thinking-preview', True),
        ('litellm_proxy/kimi-latest', True),
        ('gpt-4o', False),
        ('claude-sonnet-4-6', False),
        ('anthropic/claude-3-5-sonnet', False),
        (None, False),
        ('', False),
    ],
)
def test_is_kimi_model(model, expected):
    assert _is_kimi_model(model) is expected


def _custom_secrets(*names):
    return MappingProxyType(
        {name: CustomSecret(secret=SecretStr(f'{name}-value')) for name in names}
    )


def test_llm_api_key_secret_name_openai_model_prefers_openai():
    secrets = _custom_secrets(
        WELL_KNOWN_SECRET_OPENAI_API_KEY, WELL_KNOWN_SECRET_LLM_API_KEY
    )
    assert (
        _llm_api_key_secret_name('gpt-4o', secrets) == WELL_KNOWN_SECRET_OPENAI_API_KEY
    )


def test_llm_api_key_secret_name_anthropic_model_prefers_anthropic():
    secrets = _custom_secrets(
        WELL_KNOWN_SECRET_OPENAI_API_KEY, WELL_KNOWN_SECRET_LLM_API_KEY
    )
    assert (
        _llm_api_key_secret_name('claude-sonnet-4-6', secrets)
        == WELL_KNOWN_SECRET_LLM_API_KEY
    )


def test_llm_api_key_secret_name_falls_back_to_available_provider():
    # OpenAI model selected but only the Anthropic key is stored.
    secrets = _custom_secrets(WELL_KNOWN_SECRET_LLM_API_KEY)
    assert _llm_api_key_secret_name('gpt-4o', secrets) == WELL_KNOWN_SECRET_LLM_API_KEY
    # Anthropic model selected but only the OpenAI key is stored.
    secrets = _custom_secrets(WELL_KNOWN_SECRET_OPENAI_API_KEY)
    assert (
        _llm_api_key_secret_name('claude-sonnet-4-6', secrets)
        == WELL_KNOWN_SECRET_OPENAI_API_KEY
    )


def test_llm_api_key_secret_name_kimi_model_prefers_kimi():
    secrets = _custom_secrets(
        WELL_KNOWN_SECRET_MOONSHOT_API_KEY,
        WELL_KNOWN_SECRET_OPENAI_API_KEY,
        WELL_KNOWN_SECRET_LLM_API_KEY,
    )
    assert (
        _llm_api_key_secret_name('moonshot/kimi-k2-0711-preview', secrets)
        == WELL_KNOWN_SECRET_MOONSHOT_API_KEY
    )


def test_llm_api_key_secret_name_kimi_model_falls_back_when_no_kimi_key():
    # Kimi model selected but only the Anthropic key is stored.
    secrets = _custom_secrets(WELL_KNOWN_SECRET_LLM_API_KEY)
    assert (
        _llm_api_key_secret_name('moonshot/kimi-latest', secrets)
        == WELL_KNOWN_SECRET_LLM_API_KEY
    )


def test_llm_api_key_secret_name_none_when_no_keys():
    assert _llm_api_key_secret_name('gpt-4o', _custom_secrets()) is None
