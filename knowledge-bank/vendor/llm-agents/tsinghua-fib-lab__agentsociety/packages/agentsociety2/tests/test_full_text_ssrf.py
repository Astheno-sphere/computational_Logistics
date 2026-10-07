"""SSRF guards for literature full-text PDF downloads."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agentsociety2.skills.literature.full_text import (
    FullTextDownloadError,
    _SafeRedirectHandler,
    _validate_public_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x.pdf",
        "http://10.0.0.5/x.pdf",
        "http://192.168.1.1/x.pdf",
        "http://169.254.169.254/latest/meta-data",
        "http://localhost/x.pdf",
        "http://[::1]/x.pdf",
        "file:///etc/passwd",
        "ftp://example.com/x.pdf",
    ],
)
def test_validate_public_url_blocks_restricted_targets(url: str) -> None:
    with pytest.raises(FullTextDownloadError):
        _validate_public_url(url)


def test_validate_public_url_blocks_hostname_resolving_to_private() -> None:
    fake = [
        (0, 0, 0, "", ("10.1.2.3", 0)),
    ]
    with (
        patch(
            "agentsociety2.skills.literature.full_text.socket.getaddrinfo",
            return_value=fake,
        ),
        pytest.raises(FullTextDownloadError, match="restricted address"),
    ):
        _validate_public_url("https://evil.example/paper.pdf")


def test_validate_public_url_allows_hostname_resolving_to_public() -> None:
    fake = [
        (0, 0, 0, "", ("93.184.216.34", 0)),
    ]
    with patch(
        "agentsociety2.skills.literature.full_text.socket.getaddrinfo",
        return_value=fake,
    ):
        _validate_public_url("https://example.com/paper.pdf")


def test_safe_redirect_handler_rejects_private_hop() -> None:
    handler = _SafeRedirectHandler()
    with pytest.raises(FullTextDownloadError):
        handler.redirect_request(
            req=None,
            fp=None,
            code=302,
            msg="Found",
            headers={},
            newurl="http://127.0.0.1/secret.pdf",
        )
