"""SSRF validation tests for the URL fetching logic in document_processor."""

import socket
from unittest.mock import patch

import pytest

import sys
from pathlib import Path

# Add Frontend root to path so we can import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.document_processor import _validate_public_url, _is_public_ip


# ---------------------------------------------------------------------------
# _is_public_ip unit tests
# ---------------------------------------------------------------------------

def test_loopback_is_not_public():
    assert _is_public_ip("127.0.0.1") is False

def test_private_10_range_is_not_public():
    assert _is_public_ip("10.0.0.1") is False

def test_private_192_168_range_is_not_public():
    assert _is_public_ip("192.168.1.1") is False

def test_link_local_is_not_public():
    assert _is_public_ip("169.254.169.254") is False

def test_public_ip_is_public():
    assert _is_public_ip("8.8.8.8") is True

def test_cloudflare_ip_is_public():
    assert _is_public_ip("1.1.1.1") is True


# ---------------------------------------------------------------------------
# _validate_public_url — blocked URLs
# ---------------------------------------------------------------------------

def _fake_resolve_to(ip: str):
    """Return a mock getaddrinfo that resolves any hostname to the given IP."""
    return lambda hostname, port, **kwargs: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))
    ]


def test_blocks_localhost():
    with pytest.raises(ValueError, match="Local or internal"):
        _validate_public_url("http://localhost/secret")


def test_blocks_internal_local():
    with pytest.raises(ValueError, match="Local or internal"):
        _validate_public_url("http://internal.local/api")


def test_blocks_loopback_ip():
    with patch("socket.getaddrinfo", _fake_resolve_to("127.0.0.1")):
        with pytest.raises(ValueError, match="Private, loopback, or reserved"):
            _validate_public_url("http://127.0.0.1/admin")


def test_blocks_private_10_range():
    with patch("socket.getaddrinfo", _fake_resolve_to("10.0.0.1")):
        with pytest.raises(ValueError, match="Private, loopback, or reserved"):
            _validate_public_url("http://10.0.0.1/internal")


def test_blocks_private_192_168_range():
    with patch("socket.getaddrinfo", _fake_resolve_to("192.168.1.1")):
        with pytest.raises(ValueError, match="Private, loopback, or reserved"):
            _validate_public_url("http://192.168.1.1/config")


def test_blocks_aws_metadata_endpoint():
    """Classic SSRF target: AWS instance metadata."""
    with patch("socket.getaddrinfo", _fake_resolve_to("169.254.169.254")):
        with pytest.raises(ValueError, match="Private, loopback, or reserved"):
            _validate_public_url("http://169.254.169.254/latest/meta-data/")


def test_blocks_ftp_scheme():
    with pytest.raises(ValueError, match="Only http"):
        _validate_public_url("ftp://example.com/file")


def test_blocks_empty_url():
    with pytest.raises(ValueError):
        _validate_public_url("")


# ---------------------------------------------------------------------------
# _validate_public_url — allowed URLs
# ---------------------------------------------------------------------------

def test_allows_public_https():
    with patch("socket.getaddrinfo", _fake_resolve_to("93.184.216.34")):
        result = _validate_public_url("https://docs.example.com/whitepaper.pdf")
        assert "docs.example.com" in result


def test_allows_github():
    with patch("socket.getaddrinfo", _fake_resolve_to("140.82.121.4")):
        result = _validate_public_url("https://github.com/project/readme")
        assert "github.com" in result
