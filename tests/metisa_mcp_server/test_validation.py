"""Specify the filename and URL policies without making network requests."""

from __future__ import annotations

import socket
from unittest.mock import Mock

import pytest

from metisa_mcp_server._validation import (
    validate_filename_argument,
    validate_url_argument,
)


@pytest.fixture(autouse=True)
def _forbid_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    resolver = Mock(
        side_effect=AssertionError("Argument validation must not perform DNS lookups.")
    )
    monkeypatch.setattr(socket, "getaddrinfo", resolver)


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("filename.txt", id="simple-filename"),
        pytest.param("folder/filename.txt", id="child-directory"),
        pytest.param("folder/subfolder/filename.txt", id="nested-directories"),
        pytest.param(".hidden/file.txt", id="hidden-directory"),
        pytest.param("report..txt", id="dots-within-filename"),
        pytest.param("folder/my report.txt", id="space-within-filename"),
    ],
)
def test_validate_filename_argument_accepts_valid_filename(filename: str) -> None:
    validate_filename_argument(filename)


@pytest.mark.parametrize(
    "filename",
    [
        pytest.param("", id="empty"),
        pytest.param("file\x00.txt", id="null-character"),
        pytest.param("/folder/filename.txt", id="absolute-posix-path"),
        pytest.param("./folder/filename.txt", id="leading-current-directory"),
        pytest.param(".", id="current-directory-only"),
        pytest.param("..", id="parent-directory-only"),
        pytest.param("../filename.txt", id="leading-parent-directory"),
        pytest.param("folder/../../filename.txt", id="escaping-parent-directories"),
        pytest.param("folder/../filename.txt", id="internal-parent-directory"),
        pytest.param("folder/./filename.txt", id="internal-current-directory"),
        pytest.param("c:/folder/filename.txt", id="absolute-windows-forward-slashes"),
        pytest.param(r"c:\folder\filename.txt", id="absolute-windows-backslashes"),
        pytest.param("c:filename.txt", id="drive-relative-windows-path"),
        pytest.param(r"folder\filename.txt", id="relative-windows-path"),
        pytest.param(r"\folder\filename.txt", id="rooted-windows-path"),
        pytest.param(r"\\server\share\filename.txt", id="unc-path"),
        pytest.param("folder/file:stream", id="colon-within-path"),
        pytest.param("folder//filename.txt", id="empty-internal-component"),
        pytest.param("folder/", id="empty-final-component"),
    ],
)
def test_validate_filename_argument_rejects_invalid_filename(filename: str) -> None:
    with pytest.raises(ValueError):
        validate_filename_argument(filename)


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("http://example.com", id="http-hostname"),
        pytest.param("https://example.com/document", id="https-path"),
        pytest.param("HTTPS://EXAMPLE.COM/document", id="case-insensitive-host"),
        pytest.param("https://example.com./document", id="trailing-host-dot"),
        pytest.param("https://example.com:8443/document", id="explicit-port"),
        pytest.param("http://example.com:1/", id="minimum-port"),
        pytest.param("https://example.com:65535/", id="maximum-port"),
        pytest.param(
            "https://example.com/a%20b?q=hello%20world#part", id="encoded-path"
        ),
        pytest.param("http://93.184.216.34/", id="public-ipv4"),
        pytest.param("https://[2606:4700:4700::1111]/", id="public-ipv6"),
        pytest.param("http://[::ffff:93.184.216.34]/", id="mapped-public-ipv4"),
    ],
)
def test_validate_url_argument_accepts_valid_url(url: str) -> None:
    validate_url_argument(url)


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("", id="empty"),
        pytest.param(" https://example.com/", id="leading-space"),
        pytest.param("https://example.com/a b", id="unencoded-space"),
        pytest.param("https://example.com/\tfile", id="tab"),
        pytest.param("https://example.com/\nfile", id="newline"),
        pytest.param("https://example.com/\rfile", id="carriage-return"),
        pytest.param("https://example.com/\x00file", id="null-character"),
        pytest.param("https://example.com/\x7ffile", id="delete-character"),
        pytest.param(r"http://example.com\document", id="backslash"),
        pytest.param("ftp://example.com/document", id="unsupported-scheme"),
        pytest.param("file:///etc/passwd", id="file-scheme"),
        pytest.param("example.com/document", id="missing-scheme"),
        pytest.param("//example.com/document", id="scheme-relative"),
        pytest.param("http:///document", id="missing-hostname"),
        pytest.param("http://[::1", id="malformed-ipv6"),
        pytest.param("http://example.com:invalid/", id="non-numeric-port"),
        pytest.param("http://example.com:0/", id="zero-port"),
        pytest.param("http://example.com:-1/", id="negative-port"),
        pytest.param("http://example.com:65536/", id="port-out-of-range"),
        pytest.param("http://user@example.com/", id="username"),
        pytest.param("http://user:password@example.com/", id="password"),
        pytest.param("http://@example.com/", id="empty-credentials"),
        pytest.param("http://%65xample.com/", id="encoded-hostname"),
        pytest.param("http://[fe80::1%25eth0]/", id="scoped-ipv6"),
        pytest.param("http://localhost/", id="localhost"),
        pytest.param("http://LOCALHOST/", id="uppercase-localhost"),
        pytest.param("http://localhost./", id="localhost-trailing-dot"),
        pytest.param("http://service.localhost/", id="localhost-subdomain"),
        pytest.param("http://127.0.0.1/", id="loopback-ipv4"),
        pytest.param("http://127.10.20.30/", id="other-loopback-ipv4"),
        pytest.param("http://10.0.0.1/", id="private-ipv4-class-a"),
        pytest.param("http://172.16.0.1/", id="private-ipv4-class-b"),
        pytest.param("http://192.168.1.1/", id="private-ipv4-class-c"),
        pytest.param("http://169.254.169.254/", id="link-local-ipv4"),
        pytest.param("http://0.0.0.0/", id="unspecified-ipv4"),
        pytest.param("http://100.64.0.1/", id="shared-address-space"),
        pytest.param("http://224.0.0.1/", id="multicast-ipv4"),
        pytest.param("http://[::1]/", id="loopback-ipv6"),
        pytest.param("http://[::]/", id="unspecified-ipv6"),
        pytest.param("http://[fc00::1]/", id="private-ipv6"),
        pytest.param("http://[fe80::1]/", id="link-local-ipv6"),
        pytest.param("http://[fec0::1]/", id="site-local-ipv6"),
        pytest.param("http://[ff02::1]/", id="multicast-ipv6"),
        pytest.param("http://[::ffff:127.0.0.1]/", id="mapped-loopback-ipv4"),
        pytest.param("http://[::ffff:192.168.1.1]/", id="mapped-private-ipv4"),
        pytest.param("http://[::ffff:224.0.0.1]/", id="mapped-multicast-ipv4"),
        pytest.param("http://127.1/", id="abbreviated-loopback-ipv4"),
        pytest.param("http://2130706433/", id="integer-loopback-ipv4"),
        pytest.param("http://0x7f000001/", id="hexadecimal-loopback-ipv4"),
        pytest.param("http://./", id="empty-normalized-hostname"),
        pytest.param("http://example..com/", id="empty-hostname-label"),
        pytest.param("http://-example.com/", id="leading-hyphen"),
        pytest.param("http://example_.com/", id="invalid-hostname-character"),
    ],
)
def test_validate_url_argument_rejects_invalid_url(url: str) -> None:
    with pytest.raises(ValueError):
        validate_url_argument(url)
