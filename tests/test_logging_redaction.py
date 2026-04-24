from __future__ import annotations

import logging

from backend.core.logging import SensitiveQueryParamFilter


def test_sensitive_query_param_filter_masks_messages_args_and_extras():
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="GET /callback?code=abc&state=def&poll_token=ghi&client_secret=jkl %s",
        args=("POST /verify?token=raw-token&access_token=raw-access",),
        exc_info=None,
    )
    record.url = "/oauth/callback?refresh_token=raw-refresh&state=raw-state"

    assert SensitiveQueryParamFilter().filter(record) is True

    rendered = record.getMessage()
    assert "abc" not in rendered
    assert "def" not in rendered
    assert "ghi" not in rendered
    assert "jkl" not in rendered
    assert "raw-token" not in str(record.args)
    assert "raw-access" not in str(record.args)
    assert "raw-refresh" not in record.url
    assert "raw-state" not in record.url
    assert rendered.count("REDACTED") == 6
