"""SSRF-safe URL validation for external lesson sources."""

import ipaddress
import socket
import urllib.parse
from typing import Optional


class SSRFValidationError(Exception):
    """Raised when URL violates security constraints or targets private/loopback/metadata destinations."""
    pass


def validate_public_https_url(url: str) -> str:
    """Validates that a URL is strictly public HTTPS and safe from SSRF attacks.

    INVARIANTS:
    1. Scheme must strictly be 'https'.
    2. Hostname must be non-empty and resolvable.
    3. Resolved IP must NOT be:
       - Loopback (127.0.0.0/8, ::1)
       - Private / RFC 1918 (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
       - Link-local / Cloud metadata (169.254.0.0/16, fe80::/10)
       - Multicast or broadcast.
    4. Port must be standard HTTPS (443) or omitted.
    """
    clean_url = url.strip()
    if not clean_url:
        raise SSRFValidationError("URL cannot be empty.")

    parsed = urllib.parse.urlparse(clean_url)

    if parsed.scheme.lower() != "https":
        raise SSRFValidationError(f"Invalid URL scheme '{parsed.scheme}'. Only 'https' is permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise SSRFValidationError("URL must include a valid hostname.")

    if parsed.port and parsed.port != 443:
        raise SSRFValidationError(f"Port {parsed.port} is not allowed. Only standard HTTPS port 443 is permitted.")

    # Block well-known metadata hostnames
    low_host = hostname.lower()
    if low_host in ("localhost", "metadata.google.internal", "instance-data"):
        raise SSRFValidationError(f"Access to internal hostname '{hostname}' is forbidden.")

    # Resolve hostname to IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SSRFValidationError(f"Could not resolve hostname '{hostname}': {e}")

    for entry in addr_info:
        ip_str = entry[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if ip_obj.is_loopback:
            raise SSRFValidationError(f"Resolved IP {ip_str} is a loopback address (SSRF risk).")
        if ip_obj.is_link_local:
            raise SSRFValidationError(f"Resolved IP {ip_str} is a link-local/cloud metadata address (SSRF risk).")
        if ip_obj.is_private:
            raise SSRFValidationError(f"Resolved IP {ip_str} is a private network address (SSRF risk).")
        if ip_obj.is_multicast or ip_obj.is_reserved:
            raise SSRFValidationError(f"Resolved IP {ip_str} is a multicast/reserved address.")

    return clean_url
