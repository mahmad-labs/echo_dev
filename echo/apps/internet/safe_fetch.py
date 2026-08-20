from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
from dataclasses import dataclass
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    pass


@dataclass(frozen=True)
class ValidatedTarget:
    scheme: str
    hostname: str
    port: int
    path: str
    address: str


def _public_addresses(hostname: str, port: int) -> list[str]:
    addresses: list[str] = []
    try:
        results = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeURL("The destination hostname could not be resolved.") from exc

    for result in results:
        raw_address = result[4][0]
        address = ipaddress.ip_address(raw_address)
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise UnsafeURL("Private and reserved network destinations are blocked.")
        normalized = str(address)
        if normalized not in addresses:
            addresses.append(normalized)
    if not addresses:
        raise UnsafeURL("The destination has no public network address.")
    return addresses


def validate_public_url(url: str) -> ValidatedTarget:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeURL("Only public HTTP and HTTPS URLs are allowed.")
    if parsed.username or parsed.password:
        raise UnsafeURL("Credentials embedded in URLs are not allowed.")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeURL("The destination port is invalid.") from exc
    if not 1 <= port <= 65535:
        raise UnsafeURL("The destination port is invalid.")

    addresses = _public_addresses(parsed.hostname, port)
    path = parsed.path or "/"
    if parsed.params:
        path += f";{parsed.params}"
    if parsed.query:
        path += f"?{parsed.query}"
    return ValidatedTarget(parsed.scheme, parsed.hostname, port, path, addresses[0])


class _PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, target: ValidatedTarget, timeout: float):
        super().__init__(target.hostname, target.port, timeout=timeout)
        self._target_address = target.address

    def connect(self):
        self.sock = socket.create_connection(
            (self._target_address, self.port),
            self.timeout,
            self.source_address,
        )
        if self._tunnel_host:
            self._tunnel()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, target: ValidatedTarget, timeout: float):
        super().__init__(
            target.hostname,
            target.port,
            timeout=timeout,
            context=ssl.create_default_context(),
        )
        self._target_address = target.address

    def connect(self):
        sock = socket.create_connection(
            (self._target_address, self.port),
            self.timeout,
            self.source_address,
        )
        if self._tunnel_host:
            self.sock = sock
            self._tunnel()
            server_hostname = self._tunnel_host
        else:
            server_hostname = self.host
        self.sock = self._context.wrap_socket(sock, server_hostname=server_hostname)


class SafeFetchService:
    def fetch(self, url: str, *, timeout: float = 15, max_bytes: int = 2_000_000):
        if timeout <= 0 or timeout > 120:
            raise ValueError("timeout must be between 0 and 120 seconds.")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive.")

        target = validate_public_url(url)
        connection_class = (
            _PinnedHTTPSConnection if target.scheme == "https" else _PinnedHTTPConnection
        )
        connection = connection_class(target, timeout)
        try:
            host_header = target.hostname
            if target.port not in {80, 443}:
                host_header = f"{host_header}:{target.port}"
            connection.request(
                "GET",
                target.path,
                headers={
                    "Host": host_header,
                    "User-Agent": "EchoEnterprise/1.0",
                    "Accept": "*/*",
                    "Connection": "close",
                },
            )
            response = connection.getresponse()
            if 300 <= response.status < 400:
                raise UnsafeURL("Redirect responses are not followed automatically.")
            if response.status >= 400:
                raise RuntimeError(f"Remote server returned HTTP {response.status}.")

            declared_length = response.getheader("Content-Length")
            if declared_length and int(declared_length) > max_bytes:
                raise ValueError("Response exceeds the configured size limit.")

            body = bytearray()
            while True:
                chunk = response.read(min(65_536, max_bytes - len(body) + 1))
                if not chunk:
                    break
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise ValueError("Response exceeds the configured size limit.")
            return {
                "url": url,
                "status_code": response.status,
                "content_type": response.getheader("Content-Type", ""),
                "body": bytes(body),
            }
        finally:
            connection.close()
