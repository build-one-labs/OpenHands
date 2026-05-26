"""Tests for the git path-segment -> query-param translation in the HTTP proxy.

agent-server >=1.21 takes the git repo/file path as a ``?path=`` query
parameter, but the frontend V1 git service sends it as a trailing path segment
(so the request misses the exact V0 ``/git/changes`` route and reaches the
proxy). ``_translate_git_path`` bridges the two.
"""

from openhands.app_server.http_proxy_router import _translate_git_path


def test_git_changes_segment_becomes_path_query():
    # Decoded form (Starlette percent-decodes the matched path).
    path, extra_query = _translate_git_path('git/changes//workspace/project')
    assert path == 'git/changes'
    assert extra_query == 'path=%2Fworkspace%2Fproject'


def test_git_changes_still_encoded_segment():
    # Robust even if %2F survived undecoded.
    path, extra_query = _translate_git_path('git/changes/%2Fworkspace%2Fproject')
    assert path == 'git/changes'
    assert extra_query == 'path=%2Fworkspace%2Fproject'


def test_git_diff_file_segment_becomes_path_query():
    path, extra_query = _translate_git_path(
        'git/diff/%2Fworkspace%2Fproject%2Fsrc%2Fmain.py'
    )
    assert path == 'git/diff'
    assert extra_query == 'path=%2Fworkspace%2Fproject%2Fsrc%2Fmain.py'


def test_non_git_path_is_untouched():
    path, extra_query = _translate_git_path('file/download/%2Ffoo')
    assert path == 'file/download/%2Ffoo'
    assert extra_query is None


def test_bare_git_changes_without_segment_is_untouched():
    # No trailing segment -> not our case; leave it alone.
    path, extra_query = _translate_git_path('git/changes')
    assert path == 'git/changes'
    assert extra_query is None
