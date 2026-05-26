import os

import pytest


@pytest.fixture(autouse=True)
def _allow_short_context_windows():
    """Allow small dummy models (e.g. 'gpt-4') in unit tests.

    openhands-sdk >= 1.21 validates the LLM context window at construction and
    raises LLMContextWindowTooSmallError for models below 16k tokens. These unit
    tests use placeholder model names, so enable the SDK-provided override.
    """
    prev = os.environ.get('ALLOW_SHORT_CONTEXT_WINDOWS')
    os.environ['ALLOW_SHORT_CONTEXT_WINDOWS'] = 'true'
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop('ALLOW_SHORT_CONTEXT_WINDOWS', None)
        else:
            os.environ['ALLOW_SHORT_CONTEXT_WINDOWS'] = prev
